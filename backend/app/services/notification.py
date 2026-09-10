from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case_closure import (
    CaseClosure,
    CaseClosureChecklistItem,
    CaseDeliverable,
)
from app.models.engagement import Engagement
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.investigation_member import InvestigationMember
from app.models.investigation_task import InvestigationTask
from app.models.notification import Notification
from app.models.report import Report
from app.models.user import User
from app.schemas.notification import (
    NotificationActionResponse,
    NotificationListResponse,
    NotificationMarkAllReadResponse,
    NotificationResponse,
    NotificationSeverity,
    NotificationStatus,
    WorkflowAlertRebuildResponse,
)
from app.services.audit import record_event


class NotificationNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class NotificationCreateResult:
    notification: Notification
    created: bool


async def create_notification(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    notification_type: str,
    severity: NotificationSeverity,
    title: str,
    message: str,
    entity_type: str,
    actor_user_id: uuid.UUID | None = None,
    investigation_id: uuid.UUID | None = None,
    engagement_id: uuid.UUID | None = None,
    entity_id: uuid.UUID | None = None,
    action_url: str | None = None,
    metadata: dict[str, Any] | None = None,
    expires_at: datetime | None = None,
    dedupe_key: str | None = None,
) -> NotificationCreateResult:
    if dedupe_key:
        existing = await _notification_by_dedupe(db, dedupe_key)
        if existing is not None:
            return NotificationCreateResult(notification=existing, created=False)

    notification = Notification(
        user_id=user_id,
        actor_user_id=actor_user_id,
        investigation_id=investigation_id,
        engagement_id=engagement_id,
        entity_type=entity_type[:60],
        entity_id=entity_id,
        notification_type=notification_type[:80],
        severity=severity,
        title=_clean_text(title, 255),
        message=_clean_text(message, 4000),
        action_url=_clean_optional(action_url, 500),
        expires_at=expires_at,
        event_metadata=_safe_metadata(metadata),
        dedupe_key=dedupe_key,
    )
    db.add(notification)
    await db.flush()
    await record_event(
        db,
        action="notification.created",
        actor_id=actor_user_id,
        user_id=user_id,
        resource_type="notification",
        resource_id=notification.id,
        investigation_id=investigation_id,
        metadata={
            "notification_type": notification.notification_type,
            "severity": notification.severity,
            "entity_type": notification.entity_type,
            "entity_id": str(entity_id) if entity_id else None,
            "target_user_id": str(user_id) if user_id else None,
        },
    )
    return NotificationCreateResult(notification=notification, created=True)


async def create_admin_notification(
    db: AsyncSession,
    *,
    notification_type: str,
    severity: NotificationSeverity,
    title: str,
    message: str,
    entity_type: str,
    actor_user_id: uuid.UUID | None = None,
    investigation_id: uuid.UUID | None = None,
    engagement_id: uuid.UUID | None = None,
    entity_id: uuid.UUID | None = None,
    action_url: str | None = None,
    metadata: dict[str, Any] | None = None,
    dedupe_key_prefix: str,
) -> tuple[int, int]:
    created = 0
    existing = 0
    admins = await _active_admins(db)
    for admin in admins:
        result = await create_notification(
            db,
            user_id=admin.id,
            actor_user_id=actor_user_id,
            investigation_id=investigation_id,
            engagement_id=engagement_id,
            entity_type=entity_type,
            entity_id=entity_id,
            notification_type=notification_type,
            severity=severity,
            title=title,
            message=message,
            action_url=action_url,
            metadata=metadata,
            dedupe_key=f"{dedupe_key_prefix}:admin:{admin.id}",
        )
        if result.created:
            created += 1
        else:
            existing += 1
    return created, existing


async def list_notifications(
    db: AsyncSession,
    user: User,
    *,
    status: str | None = None,
    severity: str | None = None,
    notification_type: str | None = None,
    investigation_id: uuid.UUID | None = None,
    engagement_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> NotificationListResponse:
    filters = _notification_filters_for_user(
        user,
        status=status,
        severity=severity,
        notification_type=notification_type,
        investigation_id=investigation_id,
        engagement_id=engagement_id,
    )
    count_stmt = select(func.count()).select_from(Notification).where(*filters)
    total = int((await db.execute(count_stmt)).scalar_one())
    result = await db.execute(
        select(Notification)
        .where(*filters)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(offset)
        .limit(limit)
    )
    unread = await unread_count(db, user)
    return NotificationListResponse(
        total=total,
        unread=unread,
        limit=limit,
        offset=offset,
        items=[_notification_response(item) for item in result.scalars().all()],
    )


async def unread_count(db: AsyncSession, user: User) -> int:
    filters = _notification_filters_for_user(user, status="unread")
    result = await db.execute(
        select(func.count()).select_from(Notification).where(*filters)
    )
    return int(result.scalar_one())


async def mark_notification_read(
    db: AsyncSession,
    user: User,
    notification_id: uuid.UUID,
) -> NotificationActionResponse:
    notification = await _get_notification_for_user(db, user, notification_id)
    if notification.status != "read":
        notification.status = "read"
        notification.read_at = _now()
        db.add(notification)
        await db.flush()
        await record_event(
            db,
            action="notification.read",
            actor_id=user.id,
            resource_type="notification",
            resource_id=notification.id,
            investigation_id=notification.investigation_id,
            metadata=_audit_metadata(notification),
        )
        if notification.notification_type == "monitoring_alert":
            await _apply_monitoring_acknowledgement(db, user, notification)
        await db.refresh(notification)
    return NotificationActionResponse(
        notification=_notification_response(notification),
        message="Notification marked as read.",
    )


async def _apply_monitoring_acknowledgement(
    db: AsyncSession, user: User, notification: Notification
) -> None:
    from app.models.monitoring_policy import MonitoringPolicy
    from app.schemas.monitoring_policy import AlertSuppressionCreate
    from app.services.monitoring_policy import (
        AlertSuppressionConflictError,
        suppress_alert,
    )

    metadata = (
        notification.event_metadata
        if isinstance(notification.event_metadata, dict)
        else {}
    )
    rule_key = metadata.get("policy_rule")
    if not isinstance(rule_key, str):
        return
    policy = (
        await db.execute(
            select(MonitoringPolicy).where(MonitoringPolicy.rule_key == rule_key)
        )
    ).scalar_one_or_none()
    if policy is None or policy.acknowledge_behavior != "suppress":
        return
    try:
        await suppress_alert(
            db,
            user,
            notification.id,
            AlertSuppressionCreate(
                reason="Suppressed by configured acknowledgement behavior."
            ),
        )
    except (PermissionError, AlertSuppressionConflictError):
        # Critical and already-suppressed alerts remain visible; acknowledgement still succeeds.
        return


async def dismiss_notification(
    db: AsyncSession,
    user: User,
    notification_id: uuid.UUID,
) -> NotificationActionResponse:
    notification = await _get_notification_for_user(db, user, notification_id)
    notification.status = "dismissed"
    notification.dismissed_at = _now()
    if notification.read_at is None:
        notification.read_at = notification.dismissed_at
    db.add(notification)
    await db.flush()
    await record_event(
        db,
        action="notification.dismissed",
        actor_id=user.id,
        resource_type="notification",
        resource_id=notification.id,
        investigation_id=notification.investigation_id,
        metadata=_audit_metadata(notification),
    )
    await db.refresh(notification)
    return NotificationActionResponse(
        notification=_notification_response(notification),
        message="Notification dismissed.",
    )


async def mark_all_notifications_read(
    db: AsyncSession,
    user: User,
) -> NotificationMarkAllReadResponse:
    filters = _notification_filters_for_user(user, status="unread")
    result = await db.execute(select(Notification).where(*filters))
    notifications = list(result.scalars().all())
    now = _now()
    for notification in notifications:
        notification.status = "read"
        notification.read_at = now
        db.add(notification)
    await db.flush()
    await record_event(
        db,
        action="notification.mark_all_read",
        actor_id=user.id,
        resource_type="notification",
        metadata={"updated": len(notifications)},
    )
    return NotificationMarkAllReadResponse(
        updated=len(notifications),
        unread=await unread_count(db, user),
        message=f"{len(notifications)} notifications marked as read.",
    )


async def rebuild_workflow_alerts(
    db: AsyncSession,
    user: User,
) -> WorkflowAlertRebuildResponse:
    created = 0
    existing = 0
    c, e = await _alerts_for_pending_users(db, user)
    created += c
    existing += e
    c, e = await _alerts_for_pending_closure_reviews(db, user)
    created += c
    existing += e
    c, e = await _alerts_for_closure_blockers(db, user)
    created += c
    existing += e
    c, e = await _alerts_for_report_approvals(db, user)
    created += c
    existing += e
    c, e = await _alerts_for_ready_deliverables(db, user)
    created += c
    existing += e
    c, e = await _alerts_for_assignments(db, user)
    created += c
    existing += e
    c, e = await _alerts_for_authorization_status(db, user)
    created += c
    existing += e
    await record_event(
        db,
        action="notification.workflow_alert_generated",
        actor_id=user.id,
        resource_type="notification",
        metadata={"created": created, "existing": existing},
    )
    return WorkflowAlertRebuildResponse(
        created=created,
        existing=existing,
        total_unread=await unread_count(db, user),
        message="Workflow alerts rebuilt without external notification delivery.",
    )


async def notify_user_registered(
    db: AsyncSession,
    *,
    registered_user: User,
    actor_user_id: uuid.UUID | None = None,
) -> None:
    if registered_user.account_status != "pending":
        return
    await create_admin_notification(
        db,
        actor_user_id=actor_user_id or registered_user.id,
        notification_type="user_approval_pending",
        severity="warning",
        title="Account approval pending",
        message=f"{registered_user.username} registered and needs administrator approval.",
        entity_type="user",
        entity_id=registered_user.id,
        action_url="/admin/users?status=pending",
        metadata={
            "target_user_id": str(registered_user.id),
            "registration_source": registered_user.registration_source,
        },
        dedupe_key_prefix=f"user_approval_pending:{registered_user.id}",
    )


async def notify_user_approved(
    db: AsyncSession,
    *,
    approved_user: User,
    actor_user_id: uuid.UUID,
) -> None:
    result = await create_notification(
        db,
        user_id=approved_user.id,
        actor_user_id=actor_user_id,
        notification_type="user_approved",
        severity="success",
        title="Account approved",
        message="Your RavenTech account is active. You can access assigned defensive workspaces.",
        entity_type="user",
        entity_id=approved_user.id,
        action_url="/",
        metadata={"account_status": approved_user.account_status},
        dedupe_key=f"user_approved:{approved_user.id}:{approved_user.account_status}",
    )
    if not result.created and result.notification.status == "dismissed":
        result.notification.status = "unread"
        result.notification.dismissed_at = None
        db.add(result.notification)


async def notify_closure_submitted(
    db: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    investigation_id: uuid.UUID,
    closure_id: uuid.UUID,
) -> None:
    investigation = await db.get(Investigation, investigation_id)
    if investigation is None:
        return
    await _notify_investigation_reviewers(
        db,
        actor_user_id=actor_user_id,
        investigation=investigation,
        notification_type="closure_review_pending",
        severity="warning",
        title="Closure review pending",
        message=f"{investigation.title} was submitted for final closure review.",
        entity_type="case_closure",
        entity_id=closure_id,
        action_url=f"/investigations/{investigation.id}/closure",
        dedupe_key_prefix=f"closure_review_pending:{closure_id}",
    )


async def notify_closure_approved(
    db: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    investigation_id: uuid.UUID,
    closure_id: uuid.UUID,
) -> None:
    investigation = await db.get(Investigation, investigation_id)
    if investigation is None:
        return
    await _notify_investigation_recipients(
        db,
        actor_user_id=actor_user_id,
        investigation=investigation,
        notification_type="closure_approved",
        severity="success",
        title="Closure approved",
        message=f"{investigation.title} is approved for case closure.",
        entity_type="case_closure",
        entity_id=closure_id,
        action_url=f"/investigations/{investigation.id}/closure",
        dedupe_key_prefix=f"closure_approved:{closure_id}",
    )


async def notify_case_closed(
    db: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    investigation_id: uuid.UUID,
    closure_id: uuid.UUID,
) -> None:
    investigation = await db.get(Investigation, investigation_id)
    if investigation is None:
        return
    await _notify_investigation_recipients(
        db,
        actor_user_id=actor_user_id,
        investigation=investigation,
        notification_type="case_closed",
        severity="success",
        title="Case closed",
        message=f"{investigation.title} was closed with preserved audit history.",
        entity_type="case_closure",
        entity_id=closure_id,
        action_url=f"/investigations/{investigation.id}/closure",
        dedupe_key_prefix=f"case_closed:{closure_id}",
    )


async def notify_case_reopened(
    db: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    investigation_id: uuid.UUID,
    closure_id: uuid.UUID,
) -> None:
    investigation = await db.get(Investigation, investigation_id)
    if investigation is None:
        return
    await _notify_investigation_recipients(
        db,
        actor_user_id=actor_user_id,
        investigation=investigation,
        notification_type="case_reopened",
        severity="warning",
        title="Case reopened",
        message=f"{investigation.title} was reopened for additional analyst review.",
        entity_type="case_closure",
        entity_id=closure_id,
        action_url=f"/investigations/{investigation.id}/closure",
        dedupe_key_prefix=f"case_reopened:{closure_id}",
    )


async def notify_deliverable_ready(
    db: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    investigation_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    title: str,
    deliverable_type: str,
) -> None:
    investigation = await db.get(Investigation, investigation_id)
    if investigation is None:
        return
    await _notify_investigation_reviewers(
        db,
        actor_user_id=actor_user_id,
        investigation=investigation,
        notification_type=(
            "evidence_package_ready"
            if deliverable_type == "final_package"
            else "report_ready"
        ),
        severity="info",
        title="Deliverable ready",
        message=f"{title} is ready for {investigation.title}.",
        entity_type="case_deliverable",
        entity_id=deliverable_id,
        action_url=f"/investigations/{investigation.id}/closure",
        dedupe_key_prefix=f"deliverable_ready:{deliverable_id}:ready",
    )


async def notify_report_approval_pending(
    db: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    investigation_id: uuid.UUID,
    report_id: uuid.UUID,
    report_title: str,
) -> None:
    investigation = await db.get(Investigation, investigation_id)
    if investigation is None:
        return
    await _notify_investigation_reviewers(
        db,
        actor_user_id=actor_user_id,
        investigation=investigation,
        notification_type="report_approval_pending",
        severity="warning",
        title="Report approval pending",
        message=f"{report_title} is pending stakeholder-ready approval.",
        entity_type="report",
        entity_id=report_id,
        action_url=f"/investigations/{investigation.id}/reports",
        dedupe_key_prefix=f"report_approval_pending:{report_id}",
    )


async def notify_task_assigned(
    db: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    assigned_to: uuid.UUID | None,
    investigation_id: uuid.UUID,
    task_id: uuid.UUID,
    task_title: str,
    priority: str,
) -> None:
    if assigned_to is None:
        return
    investigation = await db.get(Investigation, investigation_id)
    if investigation is None:
        return
    await create_notification(
        db,
        user_id=assigned_to,
        actor_user_id=actor_user_id,
        investigation_id=investigation_id,
        engagement_id=investigation.engagement_id,
        notification_type="investigation_assigned",
        severity="warning" if priority in {"urgent", "critical", "high"} else "info",
        title="Task assigned",
        message=f"{task_title} is assigned to you in {investigation.title}.",
        entity_type="task",
        entity_id=task_id,
        action_url=f"/investigations/{investigation_id}/tasks",
        metadata={"priority": priority},
        dedupe_key=f"task_assigned:{task_id}:{assigned_to}",
    )


async def notify_finding_assigned(
    db: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    assigned_to: uuid.UUID | None,
    investigation_id: uuid.UUID,
    finding_id: uuid.UUID,
    finding_title: str,
    severity: str,
) -> None:
    if assigned_to is None:
        return
    investigation = await db.get(Investigation, investigation_id)
    if investigation is None:
        return
    await create_notification(
        db,
        user_id=assigned_to,
        actor_user_id=actor_user_id,
        investigation_id=investigation_id,
        engagement_id=investigation.engagement_id,
        notification_type="finding_assigned",
        severity="warning" if severity in {"high", "critical"} else "info",
        title="Finding assigned",
        message=f"{finding_title} is assigned to you for analyst review.",
        entity_type="finding",
        entity_id=finding_id,
        action_url=f"/investigations/{investigation_id}/findings",
        metadata={"severity": severity},
        dedupe_key=f"finding_assigned:{finding_id}:{assigned_to}",
    )


async def notify_scope_warning(
    db: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    engagement_id: uuid.UUID,
    value: str,
    status: str,
) -> None:
    engagement = await db.get(Engagement, engagement_id)
    if engagement is None:
        return
    recipient_ids = await _admin_ids(db)
    if engagement.created_by:
        recipient_ids.add(engagement.created_by)
    for recipient_id in recipient_ids:
        await create_notification(
            db,
            user_id=recipient_id,
            actor_user_id=actor_user_id,
            engagement_id=engagement.id,
            entity_type="engagement",
            entity_id=engagement.id,
            notification_type="scope_warning",
            severity="warning" if status == "pending_review" else "critical",
            title="Scope warning created",
            message=(
                f"{value} requires scope review for {engagement.title} "
                f"({status.replace('_', ' ')})."
            ),
            action_url=f"/engagements?engagement={engagement.id}",
            metadata={"scope_value": value[:200], "scope_status": status},
            dedupe_key=f"scope_warning:{engagement.id}:{recipient_id}:{value}:{status}",
        )


def notification_response(notification: Notification) -> NotificationResponse:
    return _notification_response(notification)


async def _notification_by_dedupe(
    db: AsyncSession,
    dedupe_key: str,
) -> Notification | None:
    result = await db.execute(
        select(Notification).where(Notification.dedupe_key == dedupe_key)
    )
    return result.scalar_one_or_none()


async def _get_notification_for_user(
    db: AsyncSession,
    user: User,
    notification_id: uuid.UUID,
) -> Notification:
    filters = _notification_filters_for_user(user)
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id, *filters)
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise NotificationNotFoundError("Notification not found")
    return notification


def _notification_filters_for_user(
    user: User,
    *,
    status: str | None = None,
    severity: str | None = None,
    notification_type: str | None = None,
    investigation_id: uuid.UUID | None = None,
    engagement_id: uuid.UUID | None = None,
) -> list[Any]:
    filters: list[Any] = [Notification.user_id == user.id]
    if user.role != "admin":
        filters.append(
            or_(
                Notification.investigation_id.is_(None),
                exists().where(
                    and_(
                        Investigation.id == Notification.investigation_id,
                        or_(
                            Investigation.owner_id == user.id,
                            Investigation.reviewer_id == user.id,
                        ),
                    )
                ),
                exists().where(
                    and_(
                        InvestigationMember.investigation_id
                        == Notification.investigation_id,
                        InvestigationMember.user_id == user.id,
                    )
                ),
            )
        )
    if status:
        filters.append(Notification.status == status)
    if severity:
        filters.append(Notification.severity == severity)
    if notification_type:
        filters.append(Notification.notification_type == notification_type)
    if investigation_id:
        filters.append(Notification.investigation_id == investigation_id)
    if engagement_id:
        filters.append(Notification.engagement_id == engagement_id)
    return filters


async def _alerts_for_pending_users(
    db: AsyncSession,
    actor: User,
) -> tuple[int, int]:
    result = await db.execute(
        select(User).where(User.account_status == "pending").order_by(User.created_at)
    )
    created = existing = 0
    for pending in result.scalars().all():
        c, e = await create_admin_notification(
            db,
            actor_user_id=actor.id,
            notification_type="user_approval_pending",
            severity="warning",
            title="Account approval pending",
            message=f"{pending.username} is waiting for administrator approval.",
            entity_type="user",
            entity_id=pending.id,
            action_url="/admin/users?status=pending",
            metadata={"target_user_id": str(pending.id)},
            dedupe_key_prefix=f"user_approval_pending:{pending.id}",
        )
        created += c
        existing += e
    return created, existing


async def _alerts_for_pending_closure_reviews(
    db: AsyncSession,
    actor: User,
) -> tuple[int, int]:
    result = await db.execute(
        select(CaseClosure, Investigation)
        .join(Investigation, Investigation.id == CaseClosure.investigation_id)
        .where(CaseClosure.status == "in_review")
    )
    created = existing = 0
    for closure, investigation in result.all():
        c, e = await _notify_investigation_reviewers(
            db,
            actor_user_id=actor.id,
            investigation=investigation,
            notification_type="closure_review_pending",
            severity="warning",
            title="Closure review pending",
            message=f"{investigation.title} needs final case closure review.",
            entity_type="case_closure",
            entity_id=closure.id,
            action_url=f"/investigations/{investigation.id}/closure",
            dedupe_key_prefix=f"closure_review_pending:{closure.id}",
        )
        created += c
        existing += e
    return created, existing


async def _alerts_for_closure_blockers(
    db: AsyncSession,
    actor: User,
) -> tuple[int, int]:
    result = await db.execute(
        select(Investigation, func.count(CaseClosureChecklistItem.id))
        .join(
            CaseClosureChecklistItem,
            CaseClosureChecklistItem.investigation_id == Investigation.id,
        )
        .where(
            CaseClosureChecklistItem.required.is_(True),
            CaseClosureChecklistItem.status == "blocked",
        )
        .group_by(Investigation.id)
    )
    created = existing = 0
    for investigation, blocker_count in result.all():
        c, e = await _notify_investigation_recipients(
            db,
            actor_user_id=actor.id,
            investigation=investigation,
            notification_type="closure_blocked",
            severity="critical" if int(blocker_count) > 2 else "warning",
            title="Closure blockers present",
            message=(
                f"{investigation.title} has {int(blocker_count)} required "
                "closure checklist blockers."
            ),
            entity_type="investigation",
            entity_id=investigation.id,
            action_url=f"/investigations/{investigation.id}/closure",
            dedupe_key_prefix=f"closure_blocked:{investigation.id}",
        )
        created += c
        existing += e
    return created, existing


async def _alerts_for_report_approvals(
    db: AsyncSession,
    actor: User,
) -> tuple[int, int]:
    result = await db.execute(
        select(Report, Investigation)
        .join(Investigation, Investigation.id == Report.investigation_id)
        .where(Report.approval_status == "pending_approval")
    )
    created = existing = 0
    for report, investigation in result.all():
        c, e = await _notify_investigation_reviewers(
            db,
            actor_user_id=actor.id,
            investigation=investigation,
            notification_type="report_approval_pending",
            severity="warning",
            title="Report approval pending",
            message=f"{report.title or report.report_type} is pending approval.",
            entity_type="report",
            entity_id=report.id,
            action_url=f"/investigations/{investigation.id}/reports",
            dedupe_key_prefix=f"report_approval_pending:{report.id}",
        )
        created += c
        existing += e
    return created, existing


async def _alerts_for_ready_deliverables(
    db: AsyncSession,
    actor: User,
) -> tuple[int, int]:
    result = await db.execute(
        select(CaseDeliverable, Investigation)
        .join(Investigation, Investigation.id == CaseDeliverable.investigation_id)
        .where(CaseDeliverable.status == "ready")
    )
    created = existing = 0
    for deliverable, investigation in result.all():
        c, e = await _notify_investigation_reviewers(
            db,
            actor_user_id=actor.id,
            investigation=investigation,
            notification_type=(
                "evidence_package_ready"
                if deliverable.deliverable_type == "final_package"
                else "report_ready"
            ),
            severity="info",
            title="Deliverable ready",
            message=f"{deliverable.title} is ready for review.",
            entity_type="case_deliverable",
            entity_id=deliverable.id,
            action_url=f"/investigations/{investigation.id}/closure",
            dedupe_key_prefix=f"deliverable_ready:{deliverable.id}",
        )
        created += c
        existing += e
    return created, existing


async def _alerts_for_assignments(
    db: AsyncSession,
    actor: User,
) -> tuple[int, int]:
    created = existing = 0
    task_result = await db.execute(
        select(InvestigationTask, Investigation)
        .join(Investigation, Investigation.id == InvestigationTask.investigation_id)
        .where(
            InvestigationTask.assigned_to.is_not(None),
            InvestigationTask.status != "completed",
            InvestigationTask.archived_at.is_(None),
        )
    )
    for task, investigation in task_result.all():
        result = await create_notification(
            db,
            user_id=task.assigned_to,
            actor_user_id=actor.id,
            investigation_id=investigation.id,
            notification_type="investigation_assigned",
            severity="info",
            title="Task assigned",
            message=f"{task.title} is assigned to you in {investigation.title}.",
            entity_type="task",
            entity_id=task.id,
            action_url=f"/investigations/{investigation.id}/tasks",
            metadata={"task_status": task.status, "priority": task.priority},
            dedupe_key=f"task_assigned:{task.id}:{task.assigned_to}",
        )
        created += int(result.created)
        existing += int(not result.created)

    finding_result = await db.execute(
        select(Finding, Investigation)
        .join(Investigation, Investigation.id == Finding.investigation_id)
        .where(
            Finding.assigned_to.is_not(None),
            ~Finding.status.in_(
                (
                    "resolved",
                    "mitigated",
                    "false_positive",
                    "archived",
                )
            ),
        )
    )
    for finding, investigation in finding_result.all():
        result = await create_notification(
            db,
            user_id=finding.assigned_to,
            actor_user_id=actor.id,
            investigation_id=investigation.id,
            notification_type="finding_assigned",
            severity="warning" if finding.severity in {"high", "critical"} else "info",
            title="Finding assigned",
            message=f"{finding.title} is assigned to you for analyst review.",
            entity_type="finding",
            entity_id=finding.id,
            action_url=f"/investigations/{investigation.id}/findings",
            metadata={"severity": finding.severity, "status": finding.status},
            dedupe_key=f"finding_assigned:{finding.id}:{finding.assigned_to}",
        )
        created += int(result.created)
        existing += int(not result.created)
    return created, existing


async def _alerts_for_authorization_status(
    db: AsyncSession,
    actor: User,
) -> tuple[int, int]:
    result = await db.execute(
        select(Engagement).where(
            Engagement.authorization_status.in_(("expired", "revoked"))
        )
    )
    created = existing = 0
    admin_ids = await _admin_ids(db)
    for engagement in result.scalars().all():
        recipients = set(admin_ids)
        if engagement.created_by:
            recipients.add(engagement.created_by)
        for recipient_id in recipients:
            item = await create_notification(
                db,
                user_id=recipient_id,
                actor_user_id=actor.id,
                engagement_id=engagement.id,
                notification_type="authorization_expired",
                severity="critical",
                title="Authorization needs review",
                message=(
                    f"{engagement.title} authorization is "
                    f"{engagement.authorization_status.replace('_', ' ')}."
                ),
                entity_type="engagement",
                entity_id=engagement.id,
                action_url=f"/engagements?engagement={engagement.id}",
                metadata={"authorization_status": engagement.authorization_status},
                dedupe_key=(
                    f"authorization:{engagement.id}:"
                    f"{engagement.authorization_status}:{recipient_id}"
                ),
            )
            created += int(item.created)
            existing += int(not item.created)
    return created, existing


async def _notify_investigation_reviewers(
    db: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    investigation: Investigation,
    notification_type: str,
    severity: NotificationSeverity,
    title: str,
    message: str,
    entity_type: str,
    entity_id: uuid.UUID,
    action_url: str,
    dedupe_key_prefix: str,
) -> tuple[int, int]:
    recipient_ids = await _reviewer_recipient_ids(db, investigation)
    return await _notify_recipients(
        db,
        recipient_ids=recipient_ids,
        actor_user_id=actor_user_id,
        investigation=investigation,
        notification_type=notification_type,
        severity=severity,
        title=title,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
        action_url=action_url,
        dedupe_key_prefix=dedupe_key_prefix,
    )


async def _notify_investigation_recipients(
    db: AsyncSession,
    *,
    actor_user_id: uuid.UUID,
    investigation: Investigation,
    notification_type: str,
    severity: NotificationSeverity,
    title: str,
    message: str,
    entity_type: str,
    entity_id: uuid.UUID,
    action_url: str,
    dedupe_key_prefix: str,
) -> tuple[int, int]:
    recipient_ids = await _investigation_recipient_ids(db, investigation)
    return await _notify_recipients(
        db,
        recipient_ids=recipient_ids,
        actor_user_id=actor_user_id,
        investigation=investigation,
        notification_type=notification_type,
        severity=severity,
        title=title,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
        action_url=action_url,
        dedupe_key_prefix=dedupe_key_prefix,
    )


async def _notify_recipients(
    db: AsyncSession,
    *,
    recipient_ids: set[uuid.UUID],
    actor_user_id: uuid.UUID,
    investigation: Investigation,
    notification_type: str,
    severity: NotificationSeverity,
    title: str,
    message: str,
    entity_type: str,
    entity_id: uuid.UUID,
    action_url: str,
    dedupe_key_prefix: str,
) -> tuple[int, int]:
    created = existing = 0
    for recipient_id in recipient_ids:
        result = await create_notification(
            db,
            user_id=recipient_id,
            actor_user_id=actor_user_id,
            investigation_id=investigation.id,
            engagement_id=investigation.engagement_id,
            notification_type=notification_type,
            severity=severity,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            action_url=action_url,
            metadata={"investigation_title": investigation.title},
            dedupe_key=f"{dedupe_key_prefix}:{recipient_id}",
        )
        created += int(result.created)
        existing += int(not result.created)
    return created, existing


async def _reviewer_recipient_ids(
    db: AsyncSession,
    investigation: Investigation,
) -> set[uuid.UUID]:
    recipients = {investigation.owner_id}
    if investigation.reviewer_id:
        recipients.add(investigation.reviewer_id)
    recipients.update(await _admin_ids(db))
    return recipients


async def _investigation_recipient_ids(
    db: AsyncSession,
    investigation: Investigation,
) -> set[uuid.UUID]:
    recipients = await _reviewer_recipient_ids(db, investigation)
    result = await db.execute(
        select(InvestigationMember.user_id).where(
            InvestigationMember.investigation_id == investigation.id,
            InvestigationMember.role.in_(("owner", "admin", "analyst")),
        )
    )
    recipients.update(result.scalars().all())
    return recipients


async def _active_admins(db: AsyncSession) -> list[User]:
    result = await db.execute(
        select(User).where(
            User.role == "admin",
            User.is_active.is_(True),
            User.account_status == "active",
        )
    )
    return list(result.scalars().all())


async def _admin_ids(db: AsyncSession) -> set[uuid.UUID]:
    return {item.id for item in await _active_admins(db)}


def _notification_response(notification: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        user_id=notification.user_id,
        actor_user_id=notification.actor_user_id,
        investigation_id=notification.investigation_id,
        engagement_id=notification.engagement_id,
        entity_type=notification.entity_type,
        entity_id=notification.entity_id,
        notification_type=notification.notification_type,
        severity=_severity(notification.severity),
        title=notification.title,
        message=notification.message,
        action_url=notification.action_url,
        status=_status(notification.status),
        created_at=notification.created_at,
        updated_at=notification.updated_at,
        read_at=notification.read_at,
        dismissed_at=notification.dismissed_at,
        expires_at=notification.expires_at,
        metadata=_safe_metadata(notification.event_metadata),
    )


def _severity(value: str) -> NotificationSeverity:
    if value in {"info", "success", "warning", "critical"}:
        return cast(NotificationSeverity, value)
    return "info"


def _status(value: str) -> NotificationStatus:
    if value in {"unread", "read", "dismissed", "archived"}:
        return cast(NotificationStatus, value)
    return "unread"


def _safe_metadata(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    blocked = {"password", "hashed_password", "token", "api_key", "invite_code"}
    return {
        str(key): item for key, item in value.items() if str(key).lower() not in blocked
    }


def _audit_metadata(notification: Notification) -> dict[str, Any]:
    return {
        "notification_id": str(notification.id),
        "notification_type": notification.notification_type,
        "severity": notification.severity,
        "entity_type": notification.entity_type,
        "entity_id": str(notification.entity_id) if notification.entity_id else None,
    }


def _clean_text(value: str, limit: int) -> str:
    clean = " ".join(value.strip().split())
    return clean[:limit] or "Notification"


def _clean_optional(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    return clean[:limit] if clean else None


def _now() -> datetime:
    return datetime.now(UTC)
