from __future__ import annotations

import logging
import uuid
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol, cast

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.investigation_member import InvestigationMember
from app.models.investigation_note import InvestigationNote
from app.models.investigation_pin import InvestigationPin
from app.models.investigation_tag import InvestigationTag, InvestigationTagLink
from app.models.investigation_task import InvestigationTask
from app.models.recon_entity import ReconEntity
from app.models.user import User
from app.schemas.case_management import InvestigationWorkflowStatus
from app.schemas.finding import FindingSeverity
from app.schemas.investigation import InvestigationPriority
from app.schemas.operations import (
    AnalystActivitySummary,
    AnalystWorkloadItem,
    AnalystWorkloadResponse,
    DashboardInvestigationItem,
    DashboardHighlightItem,
    DashboardHighlightsResponse,
    DashboardOverviewResponse,
    DashboardTimelineItem,
    DashboardTimelineResponse,
    DashboardTriageResponse,
    FindingsOperationsSummary,
    InfrastructureSignalsSummary,
    InvestigationBulkRequest,
    InvestigationBulkResponse,
    InvestigationBulkResult,
    InvestigationPinResponse,
    InvestigationQueueItem,
    InvestigationQueueResponse,
    InvestigationTriageItem,
    OperationsCount,
    QueueSort,
    QueueStatusFilter,
    QueueTag,
    RemediationOperationsSummary,
    RiskFilter,
    SignalCount,
    TriageCategory,
    TriageComponents,
)
from app.schemas.productivity import (
    InvestigationPriorityUpdate,
    InvestigationTagsUpdate,
)
from app.services.audit import record_event
from app.services.investigation import (
    CASE_ADMIN_ROLES,
    MUTATION_ROLES,
    ForbiddenError,
    InvestigationNotFoundError,
    archive_investigation,
    ensure_investigation_permission,
    ensure_owner_permission,
    ensure_user_is_member,
    get_investigation,
    update_investigation_status,
)
from app.services.playbook import start_playbook_run
from app.services.productivity import (
    generate_investigation_summary,
    update_investigation_priority,
    update_investigation_tags,
)

logger = logging.getLogger(__name__)

_OPEN_FINDING_STATUSES = {"new", "under_review", "accepted_risk", "open"}
_CLOSED_REMEDIATION_STATUSES = {"remediated", "accepted_risk", "false_positive"}
_CLOSED_TASK_STATUSES = {"completed"}
_SEVERITIES: tuple[FindingSeverity, ...] = (
    "critical",
    "high",
    "medium",
    "low",
    "info",
)
_ACTIVE_INVESTIGATION_STATUSES = {
    "intake",
    "active",
    "monitoring",
    "remediation",
    "validation",
}
_TIMELINE_ACTIONS = {
    "recon.executed",
    "findings.generated",
    "finding.remediation_updated",
    "finding.verified",
    "playbook.started",
    "playbook.completed",
    "note.created",
    "bookmark.created",
    "report.generated",
    "report.failed",
    "report.retried",
    "report.archived",
    "report.restored",
    "report.bulk_generated",
    "report.downloaded",
    "investigation.member_added",
    "investigation.member_removed",
    "investigation.member_role_changed",
    "investigation.owner_transferred",
    "investigation.bulk_update",
    "investigation.pinned",
    "investigation.owner_changed",
    "investigation.assigned",
    "investigation.watcher_added",
    "investigation.handoff",
    "investigation.state_changed",
    "investigation.stage_changed",
    "investigation.escalated",
    "task.assigned",
    "task.status_updated",
    "note.pinned",
}


class OperationsValidationError(Exception):
    pass


class _InvestigationScoped(Protocol):
    investigation_id: uuid.UUID


@dataclass(frozen=True)
class OperationsDataset:
    investigations: list[Investigation]
    members: list[InvestigationMember]
    findings: list[Finding]
    tasks: list[InvestigationTask]
    entities: list[ReconEntity]
    notes: list[InvestigationNote]
    audit_events: list[AuditLog]
    tags_by_investigation: dict[uuid.UUID, list[InvestigationTag]]
    pinned_ids: set[uuid.UUID]


async def get_dashboard_overview(
    db: AsyncSession,
    user: User,
) -> DashboardOverviewResponse:
    dataset = await _load_dataset(db, user)
    triage_items = _triage_items(dataset)
    triage_by_id = {item.investigation_id: item for item in triage_items}
    queue_items = _queue_items(dataset, triage_by_id)
    now = _now()
    open_tasks = [
        task for task in dataset.tasks if task.status not in _CLOSED_TASK_STATUSES
    ]
    completed_tasks = [
        task for task in dataset.tasks if task.status == "completed"
    ]
    overdue_tasks = [
        task
        for task in open_tasks
        if task.due_date is not None and task.due_date < now
    ]
    unresolved = [
        finding for finding in dataset.findings if _finding_is_unresolved(finding)
    ]
    recent_cutoff = now - timedelta(days=30)
    recent_audits = [
        event for event in dataset.audit_events if event.created_at >= recent_cutoff
    ]
    response = DashboardOverviewResponse(
        generated_at=now,
        investigations=OperationsCount(
            total=len(dataset.investigations),
            active=sum(
                item.status in _ACTIVE_INVESTIGATION_STATUSES
                for item in dataset.investigations
            ),
            archived=sum(item.status == "archived" for item in dataset.investigations),
            urgent=sum(
                item.priority == "urgent" and item.status != "archived"
                for item in dataset.investigations
            ),
            overdue=sum(
                item.due_date is not None
                and item.due_date < now.date()
                and item.status != "archived"
                for item in dataset.investigations
            ),
        ),
        findings=FindingsOperationsSummary(
            total=len(dataset.findings),
            unresolved=len(unresolved),
            by_severity={
                severity: sum(
                    finding.severity == severity for finding in dataset.findings
                )
                for severity in _SEVERITIES
            },
        ),
        remediation=RemediationOperationsSummary(
            open_tasks=len(open_tasks),
            overdue_tasks=len(overdue_tasks),
            blocked_tasks=sum(task.status == "blocked" for task in dataset.tasks),
            completed_tasks=len(completed_tasks),
            completion_percent=_completion_percent(
                len(completed_tasks),
                len(dataset.tasks),
            ),
        ),
        analyst_activity=AnalystActivitySummary(
            recent_actions=len(recent_audits),
            investigations_touched=len(
                {
                    event.investigation_id
                    for event in recent_audits
                    if event.investigation_id is not None
                }
            ),
            notes_created=sum(
                note.created_at >= recent_cutoff for note in dataset.notes
            ),
            remediation_completed=sum(
                event.action in {"finding.verified", "task.completed"}
                for event in recent_audits
            ),
        ),
        infrastructure_signals=_infrastructure_signals(dataset),
        pinned_investigations=[
            _dashboard_item(item)
            for item in sorted(
                (item for item in queue_items if item.pinned),
                key=lambda item: (item.triage_score, item.updated_at),
                reverse=True,
            )[:8]
        ],
        recent_investigations=[
            _dashboard_item(item)
            for item in sorted(
                queue_items,
                key=lambda item: item.updated_at,
                reverse=True,
            )[:8]
        ],
    )
    await record_event(
        db,
        action="dashboard.summary_generated",
        actor_id=user.id,
        resource_type="dashboard",
        metadata={"investigation_count": len(dataset.investigations)},
    )
    return response


async def get_dashboard_triage(
    db: AsyncSession,
    user: User,
) -> DashboardTriageResponse:
    dataset = await _load_dataset(db, user)
    items = sorted(
        _triage_items(dataset),
        key=lambda item: (item.score, item.title.lower()),
        reverse=True,
    )
    await record_event(
        db,
        action="triage.score_updated",
        actor_id=user.id,
        resource_type="dashboard",
        metadata={"investigation_count": len(items)},
    )
    return DashboardTriageResponse(
        generated_at=_now(),
        total=len(items),
        items=items,
    )


async def get_dashboard_highlights(
    db: AsyncSession,
    user: User,
) -> DashboardHighlightsResponse:
    dataset = await _load_dataset(db, user)
    now = _now()
    investigations_by_id = {
        investigation.id: investigation for investigation in dataset.investigations
    }
    findings_by_investigation = _group_by_investigation(dataset.findings)
    tasks_by_investigation = _group_by_investigation(dataset.tasks)
    triage_by_id = {
        item.investigation_id: item for item in _triage_items(dataset)
    }

    needs_attention: list[DashboardHighlightItem] = []
    overdue_remediation: list[DashboardHighlightItem] = []
    without_findings: list[DashboardHighlightItem] = []
    recently_archived: list[DashboardHighlightItem] = []
    for investigation in dataset.investigations:
        triage = triage_by_id.get(investigation.id)
        findings = findings_by_investigation.get(investigation.id, [])
        tasks = tasks_by_investigation.get(investigation.id, [])
        overdue = [
            task
            for task in tasks
            if task.status not in _CLOSED_TASK_STATUSES
            and task.due_date is not None
            and task.due_date < now
        ]
        if (
            investigation.status != "archived"
            and triage is not None
            and (triage.score >= 51 or investigation.priority == "urgent")
        ):
            needs_attention.append(
                DashboardHighlightItem(
                    investigation_id=investigation.id,
                    title=investigation.title,
                    kind="needs_attention",
                    detail=(
                        f"Triage {triage.score}/100; "
                        f"{len(findings)} stored findings."
                    ),
                    severity=_highlight_severity(triage.score),
                    occurred_at=investigation.updated_at,
                )
            )
        if overdue:
            oldest_due = min(task.due_date for task in overdue if task.due_date)
            overdue_remediation.append(
                DashboardHighlightItem(
                    investigation_id=investigation.id,
                    title=investigation.title,
                    kind="overdue_remediation",
                    detail=(
                        f"{len(overdue)} overdue remediation task(s); "
                        f"oldest due {oldest_due.date().isoformat()}."
                    ),
                    severity="high",
                    occurred_at=oldest_due,
                )
            )
        if investigation.status != "archived" and not findings:
            without_findings.append(
                DashboardHighlightItem(
                    investigation_id=investigation.id,
                    title=investigation.title,
                    kind="without_findings",
                    detail="No evidence-backed findings are stored yet.",
                    severity="low",
                    occurred_at=investigation.updated_at,
                )
            )
        if (
            investigation.status == "archived"
            and investigation.updated_at >= now - timedelta(days=30)
        ):
            recently_archived.append(
                DashboardHighlightItem(
                    investigation_id=investigation.id,
                    title=investigation.title,
                    kind="recently_archived",
                    detail="Governance-controlled archive updated in the last 30 days.",
                    severity="info",
                    occurred_at=investigation.updated_at,
                )
            )

    recent_activity = [
        DashboardHighlightItem(
            investigation_id=event.investigation_id,
            title=investigations_by_id[event.investigation_id].title,
            kind="recent_activity",
            detail=event.action.replace(".", " ").replace("_", " ").title(),
            severity="info",
            occurred_at=event.created_at,
        )
        for event in sorted(
            (
                event
                for event in dataset.audit_events
                if event.investigation_id in investigations_by_id
            ),
            key=lambda item: item.created_at,
            reverse=True,
        )[:8]
        if event.investigation_id is not None
    ]
    return DashboardHighlightsResponse(
        generated_at=now,
        needs_attention=sorted(
            needs_attention,
            key=lambda item: item.occurred_at,
            reverse=True,
        )[:8],
        overdue_remediation=sorted(
            overdue_remediation,
            key=lambda item: item.occurred_at,
        )[:8],
        without_findings=sorted(
            without_findings,
            key=lambda item: item.occurred_at,
            reverse=True,
        )[:8],
        recently_archived=sorted(
            recently_archived,
            key=lambda item: item.occurred_at,
            reverse=True,
        )[:8],
        recent_activity=recent_activity,
    )


def _highlight_severity(score: int) -> Literal["medium", "high", "critical"]:
    if score >= 76:
        return "critical"
    if score >= 61:
        return "high"
    return "medium"


async def get_investigation_queue(
    db: AsyncSession,
    user: User,
    *,
    status: QueueStatusFilter | None = None,
    priority: str | None = None,
    assigned_analyst: uuid.UUID | None = None,
    tag_id: uuid.UUID | None = None,
    risk_level: RiskFilter | None = None,
    sort: QueueSort = "highest_risk",
    skip: int = 0,
    limit: int = 50,
) -> InvestigationQueueResponse:
    dataset = await _load_dataset(db, user)
    triage_by_id = {
        item.investigation_id: item for item in _triage_items(dataset)
    }
    items = _queue_items(dataset, triage_by_id)
    if status is not None:
        items = [item for item in items if _matches_status(item.status, status)]
    if priority is not None:
        items = [item for item in items if item.priority == priority]
    if assigned_analyst is not None:
        items = [
            item
            for item in items
            if assigned_analyst in item.assigned_analyst_ids
        ]
    if tag_id is not None:
        items = [
            item for item in items if any(tag.id == tag_id for tag in item.tags)
        ]
    if risk_level is not None:
        items = [item for item in items if item.risk_level == risk_level]
    ordered = _sort_queue(items, sort)
    return InvestigationQueueResponse(
        total=len(ordered),
        skip=skip,
        limit=limit,
        items=ordered[skip : skip + limit],
    )


async def get_dashboard_timeline(
    db: AsyncSession,
    user: User,
    *,
    actor_id: uuid.UUID | None = None,
    investigation_id: uuid.UUID | None = None,
    event_type: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> DashboardTimelineResponse:
    investigations = await _accessible_investigations(db, user)
    accessible_ids = {item.id for item in investigations}
    if investigation_id is not None and investigation_id not in accessible_ids:
        raise InvestigationNotFoundError("Investigation not found")
    if not accessible_ids:
        return DashboardTimelineResponse(
            total=0,
            limit=limit,
            offset=offset,
            items=[],
        )
    stmt = select(AuditLog).where(
        AuditLog.investigation_id.in_(accessible_ids),
        AuditLog.action.in_(_TIMELINE_ACTIONS),
    )
    if actor_id is not None:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if investigation_id is not None:
        stmt = stmt.where(AuditLog.investigation_id == investigation_id)
    if event_type:
        stmt = stmt.where(AuditLog.action == event_type)
    if start_date:
        stmt = stmt.where(AuditLog.created_at >= start_date)
    if end_date:
        stmt = stmt.where(AuditLog.created_at <= end_date)
    result = await db.execute(stmt.order_by(AuditLog.created_at.desc()))
    events = list(result.scalars().all())
    users = await _users_by_id(
        db,
        {event.actor_id for event in events if event.actor_id is not None},
    )
    titles = {item.id: item.title for item in investigations}
    items = [
        DashboardTimelineItem(
            id=event.id,
            timestamp=event.created_at,
            actor_id=event.actor_id,
            actor_name=(
                users[event.actor_id].username
                if event.actor_id is not None and event.actor_id in users
                else None
            ),
            investigation_id=event.investigation_id,
            investigation_title=(
                titles.get(event.investigation_id)
                if event.investigation_id is not None
                else None
            ),
            event_type=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            metadata=_json_object(event.event_metadata or event.details),
        )
        for event in events
    ]
    return DashboardTimelineResponse(
        total=len(items),
        limit=limit,
        offset=offset,
        items=items[offset : offset + limit],
    )


async def get_analyst_workload(
    db: AsyncSession,
    user: User,
) -> AnalystWorkloadResponse:
    dataset = await _load_dataset(db, user)
    now = _now()
    recent_cutoff = now - timedelta(days=30)
    previous_cutoff = now - timedelta(days=60)
    analyst_ids = {
        member.user_id
        for member in dataset.members
        if member.role in MUTATION_ROLES
    }
    analyst_ids.update(
        investigation.owner_id for investigation in dataset.investigations
    )
    analyst_ids.update(
        investigation.reviewer_id
        for investigation in dataset.investigations
        if investigation.reviewer_id is not None
    )
    users = await _users_by_id(db, analyst_ids)
    items: list[AnalystWorkloadItem] = []
    for analyst_id, analyst in users.items():
        active_ids = {
            member.investigation_id
            for member in dataset.members
            if member.user_id == analyst_id
            and member.role != "viewer"
            and any(
                investigation.id == member.investigation_id
                and investigation.status in _ACTIVE_INVESTIGATION_STATUSES
                for investigation in dataset.investigations
            )
        }
        completed_recent = sum(
            task.assigned_to == analyst_id
            and task.completed_at is not None
            and task.completed_at >= recent_cutoff
            for task in dataset.tasks
        )
        completed_previous = sum(
            task.assigned_to == analyst_id
            and task.completed_at is not None
            and previous_cutoff <= task.completed_at < recent_cutoff
            for task in dataset.tasks
        )
        items.append(
            AnalystWorkloadItem(
                user_id=analyst_id,
                username=analyst.username,
                email=analyst.email,
                active_investigations=len(active_ids),
                overdue_remediation=sum(
                    task.assigned_to == analyst_id
                    and task.status not in _CLOSED_TASK_STATUSES
                    and task.due_date is not None
                    and task.due_date < now
                    for task in dataset.tasks
                ),
                findings_assigned=sum(
                    finding.assigned_to == analyst_id
                    or finding.reviewed_by == analyst_id
                    for finding in dataset.findings
                ),
                notes_added_30d=sum(
                    note.created_by == analyst_id and note.created_at >= recent_cutoff
                    for note in dataset.notes
                ),
                remediations_completed_30d=completed_recent,
                previous_30d_completed=completed_previous,
                completion_trend=_trend(completed_recent, completed_previous),
            )
        )
    return AnalystWorkloadResponse(
        generated_at=now,
        total=len(items),
        items=sorted(
            items,
            key=lambda item: (
                item.overdue_remediation,
                item.active_investigations,
                item.username.lower(),
            ),
            reverse=True,
        ),
    )


async def get_investigation_operational_snapshot(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> tuple[dict[str, object], list[str]]:
    await get_investigation(db, user, investigation_id)
    dataset = await _load_dataset(db, user)
    triage = next(
        (
            item
            for item in _triage_items(dataset)
            if item.investigation_id == investigation_id
        ),
        None,
    )
    findings = [
        finding
        for finding in dataset.findings
        if finding.investigation_id == investigation_id
    ]
    tasks = [
        task
        for task in dataset.tasks
        if task.investigation_id == investigation_id
    ]
    members = [
        member
        for member in dataset.members
        if member.investigation_id == investigation_id
    ]
    now = _now()
    unresolved = [
        finding for finding in findings if _finding_is_unresolved(finding)
    ]
    open_tasks = [
        task for task in tasks if task.status not in _CLOSED_TASK_STATUSES
    ]
    overdue_tasks = [
        task
        for task in open_tasks
        if task.due_date is not None and task.due_date < now
    ]
    recurring_keys = {
        (entity.entity_type, entity.value)
        for entity in dataset.entities
        if entity.investigation_id == investigation_id
        and entity.entity_type in {"Domain", "Subdomain", "IPAddress", "Technology"}
    }
    recurring: list[str] = []
    for entity_type, value in sorted(recurring_keys):
        investigation_count = len(
            {
                entity.investigation_id
                for entity in dataset.entities
                if entity.entity_type == entity_type and entity.value == value
            }
        )
        if investigation_count > 1:
            recurring.append(
                f"{entity_type}: {value} ({investigation_count} investigations)"
            )
    return (
        {
            "triage_score": triage.score if triage else 0,
            "triage_category": triage.category if triage else "low_attention",
            "unresolved_findings": len(unresolved),
            "open_tasks": len(open_tasks),
            "overdue_tasks": len(overdue_tasks),
            "assigned_analysts": sum(
                member.role != "viewer" for member in members
            ),
            "remediation_completion_percent": _completion_percent(
                sum(task.status == "completed" for task in tasks),
                len(tasks),
            ),
        },
        recurring[:10],
    )


async def set_investigation_pin(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    *,
    pinned: bool,
) -> InvestigationPinResponse:
    await get_investigation(db, user, investigation_id)
    result = await db.execute(
        select(InvestigationPin).where(
            InvestigationPin.investigation_id == investigation_id,
            InvestigationPin.user_id == user.id,
        )
    )
    existing = result.scalar_one_or_none()
    if pinned and existing is None:
        db.add(
            InvestigationPin(
                investigation_id=investigation_id,
                user_id=user.id,
            )
        )
    elif not pinned and existing is not None:
        await db.delete(existing)
    await record_event(
        db,
        action="investigation.pinned",
        actor_id=user.id,
        resource_type="investigation",
        resource_id=investigation_id,
        investigation_id=investigation_id,
        metadata={"pinned": pinned},
    )
    return InvestigationPinResponse(
        investigation_id=investigation_id,
        user_id=user.id,
        pinned=pinned,
    )


async def apply_investigation_bulk_action(
    db: AsyncSession,
    user: User,
    body: InvestigationBulkRequest,
) -> InvestigationBulkResponse:
    results: list[InvestigationBulkResult] = []
    for investigation_id in body.investigation_ids:
        try:
            async with db.begin_nested():
                detail = await _apply_single_bulk_action(
                    db,
                    user,
                    investigation_id,
                    body,
                )
        except (
            ForbiddenError,
            InvestigationNotFoundError,
            OperationsValidationError,
            ValueError,
        ) as exc:
            results.append(
                InvestigationBulkResult(
                    investigation_id=investigation_id,
                    success=False,
                    detail=str(exc),
                )
            )
        except Exception as exc:
            logger.warning(
                "bulk action %s failed for investigation %s: %s",
                body.action,
                investigation_id,
                exc,
            )
            results.append(
                InvestigationBulkResult(
                    investigation_id=investigation_id,
                    success=False,
                    detail="The operation could not be completed.",
                )
            )
        else:
            results.append(
                InvestigationBulkResult(
                    investigation_id=investigation_id,
                    success=True,
                    detail=detail,
                )
            )
            await record_event(
                db,
                action="investigation.bulk_update",
                actor_id=user.id,
                resource_type="investigation",
                resource_id=investigation_id,
                investigation_id=investigation_id,
                metadata={"action": body.action, "detail": detail},
            )
    succeeded = sum(item.success for item in results)
    await record_event(
        db,
        action="investigation.bulk_update",
        actor_id=user.id,
        resource_type="investigation",
        metadata={
            "action": body.action,
            "investigation_ids": [
                str(investigation_id)
                for investigation_id in body.investigation_ids
            ],
            "succeeded": succeeded,
            "failed": len(results) - succeeded,
        },
    )
    return InvestigationBulkResponse(
        action=body.action,
        requested=len(results),
        succeeded=succeeded,
        failed=len(results) - succeeded,
        results=results,
    )


async def _apply_single_bulk_action(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    body: InvestigationBulkRequest,
) -> str:
    investigation = await get_investigation(db, user, investigation_id)
    if body.action == "assign_owner":
        if body.owner_id is None:
            raise OperationsValidationError("owner_id is required")
        await ensure_owner_permission(
            db,
            user,
            investigation_id,
            "Only owners or platform admins can assign case ownership",
        )
        await ensure_user_is_member(
            db,
            investigation_id,
            body.owner_id,
            "The new owner must be an investigation member",
        )
        await _transfer_owner(db, user, investigation, body.owner_id)
        return "Owner assigned."
    if body.action == "assign_reviewer":
        if body.reviewer_id is None:
            raise OperationsValidationError("reviewer_id is required")
        await ensure_investigation_permission(
            db,
            user,
            investigation_id,
            CASE_ADMIN_ROLES,
            "Only owners or admins can assign analysts",
        )
        await ensure_user_is_member(
            db,
            investigation_id,
            body.reviewer_id,
            "The reviewer must be an investigation member",
        )
        investigation.reviewer_id = body.reviewer_id
        db.add(investigation)
        await record_event(
            db,
            action="analyst.assigned",
            actor_id=user.id,
            resource_type="investigation",
            resource_id=investigation_id,
            investigation_id=investigation_id,
            metadata={"reviewer_id": str(body.reviewer_id)},
        )
        return "Lead analyst assigned."
    if body.action == "update_priority":
        if body.priority is None:
            raise OperationsValidationError("priority is required")
        await update_investigation_priority(
            db,
            user,
            investigation_id,
            InvestigationPriorityUpdate(
                priority=body.priority,
                business_impact=investigation.business_impact,
                due_date=investigation.due_date,
            ),
        )
        return "Priority updated."
    if body.action == "update_tags":
        await update_investigation_tags(
            db,
            user,
            investigation_id,
            InvestigationTagsUpdate(tag_ids=body.tag_ids or []),
        )
        return "Tags updated."
    if body.action == "archive":
        await archive_investigation(db, user, investigation_id)
        return "Investigation archived."
    if body.action == "change_status":
        if body.status is None:
            raise OperationsValidationError("status is required")
        await update_investigation_status(
            db,
            user,
            investigation_id,
            body.status,
            reason="Bulk operations workflow update",
        )
        return "Workflow status updated."
    if body.action == "add_playbook":
        if body.playbook_id is None:
            raise OperationsValidationError("playbook_id is required")
        await ensure_investigation_permission(
            db,
            user,
            investigation_id,
            MUTATION_ROLES,
            "Viewers cannot start playbooks",
        )
        finding = await _highest_priority_finding(db, investigation_id)
        if finding is None:
            raise OperationsValidationError(
                "A stored unresolved finding is required to start a playbook"
            )
        await start_playbook_run(db, user, finding.id, body.playbook_id)
        return f"Playbook started for finding '{finding.title}'."
    if body.action == "generate_summary":
        await generate_investigation_summary(db, user, investigation_id)
        return "Deterministic summary generated."
    raise OperationsValidationError("Unsupported bulk action")


async def _transfer_owner(
    db: AsyncSession,
    user: User,
    investigation: Investigation,
    new_owner_id: uuid.UUID,
) -> None:
    if investigation.owner_id == new_owner_id:
        return
    old_owner_id = investigation.owner_id
    memberships = await db.execute(
        select(InvestigationMember).where(
            InvestigationMember.investigation_id == investigation.id,
            InvestigationMember.user_id.in_((old_owner_id, new_owner_id)),
        )
    )
    by_user = {member.user_id: member for member in memberships.scalars().all()}
    new_owner = by_user.get(new_owner_id)
    if new_owner is None:
        raise OperationsValidationError(
            "The new owner must be an investigation member"
        )
    previous_owner = by_user.get(old_owner_id)
    if previous_owner is not None:
        previous_owner.role = "admin"
        db.add(previous_owner)
    new_owner.role = "owner"
    investigation.owner_id = new_owner_id
    db.add(new_owner)
    db.add(investigation)
    await record_event(
        db,
        action="investigation.owner_transferred",
        actor_id=user.id,
        resource_type="investigation",
        resource_id=investigation.id,
        investigation_id=investigation.id,
        metadata={
            "previous_owner": str(old_owner_id),
            "new_owner": str(new_owner_id),
        },
    )


async def _load_dataset(
    db: AsyncSession,
    user: User,
) -> OperationsDataset:
    investigations = await _accessible_investigations(db, user)
    investigation_ids = [item.id for item in investigations]
    if not investigation_ids:
        return OperationsDataset(
            investigations=[],
            members=[],
            findings=[],
            tasks=[],
            entities=[],
            notes=[],
            audit_events=[],
            tags_by_investigation={},
            pinned_ids=set(),
        )
    members = await _load_models(
        db,
        select(InvestigationMember).where(
            InvestigationMember.investigation_id.in_(investigation_ids)
        ),
    )
    findings = await _load_models(
        db,
        select(Finding).where(Finding.investigation_id.in_(investigation_ids)),
    )
    tasks = await _load_models(
        db,
        select(InvestigationTask).where(
            InvestigationTask.investigation_id.in_(investigation_ids),
            InvestigationTask.archived_at.is_(None),
        ),
    )
    entities = await _load_models(
        db,
        select(ReconEntity).where(
            ReconEntity.investigation_id.in_(investigation_ids)
        ),
    )
    notes = await _load_models(
        db,
        select(InvestigationNote).where(
            InvestigationNote.investigation_id.in_(investigation_ids)
        ),
    )
    audits = await _load_models(
        db,
        select(AuditLog).where(AuditLog.investigation_id.in_(investigation_ids)),
    )
    tag_rows = await db.execute(
        select(InvestigationTagLink.investigation_id, InvestigationTag)
        .join(
            InvestigationTag,
            InvestigationTag.id == InvestigationTagLink.tag_id,
        )
        .where(InvestigationTagLink.investigation_id.in_(investigation_ids))
    )
    tags_by_investigation: dict[uuid.UUID, list[InvestigationTag]] = defaultdict(
        list
    )
    for investigation_id, tag in tag_rows.all():
        tags_by_investigation[investigation_id].append(tag)
    pins = await db.execute(
        select(InvestigationPin.investigation_id).where(
            InvestigationPin.user_id == user.id,
            InvestigationPin.investigation_id.in_(investigation_ids),
        )
    )
    return OperationsDataset(
        investigations=investigations,
        members=members,
        findings=findings,
        tasks=tasks,
        entities=entities,
        notes=notes,
        audit_events=audits,
        tags_by_investigation=dict(tags_by_investigation),
        pinned_ids=set(pins.scalars().all()),
    )


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


async def _load_models[T](
    db: AsyncSession,
    statement: Select[tuple[T]],
) -> list[T]:
    result = await db.execute(statement)
    return list(result.scalars().all())


def _triage_items(dataset: OperationsDataset) -> list[InvestigationTriageItem]:
    findings_by_investigation = _group_by_investigation(dataset.findings)
    tasks_by_investigation = _group_by_investigation(dataset.tasks)
    recurring_by_investigation = _recurring_evidence_counts(dataset.entities)
    return [
        _triage_item(
            investigation,
            findings_by_investigation.get(investigation.id, []),
            tasks_by_investigation.get(investigation.id, []),
            recurring_by_investigation.get(investigation.id, 0),
        )
        for investigation in dataset.investigations
    ]


def _triage_item(
    investigation: Investigation,
    findings: list[Finding],
    tasks: list[InvestigationTask],
    recurring_evidence_count: int,
) -> InvestigationTriageItem:
    unresolved = [finding for finding in findings if _finding_is_unresolved(finding)]
    severity_points = min(
        40,
        sum(
            {
                "critical": 20,
                "high": 12,
                "medium": 6,
                "low": 2,
                "info": 0,
            }.get(finding.severity, 0)
            for finding in unresolved
        ),
    )
    unresolved_points = (
        min(15, round((len(unresolved) / max(1, len(findings))) * 15))
        if unresolved
        else 0
    )
    unplanned = sum(
        finding.remediation_status in {"not_started", "validating"}
        for finding in unresolved
    )
    remediation_points = (
        min(15, round((unplanned / max(1, len(unresolved))) * 15))
        if unresolved
        else 0
    )
    overdue_count = sum(
        task.status not in _CLOSED_TASK_STATUSES
        and task.due_date is not None
        and task.due_date < _now()
        for task in tasks
    )
    overdue_points = min(15, overdue_count * 5)
    recurring_points = min(10, recurring_evidence_count * 2)
    priority_points = {
        "low": 0,
        "medium": 5,
        "high": 10,
        "urgent": 15,
    }.get(investigation.priority, 5)
    components = TriageComponents(
        severity=severity_points,
        unresolved=unresolved_points,
        remediation=remediation_points,
        overdue_tasks=overdue_points,
        recurring_evidence=recurring_points,
        priority=priority_points,
    )
    score = min(
        100,
        sum(
            (
                components.severity,
                components.unresolved,
                components.remediation,
                components.overdue_tasks,
                components.recurring_evidence,
                components.priority,
            )
        ),
    )
    reasons: list[str] = []
    if severity_points:
        reasons.append(f"{len(unresolved)} unresolved finding(s) affect severity.")
    if unplanned:
        reasons.append(f"{unplanned} finding(s) lack a remediation plan.")
    if overdue_count:
        reasons.append(f"{overdue_count} remediation task(s) are overdue.")
    if recurring_evidence_count:
        reasons.append(
            f"{recurring_evidence_count} recurring infrastructure signal(s) overlap."
        )
    if investigation.priority in {"high", "urgent"}:
        reasons.append(f"Investigation priority is {investigation.priority}.")
    if not reasons:
        reasons.append("No elevated deterministic triage signals are stored.")
    return InvestigationTriageItem(
        investigation_id=investigation.id,
        title=investigation.title,
        score=score,
        category=_triage_category(score),
        components=components,
        reasons=reasons,
    )


def _queue_items(
    dataset: OperationsDataset,
    triage_by_id: dict[uuid.UUID, InvestigationTriageItem],
) -> list[InvestigationQueueItem]:
    findings_by_investigation = _group_by_investigation(dataset.findings)
    tasks_by_investigation = _group_by_investigation(dataset.tasks)
    members_by_investigation = _group_by_investigation(dataset.members)
    audit_by_investigation = _group_by_optional_investigation(dataset.audit_events)
    items: list[InvestigationQueueItem] = []
    now = _now()
    for investigation in dataset.investigations:
        findings = findings_by_investigation.get(investigation.id, [])
        tasks = tasks_by_investigation.get(investigation.id, [])
        open_tasks = [
            task for task in tasks if task.status not in _CLOSED_TASK_STATUSES
        ]
        overdue_tasks = [
            task
            for task in open_tasks
            if task.due_date is not None and task.due_date < now
        ]
        risk_score = max((finding.risk_score for finding in findings), default=0)
        triage = triage_by_id[investigation.id]
        assigned_ids = {
            member.user_id
            for member in members_by_investigation.get(investigation.id, [])
            if member.role != "viewer"
        }
        assigned_ids.add(investigation.owner_id)
        if investigation.reviewer_id is not None:
            assigned_ids.add(investigation.reviewer_id)
        activity_dates = [
            investigation.updated_at,
            *(
                event.created_at
                for event in audit_by_investigation.get(investigation.id, [])
            ),
            *(finding.updated_at for finding in findings),
            *(task.updated_at for task in tasks),
        ]
        items.append(
            InvestigationQueueItem(
                id=investigation.id,
                title=investigation.title,
                status=cast(InvestigationWorkflowStatus, investigation.status),
                priority=cast(InvestigationPriority, investigation.priority),
                owner_id=investigation.owner_id,
                reviewer_id=investigation.reviewer_id,
                assigned_analyst_ids=sorted(assigned_ids, key=str),
                due_date=investigation.due_date,
                overdue=(
                    investigation.due_date is not None
                    and investigation.due_date < now.date()
                    and investigation.status != "archived"
                ),
                risk_score=risk_score,
                risk_level=_risk_level(risk_score),
                triage_score=triage.score,
                triage_category=triage.category,
                findings_count=len(findings),
                unresolved_findings=sum(
                    _finding_is_unresolved(finding) for finding in findings
                ),
                open_tasks=len(open_tasks),
                overdue_tasks=len(overdue_tasks),
                tags=[
                    QueueTag(id=tag.id, name=tag.name, color=tag.color)
                    for tag in sorted(
                        dataset.tags_by_investigation.get(investigation.id, []),
                        key=lambda item: item.name,
                    )
                ],
                pinned=investigation.id in dataset.pinned_ids,
                last_activity_at=max(activity_dates),
                created_at=investigation.created_at,
                updated_at=investigation.updated_at,
            )
        )
    return items


def _dashboard_item(item: InvestigationQueueItem) -> DashboardInvestigationItem:
    return DashboardInvestigationItem(
        id=item.id,
        title=item.title,
        status=item.status,
        priority=item.priority,
        risk_score=item.risk_score,
        triage_score=item.triage_score,
        triage_category=item.triage_category,
        findings_count=item.findings_count,
        overdue_tasks=item.overdue_tasks,
        pinned=item.pinned,
        updated_at=item.updated_at,
    )


def _infrastructure_signals(
    dataset: OperationsDataset,
) -> InfrastructureSignalsSummary:
    return InfrastructureSignalsSummary(
        recurring_technologies=_signal_counts(
            (
                entity.value,
                entity.investigation_id,
            )
            for entity in dataset.entities
            if entity.entity_type == "Technology"
        ),
        repeated_findings=_signal_counts(
            (finding.title, finding.investigation_id)
            for finding in dataset.findings
        ),
        recurring_domains=_signal_counts(
            (entity.value, entity.investigation_id)
            for entity in dataset.entities
            if entity.entity_type in {"Domain", "Subdomain"}
        ),
        recurring_ips=_signal_counts(
            (entity.value, entity.investigation_id)
            for entity in dataset.entities
            if entity.entity_type == "IPAddress"
        ),
    )


def _signal_counts(
    values: Iterable[tuple[str, uuid.UUID]],
    *,
    limit: int = 8,
) -> list[SignalCount]:
    counts: Counter[str] = Counter()
    investigations_by_value: dict[str, set[uuid.UUID]] = defaultdict(set)
    for raw_value, investigation_id in values:
        value = str(raw_value).strip()
        if not value:
            continue
        counts[value] += 1
        investigations_by_value[value].add(investigation_id)
    recurring = [
        SignalCount(
            value=value,
            count=counts[value],
            investigation_count=len(investigation_ids),
        )
        for value, investigation_ids in investigations_by_value.items()
        if len(investigation_ids) > 1
    ]
    return sorted(
        recurring,
        key=lambda item: (item.investigation_count, item.count, item.value),
        reverse=True,
    )[:limit]


def _recurring_evidence_counts(
    entities: list[ReconEntity],
) -> dict[uuid.UUID, int]:
    investigations_by_key: dict[tuple[str, str], set[uuid.UUID]] = defaultdict(set)
    for entity in entities:
        if entity.entity_type not in {"Domain", "Subdomain", "IPAddress", "Technology"}:
            continue
        investigations_by_key[(entity.entity_type, entity.value)].add(
            entity.investigation_id
        )
    counts: Counter[uuid.UUID] = Counter()
    for investigation_ids in investigations_by_key.values():
        if len(investigation_ids) > 1:
            counts.update(investigation_ids)
    return dict(counts)


def _sort_queue(
    items: list[InvestigationQueueItem],
    sort: QueueSort,
) -> list[InvestigationQueueItem]:
    if sort == "newest":
        return sorted(items, key=lambda item: item.created_at, reverse=True)
    if sort == "oldest":
        return sorted(items, key=lambda item: item.created_at)
    if sort == "overdue":
        return sorted(
            items,
            key=lambda item: (
                item.overdue,
                item.overdue_tasks,
                item.triage_score,
            ),
            reverse=True,
        )
    if sort == "most_findings":
        return sorted(
            items,
            key=lambda item: (item.findings_count, item.triage_score),
            reverse=True,
        )
    if sort == "least_activity":
        return sorted(items, key=lambda item: item.last_activity_at)
    return sorted(
        items,
        key=lambda item: (item.triage_score, item.risk_score, item.updated_at),
        reverse=True,
    )


def _matches_status(
    current: str,
    expected: QueueStatusFilter,
) -> bool:
    if expected == "completed":
        return current == "completed"
    return current == expected


def _finding_is_unresolved(finding: Finding) -> bool:
    return (
        finding.status in _OPEN_FINDING_STATUSES
        and finding.remediation_status not in _CLOSED_REMEDIATION_STATUSES
    )


def _triage_category(score: int) -> TriageCategory:
    if score >= 76:
        return "urgent_review"
    if score >= 51:
        return "active_review"
    if score >= 26:
        return "monitor"
    return "low_attention"


def _risk_level(score: int) -> RiskFilter:
    if score >= 76:
        return "critical"
    if score >= 51:
        return "high"
    if score >= 26:
        return "medium"
    return "low"


def _completion_percent(completed: int, total: int) -> int:
    return round((completed / total) * 100) if total else 0


def _trend(current: int, previous: int) -> Literal["up", "steady", "down"]:
    if current > previous:
        return "up"
    if current < previous:
        return "down"
    return "steady"


async def _highest_priority_finding(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> Finding | None:
    result = await db.execute(
        select(Finding)
        .where(
            Finding.investigation_id == investigation_id,
            Finding.status.in_(_OPEN_FINDING_STATUSES),
        )
        .order_by(
            Finding.risk_score.desc(),
            Finding.confidence_score.desc(),
            Finding.created_at.desc(),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _users_by_id(
    db: AsyncSession,
    user_ids: set[uuid.UUID],
) -> dict[uuid.UUID, User]:
    if not user_ids:
        return {}
    result = await db.execute(select(User).where(User.id.in_(user_ids)))
    return {user.id: user for user in result.scalars().all()}


def _group_by_investigation[T: _InvestigationScoped](
    items: list[T],
) -> dict[uuid.UUID, list[T]]:
    grouped: dict[uuid.UUID, list[T]] = defaultdict(list)
    for item in items:
        grouped[item.investigation_id].append(item)
    return dict(grouped)


def _group_by_optional_investigation(
    items: list[AuditLog],
) -> dict[uuid.UUID, list[AuditLog]]:
    grouped: dict[uuid.UUID, list[AuditLog]] = defaultdict(list)
    for item in items:
        if item.investigation_id is not None:
            grouped[item.investigation_id].append(item)
    return dict(grouped)


def _json_object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _now() -> datetime:
    return datetime.now(UTC)
