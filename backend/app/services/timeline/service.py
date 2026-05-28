from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_analysis import AiAnalysis
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.investigation_enrichment import InvestigationEnrichment
from app.models.recon_entity import ReconEntity
from app.models.recon_relationship import ReconRelationship
from app.models.report import Report
from app.models.target import Target
from app.models.threat_finding import ThreatFinding
from app.models.user import User
from app.schemas.finding import FindingSeverity
from app.schemas.timeline import TimelineEvent, TimelineEventType, TimelineResponse
from app.services.investigation import get_investigation


@dataclass(frozen=True)
class TimelineFilters:
    severity: FindingSeverity | None = None
    event_type: TimelineEventType | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    source: str | None = None


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
    return [_event_from_finding(finding) for finding in result.scalars().all()]


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
        summary=f"Analysis artifact stored for {target.target_type} {target.target_value}.",
        related_finding_ids=list(analysis.finding_ids),
        confidence=80 if analysis.risk_assessment != "none" else 55,
        metadata={
            "target_type": target.target_type,
            "target_value": target.target_value,
            "risk_assessment": analysis.risk_assessment,
        },
    )


def _event_from_report(report: Report) -> TimelineEvent:
    return TimelineEvent(
        id=f"report:{report.id}:generated",
        timestamp=report.created_at,
        event_type="report_generated",
        severity="info",
        source="report",
        title=report.title or "Investigation report generated",
        summary=f"{report.report_type.title()} report generated with status {report.status}.",
        confidence=90 if report.status == "ready" else 50,
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
