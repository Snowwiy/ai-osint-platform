from __future__ import annotations

import re
import uuid
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.investigation_member import InvestigationMember
from app.models.investigation_task import InvestigationTask
from app.models.ioc import IOC, IOCObservation
from app.models.recon_entity import ReconEntity
from app.models.report import Report
from app.models.threat_workspace import (
    ThreatCampaign,
    ThreatCampaignFinding,
    ThreatCampaignIndicator,
    ThreatCampaignInvestigation,
    ThreatCampaignTechnique,
    ThreatFindingTechnique,
    ThreatGroup,
    ThreatGroupCampaign,
    ThreatGroupIndicator,
    ThreatGroupTechnique,
    ThreatTechnique,
)
from app.models.user import User
from app.schemas.threat_workspace import (
    ThreatCampaignListResponse,
    ThreatCampaignSummary,
    ThreatGroupListResponse,
    ThreatGroupSummary,
    ThreatIndicatorListResponse,
    ThreatIndicatorSummary,
    ThreatInfrastructureResponse,
    ThreatInfrastructureSummary,
    ThreatInvestigationReference,
    ThreatOverviewResponse,
    ThreatTechniqueListResponse,
    ThreatTechniqueSummary,
    ThreatTimelineEvent,
    ThreatTimelineResponse,
    ThreatWorkspaceConfidence,
)

_ATTACK_PATTERN = re.compile(r"\bT\d{4}(?:\.\d{3})?\b", re.IGNORECASE)
_REMEDIATED_FINDING_STATUSES = {"remediated", "mitigated", "resolved"}
_ACTIVE_CAMPAIGN_STATUSES = {"active", "monitoring"}
_INFRASTRUCTURE_ENTITY_TYPES = {
    "Domain": "domain",
    "Subdomain": "domain",
    "IPAddress": "ip",
    "Technology": "technology",
    "Certificate": "certificate",
    "ASN": "hosting_reference",
    "Organization": "hosting_reference",
}


@dataclass(frozen=True)
class _ThreatDataset:
    investigations: list[Investigation]
    iocs: list[IOC]
    observations: list[IOCObservation]
    findings: list[Finding]
    tasks: list[InvestigationTask]
    reports: list[Report]
    entities: list[ReconEntity]
    campaigns: list[ThreatCampaign]
    groups: list[ThreatGroup]
    techniques: list[ThreatTechnique]
    campaign_indicators: list[ThreatCampaignIndicator]
    campaign_findings: list[ThreatCampaignFinding]
    campaign_investigations: list[ThreatCampaignInvestigation]
    campaign_techniques: list[ThreatCampaignTechnique]
    group_campaigns: list[ThreatGroupCampaign]
    group_indicators: list[ThreatGroupIndicator]
    group_techniques: list[ThreatGroupTechnique]
    finding_techniques: list[ThreatFindingTechnique]


async def get_threat_overview(
    db: AsyncSession,
    user: User,
) -> ThreatOverviewResponse:
    dataset = await _load_dataset(db, user)
    indicators = _indicator_summaries(dataset)
    techniques = _technique_summaries(dataset)
    infrastructure = _infrastructure_summaries(dataset)
    timeline = _timeline_events(dataset, indicators, techniques)
    return ThreatOverviewResponse(
        generated_at=_now(),
        indicator_count=len(indicators),
        active_campaigns=sum(
            campaign.status in _ACTIVE_CAMPAIGN_STATUSES
            for campaign in dataset.campaigns
        ),
        threat_group_count=len(dataset.groups),
        technique_count=len(techniques),
        recurring_infrastructure_count=sum(
            item.investigation_count >= 2 or item.occurrence_count >= 2
            for item in infrastructure
        ),
        high_confidence_observations=sum(
            item.confidence in {"High", "Confirmed"} for item in indicators
        ),
        attack_coverage=sum(item.coverage_count > 0 for item in techniques),
        recent_activity=timeline[:8],
    )


async def get_threat_indicators(
    db: AsyncSession,
    user: User,
) -> ThreatIndicatorListResponse:
    dataset = await _load_dataset(db, user)
    items = _indicator_summaries(dataset)
    return ThreatIndicatorListResponse(
        generated_at=_now(),
        total=len(items),
        items=items,
    )


async def get_threat_campaigns(
    db: AsyncSession,
    user: User,
) -> ThreatCampaignListResponse:
    dataset = await _load_dataset(db, user)
    items = _campaign_summaries(dataset)
    return ThreatCampaignListResponse(
        generated_at=_now(),
        total=len(items),
        items=items,
    )


async def get_threat_groups(
    db: AsyncSession,
    user: User,
) -> ThreatGroupListResponse:
    dataset = await _load_dataset(db, user)
    items = _group_summaries(dataset)
    return ThreatGroupListResponse(
        generated_at=_now(),
        total=len(items),
        items=items,
    )


async def get_threat_techniques(
    db: AsyncSession,
    user: User,
) -> ThreatTechniqueListResponse:
    dataset = await _load_dataset(db, user)
    items = _technique_summaries(dataset)
    return ThreatTechniqueListResponse(
        generated_at=_now(),
        total=len(items),
        items=items,
    )


async def get_threat_infrastructure(
    db: AsyncSession,
    user: User,
) -> ThreatInfrastructureResponse:
    dataset = await _load_dataset(db, user)
    items = _infrastructure_summaries(dataset)
    return ThreatInfrastructureResponse(
        generated_at=_now(),
        total=len(items),
        items=items,
    )


async def build_investigation_threat_intelligence_lines(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> list[str]:
    dataset = await _load_dataset(db, user)
    indicators = [
        item
        for item in _indicator_summaries(dataset)
        if any(ref.investigation_id == investigation_id for ref in item.investigations)
    ][:10]
    infrastructure = [
        item
        for item in _infrastructure_summaries(dataset)
        if any(ref.investigation_id == investigation_id for ref in item.investigations)
    ][:10]
    techniques = _technique_summaries(dataset)[:10]
    lines = [
        (
            f"Indicator {item.type} {item.value}: {item.confidence} confidence, "
            f"{item.occurrence_count} observations across "
            f"{item.investigation_count} investigations."
        )
        for item in indicators
    ]
    lines.extend(
        (
            f"Infrastructure {item.infrastructure_type} {item.value}: "
            f"{item.confidence} confidence across {item.investigation_count} "
            "investigations."
        )
        for item in infrastructure
    )
    lines.extend(
        (
            f"ATT&CK {item.technique_id} {item.name}: "
            f"{item.coverage_count} evidence-backed mappings."
        )
        for item in techniques
        if item.coverage_count
    )
    return lines[:25]


async def get_threat_timeline(
    db: AsyncSession,
    user: User,
) -> ThreatTimelineResponse:
    dataset = await _load_dataset(db, user)
    indicators = _indicator_summaries(dataset)
    techniques = _technique_summaries(dataset)
    items = _timeline_events(dataset, indicators, techniques)
    return ThreatTimelineResponse(generated_at=_now(), total=len(items), items=items)


async def _load_dataset(db: AsyncSession, user: User) -> _ThreatDataset:
    investigations = await _accessible_investigations(db, user)
    investigation_ids = [item.id for item in investigations]
    if not investigation_ids:
        return _empty_dataset()
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
        list((await db.execute(select(IOC).where(IOC.id.in_(ioc_ids)))).scalars().all())
        if ioc_ids
        else []
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
    entities = list(
        (
            await db.execute(
                select(ReconEntity).where(
                    ReconEntity.investigation_id.in_(investigation_ids)
                )
            )
        )
        .scalars()
        .all()
    )
    campaigns = list((await db.execute(select(ThreatCampaign))).scalars().all())
    groups = list((await db.execute(select(ThreatGroup))).scalars().all())
    techniques = list((await db.execute(select(ThreatTechnique))).scalars().all())
    campaign_ids = [item.id for item in campaigns]
    group_ids = [item.id for item in groups]
    technique_ids = [item.id for item in techniques]
    return _ThreatDataset(
        investigations=investigations,
        iocs=iocs,
        observations=observations,
        findings=findings,
        tasks=tasks,
        reports=reports,
        entities=entities,
        campaigns=campaigns,
        groups=groups,
        techniques=techniques,
        campaign_indicators=await _load_optional(
            db,
            ThreatCampaignIndicator,
            ThreatCampaignIndicator.campaign_id,
            campaign_ids,
        ),
        campaign_findings=await _load_optional(
            db,
            ThreatCampaignFinding,
            ThreatCampaignFinding.finding_id,
            finding_ids,
        ),
        campaign_investigations=await _load_optional(
            db,
            ThreatCampaignInvestigation,
            ThreatCampaignInvestigation.investigation_id,
            investigation_ids,
        ),
        campaign_techniques=await _load_optional(
            db,
            ThreatCampaignTechnique,
            ThreatCampaignTechnique.technique_id,
            technique_ids,
        ),
        group_campaigns=await _load_optional(
            db,
            ThreatGroupCampaign,
            ThreatGroupCampaign.group_id,
            group_ids,
        ),
        group_indicators=await _load_optional(
            db,
            ThreatGroupIndicator,
            ThreatGroupIndicator.group_id,
            group_ids,
        ),
        group_techniques=await _load_optional(
            db,
            ThreatGroupTechnique,
            ThreatGroupTechnique.technique_id,
            technique_ids,
        ),
        finding_techniques=await _load_optional(
            db,
            ThreatFindingTechnique,
            ThreatFindingTechnique.finding_id,
            finding_ids,
        ),
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
    return list(result.scalars().unique().all())


async def _load_optional[ModelT](
    db: AsyncSession,
    model: type[ModelT],
    column: Any,
    values: Sequence[uuid.UUID],
) -> list[ModelT]:
    if not values:
        return []
    result = await db.execute(select(model).where(column.in_(values)))
    return list(result.scalars().all())


def _indicator_summaries(dataset: _ThreatDataset) -> list[ThreatIndicatorSummary]:
    investigations_by_id = {item.id: item for item in dataset.investigations}
    observations_by_ioc: defaultdict[uuid.UUID, list[IOCObservation]] = defaultdict(
        list
    )
    for observation in dataset.observations:
        observations_by_ioc[observation.ioc_id].append(observation)
    findings_by_investigation = _group_by_investigation(dataset.findings)
    reports_by_investigation = _group_by_investigation(dataset.reports)
    items: list[ThreatIndicatorSummary] = []
    for ioc in dataset.iocs:
        observations = observations_by_ioc.get(ioc.id, [])
        if not observations:
            continue
        references = [
            _investigation_reference(
                investigations_by_id[observation.investigation_id],
                first_seen=observation.first_seen,
                last_seen=observation.last_seen,
            )
            for observation in observations
            if observation.investigation_id in investigations_by_id
        ]
        finding_count = len(
            {
                finding.id
                for observation in observations
                for finding in findings_by_investigation.get(
                    observation.investigation_id,
                    [],
                )
            }
        )
        report_count = len(
            {
                report.id
                for observation in observations
                for report in reports_by_investigation.get(
                    observation.investigation_id,
                    [],
                )
            }
        )
        occurrence_count = sum(item.observation_count for item in observations)
        confidence, reason = _confidence(
            evidence_count=occurrence_count,
            corroboration_count=finding_count,
            recurrence=len({item.investigation_id for item in observations}),
            analyst_validated=ioc.confidence == "high",
        )
        items.append(
            ThreatIndicatorSummary(
                id=ioc.id,
                value=ioc.value,
                type=ioc.ioc_type,
                source=ioc.source,
                confidence=confidence,
                confidence_reason=reason,
                first_seen=min(item.first_seen for item in observations),
                last_seen=max(item.last_seen for item in observations),
                occurrence_count=occurrence_count,
                investigation_count=len(
                    {item.investigation_id for item in observations}
                ),
                findings_count=finding_count,
                reports_count=report_count,
                investigations=references,
                tags=ioc.tags,
            )
        )
    return sorted(
        items,
        key=lambda item: (item.investigation_count, item.occurrence_count),
        reverse=True,
    )


def _campaign_summaries(dataset: _ThreatDataset) -> list[ThreatCampaignSummary]:
    indicators = Counter(item.campaign_id for item in dataset.campaign_indicators)
    findings = Counter(item.campaign_id for item in dataset.campaign_findings)
    investigations = Counter(
        item.campaign_id for item in dataset.campaign_investigations
    )
    techniques = Counter(item.campaign_id for item in dataset.campaign_techniques)
    return [
        ThreatCampaignSummary(
            id=campaign.id,
            name=campaign.name,
            description=campaign.description,
            status=campaign.status,
            confidence=_stored_confidence(campaign.confidence),
            first_observed=campaign.first_observed,
            last_observed=campaign.last_observed,
            indicator_count=indicators[campaign.id],
            finding_count=findings[campaign.id],
            investigation_count=investigations[campaign.id],
            technique_count=techniques[campaign.id],
        )
        for campaign in sorted(
            dataset.campaigns,
            key=lambda item: item.updated_at,
            reverse=True,
        )
    ]


def _group_summaries(dataset: _ThreatDataset) -> list[ThreatGroupSummary]:
    campaigns = Counter(item.group_id for item in dataset.group_campaigns)
    indicators = Counter(item.group_id for item in dataset.group_indicators)
    techniques = Counter(item.group_id for item in dataset.group_techniques)
    return [
        ThreatGroupSummary(
            id=group.id,
            name=group.name,
            aliases=group.aliases,
            description=group.description,
            confidence=_stored_confidence(group.confidence),
            notes=group.notes,
            campaign_count=campaigns[group.id],
            indicator_count=indicators[group.id],
            technique_count=techniques[group.id],
        )
        for group in sorted(
            dataset.groups,
            key=lambda item: item.updated_at,
            reverse=True,
        )
    ]


def _technique_summaries(dataset: _ThreatDataset) -> list[ThreatTechniqueSummary]:
    derived = _derived_attack_techniques(dataset.findings)
    stored_by_key = {item.technique_id.upper(): item for item in dataset.techniques}
    finding_mappings = Counter(item.technique_id for item in dataset.finding_techniques)
    campaign_mappings = Counter(
        item.technique_id for item in dataset.campaign_techniques
    )
    group_mappings = Counter(item.technique_id for item in dataset.group_techniques)
    items: list[ThreatTechniqueSummary] = []
    for key, count in derived.items():
        stored = stored_by_key.get(key.upper())
        mapped_findings = count + (finding_mappings[stored.id] if stored else 0)
        mapped_campaigns = campaign_mappings[stored.id] if stored else 0
        mapped_groups = group_mappings[stored.id] if stored else 0
        coverage_count = mapped_findings + mapped_campaigns + mapped_groups
        confidence, _reason = _confidence(
            evidence_count=coverage_count,
            corroboration_count=mapped_campaigns + mapped_groups,
            recurrence=count,
            analyst_validated=stored is not None,
        )
        items.append(
            ThreatTechniqueSummary(
                id=str(stored.id) if stored else f"derived:{key}",
                technique_id=stored.technique_id if stored else key,
                name=stored.name if stored else f"ATT&CK technique {key}",
                tactic=stored.tactic if stored else None,
                procedure=stored.procedure if stored else None,
                confidence=confidence,
                mapped_findings=mapped_findings,
                mapped_campaigns=mapped_campaigns,
                mapped_groups=mapped_groups,
                coverage_count=coverage_count,
                why_mapping_exists=(
                    "Mapped from analyst-created technique records and stored "
                    "finding metadata."
                    if stored
                    else "Derived from ATT&CK technique references in stored findings."
                ),
            )
        )
    for stored in dataset.techniques:
        if stored.technique_id.upper() in derived:
            continue
        mapped_findings = finding_mappings[stored.id]
        mapped_campaigns = campaign_mappings[stored.id]
        mapped_groups = group_mappings[stored.id]
        coverage_count = mapped_findings + mapped_campaigns + mapped_groups
        confidence, _reason = _confidence(
            evidence_count=coverage_count,
            corroboration_count=mapped_campaigns + mapped_groups,
            recurrence=coverage_count,
            analyst_validated=True,
        )
        items.append(
            ThreatTechniqueSummary(
                id=str(stored.id),
                technique_id=stored.technique_id,
                name=stored.name,
                tactic=stored.tactic,
                procedure=stored.procedure,
                confidence=confidence,
                mapped_findings=mapped_findings,
                mapped_campaigns=mapped_campaigns,
                mapped_groups=mapped_groups,
                coverage_count=coverage_count,
                why_mapping_exists="Analyst-created ATT&CK technique mapping.",
            )
        )
    return sorted(items, key=lambda item: item.coverage_count, reverse=True)


def _infrastructure_summaries(
    dataset: _ThreatDataset,
) -> list[ThreatInfrastructureSummary]:
    investigations_by_id = {item.id: item for item in dataset.investigations}
    grouped: dict[tuple[str, str], list[ReconEntity]] = defaultdict(list)
    for entity in dataset.entities:
        infrastructure_type = _INFRASTRUCTURE_ENTITY_TYPES.get(entity.entity_type)
        if infrastructure_type and entity.value:
            grouped[(infrastructure_type, entity.value.strip().lower())].append(entity)
    items: list[ThreatInfrastructureSummary] = []
    for (infrastructure_type, value), entities in grouped.items():
        investigation_ids = {item.investigation_id for item in entities}
        confidence, _reason = _confidence(
            evidence_count=len(entities),
            corroboration_count=len({item.source for item in entities if item.source}),
            recurrence=len(investigation_ids),
            analyst_validated=False,
        )
        items.append(
            ThreatInfrastructureSummary(
                id=f"{infrastructure_type}:{value}",
                infrastructure_type=infrastructure_type,
                value=value,
                confidence=confidence,
                first_seen=min((item.first_seen for item in entities), default=None),
                last_seen=max((item.last_seen for item in entities), default=None),
                occurrence_count=len(entities),
                investigation_count=len(investigation_ids),
                investigations=[
                    _investigation_reference(investigations_by_id[investigation_id])
                    for investigation_id in investigation_ids
                    if investigation_id in investigations_by_id
                ],
            )
        )
    return sorted(
        items,
        key=lambda item: (item.investigation_count, item.occurrence_count),
        reverse=True,
    )


def _timeline_events(
    dataset: _ThreatDataset,
    indicators: Sequence[ThreatIndicatorSummary],
    techniques: Sequence[ThreatTechniqueSummary],
) -> list[ThreatTimelineEvent]:
    events: list[ThreatTimelineEvent] = []
    for indicator in indicators:
        if indicator.first_seen:
            events.append(
                ThreatTimelineEvent(
                    id=f"indicator:{indicator.id}:first",
                    timestamp=indicator.first_seen,
                    event_type="indicator_observed",
                    title="Indicator observed",
                    summary=f"{indicator.type} {indicator.value} was first observed.",
                    confidence=indicator.confidence,
                    investigation_id=(
                        indicator.investigations[0].investigation_id
                        if indicator.investigations
                        else None
                    ),
                    investigation_title=(
                        indicator.investigations[0].investigation_title
                        if indicator.investigations
                        else None
                    ),
                )
            )
        if indicator.investigation_count >= 2:
            events.append(
                ThreatTimelineEvent(
                    id=f"indicator:{indicator.id}:repeat",
                    timestamp=indicator.last_seen,
                    event_type="indicator_repeated",
                    title="Indicator repeated",
                    summary=(
                        f"{indicator.value} is visible in "
                        f"{indicator.investigation_count} investigations."
                    ),
                    confidence=indicator.confidence,
                )
            )
    for campaign in dataset.campaigns:
        events.append(
            ThreatTimelineEvent(
                id=f"campaign:{campaign.id}:created",
                timestamp=campaign.created_at,
                event_type="campaign_created",
                title="Campaign created",
                summary=f"Analyst-created campaign: {campaign.name}.",
                confidence=_stored_confidence(campaign.confidence),
            )
        )
        events.append(
            ThreatTimelineEvent(
                id=f"campaign:{campaign.id}:updated",
                timestamp=campaign.updated_at,
                event_type="campaign_updated",
                title="Campaign updated",
                summary=f"Campaign {campaign.name} was updated.",
                confidence=_stored_confidence(campaign.confidence),
            )
        )
    for mapping in dataset.group_campaigns:
        events.append(
            ThreatTimelineEvent(
                id=f"group-link:{mapping.id}",
                timestamp=mapping.created_at,
                event_type="group_linked",
                title="Threat group linked",
                summary="Analyst linked a threat group to a campaign.",
                confidence="Low",
            )
        )
    for technique in techniques:
        if technique.coverage_count:
            events.append(
                ThreatTimelineEvent(
                    id=f"technique:{technique.id}",
                    timestamp=_now(),
                    event_type="technique_mapped",
                    title="ATT&CK technique mapped",
                    summary=(
                        f"{technique.technique_id} has "
                        f"{technique.coverage_count} evidence-backed mappings."
                    ),
                    confidence=technique.confidence,
                )
            )
    for finding in dataset.findings:
        if (
            finding.remediation_status in _REMEDIATED_FINDING_STATUSES
            or finding.status in _REMEDIATED_FINDING_STATUSES
        ):
            events.append(
                ThreatTimelineEvent(
                    id=f"remediation:{finding.id}",
                    timestamp=finding.updated_at,
                    event_type="remediation_completed",
                    title="Remediation completed",
                    summary=f"Finding remediation updated for {finding.title}.",
                    confidence=_finding_confidence(finding),
                    investigation_id=finding.investigation_id,
                    investigation_title=_investigation_title(
                        dataset.investigations,
                        finding.investigation_id,
                    ),
                )
            )
    events.sort(key=lambda item: item.timestamp, reverse=True)
    return events[:250]


def _derived_attack_techniques(findings: Iterable[Finding]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for finding in findings:
        payloads = [
            finding.title,
            finding.description,
            finding.normalized_data,
            finding.raw_data,
        ]
        for payload in payloads:
            for technique_id in _extract_attack_ids(payload):
                counter[technique_id.upper()] += 1
    return counter


def _extract_attack_ids(value: object) -> set[str]:
    if isinstance(value, dict):
        ids: set[str] = set()
        for item in value.values():
            ids.update(_extract_attack_ids(item))
        return ids
    if isinstance(value, list):
        list_ids: set[str] = set()
        for item in value:
            list_ids.update(_extract_attack_ids(item))
        return list_ids
    if isinstance(value, str):
        return {match.group(0).upper() for match in _ATTACK_PATTERN.finditer(value)}
    return set()


def _confidence(
    *,
    evidence_count: int,
    corroboration_count: int,
    recurrence: int,
    analyst_validated: bool,
) -> tuple[ThreatWorkspaceConfidence, str]:
    score = 0
    if evidence_count >= 5:
        score += 2
    elif evidence_count >= 2:
        score += 1
    if corroboration_count >= 2:
        score += 1
    if recurrence >= 3:
        score += 2
    elif recurrence >= 2:
        score += 1
    if analyst_validated:
        score += 2
    confidence: ThreatWorkspaceConfidence
    if analyst_validated and score >= 5:
        confidence = "Confirmed"
    elif score >= 4:
        confidence = "High"
    elif score >= 2:
        confidence = "Medium"
    else:
        confidence = "Low"
    reason = (
        "Confidence is based on stored evidence count, corroboration, recurrence, "
        "and analyst validation. It does not assert attribution or compromise."
    )
    return confidence, reason


def _stored_confidence(value: str) -> ThreatWorkspaceConfidence:
    if value in {"Low", "Medium", "High", "Confirmed"}:
        return cast(ThreatWorkspaceConfidence, value)
    return "Low"


def _finding_confidence(finding: Finding) -> ThreatWorkspaceConfidence:
    if finding.confidence == "high" or finding.confidence_score >= 80:
        return "High"
    if finding.confidence == "medium" or finding.confidence_score >= 45:
        return "Medium"
    return "Low"


def _investigation_reference(
    investigation: Investigation,
    *,
    first_seen: datetime | None = None,
    last_seen: datetime | None = None,
) -> ThreatInvestigationReference:
    return ThreatInvestigationReference(
        investigation_id=investigation.id,
        investigation_title=investigation.title,
        status=investigation.status,
        priority=investigation.priority,
        first_seen=first_seen,
        last_seen=last_seen,
    )


def _group_by_investigation[InvestigationScopedT](
    items: Iterable[InvestigationScopedT],
) -> defaultdict[uuid.UUID, list[InvestigationScopedT]]:
    grouped: defaultdict[uuid.UUID, list[InvestigationScopedT]] = defaultdict(list)
    for item in items:
        investigation_id = getattr(item, "investigation_id", None)
        if isinstance(investigation_id, uuid.UUID):
            grouped[investigation_id].append(item)
    return grouped


def _investigation_title(
    investigations: Iterable[Investigation],
    investigation_id: uuid.UUID,
) -> str | None:
    for investigation in investigations:
        if investigation.id == investigation_id:
            return investigation.title
    return None


def _empty_dataset() -> _ThreatDataset:
    return _ThreatDataset(
        investigations=[],
        iocs=[],
        observations=[],
        findings=[],
        tasks=[],
        reports=[],
        entities=[],
        campaigns=[],
        groups=[],
        techniques=[],
        campaign_indicators=[],
        campaign_findings=[],
        campaign_investigations=[],
        campaign_techniques=[],
        group_campaigns=[],
        group_indicators=[],
        group_techniques=[],
        finding_techniques=[],
    )


def _now() -> datetime:
    return datetime.now(UTC)
