from __future__ import annotations

import uuid

from app.models.investigation_enrichment import InvestigationEnrichment
from app.models.recon_entity import ReconEntity
from app.models.threat_finding import ThreatFinding
from app.services.intelligence.correlation_service import build_finding_candidates
from tests.conftest import VALID_AUTH_STATEMENT


def test_build_finding_candidates_from_recon_and_threat_signals() -> None:
    investigation_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    entity = ReconEntity(
        id=entity_id,
        investigation_id=investigation_id,
        entity_type="Domain",
        value="example.com",
        properties={},
        source="dns",
    )
    threat_finding = ThreatFinding(
        investigation_id=investigation_id,
        recon_entity_id=entity_id,
        target_type="domain",
        target_value="example.com",
        provider="virustotal",
        status="completed",
        risk_score=80,
        confidence="high",
        verdict="high",
        signals=["malicious:4"],
        normalized_data={"malicious": 4},
        raw_data={},
    )
    enrichment = InvestigationEnrichment(
        investigation_id=investigation_id,
        target_type="domain",
        target_value="example.com",
        authorization_statement=VALID_AUTH_STATEMENT,
        status="completed",
        summary={},
        result={
            "target_type": "domain",
            "target_value": "example.com",
            "dns": {"spf_records": ["v=spf1 +all"]},
            "http": {
                "server": "Apache/2.4.49",
                "headers": {"x-powered-by": "Express"},
                "certificate": {"not_after": "2020-01-01T00:00:00Z"},
            },
        },
    )

    candidates = build_finding_candidates(
        enrichments=[enrichment],
        threat_findings=[threat_finding],
        entities=[entity],
    )

    titles = {candidate.title: candidate for candidate in candidates}
    assert titles["Expired TLS certificate for example.com"].severity == "medium"
    assert titles["Malicious VirusTotal reputation for example.com"].severity == "high"
    assert titles["Risky server disclosure for example.com"].severity == "low"
    assert titles["Exposed internal metadata for example.com"].severity == "medium"
    assert titles["Suspicious SPF policy for example.com"].severity == "low"


def test_build_finding_candidates_continues_after_malformed_enrichment() -> None:
    investigation_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    entity = ReconEntity(
        id=entity_id,
        investigation_id=investigation_id,
        entity_type="IPAddress",
        value="8.8.8.8",
        properties={},
        source="threat-intel",
    )
    threat_finding = ThreatFinding(
        investigation_id=investigation_id,
        recon_entity_id=entity_id,
        target_type="ip",
        target_value="8.8.8.8",
        provider="abuseipdb",
        status="completed",
        risk_score=75,
        confidence="high",
        verdict="high",
        signals=["abuse_confidence_score:75"],
        normalized_data={"abuse_confidence_score": 75},
        raw_data={},
    )
    malformed = InvestigationEnrichment(
        investigation_id=investigation_id,
        target_type="domain",
        target_value="broken.example",
        authorization_statement=VALID_AUTH_STATEMENT,
        status="completed",
        summary={},
        result={"http": "not-a-dict", "dns": None},
    )

    candidates = build_finding_candidates(
        enrichments=[malformed],
        threat_findings=[threat_finding],
        entities=[entity],
    )

    assert [candidate.title for candidate in candidates] == [
        "High AbuseIPDB reputation for 8.8.8.8"
    ]
