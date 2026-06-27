from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding import Finding
from app.models.finding_evidence import FindingEvidence
from app.models.finding_tag import FindingTag
from app.models.investigation_enrichment import InvestigationEnrichment
from app.models.recon_entity import ReconEntity
from app.models.recon_relationship import ReconRelationship
from app.models.threat_finding import ThreatFinding
from app.models.user import User
from app.schemas.finding import FindingSeverity
from app.schemas.recon import JsonProperties
from app.services.knowledge.retriever import KnowledgeCitation, retrieve_context

_ENGINE_NAME = "findings-intelligence-v1"
_SENSITIVE_SERVICES = {
    "rdp": ("high", 70),
    "3389": ("high", 70),
    "ssh": ("medium", 55),
    "22": ("medium", 55),
    "ftp": ("medium", 50),
    "21": ("medium", 50),
    "mysql": ("medium", 55),
    "3306": ("medium", 55),
    "postgres": ("medium", 55),
    "postgresql": ("medium", 55),
    "5432": ("medium", 55),
    "mssql": ("medium", 55),
    "1433": ("medium", 55),
    "redis": ("medium", 55),
    "6379": ("medium", 55),
}


@dataclass(frozen=True)
class EvidenceCandidate:
    evidence_type: str
    source: str
    description: str
    data: JsonProperties = field(default_factory=dict)
    recon_entity_id: uuid.UUID | None = None
    threat_finding_id: uuid.UUID | None = None


@dataclass(frozen=True)
class FindingCandidate:
    title: str
    description: str
    severity: FindingSeverity
    confidence_score: int
    risk_score: int
    source: str
    evidence: list[EvidenceCandidate]
    tags: list[str] = field(default_factory=list)
    rule_id: str = "generic"
    summary: str | None = None
    affected_targets: list[str] = field(default_factory=list)
    framework_mappings: list[dict[str, object]] = field(default_factory=list)
    remediation_guidance: list[str] = field(default_factory=list)
    analyst_notes: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)


async def generate_findings_for_investigation(
    db: AsyncSession,
    user: User | None,
    investigation_id: uuid.UUID,
) -> list[Finding]:
    dataset = await _load_dataset(db, investigation_id)
    for candidate in build_finding_candidates(
        enrichments=dataset.enrichments,
        threat_findings=dataset.threat_findings,
        entities=dataset.entities,
        relationships=dataset.relationships,
        stored_evidence=dataset.stored_evidence,
    ):
        await _ensure_finding(db, user, investigation_id, candidate)

    result = await db.execute(
        select(Finding)
        .where(Finding.investigation_id == investigation_id)
        .order_by(Finding.risk_score.desc(), Finding.created_at.desc())
    )
    return list(result.scalars().all())


def build_finding_candidates(
    *,
    enrichments: list[InvestigationEnrichment],
    threat_findings: list[ThreatFinding],
    entities: list[ReconEntity],
    relationships: list[ReconRelationship] | None = None,
    stored_evidence: list[FindingEvidence] | None = None,
) -> list[FindingCandidate]:
    entity_by_value = {entity.value.lower(): entity for entity in entities}
    entity_by_id = {entity.id: entity for entity in entities}
    candidates: list[FindingCandidate] = []

    for threat in threat_findings:
        try:
            candidate = _candidate_from_threat_finding(threat)
            if candidate is not None:
                candidates.append(candidate)
        except Exception:
            continue

    for enrichment in enrichments:
        try:
            candidates.extend(_candidates_from_enrichment(enrichment, entity_by_value))
        except Exception:
            continue

    for entity in entities:
        try:
            candidate = _candidate_from_recon_entity(entity)
            if candidate is not None:
                candidates.append(candidate)
        except Exception:
            continue

    for relationship in relationships or []:
        try:
            candidate = _candidate_from_relationship(relationship, entity_by_id)
            if candidate is not None:
                candidates.append(candidate)
        except Exception:
            continue

    candidates.extend(
        _candidates_from_stored_evidence(stored_evidence or [], entity_by_id)
    )
    return [_enrich_candidate(candidate) for candidate in _dedupe_candidates(candidates)]


@dataclass(frozen=True)
class _FindingDataset:
    enrichments: list[InvestigationEnrichment]
    threat_findings: list[ThreatFinding]
    entities: list[ReconEntity]
    relationships: list[ReconRelationship]
    stored_evidence: list[FindingEvidence]


async def _load_dataset(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> _FindingDataset:
    enrichment_result = await db.execute(
        select(InvestigationEnrichment).where(
            InvestigationEnrichment.investigation_id == investigation_id
        )
    )
    threat_result = await db.execute(
        select(ThreatFinding).where(ThreatFinding.investigation_id == investigation_id)
    )
    entity_result = await db.execute(
        select(ReconEntity).where(ReconEntity.investigation_id == investigation_id)
    )
    relationship_result = await db.execute(
        select(ReconRelationship).where(
            ReconRelationship.investigation_id == investigation_id
        )
    )
    finding_result = await db.execute(
        select(Finding.id).where(Finding.investigation_id == investigation_id)
    )
    finding_ids = list(finding_result.scalars().all())
    stored_evidence: list[FindingEvidence] = []
    if finding_ids:
        evidence_result = await db.execute(
            select(FindingEvidence).where(FindingEvidence.finding_id.in_(finding_ids))
        )
        stored_evidence = list(evidence_result.scalars().all())

    return _FindingDataset(
        enrichments=list(enrichment_result.scalars().all()),
        threat_findings=list(threat_result.scalars().all()),
        entities=list(entity_result.scalars().all()),
        relationships=list(relationship_result.scalars().all()),
        stored_evidence=stored_evidence,
    )


def _candidate_from_threat_finding(
    threat: ThreatFinding,
) -> FindingCandidate | None:
    if threat.status != "completed" or threat.risk_score < 50:
        return None
    if threat.provider == "virustotal":
        severity: FindingSeverity = "critical" if threat.risk_score >= 90 else "high"
        return FindingCandidate(
            title=f"Malicious VirusTotal reputation for {threat.target_value}",
            description=(
                "VirusTotal reputation signals indicate malicious or suspicious "
                f"activity for {threat.target_value}."
            ),
            severity=severity,
            confidence_score=90,
            risk_score=threat.risk_score,
            source="virustotal",
            evidence=[
                EvidenceCandidate(
                    evidence_type="threat_reputation",
                    source="virustotal",
                    description=(
                        "VirusTotal provider result exceeded the risk threshold."
                    ),
                    data=_safe_properties(threat.normalized_data),
                    recon_entity_id=threat.recon_entity_id,
                    threat_finding_id=threat.id,
                )
            ],
            tags=["threat-intel", "reputation", "virustotal"],
            rule_id="threat-intel:virustotal-risk",
            affected_targets=[threat.target_value],
        )
    if threat.provider == "abuseipdb":
        severity = "critical" if threat.risk_score >= 90 else "high"
        return FindingCandidate(
            title=f"High AbuseIPDB reputation for {threat.target_value}",
            description=(
                "AbuseIPDB confidence indicates reported abuse activity for "
                f"{threat.target_value}."
            ),
            severity=severity,
            confidence_score=90,
            risk_score=threat.risk_score,
            source="abuseipdb",
            evidence=[
                EvidenceCandidate(
                    evidence_type="threat_reputation",
                    source="abuseipdb",
                    description=(
                        "AbuseIPDB provider result exceeded the risk threshold."
                    ),
                    data=_safe_properties(threat.normalized_data),
                    recon_entity_id=threat.recon_entity_id,
                    threat_finding_id=threat.id,
                )
            ],
            tags=["threat-intel", "reputation", "abuseipdb"],
            rule_id="threat-intel:abuseipdb-risk",
            affected_targets=[threat.target_value],
        )
    return None


def _candidates_from_enrichment(
    enrichment: InvestigationEnrichment,
    entity_by_value: dict[str, ReconEntity],
) -> list[FindingCandidate]:
    result: dict[str, Any] = (
        enrichment.result if isinstance(enrichment.result, dict) else {}
    )
    http_value = result.get("http")
    http: dict[str, Any] = http_value if isinstance(http_value, dict) else {}
    dns_value = result.get("dns")
    dns: dict[str, Any] = dns_value if isinstance(dns_value, dict) else {}
    certs_value = result.get("certificates")
    certs: dict[str, Any] = certs_value if isinstance(certs_value, dict) else {}
    target = str(result.get("target_value") or enrichment.target_value)
    entity = entity_by_value.get(target.lower())
    entity_id = entity.id if entity is not None else None

    candidates: list[FindingCandidate] = []
    not_after = _nested_str(http, "certificate", "not_after")
    if not_after and _is_expired(not_after):
        candidates.append(
            FindingCandidate(
                title=f"Expired TLS certificate for {target}",
                description=f"The TLS certificate observed for {target} is expired.",
                severity="medium",
                confidence_score=85,
                risk_score=50,
                source="tls",
                evidence=[
                    EvidenceCandidate(
                        evidence_type="tls_certificate",
                        source="tls",
                        description="Certificate not_after timestamp is in the past.",
                        data={"not_after": not_after},
                        recon_entity_id=entity_id,
                    )
                ],
                tags=["tls", "certificate"],
                rule_id="tls:expired-certificate",
                affected_targets=[target],
            )
        )

    server = _str_or_none(http.get("server"))
    if server and _contains_version(server):
        candidates.append(
            FindingCandidate(
                title=f"Risky server disclosure for {target}",
                description=(
                    f"The HTTP Server header discloses technology details: {server}."
                ),
                severity="low",
                confidence_score=70,
                risk_score=20,
                source="http",
                evidence=[
                    EvidenceCandidate(
                        evidence_type="http_header",
                        source="http",
                        description="Server header exposes product or version details.",
                        data={"server": server},
                        recon_entity_id=entity_id,
                    )
                ],
                tags=["http", "technology-disclosure"],
                rule_id="http:server-version-disclosure",
                affected_targets=[target],
            )
        )

    headers_value = http.get("headers")
    headers: dict[object, object] = (
        headers_value if isinstance(headers_value, dict) else {}
    )
    exposed = _exposed_internal_headers(headers)
    if exposed:
        candidates.append(
            FindingCandidate(
                title=f"Exposed internal metadata for {target}",
                description=(
                    "HTTP response headers expose internal implementation metadata."
                ),
                severity="medium",
                confidence_score=75,
                risk_score=45,
                source="http",
                evidence=[
                    EvidenceCandidate(
                        evidence_type="http_header",
                        source="http",
                        description="Internal metadata headers were present.",
                        data={"headers": list(exposed.keys())},
                        recon_entity_id=entity_id,
                    )
                ],
                tags=["http", "metadata-disclosure"],
                rule_id="http:internal-metadata-disclosure",
                affected_targets=[target],
            )
        )

    for spf in _list_of_strings(dns.get("spf_records")):
        if "+all" in spf.lower():
            candidates.append(
                FindingCandidate(
                    title=f"Suspicious SPF policy for {target}",
                    description=(
                        "SPF policy includes +all, which authorizes any sender."
                    ),
                    severity="low",
                    confidence_score=75,
                    risk_score=20,
                    source="dns",
                    evidence=[
                        EvidenceCandidate(
                            evidence_type="dns_txt",
                            source="dns",
                            description="Permissive SPF record detected.",
                            data={"spf_record": spf},
                            recon_entity_id=entity_id,
                        )
                    ],
                    tags=["dns", "spf"],
                    rule_id="dns:permissive-spf",
                    affected_targets=[target],
                )
            )

    cert_records = certs.get("certificates") if isinstance(certs, dict) else []
    for cert in cert_records if isinstance(cert_records, list) else []:
        if not isinstance(cert, dict):
            continue
        san_names = _list_of_strings(cert.get("san_names"))
        if len(san_names) > 100:
            candidates.append(
                FindingCandidate(
                    title=f"Large certificate SAN set for {target}",
                    description=(
                        "Certificate contains an unusually large number of SAN names."
                    ),
                    severity="medium",
                    confidence_score=70,
                    risk_score=45,
                    source="certificate",
                    evidence=[
                        EvidenceCandidate(
                            evidence_type="certificate",
                            source="certificate",
                            description="Large SAN list observed in certificate data.",
                            data={"san_count": len(san_names)},
                            recon_entity_id=entity_id,
                        )
                    ],
                    tags=["certificate", "anomaly"],
                    rule_id="certificate:large-san-set",
                    affected_targets=[target],
                )
            )

    if enrichment.status == "partial":
        errors = _enrichment_errors(result)
        if errors:
            candidates.append(
                FindingCandidate(
                    title=f"Partial passive enrichment for {target}",
                    description=(
                        "Passive enrichment completed with provider-specific errors."
                    ),
                    severity="info",
                    confidence_score=70,
                    risk_score=5,
                    source="timeline",
                    evidence=[
                        EvidenceCandidate(
                            evidence_type="timeline_artifact",
                            source="recon",
                            description="Recon enrichment status was partial.",
                            data={"errors": errors},
                            recon_entity_id=entity_id,
                        )
                    ],
                    tags=["timeline", "recon", "partial"],
                    rule_id="timeline:partial-enrichment",
                    affected_targets=[target],
                )
            )

    return candidates


def _candidate_from_recon_entity(entity: ReconEntity) -> FindingCandidate | None:
    if entity.entity_type == "Subdomain" and _suspicious_subdomain(entity.value):
        return FindingCandidate(
            title=f"Suspicious subdomain discovered: {entity.value}",
            description=(
                "Subdomain naming suggests an administrative, internal, or staging "
                "system that may need validation."
            ),
            severity="medium",
            confidence_score=65,
            risk_score=35,
            source="entity-graph",
            evidence=[
                EvidenceCandidate(
                    evidence_type="recon_entity",
                    source="entity-graph",
                    description="Suspicious subdomain keyword detected.",
                    data={"subdomain": entity.value},
                    recon_entity_id=entity.id,
                )
            ],
            tags=["subdomain", "entity-graph"],
            rule_id="entity:suspicious-subdomain",
            affected_targets=[entity.value],
        )
    if entity.entity_type == "ASN":
        provider = str(entity.properties.get("provider", "")).lower()
        if any(term in provider for term in ("bulletproof", "offshore", "anonymous")):
            return FindingCandidate(
                title=f"Suspicious ASN provider for {entity.value}",
                description="ASN provider metadata contains suspicious hosting terms.",
                severity="medium",
                confidence_score=60,
                risk_score=40,
                source="asn",
                evidence=[
                    EvidenceCandidate(
                        evidence_type="recon_entity",
                        source="asn",
                        description="Suspicious ASN provider metadata detected.",
                        data={"provider": provider},
                        recon_entity_id=entity.id,
                    )
                ],
                tags=["asn", "hosting"],
                rule_id="entity:suspicious-asn-provider",
                affected_targets=[entity.value],
            )
    if entity.entity_type == "Service":
        service_value = _service_value(entity)
        service_key = service_value.lower()
        for marker, (severity, risk_score) in _SENSITIVE_SERVICES.items():
            if marker in service_key:
                finding_severity: FindingSeverity = severity  # type: ignore[assignment]
                return FindingCandidate(
                    title=f"Sensitive service observed: {entity.value}",
                    description=(
                        "Passive recon identified a service that should be reviewed "
                        "for exposure, ownership, and access controls."
                    ),
                    severity=finding_severity,
                    confidence_score=65,
                    risk_score=risk_score,
                    source="service",
                    evidence=[
                        EvidenceCandidate(
                            evidence_type="recon_entity",
                            source="service",
                            description="Sensitive service keyword or port observed.",
                            data={"service": service_value},
                            recon_entity_id=entity.id,
                        )
                    ],
                    tags=["service", "exposure"],
                    rule_id="entity:sensitive-service",
                    affected_targets=[entity.value],
                )
    if entity.entity_type == "Technology" and _contains_version(entity.value):
        return FindingCandidate(
            title=f"Technology version disclosure: {entity.value}",
            description=(
                "Technology entity includes version details that should be reviewed "
                "for lifecycle and disclosure risk."
            ),
            severity="low",
            confidence_score=60,
            risk_score=20,
            source="technology",
            evidence=[
                EvidenceCandidate(
                    evidence_type="recon_entity",
                    source="technology",
                    description="Technology version string observed.",
                    data={"technology": entity.value},
                    recon_entity_id=entity.id,
                )
            ],
            tags=["technology", "version-disclosure"],
            rule_id="entity:technology-version",
            affected_targets=[entity.value],
        )
    return None


def _candidate_from_relationship(
    relationship: ReconRelationship,
    entity_by_id: dict[uuid.UUID, ReconEntity],
) -> FindingCandidate | None:
    source = entity_by_id.get(relationship.source_entity_id)
    target = entity_by_id.get(relationship.target_entity_id)
    if source is None or target is None:
        return None
    if relationship.relationship_type == "HOSTS" and target.entity_type == "Service":
        service_candidate = _candidate_from_recon_entity(target)
        if service_candidate is None:
            return None
        return FindingCandidate(
            title=f"{source.value} hosts sensitive service {target.value}",
            description=(
                "Recon relationships show an asset hosting a sensitive service that "
                "requires defensive validation."
            ),
            severity=service_candidate.severity,
            confidence_score=70,
            risk_score=max(service_candidate.risk_score, 50),
            source="relationship",
            evidence=[
                EvidenceCandidate(
                    evidence_type="recon_relationship",
                    source=relationship.source or "recon",
                    description="HOSTS relationship links asset to sensitive service.",
                    data={
                        "relationship_type": relationship.relationship_type,
                        "source": source.value,
                        "target": target.value,
                    },
                    recon_entity_id=source.id,
                )
            ],
            tags=["relationship", "service", "exposure"],
            rule_id="relationship:hosted-sensitive-service",
            affected_targets=[source.value, target.value],
        )
    return None


def _candidates_from_stored_evidence(
    stored_evidence: list[FindingEvidence],
    entity_by_id: dict[uuid.UUID, ReconEntity],
) -> list[FindingCandidate]:
    candidates: list[FindingCandidate] = []
    grouped: dict[str, list[FindingEvidence]] = {}
    for evidence in stored_evidence:
        grouped.setdefault(evidence.evidence_type, []).append(evidence)
    for evidence_type, items in grouped.items():
        if len(items) < 3:
            continue
        affected_targets = _targets_from_evidence(items, entity_by_id)
        candidates.append(
            FindingCandidate(
                title=f"Recurring evidence pattern: {evidence_type}",
                description=(
                    "Multiple stored evidence records share the same evidence type, "
                    "indicating a recurring defensive pattern to review."
                ),
                severity="info",
                confidence_score=60,
                risk_score=10,
                source="stored-evidence",
                evidence=[
                    EvidenceCandidate(
                        evidence_type="finding_evidence",
                        source="stored-evidence",
                        description=f"{len(items)} evidence records matched.",
                        data={
                            "evidence_type": evidence_type,
                            "evidence_count": len(items),
                        },
                    )
                ],
                tags=["stored-evidence", evidence_type],
                rule_id="evidence:recurring-pattern",
                affected_targets=affected_targets,
            )
        )
    return candidates


async def _ensure_finding(
    db: AsyncSession,
    user: User | None,
    investigation_id: uuid.UUID,
    candidate: FindingCandidate,
) -> Finding:
    result = await db.execute(
        select(Finding).where(
            Finding.investigation_id == investigation_id,
            Finding.title == candidate.title,
            Finding.source == candidate.source,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.normalized_data = _normalized_data(candidate)
        existing.raw_data = _raw_data(candidate)
        existing.description = candidate.description
        existing.confidence_score = candidate.confidence_score
        existing.risk_score = candidate.risk_score
        existing.severity = candidate.severity
        db.add(existing)
        await db.flush()
        await _ensure_evidence_and_tags(db, existing, candidate)
        await db.refresh(existing)
        return existing

    finding = Finding(
        investigation_id=investigation_id,
        title=candidate.title,
        description=candidate.description,
        severity=candidate.severity,
        confidence_score=candidate.confidence_score,
        risk_score=candidate.risk_score,
        source=candidate.source,
        status="new",
        created_by=user.id if user is not None else None,
        raw_data=_raw_data(candidate),
        normalized_data=_normalized_data(candidate),
        evidence_urls=candidate.references,
    )
    db.add(finding)
    await db.flush()
    await _ensure_evidence_and_tags(db, finding, candidate)
    await db.refresh(finding)
    return finding


async def _ensure_evidence_and_tags(
    db: AsyncSession,
    finding: Finding,
    candidate: FindingCandidate,
) -> None:
    evidence_result = await db.execute(
        select(FindingEvidence).where(FindingEvidence.finding_id == finding.id)
    )
    existing_evidence = {
        (item.evidence_type, item.source, item.description)
        for item in evidence_result.scalars().all()
    }
    for evidence in candidate.evidence:
        key = (evidence.evidence_type, evidence.source, evidence.description)
        if key in existing_evidence:
            continue
        db.add(
            FindingEvidence(
                finding_id=finding.id,
                recon_entity_id=evidence.recon_entity_id,
                threat_finding_id=evidence.threat_finding_id,
                evidence_type=evidence.evidence_type,
                source=evidence.source,
                description=evidence.description,
                data=evidence.data,
            )
        )

    tag_result = await db.execute(
        select(FindingTag.tag).where(FindingTag.finding_id == finding.id)
    )
    existing_tags = set(tag_result.scalars().all())
    for tag in candidate.tags:
        if tag not in existing_tags:
            db.add(FindingTag(finding_id=finding.id, tag=tag))
    await db.flush()


def _enrich_candidate(candidate: FindingCandidate) -> FindingCandidate:
    citations = _knowledge_citations(candidate)
    framework_mappings = candidate.framework_mappings or [
        _mapping_from_citation(candidate, citation) for citation in citations
    ]
    references = _dedupe_strings(
        [*candidate.references, *[citation.id for citation in citations]]
    )
    return FindingCandidate(
        title=candidate.title,
        description=candidate.description,
        severity=candidate.severity,
        confidence_score=candidate.confidence_score,
        risk_score=candidate.risk_score,
        source=candidate.source,
        evidence=candidate.evidence,
        tags=_dedupe_strings(candidate.tags),
        rule_id=candidate.rule_id,
        summary=candidate.summary or _summary(candidate),
        affected_targets=_affected_targets(candidate),
        framework_mappings=framework_mappings,
        remediation_guidance=candidate.remediation_guidance
        or _remediation_guidance(candidate),
        analyst_notes=candidate.analyst_notes or _analyst_notes(candidate),
        references=references,
    )


def _knowledge_citations(candidate: FindingCandidate) -> list[KnowledgeCitation]:
    query = " ".join(
        [
            candidate.title,
            candidate.description,
            " ".join(candidate.tags),
            candidate.source,
        ]
    )
    result = retrieve_context(query, top_k=3)
    return result.citations


def _mapping_from_citation(
    candidate: FindingCandidate,
    citation: KnowledgeCitation,
) -> dict[str, object]:
    return {
        "framework": citation.framework,
        "control": citation.category,
        "rationale": (
            f"Local defensive knowledge matched deterministic finding rule "
            f"{candidate.rule_id}."
        ),
        "citation_ids": [citation.id],
        "confidence": round(citation.confidence * 100),
    }


def _normalized_data(candidate: FindingCandidate) -> dict[str, Any]:
    return {
        "engine": _ENGINE_NAME,
        "rule_id": candidate.rule_id,
        "summary": candidate.summary or _summary(candidate),
        "evidence_count": len(candidate.evidence),
        "affected_targets": candidate.affected_targets,
        "framework_mappings": candidate.framework_mappings,
        "remediation_guidance": candidate.remediation_guidance,
        "analyst_notes": candidate.analyst_notes,
        "references": candidate.references,
        "tags": candidate.tags,
    }


def _raw_data(candidate: FindingCandidate) -> dict[str, Any]:
    return {
        "engine": _ENGINE_NAME,
        "rule_id": candidate.rule_id,
        "evidence": [
            {
                "evidence_type": evidence.evidence_type,
                "source": evidence.source,
                "description": evidence.description,
                "data": evidence.data,
                "recon_entity_id": str(evidence.recon_entity_id)
                if evidence.recon_entity_id
                else None,
                "threat_finding_id": str(evidence.threat_finding_id)
                if evidence.threat_finding_id
                else None,
            }
            for evidence in candidate.evidence
        ],
    }


def _summary(candidate: FindingCandidate) -> str:
    return candidate.description.split(".")[0].strip() + "."


def _affected_targets(candidate: FindingCandidate) -> list[str]:
    values = list(candidate.affected_targets)
    for evidence in candidate.evidence:
        for key in (
            "target",
            "target_value",
            "value",
            "domain",
            "ip",
            "url",
            "host",
            "hostname",
            "source",
            "target",
            "service",
            "subdomain",
        ):
            raw = evidence.data.get(key)
            if isinstance(raw, str) and raw:
                values.append(raw)
    return _dedupe_strings(values)


def _remediation_guidance(candidate: FindingCandidate) -> list[str]:
    tags = set(candidate.tags)
    if "certificate" in tags or candidate.source == "tls":
        return [
            "Renew or replace the affected certificate.",
            "Validate certificate chain, SAN coverage, and expiration monitoring.",
        ]
    if "metadata-disclosure" in tags:
        return [
            "Remove internal/debug headers from externally visible responses.",
            "Review reverse proxy and application middleware header policies.",
        ]
    if "technology-disclosure" in tags or candidate.source == "technology":
        return [
            "Reduce unnecessary product and version disclosure in response metadata.",
            "Confirm the disclosed technology version is supported and patched.",
        ]
    if "spf" in tags:
        return [
            "Replace permissive SPF mechanisms with an explicit sender policy.",
            "Review DKIM and DMARC alignment for the domain.",
        ]
    if "threat-intel" in tags:
        return [
            "Validate the reputation signal with asset ownership and business context.",
            "Apply monitoring, blocking, or remediation according to defensive policy.",
        ]
    if "service" in tags:
        return [
            "Confirm whether the service is intentionally exposed.",
            "Restrict access with network controls, MFA, and asset-owner approval.",
        ]
    return [
        "Validate the finding with the asset owner.",
        "Track remediation status and preserve linked evidence for auditability.",
    ]


def _analyst_notes(candidate: FindingCandidate) -> list[str]:
    return [
        f"Generated by deterministic rule {candidate.rule_id}.",
        "Evidence was derived from stored passive recon, timeline, or local data.",
        "No LLM, active scanning, crawling, or external enumeration was used.",
    ]


def _dedupe_candidates(candidates: list[FindingCandidate]) -> list[FindingCandidate]:
    deduped: dict[tuple[str, str], FindingCandidate] = {}
    for candidate in candidates:
        deduped.setdefault((candidate.source, candidate.title), candidate)
    return list(deduped.values())


def _nested_str(value: object, *keys: str) -> str | None:
    current: object = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _str_or_none(current)


def _is_expired(value: str) -> bool:
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed < datetime.now(UTC)


def _contains_version(value: str) -> bool:
    return any(char.isdigit() for char in value) and "/" in value


def _exposed_internal_headers(headers: dict[object, object]) -> dict[str, str]:
    exposed: dict[str, str] = {}
    suspicious = (
        "x-powered-by",
        "x-aspnet-version",
        "x-internal",
        "x-internal-env",
        "x-debug",
    )
    for key, value in headers.items():
        header = str(key).lower()
        if header.startswith(suspicious):
            exposed[str(key)] = str(value)
    return exposed


def _suspicious_subdomain(value: str) -> bool:
    labels = value.lower().split(".")
    keywords = {"admin", "dev", "staging", "test", "internal", "vpn", "backup"}
    return any(label in keywords for label in labels)


def _list_of_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _service_value(entity: ReconEntity) -> str:
    values = [entity.value]
    for key in ("service", "name", "port", "protocol", "technology"):
        raw = entity.properties.get(key)
        if isinstance(raw, str | int):
            values.append(str(raw))
    return " ".join(values)


def _enrichment_errors(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    raw_errors = result.get("errors")
    if isinstance(raw_errors, list):
        for item in raw_errors:
            if isinstance(item, dict):
                source = item.get("source")
                message = item.get("message")
                errors.append(f"{source}: {message}")
            elif isinstance(item, str):
                errors.append(item)
    for key, value in result.items():
        if isinstance(value, dict):
            nested = value.get("errors")
            if isinstance(nested, list):
                errors.extend(str(item) for item in nested)
    return _dedupe_strings([error for error in errors if error.strip()])


def _targets_from_evidence(
    items: list[FindingEvidence],
    entity_by_id: dict[uuid.UUID, ReconEntity],
) -> list[str]:
    targets: list[str] = []
    for item in items:
        if item.recon_entity_id is not None and item.recon_entity_id in entity_by_id:
            targets.append(entity_by_id[item.recon_entity_id].value)
        for key in ("target", "target_value", "value", "domain", "ip", "url"):
            raw = item.data.get(key)
            if isinstance(raw, str) and raw:
                targets.append(raw)
    return _dedupe_strings(targets)


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = value.strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def _safe_properties(value: dict[str, Any]) -> JsonProperties:
    safe: JsonProperties = {}
    for key, candidate in value.items():
        if isinstance(candidate, str | int | float | bool) or candidate is None:
            safe[key] = candidate
        elif isinstance(candidate, list) and all(
            isinstance(item, str) for item in candidate
        ):
            safe[key] = candidate
    return safe
