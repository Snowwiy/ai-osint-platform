from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lan_monitoring import LanAsset, VulnerabilityBaselineFinding
from app.models.monitoring_policy import AlertSuppression
from app.models.monitoring_triage import MonitoringAlertTriage
from app.models.notification import Notification
from app.models.user import User
from app.schemas.monitoring_triage import (
    MonitoringTriageAssign,
    MonitoringTriageItem,
    MonitoringTriageListResponse,
    MonitoringTriageMute,
    MonitoringTriageResolution,
    MonitoringTriageUpdate,
    TriageSeverity,
    TriageStatus,
)
from app.services.audit import record_event

_UUID_PATTERN = re.compile(
    r"(?<![0-9a-f])([0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})(?![0-9a-f])",
    re.IGNORECASE,
)
_TERMINAL = {"resolved", "false_positive"}


class MonitoringTriageNotFoundError(Exception):
    pass


class MonitoringTriageConflictError(Exception):
    pass


class MonitoringTriageOwnerNotFoundError(Exception):
    pass


class MonitoringTriageValidationError(Exception):
    pass


async def list_triage(
    db: AsyncSession,
    user: User,
    *,
    status: TriageStatus | None,
    severity: TriageSeverity | None,
    source: str | None,
    asset_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> MonitoringTriageListResponse:
    await _ensure_user_triage(db, user)
    filters: list[Any] = [Notification.user_id == user.id]
    if status:
        filters.append(MonitoringAlertTriage.status == status)
    if severity:
        filters.append(MonitoringAlertTriage.severity == severity)
    if source:
        filters.append(MonitoringAlertTriage.source == source)
    if asset_id:
        filters.append(MonitoringAlertTriage.related_asset_id == asset_id)
    base = (
        select(MonitoringAlertTriage, Notification)
        .join(Notification, Notification.id == MonitoringAlertTriage.alert_id)
        .where(*filters)
    )
    total = int(
        (
            await db.execute(
                select(func.count())
                .select_from(MonitoringAlertTriage)
                .join(Notification, Notification.id == MonitoringAlertTriage.alert_id)
                .where(*filters)
            )
        ).scalar_one()
    )
    rows = list(
        (
            await db.execute(
                base.order_by(MonitoringAlertTriage.last_seen.desc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
    )
    return MonitoringTriageListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[await _response(db, triage, notification) for triage, notification in rows],
    )


async def update_triage(
    db: AsyncSession,
    user: User,
    alert_id: uuid.UUID,
    body: MonitoringTriageUpdate,
) -> MonitoringTriageItem:
    triage, notification = await _get_triage(db, user, alert_id)
    changes = body.model_dump(exclude_unset=True)
    target = changes.pop("status", None)
    if target:
        await _transition(db, user, triage, notification, cast(TriageStatus, target), changes.get("notes"))
    for field, value in changes.items():
        setattr(triage, field, value)
    if target in {"triaged", "investigating"}:
        await _audit(db, user, triage, "monitoring.alert_triaged", {"status": target})
    await db.flush()
    return await _response(db, triage, notification)


async def assign_triage(
    db: AsyncSession,
    user: User,
    alert_id: uuid.UUID,
    body: MonitoringTriageAssign,
) -> MonitoringTriageItem:
    triage, notification = await _get_triage(db, user, alert_id)
    owner: User | None = None
    if body.owner_id:
        owner = await db.get(User, body.owner_id)
        if owner is None or not owner.is_active or owner.account_status != "active":
            raise MonitoringTriageOwnerNotFoundError
        if user.role != "admin" and owner.id != user.id:
            raise PermissionError
    triage.owner_id = owner.id if owner else None
    if triage.status == "new":
        triage.status = "triaged"
        notification.status = "read"
        notification.read_at = datetime.now(UTC)
    await _audit(
        db,
        user,
        triage,
        "monitoring.alert_assigned",
        {"owner_id": str(owner.id) if owner else None},
    )
    await db.flush()
    return await _response(db, triage, notification)


async def resolve_triage(
    db: AsyncSession, user: User, alert_id: uuid.UUID, body: MonitoringTriageResolution
) -> MonitoringTriageItem:
    return await _terminal_action(
        db, user, alert_id, "resolved", body.resolution_summary, "monitoring.alert_resolved"
    )


async def false_positive_triage(
    db: AsyncSession, user: User, alert_id: uuid.UUID, body: MonitoringTriageResolution
) -> MonitoringTriageItem:
    return await _terminal_action(
        db,
        user,
        alert_id,
        "false_positive",
        body.resolution_summary,
        "monitoring.alert_false_positive",
    )


async def mute_triage(
    db: AsyncSession, user: User, alert_id: uuid.UUID, body: MonitoringTriageMute
) -> MonitoringTriageItem:
    triage, notification = await _get_triage(db, user, alert_id)
    if triage.status == "muted" or triage.status in _TERMINAL:
        raise MonitoringTriageConflictError
    if notification.severity == "critical" and user.role != "admin":
        raise PermissionError
    active_manual = (
        await db.execute(
            select(AlertSuppression).where(
                AlertSuppression.alert_id == alert_id,
                AlertSuppression.active.is_(True),
                AlertSuppression.source == "manual",
            )
        )
    ).scalar_one_or_none()
    if active_manual:
        raise MonitoringTriageConflictError
    db.add(
        AlertSuppression(
            alert_id=alert_id,
            source="manual",
            reason=body.reason,
            starts_at=datetime.now(UTC),
            created_by=user.id,
        )
    )
    triage.status = "muted"
    triage.notes = body.reason
    notification.status = "dismissed"
    notification.dismissed_at = datetime.now(UTC)
    notification.event_metadata = {
        **(notification.event_metadata or {}),
        "suppressed": True,
        "suppressed_due_to_maintenance": False,
    }
    await _audit(db, user, triage, "monitoring.alert_muted", {"critical": notification.severity == "critical"})
    await db.flush()
    return await _response(db, triage, notification)


async def _terminal_action(
    db: AsyncSession,
    user: User,
    alert_id: uuid.UUID,
    status: TriageStatus,
    summary: str,
    audit_action: str,
) -> MonitoringTriageItem:
    triage, notification = await _get_triage(db, user, alert_id)
    if triage.status in _TERMINAL:
        raise MonitoringTriageConflictError
    if triage.status == "muted":
        await _lift_manual_suppressions(db, user, triage, notification)
    triage.status = status
    triage.resolution_summary = summary
    notification.status = "dismissed"
    notification.dismissed_at = datetime.now(UTC)
    await _audit(db, user, triage, audit_action, {})
    await db.flush()
    return await _response(db, triage, notification)


async def _transition(
    db: AsyncSession,
    user: User,
    triage: MonitoringAlertTriage,
    notification: Notification,
    target: TriageStatus,
    reason: str | None,
) -> None:
    if target == triage.status:
        raise MonitoringTriageConflictError
    if target == "muted":
        if not reason:
            raise MonitoringTriageValidationError
        result = await mute_triage(db, user, triage.alert_id, MonitoringTriageMute(reason=reason))
        triage.status = result.status
        return
    if target in _TERMINAL:
        raise MonitoringTriageValidationError
    if triage.status == "muted":
        await _lift_manual_suppressions(db, user, triage, notification)
    triage.status = target
    if target == "new":
        notification.status = "unread"
        notification.read_at = None
        notification.dismissed_at = None
    else:
        notification.status = "read"
        notification.read_at = datetime.now(UTC)


async def _lift_manual_suppressions(
    db: AsyncSession, user: User, triage: MonitoringAlertTriage, notification: Notification
) -> None:
    rows = list(
        (
            await db.execute(
                select(AlertSuppression).where(
                    AlertSuppression.alert_id == triage.alert_id,
                    AlertSuppression.active.is_(True),
                    AlertSuppression.source == "manual",
                )
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    for item in rows:
        item.active = False
        item.lifted_by = user.id
        item.lifted_at = now
    notification.event_metadata = {
        **(notification.event_metadata or {}),
        "suppressed": False,
        "suppressed_due_to_maintenance": False,
    }
    await _audit(db, user, triage, "monitoring.alert_unmuted", {})


async def _ensure_user_triage(db: AsyncSession, user: User) -> None:
    notifications = list(
        (
            await db.execute(
                select(Notification)
                .outerjoin(MonitoringAlertTriage, MonitoringAlertTriage.alert_id == Notification.id)
                .where(
                    Notification.user_id == user.id,
                    Notification.notification_type == "monitoring_alert",
                    MonitoringAlertTriage.id.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for notification in notifications:
        metadata = notification.event_metadata if isinstance(notification.event_metadata, dict) else {}
        related_asset = await _related_asset_id(db, notification, metadata)
        related_finding = await _related_finding_id(db, notification)
        recovered = bool(metadata.get("recovered_at"))
        db.add(
            MonitoringAlertTriage(
                alert_id=notification.id,
                status="resolved" if recovered else "new",
                severity=notification.severity,
                source=_safe_source(metadata.get("category") or notification.entity_type),
                related_asset_id=related_asset,
                related_finding_id=related_finding,
                first_seen=notification.created_at,
                last_seen=notification.updated_at,
                resolution_summary="Monitoring condition recovered automatically." if recovered else None,
            )
        )
    existing = list(
        (
            await db.execute(
                select(MonitoringAlertTriage, Notification)
                .join(Notification, Notification.id == MonitoringAlertTriage.alert_id)
                .where(
                    Notification.user_id == user.id,
                    Notification.notification_type == "monitoring_alert",
                    MonitoringAlertTriage.status.not_in(_TERMINAL),
                )
            )
        ).all()
    )
    for triage, notification in existing:
        metadata = notification.event_metadata if isinstance(notification.event_metadata, dict) else {}
        if metadata.get("recovered_at"):
            triage.status = "resolved"
            triage.resolution_summary = "Monitoring condition recovered automatically."
            notification.status = "dismissed"
            notification.dismissed_at = notification.updated_at
    await db.flush()


async def _get_triage(
    db: AsyncSession, user: User, alert_id: uuid.UUID
) -> tuple[MonitoringAlertTriage, Notification]:
    await _ensure_user_triage(db, user)
    row = (
        await db.execute(
            select(MonitoringAlertTriage, Notification)
            .join(Notification, Notification.id == MonitoringAlertTriage.alert_id)
            .where(MonitoringAlertTriage.alert_id == alert_id, Notification.user_id == user.id)
        )
    ).one_or_none()
    if row is None:
        raise MonitoringTriageNotFoundError
    return row[0], row[1]


async def _response(
    db: AsyncSession, triage: MonitoringAlertTriage, notification: Notification
) -> MonitoringTriageItem:
    owner = await db.get(User, triage.owner_id) if triage.owner_id else None
    suppressions = list(
        (
            await db.execute(
                select(AlertSuppression).where(
                    AlertSuppression.alert_id == triage.alert_id,
                    AlertSuppression.active.is_(True),
                    or_(AlertSuppression.ends_at.is_(None), AlertSuppression.ends_at > datetime.now(UTC)),
                )
            )
        )
        .scalars()
        .all()
    )
    return MonitoringTriageItem(
        alert_id=triage.alert_id,
        status=cast(TriageStatus, triage.status),
        owner_id=triage.owner_id,
        owner_name=owner.full_name or owner.username if owner else None,
        severity=cast(TriageSeverity, triage.severity),
        source=triage.source,
        related_asset_id=triage.related_asset_id,
        related_finding_id=triage.related_finding_id,
        title=_safe_display(notification.title, "Monitoring alert"),
        description=_safe_display(notification.message, "Review the monitoring condition."),
        action_url=_safe_action(notification.action_url),
        first_seen=triage.first_seen,
        last_seen=triage.last_seen,
        notes=triage.notes,
        resolution_summary=triage.resolution_summary,
        suppressed=bool(suppressions),
        suppressed_due_to_maintenance=any(item.source == "maintenance" for item in suppressions),
    )


async def _related_asset_id(
    db: AsyncSession, notification: Notification, metadata: dict[str, Any]
) -> uuid.UUID | None:
    if notification.entity_type == "lan_asset" and notification.entity_id:
        return notification.entity_id if await db.get(LanAsset, notification.entity_id) else None
    rule = str(metadata.get("rule", ""))
    for value in _UUID_PATTERN.findall(rule):
        candidate = uuid.UUID(value)
        if await db.get(LanAsset, candidate):
            return candidate
    return None


async def _related_finding_id(
    db: AsyncSession, notification: Notification
) -> uuid.UUID | None:
    if notification.entity_type == "vulnerability_baseline_finding" and notification.entity_id:
        return notification.entity_id if await db.get(VulnerabilityBaselineFinding, notification.entity_id) else None
    return None


async def _audit(
    db: AsyncSession,
    user: User,
    triage: MonitoringAlertTriage,
    action: str,
    metadata: dict[str, Any],
) -> None:
    await record_event(
        db,
        action=action,
        actor_id=user.id,
        resource_type="monitoring_alert",
        resource_id=triage.alert_id,
        metadata=metadata,
    )


def _safe_source(value: Any) -> str:
    source = str(value or "monitoring")[:80]
    return "monitoring" if _contains_secret_term(source) else source


def _safe_display(value: str | None, fallback: str) -> str:
    if not value or _contains_secret_term(value):
        return fallback
    return value


def _safe_action(value: str | None) -> str | None:
    return value if value and value.startswith("/") and not value.startswith("//") else None


def _contains_secret_term(value: str) -> bool:
    return any(
        term in value.lower()
        for term in ("password", "secret", "token", "credential", "database_url", "api key")
    )
