from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.monitoring_policy import (
    AlertSuppression,
    MaintenanceWindow,
    MonitoringPolicy,
)
from app.models.notification import Notification
from app.models.user import User
from app.schemas.monitoring_policy import (
    AlertSuppressionCreate,
    AlertSuppressionResponse,
    MaintenanceWindowCreate,
    MaintenanceWindowResponse,
    MaintenanceWindowUpdate,
    MonitoringPolicyCreate,
    MonitoringPolicyUpdate,
)
from app.services.audit import record_event

DEFAULT_POLICIES = (
    (
        "cpu_threshold",
        "CPU utilization",
        "Alert on sustained high CPU utilization.",
        90,
        "percent",
        240,
        "system.cpu",
    ),
    (
        "memory_threshold",
        "Memory utilization",
        "Alert on sustained high memory utilization.",
        90,
        "percent",
        240,
        "system.memory",
    ),
    (
        "disk_threshold",
        "Disk utilization",
        "Alert before storage exhaustion.",
        90,
        "percent",
        240,
        "system.disk",
    ),
    (
        "stale_agent",
        "Stale endpoint agent",
        "Warn when approved endpoint telemetry becomes stale.",
        30,
        "minutes",
        360,
        "agent.stale",
    ),
    (
        "offline_asset",
        "Offline asset",
        "Warn after an authorized monitored asset remains offline.",
        60,
        "minutes",
        360,
        "asset.offline",
    ),
    (
        "risky_service",
        "Risky service",
        "Warn on passively observed risky services.",
        None,
        None,
        720,
        "service.risky",
    ),
    (
        "unauthorized_asset",
        "Unauthorized asset",
        "Alert when an observed asset lacks authorization.",
        None,
        None,
        60,
        "asset.unauthorized",
    ),
    (
        "weak_coverage",
        "Weak monitoring coverage",
        "Warn when approved passive coverage is insufficient.",
        None,
        None,
        1440,
        "coverage.weak",
    ),
    (
        "high_critical_finding",
        "High or critical finding",
        "Alert on unresolved high and critical findings.",
        None,
        None,
        240,
        "finding.high_critical",
    ),
    (
        "overdue_remediation",
        "Overdue remediation",
        "Alert when an unresolved remediation due date has passed.",
        None,
        None,
        1440,
        "remediation.overdue",
    ),
)


class MonitoringPolicyNotFoundError(Exception):
    pass


class MaintenanceWindowNotFoundError(Exception):
    pass


class AlertNotFoundError(Exception):
    pass


class AlertSuppressionConflictError(Exception):
    pass


async def ensure_default_policies(db: AsyncSession) -> None:
    existing = set(
        (await db.execute(select(MonitoringPolicy.rule_key))).scalars().all()
    )
    for key, title, description, threshold, unit, cooldown, dedupe in DEFAULT_POLICIES:
        if key not in existing:
            db.add(
                MonitoringPolicy(
                    rule_key=key,
                    title=title,
                    description=description,
                    threshold_value=threshold,
                    threshold_unit=unit,
                    cooldown_minutes=cooldown,
                    dedupe_key=dedupe,
                    max_alerts_per_rule=3,
                )
            )
    await db.flush()


async def list_policies(db: AsyncSession) -> list[MonitoringPolicy]:
    await ensure_default_policies(db)
    return list(
        (await db.execute(select(MonitoringPolicy).order_by(MonitoringPolicy.rule_key)))
        .scalars()
        .all()
    )


async def create_policy(
    db: AsyncSession, user: User, body: MonitoringPolicyCreate
) -> MonitoringPolicy:
    if (
        await db.execute(
            select(MonitoringPolicy.id).where(
                MonitoringPolicy.rule_key == body.rule_key
            )
        )
    ).scalar_one_or_none():
        raise AlertSuppressionConflictError
    item = MonitoringPolicy(**body.model_dump(), created_by=user.id, updated_by=user.id)
    db.add(item)
    await db.flush()
    await record_event(
        db,
        action="monitoring.policy_created",
        actor_id=user.id,
        resource_type="monitoring_policy",
        resource_id=item.id,
        metadata={"rule_key": item.rule_key},
    )
    return item


async def update_policy(
    db: AsyncSession, user: User, policy_id: uuid.UUID, body: MonitoringPolicyUpdate
) -> MonitoringPolicy:
    item = await db.get(MonitoringPolicy, policy_id)
    if not item:
        raise MonitoringPolicyNotFoundError
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    item.updated_by = user.id
    await db.flush()
    await db.refresh(item)
    await record_event(
        db,
        action="monitoring.policy_updated",
        actor_id=user.id,
        resource_type="monitoring_policy",
        resource_id=item.id,
        metadata={
            "rule_key": item.rule_key,
            "changed_fields": sorted(body.model_fields_set),
        },
    )
    return item


def window_response(item: MaintenanceWindow) -> MaintenanceWindowResponse:
    now = datetime.now(UTC)
    state = (
        "scheduled"
        if now < item.start_time
        else "active"
        if now < item.end_time
        else "completed"
    )
    return MaintenanceWindowResponse.model_validate({**item.__dict__, "status": state})


async def list_windows(db: AsyncSession) -> list[MaintenanceWindow]:
    return list(
        (
            await db.execute(
                select(MaintenanceWindow).order_by(MaintenanceWindow.start_time.desc())
            )
        )
        .scalars()
        .all()
    )


async def create_window(
    db: AsyncSession, user: User, body: MaintenanceWindowCreate
) -> MaintenanceWindow:
    item = MaintenanceWindow(
        **body.model_dump(), created_by=user.id, updated_by=user.id
    )
    db.add(item)
    await db.flush()
    await record_event(
        db,
        action="monitoring.maintenance_window_created",
        actor_id=user.id,
        resource_type="maintenance_window",
        resource_id=item.id,
        metadata={"title": item.title, "suppress_alerts": item.suppress_alerts},
    )
    return item


async def update_window(
    db: AsyncSession, user: User, window_id: uuid.UUID, body: MaintenanceWindowUpdate
) -> MaintenanceWindow:
    item = await db.get(MaintenanceWindow, window_id)
    if not item:
        raise MaintenanceWindowNotFoundError
    values = body.model_dump(exclude_unset=True)
    start, end = (
        values.get("start_time", item.start_time),
        values.get("end_time", item.end_time),
    )
    if end <= start or end - start > __import__("datetime").timedelta(days=30):
        raise ValueError("Invalid maintenance window range.")
    for key, value in values.items():
        setattr(item, key, value)
    item.updated_by = user.id
    await db.flush()
    await db.refresh(item)
    await record_event(
        db,
        action="monitoring.maintenance_window_updated",
        actor_id=user.id,
        resource_type="maintenance_window",
        resource_id=item.id,
        metadata={"changed_fields": sorted(body.model_fields_set)},
    )
    return item


async def suppress_alert(
    db: AsyncSession, user: User, alert_id: uuid.UUID, body: AlertSuppressionCreate
) -> AlertSuppression:
    alert = await db.get(Notification, alert_id)
    if not alert or alert.notification_type != "monitoring_alert":
        raise AlertNotFoundError
    if user.role != "admin" and alert.user_id != user.id:
        raise PermissionError
    current = (
        await db.execute(
            select(AlertSuppression).where(
                AlertSuppression.alert_id == alert_id, AlertSuppression.active.is_(True)
            )
        )
    ).scalar_one_or_none()
    if current and (current.ends_at is None or current.ends_at > datetime.now(UTC)):
        raise AlertSuppressionConflictError
    if alert.severity == "critical" and user.role != "admin":
        raise PermissionError
    item = AlertSuppression(
        alert_id=alert_id,
        source="manual",
        reason=body.reason,
        starts_at=datetime.now(UTC),
        ends_at=body.ends_at,
        created_by=user.id,
    )
    db.add(item)
    alert.event_metadata = {
        **(alert.event_metadata or {}),
        "suppressed": True,
        "suppressed_due_to_maintenance": False,
    }
    await db.flush()
    await record_event(
        db,
        action="monitoring.alert_suppressed",
        actor_id=user.id,
        resource_type="notification",
        resource_id=alert.id,
        metadata={
            "reason": body.reason[:200],
            "critical": alert.severity == "critical",
        },
    )
    return item


async def unsuppress_alert(
    db: AsyncSession, user: User, alert_id: uuid.UUID
) -> AlertSuppression:
    alert = await db.get(Notification, alert_id)
    if not alert or alert.notification_type != "monitoring_alert":
        raise AlertNotFoundError
    if user.role != "admin" and alert.user_id != user.id:
        raise PermissionError
    item = (
        (
            await db.execute(
                select(AlertSuppression)
                .where(
                    AlertSuppression.alert_id == alert_id,
                    AlertSuppression.active.is_(True),
                )
                .order_by(AlertSuppression.created_at.desc())
            )
        )
        .scalars()
        .first()
    )
    if not item:
        raise AlertSuppressionConflictError
    item.active = False
    item.lifted_by = user.id
    item.lifted_at = datetime.now(UTC)
    alert.event_metadata = {
        **(alert.event_metadata or {}),
        "suppressed": False,
        "suppressed_due_to_maintenance": False,
    }
    await db.flush()
    await record_event(
        db,
        action="monitoring.alert_unsuppressed",
        actor_id=user.id,
        resource_type="notification",
        resource_id=alert.id,
        metadata={"source": item.source},
    )
    return item


def suppression_response(item: AlertSuppression) -> AlertSuppressionResponse:
    return AlertSuppressionResponse(
        id=item.id,
        alert_id=item.alert_id,
        source=cast(Literal["manual", "maintenance"], item.source),
        reason=item.reason,
        starts_at=item.starts_at,
        ends_at=item.ends_at,
        active=item.active,
        suppressed_due_to_maintenance=item.source == "maintenance",
    )
