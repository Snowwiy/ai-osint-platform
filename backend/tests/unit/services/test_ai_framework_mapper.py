from __future__ import annotations

from app.services.ai.evidence_builder import EvidenceItem
from app.services.ai.framework_mapper import map_frameworks


def test_framework_mapper_maps_reputation_headers_and_tls() -> None:
    evidence = [
        EvidenceItem(
            id="finding:vt",
            source_type="finding",
            title="Malicious VirusTotal reputation for example.com",
            summary="Reputation evidence is high risk.",
        ),
        EvidenceItem(
            id="finding:http",
            source_type="finding",
            title="Risky server disclosure",
            summary="Server header discloses Apache/2.4.49.",
        ),
        EvidenceItem(
            id="finding:tls",
            source_type="finding",
            title="Expired TLS certificate",
            summary="TLS certificate expired.",
        ),
    ]

    mappings = map_frameworks(evidence, [])

    frameworks = {mapping.framework for mapping in mappings}
    assert "MITRE ATT&CK" in frameworks
    assert "OWASP" in frameworks
    assert "NIST 800-53" in frameworks
    assert all(mapping.citation_ids for mapping in mappings)
