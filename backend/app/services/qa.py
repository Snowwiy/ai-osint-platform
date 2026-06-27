from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.investigation import Investigation
from app.models.report_template import ReportTemplate
from app.schemas.qa import AdminQaStatusResponse, QaComponentStatus
from app.services.demo import DEMO_INVESTIGATION_ID, demo_workspace_ready
from app.services.governance import get_feature_flags
from app.services.health import health_snapshot


async def get_qa_status(
    db: AsyncSession,
    redis: Any,
) -> AdminQaStatusResponse:
    health = await health_snapshot(redis, include_ready=True)
    flags = await get_feature_flags(db)
    current_migration = await _current_migration(db)
    head_migration = _head_migration()
    template_count = await _count(db, ReportTemplate)
    active_count = await _count_where(
        db,
        Investigation.status != "archived",
    )
    archived_count = await _count_where(
        db,
        Investigation.status == "archived",
    )
    audit_count = await _count(db, AuditLog)
    demo_ready = await demo_workspace_ready(db)
    warnings = _warnings(
        health=health,
        flags=flags.model_dump(),
        current_migration=current_migration,
        head_migration=head_migration,
        template_count=template_count,
        demo_ready=demo_ready,
    )
    components = {
        name: QaComponentStatus(
            status=str(check.get("status", "error")),
            detail=_component_detail(name, check),
        )
        for name, check in health.get("checks", {}).items()
        if isinstance(check, dict)
    }
    return AdminQaStatusResponse(
        app_version=settings.APP_VERSION,
        environment=settings.APP_ENVIRONMENT,
        generated_at=datetime.now(UTC),
        current_migration=current_migration,
        head_migration=head_migration,
        migration_status=(
            "ok" if current_migration == head_migration else "degraded"
        ),
        feature_flags={
            name: bool(value) for name, value in flags.model_dump().items()
        },
        report_templates_count=template_count,
        active_investigations_count=active_count,
        archived_investigations_count=archived_count,
        audit_count=audit_count,
        demo_mode_enabled=flags.enable_demo_mode,
        demo_investigation_ready=demo_ready,
        demo_investigation_id=DEMO_INVESTIGATION_ID if demo_ready else None,
        components=components,
        warnings=warnings,
    )


async def _current_migration(db: AsyncSession) -> str:
    result = await db.execute(text("SELECT version_num FROM alembic_version"))
    return str(result.scalar_one_or_none() or "")


def _head_migration() -> str:
    backend_root = Path(__file__).resolve().parents[2]
    script = ScriptDirectory(str(backend_root / "alembic"))
    return str(script.get_current_head())


async def _count(db: AsyncSession, model: type[Any]) -> int:
    result = await db.execute(select(func.count()).select_from(model))
    return int(result.scalar_one())


async def _count_where(db: AsyncSession, condition: Any) -> int:
    result = await db.execute(
        select(func.count()).select_from(Investigation).where(condition)
    )
    return int(result.scalar_one())


def _component_detail(name: str, check: dict[str, Any]) -> str:
    if name == "migrations":
        return (
            f"Current {check.get('current', 'unknown')}; "
            f"head {check.get('head', 'unknown')}."
        )
    if name == "ai_provider" and not check.get("available"):
        return "Optional AI provider unavailable; deterministic workflows remain usable."
    if name == "worker":
        return str(check.get("detail", "Background broker check completed."))
    if name == "storage":
        paths = check.get("paths", {})
        if isinstance(paths, dict):
            return ", ".join(f"{key}: {value}" for key, value in paths.items())
    return str(check.get("detail", f"{name.replace('_', ' ').title()} check passed."))


def _warnings(
    *,
    health: dict[str, Any],
    flags: dict[str, bool],
    current_migration: str,
    head_migration: str,
    template_count: int,
    demo_ready: bool,
) -> list[str]:
    warnings: list[str] = []
    if health.get("status") != "ok":
        warnings.append(
            "Platform health is degraded. Review component details before a demo."
        )
    if current_migration != head_migration:
        warnings.append("Database migration is not at the current application head.")
    if template_count == 0:
        warnings.append("No report templates are available.")
    if flags.get("enable_demo_mode") and not demo_ready:
        warnings.append("Demo mode is enabled but the demo workspace is not ready.")
    if not flags.get("enable_report_exports", False):
        warnings.append("Report exports are disabled by governance.")
    if not flags.get("enable_audit_exports", False):
        warnings.append("Audit exports are disabled by governance.")
    return warnings
