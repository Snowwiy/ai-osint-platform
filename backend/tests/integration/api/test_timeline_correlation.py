from __future__ import annotations

from app.core.security import create_access_token
from app.models.ai_analysis import AiAnalysis
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.investigation_enrichment import InvestigationEnrichment
from app.models.recon_entity import ReconEntity
from app.models.recon_relationship import ReconRelationship
from app.models.report import Report
from app.models.target import Target
from app.models.threat_finding import ThreatFinding
from app.schemas.correlation import CorrelationResponse
from app.schemas.timeline import TimelineResponse
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import VALID_AUTH_STATEMENT


async def test_timeline_requires_auth(
    client: AsyncClient,
    test_investigation,
) -> None:
    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/timeline"
    )

    assert response.status_code == 401


async def test_timeline_non_member_gets_404(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    admin_user,
) -> None:
    investigation = Investigation(
        title="Private Timeline",
        owner_id=admin_user.id,
        authorization_statement=VALID_AUTH_STATEMENT,
        status="active",
    )
    db.add(investigation)
    await db.commit()
    await db.refresh(investigation)

    response = await client.get(
        f"/api/v1/investigations/{investigation.id}/timeline",
        headers=analyst_headers,
    )

    assert response.status_code == 404


async def test_empty_timeline_returns_investigation_created_event(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
) -> None:
    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/timeline",
        headers=analyst_headers,
    )

    assert response.status_code == 200
    parsed = TimelineResponse.model_validate(response.json())
    assert parsed.total == 1
    assert parsed.events[0].event_type == "investigation_created"
    assert parsed.events[0].severity == "info"


async def test_populated_timeline_and_filters(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    await _add_phase2f_data(db, test_investigation.id)

    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/timeline",
        headers=analyst_headers,
    )
    filtered = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/timeline",
        headers=analyst_headers,
        params={
            "severity": "high",
            "event_type": "finding_created",
            "source": "virustotal",
        },
    )

    assert response.status_code == 200
    parsed = TimelineResponse.model_validate(response.json())
    event_types = {event.event_type for event in parsed.events}
    assert "recon_entity_observed" in event_types
    assert "threat_finding_observed" in event_types
    assert "finding_created" in event_types
    assert "ai_analysis_created" in event_types
    assert "report_generated" in event_types
    assert "knowledge_citation_observed" in event_types

    assert filtered.status_code == 200
    filtered_body = filtered.json()
    assert filtered_body["total"] == 2
    assert {
        event["title"] for event in filtered_body["events"]
    } == {"High reputation signal"}


async def test_admin_can_access_timeline(
    client: AsyncClient,
    admin_headers: dict[str, str],
    test_investigation,
) -> None:
    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/timeline",
        headers=admin_headers,
    )

    assert response.status_code == 200


async def test_empty_correlations_returns_empty_projection(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
) -> None:
    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/correlations",
        headers=analyst_headers,
    )

    assert response.status_code == 200
    parsed = CorrelationResponse.model_validate(response.json())
    assert parsed.total_nodes == 0
    assert parsed.total_edges == 0


async def test_populated_correlations_and_permissions(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
    other_user,
) -> None:
    await _add_phase2f_data(db, test_investigation.id)
    other_token = create_access_token(user_id=str(other_user.id), role=other_user.role)
    other_headers = {"Authorization": f"Bearer {other_token}"}

    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/correlations",
        headers=analyst_headers,
    )
    denied = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/correlations",
        headers=other_headers,
    )

    assert response.status_code == 200
    parsed = CorrelationResponse.model_validate(response.json())
    edge_types = {edge.correlation_type for edge in parsed.edges}
    assert "shared_ip" in edge_types
    assert "shared_certificate" in edge_types
    assert "provider_overlap" in edge_types
    assert "repeated_ioc_pattern" in edge_types
    assert "recurring_finding" in edge_types
    assert "related_knowledge_citation" in edge_types
    assert denied.status_code == 404


async def _add_phase2f_data(db: AsyncSession, investigation_id) -> None:
    domain = ReconEntity(
        investigation_id=investigation_id,
        entity_type="Domain",
        value="example.com",
        properties={},
        source="dns",
    )
    app = ReconEntity(
        investigation_id=investigation_id,
        entity_type="Subdomain",
        value="app.example.com",
        properties={"server": "nginx"},
        source="dns",
    )
    api = ReconEntity(
        investigation_id=investigation_id,
        entity_type="Subdomain",
        value="api.example.com",
        properties={"server": "nginx"},
        source="dns",
    )
    ip_address = ReconEntity(
        investigation_id=investigation_id,
        entity_type="IPAddress",
        value="93.184.216.34",
        properties={"country": "US"},
        source="dns",
    )
    certificate = ReconEntity(
        investigation_id=investigation_id,
        entity_type="Certificate",
        value="crtsh:12345",
        properties={"issuer": "Example CA"},
        source="crt.sh",
    )
    db.add_all([domain, app, api, ip_address, certificate])
    await db.flush()
    db.add_all(
        [
            ReconRelationship(
                investigation_id=investigation_id,
                source_entity_id=app.id,
                target_entity_id=ip_address.id,
                relationship_type="RESOLVES_TO",
                source="dns",
            ),
            ReconRelationship(
                investigation_id=investigation_id,
                source_entity_id=api.id,
                target_entity_id=ip_address.id,
                relationship_type="RESOLVES_TO",
                source="dns",
            ),
            ReconRelationship(
                investigation_id=investigation_id,
                source_entity_id=app.id,
                target_entity_id=certificate.id,
                relationship_type="USES_CERTIFICATE",
                source="crt.sh",
            ),
            ReconRelationship(
                investigation_id=investigation_id,
                source_entity_id=api.id,
                target_entity_id=certificate.id,
                relationship_type="USES_CERTIFICATE",
                source="crt.sh",
            ),
            InvestigationEnrichment(
                investigation_id=investigation_id,
                target_type="domain",
                target_value="example.com",
                authorization_statement=VALID_AUTH_STATEMENT,
                status="completed",
                summary={"entity_count": 5, "relationship_count": 4},
                result={"target_type": "domain", "target_value": "example.com"},
            ),
        ]
    )
    await db.flush()
    vt_domain = ThreatFinding(
        investigation_id=investigation_id,
        recon_entity_id=app.id,
        target_type="domain",
        target_value="app.example.com",
        provider="virustotal",
        status="completed",
        risk_score=10,
        confidence="low",
        verdict="low",
        signals=["malicious:0"],
        normalized_data={},
        raw_data={},
    )
    vt_ip = ThreatFinding(
        investigation_id=investigation_id,
        recon_entity_id=ip_address.id,
        target_type="ip",
        target_value="93.184.216.34",
        provider="virustotal",
        status="completed",
        risk_score=70,
        confidence="high",
        verdict="high",
        signals=["malicious:5"],
        normalized_data={},
        raw_data={},
    )
    abuse_ip = ThreatFinding(
        investigation_id=investigation_id,
        recon_entity_id=ip_address.id,
        target_type="ip",
        target_value="93.184.216.34",
        provider="abuseipdb",
        status="completed",
        risk_score=80,
        confidence="high",
        verdict="high",
        signals=["abuse_confidence:80"],
        normalized_data={},
        raw_data={},
    )
    db.add_all([vt_domain, vt_ip, abuse_ip])
    await db.flush()
    finding_one = Finding(
        investigation_id=investigation_id,
        title="High reputation signal",
        description="The stored reputation signal is high risk.",
        severity="high",
        confidence_score=85,
        risk_score=70,
        source="virustotal",
        raw_data={},
        normalized_data={},
        status="open",
    )
    finding_two = Finding(
        investigation_id=investigation_id,
        title="High reputation signal",
        description="The stored reputation signal recurred.",
        severity="high",
        confidence_score=80,
        risk_score=68,
        source="virustotal",
        raw_data={},
        normalized_data={},
        status="open",
    )
    target = Target(
        investigation_id=investigation_id,
        target_type="domain",
        target_value="example.com",
    )
    report = Report(
        investigation_id=investigation_id,
        generated_by=None,
        title="Technical Report",
        report_type="technical",
        report_format="html",
        status="ready",
        html_content="<html></html>",
        markdown_content="- [knowledge:local-cis] CIS hardening guidance\n",
        report_metadata={"knowledge_citation_count": 1},
    )
    db.add_all([finding_one, finding_two, target, report])
    await db.flush()
    db.add(
        AiAnalysis(
            target_id=target.id,
            finding_ids=[finding_one.id, finding_two.id],
            analysis_text="Stored analysis artifact.",
            risk_assessment="high",
            framework_mappings={},
            recommendations=[],
            rag_sources=[],
            model_used="mock",
        )
    )
    await db.commit()
