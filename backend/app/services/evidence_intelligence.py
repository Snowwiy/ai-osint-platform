from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding import Finding
from app.models.finding_evidence import FindingEvidence
from app.models.investigation import Investigation
from app.models.investigation_member import InvestigationMember
from app.models.investigation_task import InvestigationTask
from app.models.ioc import IOC, IOCObservation
from app.models.recon_entity import ReconEntity
from app.models.report import Report
from app.models.user import User
from app.schemas.evidence_intelligence import (
    EvidenceIntelligenceEvidenceResponse,
    EvidenceIntelligenceIOCResponse,
    EvidenceIntelligenceItem,
    EvidenceIntelligenceOverviewResponse,
    EvidenceIntelligencePriorityResponse,
    EvidenceIntelligenceTimelineEvent,
    EvidenceIntelligenceTimelineResponse,
    EvidenceIOCIntelligenceItem,
    IntelligenceConfidence,
    IntelligenceInvestigationReference,
    InvestigationPrioritySuggestion,
    PriorityRecommendationItem,
)

_ENTITY_GROUPS = {
    "Domain": "domain",
    "Subdomain": "domain",
    "IPAddress": "ip",
    "Technology": "technology",
}
_UNRESOLVED_FINDING_STATUSES = {"new", "under_review", "accepted_risk", "open"}
_RESOLVED_FINDING_STATUSES = {
    "validated",
    "mitigated",
    "resolved",
    "archived",
    "false_positive",
}
_REMEDIATED_FINDING_STATUSES = {"remediated", "mitigated", "resolved"}
_OPEN_TASK_STATUSES = {"todo", "in_progress", "blocked", "validation", "open"}
_SEVERITY_POINTS = {
    "critical": 30,
    "high": 22,
    "medium": 12,
    "low": 5,
    "info": 1,
}
type _TimelineEventType = Literal[
    "first_observed",
    "repeated_observation",
    "remediation_completed",
    "recurrence_after_remediation",
]


@dataclass(frozen=True)
class _Dataset:
    investigations: list[Investigation]
    entities: list[ReconEntity]
    findings: list[Finding]
    evidence: list[FindingEvidence]
    tasks: list[InvestigationTask]
    reports: list[Report]
    iocs: list[IOC]
    observations: list[IOCObservation]


@dataclass
class _GroupAccumulator:
    item_type: str
    value: str
    occurrence_count: int = 0
    sources: set[str] = field(default_factory=set)
    investigation_ids: set[uuid.UUID] = field(default_factory=set)
    resource_ids: dict[uuid.UUID, uuid.UUID] = field(default_factory=dict)
    related_findings: set[uuid.UUID] = field(default_factory=set)
    first_seen: datetime | None = None
    last_seen: datetime | None = None

    def add(
        self,
        *,
        investigation_id: uuid.UUID,
        source: str | None,
        resource_id: uuid.UUID | None,
        timestamp: datetime | None,
        finding_id: uuid.UUID | None = None,
    ) -> None:
        self.occurrence_count += 1
        self.investigation_ids.add(investigation_id)
        if resource_id is not None:
            self.resource_ids[investigation_id] = resource_id
        if source:
            self.sources.add(source)
        if finding_id is not None:
            self.related_findings.add(finding_id)
        if timestamp is not None:
            self.first_seen = timestamp if self.first_seen is None else min(
                self.first_seen,
                timestamp,
            )
            self.last_seen = (
                timestamp if self.last_seen is None else max(self.last_seen, timestamp)
            )


async def get_intelligence_overview(
    db: AsyncSession,
    user: User,
) -> EvidenceIntelligenceOverviewResponse:
    dataset = await _load_dataset(db, user)
    items = _build_items(dataset)
    recurring = [item for item in items if _is_recurring(item)]
    high_risk = [
        item
        for item in recurring
        if item.item_type in {"finding", "ip", "domain"}
        and item.confidence in {"High", "Very High"}
    ][:10]
    return EvidenceIntelligenceOverviewResponse(
        generated_at=_now(),
        total_items=len(items),
        recurring_domains=_items_of(recurring, "domain"),
        recurring_ips=_items_of(recurring, "ip"),
        recurring_technologies=_items_of(recurring, "technology"),
        recurring_findings=_items_of(recurring, "finding"),
        recurring_framework_mappings=_items_of(recurring, "framework"),
        recurring_evidence_chains=_items_of(recurring, "evidence_chain"),
        repeated_high_risk_items=high_risk,
    )


async def get_intelligence_evidence(
    db: AsyncSession,
    user: User,
) -> EvidenceIntelligenceEvidenceResponse:
    dataset = await _load_dataset(db, user)
    items = _build_items(dataset)
    return EvidenceIntelligenceEvidenceResponse(
        generated_at=_now(),
        total=len(items),
        items=items,
    )


async def get_intelligence_priority(
    db: AsyncSession,
    user: User,
) -> EvidenceIntelligencePriorityResponse:
    dataset = await _load_dataset(db, user)
    recurring_items = [item for item in _build_items(dataset) if _is_recurring(item)]
    recurrence_by_investigation: Counter[uuid.UUID] = Counter()
    for item in recurring_items:
        for reference in item.related_investigations:
            recurrence_by_investigation[reference.investigation_id] += 1
    ioc_count_by_investigation: Counter[uuid.UUID] = Counter(
        observation.investigation_id for observation in dataset.observations
    )
    findings_by_investigation = _group_by_investigation(dataset.findings)
    tasks_by_investigation = _group_by_investigation(dataset.tasks)
    items = [
        _priority_item(
            investigation,
            findings_by_investigation[investigation.id],
            tasks_by_investigation[investigation.id],
            recurrence_by_investigation[investigation.id],
            ioc_count_by_investigation[investigation.id],
        )
        for investigation in dataset.investigations
    ]
    items.sort(key=lambda item: item.score, reverse=True)
    return EvidenceIntelligencePriorityResponse(
        generated_at=_now(),
        total=len(items),
        items=items,
    )


async def get_intelligence_timeline(
    db: AsyncSession,
    user: User,
) -> EvidenceIntelligenceTimelineResponse:
    dataset = await _load_dataset(db, user)
    items = _build_items(dataset)
    investigation_titles = {item.id: item.title for item in dataset.investigations}
    events: list[EvidenceIntelligenceTimelineEvent] = []
    remediated_findings = {
        finding.id
        for finding in dataset.findings
        if finding.remediation_status in _REMEDIATED_FINDING_STATUSES
        or finding.status in _RESOLVED_FINDING_STATUSES
    }
    for item in items:
        primary_reference = (
            item.related_investigations[0]
            if item.related_investigations
            else None
        )
        if item.first_seen is not None:
            events.append(
                _timeline_event(
                    item,
                    timestamp=item.first_seen,
                    event_type="first_observed",
                    title=f"{item.item_type.title()} first observed",
                    summary=f"{item.value} was first observed in stored evidence.",
                    reference=primary_reference,
                    investigation_titles=investigation_titles,
                )
            )
        if _is_recurring(item) and item.last_seen is not None:
            events.append(
                _timeline_event(
                    item,
                    timestamp=item.last_seen,
                    event_type="repeated_observation",
                    title=f"{item.item_type.title()} repeated observation",
                    summary=(
                        f"{item.value} appears {item.occurrence_count} times across "
                        f"{item.investigation_count} accessible investigations."
                    ),
                    reference=primary_reference,
                    investigation_titles=investigation_titles,
                )
            )
        if remediated_findings.intersection(item.related_findings):
            timestamp = item.last_seen or item.first_seen or _now()
            events.append(
                _timeline_event(
                    item,
                    timestamp=timestamp,
                    event_type="remediation_completed",
                    title="Linked remediation completed",
                    summary=(
                        f"At least one finding linked to {item.value} has a "
                        "completed or resolved remediation state."
                    ),
                    reference=primary_reference,
                    investigation_titles=investigation_titles,
                )
            )
            if _is_recurring(item):
                events.append(
                    _timeline_event(
                        item,
                        timestamp=timestamp,
                        event_type="recurrence_after_remediation",
                        title="Recurring evidence after remediation linkage",
                        summary=(
                            f"{item.value} remains recurring across stored cases; "
                            "analyst review should verify remediation scope."
                        ),
                        reference=primary_reference,
                        investigation_titles=investigation_titles,
                    )
                )
    events.sort(key=lambda event: event.timestamp, reverse=True)
    return EvidenceIntelligenceTimelineResponse(
        generated_at=_now(),
        total=len(events),
        items=events[:250],
    )


async def get_intelligence_iocs(
    db: AsyncSession,
    user: User,
) -> EvidenceIntelligenceIOCResponse:
    dataset = await _load_dataset(db, user)
    investigation_by_id = {item.id: item for item in dataset.investigations}
    observations_by_ioc: defaultdict[uuid.UUID, list[IOCObservation]] = defaultdict(
        list
    )
    for observation in dataset.observations:
        observations_by_ioc[observation.ioc_id].append(observation)
    finding_ids_by_entity = _finding_ids_by_entity(dataset.evidence)
    reports_by_investigation = _reports_by_investigation(dataset.reports)
    items: list[EvidenceIOCIntelligenceItem] = []
    for ioc in dataset.iocs:
        observations = observations_by_ioc[ioc.id]
        references = [
            _investigation_reference(
                investigation_by_id[observation.investigation_id],
                resource_id=observation.recon_entity_id,
            )
            for observation in observations
            if observation.investigation_id in investigation_by_id
        ]
        seen_findings = {
            finding_id
            for observation in observations
            if observation.recon_entity_id is not None
            for finding_id in finding_ids_by_entity.get(
                observation.recon_entity_id,
                set(),
            )
        }
        seen_reports = {
            report.id
            for observation in observations
            for report in reports_by_investigation.get(observation.investigation_id, [])
        }
        if not references:
            continue
        items.append(
            EvidenceIOCIntelligenceItem(
                ioc_id=ioc.id,
                value=ioc.value,
                type=ioc.ioc_type,
                confidence=ioc.confidence,
                investigation_count=len({item.investigation_id for item in references}),
                frequency=sum(
                    observation.observation_count for observation in observations
                ),
                first_seen=min(observation.first_seen for observation in observations),
                last_seen=max(observation.last_seen for observation in observations),
                seen_in_investigations=references,
                seen_in_findings=sorted(seen_findings, key=str),
                seen_in_reports=sorted(seen_reports, key=str),
            )
        )
    items.sort(
        key=lambda item: (item.investigation_count, item.frequency, item.last_seen),
        reverse=True,
    )
    return EvidenceIntelligenceIOCResponse(
        generated_at=_now(),
        total=len(items),
        items=items[:250],
    )


async def build_investigation_evidence_intelligence_lines(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> list[str]:
    dataset = await _load_dataset(db, user)
    items = [
        item
        for item in _build_items(dataset)
        if any(
            reference.investigation_id == investigation_id
            for reference in item.related_investigations
        )
    ]
    recurring = [item for item in items if _is_recurring(item)]
    lines = [
        (
            f"{item.item_type}: {item.value} | {item.confidence} confidence | "
            f"{item.occurrence_count} observations across "
            f"{item.investigation_count} investigations"
        )
        for item in recurring[:12]
    ]
    return lines


async def _load_dataset(db: AsyncSession, user: User) -> _Dataset:
    investigations = await _accessible_investigations(db, user)
    investigation_ids = [item.id for item in investigations]
    if not investigation_ids:
        return _Dataset(
            investigations=[],
            entities=[],
            findings=[],
            evidence=[],
            tasks=[],
            reports=[],
            iocs=[],
            observations=[],
        )
    entities = list(
        (
            await db.execute(
                select(ReconEntity).where(ReconEntity.investigation_id.in_(investigation_ids))
            )
        )
        .scalars()
        .all()
    )
    findings = list(
        (
            await db.execute(
                select(Finding).where(Finding.investigation_id.in_(investigation_ids))
            )
        )
        .scalars()
        .all()
    )
    finding_ids = [item.id for item in findings]
    evidence = (
        list(
            (
                await db.execute(
                    select(FindingEvidence).where(
                        FindingEvidence.finding_id.in_(finding_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        if finding_ids
        else []
    )
    tasks = list(
        (
            await db.execute(
                select(InvestigationTask).where(
                    InvestigationTask.investigation_id.in_(investigation_ids)
                )
            )
        )
        .scalars()
        .all()
    )
    reports = list(
        (
            await db.execute(
                select(Report).where(Report.investigation_id.in_(investigation_ids))
            )
        )
        .scalars()
        .all()
    )
    observations = list(
        (
            await db.execute(
                select(IOCObservation).where(
                    IOCObservation.investigation_id.in_(investigation_ids)
                )
            )
        )
        .scalars()
        .all()
    )
    ioc_ids = {item.ioc_id for item in observations}
    iocs = (
        list(
            (
                await db.execute(select(IOC).where(IOC.id.in_(ioc_ids)))
            )
            .scalars()
            .all()
        )
        if ioc_ids
        else []
    )
    return _Dataset(
        investigations=investigations,
        entities=entities,
        findings=findings,
        evidence=evidence,
        tasks=tasks,
        reports=reports,
        iocs=iocs,
        observations=observations,
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
            .outerjoin(
                InvestigationMember,
                InvestigationMember.investigation_id == Investigation.id,
            )
            .where(
                or_(
                    Investigation.owner_id == user.id,
                    InvestigationMember.user_id == user.id,
                )
            )
        )
    investigations = list(result.scalars().unique().all())
    investigations.sort(key=lambda item: item.created_at, reverse=True)
    return investigations


def _build_items(dataset: _Dataset) -> list[EvidenceIntelligenceItem]:
    investigations = {item.id: item for item in dataset.investigations}
    reports_by_investigation = _reports_by_investigation(dataset.reports)
    groups: dict[tuple[str, str], _GroupAccumulator] = {}
    for entity in dataset.entities:
        item_type = _ENTITY_GROUPS.get(entity.entity_type)
        if item_type is None:
            continue
        value = _normalize_value(entity.value)
        if not value:
            continue
        _group(groups, item_type, value).add(
            investigation_id=entity.investigation_id,
            source=entity.source or "passive_recon",
            resource_id=entity.id,
            timestamp=entity.last_seen,
        )
    for finding in dataset.findings:
        finding_value = _normalize_value(finding.title)
        if finding_value:
            _group(groups, "finding", finding_value).add(
                investigation_id=finding.investigation_id,
                source=finding.source,
                resource_id=finding.id,
                timestamp=finding.created_at,
                finding_id=finding.id,
            )
        for framework in _framework_values(finding):
            _group(groups, "framework", framework).add(
                investigation_id=finding.investigation_id,
                source=finding.source,
                resource_id=finding.id,
                timestamp=finding.created_at,
                finding_id=finding.id,
            )
    findings_by_id = {item.id: item for item in dataset.findings}
    for evidence in dataset.evidence:
        evidence_finding = findings_by_id.get(evidence.finding_id)
        if evidence_finding is None:
            continue
        value = _normalize_value(
            f"{evidence.source}:{evidence.evidence_type}:{evidence.description[:160]}"
        )
        if not value:
            continue
        _group(groups, "evidence_chain", value).add(
            investigation_id=evidence_finding.investigation_id,
            source=evidence.source,
            resource_id=evidence.id,
            timestamp=evidence.created_at,
            finding_id=evidence_finding.id,
        )
    items = [
        _item_from_group(group, investigations, reports_by_investigation)
        for group in groups.values()
        if group.occurrence_count > 0
    ]
    items.sort(
        key=lambda item: (
            item.investigation_count,
            item.occurrence_count,
            _confidence_rank(item.confidence),
            item.last_seen or datetime.min.replace(tzinfo=UTC),
        ),
        reverse=True,
    )
    return items


def _item_from_group(
    group: _GroupAccumulator,
    investigations: dict[uuid.UUID, Investigation],
    reports_by_investigation: dict[uuid.UUID, list[Report]],
) -> EvidenceIntelligenceItem:
    confidence, reasons = _confidence(
        occurrence_count=group.occurrence_count,
        investigation_count=len(group.investigation_ids),
        source_count=len(group.sources),
        linked_findings=len(group.related_findings),
    )
    references = [
        _investigation_reference(
            investigations[investigation_id],
            resource_id=group.resource_ids.get(investigation_id),
        )
        for investigation_id in sorted(
            group.investigation_ids,
            key=lambda item: investigations[item].created_at,
            reverse=True,
        )
        if investigation_id in investigations
    ]
    report_ids = {
        report.id
        for investigation_id in group.investigation_ids
        for report in reports_by_investigation.get(investigation_id, [])
    }
    return EvidenceIntelligenceItem(
        id=f"{group.item_type}:{_stable_key(group.value)}",
        item_type=group.item_type,
        value=group.value,
        occurrence_count=group.occurrence_count,
        investigation_count=len(group.investigation_ids),
        source_count=len(group.sources),
        first_seen=group.first_seen,
        last_seen=group.last_seen,
        confidence=confidence,
        confidence_reasons=reasons,
        related_investigations=references,
        related_findings=sorted(group.related_findings, key=str),
        related_reports=sorted(report_ids, key=str),
    )


def _priority_item(
    investigation: Investigation,
    findings: Sequence[Finding],
    tasks: Sequence[InvestigationTask],
    recurrence_count: int,
    ioc_count: int,
) -> PriorityRecommendationItem:
    unresolved = [
        item for item in findings if item.status in _UNRESOLVED_FINDING_STATUSES
    ]
    remediation_backlog = [
        item for item in tasks if item.status in _OPEN_TASK_STATUSES
    ]
    correlation_count = recurrence_count
    severity_points = min(
        45,
        sum(_SEVERITY_POINTS.get(item.severity, 0) for item in unresolved),
    )
    backlog_points = min(20, len(remediation_backlog) * 4)
    recurrence_points = min(20, recurrence_count * 4)
    ioc_points = min(10, ioc_count * 2)
    correlation_points = min(5, correlation_count)
    score = min(
        100,
        severity_points
        + backlog_points
        + recurrence_points
        + ioc_points
        + correlation_points,
    )
    reasons = _priority_reasons(
        unresolved,
        remediation_backlog,
        recurrence_count,
        ioc_count,
        correlation_count,
    )
    return PriorityRecommendationItem(
        investigation_id=investigation.id,
        investigation_title=investigation.title,
        current_priority=investigation.priority,
        suggested_priority=_priority_category(score),
        score=score,
        reasons=reasons,
        metrics={
            "unresolved_findings": len(unresolved),
            "remediation_backlog": len(remediation_backlog),
            "evidence_recurrence": recurrence_count,
            "ioc_count": ioc_count,
            "correlation_count": correlation_count,
        },
    )


def _priority_reasons(
    unresolved: Sequence[Finding],
    remediation_backlog: Sequence[InvestigationTask],
    recurrence_count: int,
    ioc_count: int,
    correlation_count: int,
) -> list[str]:
    reasons: list[str] = []
    high_risk = [
        item for item in unresolved if item.severity in {"critical", "high"}
    ]
    if high_risk:
        reasons.append(
            f"{len(high_risk)} unresolved high or critical findings are present."
        )
    if remediation_backlog:
        reasons.append(f"{len(remediation_backlog)} remediation tasks remain open.")
    if recurrence_count:
        reasons.append(
            f"{recurrence_count} recurring evidence signals link this case to others."
        )
    if ioc_count:
        reasons.append(f"{ioc_count} normalized IOC observations are stored.")
    if correlation_count:
        reasons.append(f"{correlation_count} internal correlations are available.")
    if not reasons:
        reasons.append("No elevated recurring evidence or unresolved risk is stored.")
    return reasons


def _timeline_event(
    item: EvidenceIntelligenceItem,
    *,
    timestamp: datetime,
    event_type: str,
    title: str,
    summary: str,
    reference: IntelligenceInvestigationReference | None,
    investigation_titles: dict[uuid.UUID, str],
) -> EvidenceIntelligenceTimelineEvent:
    investigation_id = reference.investigation_id if reference else None
    return EvidenceIntelligenceTimelineEvent(
        id=f"{item.id}:{event_type}:{timestamp.isoformat()}",
        timestamp=timestamp,
        event_type=cast(_TimelineEventType, event_type),
        item_type=item.item_type,
        value=item.value,
        title=title,
        summary=summary,
        confidence=item.confidence,
        investigation_id=investigation_id,
        investigation_title=(
            investigation_titles.get(investigation_id) if investigation_id else None
        ),
    )


def _confidence(
    *,
    occurrence_count: int,
    investigation_count: int,
    source_count: int,
    linked_findings: int,
) -> tuple[IntelligenceConfidence, list[str]]:
    score = 0
    reasons = [
        f"{occurrence_count} stored observations",
        f"{investigation_count} accessible investigations",
        f"{source_count} distinct sources",
    ]
    if occurrence_count >= 5:
        score += 2
    elif occurrence_count >= 2:
        score += 1
    if investigation_count >= 3:
        score += 2
    elif investigation_count >= 2:
        score += 1
    if source_count >= 2:
        score += 1
    if linked_findings:
        score += 1
        reasons.append(f"{linked_findings} linked findings")
    confidence: IntelligenceConfidence
    if score >= 5:
        confidence = "Very High"
    elif score >= 3:
        confidence = "High"
    elif score >= 2:
        confidence = "Medium"
    else:
        confidence = "Low"
    return confidence, reasons


def _framework_values(finding: Finding) -> list[str]:
    values: set[str] = set()
    for payload in (finding.normalized_data, finding.raw_data):
        values.update(_extract_framework_strings(payload))
    return sorted(values, key=str.lower)


def _extract_framework_strings(value: object) -> set[str]:
    frameworks = {
        "mitre",
        "attack",
        "owasp",
        "nist",
        "cis",
        "iso",
        "sigma",
        "yara",
        "dfir",
    }
    results: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key).lower()
            if any(framework in key_text for framework in frameworks):
                if isinstance(item, str):
                    results.add(_normalize_value(f"{key}: {item}"))
                else:
                    results.add(_normalize_value(key))
            results.update(_extract_framework_strings(item))
    elif isinstance(value, list):
        for item in value:
            results.update(_extract_framework_strings(item))
    elif isinstance(value, str):
        text = value.lower()
        if any(framework in text for framework in frameworks):
            results.add(_normalize_value(value))
    return {item for item in results if item}


def _group(
    groups: dict[tuple[str, str], _GroupAccumulator],
    item_type: str,
    value: str,
) -> _GroupAccumulator:
    key = (item_type, value)
    if key not in groups:
        groups[key] = _GroupAccumulator(item_type=item_type, value=value)
    return groups[key]


def _investigation_reference(
    investigation: Investigation,
    *,
    resource_id: uuid.UUID | None = None,
) -> IntelligenceInvestigationReference:
    return IntelligenceInvestigationReference(
        investigation_id=investigation.id,
        investigation_title=investigation.title,
        status=investigation.status,
        priority=investigation.priority,
        resource_id=resource_id,
    )


def _items_of(
    items: Sequence[EvidenceIntelligenceItem],
    item_type: str,
) -> list[EvidenceIntelligenceItem]:
    return [item for item in items if item.item_type == item_type][:20]


def _is_recurring(item: EvidenceIntelligenceItem) -> bool:
    return item.occurrence_count >= 2 or item.investigation_count >= 2


def _priority_category(score: int) -> InvestigationPrioritySuggestion:
    if score >= 75:
        return "Critical"
    if score >= 50:
        return "High"
    if score >= 25:
        return "Medium"
    return "Low"


def _confidence_rank(confidence: IntelligenceConfidence) -> int:
    return {"Low": 1, "Medium": 2, "High": 3, "Very High": 4}[confidence]


def _normalize_value(value: str | None) -> str:
    return " ".join((value or "").strip().split()).lower()


def _stable_key(value: str) -> str:
    return value.replace(" ", "-").replace("/", "-").replace(":", "-")[:120]


def _group_by_investigation[GroupedItemT](
    items: Iterable[GroupedItemT],
) -> defaultdict[uuid.UUID, list[GroupedItemT]]:
    grouped: defaultdict[uuid.UUID, list[GroupedItemT]] = defaultdict(list)
    for item in items:
        investigation_id = getattr(item, "investigation_id", None)
        if isinstance(investigation_id, uuid.UUID):
            grouped[investigation_id].append(item)
    return grouped


def _reports_by_investigation(
    reports: Iterable[Report],
) -> dict[uuid.UUID, list[Report]]:
    grouped: defaultdict[uuid.UUID, list[Report]] = defaultdict(list)
    for report in reports:
        grouped[report.investigation_id].append(report)
    return dict(grouped)


def _finding_ids_by_entity(
    evidence: Iterable[FindingEvidence],
) -> dict[uuid.UUID, set[uuid.UUID]]:
    grouped: defaultdict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for item in evidence:
        if item.recon_entity_id is not None:
            grouped[item.recon_entity_id].add(item.finding_id)
    return dict(grouped)


def _now() -> datetime:
    return datetime.now(UTC)
