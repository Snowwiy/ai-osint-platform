from __future__ import annotations

import ipaddress
import uuid
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding import Finding
from app.models.finding_evidence import FindingEvidence
from app.models.investigation import Investigation
from app.models.investigation_member import InvestigationMember
from app.models.ioc import IOC, IOCObservation
from app.models.playbook import PlaybookRun
from app.models.recon_entity import ReconEntity
from app.models.report import Report
from app.models.user import User
from app.schemas.finding import FindingSeverity
from app.schemas.ioc import (
    IOCConfidence,
    IOCCorrelation,
    IOCCorrelationCategory,
    IOCCorrelationResponse,
    IOCDetail,
    IOCEvidenceRelationship,
    IOCFindingReference,
    IOCGuidanceCard,
    IOCGuidanceResponse,
    IOCInvestigationReference,
    IOCListResponse,
    IOCPriorityCategory,
    IOCPriorityItem,
    IOCSummary,
    IOCType,
    InvestigationPrioritizationResponse,
)
from app.services.investigation import (
    InvestigationNotFoundError,
    get_investigation,
)

_ENTITY_TYPE_TO_IOC: dict[str, IOCType] = {
    "Domain": "domain",
    "Subdomain": "subdomain",
    "IPAddress": "ip",
    "ASN": "asn",
    "Certificate": "certificate",
    "Technology": "technology",
}
_UNRESOLVED_FINDING_STATUSES = {"new", "under_review", "accepted_risk", "open"}
_RESOLVED_REMEDIATION = {"remediated", "accepted_risk", "false_positive"}
_SEVERITY_WEIGHT = {
    "critical": 25,
    "high": 20,
    "medium": 12,
    "low": 6,
    "info": 2,
}
_SEVERITY_ORDER = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "info": 1,
}

_IOC_GUIDANCE: tuple[IOCGuidanceCard, ...] = (
    IOCGuidanceCard(
        id="ioc-guidance:exposed-rdp",
        title="Exposed RDP defensive review",
        applies_to=["RDP", "3389", "remote desktop", "management service"],
        monitoring_guidance=[
            "Monitor remote interactive logons and authentication failures.",
            "Alert on repeated failures followed by a successful remote logon.",
        ],
        logging_recommendations=[
            "Collect Windows Security events 4624, 4625, and 4740.",
            "Collect RemoteDesktopServices event 1149 where available.",
        ],
        mitre_relevance=[
            "T1133 External Remote Services",
            "T1110 Brute Force",
        ],
        sigma_references=[
            "Sigma authentication failure and remote service logon references."
        ],
        remediation_guidance=[
            "Restrict management access through approved network controls.",
            "Require strong authentication and documented service ownership.",
        ],
        why_this_matters=(
            "Externally visible management services increase authentication and "
            "monitoring requirements even when no malicious activity is observed."
        ),
    ),
    IOCGuidanceCard(
        id="ioc-guidance:dns-email",
        title="DNS and email security posture",
        applies_to=["DNS", "SPF", "DMARC", "MX", "nameserver"],
        monitoring_guidance=[
            "Track authoritative DNS and email-security record changes.",
            "Review unexpected resolver, nameserver, and mail-routing changes.",
        ],
        logging_recommendations=[
            "Retain DNS change records and resolver telemetry for authorized domains."
        ],
        mitre_relevance=["T1071.004 DNS monitoring context when anomalies exist"],
        sigma_references=["Sigma DNS anomaly monitoring reference."],
        remediation_guidance=[
            "Validate SPF alignment and publish an appropriate DMARC policy.",
            "Document authoritative DNS ownership and approved change paths.",
        ],
        why_this_matters=(
            "DNS configuration influences identity, email trust, and external service "
            "visibility across the authorized scope."
        ),
    ),
    IOCGuidanceCard(
        id="ioc-guidance:cloud-proxy",
        title="Cloud and reverse-proxy visibility",
        applies_to=["Cloudflare", "CDN", "reverse proxy", "cloud"],
        monitoring_guidance=[
            "Distinguish provider edge addresses from origin infrastructure.",
            "Monitor DNS and certificate changes that alter the delivery path.",
        ],
        logging_recommendations=[
            "Retain provider access, WAF, DNS, and origin authentication logs."
        ],
        mitre_relevance=[],
        sigma_references=[],
        remediation_guidance=[
            "Restrict origin access to approved provider paths where appropriate.",
            "Document shared-responsibility ownership for telemetry and response.",
        ],
        why_this_matters=(
            "A proxy or CDN changes what passive evidence represents and can obscure "
            "the underlying service boundary without implying compromise."
        ),
    ),
    IOCGuidanceCard(
        id="ioc-guidance:management-interface",
        title="Open management interface review",
        applies_to=["admin", "management", "console", "dashboard", "login"],
        monitoring_guidance=[
            "Monitor administrative authentication, role changes, and access anomalies.",
            "Establish an approved baseline for management interface exposure.",
        ],
        logging_recommendations=[
            "Collect authentication, authorization, and administrative action logs."
        ],
        mitre_relevance=["T1133 External Remote Services where applicable"],
        sigma_references=["Sigma administrative authentication monitoring references."],
        remediation_guidance=[
            "Limit access to authorized administrative networks and identities.",
            "Require MFA and review dormant privileged accounts.",
        ],
        why_this_matters=(
            "Management interfaces require stronger access controls and audit coverage "
            "than ordinary public application paths."
        ),
    ),
)


async def sync_recon_entity_ioc(
    db: AsyncSession,
    entity: ReconEntity,
) -> None:
    ioc_type = ioc_type_for_entity(entity)
    if ioc_type is None:
        return
    normalized = normalize_ioc_value(ioc_type, entity.value)
    if not normalized:
        return
    result = await db.execute(
        select(IOC).where(
            IOC.ioc_type == ioc_type,
            IOC.normalized_value == normalized,
        )
    )
    ioc = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if ioc is None:
        ioc = IOC(
            value=entity.value,
            normalized_value=normalized,
            ioc_type=ioc_type,
            source=entity.source or "passive_recon",
            first_seen=entity.first_seen,
            last_seen=entity.last_seen,
            tags=_ioc_tags(entity),
        )
        db.add(ioc)
        await db.flush()
    else:
        ioc.last_seen = max(ioc.last_seen, entity.last_seen, now)
        ioc.tags = list(dict.fromkeys([*ioc.tags, *_ioc_tags(entity)]))
        db.add(ioc)

    observation_result = await db.execute(
        select(IOCObservation).where(
            IOCObservation.ioc_id == ioc.id,
            IOCObservation.investigation_id == entity.investigation_id,
        )
    )
    observation = observation_result.scalar_one_or_none()
    if observation is None:
        observation = IOCObservation(
            ioc_id=ioc.id,
            investigation_id=entity.investigation_id,
            recon_entity_id=entity.id,
            source=entity.source or "passive_recon",
            evidence_quality=_entity_evidence_quality(entity),
            first_seen=entity.first_seen,
            last_seen=entity.last_seen,
            observation_metadata={
                "entity_type": entity.entity_type,
                "display_name": entity.display_name,
            },
        )
        db.add(observation)
    else:
        observation.recon_entity_id = entity.id
        observation.observation_count += 1
        observation.last_seen = max(observation.last_seen, entity.last_seen, now)
        observation.evidence_quality = max(
            observation.evidence_quality,
            _entity_evidence_quality(entity),
        )
        db.add(observation)
    await db.flush()
    await _refresh_persisted_confidence(db, ioc)


async def list_iocs(
    db: AsyncSession,
    user: User,
    *,
    ioc_type: IOCType | None = None,
    confidence: IOCConfidence | None = None,
    query: str | None = None,
    recurring_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> IOCListResponse:
    dataset = await _load_accessible_dataset(db, user)
    summaries = _build_summaries(dataset)
    if ioc_type is not None:
        summaries = [item for item in summaries if item.type == ioc_type]
    if confidence is not None:
        summaries = [item for item in summaries if item.confidence == confidence]
    if query and query.strip():
        needle = query.strip().lower()
        summaries = [
            item
            for item in summaries
            if needle in item.value.lower()
            or any(needle in tag.lower() for tag in item.tags)
        ]
    if recurring_only:
        summaries = [item for item in summaries if item.investigation_count >= 2]
    summaries.sort(
        key=lambda item: (
            -item.investigation_count,
            -item.confidence_score,
            -item.related_findings,
            item.value.lower(),
        )
    )
    return IOCListResponse(
        total=len(summaries),
        limit=limit,
        offset=offset,
        items=summaries[offset : offset + limit],
    )


async def get_ioc_detail(
    db: AsyncSession,
    user: User,
    ioc_id: uuid.UUID,
) -> IOCDetail:
    dataset = await _load_accessible_dataset(db, user, ioc_id=ioc_id)
    summary = _build_summaries(dataset)
    if not summary:
        raise InvestigationNotFoundError("IOC not found")
    ioc = dataset.iocs[0]
    observations = dataset.observations_by_ioc.get(ioc.id, [])
    findings = dataset.findings_by_ioc.get(ioc.id, [])
    return IOCDetail(
        **summary[0].model_dump(),
        investigations=_investigation_references(dataset, ioc.id),
        findings=[_finding_reference(item) for item in findings],
        evidence_relationships=_evidence_relationships(
            dataset,
            ioc,
            observations,
            findings,
        ),
        defensive_guidance=_guidance_for_ioc(ioc),
    )


async def list_investigation_iocs(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    *,
    limit: int = 100,
    offset: int = 0,
) -> IOCListResponse:
    await get_investigation(db, user, investigation_id)
    dataset = await _load_accessible_dataset(
        db,
        user,
        investigation_id=investigation_id,
    )
    summaries = _build_summaries(dataset)
    summaries.sort(
        key=lambda item: (
            -item.confidence_score,
            -item.related_findings,
            item.value.lower(),
        )
    )
    return IOCListResponse(
        total=len(summaries),
        limit=limit,
        offset=offset,
        items=summaries[offset : offset + limit],
    )


async def get_ioc_correlations(
    db: AsyncSession,
    user: User,
    *,
    limit: int = 100,
) -> IOCCorrelationResponse:
    dataset = await _load_accessible_dataset(db, user)
    summaries = {item.id: item for item in _build_summaries(dataset)}
    items: list[IOCCorrelation] = []
    for ioc in dataset.iocs:
        summary = summaries.get(ioc.id)
        if summary is None or summary.investigation_count < 2:
            continue
        findings = dataset.findings_by_ioc.get(ioc.id, [])
        items.append(
            IOCCorrelation(
                ioc=summary,
                category=_correlation_category(ioc, findings),
                investigations=_investigation_references(dataset, ioc.id),
                related_findings=[
                    _finding_reference(item)
                    for item in sorted(
                        findings,
                        key=lambda finding: (
                            -_SEVERITY_ORDER.get(finding.severity, 0),
                            finding.title.lower(),
                        ),
                    )
                ],
                severity_distribution=_severity_distribution(findings),
            )
        )
    items.sort(
        key=lambda item: (
            -item.ioc.investigation_count,
            -item.ioc.confidence_score,
            item.ioc.value.lower(),
        )
    )
    return IOCCorrelationResponse(
        generated_at=datetime.now(UTC),
        total=len(items),
        items=items[:limit],
    )


async def get_investigation_prioritization(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> InvestigationPrioritizationResponse:
    investigation = await get_investigation(db, user, investigation_id)
    dataset = await _load_accessible_dataset(
        db,
        user,
        investigation_id=investigation_id,
    )
    summaries = _build_summaries(dataset)
    findings = [
        finding
        for values in dataset.findings_by_ioc.values()
        for finding in values
        if finding.investigation_id == investigation_id
    ]
    findings = list({item.id: item for item in findings}.values())
    severity_points = max(
        (_SEVERITY_WEIGHT.get(item.severity, 0) for item in findings),
        default=0,
    )
    unresolved = [
        item for item in findings if item.status in _UNRESOLVED_FINDING_STATUSES
    ]
    unresolved_points = min(20, len(unresolved) * 4)
    recurrence_points = min(
        20,
        sum(max(0, item.investigation_count - 1) * 5 for item in summaries),
    )
    missing_remediation = sum(
        item.remediation_status not in _RESOLVED_REMEDIATION
        for item in unresolved
    )
    remediation_points = min(15, missing_remediation * 3)
    confidence_points = min(
        10,
        round(
            sum(item.confidence_score for item in summaries)
            / max(1, len(summaries))
            / 10
        ),
    )
    priority_points = {
        "low": 1,
        "medium": 4,
        "high": 7,
        "urgent": 10,
    }.get(investigation.priority, 4)
    contributors = {
        "severity": severity_points,
        "unresolved_findings": unresolved_points,
        "recurrence": recurrence_points,
        "missing_remediation": remediation_points,
        "ioc_confidence": confidence_points,
        "investigation_priority": priority_points,
    }
    score = min(100, sum(contributors.values()))
    prioritized_iocs = [
        _prioritize_ioc(
            summary,
            dataset.findings_by_ioc.get(summary.id, []),
            investigation_id,
            score,
        )
        for summary in summaries
    ]
    prioritized_iocs.sort(
        key=lambda item: (-item.score, item.ioc.value.lower())
    )
    category = _priority_category(score)
    return InvestigationPrioritizationResponse(
        investigation_id=investigation_id,
        generated_at=datetime.now(UTC),
        score=score,
        category=category,
        explanation=(
            f"{category} is based only on stored severity, recurrence, unresolved "
            "findings, remediation state, IOC confidence, and case priority."
        ),
        contributors=contributors,
        prioritized_iocs=prioritized_iocs,
    )


def list_ioc_guidance(query: str | None = None) -> IOCGuidanceResponse:
    items = list(_IOC_GUIDANCE)
    if query and query.strip():
        tokens = query.lower().split()
        items = [
            item
            for item in items
            if all(
                token
                in " ".join(
                    [
                        item.title,
                        item.why_this_matters,
                        *item.applies_to,
                        *item.monitoring_guidance,
                        *item.remediation_guidance,
                    ]
                ).lower()
                for token in tokens
            )
        ]
    return IOCGuidanceResponse(total=len(items), items=items)


def ioc_type_for_entity(entity: ReconEntity) -> IOCType | None:
    if entity.entity_type == "Service":
        return "url" if entity.value.lower().startswith(("http://", "https://")) else "hostname"
    return _ENTITY_TYPE_TO_IOC.get(entity.entity_type)


def normalize_ioc_value(ioc_type: IOCType, value: str) -> str:
    clean = value.strip()
    if not clean:
        return ""
    if ioc_type == "ip":
        try:
            return str(ipaddress.ip_address(clean))
        except ValueError:
            return clean.lower()
    if ioc_type in {"domain", "subdomain", "hostname"}:
        return clean.lower().rstrip(".")
    if ioc_type == "url":
        parsed = urlsplit(clean)
        if not parsed.scheme or not parsed.netloc:
            return clean.lower()
        hostname = (parsed.hostname or "").lower()
        port = parsed.port
        if port and not (
            (parsed.scheme.lower() == "http" and port == 80)
            or (parsed.scheme.lower() == "https" and port == 443)
        ):
            hostname = f"{hostname}:{port}"
        return urlunsplit(
            (
                parsed.scheme.lower(),
                hostname,
                parsed.path,
                parsed.query,
                "",
            )
        )
    if ioc_type == "asn":
        return clean.upper().replace(" ", "")
    return clean.lower()


class _IOCDataset:
    def __init__(
        self,
        *,
        iocs: list[IOC],
        observations: list[IOCObservation],
        investigations: list[Investigation],
        entities: list[ReconEntity],
        findings: list[Finding],
        evidence: list[FindingEvidence],
        reports: list[Report],
        playbook_runs: list[PlaybookRun],
    ) -> None:
        self.iocs = iocs
        self.observations = observations
        self.investigations = {item.id: item for item in investigations}
        self.entities = {item.id: item for item in entities}
        self.findings = findings
        self.evidence = evidence
        self.reports = reports
        self.playbook_runs = playbook_runs
        self.observations_by_ioc: defaultdict[
            uuid.UUID, list[IOCObservation]
        ] = defaultdict(list)
        self.findings_by_ioc: defaultdict[uuid.UUID, list[Finding]] = defaultdict(
            list
        )
        entity_to_ioc: dict[uuid.UUID, uuid.UUID] = {}
        for observation in observations:
            self.observations_by_ioc[observation.ioc_id].append(observation)
            if observation.recon_entity_id is not None:
                entity_to_ioc[observation.recon_entity_id] = observation.ioc_id
        findings_by_id = {item.id: item for item in findings}
        for item in evidence:
            if item.recon_entity_id is None:
                continue
            ioc_id = entity_to_ioc.get(item.recon_entity_id)
            finding = findings_by_id.get(item.finding_id)
            if ioc_id is not None and finding is not None:
                self.findings_by_ioc[ioc_id].append(finding)
        for ioc_id, values in self.findings_by_ioc.items():
            self.findings_by_ioc[ioc_id] = list(
                {item.id: item for item in values}.values()
            )


async def _load_accessible_dataset(
    db: AsyncSession,
    user: User,
    *,
    ioc_id: uuid.UUID | None = None,
    investigation_id: uuid.UUID | None = None,
) -> _IOCDataset:
    accessible = await _accessible_investigation_ids(db, user)
    if investigation_id is not None:
        accessible &= {investigation_id}
    if not accessible:
        return _IOCDataset(
            iocs=[],
            observations=[],
            investigations=[],
            entities=[],
            findings=[],
            evidence=[],
            reports=[],
            playbook_runs=[],
        )
    statement: Select[tuple[IOCObservation]] = select(IOCObservation).where(
        IOCObservation.investigation_id.in_(accessible)
    )
    if ioc_id is not None:
        statement = statement.where(IOCObservation.ioc_id == ioc_id)
    observation_result = await db.execute(statement)
    observations = list(observation_result.scalars().all())
    ioc_ids = {item.ioc_id for item in observations}
    investigation_ids = {item.investigation_id for item in observations}
    entity_ids = {
        item.recon_entity_id
        for item in observations
        if item.recon_entity_id is not None
    }
    if not ioc_ids:
        return _IOCDataset(
            iocs=[],
            observations=[],
            investigations=[],
            entities=[],
            findings=[],
            evidence=[],
            reports=[],
            playbook_runs=[],
        )
    iocs = list(
        (
            await db.execute(
                select(IOC).where(IOC.id.in_(ioc_ids)).order_by(IOC.last_seen.desc())
            )
        )
        .scalars()
        .all()
    )
    investigations = list(
        (
            await db.execute(
                select(Investigation).where(Investigation.id.in_(investigation_ids))
            )
        )
        .scalars()
        .all()
    )
    entities = (
        list(
            (
                await db.execute(
                    select(ReconEntity).where(ReconEntity.id.in_(entity_ids))
                )
            )
            .scalars()
            .all()
        )
        if entity_ids
        else []
    )
    evidence = (
        list(
            (
                await db.execute(
                    select(FindingEvidence).where(
                        FindingEvidence.recon_entity_id.in_(entity_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        if entity_ids
        else []
    )
    finding_ids = {item.finding_id for item in evidence}
    findings = (
        list(
            (
                await db.execute(select(Finding).where(Finding.id.in_(finding_ids)))
            )
            .scalars()
            .all()
        )
        if finding_ids
        else []
    )
    reports = list(
        (
            await db.execute(
                select(Report).where(
                    Report.investigation_id.in_(investigation_ids),
                    Report.status.in_(("ready", "archived")),
                )
            )
        )
        .scalars()
        .all()
    )
    playbook_runs = (
        list(
            (
                await db.execute(
                    select(PlaybookRun).where(PlaybookRun.finding_id.in_(finding_ids))
                )
            )
            .scalars()
            .all()
        )
        if finding_ids
        else []
    )
    return _IOCDataset(
        iocs=iocs,
        observations=observations,
        investigations=investigations,
        entities=entities,
        findings=findings,
        evidence=evidence,
        reports=reports,
        playbook_runs=playbook_runs,
    )


async def _accessible_investigation_ids(
    db: AsyncSession,
    user: User,
) -> set[uuid.UUID]:
    if user.role == "admin":
        result = await db.execute(select(Investigation.id))
    else:
        result = await db.execute(
            select(InvestigationMember.investigation_id).where(
                InvestigationMember.user_id == user.id
            )
        )
    return set(result.scalars().all())


def _build_summaries(dataset: _IOCDataset) -> list[IOCSummary]:
    return [
        _ioc_summary(
            ioc,
            dataset.observations_by_ioc.get(ioc.id, []),
            dataset.findings_by_ioc.get(ioc.id, []),
        )
        for ioc in dataset.iocs
    ]


def _ioc_summary(
    ioc: IOC,
    observations: Sequence[IOCObservation],
    findings: Sequence[Finding],
) -> IOCSummary:
    confidence, score, reason = _confidence(observations, findings)
    return IOCSummary(
        id=ioc.id,
        value=ioc.value,
        type=cast(IOCType, ioc.ioc_type),
        source=ioc.source,
        confidence=confidence,
        confidence_score=score,
        confidence_reason=reason,
        first_seen=min(
            (item.first_seen for item in observations),
            default=ioc.first_seen,
        ),
        last_seen=max(
            (item.last_seen for item in observations),
            default=ioc.last_seen,
        ),
        investigation_count=len({item.investigation_id for item in observations}),
        observation_count=sum(item.observation_count for item in observations),
        related_findings=len({item.id for item in findings}),
        related_entities=sum(item.recon_entity_id is not None for item in observations),
        tags=ioc.tags,
        notes=ioc.notes,
    )


def _confidence(
    observations: Sequence[IOCObservation],
    findings: Sequence[Finding],
) -> tuple[IOCConfidence, int, str]:
    investigation_count = len({item.investigation_id for item in observations})
    observation_count = sum(item.observation_count for item in observations)
    evidence_quality = round(
        sum(item.evidence_quality for item in observations) / len(observations)
    ) if observations else 0
    remediation_linked = any(
        item.remediation_status != "not_started" for item in findings
    )
    recurrence_points = min(40, investigation_count * 15)
    observation_points = min(15, observation_count * 5)
    quality_points = round(evidence_quality * 0.2)
    finding_points = min(15, len({item.id for item in findings}) * 5)
    remediation_points = 10 if remediation_linked else 0
    score = min(
        100,
        recurrence_points
        + observation_points
        + quality_points
        + finding_points
        + remediation_points,
    )
    confidence: IOCConfidence = (
        "high" if score >= 70 else "medium" if score >= 40 else "low"
    )
    reason_parts = [
        f"{investigation_count} accessible investigation observations",
        f"{observation_count} total observations",
        f"{evidence_quality}% average evidence quality",
        f"{len({item.id for item in findings})} linked findings",
    ]
    if remediation_linked:
        reason_parts.append("documented remediation linkage")
    return confidence, score, "Confidence is based on " + ", ".join(reason_parts) + "."


async def _refresh_persisted_confidence(db: AsyncSession, ioc: IOC) -> None:
    result = await db.execute(
        select(IOCObservation).where(IOCObservation.ioc_id == ioc.id)
    )
    confidence, _, reason = _confidence(list(result.scalars().all()), [])
    ioc.confidence = confidence
    ioc.confidence_reason = reason
    db.add(ioc)
    await db.flush()


def _investigation_references(
    dataset: _IOCDataset,
    ioc_id: uuid.UUID,
) -> list[IOCInvestigationReference]:
    findings = dataset.findings_by_ioc.get(ioc_id, [])
    finding_counts = Counter(item.investigation_id for item in findings)
    references: list[IOCInvestigationReference] = []
    for observation in dataset.observations_by_ioc.get(ioc_id, []):
        investigation = dataset.investigations.get(observation.investigation_id)
        if investigation is None:
            continue
        references.append(
            IOCInvestigationReference(
                investigation_id=investigation.id,
                investigation_title=investigation.title,
                first_seen=observation.first_seen,
                last_seen=observation.last_seen,
                recon_entity_id=observation.recon_entity_id,
                finding_count=finding_counts[investigation.id],
            )
        )
    return sorted(
        references,
        key=lambda item: (-item.finding_count, item.investigation_title.lower()),
    )


def _finding_reference(finding: Finding) -> IOCFindingReference:
    return IOCFindingReference(
        id=finding.id,
        investigation_id=finding.investigation_id,
        title=finding.title,
        severity=cast(FindingSeverity, finding.severity),
        status=finding.status,
        remediation_status=finding.remediation_status,
    )


def _evidence_relationships(
    dataset: _IOCDataset,
    ioc: IOC,
    observations: Sequence[IOCObservation],
    findings: Sequence[Finding],
) -> list[IOCEvidenceRelationship]:
    relationships: list[IOCEvidenceRelationship] = []
    investigation_ids = {item.investigation_id for item in observations}
    for observation in observations:
        if observation.recon_entity_id is not None:
            relationships.append(
                IOCEvidenceRelationship(
                    relationship_type="recon_entity",
                    resource_id=str(observation.recon_entity_id),
                    title=f"Passive recon observation: {ioc.value}",
                    investigation_id=observation.investigation_id,
                    why_this_matters=(
                        "This IOC originates from a stored passive recon entity with "
                        "source and observation timestamps."
                    ),
                )
            )
        relationships.append(
            IOCEvidenceRelationship(
                relationship_type="timeline",
                resource_id=f"ioc:{ioc.id}:{observation.id}",
                title="IOC observation window",
                investigation_id=observation.investigation_id,
                why_this_matters=(
                    f"Observed from {observation.first_seen.isoformat()} through "
                    f"{observation.last_seen.isoformat()}."
                ),
            )
        )
    for finding in findings:
        relationships.append(
            IOCEvidenceRelationship(
                relationship_type="finding",
                resource_id=str(finding.id),
                title=finding.title,
                investigation_id=finding.investigation_id,
                why_this_matters=(
                    "The finding contains evidence that references this IOC's stored "
                    "recon entity."
                ),
            )
        )
        if finding.remediation_status != "not_started":
            relationships.append(
                IOCEvidenceRelationship(
                    relationship_type="remediation",
                    resource_id=str(finding.id),
                    title=f"{finding.title}: {finding.remediation_status}",
                    investigation_id=finding.investigation_id,
                    why_this_matters=(
                        "Remediation ownership or progress is documented for a finding "
                        "linked to this IOC."
                    ),
                )
            )
    for report in dataset.reports:
        if report.investigation_id in investigation_ids:
            relationships.append(
                IOCEvidenceRelationship(
                    relationship_type="report",
                    resource_id=str(report.id),
                    title=report.title or f"{report.report_type.title()} report",
                    investigation_id=report.investigation_id,
                    why_this_matters=(
                        "The report summarizes the investigation that contains this "
                        "IOC observation."
                    ),
                )
            )
    finding_ids = {item.id for item in findings}
    for run in dataset.playbook_runs:
        if run.finding_id in finding_ids:
            finding = next(
                item for item in findings if item.id == run.finding_id
            )
            relationships.append(
                IOCEvidenceRelationship(
                    relationship_type="playbook",
                    resource_id=str(run.id),
                    title=f"Defensive playbook run: {run.status}",
                    investigation_id=finding.investigation_id,
                    why_this_matters=(
                        "An analyst-approved defensive playbook is linked through a "
                        "finding associated with this IOC."
                    ),
                )
            )
    return relationships


def _correlation_category(
    ioc: IOC,
    findings: Sequence[Finding],
) -> IOCCorrelationCategory:
    title_counts = Counter(item.title.lower() for item in findings)
    if any(count >= 2 for count in title_counts.values()):
        return "recurring findings"
    if ioc.ioc_type in {"domain", "subdomain", "hostname", "url"}:
        return "recurring domains"
    if ioc.ioc_type == "ip":
        return "recurring IPs"
    if ioc.ioc_type == "certificate":
        return "recurring certificates"
    if ioc.ioc_type == "technology":
        return "recurring technologies"
    return "recurring infrastructure"


def _severity_distribution(
    findings: Sequence[Finding],
) -> dict[FindingSeverity, int]:
    counts: dict[FindingSeverity, int] = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "info": 0,
    }
    for finding in findings:
        counts[cast(FindingSeverity, finding.severity)] += 1
    return counts


def _prioritize_ioc(
    summary: IOCSummary,
    findings: Sequence[Finding],
    investigation_id: uuid.UUID,
    investigation_score: int,
) -> IOCPriorityItem:
    relevant = [
        item for item in findings if item.investigation_id == investigation_id
    ]
    unresolved = [
        item for item in relevant if item.status in _UNRESOLVED_FINDING_STATUSES
    ]
    severity = max(
        (_SEVERITY_WEIGHT.get(item.severity, 0) for item in relevant),
        default=0,
    )
    recurrence = min(20, max(0, summary.investigation_count - 1) * 10)
    unresolved_points = min(20, len(unresolved) * 5)
    remediation_gap = min(
        15,
        sum(
            item.remediation_status not in _RESOLVED_REMEDIATION
            for item in unresolved
        )
        * 5,
    )
    confidence = round(summary.confidence_score * 0.1)
    case_risk = round(investigation_score * 0.1)
    score = min(
        100,
        severity
        + recurrence
        + unresolved_points
        + remediation_gap
        + confidence
        + case_risk,
    )
    reasons = [
        f"IOC confidence is {summary.confidence} ({summary.confidence_score}/100).",
        f"Seen in {summary.investigation_count} accessible investigations.",
    ]
    if unresolved:
        reasons.append(f"{len(unresolved)} linked findings remain unresolved.")
    if remediation_gap:
        reasons.append("Linked findings have incomplete remediation.")
    return IOCPriorityItem(
        ioc=summary,
        score=score,
        category=_priority_category(score),
        reasons=reasons,
    )


def _priority_category(score: int) -> IOCPriorityCategory:
    if score <= 25:
        return "Low Priority"
    if score <= 50:
        return "Moderate Priority"
    if score <= 75:
        return "High Priority"
    return "Immediate Review"


def _guidance_for_ioc(ioc: IOC) -> list[str]:
    text = f"{ioc.value} {' '.join(ioc.tags)}".lower()
    guidance = [
        item
        for card in _IOC_GUIDANCE
        if any(term.lower() in text for term in card.applies_to)
        for item in (
            *card.monitoring_guidance,
            *card.logging_recommendations,
            *card.remediation_guidance,
        )
    ]
    return list(dict.fromkeys(guidance)) or [
        "Validate ownership and expected exposure for this IOC.",
        "Document an observable signal before closing related findings.",
    ]


def _ioc_tags(entity: ReconEntity) -> list[str]:
    values = [
        entity.entity_type.lower(),
        entity.source or "passive_recon",
    ]
    technologies = entity.properties.get("technologies")
    if isinstance(technologies, list):
        values.extend(
            item.lower()
            for item in technologies
            if isinstance(item, str) and item.strip()
        )
    return list(dict.fromkeys(values))


def _entity_evidence_quality(entity: ReconEntity) -> int:
    populated = sum(
        value not in (None, "", [], {})
        for value in entity.properties.values()
    )
    return min(90, 50 + populated * 10 + (10 if entity.source else 0))
