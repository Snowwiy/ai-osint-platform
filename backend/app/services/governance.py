from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.admin_settings import AdminSettings
from app.models.audit_log import AuditLog
from app.models.investigation import Investigation
from app.models.investigation_note import InvestigationNote
from app.models.investigation_task import InvestigationTask
from app.models.report import Report
from app.models.user import User
from app.schemas.governance import (
    AdminOverviewResponse,
    AdminSettingsResponse,
    AdminSettingsUpdate,
    AuditPolicySettings,
    ExportControlSettings,
    FeatureAvailabilityResponse,
    FeatureFlagName,
    FeatureFlagSettings,
    GeneralSettings,
    ReportBrandingSettings,
    RetentionSettings,
    RetentionStatusResponse,
    RetentionUpdate,
    SecuritySettings,
)
from app.services.audit import record_event
from app.services.demo import set_demo_workspace_enabled

logger = logging.getLogger(__name__)
SETTINGS_ID = uuid.UUID("50000000-0000-4000-8000-000000000001")


class FeatureDisabledError(Exception):
    def __init__(self, feature: FeatureFlagName) -> None:
        self.feature = feature
        super().__init__(f"Feature '{feature}' is disabled by an administrator.")


def default_general_settings() -> GeneralSettings:
    return GeneralSettings()


def default_security_settings() -> SecuritySettings:
    return SecuritySettings()


def default_retention_settings() -> RetentionSettings:
    return RetentionSettings()


def default_export_controls() -> ExportControlSettings:
    return ExportControlSettings()


def default_report_branding() -> ReportBrandingSettings:
    return ReportBrandingSettings(
        company_name=settings.REPORT_COMPANY_NAME or "RavenTech",
        logo_path=settings.REPORT_LOGO_PATH,
        primary_color=settings.REPORT_PRIMARY_COLOR,
        secondary_color=settings.REPORT_SECONDARY_COLOR,
    )


def default_audit_policy() -> AuditPolicySettings:
    return AuditPolicySettings()


def default_feature_flags() -> FeatureFlagSettings:
    return FeatureFlagSettings(
        enable_demo_mode=settings.ENABLE_DEMO_MODE and not settings.is_production
    )


async def get_admin_settings(db: AsyncSession) -> AdminSettingsResponse:
    row = await _settings_row(db)
    return _settings_response(row)


async def update_admin_settings(
    db: AsyncSession,
    user: User,
    body: AdminSettingsUpdate,
) -> AdminSettingsResponse:
    row = await _settings_row(db)
    changed: list[str] = []
    if body.general is not None:
        row.general = body.general.model_dump()
        changed.append("general")
    if body.security is not None:
        row.security = body.security.model_dump()
        changed.append("security")
    if body.export_controls is not None:
        row.export_controls = body.export_controls.model_dump()
        changed.append("export_controls")
    if body.report_branding is not None:
        row.report_branding = body.report_branding.model_dump()
        changed.append("report_branding")
    if body.audit_policy is not None:
        row.audit_policy = body.audit_policy.model_dump()
        changed.append("audit_policy")
    row.updated_by = user.id
    db.add(row)
    await db.flush()
    await db.refresh(row)
    await record_event(
        db,
        action="admin.settings_updated",
        actor_id=user.id,
        resource_type="admin_settings",
        resource_id=row.id,
        metadata={"sections": changed},
    )
    if body.export_controls is not None:
        await record_event(
            db,
            action="admin.export_controls_updated",
            actor_id=user.id,
            resource_type="admin_settings",
            resource_id=row.id,
            metadata={"enabled_formats": _enabled_export_formats(body.export_controls)},
        )
    if body.report_branding is not None:
        await record_event(
            db,
            action="admin.branding_updated",
            actor_id=user.id,
            resource_type="admin_settings",
            resource_id=row.id,
            metadata={
                "company_name": body.report_branding.company_name,
                "confidentiality_label": (
                    body.report_branding.confidentiality_label
                ),
            },
        )
    return _settings_response(row)


async def get_feature_availability(
    db: AsyncSession,
) -> FeatureAvailabilityResponse:
    flags = await get_feature_flags(db)
    controls = await get_export_controls(db)
    return FeatureAvailabilityResponse(
        feature_flags=flags,
        allowed_export_formats=cast(
            list[Literal["pdf", "docx", "html", "md"]],
            _enabled_export_formats(controls),
        ),
    )


async def get_feature_flags(db: AsyncSession) -> FeatureFlagSettings:
    try:
        row = await _settings_row(db)
    except Exception as exc:
        logger.warning("Feature flags unavailable; using safe defaults: %s", exc)
        await db.rollback()
        return default_feature_flags()
    return _model_from_json(
        FeatureFlagSettings,
        row.feature_flags,
        default_feature_flags(),
    )


async def update_feature_flags(
    db: AsyncSession,
    user: User,
    feature_flags: FeatureFlagSettings,
) -> FeatureAvailabilityResponse:
    if settings.is_production and feature_flags.enable_demo_mode:
        feature_flags = feature_flags.model_copy(update={"enable_demo_mode": False})
    row = await _settings_row(db)
    previous = _model_from_json(
        FeatureFlagSettings,
        row.feature_flags,
        default_feature_flags(),
    )
    row.feature_flags = feature_flags.model_dump()
    row.updated_by = user.id
    db.add(row)
    await db.flush()
    await db.refresh(row)
    changed = [
        name
        for name, enabled in feature_flags.model_dump().items()
        if previous.model_dump().get(name) != enabled
    ]
    await record_event(
        db,
        action="admin.feature_flag_updated",
        actor_id=user.id,
        resource_type="admin_settings",
        resource_id=row.id,
        metadata={"changed": changed},
    )
    if previous.enable_demo_mode != feature_flags.enable_demo_mode:
        await set_demo_workspace_enabled(
            db,
            user,
            enabled=feature_flags.enable_demo_mode,
        )
    controls = await get_export_controls(db)
    return FeatureAvailabilityResponse(
        feature_flags=feature_flags,
        allowed_export_formats=cast(
            list[Literal["pdf", "docx", "html", "md"]],
            _enabled_export_formats(controls),
        ),
    )


async def ensure_feature_enabled(
    db: AsyncSession,
    feature: FeatureFlagName,
) -> None:
    flags = await get_feature_flags(db)
    if not getattr(flags, feature):
        raise FeatureDisabledError(feature)


async def get_export_controls(db: AsyncSession) -> ExportControlSettings:
    row = await _settings_row(db)
    return _model_from_json(
        ExportControlSettings,
        row.export_controls,
        default_export_controls(),
    )


async def get_report_branding(db: AsyncSession) -> ReportBrandingSettings:
    row = await _settings_row(db)
    return _model_from_json(
        ReportBrandingSettings,
        row.report_branding,
        default_report_branding(),
    )


async def ensure_export_format_allowed(db: AsyncSession, report_format: str) -> None:
    controls = await get_export_controls(db)
    allowed = {
        "pdf": controls.allow_pdf_export,
        "docx": controls.allow_docx_export,
        "html": controls.allow_html_export,
        "md": controls.allow_markdown_export,
    }
    if not allowed.get(report_format, False):
        raise FeatureDisabledError("enable_report_exports")


async def get_retention_status(db: AsyncSession) -> RetentionStatusResponse:
    row = await _settings_row(db)
    retention = _model_from_json(
        RetentionSettings,
        row.retention,
        default_retention_settings(),
    )
    return RetentionStatusResponse(
        retention=retention,
        eligible_for_archive=await _retention_eligibility(db, retention),
    )


async def update_retention(
    db: AsyncSession,
    user: User,
    body: RetentionUpdate,
) -> RetentionStatusResponse:
    row = await _settings_row(db)
    row.retention = body.retention.model_dump()
    row.updated_by = user.id
    db.add(row)
    await db.flush()
    await db.refresh(row)
    await record_event(
        db,
        action="admin.retention_updated",
        actor_id=user.id,
        resource_type="admin_settings",
        resource_id=row.id,
        metadata={"policies": body.retention.model_dump()},
    )
    return RetentionStatusResponse(
        retention=body.retention,
        eligible_for_archive=await _retention_eligibility(db, body.retention),
    )


async def get_admin_overview(db: AsyncSession) -> AdminOverviewResponse:
    settings_row = await _settings_row(db)
    flags = _model_from_json(
        FeatureFlagSettings,
        settings_row.feature_flags,
        default_feature_flags(),
    )
    retention = _model_from_json(
        RetentionSettings,
        settings_row.retention,
        default_retention_settings(),
    )
    storage_bytes = (
        await db.execute(
            select(func.coalesce(func.sum(Report.file_size_bytes), 0))
        )
    ).scalar_one()
    return AdminOverviewResponse(
        total_users=await _count(db, User),
        active_investigations=await _count_where(
            db,
            Investigation,
            Investigation.status != "archived",
        ),
        archived_investigations=await _count_where(
            db,
            Investigation,
            Investigation.status == "archived",
        ),
        reports_generated=await _count(db, Report),
        audit_events=await _count(db, AuditLog),
        report_storage_bytes=int(storage_bytes or 0),
        feature_flags_enabled=sum(flags.model_dump().values()),
        retention_policies_configured=len(retention.model_dump()),
        updated_at=settings_row.updated_at,
    )


async def _settings_row(db: AsyncSession) -> AdminSettings:
    row = await db.get(AdminSettings, SETTINGS_ID)
    if row is not None:
        return row
    row = AdminSettings(
        id=SETTINGS_ID,
        general=default_general_settings().model_dump(),
        security=default_security_settings().model_dump(),
        retention=default_retention_settings().model_dump(),
        export_controls=default_export_controls().model_dump(),
        report_branding=default_report_branding().model_dump(),
        audit_policy=default_audit_policy().model_dump(),
        feature_flags=default_feature_flags().model_dump(),
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row


def _settings_response(row: AdminSettings) -> AdminSettingsResponse:
    return AdminSettingsResponse(
        id=row.id,
        general=_model_from_json(
            GeneralSettings,
            row.general,
            default_general_settings(),
        ),
        security=_model_from_json(
            SecuritySettings,
            row.security,
            default_security_settings(),
        ),
        retention=_model_from_json(
            RetentionSettings,
            row.retention,
            default_retention_settings(),
        ),
        export_controls=_model_from_json(
            ExportControlSettings,
            row.export_controls,
            default_export_controls(),
        ),
        report_branding=_model_from_json(
            ReportBrandingSettings,
            row.report_branding,
            default_report_branding(),
        ),
        audit_policy=_model_from_json(
            AuditPolicySettings,
            row.audit_policy,
            default_audit_policy(),
        ),
        feature_flags=_model_from_json(
            FeatureFlagSettings,
            row.feature_flags,
            default_feature_flags(),
        ),
        updated_by=row.updated_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _model_from_json(
    model_type: type[Any],
    value: object,
    default: Any,
) -> Any:
    if not isinstance(value, dict):
        return default
    merged = {**default.model_dump(), **value}
    try:
        return model_type.model_validate(merged)
    except Exception:
        return default


async def _retention_eligibility(
    db: AsyncSession,
    retention: RetentionSettings,
) -> dict[str, int]:
    return {
        "investigations": await _eligible_count(
            db,
            Investigation,
            Investigation.updated_at,
            retention.investigations,
            Investigation.status != "archived",
        ),
        "audit_logs": await _eligible_count(
            db,
            AuditLog,
            AuditLog.created_at,
            retention.audit_logs,
        ),
        "reports": await _eligible_count(
            db,
            Report,
            Report.created_at,
            retention.reports,
            Report.status != "archived",
        ),
        "notes": await _eligible_count(
            db,
            InvestigationNote,
            InvestigationNote.updated_at,
            retention.notes,
            InvestigationNote.archived.is_(False),
        ),
        "tasks": await _eligible_count(
            db,
            InvestigationTask,
            InvestigationTask.updated_at,
            retention.tasks,
            InvestigationTask.archived_at.is_(None),
        ),
        "exports": await _eligible_count(
            db,
            Report,
            Report.generated_at,
            retention.exports,
            Report.generated_at.is_not(None),
        ),
    }


async def _eligible_count(
    db: AsyncSession,
    model: type[Any],
    date_column: Any,
    policy: str,
    *conditions: Any,
) -> int:
    days = _retention_days(policy)
    if days is None:
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=days)
    statement = (
        select(func.count())
        .select_from(model)
        .where(date_column.is_not(None), date_column <= cutoff, *conditions)
    )
    return int((await db.execute(statement)).scalar_one())


def _retention_days(policy: str) -> int | None:
    values = {
        "30_days": 30,
        "90_days": 90,
        "180_days": 180,
        "365_days": 365,
    }
    return values.get(policy)


async def _count(db: AsyncSession, model: type[Any]) -> int:
    return int(
        (await db.execute(select(func.count()).select_from(model))).scalar_one()
    )


async def _count_where(
    db: AsyncSession,
    model: type[Any],
    condition: Any,
) -> int:
    return int(
        (
            await db.execute(
                select(func.count()).select_from(model).where(condition)
            )
        ).scalar_one()
    )


def _enabled_export_formats(controls: ExportControlSettings) -> list[str]:
    values = {
        "pdf": controls.allow_pdf_export,
        "docx": controls.allow_docx_export,
        "html": controls.allow_html_export,
        "md": controls.allow_markdown_export,
    }
    return [name for name, enabled in values.items() if enabled]
