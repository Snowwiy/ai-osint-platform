from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.investigation_escalation import InvestigationEscalation
from app.models.investigation_handoff import InvestigationHandoff
from app.models.investigation_member import InvestigationMember
from app.models.investigation_task import InvestigationTask
from app.models.user import User
from app.schemas.collaboration import (
    CollaborationActivity,
    CollaborationDashboardResponse,
    CollaborationInvestigation,
    CollaborationUser,
    EscalationCreate,
    InvestigationHandoffCreate,
    InvestigationOwnershipResponse,
    InvestigationOwnershipUpdate,
)
from app.services.audit import record_event
from app.services.investigation import (
    CASE_ADMIN_ROLES,
    MUTATION_ROLES,
    InvestigationNotFoundError,
    MemberValidationError,
    ensure_investigation_permission,
    ensure_user_is_member,
    get_investigation,
)

_COORDINATION_ACTIONS = (
    "investigation.owner_changed",
    "investigation.assigned",
    "investigation.watcher_added",
    "investigation.handoff",
    "investigation.state_changed",
    "investigation.escalated",
    "task.assigned",
    "task.status_updated",
    "note.pinned",
)
_CLOSED_TASK_STATUSES = frozenset({"completed"})
_URGENT_FINDING_SEVERITIES = frozenset({"critical", "high"})


class CollaborationValidationError(Exception):
    pass


async def get_ownership(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> InvestigationOwnershipResponse:
    investigation = await get_investigation(db, user, investigation_id)
    members, users = await _members_and_users(db, investigation_id)
    return _ownership_response(investigation, members, users)


async def update_ownership(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    data: InvestigationOwnershipUpdate,
) -> InvestigationOwnershipResponse:
    investigation = await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        CASE_ADMIN_ROLES,
        "Only investigation owners or admins can update ownership",
    )
    members, users = await _members_and_users(db, investigation_id)
    members_by_user = {member.user_id: member for member in members}
    assigned = set(data.assigned_analyst_ids or [])
    watchers = set(data.watcher_ids or [])
    if assigned & watchers:
        raise CollaborationValidationError(
            "A user cannot be both an assigned analyst and a watcher"
        )
    requested_ids = assigned | watchers
    if data.owner_id is not None:
        requested_ids.add(data.owner_id)
    missing = requested_ids - members_by_user.keys()
    if missing:
        raise MemberValidationError(
            "Ownership assignments must reference investigation members"
        )

    previous_owner_id = investigation.owner_id
    if data.owner_id is not None and data.owner_id != previous_owner_id:
        new_owner = members_by_user[data.owner_id]
        for member in members:
            if member.role == "owner" and member.user_id != data.owner_id:
                member.role = "analyst"
                db.add(member)
        new_owner.role = "owner"
        investigation.owner_id = data.owner_id
        db.add(new_owner)
        db.add(investigation)
        await record_event(
            db,
            action="investigation.owner_changed",
            actor_id=user.id,
            resource_type="investigation",
            resource_id=investigation_id,
            investigation_id=investigation_id,
            metadata={
                "previous_owner": str(previous_owner_id),
                "new_owner": str(data.owner_id),
                "reason": data.reason,
            },
        )

    for assigned_id in assigned:
        member = members_by_user[assigned_id]
        if member.user_id != investigation.owner_id and member.role != "analyst":
            previous_role = member.role
            member.role = "analyst"
            db.add(member)
            await record_event(
                db,
                action="investigation.assigned",
                actor_id=user.id,
                resource_type="investigation_member",
                resource_id=member.id,
                investigation_id=investigation_id,
                metadata={
                    "target_user": str(member.user_id),
                    "before_role": previous_role,
                    "after_role": "analyst",
                },
            )

    for watcher_id in watchers:
        member = members_by_user[watcher_id]
        if member.user_id != investigation.owner_id and member.role != "viewer":
            previous_role = member.role
            member.role = "viewer"
            db.add(member)
            await record_event(
                db,
                action="investigation.watcher_added",
                actor_id=user.id,
                resource_type="investigation_member",
                resource_id=member.id,
                investigation_id=investigation_id,
                metadata={
                    "target_user": str(member.user_id),
                    "before_role": previous_role,
                    "after_role": "viewer",
                },
            )

    await db.flush()
    members, users = await _members_and_users(db, investigation_id)
    return _ownership_response(investigation, members, users)


async def create_handoff(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    data: InvestigationHandoffCreate,
) -> InvestigationHandoff:
    investigation = await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        CASE_ADMIN_ROLES,
        "Only investigation owners or admins can hand off a case",
    )
    if data.new_owner_id == investigation.owner_id:
        raise CollaborationValidationError("The new owner already owns this case")
    new_owner_member = await ensure_user_is_member(
        db,
        investigation_id,
        data.new_owner_id,
        "The new owner must be an investigation member",
    )
    previous_owner_id = investigation.owner_id
    previous_owner_member = await ensure_user_is_member(
        db,
        investigation_id,
        previous_owner_id,
    )
    members, _users = await _members_and_users(db, investigation_id)
    for member in members:
        if member.role == "owner" and member.user_id != data.new_owner_id:
            member.role = "analyst"
            db.add(member)
    previous_owner_member.role = "analyst"
    new_owner_member.role = "owner"
    investigation.owner_id = data.new_owner_id
    handoff = InvestigationHandoff(
        investigation_id=investigation_id,
        previous_owner_id=previous_owner_id,
        new_owner_id=data.new_owner_id,
        initiated_by=user.id,
        reason=data.reason,
        context_transfer=data.context_transfer,
        pending_work_summary=data.pending_work_summary,
        unresolved_findings_summary=data.unresolved_findings_summary,
        remediation_status_summary=data.remediation_status_summary,
    )
    db.add(previous_owner_member)
    db.add(new_owner_member)
    db.add(investigation)
    db.add(handoff)
    await db.flush()
    await record_event(
        db,
        action="investigation.owner_changed",
        actor_id=user.id,
        resource_type="investigation",
        resource_id=investigation_id,
        investigation_id=investigation_id,
        metadata={
            "previous_owner": str(previous_owner_id),
            "new_owner": str(data.new_owner_id),
            "reason": data.reason,
        },
    )
    await record_event(
        db,
        action="investigation.handoff",
        actor_id=user.id,
        resource_type="investigation_handoff",
        resource_id=handoff.id,
        investigation_id=investigation_id,
        metadata={
            "previous_owner": str(previous_owner_id),
            "new_owner": str(data.new_owner_id),
            "reason": data.reason,
            "pending_work_summary": data.pending_work_summary,
        },
    )
    await db.refresh(handoff)
    return handoff


async def create_escalation(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    data: EscalationCreate,
) -> InvestigationEscalation:
    await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot escalate investigations",
    )
    escalation = InvestigationEscalation(
        investigation_id=investigation_id,
        level=data.level,
        reason=data.reason,
        created_by=user.id,
    )
    db.add(escalation)
    await db.flush()
    await record_event(
        db,
        action="investigation.escalated",
        actor_id=user.id,
        resource_type="investigation_escalation",
        resource_id=escalation.id,
        investigation_id=investigation_id,
        metadata={"level": data.level, "reason": data.reason},
    )
    await db.refresh(escalation)
    return escalation


async def list_escalations(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> list[InvestigationEscalation]:
    await get_investigation(db, user, investigation_id)
    result = await db.execute(
        select(InvestigationEscalation)
        .where(InvestigationEscalation.investigation_id == investigation_id)
        .order_by(InvestigationEscalation.created_at.desc())
    )
    return list(result.scalars().all())


async def get_collaboration_dashboard(
    db: AsyncSession,
    user: User,
) -> CollaborationDashboardResponse:
    investigations = await _accessible_investigations(db, user)
    if not investigations:
        return CollaborationDashboardResponse(generated_at=_now())
    investigation_ids = [item.id for item in investigations]
    members_result = await db.execute(
        select(InvestigationMember).where(
            InvestigationMember.investigation_id.in_(investigation_ids)
        )
    )
    members = list(members_result.scalars().all())
    tasks_result = await db.execute(
        select(InvestigationTask).where(
            InvestigationTask.investigation_id.in_(investigation_ids),
            InvestigationTask.archived_at.is_(None),
        )
    )
    tasks = list(tasks_result.scalars().all())
    findings_result = await db.execute(
        select(Finding).where(Finding.investigation_id.in_(investigation_ids))
    )
    findings = list(findings_result.scalars().all())
    escalations_result = await db.execute(
        select(InvestigationEscalation).where(
            InvestigationEscalation.investigation_id.in_(investigation_ids)
        )
    )
    escalations = list(escalations_result.scalars().all())
    activity_result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.investigation_id.in_(investigation_ids),
            AuditLog.action.in_(_COORDINATION_ACTIONS),
        )
        .order_by(AuditLog.created_at.desc())
        .limit(50)
    )
    activities = list(activity_result.scalars().all())

    members_by_investigation = _group_by_investigation(members)
    tasks_by_investigation = _group_by_investigation(tasks)
    findings_by_investigation = _group_by_investigation(findings)
    escalations_by_investigation = _group_by_investigation(escalations)
    items: list[CollaborationInvestigation] = []
    for investigation in investigations:
        scope = _collaboration_scope(
            user,
            investigation,
            members_by_investigation.get(investigation.id, []),
        )
        items.append(
            _collaboration_item(
                investigation,
                scope,
                tasks_by_investigation.get(investigation.id, []),
                findings_by_investigation.get(investigation.id, []),
                escalations_by_investigation.get(investigation.id, []),
            )
        )
    items.sort(key=lambda item: item.updated_at, reverse=True)
    investigation_titles = {item.id: item.title for item in investigations}
    recent = [
        CollaborationActivity(
            id=event.id,
            investigation_id=event.investigation_id,
            investigation_title=investigation_titles.get(
                event.investigation_id,
                "Investigation",
            ),
            actor_id=event.actor_id or event.user_id,
            action=event.action,
            timestamp=event.created_at,
            metadata=_safe_metadata(event.event_metadata),
        )
        for event in activities
        if event.investigation_id is not None
    ]
    return CollaborationDashboardResponse(
        generated_at=_now(),
        owned=[item for item in items if item.scope == "owned"],
        assigned=[item for item in items if item.scope == "assigned"],
        watching=[item for item in items if item.scope == "watching"],
        needs_attention=[
            item
            for item in items
            if item.overdue_tasks
            or item.blocked_tasks
            or item.escalation_count
            or item.urgent_findings
        ],
        recent_coordination=recent,
    )


async def _members_and_users(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> tuple[list[InvestigationMember], dict[uuid.UUID, User]]:
    members_result = await db.execute(
        select(InvestigationMember).where(
            InvestigationMember.investigation_id == investigation_id
        )
    )
    members = list(members_result.scalars().all())
    if not members:
        return [], {}
    users_result = await db.execute(
        select(User).where(User.id.in_([member.user_id for member in members]))
    )
    return members, {item.id: item for item in users_result.scalars().all()}


def _ownership_response(
    investigation: Investigation,
    members: list[InvestigationMember],
    users: dict[uuid.UUID, User],
) -> InvestigationOwnershipResponse:
    owner = users.get(investigation.owner_id)
    if owner is None:
        raise InvestigationNotFoundError("Investigation owner not found")
    assigned = [
        users[member.user_id]
        for member in members
        if member.user_id in users
        and member.user_id != investigation.owner_id
        and member.role in {"admin", "analyst"}
    ]
    watchers = [
        users[member.user_id]
        for member in members
        if member.user_id in users and member.role == "viewer"
    ]
    return InvestigationOwnershipResponse(
        investigation_id=investigation.id,
        owner=_user_response(owner),
        assigned_analysts=[_user_response(item) for item in assigned],
        watchers=[_user_response(item) for item in watchers],
    )


def _user_response(user: User) -> CollaborationUser:
    return CollaborationUser(id=user.id, username=user.username, email=user.email)


async def _accessible_investigations(
    db: AsyncSession,
    user: User,
) -> list[Investigation]:
    if user.role == "admin":
        result = await db.execute(select(Investigation))
    else:
        result = await db.execute(
            select(Investigation)
            .join(
                InvestigationMember,
                InvestigationMember.investigation_id == Investigation.id,
            )
            .where(InvestigationMember.user_id == user.id)
        )
    return list(result.scalars().unique().all())


def _group_by_investigation[T](
    items: list[T],
) -> dict[uuid.UUID, list[T]]:
    grouped: dict[uuid.UUID, list[T]] = defaultdict(list)
    for item in items:
        investigation_id = getattr(item, "investigation_id", None)
        if isinstance(investigation_id, uuid.UUID):
            grouped[investigation_id].append(item)
    return grouped


def _collaboration_scope(
    user: User,
    investigation: Investigation,
    members: list[InvestigationMember],
) -> str:
    if investigation.owner_id == user.id:
        return "owned"
    member = next((item for item in members if item.user_id == user.id), None)
    if member is not None and member.role == "viewer":
        return "watching"
    return "assigned"


def _collaboration_item(
    investigation: Investigation,
    scope: str,
    tasks: list[InvestigationTask],
    findings: list[Finding],
    escalations: list[InvestigationEscalation],
) -> CollaborationInvestigation:
    now = _now()
    open_tasks = [item for item in tasks if item.status not in _CLOSED_TASK_STATUSES]
    return CollaborationInvestigation(
        id=investigation.id,
        title=investigation.title,
        state=investigation.status,  # type: ignore[arg-type]
        priority=investigation.priority,
        scope=scope,  # type: ignore[arg-type]
        owner_id=investigation.owner_id,
        open_tasks=len(open_tasks),
        blocked_tasks=sum(item.status == "blocked" for item in open_tasks),
        overdue_tasks=sum(
            item.due_date is not None and item.due_date < now for item in open_tasks
        ),
        urgent_findings=sum(
            item.severity in _URGENT_FINDING_SEVERITIES
            and item.status not in {"mitigated", "false_positive", "archived"}
            for item in findings
        ),
        escalation_count=len(escalations),
        updated_at=investigation.updated_at,
    )


def _safe_metadata(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _now() -> datetime:
    return datetime.now(UTC)
