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
from app.models.threat_finding import ThreatFinding
from app.models.user import User
from app.schemas.finding import FindingSeverity
from app.schemas.recon import JsonProperties


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


async def generate_findings_for_investigation(
    db: AsyncSession,
    user: User | None,
    investigation_id: uuid.UUID,
) -> list[Finding]:
    enrichments = list(
        (
            await db.execute(
                select(InvestigationEnrichment).where(
                    InvestigationEnrichment.investigation_id == investigation_id
                )
            )
        )
        .scalars()
        .all()
    )
    threat_findings = list(
        (
            await db.execute(
                select(ThreatFinding).where(
                    ThreatFinding.investigation_id == investigation_id
                )
            )
        )
        .scalars()
        .all()
    )
    entities = list(
        (
            await db.execute(
                select(ReconEntity).where(
                    ReconEntity.investigation_id == investigation_id
                )
            )
        )
        .scalars()
        .all()
    )

    for candidate in build_finding_candidates(
        enrichments=enrichments,
        threat_findings=threat_findings,
        entities=entities,
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
) -> list[FindingCandidate]:
    entity_by_value = {entity.value.lower(): entity for entity in entities}
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

    return _dedupe_candidates(candidates)


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
            )
    return None


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
        return existing

    finding = Finding(
        investigation_id=investigation_id,
        title=candidate.title,
        description=candidate.description,
        severity=candidate.severity,
        confidence_score=candidate.confidence_score,
        risk_score=candidate.risk_score,
        source=candidate.source,
        status="open",
        created_by=user.id if user is not None else None,
        raw_data={},
        normalized_data={
            "tags": candidate.tags,
            "evidence_count": len(candidate.evidence),
        },
    )
    db.add(finding)
    await db.flush()
    for evidence in candidate.evidence:
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
    for tag in candidate.tags:
        db.add(FindingTag(finding_id=finding.id, tag=tag))
    await db.flush()
    await db.refresh(finding)
    return finding


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
