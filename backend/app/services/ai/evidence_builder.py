from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding import Finding
from app.models.finding_evidence import FindingEvidence
from app.models.investigation_enrichment import InvestigationEnrichment
from app.models.recon_entity import ReconEntity
from app.models.recon_relationship import ReconRelationship
from app.models.threat_finding import ThreatFinding
from app.models.user import User
from app.schemas.analysis import AnalysisCitation, CitationSourceType, IocType
from app.schemas.recon import JsonProperties
from app.services.intelligence.correlation_service import (
    generate_findings_for_investigation,
)


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    source_type: CitationSourceType
    title: str
    summary: str
    metadata: JsonProperties = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceBundle:
    investigation_id: uuid.UUID
    items: list[EvidenceItem]
    focus_terms: list[str]

    @property
    def citation_ids(self) -> set[str]:
        return {item.id for item in self.items}


async def build_investigation_evidence(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> EvidenceBundle:
    await generate_findings_for_investigation(db, user, investigation_id)
    findings = await _findings(db, investigation_id)
    finding_ids = [finding.id for finding in findings]
    evidence = await _finding_evidence(db, finding_ids)
    entities = await _recon_entities(db, investigation_id)
    relationships = await _recon_relationships(db, investigation_id)
    threat_findings = await _threat_findings(db, investigation_id)
    enrichments = await _enrichments(db, investigation_id)

    items: list[EvidenceItem] = []
    items.extend(_finding_items(findings))
    items.extend(_finding_evidence_items(evidence))
    items.extend(_entity_items(entities))
    items.extend(_relationship_items(relationships))
    items.extend(_threat_finding_items(threat_findings))
    items.extend(_enrichment_items(enrichments))
    return EvidenceBundle(
        investigation_id=investigation_id,
        items=_dedupe_items(items),
        focus_terms=_focus_terms(findings, entities, threat_findings),
    )


async def build_ioc_evidence(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    *,
    ioc_type: IocType,
    value: str,
) -> EvidenceBundle:
    bundle = await build_investigation_evidence(db, user, investigation_id)
    needle = value.lower()
    related = [
        item
        for item in bundle.items
        if needle in item.title.lower()
        or needle in item.summary.lower()
        or needle in " ".join(str(v).lower() for v in item.metadata.values())
    ]
    if not related:
        related = [
            EvidenceItem(
                id=f"ioc:{ioc_type}:{value}",
                source_type="recon_entity",
                title=f"{ioc_type.upper()} under review: {value}",
                summary=(
                    "The IOC was submitted for analyst context, but no matching "
                    "stored recon or threat intelligence evidence was found."
                ),
                metadata={"ioc_type": ioc_type, "value": value},
            )
        ]
    return EvidenceBundle(
        investigation_id=investigation_id,
        items=_dedupe_items(related),
        focus_terms=[value, ioc_type, *bundle.focus_terms[:6]],
    )


async def build_threat_context_evidence(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    *,
    finding_ids: list[uuid.UUID],
) -> EvidenceBundle:
    bundle = await build_investigation_evidence(db, user, investigation_id)
    if not finding_ids:
        return bundle
    allowed = {f"finding:{finding_id}" for finding_id in finding_ids}
    filtered = [
        item
        for item in bundle.items
        if item.id in allowed
        or str(item.metadata.get("finding_id", "")) in {str(fid) for fid in finding_ids}
    ]
    return EvidenceBundle(
        investigation_id=investigation_id,
        items=_dedupe_items(filtered),
        focus_terms=[item.title for item in filtered[:8]],
    )


def citations_from_items(items: list[EvidenceItem]) -> list[AnalysisCitation]:
    return [
        AnalysisCitation(
            id=item.id,
            source_type=item.source_type,
            title=item.title,
            summary=item.summary,
            metadata=item.metadata,
        )
        for item in items
    ]


async def _findings(db: AsyncSession, investigation_id: uuid.UUID) -> list[Finding]:
    result = await db.execute(
        select(Finding)
        .where(Finding.investigation_id == investigation_id)
        .order_by(Finding.risk_score.desc(), Finding.created_at.desc())
    )
    return list(result.scalars().all())


async def _finding_evidence(
    db: AsyncSession,
    finding_ids: list[uuid.UUID],
) -> list[FindingEvidence]:
    if not finding_ids:
        return []
    result = await db.execute(
        select(FindingEvidence)
        .where(FindingEvidence.finding_id.in_(finding_ids))
        .order_by(FindingEvidence.created_at)
    )
    return list(result.scalars().all())


async def _recon_entities(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[ReconEntity]:
    result = await db.execute(
        select(ReconEntity)
        .where(ReconEntity.investigation_id == investigation_id)
        .order_by(ReconEntity.entity_type, ReconEntity.value)
    )
    return list(result.scalars().all())


async def _recon_relationships(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[ReconRelationship]:
    result = await db.execute(
        select(ReconRelationship)
        .where(ReconRelationship.investigation_id == investigation_id)
        .order_by(ReconRelationship.relationship_type)
    )
    return list(result.scalars().all())


async def _threat_findings(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[ThreatFinding]:
    result = await db.execute(
        select(ThreatFinding)
        .where(ThreatFinding.investigation_id == investigation_id)
        .order_by(ThreatFinding.risk_score.desc(), ThreatFinding.collected_at.desc())
    )
    return list(result.scalars().all())


async def _enrichments(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[InvestigationEnrichment]:
    result = await db.execute(
        select(InvestigationEnrichment)
        .where(InvestigationEnrichment.investigation_id == investigation_id)
        .order_by(InvestigationEnrichment.created_at.desc())
    )
    return list(result.scalars().all())


def _finding_items(findings: list[Finding]) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            id=f"finding:{finding.id}",
            source_type="finding",
            title=finding.title,
            summary=finding.description,
            metadata={
                "finding_id": str(finding.id),
                "severity": finding.severity,
                "risk_score": finding.risk_score,
                "confidence_score": finding.confidence_score,
                "source": finding.source,
                "status": finding.status,
            },
        )
        for finding in findings
    ]


def _finding_evidence_items(evidence: list[FindingEvidence]) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            id=f"finding_evidence:{item.id}",
            source_type="finding_evidence",
            title=f"{item.evidence_type}: {item.source}",
            summary=item.description,
            metadata={
                "finding_id": str(item.finding_id),
                "recon_entity_id": str(item.recon_entity_id)
                if item.recon_entity_id
                else None,
                "threat_finding_id": str(item.threat_finding_id)
                if item.threat_finding_id
                else None,
                **_safe_properties(item.data),
            },
        )
        for item in evidence
    ]


def _entity_items(entities: list[ReconEntity]) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            id=f"recon_entity:{entity.id}",
            source_type="recon_entity",
            title=f"{entity.entity_type}: {entity.value}",
            summary=f"Recon entity observed from {entity.source or 'unknown source'}.",
            metadata={
                "entity_id": str(entity.id),
                "entity_type": entity.entity_type,
                "value": entity.value,
                "source": entity.source,
                **_safe_properties(entity.properties),
            },
        )
        for entity in entities
    ]


def _relationship_items(
    relationships: list[ReconRelationship],
) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            id=f"recon_relationship:{relationship.id}",
            source_type="recon_relationship",
            title=f"Relationship: {relationship.relationship_type}",
            summary=(
                "Investigation graph relationship connects recon entities "
                f"{relationship.source_entity_id} and {relationship.target_entity_id}."
            ),
            metadata={
                "relationship_id": str(relationship.id),
                "relationship_type": relationship.relationship_type,
                "source_entity_id": str(relationship.source_entity_id),
                "target_entity_id": str(relationship.target_entity_id),
                "source": relationship.source,
            },
        )
        for relationship in relationships
    ]


def _threat_finding_items(threats: list[ThreatFinding]) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            id=f"threat_finding:{threat.id}",
            source_type="threat_finding",
            title=f"{threat.provider} reputation for {threat.target_value}",
            summary=(
                f"Provider status {threat.status}; verdict {threat.verdict}; "
                f"risk score {threat.risk_score}."
            ),
            metadata={
                "threat_finding_id": str(threat.id),
                "recon_entity_id": str(threat.recon_entity_id),
                "provider": threat.provider,
                "target_type": threat.target_type,
                "target_value": threat.target_value,
                "status": threat.status,
                "risk_score": threat.risk_score,
                "confidence": threat.confidence,
                "signals": threat.signals,
            },
        )
        for threat in threats
    ]


def _enrichment_items(
    enrichments: list[InvestigationEnrichment],
) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            id=f"investigation_enrichment:{enrichment.id}",
            source_type="investigation_enrichment",
            title=f"{enrichment.target_type}: {enrichment.target_value}",
            summary=f"Passive enrichment status: {enrichment.status}.",
            metadata={
                "enrichment_id": str(enrichment.id),
                "target_type": enrichment.target_type,
                "target_value": enrichment.target_value,
                "status": enrichment.status,
                **_safe_properties(enrichment.summary),
            },
        )
        for enrichment in enrichments
    ]


def _focus_terms(
    findings: list[Finding],
    entities: list[ReconEntity],
    threats: list[ThreatFinding],
) -> list[str]:
    terms: list[str] = []
    terms.extend(finding.title for finding in findings[:8])
    terms.extend(entity.value for entity in entities[:8])
    terms.extend(threat.target_value for threat in threats[:8])
    terms.extend(threat.provider for threat in threats[:4])
    return _dedupe_strings(terms)


def _dedupe_items(items: list[EvidenceItem]) -> list[EvidenceItem]:
    deduped: dict[str, EvidenceItem] = {}
    for item in items:
        deduped.setdefault(item.id, item)
    return list(deduped.values())


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        clean = value.strip()
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            deduped.append(clean)
    return deduped


def _safe_properties(value: dict[str, object]) -> JsonProperties:
    safe: JsonProperties = {}
    for key, candidate in value.items():
        if isinstance(candidate, str | int | float | bool) or candidate is None:
            safe[key] = candidate
        elif isinstance(candidate, list):
            safe_list = _safe_list(candidate)
            if safe_list is not None:
                safe[key] = safe_list
    return safe


def _safe_list(value: list[object]) -> list[str] | list[int] | list[float] | list[bool] | None:
    if all(isinstance(item, str) for item in value):
        return [str(item) for item in value]
    if all(isinstance(item, bool) for item in value):
        return [bool(item) for item in value]
    if all(isinstance(item, int) and not isinstance(item, bool) for item in value):
        return [int(item) for item in value]
    if all(isinstance(item, float) for item in value):
        return [float(item) for item in value]
    return None
