from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import TypeVar, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding import Finding
from app.models.recon_entity import ReconEntity
from app.models.user import User
from app.schemas.defensive_intelligence import (
    CoverageLevel,
    DetectionKnowledgeCard,
    DetectionKnowledgeResponse,
    FindingCoverageItem,
    FindingDetectionRecommendation,
    FrameworkKnowledgeCard,
    FrameworkKnowledgeResponse,
    InvestigationCoverageResponse,
    InvestigationRecommendationsResponse,
    MitreDefensiveMapping,
    SigmaDetectionReference,
    YaraDefensiveReference,
)
from app.schemas.finding import FindingSeverity
from app.services.investigation import get_investigation

_UNRESOLVED_STATUSES = {"new", "under_review", "accepted_risk", "open"}

_MITRE_CATALOG = {
    "remote_access": MitreDefensiveMapping(
        technique_id="T1133",
        name="External Remote Services",
        tactic="Persistence, Initial Access",
        defensive_explanation=(
            "Monitor approved remote-access services for unusual authentication, "
            "new source networks, and access outside expected operating periods."
        ),
        why_mapping_exists=(
            "The stored finding references an externally reachable management or "
            "remote-access service. This is exposure context, not evidence that the "
            "technique occurred."
        ),
        references=["MITRE ATT&CK T1133", "CIS Controls 6 and 13"],
    ),
    "brute_force": MitreDefensiveMapping(
        technique_id="T1110",
        name="Brute Force",
        tactic="Credential Access",
        defensive_explanation=(
            "Correlate repeated authentication failures, account lockouts, and "
            "successful logons that follow concentrated failure activity."
        ),
        why_mapping_exists=(
            "The finding concerns authentication exposure or repeated reputation "
            "signals where credential-abuse monitoring is defensively relevant."
        ),
        references=["MITRE ATT&CK T1110", "NIST CSF DE.CM"],
    ),
    "public_application": MitreDefensiveMapping(
        technique_id="T1190",
        name="Exploit Public-Facing Application",
        tactic="Initial Access",
        defensive_explanation=(
            "Maintain application, reverse-proxy, authentication, and change logs "
            "for externally reachable services and review anomalous access patterns."
        ),
        why_mapping_exists=(
            "A public-facing service or technology disclosure was observed. The "
            "mapping supports monitoring priorities and does not assert exploitation."
        ),
        references=["MITRE ATT&CK T1190", "OWASP Top 10 A05"],
    ),
    "phishing": MitreDefensiveMapping(
        technique_id="T1566",
        name="Phishing",
        tactic="Initial Access",
        defensive_explanation=(
            "Monitor mail authentication failures, spoofing reports, and anomalous "
            "sender alignment while validating SPF, DKIM, and DMARC configuration."
        ),
        why_mapping_exists=(
            "The finding concerns email-domain authentication controls that reduce "
            "spoofing exposure. It does not establish that phishing occurred."
        ),
        references=["MITRE ATT&CK T1566", "CIS Controls 9"],
    ),
    "dns_channel": MitreDefensiveMapping(
        technique_id="T1071.004",
        name="Application Layer Protocol: DNS",
        tactic="Command and Control",
        defensive_explanation=(
            "Review resolver telemetry for unusual query volume, rare domains, long "
            "labels, and unexpected record types using organization-approved rules."
        ),
        why_mapping_exists=(
            "The stored evidence includes suspicious DNS patterns where resolver "
            "visibility is useful. This is a monitoring hypothesis, not a C2 claim."
        ),
        references=["MITRE ATT&CK T1071.004", "NIST CSF DE.CM"],
    ),
}

_SIGMA_CATALOG = {
    "windows_logon": SigmaDetectionReference(
        id="sigma:windows-authentication-monitoring",
        title="Repeated Windows Authentication Failures",
        description=(
            "Reference pattern for repeated failed logons followed by account "
            "lockout or a successful remote logon."
        ),
        log_source="Windows Security",
        tags=["attack.t1110", "authentication", "remote-access"],
        detection_idea=(
            "Correlate Event IDs 4625 and 4740 by account and source, then review "
            "Event IDs 4624 and 1149 for a subsequent successful remote session."
        ),
        defensive_explanation=(
            "Use this as analyst guidance for authentication telemetry review. Tune "
            "thresholds to approved remote-access patterns before operational use."
        ),
        references=["Sigma rule specification", "Windows Security audit events"],
    ),
    "web_access": SigmaDetectionReference(
        id="sigma:public-service-access-monitoring",
        title="Unusual Access to Public Management Services",
        description=(
            "Reference pattern for unusual requests or authentication activity "
            "against externally reachable management interfaces."
        ),
        log_source="Web server, reverse proxy, or identity provider",
        tags=["attack.t1190", "web", "management-service"],
        detection_idea=(
            "Monitor new source networks, repeated denials, unexpected methods, "
            "unusual user agents, and successful access outside approved periods."
        ),
        defensive_explanation=(
            "The reference describes monitoring coverage only and must be adapted "
            "to the organization's authorized service inventory."
        ),
        references=["Sigma rule specification", "OWASP logging guidance"],
    ),
    "dns_monitoring": SigmaDetectionReference(
        id="sigma:dns-anomaly-monitoring",
        title="Unusual DNS Query Pattern",
        description=(
            "Reference pattern for high-volume, rare, or unusually encoded DNS "
            "queries in resolver telemetry."
        ),
        log_source="DNS resolver",
        tags=["attack.t1071.004", "dns", "network"],
        detection_idea=(
            "Baseline query length, record types, NXDOMAIN rates, and newly observed "
            "domains, then review meaningful deviations with asset context."
        ),
        defensive_explanation=(
            "Use passive resolver logs and organization-approved thresholds. A match "
            "requires analyst validation and is not a compromise statement."
        ),
        references=["Sigma DNS logsource guidance", "MITRE ATT&CK T1071.004"],
    ),
    "tls_monitoring": SigmaDetectionReference(
        id="sigma:certificate-health-monitoring",
        title="Certificate Health and Expiration Monitoring",
        description=(
            "Reference pattern for expired, unexpectedly replaced, or weakly "
            "configured certificates observed by approved monitoring."
        ),
        log_source="TLS inventory or certificate monitoring",
        tags=["tls", "certificate", "configuration"],
        detection_idea=(
            "Alert on expiration windows, unexpected issuers, SAN drift, and "
            "protocol-policy violations using approved certificate inventory."
        ),
        defensive_explanation=(
            "This reference supports configuration assurance and service continuity; "
            "it does not imply malicious activity."
        ),
        references=["NIST 800-53 SC family", "CIS secure configuration guidance"],
    ),
}

_YARA_CATALOG = {
    "artifact_triage": YaraDefensiveReference(
        id="yara:defensive-artifact-triage",
        title="Defensive Artifact Classification",
        family="Generic security artifact",
        category="DFIR triage",
        why_it_matters=(
            "File or artifact evidence may require repeatable classification before "
            "an analyst decides whether deeper review is warranted."
        ),
        defensive_detection_context=(
            "Use organization-approved YARA rules only against authorized evidence "
            "collections in a controlled analysis environment."
        ),
        analyst_explanation=(
            "This reference provides context only. It contains no sample, payload, "
            "rule body, or execution workflow."
        ),
        references=["YARA documentation", "Internal DFIR handling procedure"],
    )
}

_FRAMEWORK_CATALOG: tuple[FrameworkKnowledgeCard, ...] = (
    FrameworkKnowledgeCard(
        framework="MITRE ATT&CK",
        description=(
            "A behavior-oriented knowledge base used here to explain defensive "
            "monitoring relevance without asserting observed adversary activity."
        ),
        defensive_use="Map evidence-backed findings to monitoring hypotheses.",
        common_categories=["Exposure", "Authentication", "DNS monitoring"],
        references=["MITRE ATT&CK Enterprise"],
    ),
    FrameworkKnowledgeCard(
        framework="NIST CSF",
        description="Risk and control outcomes for defensive governance.",
        defensive_use="Track identify, protect, detect, respond, and recover outcomes.",
        common_categories=["Continuous monitoring", "Incident response"],
        references=["NIST Cybersecurity Framework"],
    ),
    FrameworkKnowledgeCard(
        framework="NIST 800-53",
        description="Security and privacy control families for system assurance.",
        defensive_use="Relate TLS, logging, access, and monitoring gaps to controls.",
        common_categories=["AU", "AC", "SC", "SI"],
        references=["NIST SP 800-53"],
    ),
    FrameworkKnowledgeCard(
        framework="CIS Controls",
        description="Prioritized defensive safeguards for enterprise environments.",
        defensive_use="Guide hardening, logging, access control, and remediation.",
        common_categories=["Secure configuration", "Account management", "Logging"],
        references=["CIS Critical Security Controls"],
    ),
    FrameworkKnowledgeCard(
        framework="OWASP Top 10",
        description="Application security risk categories and defensive guidance.",
        defensive_use="Explain public-service configuration and logging concerns.",
        common_categories=["Security misconfiguration", "Access control"],
        references=["OWASP Top 10"],
    ),
    FrameworkKnowledgeCard(
        framework="Sigma",
        description="Portable detection-rule references for log-based monitoring.",
        defensive_use="Describe detection ideas and required telemetry without execution.",
        common_categories=["Authentication", "DNS", "Web access"],
        references=["Sigma rule specification"],
    ),
    FrameworkKnowledgeCard(
        framework="YARA",
        description="Pattern-based artifact classification references.",
        defensive_use="Support controlled, authorized DFIR evidence classification.",
        common_categories=["Artifact triage", "DFIR"],
        references=["YARA documentation"],
    ),
    FrameworkKnowledgeCard(
        framework="DFIR",
        description=(
            "Evidence preservation, timeline reconstruction, and defensible "
            "investigation review."
        ),
        defensive_use=(
            "Maintain provenance, analyst decisions, and an auditable evidence chain."
        ),
        common_categories=["Evidence handling", "Timeline analysis", "Incident review"],
        references=["Internal DFIR handling guidance"],
    ),
    FrameworkKnowledgeCard(
        framework="Threat Intelligence",
        description=(
            "Evidence-backed context for indicators, recurring infrastructure, "
            "and confidence."
        ),
        defensive_use=(
            "Separate observed facts from analytical judgments and prioritize review."
        ),
        common_categories=["IOC context", "Infrastructure", "Confidence"],
        references=["Internal threat intelligence guidance"],
    ),
    FrameworkKnowledgeCard(
        framework="Secure Architecture",
        description=(
            "Defensive design guidance for trust boundaries, dependencies, and "
            "externally visible services."
        ),
        defensive_use=(
            "Relate exposure findings to least privilege, defense in depth, and "
            "secure defaults."
        ),
        common_categories=["Trust boundaries", "Service exposure", "Dependencies"],
        references=["Secure architecture review guidance"],
    ),
    FrameworkKnowledgeCard(
        framework="Cloud Security",
        description=(
            "Defensive assurance for cloud-hosted assets, identity, telemetry, "
            "and shared responsibility."
        ),
        defensive_use=(
            "Review cloud exposure, logging, encryption, ownership, and provider "
            "responsibilities."
        ),
        common_categories=["Cloud identity", "Telemetry", "Shared responsibility"],
        references=["Cloud security review guidance"],
    ),
)


async def get_investigation_recommendations(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> InvestigationRecommendationsResponse:
    await get_investigation(db, user, investigation_id)
    findings, entities = await _load_data(db, investigation_id)
    recommendations = build_detection_recommendations(findings, entities)
    return InvestigationRecommendationsResponse(
        investigation_id=investigation_id,
        generated_at=_now(),
        total_findings=len(findings),
        recommendations=recommendations,
        recommended_next_steps=_next_steps(recommendations, findings),
    )


async def get_investigation_coverage(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> InvestigationCoverageResponse:
    await get_investigation(db, user, investigation_id)
    findings, entities = await _load_data(db, investigation_id)
    recommendations = build_detection_recommendations(findings, entities)
    return build_coverage_response(
        investigation_id,
        findings,
        recommendations,
    )


def build_detection_recommendations(
    findings: list[Finding],
    entities: list[ReconEntity],
) -> list[FindingDetectionRecommendation]:
    entity_text = " ".join(
        f"{entity.entity_type} {entity.value} {entity.properties}"
        for entity in entities
    ).lower()
    return [
        _recommendation_for_finding(finding, entity_text)
        for finding in findings
        if finding.status != "archived"
    ]


def build_coverage_response(
    investigation_id: uuid.UUID,
    findings: list[Finding],
    recommendations: list[FindingDetectionRecommendation],
) -> InvestigationCoverageResponse:
    recommendation_by_id = {item.finding_id: item for item in recommendations}
    items: list[FindingCoverageItem] = []
    framework_counts: Counter[str] = Counter()
    all_missing: list[str] = []
    mapped = 0
    guidance = 0
    for finding in findings:
        recommendation = recommendation_by_id.get(finding.id)
        frameworks = _finding_frameworks(finding)
        if recommendation is not None:
            frameworks.extend(
                mapping.technique_id for mapping in recommendation.mitre_mappings
            )
        frameworks = _dedupe(frameworks)
        missing = (
            _missing_visibility(finding, recommendation)
            if recommendation is not None
            else ["No deterministic monitoring guidance matched this finding."]
        )
        is_mapped = bool(frameworks)
        has_guidance = bool(
            recommendation
            and (
                recommendation.monitoring_recommendations
                or recommendation.sigma_references
            )
        )
        mapped += int(is_mapped)
        guidance += int(has_guidance)
        framework_counts.update(frameworks)
        all_missing.extend(missing)
        items.append(
            FindingCoverageItem(
                finding_id=finding.id,
                title=finding.title,
                mapped=is_mapped,
                guidance_available=has_guidance,
                frameworks=frameworks,
                missing_visibility=missing,
            )
        )
    total = len(findings)
    coverage_percent = (
        round((((mapped / total) * 0.6) + ((guidance / total) * 0.4)) * 100)
        if total
        else 0
    )
    return InvestigationCoverageResponse(
        investigation_id=investigation_id,
        generated_at=_now(),
        total_findings=total,
        mapped_findings=mapped,
        detection_guidance_available=guidance,
        missing_coverage=max(0, total - guidance),
        coverage_percent=coverage_percent,
        category=_coverage_category(coverage_percent),
        framework_counts=dict(framework_counts.most_common()),
        missing_defensive_visibility=_dedupe(all_missing)[:12],
        monitoring_recommendations=_dedupe(
            [
                item
                for recommendation in recommendations
                for item in recommendation.monitoring_recommendations
            ]
        )[:12],
        findings=items,
    )


def list_detection_knowledge(
    *,
    kind: str | None = None,
    query: str | None = None,
) -> DetectionKnowledgeResponse:
    cards = [
        *[
            _sigma_card(item)
            for item in _SIGMA_CATALOG.values()
        ],
        *[
            _yara_card(item)
            for item in _YARA_CATALOG.values()
        ],
    ]
    if kind:
        cards = [item for item in cards if item.kind == kind.lower()]
    if query and query.strip():
        tokens = query.lower().split()
        cards = [
            item
            for item in cards
            if all(
                token
                in " ".join(
                    [
                        item.title,
                        item.description,
                        item.category,
                        item.detection_idea,
                        " ".join(item.tags),
                    ]
                ).lower()
                for token in tokens
            )
        ]
    return DetectionKnowledgeResponse(total=len(cards), items=cards)


def list_framework_knowledge(
    framework: str | None = None,
) -> FrameworkKnowledgeResponse:
    items = list(_FRAMEWORK_CATALOG)
    if framework and framework.strip():
        clean = framework.strip().lower()
        items = [item for item in items if item.framework.lower() == clean]
    return FrameworkKnowledgeResponse(total=len(items), items=items)


def _recommendation_for_finding(
    finding: Finding,
    entity_text: str,
) -> FindingDetectionRecommendation:
    text = _finding_text(finding)
    mitre: list[MitreDefensiveMapping] = []
    sigma: list[SigmaDetectionReference] = []
    yara: list[YaraDefensiveReference] = []
    monitoring: list[str] = []
    logging: list[str] = []

    if _has_any(text, ("rdp", "3389", "remote desktop", "remote service")):
        mitre.extend(
            [_MITRE_CATALOG["remote_access"], _MITRE_CATALOG["brute_force"]]
        )
        sigma.append(_SIGMA_CATALOG["windows_logon"])
        monitoring.extend(
            [
                "Review successful and failed remote logons by account and source.",
                "Alert on access from new networks or outside approved time windows.",
            ]
        )
        logging.extend(
            [
                "Collect Windows Event IDs 4624, 4625, 4740, and RDP Event ID 1149.",
                "Preserve VPN, identity-provider, and remote-access gateway logs.",
            ]
        )
    elif _has_any(
        text,
        ("service", "exposure", "public-facing", "http", "server header"),
    ):
        mitre.append(_MITRE_CATALOG["public_application"])
        sigma.append(_SIGMA_CATALOG["web_access"])
        monitoring.extend(
            [
                "Baseline approved public services and review unexpected exposure.",
                "Monitor access denials, authentication events, and anomalous methods.",
            ]
        )
        logging.extend(
            [
                "Retain reverse-proxy, web-server, identity, and configuration logs.",
                "Record service owner, approved purpose, and expected source networks.",
            ]
        )

    if _has_any(text, ("spf", "dmarc", "dkim", "mail authentication")):
        mitre.append(_MITRE_CATALOG["phishing"])
        monitoring.extend(
            [
                "Review DMARC aggregate reports and sender-alignment failures.",
                "Track unauthorized changes to SPF, DKIM, and DMARC records.",
            ]
        )
        logging.append(
            "Retain authoritative DNS changes and mail-gateway authentication results."
        )
    elif _has_any(text, ("dns", "txt", "resolver", "subdomain")):
        if _has_any(text, ("suspicious", "encoded", "unusual", "recurring")):
            mitre.append(_MITRE_CATALOG["dns_channel"])
        sigma.append(_SIGMA_CATALOG["dns_monitoring"])
        monitoring.extend(
            [
                "Baseline DNS query volume, rare domains, and record-type usage.",
                "Review newly observed subdomains against approved asset inventory.",
            ]
        )
        logging.append(
            "Collect resolver query logs and authoritative DNS change history."
        )

    if _has_any(text, ("tls", "certificate", "expired", "issuer", "san")):
        sigma.append(_SIGMA_CATALOG["tls_monitoring"])
        monitoring.extend(
            [
                "Monitor expiration windows, issuer changes, and SAN coverage drift.",
                "Validate TLS protocol and cipher policy against approved baselines.",
            ]
        )
        logging.append(
            "Maintain certificate inventory with owner, issuer, SANs, and expiry."
        )

    if _has_any(text, ("artifact", "file hash", "file evidence")):
        yara.append(_YARA_CATALOG["artifact_triage"])

    if not monitoring:
        monitoring.extend(
            [
                "Confirm the affected asset owner and expected configuration.",
                "Define a measurable monitoring signal before closing the finding.",
            ]
        )
    if not logging:
        logging.append(
            "Preserve the telemetry required to validate this finding over time."
        )

    references = _dedupe(
        [
            *finding.evidence_urls,
            *_finding_references(finding),
            *[
                reference
                for mapping in mitre
                for reference in mapping.references
            ],
            *[
                reference
                for item in sigma
                for reference in item.references
            ],
        ]
    )
    remediation = _string_list(
        finding.normalized_data.get("remediation_guidance")
    )
    if not remediation:
        remediation = [
            "Validate the observed configuration with the authorized asset owner.",
            "Document remediation ownership, due date, and verification evidence.",
        ]
    return FindingDetectionRecommendation(
        finding_id=finding.id,
        finding_title=finding.title,
        severity=cast(FindingSeverity, finding.severity),
        why_this_matters=_why_this_matters(finding, entity_text),
        monitoring_recommendations=_dedupe(monitoring),
        logging_recommendations=_dedupe(logging),
        remediation_guidance=_dedupe(remediation),
        mitre_mappings=_dedupe_models(mitre),
        sigma_references=_dedupe_models(sigma),
        yara_references=_dedupe_models(yara),
        references=references,
    )


def _why_this_matters(finding: Finding, entity_text: str) -> str:
    if _has_any(_finding_text(finding), ("rdp", "3389", "remote")):
        return (
            "Externally reachable remote access increases authentication-monitoring "
            "and access-control requirements."
        )
    if finding.source == "dns":
        return (
            "DNS configuration influences service discovery, email trust, and the "
            "quality of resolver-based defensive visibility."
        )
    if finding.source in {"tls", "certificate"}:
        return (
            "Certificate health affects service trust, continuity, and configuration "
            "assurance."
        )
    if "Service" in entity_text:
        return (
            "Observed services require ownership, exposure justification, and "
            "appropriate telemetry."
        )
    return (
        "This evidence-backed finding should have explicit monitoring, ownership, "
        "and validation criteria."
    )


def _missing_visibility(
    finding: Finding,
    recommendation: FindingDetectionRecommendation,
) -> list[str]:
    text = _finding_text(finding)
    missing: list[str] = []
    if _has_any(text, ("rdp", "3389", "remote", "authentication")):
        missing.append(
            "Confirm centralized authentication and remote-access telemetry coverage."
        )
    if _has_any(text, ("dns", "spf", "dmarc", "dkim", "subdomain")):
        missing.append("Confirm resolver and authoritative DNS change visibility.")
    if _has_any(text, ("tls", "certificate", "expired")):
        missing.append("Confirm certificate inventory and expiration alerting.")
    if _has_any(text, ("http", "service", "server", "technology")):
        missing.append("Confirm web, proxy, and service authentication log coverage.")
    if not recommendation.sigma_references:
        missing.append("No Sigma monitoring reference matched this evidence.")
    return _dedupe(missing)


def _finding_text(finding: Finding) -> str:
    return " ".join(
        [
            finding.title,
            finding.description,
            finding.source,
            str(finding.raw_data),
            str(finding.normalized_data),
        ]
    ).lower()


def _finding_frameworks(finding: Finding) -> list[str]:
    raw = finding.normalized_data.get("framework_mappings")
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            framework = item.get("framework")
            control = item.get("control")
            if isinstance(framework, str):
                values.append(
                    f"{framework}: {control}" if isinstance(control, str) else framework
                )
    return _dedupe(values)


def _finding_references(finding: Finding) -> list[str]:
    return _string_list(finding.normalized_data.get("references"))


def _next_steps(
    recommendations: list[FindingDetectionRecommendation],
    findings: list[Finding],
) -> list[str]:
    steps: list[str] = []
    unresolved = [
        item for item in findings if item.status in _UNRESOLVED_STATUSES
    ]
    if any(
        mapping.technique_id == "T1133"
        for item in recommendations
        for mapping in item.mitre_mappings
    ):
        steps.append(
            "Prioritize review of exposed management services and authentication "
            "telemetry."
        )
    if any(
        item.sigma_references for item in recommendations
    ):
        steps.append(
            "Validate Sigma references against available log sources and approved "
            "operational baselines."
        )
    if any("DNS" in item.why_this_matters for item in recommendations):
        steps.append("Validate DNS security posture and resolver visibility.")
    if unresolved:
        steps.append(
            f"Assign analyst review and monitoring ownership for {len(unresolved)} "
            "unresolved findings."
        )
    steps.append(
        "Record monitoring gaps and remediation verification evidence before closure."
    )
    return _dedupe(steps)[:8]


def _sigma_card(item: SigmaDetectionReference) -> DetectionKnowledgeCard:
    return DetectionKnowledgeCard(
        id=item.id,
        kind="sigma",
        title=item.title,
        description=item.description,
        category="Detection Engineering",
        framework="Sigma",
        log_source=item.log_source,
        tags=item.tags,
        detection_idea=item.detection_idea,
        why_this_matters=item.defensive_explanation,
        remediation_guidance=[
            "Validate telemetry availability and false-positive conditions.",
            "Assign analyst ownership before operational adoption.",
        ],
        references=item.references,
    )


def _yara_card(item: YaraDefensiveReference) -> DetectionKnowledgeCard:
    return DetectionKnowledgeCard(
        id=item.id,
        kind="yara",
        title=item.title,
        description=item.defensive_detection_context,
        category=item.category,
        framework="YARA",
        tags=["yara", "dfir", "artifact-classification"],
        detection_idea=item.analyst_explanation,
        why_this_matters=item.why_it_matters,
        remediation_guidance=[
            "Use only approved rules in an authorized evidence-handling process.",
            "Record analyst validation and evidence provenance.",
        ],
        references=item.references,
    )


def _coverage_category(score: int) -> CoverageLevel:
    if score >= 80:
        return "strong"
    if score >= 60:
        return "moderate"
    if score >= 30:
        return "partial"
    return "weak"


async def _load_data(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> tuple[list[Finding], list[ReconEntity]]:
    finding_result = await db.execute(
        select(Finding).where(Finding.investigation_id == investigation_id)
    )
    entity_result = await db.execute(
        select(ReconEntity).where(ReconEntity.investigation_id == investigation_id)
    )
    return (
        list(finding_result.scalars().all()),
        list(entity_result.scalars().all()),
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _has_any(value: str, needles: tuple[str, ...]) -> bool:
    return any(needle in value for needle in needles)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in values if item.strip()))


_ModelT = TypeVar("_ModelT")


def _dedupe_models(values: list[_ModelT]) -> list[_ModelT]:
    deduped: dict[str, _ModelT] = {}
    for item in values:
        key = getattr(item, "id", None) or getattr(item, "technique_id", repr(item))
        deduped.setdefault(str(key), item)
    return list(deduped.values())


def _now() -> datetime:
    return datetime.now(UTC)
