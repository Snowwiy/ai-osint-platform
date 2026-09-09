from __future__ import annotations

import base64
import json
import os
import zipfile
from datetime import UTC, datetime
from io import BytesIO
from typing import Any, Literal

from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.knowledge_document import KnowledgeDocument
from app.models.report import Report
from app.models.report_template import ReportTemplate
from app.schemas.operations_center import (
    BackupPackageResponse,
    DiagnosticsPackageResponse,
    EnvironmentValidationItem,
    EnvironmentValidationResponse,
    OperationalStatus,
    OperationsComponentStatus,
    OperationsStatusResponse,
    RecentOperationEvent,
    ReleaseInfo,
    RestoreValidationRequest,
    RestoreValidationResponse,
    StorageMetrics,
    ValidationStatus,
)
from app.services.governance import (
    get_admin_settings,
    get_feature_availability,
    get_retention_status,
)
from app.services.health import health_snapshot
from app.services.release import get_release_metadata

STARTED_AT = datetime.now(UTC)
BACKUP_SCHEMA_VERSION = "raventech-backup-v1"
DIAGNOSTICS_SCHEMA_VERSION = "raventech-diagnostics-v1"


async def get_operations_status(
    db: AsyncSession,
    redis: Any,
) -> OperationsStatusResponse:
    health = await health_snapshot(redis, include_ready=True)
    release = await _release_info(db)
    storage = await _storage_metrics(db)
    components = _components_from_health(health)
    status = _overall_status(components)
    return OperationsStatusResponse(
        generated_at=datetime.now(UTC),
        status=status,
        uptime_seconds=max(0, int((datetime.now(UTC) - STARTED_AT).total_seconds())),
        release=release,
        components=components,
        storage=storage,
        recent_operations=await _recent_operation_events(db),
    )


async def get_environment_validation() -> EnvironmentValidationResponse:
    items = [
        _configured(
            "DATABASE_URL",
            "backend",
            bool(settings.DATABASE_URL),
            "Database connection string is present.",
            "DATABASE_URL is required for PostgreSQL connectivity.",
            misconfigured=not settings.DATABASE_URL.startswith("postgresql+asyncpg://"),
            misconfigured_detail="DATABASE_URL should use postgresql+asyncpg://.",
        ),
        _configured(
            "REDIS_URL",
            "backend",
            bool(settings.REDIS_URL),
            "Redis connection string is present.",
            "REDIS_URL is required for cache, rate limiting, and workers.",
            misconfigured=not settings.REDIS_URL.startswith("redis://"),
            misconfigured_detail="REDIS_URL should use redis://.",
        ),
        _configured(
            "SECRET_KEY / APP_SECRET_KEY",
            "backend",
            bool(settings.APP_SECRET_KEY),
            "Application signing key is present.",
            "A signing key is required for JWT authentication.",
            misconfigured=settings.has_weak_secret_key,
            misconfigured_detail="Signing key is too weak for this environment.",
        ),
        _configured(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            "backend",
            settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0,
            "Access token expiration is configured.",
            "Token expiration must be greater than zero.",
        ),
        EnvironmentValidationItem(
            name="PUBLIC_REGISTRATION_ENABLED",
            scope="backend",
            status="configured",
            required=False,
            detail=(
                "Public registration is enabled."
                if settings.PUBLIC_REGISTRATION_ENABLED
                else "Public registration is disabled by default."
            ),
        ),
        EnvironmentValidationItem(
            name="REGISTRATION_REQUIRES_APPROVAL",
            scope="backend",
            status="configured",
            required=False,
            detail=(
                "New registered users require administrator approval."
                if settings.REGISTRATION_REQUIRES_APPROVAL
                else "New registered users are active immediately."
            ),
        ),
        EnvironmentValidationItem(
            name="REGISTRATION_INVITE_CODE",
            scope="backend",
            status=(
                "configured"
                if settings.REGISTRATION_INVITE_CODE.strip()
                else "missing"
            ),
            required=False,
            detail=(
                "Registration invite code is configured."
                if settings.REGISTRATION_INVITE_CODE.strip()
                else "No registration invite code is configured."
            ),
        ),
        EnvironmentValidationItem(
            name="DEFAULT_REGISTERED_USER_ROLE",
            scope="backend",
            status="configured",
            required=False,
            detail=(
                "Registered users are never created as admins. Effective role: "
                f"{settings.effective_registered_user_role}."
            ),
        ),
        _configured(
            "ANTHROPIC_API_KEY",
            "ai",
            bool(settings.ANTHROPIC_API_KEY),
            "AI provider key is configured.",
            "AI analysis will use deterministic fallback when this key is missing.",
            required=False,
        ),
        _configured(
            "REPORT_COMPANY_NAME",
            "reports",
            bool(settings.REPORT_COMPANY_NAME),
            "Report company name is configured.",
            "Reports fall back to RavenTech branding when missing.",
            required=False,
        ),
        _configured(
            "REPORT_LOGO_PATH",
            "reports",
            bool(settings.REPORT_LOGO_PATH),
            "Report logo path is configured.",
            "Reports use text branding when no logo path is configured.",
            required=False,
        ),
        _configured(
            "REPORT_PRIMARY_COLOR",
            "reports",
            _valid_hex(settings.REPORT_PRIMARY_COLOR),
            "Report primary color is configured.",
            "Use #RRGGBB for report primary color.",
            required=False,
        ),
        _configured(
            "REPORT_SECONDARY_COLOR",
            "reports",
            _valid_hex(settings.REPORT_SECONDARY_COLOR),
            "Report secondary color is configured.",
            "Use #RRGGBB for report secondary color.",
            required=False,
        ),
        _configured(
            "CHROMA_DATA_PATH",
            "storage",
            bool(settings.CHROMA_DATA_PATH),
            "Local knowledge storage path is configured.",
            "CHROMA_DATA_PATH is required when local knowledge indexing is enabled.",
            required=False,
        ),
        EnvironmentValidationItem(
            name="VITE_API_BASE_URL",
            scope="frontend",
            status="configured",
            required=True,
            detail=(
                "Frontend API base URL is validated in the browser build. "
                "This backend confirms the API is reachable without exposing values."
            ),
        ),
    ]
    return EnvironmentValidationResponse(generated_at=datetime.now(UTC), items=items)


async def build_diagnostics_package(
    db: AsyncSession,
    redis: Any,
) -> DiagnosticsPackageResponse:
    settings_response = await get_admin_settings(db)
    feature_response = await get_feature_availability(db)
    retention_response = await get_retention_status(db)
    return DiagnosticsPackageResponse(
        schema_version=DIAGNOSTICS_SCHEMA_VERSION,
        generated_at=datetime.now(UTC),
        health=_scrub_secrets(await health_snapshot(redis, include_ready=True)),
        release=await _release_info(db),
        environment_validation=await get_environment_validation(),
        enabled_modules=feature_response.feature_flags.model_dump(),
        retention_config=retention_response.retention.model_dump(),
        governance_config={
            "general": settings_response.general.model_dump(),
            "security": settings_response.security.model_dump(),
            "audit_policy": settings_response.audit_policy.model_dump(),
            "export_controls": settings_response.export_controls.model_dump(),
        },
        report_configuration=settings_response.report_branding.model_dump(),
        storage=await _storage_metrics(db),
    )


async def build_backup_package(db: AsyncSession) -> BackupPackageResponse:
    settings_response = await get_admin_settings(db)
    retention_response = await get_retention_status(db)
    records = {
        "investigations": await _investigation_records(db),
        "findings": await _finding_records(db),
        "reports": await _report_records(db),
        "templates": await _template_records(db),
        "settings": {
            "general": settings_response.general.model_dump(),
            "security": settings_response.security.model_dump(),
            "export_controls": settings_response.export_controls.model_dump(),
            "report_branding": settings_response.report_branding.model_dump(),
            "audit_policy": settings_response.audit_policy.model_dump(),
            "feature_flags": settings_response.feature_flags.model_dump(),
        },
        "governance": {"retention": retention_response.retention.model_dump()},
        "knowledge_metadata": await _knowledge_records(db),
    }
    return BackupPackageResponse(
        schema_version=BACKUP_SCHEMA_VERSION,
        generated_at=datetime.now(UTC),
        app_version=settings.APP_VERSION,
        manifest={
            "format": "json",
            "contains_secrets": False,
            "restore_mode": "dry_run_supported",
            "record_counts": _record_counts(records),
        },
        records=records,
    )


def package_to_zip(filename: str, payload: dict[str, Any]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(filename, json.dumps(payload, default=str, indent=2))
        archive.writestr(
            "README.txt",
            (
                "RavenTech OSINT operations export. This package intentionally "
                "excludes tokens, passwords, API keys, and other secrets.\n"
            ),
        )
    return buffer.getvalue()


def validate_restore_payload(
    body: RestoreValidationRequest,
) -> RestoreValidationResponse:
    errors: list[str] = []
    warnings: list[str] = []
    payload: dict[str, Any] | None = body.backup
    if payload is None and body.archive_base64:
        payload = _decode_backup_archive(body.archive_base64, errors)
    if payload is None:
        errors.append("No backup payload or ZIP archive was provided.")
        return _restore_response(body.dry_run, None, errors, warnings)

    schema_version = _string_or_none(payload.get("schema_version"))
    if schema_version != BACKUP_SCHEMA_VERSION:
        errors.append("Backup schema version is not supported.")
    records = payload.get("records")
    if not isinstance(records, dict):
        errors.append("Backup records object is missing or malformed.")
        records = {}

    required_sections = {
        "investigations",
        "findings",
        "reports",
        "templates",
        "settings",
        "governance",
        "knowledge_metadata",
    }
    missing = sorted(section for section in required_sections if section not in records)
    if missing:
        warnings.append(f"Backup is missing optional sections: {', '.join(missing)}.")

    record_counts = _record_counts(records)
    if not body.dry_run:
        warnings.append("Restore writes are not enabled in Phase 5A; dry-run only.")

    return RestoreValidationResponse(
        dry_run=True,
        valid=not errors,
        schema_version=schema_version,
        compatible=schema_version == BACKUP_SCHEMA_VERSION,
        corruption_detected=bool(errors),
        record_counts=record_counts,
        warnings=warnings,
        errors=errors,
    )


async def _release_info(db: AsyncSession) -> ReleaseInfo:
    metadata = await get_release_metadata(db)
    current_migration = await _current_migration(db)
    head_migration = _head_migration()
    return ReleaseInfo(
        app_name=metadata.app_name,
        version=metadata.version,
        release_channel=metadata.release_channel,
        build_date=metadata.build_date,
        git_commit=metadata.git_commit,
        build=os.getenv("APP_BUILD", "local"),
        environment=metadata.environment,
        current_migration=current_migration,
        head_migration=head_migration,
        migration_status="current" if current_migration == head_migration else "drift",
        database_version=await _database_version(db),
    )


async def _storage_metrics(db: AsyncSession) -> StorageMetrics:
    return StorageMetrics(
        investigations_count=await _count(db, Investigation),
        findings_count=await _count(db, Finding),
        reports_count=await _count(db, Report),
        templates_count=await _count(db, ReportTemplate),
        audit_events_count=await _count(db, AuditLog),
        knowledge_documents_count=await _count(db, KnowledgeDocument),
        report_storage_bytes=await _report_storage_bytes(db),
        database_size_bytes=await _database_size_bytes(db),
    )


async def _recent_operation_events(db: AsyncSession) -> list[RecentOperationEvent]:
    actions = (
        "admin.settings_updated",
        "admin.feature_flag_updated",
        "admin.retention_updated",
        "admin.export_controls_updated",
        "admin.branding_updated",
        "data.exported",
        "diagnostics.generated",
        "restore.validated",
        "data_quality.scan_completed",
        "data_quality.issue_acknowledged",
        "data_quality.issue_ignored",
        "data_quality.issue_resolved",
        "maintenance.dry_run_completed",
        "maintenance.stale_notifications_archived",
    )
    try:
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.action.in_(actions))
            .order_by(AuditLog.created_at.desc())
            .limit(10)
        )
        return [
            RecentOperationEvent(
                action=event.action,
                resource_type=event.resource_type,
                created_at=event.created_at,
            )
            for event in result.scalars().all()
        ]
    except Exception:
        await db.rollback()
        return []


def _components_from_health(
    health: dict[str, Any],
) -> dict[str, OperationsComponentStatus]:
    checks = health.get("checks", {})
    components: dict[str, OperationsComponentStatus] = {}
    for name in (
        "database",
        "redis",
        "migrations",
        "ai_provider",
        "storage",
        "worker",
    ):
        raw = checks.get(name, {})
        status = _status_from_health(raw.get("status"))
        components[name] = OperationsComponentStatus(
            status=status,
            detail=_redact(str(raw.get("detail", ""))),
            metadata=_safe_metadata(raw),
        )
    storage_component = components.get(
        "storage",
        OperationsComponentStatus(status="degraded"),
    )
    components["local_knowledge"] = OperationsComponentStatus(
        status=storage_component.status,
        detail="Local knowledge storage uses configured application storage.",
        metadata={"path_configured": bool(settings.CHROMA_DATA_PATH)},
    )
    return components


def _overall_status(
    components: dict[str, OperationsComponentStatus],
) -> OperationalStatus:
    statuses = [component.status for component in components.values()]
    if "unavailable" in statuses:
        return "unavailable"
    if "degraded" in statuses:
        return "degraded"
    return "healthy"


def _status_from_health(status: object) -> OperationalStatus:
    if status == "ok":
        return "healthy"
    if status == "degraded":
        return "degraded"
    return "unavailable"


def _safe_metadata(raw: object) -> dict[str, str | bool | int | None]:
    if not isinstance(raw, dict):
        return {}
    blocked = {"detail"}
    safe: dict[str, str | bool | int | None] = {}
    for key, value in raw.items():
        if key in blocked:
            continue
        if isinstance(value, (str, bool, int)) or value is None:
            safe[key] = _redact(value) if isinstance(value, str) else value
        elif isinstance(value, dict):
            safe[key] = str({inner_key: "configured" for inner_key in value})
    return safe


def _scrub_secrets(value: object) -> Any:
    if isinstance(value, dict):
        return {key: _scrub_secrets(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub_secrets(item) for item in value]
    if isinstance(value, str):
        return _redact(value)
    return value


def _redact(value: str) -> str:
    redacted = value
    sensitive_values = (
        settings.APP_SECRET_KEY,
        settings.DATABASE_URL,
        settings.REDIS_URL,
        settings.ANTHROPIC_API_KEY,
        settings.OPENAI_API_KEY,
        settings.VT_API_KEY,
        settings.ABUSEIPDB_API_KEY,
        settings.REGISTRATION_INVITE_CODE,
    )
    for secret in sensitive_values:
        if secret and len(secret) >= 4:
            redacted = redacted.replace(secret, "[redacted]")
    return redacted


def _configured(
    name: str,
    scope: Literal["backend", "frontend", "reports", "ai", "storage"],
    present: bool,
    configured_detail: str,
    missing_detail: str,
    *,
    required: bool = True,
    misconfigured: bool = False,
    misconfigured_detail: str = "",
) -> EnvironmentValidationItem:
    status: ValidationStatus = "configured"
    detail = configured_detail
    if not present:
        status = "missing"
        detail = missing_detail
    elif misconfigured:
        status = "misconfigured"
        detail = misconfigured_detail
    return EnvironmentValidationItem(
        name=name,
        scope=scope,
        status=status,
        required=required,
        detail=detail,
    )


def _valid_hex(value: str) -> bool:
    clean = value.strip()
    if len(clean) != 7 or not clean.startswith("#"):
        return False
    try:
        int(clean[1:], 16)
    except ValueError:
        return False
    return True


async def _count(db: AsyncSession, model: type[Any]) -> int:
    try:
        return int((await db.execute(select(func.count(model.id)))).scalar_one())
    except Exception:
        await db.rollback()
        return 0


async def _report_storage_bytes(db: AsyncSession) -> int:
    try:
        value = (
            await db.execute(
                select(func.coalesce(func.sum(Report.file_size_bytes), 0))
            )
        ).scalar_one()
        return int(value or 0)
    except Exception:
        await db.rollback()
        return 0


async def _database_size_bytes(db: AsyncSession) -> int:
    try:
        value = (
            await db.execute(text("SELECT pg_database_size(current_database())"))
        ).scalar_one()
        return int(value or 0)
    except Exception:
        await db.rollback()
        return 0


async def _database_version(db: AsyncSession) -> str:
    try:
        value = (await db.execute(text("SELECT version()"))).scalar_one_or_none()
        return str(value or "unknown").split(",")[0]
    except Exception:
        await db.rollback()
        return "unknown"


async def _current_migration(db: AsyncSession) -> str:
    try:
        value = (
            await db.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one_or_none()
        return str(value or "")
    except Exception:
        await db.rollback()
        return ""


def _head_migration() -> str:
    backend_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    script = ScriptDirectory(os.path.join(backend_root, "alembic"))
    return str(script.get_current_head())


async def _investigation_records(db: AsyncSession) -> list[dict[str, Any]]:
    stmt = select(
        Investigation.id,
        Investigation.title,
        Investigation.description,
        Investigation.status,
        Investigation.stage,
        Investigation.priority,
        Investigation.owner_id,
        Investigation.authorization_statement,
        Investigation.scope_definition,
        Investigation.business_impact,
        Investigation.due_date,
        Investigation.created_at,
        Investigation.updated_at,
    )
    return await _rows_as_dicts(db, stmt)


async def _finding_records(db: AsyncSession) -> list[dict[str, Any]]:
    stmt = select(
        Finding.id,
        Finding.investigation_id,
        Finding.title,
        Finding.description,
        Finding.severity,
        Finding.status,
        Finding.confidence_score,
        Finding.risk_score,
        Finding.source,
        Finding.evidence_summary,
        Finding.remediation_status,
        Finding.remediation_notes,
        Finding.verification_notes,
        Finding.created_at,
        Finding.updated_at,
    )
    return await _rows_as_dicts(db, stmt)


async def _report_records(db: AsyncSession) -> list[dict[str, Any]]:
    stmt = select(
        Report.id,
        Report.investigation_id,
        Report.template_id,
        Report.title,
        Report.report_type,
        Report.report_format,
        Report.status,
        Report.file_size_bytes,
        Report.report_metadata,
        Report.html_content,
        Report.markdown_content,
        Report.progress_label,
        Report.failure_reason,
        Report.generated_at,
        Report.created_at,
    )
    return await _rows_as_dicts(db, stmt)


async def _template_records(db: AsyncSession) -> list[dict[str, Any]]:
    stmt = select(
        ReportTemplate.id,
        ReportTemplate.name,
        ReportTemplate.description,
        ReportTemplate.report_type,
        ReportTemplate.sections,
        ReportTemplate.is_default,
        ReportTemplate.is_active,
        ReportTemplate.created_at,
        ReportTemplate.updated_at,
    )
    return await _rows_as_dicts(db, stmt)


async def _knowledge_records(db: AsyncSession) -> list[dict[str, Any]]:
    stmt = select(
        KnowledgeDocument.id,
        KnowledgeDocument.source_type,
        KnowledgeDocument.title,
        KnowledgeDocument.hash,
        KnowledgeDocument.tags,
        KnowledgeDocument.created_at,
        KnowledgeDocument.updated_at,
    )
    return await _rows_as_dicts(db, stmt)


async def _rows_as_dicts(
    db: AsyncSession,
    stmt: Any,
) -> list[dict[str, Any]]:
    try:
        result = await db.execute(stmt)
        return [dict(row._mapping) for row in result.all()]
    except Exception:
        await db.rollback()
        return []


def _record_counts(records: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key, value in records.items():
        if isinstance(value, list):
            counts[key] = len(value)
        elif isinstance(value, dict):
            counts[key] = len(value)
        else:
            counts[key] = 0
    return counts


def _decode_backup_archive(
    archive_base64: str,
    errors: list[str],
) -> dict[str, Any] | None:
    try:
        decoded = base64.b64decode(archive_base64, validate=True)
        with zipfile.ZipFile(BytesIO(decoded)) as archive:
            names = [
                name
                for name in archive.namelist()
                if name.endswith(".json") and not name.startswith("__")
            ]
            if not names:
                errors.append("ZIP archive does not contain a JSON backup.")
                return None
            with archive.open(names[0]) as handle:
                payload = json.loads(handle.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        errors.append("Backup archive could not be decoded or parsed.")
        return None


def _restore_response(
    dry_run: bool,
    schema_version: str | None,
    errors: list[str],
    warnings: list[str],
) -> RestoreValidationResponse:
    return RestoreValidationResponse(
        dry_run=dry_run,
        valid=False,
        schema_version=schema_version,
        compatible=False,
        corruption_detected=True,
        record_counts={},
        warnings=warnings,
        errors=errors,
    )


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None
