from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.finding import Finding
from app.models.recon_entity import ReconEntity
from app.models.recon_relationship import ReconRelationship
from app.models.report import Report
from app.models.threat_finding import ThreatFinding
from app.services.correlation.service import CorrelationDataset, _CorrelationBuilder


def test_correlation_service_detects_shared_ip_and_provider_overlap() -> None:
    domain_one, domain_two, ip_address = _shared_ip_entities()
    dataset = CorrelationDataset(
        entities=[domain_one, domain_two, ip_address],
        relationships=[
            _relationship(domain_one.id, ip_address.id, "RESOLVES_TO"),
            _relationship(domain_two.id, ip_address.id, "RESOLVES_TO"),
        ],
        threat_findings=[
            _threat_finding(domain_one.id, "example.com", "virustotal"),
            _threat_finding(ip_address.id, "93.184.216.34", "virustotal"),
        ],
        findings=[],
        finding_evidence=[],
        reports=[],
    )

    response = _CorrelationBuilder(dataset).build(uuid.uuid4())

    edge_types = {edge.correlation_type for edge in response.edges}
    assert "shared_ip" in edge_types
    assert "provider_overlap" in edge_types
    assert response.total_nodes >= 4


def test_correlation_service_detects_recurring_findings_and_knowledge() -> None:
    finding_one = _finding("Risky server disclosure")
    finding_two = _finding("Risky server disclosure")
    report = Report(
        id=uuid.uuid4(),
        investigation_id=uuid.uuid4(),
        generated_by=None,
        title="Technical Report",
        report_type="technical",
        report_format="html",
        status="ready",
        markdown_content="- [knowledge:local-cis] CIS hardening guidance\n",
        html_content="<html></html>",
        report_metadata={"knowledge_citation_count": 1},
        created_at=datetime(2026, 5, 28, tzinfo=UTC),
    )
    dataset = CorrelationDataset(
        entities=[],
        relationships=[],
        threat_findings=[],
        findings=[finding_one, finding_two],
        finding_evidence=[],
        reports=[report],
    )

    response = _CorrelationBuilder(dataset).build(uuid.uuid4())

    edge_types = {edge.correlation_type for edge in response.edges}
    assert "recurring_finding" in edge_types
    assert "related_knowledge_citation" in edge_types


def _shared_ip_entities() -> tuple[ReconEntity, ReconEntity, ReconEntity]:
    investigation_id = uuid.uuid4()
    domain_one = ReconEntity(
        id=uuid.uuid4(),
        investigation_id=investigation_id,
        entity_type="Subdomain",
        value="app.example.com",
        properties={},
        source="dns",
    )
    domain_two = ReconEntity(
        id=uuid.uuid4(),
        investigation_id=investigation_id,
        entity_type="Subdomain",
        value="api.example.com",
        properties={},
        source="dns",
    )
    ip_address = ReconEntity(
        id=uuid.uuid4(),
        investigation_id=investigation_id,
        entity_type="IPAddress",
        value="93.184.216.34",
        properties={},
        source="dns",
    )
    return domain_one, domain_two, ip_address


def _relationship(
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    relationship_type: str,
) -> ReconRelationship:
    return ReconRelationship(
        id=uuid.uuid4(),
        investigation_id=uuid.uuid4(),
        source_entity_id=source_id,
        target_entity_id=target_id,
        relationship_type=relationship_type,
        source="dns",
        properties={},
        created_at=datetime(2026, 5, 28, tzinfo=UTC),
    )


def _threat_finding(
    entity_id: uuid.UUID,
    target_value: str,
    provider: str,
) -> ThreatFinding:
    return ThreatFinding(
        id=uuid.uuid4(),
        investigation_id=uuid.uuid4(),
        recon_entity_id=entity_id,
        target_type="domain",
        target_value=target_value,
        provider=provider,
        status="completed",
        risk_score=20,
        confidence="medium",
        verdict="low",
        signals=[],
        normalized_data={},
        raw_data={},
        collected_at=datetime(2026, 5, 28, tzinfo=UTC),
    )


def _finding(title: str) -> Finding:
    return Finding(
        id=uuid.uuid4(),
        investigation_id=uuid.uuid4(),
        title=title,
        description="The HTTP Server header discloses technology details.",
        severity="low",
        confidence_score=70,
        risk_score=20,
        source="http",
        raw_data={},
        normalized_data={},
        status="open",
        created_at=datetime(2026, 5, 28, tzinfo=UTC),
        updated_at=datetime(2026, 5, 28, tzinfo=UTC),
    )
