from __future__ import annotations

from app.schemas.analysis import AnalysisFrameworkMapping
from app.services.ai.evidence_builder import EvidenceItem


def map_frameworks(
    evidence_items: list[EvidenceItem],
    knowledge_items: list[EvidenceItem],
) -> list[AnalysisFrameworkMapping]:
    mappings: list[AnalysisFrameworkMapping] = []
    combined = [*evidence_items, *knowledge_items]
    for item in combined:
        text = f"{item.title} {item.summary}".lower()
        if _has_any(text, ("virustotal", "abuseipdb", "malicious", "reputation")):
            mappings.extend(
                [
                    AnalysisFrameworkMapping(
                        framework="MITRE ATT&CK",
                        control="Reconnaissance / Resource Development context",
                        rationale=(
                            "Reputation evidence can support defensive context for "
                            "observed infrastructure and indicators."
                        ),
                        citation_ids=[item.id],
                    ),
                    AnalysisFrameworkMapping(
                        framework="NIST CSF",
                        control="DE.CM - Security Continuous Monitoring",
                        rationale=(
                            "Threat reputation signals are monitoring evidence that "
                            "should be validated and tracked."
                        ),
                        citation_ids=[item.id],
                    ),
                ]
            )
        if _has_any(text, ("server header", "x-powered-by", "metadata", "disclosure")):
            mappings.extend(
                [
                    AnalysisFrameworkMapping(
                        framework="OWASP",
                        control="Security Misconfiguration",
                        rationale=(
                            "HTTP disclosure evidence aligns with common "
                            "misconfiguration review and hardening guidance."
                        ),
                        citation_ids=[item.id],
                    ),
                    AnalysisFrameworkMapping(
                        framework="CIS Controls",
                        control="Secure Configuration of Enterprise Assets and Software",
                        rationale=(
                            "Technology disclosure should be reviewed as part of "
                            "secure configuration management."
                        ),
                        citation_ids=[item.id],
                    ),
                ]
            )
        if _has_any(text, ("tls", "certificate", "expired", "san")):
            mappings.extend(
                [
                    AnalysisFrameworkMapping(
                        framework="NIST 800-53",
                        control="SC - System and Communications Protection",
                        rationale=(
                            "TLS and certificate evidence supports review of "
                            "communications protection controls."
                        ),
                        citation_ids=[item.id],
                    ),
                    AnalysisFrameworkMapping(
                        framework="ISO 27001",
                        control="Cryptography and communications security",
                        rationale=(
                            "Certificate health is relevant to cryptographic "
                            "control operation and monitoring."
                        ),
                        citation_ids=[item.id],
                    ),
                ]
            )
        if _has_any(text, ("spf", "dmarc", "dkim", "dns", "txt")):
            mappings.append(
                AnalysisFrameworkMapping(
                    framework="CIS Controls",
                    control="Email and Web Browser Protections",
                    rationale=(
                        "DNS mail-authentication evidence supports review of "
                        "email-domain protection controls."
                    ),
                    citation_ids=[item.id],
                )
            )
        if item.source_type == "knowledge_document" and _has_any(
            text,
            ("mitre", "owasp", "nist", "iso 27001", "cis controls"),
        ):
            mappings.append(
                AnalysisFrameworkMapping(
                    framework="Knowledge Base",
                    control=item.title,
                    rationale=(
                        "Indexed framework or playbook material was retrieved as "
                        "supporting context."
                    ),
                    citation_ids=[item.id],
                )
            )
    return _dedupe_mappings(mappings)


def _has_any(value: str, needles: tuple[str, ...]) -> bool:
    return any(needle in value for needle in needles)


def _dedupe_mappings(
    mappings: list[AnalysisFrameworkMapping],
) -> list[AnalysisFrameworkMapping]:
    deduped: dict[tuple[str, str, tuple[str, ...]], AnalysisFrameworkMapping] = {}
    for mapping in mappings:
        key = (mapping.framework, mapping.control, tuple(mapping.citation_ids))
        deduped.setdefault(key, mapping)
    return list(deduped.values())[:12]
