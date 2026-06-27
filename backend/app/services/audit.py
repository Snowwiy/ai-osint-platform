from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, TypeVar

from sqlalchemy import Select, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.schemas.audit import AuditLogResponse

logger = logging.getLogger(__name__)
_SelectRow = TypeVar("_SelectRow")


async def record_event(
    db: AsyncSession,
    *,
    action: str,
    actor_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    investigation_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    try:
        if not await _audit_schema_available(db):
            logger.warning(
                "audit.record_event skipped because audit_logs is not migrated"
            )
            return
        policy_key = _audit_policy_key(action)
        if policy_key is not None and not await _audit_policy_enabled(db, policy_key):
            return
        effective_actor_id = actor_id or user_id
        event_metadata = metadata if metadata is not None else details or {}
        db.add(
            AuditLog(
                user_id=effective_actor_id,
                actor_id=effective_actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                investigation_id=investigation_id,
                ip_address=ip_address,
                user_agent=user_agent,
                details=event_metadata,
                event_metadata=event_metadata,
            )
        )
    except Exception:
        logger.exception("audit.record_event failed for action=%s", action)


async def list_audit_events(
    db: AsyncSession,
    *,
    action: str | None = None,
    resource_type: str | None = None,
    actor_id: uuid.UUID | None = None,
    investigation_id: uuid.UUID | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[AuditLog]]:
    if not await _audit_schema_available(db):
        logger.warning("audit.list_audit_events skipped: audit_logs is not migrated")
        return 0, []
    stmt = _audit_filters(
        select(AuditLog),
        action=action,
        resource_type=resource_type,
        actor_id=actor_id,
        investigation_id=investigation_id,
        start_date=start_date,
        end_date=end_date,
    )
    count_stmt = _audit_filters(
        select(func.count()).select_from(AuditLog),
        action=action,
        resource_type=resource_type,
        actor_id=actor_id,
        investigation_id=investigation_id,
        start_date=start_date,
        end_date=end_date,
    )
    try:
        total = int((await db.execute(count_stmt)).scalar_one())
        result = await db.execute(
            stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
        )
        return total, list(result.scalars().all())
    except Exception as exc:
        logger.warning("audit.list_audit_events failed: %s", exc)
        await db.rollback()
        return 0, []


def to_audit_response(event: AuditLog) -> AuditLogResponse:
    event_metadata = _json_object(event.event_metadata)
    details = _json_object(event.details)
    return AuditLogResponse(
        id=event.id,
        actor_id=event.actor_id or event.user_id,
        action=event.action,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        investigation_id=event.investigation_id,
        ip_address=str(event.ip_address) if event.ip_address else None,
        user_agent=event.user_agent,
        metadata=event_metadata or details,
        created_at=event.created_at or event.timestamp or datetime.now(UTC),
    )


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _audit_filters(
    stmt: Select[tuple[_SelectRow]],
    *,
    action: str | None,
    resource_type: str | None,
    actor_id: uuid.UUID | None,
    investigation_id: uuid.UUID | None,
    start_date: datetime | None,
    end_date: datetime | None,
) -> Select[tuple[_SelectRow]]:
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if investigation_id:
        stmt = stmt.where(AuditLog.investigation_id == investigation_id)
    if start_date:
        stmt = stmt.where(AuditLog.created_at >= start_date)
    if end_date:
        stmt = stmt.where(AuditLog.created_at <= end_date)
    return stmt


async def _audit_schema_available(db: AsyncSession) -> bool:
    try:
        result = await db.execute(
            text(
                """
                SELECT count(*)
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'audit_logs'
                  AND column_name IN (
                    'actor_id',
                    'investigation_id',
                    'metadata',
                    'created_at'
                  )
                """
            )
        )
    except Exception as exc:
        logger.warning("audit schema check failed: %s", exc)
        await db.rollback()
        return False
    return int(result.scalar_one()) == 4


def _audit_policy_key(action: str) -> str | None:
    if action in {"auth.login.success", "auth.logout"}:
        return "audit_login_events"
    if action == "report.downloaded":
        return "audit_report_downloads"
    if action == "recon.executed":
        return "audit_recon_runs"
    if action.startswith("investigation.member_") or action in {
        "investigation.owner_transferred",
        "investigation.owner_changed",
    }:
        return "audit_member_changes"
    if action in {"data.exported", "audit.exported"}:
        return "audit_data_exports"
    return None


async def _audit_policy_enabled(db: AsyncSession, policy_key: str) -> bool:
    table_exists = await db.execute(
        text("SELECT to_regclass('admin_settings') IS NOT NULL")
    )
    if not bool(table_exists.scalar_one()):
        return True
    result = await db.execute(
        text(
            """
            SELECT COALESCE(
                (audit_policy ->> :policy_key)::boolean,
                true
            )
            FROM admin_settings
            LIMIT 1
            """
        ),
        {"policy_key": policy_key},
    )
    value = result.scalar_one_or_none()
    return True if value is None else bool(value)
