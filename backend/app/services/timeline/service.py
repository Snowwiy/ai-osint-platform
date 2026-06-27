from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_analysis import AiAnalysis
from app.models.audit_log import AuditLog
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.investigation_enrichment import InvestigationEnrichment
from app.models.investigation_evidence import InvestigationEvidence
from app.models.investigation_note import InvestigationNote
from app.models.investigation_task import InvestigationTask
from app.models.investigation_workflow_event import InvestigationWorkflowEvent
from app.models.recon_entity import ReconEntity
from app.models.recon_relationship import ReconRelationship
from app.models.report import Report
from app.models.target import Target
from app.models.threat_finding import ThreatFinding
from app.models.user import User
from app.schemas.finding import FindingSeverity
from app.schemas.recon import JsonProperties
from app.schemas.timeline import TimelineEvent, TimelineEventType, TimelineResponse
from app.services.investigation import get_investigation


@dataclass(frozen=True)
class TimelineFilters:
    severity: FindingSeverity | None = None
    event_type: TimelineEventType | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    source: str | None = None
    actor_id: uuid.UUID | None = None


async def get_investigation_timeline(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    *,
    filters: TimelineFilters | None = None,
) -> TimelineResponse:
    investigation = await get_investigation(db, user, investigation_id)
    events = await collect_timeline_events(db, investigation)
    filtered = filter_timeline_events(events, filters or TimelineFilters())
    return TimelineResponse(
        investigation_id=investigation_id,
        total=len(filtered),
        events=filtered,
    )


async def collect_timeline_events(
    db: AsyncSession,
    investigation: Investigation,
) -> list[TimelineEvent]:
    events: list[TimelineEvent] = [_event_from_investigation(investigation)]
    events.extend(await _recon_entity_events(db, investigation.id))
    events.extend(await _recon_relationship_events(db, investigation.id))
    events.extend(await _enrichment_events(db, investigation.id))
    events.extend(await _threat_finding_events(db, investigation.id))
    events.extend(await _finding_events(db, investigation.id))
    events.extend(await _ai_analysis_events(db, investigation.id))
    events.extend(await _report_events(db, investigation.id))
    events.extend(await _workflow_events(db, investigation.id))
    events.extend(await _note_events(db, investigation.id))
    events.extend(await _task_events(db, investigation.id))
    events.extend(await _case_evidence_events(db, investigation.id))
    events.extend(await _audit_collaboration_events(db, investigation.id))
    return sorted(events, key=lambda item: (item.timestamp, item.event_type, item.id))


def filter_timeline_events(
    events: list[TimelineEvent],
    filters: TimelineFilters,
) -> list[TimelineEvent]:
    filtered = events
    if filters.severity is not None:
        filtered = [event for event in filtered if event.severity == filters.severity]
    if filters.event_type is not None:
        filtered = [
            event for event in filtered if event.event_type == filters.event_type
        ]
    if filters.start_date is not None:
        filtered = [
            event for event in filtered if event.timestamp >= filters.start_date
        ]
    if filters.end_date is not None:
        filtered = [event for event in filtered if event.timestamp <= filters.end_date]
    if filters.source is not None:
        expected = filters.source.lower()
        filtered = [
            event for event in filtered if event.source.lower() == expected
        ]
    if filters.actor_id is not None:
        actor_id = str(filters.actor_id)
        filtered = [
            event
            for event in filtered
            if event.metadata.get("actor_id") == actor_id
            or event.metadata.get("author_id") == actor_id
            or event.metadata.get("created_by") == actor_id
        ]
    return filtered


async def _recon_entity_events(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[TimelineEvent]:
    result = await db.execute(
        select(ReconEntity)
        .where(ReconEntity.investigation_id == investigation_id)
        .order_by(ReconEntity.first_seen)
    )
    return [_event_from_recon_entity(entity) for entity in result.scalars().all()]


async def _recon_relationship_events(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[TimelineEvent]:
    result = await db.execute(
        select(ReconRelationship)
        .where(ReconRelationship.investigation_id == investigation_id)
        .order_by(ReconRelationship.created_at)
    )
    return [
        _event_from_recon_relationship(relationship)
        for relationship in result.scalars().all()
    ]


async def _enrichment_events(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[TimelineEvent]:
    result = await db.execute(
        select(InvestigationEnrichment)
        .where(InvestigationEnrichment.investigation_id == investigation_id)
        .order_by(InvestigationEnrichment.created_at)
    )
    return [
        _event_from_enrichment(enrichment)
        for enrichment in result.scalars().all()
    ]


async def _threat_finding_events(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[TimelineEvent]:
    result = await db.execute(
        select(ThreatFinding)
        .where(ThreatFinding.investigation_id == investigation_id)
        .order_by(ThreatFinding.collected_at)
    )
    return [
        _event_from_threat_finding(threat_finding)
        for threat_finding in result.scalars().all()
    ]


async def _finding_events(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[TimelineEvent]:
    result = await db.execute(
        select(Finding)
        .where(Finding.investigation_id == investigation_id)
        .order_by(Finding.created_at)
    )
    events: list[TimelineEvent] = []
    for finding in result.scalars().all():
        events.append(_event_from_finding(finding))
        if finding.status != "new" or finding.reviewed_by is not None:
            events.append(_event_from_finding_reviewed(finding))
        if finding.assigned_to is not None or finding.reviewed_by is not None:
            events.append(_event_from_finding_assignment(finding))
    return events


async def _ai_analysis_events(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[TimelineEvent]:
    result = await db.execute(
        select(AiAnalysis, Target)
        .join(Target, AiAnalysis.target_id == Target.id)
        .where(Target.investigation_id == investigation_id)
        .order_by(AiAnalysis.created_at)
    )
    return [
        _event_from_ai_analysis(analysis, target)
        for analysis, target in result.all()
    ]


async def _report_events(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[TimelineEvent]:
    result = await db.execute(
        select(Report)
        .where(Report.investigation_id == investigation_id)
        .order_by(Report.created_at)
    )
    events: list[TimelineEvent] = []
    for report in result.scalars().all():
        events.append(_event_from_report(report))
        citation_event = _event_from_report_citations(report)
        if citation_event is not None:
            events.append(citation_event)
    return events


async def _workflow_events(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[TimelineEvent]:
    result = await db.execute(
        select(InvestigationWorkflowEvent)
        .where(InvestigationWorkflowEvent.investigation_id == investigation_id)
        .order_by(InvestigationWorkflowEvent.created_at)
    )
    return [_event_from_workflow_event(item) for item in result.scalars().all()]


async def _note_events(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[TimelineEvent]:
    result = await db.execute(
        select(InvestigationNote)
        .where(InvestigationNote.investigation_id == investigation_id)
        .order_by(InvestigationNote.created_at)
    )
    return [_event_from_note(note) for note in result.scalars().all()]


async def _task_events(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[TimelineEvent]:
    result = await db.execute(
        select(InvestigationTask)
        .where(InvestigationTask.investigation_id == investigation_id)
        .order_by(InvestigationTask.created_at)
    )
    events: list[TimelineEvent] = []
    for task in result.scalars().all():
        events.append(_event_from_task(task))
        if task.completed_at is not None:
            events.append(_event_from_task_completed(task))
    return events


async def _case_evidence_events(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[TimelineEvent]:
    result = await db.execute(
        select(InvestigationEvidence)
        .where(InvestigationEvidence.investigation_id == investigation_id)
        .order_by(InvestigationEvidence.created_at)
    )
    events: list[TimelineEvent] = []
    for item in result.scalars().all():
        events.append(_event_from_case_evidence(item))
        if item.review_status in {"reviewed", "validated", "dismissed"}:
            events.append(_event_from_case_evidence_reviewed(item))
    return events


async def _audit_collaboration_events(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[TimelineEvent]:
    result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.investigation_id == investigation_id,
            AuditLog.action.in_(
                (
                    "investigation.member_added",
                    "investigation.member_removed",
                    "investigation.member_role_changed",
                    "investigation.owner_transferred",
                    "task.assigned",
                    "task.reassigned",
                    "finding.assigned",
                    "finding.review_assigned",
                    "playbook.started",
                    "playbook.step_updated",
                    "playbook.completed",
                    "playbook.cancelled",
                    "finding.remediation_updated",
                    "finding.verified",
                    "risk.accepted",
                    "note.updated",
                    "note.archived",
                    "bookmark.created",
                    "bookmark.deleted",
                    "summary.generated",
                    "investigation.priority_updated",
                    "investigation.tag_updated",
                    "investigation.bulk_update",
                    "investigation.pinned",
                    "report.failed",
                    "report.archived",
                    "report.restored",
                    "investigation.owner_changed",
                    "investigation.assigned",
                    "investigation.watcher_added",
                    "investigation.handoff",
                    "investigation.state_changed",
                    "investigation.stage_changed",
                    "investigation.escalated",
                    "task.status_updated",
                    "note.pinned",
                )
            ),
        )
        .order_by(AuditLog.created_at)
    )
    return [_event_from_audit_collaboration(item) for item in result.scalars().all()]


def _event_from_investigation(investigation: Investigation) -> TimelineEvent:
    return TimelineEvent(
        id=f"investigation:{investigation.id}:created",
        timestamp=investigation.created_at,
        event_type="investigation_created",
        severity="info",
        source="investigation",
        title="Investigation created",
        summary=f"Investigation '{investigation.title}' was created.",
        confidence=100,
        metadata={"status": investigation.status},
    )


def _event_from_recon_entity(entity: ReconEntity) -> TimelineEvent:
    severity = "low" if entity.entity_type in {"Service", "Technology"} else "info"
    return TimelineEvent(
        id=f"entity:{entity.id}:observed",
        timestamp=entity.first_seen,
        event_type="recon_entity_observed",
        severity=cast(FindingSeverity, severity),
        source=entity.source or "recon",
        title=f"{entity.entity_type} observed",
        summary=f"{entity.entity_type} '{entity.value}' was stored in the graph.",
        related_entity_ids=[entity.id],
        confidence=75,
        metadata={
            "entity_type": entity.entity_type,
            "value": entity.value,
        },
    )


def _event_from_recon_relationship(
    relationship: ReconRelationship,
) -> TimelineEvent:
    return TimelineEvent(
        id=f"relationship:{relationship.id}:observed",
        timestamp=relationship.created_at,
        event_type="recon_relationship_observed",
        severity="info",
        source=relationship.source or "recon",
        title=f"{relationship.relationship_type} relationship observed",
        summary="A passive recon relationship was stored between two entities.",
        related_entity_ids=[
            relationship.source_entity_id,
            relationship.target_entity_id,
        ],
        confidence=70,
        metadata={"relationship_type": relationship.relationship_type},
    )


def _event_from_enrichment(
    enrichment: InvestigationEnrichment,
) -> TimelineEvent:
    return TimelineEvent(
        id=f"enrichment:{enrichment.id}",
        timestamp=enrichment.created_at,
        event_type="enrichment_completed",
        severity=_severity_from_enrichment_status(enrichment.status),
        source="recon",
        title=f"Recon enrichment {enrichment.status}",
        summary=(
            f"{enrichment.target_type} enrichment for "
            f"'{enrichment.target_value}' finished with status {enrichment.status}."
        ),
        confidence=_confidence_from_status(enrichment.status),
        metadata={
            "target_type": enrichment.target_type,
            "target_value": enrichment.target_value,
            "status": enrichment.status,
        },
    )


def _event_from_threat_finding(
    threat_finding: ThreatFinding,
) -> TimelineEvent:
    return TimelineEvent(
        id=f"threat_finding:{threat_finding.id}",
        timestamp=threat_finding.collected_at,
        event_type="threat_finding_observed",
        severity=_severity_from_risk(threat_finding.risk_score),
        source=threat_finding.provider,
        title=f"{threat_finding.provider} verdict: {threat_finding.verdict}",
        summary=(
            f"{threat_finding.target_type} '{threat_finding.target_value}' "
            f"received risk score {threat_finding.risk_score}."
        ),
        related_entity_ids=[threat_finding.recon_entity_id],
        confidence=_confidence_from_label(threat_finding.confidence),
        metadata={
            "provider": threat_finding.provider,
            "status": threat_finding.status,
            "target_type": threat_finding.target_type,
            "target_value": threat_finding.target_value,
            "risk_score": threat_finding.risk_score,
        },
    )


def _event_from_finding(finding: Finding) -> TimelineEvent:
    return TimelineEvent(
        id=f"finding:{finding.id}:created",
        timestamp=finding.created_at,
        event_type="finding_created",
        severity=cast(FindingSeverity, finding.severity),
        source=finding.source,
        title=finding.title,
        summary=finding.description,
        related_finding_ids=[finding.id],
        confidence=finding.confidence_score,
        metadata={
            "status": finding.status,
            "risk_score": finding.risk_score,
        },
    )


def _event_from_finding_reviewed(finding: Finding) -> TimelineEvent:
    return TimelineEvent(
        id=f"finding:{finding.id}:reviewed",
        timestamp=finding.updated_at,
        event_type="finding_reviewed",
        severity=cast(FindingSeverity, finding.severity),
        source="case_management",
        title="Finding review updated",
        summary=f"{finding.title} is now {finding.status}.",
        related_finding_ids=[finding.id],
        confidence=finding.confidence_score,
        metadata={
            "status": finding.status,
            "reviewed_by": str(finding.reviewed_by) if finding.reviewed_by else None,
            "assigned_to": str(finding.assigned_to) if finding.assigned_to else None,
        },
    )


def _event_from_finding_assignment(finding: Finding) -> TimelineEvent:
    return TimelineEvent(
        id=f"finding:{finding.id}:assignment",
        timestamp=finding.updated_at,
        event_type="analyst_assignment",
        severity="info",
        source="case_management",
        title="Finding ownership assigned",
        summary=f"Assignment metadata changed for finding '{finding.title}'.",
        related_finding_ids=[finding.id],
        confidence=90,
        metadata={
            "assigned_to": str(finding.assigned_to) if finding.assigned_to else None,
            "reviewed_by": str(finding.reviewed_by) if finding.reviewed_by else None,
        },
    )


def _event_from_ai_analysis(
    analysis: AiAnalysis,
    target: Target,
) -> TimelineEvent:
    return TimelineEvent(
        id=f"ai_analysis:{analysis.id}",
        timestamp=analysis.created_at,
        event_type="ai_analysis_created",
        severity=_severity_from_ai_risk(analysis.risk_assessment),
        source="ai_analysis",
        title="Stored AI analysis artifact",
        summary=
        f"Analysis artifact stored for " 
        f"{target.target_type} "
        f"{target.target_value}.",
        related_finding_ids=list(analysis.finding_ids),
        confidence=80 if analysis.risk_assessment != "none" else 55,
        metadata={
            "target_type": target.target_type,
            "target_value": target.target_value,
            "risk_assessment": analysis.risk_assessment,
        },
    )


def _event_from_report(report: Report) -> TimelineEvent:
    event_type: TimelineEventType = "report_generated"
    title = report.title or "Investigation report generated"
    summary = (
        f"{report.report_type.title()} report generated with status "
        f"{report.status}."
    )
    timestamp = report.generated_at or report.created_at
    confidence = 90 if report.status == "ready" else 50
    if report.status == "failed":
        event_type = "report_failed"
        title = report.title or "Investigation report failed"
        summary = report.failure_reason or "Report generation failed."
        confidence = 95
    elif report.status == "archived":
        event_type = "report_archived"
        title = report.title or "Investigation report archived"
        summary = "Report was archived and remains available for restoration."
        timestamp = report.archived_at or report.created_at
        confidence = 95
    return TimelineEvent(
        id=f"report:{report.id}:{event_type}",
        timestamp=timestamp,
        event_type=event_type,
        severity="info",
        source="report",
        title=title,
        summary=summary,
        confidence=confidence,
        metadata={
            "report_type": report.report_type,
            "status": report.status,
            "format": report.report_format,
        },
    )


def _event_from_report_citations(report: Report) -> TimelineEvent | None:
    citation_ids = _knowledge_citation_ids(report)
    if not citation_ids:
        return None
    return TimelineEvent(
        id=f"report:{report.id}:knowledge-citations",
        timestamp=report.created_at,
        event_type="knowledge_citation_observed",
        severity="info",
        source="knowledge",
        title="Knowledge citations referenced",
        summary=f"{len(citation_ids)} defensive knowledge citations were referenced.",
        confidence=80,
        metadata={
            "report_id": str(report.id),
            "citation_ids": citation_ids[:20],
        },
    )


def _knowledge_citation_ids(report: Report) -> list[str]:
    markdown = report.markdown_content or ""
    ids = {
        item.strip("[]().,")
        for item in markdown.split()
        if item.strip("[]().,").startswith("knowledge:")
    }
    count = report.report_metadata.get("knowledge_citation_count")
    if not ids and isinstance(count, int) and count > 0:
        ids.add(f"knowledge:report:{report.id}")
    return sorted(ids)


def _event_from_workflow_event(event: InvestigationWorkflowEvent) -> TimelineEvent:
    from_status = event.from_status or "new"
    return TimelineEvent(
        id=f"workflow:{event.id}",
        timestamp=event.created_at,
        event_type="workflow_status_changed",
        severity="info",
        source="case_management",
        title="Workflow status changed",
        summary=f"Investigation moved from {from_status} to {event.to_status}.",
        confidence=95,
        metadata={
            "from_status": event.from_status,
            "to_status": event.to_status,
            "reason": event.reason,
            "actor_id": str(event.actor_id) if event.actor_id else None,
        },
    )


def _event_from_note(note: InvestigationNote) -> TimelineEvent:
    return TimelineEvent(
        id=f"note:{note.id}:added",
        timestamp=note.created_at,
        event_type="note_added",
        severity="info",
        source="case_management",
        title=f"{note.note_type.title()} note added",
        summary=note.title,
        confidence=90,
        metadata={
            "note_id": str(note.id),
            "note_type": note.note_type,
            "author_id": str(note.author_id) if note.author_id else None,
        },
    )


def _event_from_task(task: InvestigationTask) -> TimelineEvent:
    return TimelineEvent(
        id=f"task:{task.id}:created",
        timestamp=task.created_at,
        event_type="task_created",
        severity=_severity_from_task_priority(task.priority),
        source="case_management",
        title="Task created",
        summary=task.title,
        confidence=90,
        metadata={
            "task_id": str(task.id),
            "status": task.status,
            "priority": task.priority,
            "assigned_to": str(task.assigned_to) if task.assigned_to else None,
            "finding_id": str(task.finding_id) if task.finding_id else None,
            "remediation_link": task.remediation_link,
            "evidence_reference_ids": [
                str(item) for item in task.evidence_reference_ids
            ],
        },
    )


def _event_from_task_completed(task: InvestigationTask) -> TimelineEvent:
    return TimelineEvent(
        id=f"task:{task.id}:completed",
        timestamp=task.completed_at or task.created_at,
        event_type="task_completed",
        severity="info",
        source="case_management",
        title="Task completed",
        summary=task.title,
        confidence=95,
        metadata={
            "task_id": str(task.id),
            "priority": task.priority,
            "assigned_to": str(task.assigned_to) if task.assigned_to else None,
        },
    )


def _event_from_case_evidence(evidence: InvestigationEvidence) -> TimelineEvent:
    related_finding_ids = [evidence.finding_id] if evidence.finding_id else []
    return TimelineEvent(
        id=f"case_evidence:{evidence.id}:linked",
        timestamp=evidence.created_at,
        event_type="evidence_linked",
        severity="info",
        source=evidence.source,
        title=f"{evidence.evidence_type.title()} evidence linked",
        summary=evidence.title,
        related_finding_ids=related_finding_ids,
        confidence=evidence.confidence,
        metadata={
            "evidence_id": str(evidence.id),
            "evidence_type": evidence.evidence_type,
            "note_id": str(evidence.note_id) if evidence.note_id else None,
            "task_id": str(evidence.task_id) if evidence.task_id else None,
            "tags": evidence.tags,
            "review_status": evidence.review_status,
        },
    )


def _event_from_case_evidence_reviewed(
    evidence: InvestigationEvidence,
) -> TimelineEvent:
    related_finding_ids = [evidence.finding_id] if evidence.finding_id else []
    return TimelineEvent(
        id=f"case_evidence:{evidence.id}:reviewed",
        timestamp=evidence.reviewed_at or evidence.updated_at,
        event_type="evidence_validated",
        severity="info",
        source="case_management",
        title=f"Evidence {evidence.review_status}",
        summary=evidence.title,
        related_finding_ids=related_finding_ids,
        confidence=evidence.confidence_score,
        metadata={
            "evidence_id": str(evidence.id),
            "review_status": evidence.review_status,
            "reviewed_by": str(evidence.reviewed_by) if evidence.reviewed_by else None,
        },
    )


def _event_from_audit_collaboration(event: AuditLog) -> TimelineEvent:
    raw_metadata = (
        event.event_metadata if isinstance(event.event_metadata, dict) else {}
    )
    metadata = _timeline_metadata(raw_metadata)
    event_type = _collaboration_event_type(event.action)
    return TimelineEvent(
        id=f"audit:{event.id}:{event.action}",
        timestamp=event.created_at,
        event_type=event_type,
        severity="info",
        source=(
            "productivity"
            if event.action.startswith(("note.", "bookmark.", "summary."))
            or event.action
            in {"investigation.priority_updated", "investigation.tag_updated"}
            else "collaboration"
        ),
        title=_collaboration_title(event.action),
        summary=_collaboration_summary(event.action, metadata),
        confidence=95,
        metadata={
            "audit_id": event.id,
            "actor_id": str(event.actor_id) if event.actor_id else None,
            "resource_type": event.resource_type,
            "resource_id": str(event.resource_id) if event.resource_id else None,
            **metadata,
        },
    )


def _collaboration_event_type(action: str) -> TimelineEventType:
    mapping: dict[str, TimelineEventType] = {
        "investigation.member_added": "member_added",
        "investigation.member_removed": "member_removed",
        "investigation.member_role_changed": "member_role_changed",
        "investigation.owner_transferred": "ownership_transferred",
        "task.assigned": "task_assigned",
        "task.reassigned": "task_assigned",
        "finding.assigned": "finding_assigned",
        "finding.review_assigned": "finding_assigned",
        "playbook.started": "playbook_started",
        "playbook.step_updated": "playbook_step_updated",
        "playbook.completed": "playbook_completed",
        "playbook.cancelled": "playbook_cancelled",
        "finding.remediation_updated": "remediation_updated",
        "finding.verified": "finding_verified",
        "risk.accepted": "risk_accepted",
        "note.updated": "note_updated",
        "note.archived": "note_archived",
        "bookmark.created": "bookmark_created",
        "bookmark.deleted": "bookmark_deleted",
        "summary.generated": "summary_generated",
        "investigation.priority_updated": "priority_updated",
        "investigation.tag_updated": "tag_updated",
        "investigation.bulk_update": "investigation_bulk_updated",
        "investigation.pinned": "investigation_pinned",
        "report.failed": "report_failed",
        "report.archived": "report_archived",
        "report.restored": "report_restored",
        "investigation.owner_changed": "ownership_changed",
        "investigation.assigned": "analyst_assignment",
        "investigation.watcher_added": "watcher_added",
        "investigation.handoff": "investigation_handoff",
        "investigation.state_changed": "investigation_state_changed",
        "investigation.stage_changed": "investigation_stage_changed",
        "case.review_submitted": "case_review_submitted",
        "case.review_approved": "case_review_approved",
        "case.review_rejected": "case_review_rejected",
        "case.changes_requested": "case_changes_requested",
        "case.closed": "case_closed",
        "case.closure_overridden": "case_closure_overridden",
        "report.approval_submitted": "report_approval_submitted",
        "report.approved": "report_approved",
        "report.rejected": "report_rejected",
        "remediation.validation_submitted": "remediation_validation_submitted",
        "remediation.validated": "remediation_validated",
        "remediation.validation_failed": "remediation_validation_failed",
        "remediation.accepted_risk": "remediation_accepted_risk",
        "investigation.escalated": "investigation_escalated",
        "task.status_updated": "task_status_updated",
        "note.pinned": "note_pinned",
    }
    return mapping.get(action, "analyst_assignment")


def _collaboration_title(action: str) -> str:
    titles = {
        "playbook.started": "Defensive playbook started",
        "playbook.step_updated": "Playbook step updated",
        "playbook.completed": "Defensive playbook completed",
        "playbook.cancelled": "Defensive playbook cancelled",
        "finding.remediation_updated": "Finding remediation updated",
        "finding.verified": "Finding remediation verified",
        "risk.accepted": "Finding risk accepted",
        "note.updated": "Investigation note updated",
        "note.archived": "Investigation note archived",
        "bookmark.created": "Evidence bookmark created",
        "bookmark.deleted": "Evidence bookmark deleted",
        "summary.generated": "Investigation summary generated",
        "investigation.priority_updated": "Investigation priority updated",
        "investigation.tag_updated": "Investigation tags updated",
        "investigation.bulk_update": "Investigation bulk action applied",
        "investigation.pinned": "Investigation pin updated",
        "report.failed": "Report generation failed",
        "report.archived": "Report archived",
        "report.restored": "Report restored",
        "investigation.owner_changed": "Investigation owner changed",
        "investigation.assigned": "Analyst assigned",
        "investigation.watcher_added": "Watcher added",
        "investigation.handoff": "Investigation handed off",
        "investigation.state_changed": "Investigation state changed",
        "investigation.stage_changed": "Investigation stage changed",
        "case.review_submitted": "Case submitted for review",
        "case.review_approved": "Case review approved",
        "case.review_rejected": "Case review rejected",
        "case.changes_requested": "Case changes requested",
        "case.closed": "Case closed",
        "case.closure_overridden": "Case closure overridden",
        "report.approval_submitted": "Report submitted for approval",
        "report.approved": "Report approved",
        "report.rejected": "Report rejected",
        "remediation.validation_submitted": "Remediation submitted for validation",
        "remediation.validated": "Remediation validated",
        "remediation.validation_failed": "Remediation validation failed",
        "remediation.accepted_risk": "Remediation risk accepted",
        "investigation.escalated": "Investigation escalated",
        "task.status_updated": "Task status updated",
        "note.pinned": "Operational note pin updated",
    }
    return titles.get(action, action.replace(".", " ").replace("_", " ").title())


def _collaboration_summary(action: str, metadata: Mapping[str, object]) -> str:
    target = metadata.get("target_user") or metadata.get("assigned_to")
    if target is not None:
        return f"{_collaboration_title(action)} for {target}."
    return _collaboration_title(action)


def _timeline_metadata(metadata: dict[str, object]) -> JsonProperties:
    normalized: JsonProperties = {}
    for key, value in metadata.items():
        if value is None or isinstance(value, (str, int, float, bool)):
            normalized[key] = value
        elif isinstance(value, list):
            normalized[key] = [str(item) for item in value]
        elif isinstance(value, dict):
            normalized[key] = json.dumps(value, sort_keys=True, default=str)
        else:
            normalized[key] = str(value)
    return normalized


def _severity_from_risk(risk_score: int) -> FindingSeverity:
    if risk_score >= 90:
        return "critical"
    if risk_score >= 65:
        return "high"
    if risk_score >= 35:
        return "medium"
    if risk_score >= 10:
        return "low"
    return "info"


def _severity_from_ai_risk(value: str) -> FindingSeverity:
    if value in {"low", "medium", "high", "critical"}:
        return cast(FindingSeverity, value)
    return "info"


def _severity_from_enrichment_status(status: str) -> FindingSeverity:
    if status == "failed":
        return "medium"
    if status == "partial":
        return "low"
    return "info"


def _confidence_from_label(value: str) -> int:
    if value == "high":
        return 90
    if value == "medium":
        return 70
    return 50


def _confidence_from_status(value: str) -> int:
    if value == "completed":
        return 80
    if value == "partial":
        return 60
    return 40


def _severity_from_task_priority(priority: str) -> FindingSeverity:
    if priority == "critical":
        return "high"
    if priority == "high":
        return "medium"
    if priority == "medium":
        return "low"
    return "info"
