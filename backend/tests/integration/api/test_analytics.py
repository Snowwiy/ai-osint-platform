from __future__ import annotations

from app.models.ai_analysis import AiAnalysis
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.investigation_member import InvestigationMember
from app.models.recon_entity import ReconEntity
from app.models.recon_relationship import ReconRelationship
from app.models.report import Report
from app.models.target import Target
from app.models.threat_finding import ThreatFinding
from app.schemas.analytics import (
    DashboardAnalyticsResponse,
    InvestigationAnalyticsResponse,
)
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import VALID_AUTH_STATEMENT


async def test_investigation_analytics_requires_auth(
    client: AsyncClient,
    test_investigation,
) -> None:
    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/analytics"
    )

    assert response.status_code == 401


async def test_investigation_analytics_non_member_gets_404(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    admin_user,
) -> None:
    investigation = Investigation(
        title="Private Analytics",
        owner_id=admin_user.id,
        authorization_statement=VALID_AUTH_STATEMENT,
        status="active",
    )
    db.add(investigation)
    await db.commit()
    await db.refresh(investigation)

    response = await client.get(
        f"/api/v1/investigations/{investigation.id}/analytics",
        headers=analyst_headers,
    )

    assert response.status_code == 404


async def test_empty_investigation_analytics(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
) -> None:
    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/analytics",
        headers=analyst_headers,
    )

    assert response.status_code == 200
    parsed = InvestigationAnalyticsResponse.model_validate(response.json())
    assert parsed.risk_summary.risk_score == 0
    assert parsed.target_summary.total == 0
    assert parsed.recon_summary.total_entities == 0
    assert parsed.findings_summary.total == 0
    assert parsed.timeline_summary.total == 1
    assert parsed.latest_activity[0].title == "Investigation created"


async def test_populated_investigation_analytics(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    await _add_analytics_data(db, test_investigation.id)

    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/analytics",
        headers=analyst_headers,
    )

    assert response.status_code == 200
    parsed = InvestigationAnalyticsResponse.model_validate(response.json())
    assert parsed.target_summary.total == 1
    assert parsed.target_summary.by_type["domain"] == 1
    assert parsed.recon_summary.entity_counts["Domain"] == 1
    assert parsed.recon_summary.entity_counts["Technology"] == 1
    assert parsed.findings_summary.by_severity["high"] == 1
    assert parsed.findings_summary.by_status["open"] == 1
    assert parsed.risk_summary.risk_score == 88
    assert parsed.risk_summary.risk_level == "Critical"
    assert parsed.correlation_summary.total_edges >= 1
    assert parsed.report_summary.ready == 1
    assert parsed.ai_analysis_summary.available is True
    assert parsed.top_assets[0].label == "app.example.com"
    assert parsed.top_technologies[0].label == "nginx"
    assert parsed.latest_activity


async def test_dashboard_analytics_user_scoping_and_admin_aggregate(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    admin_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
    admin_user,
) -> None:
    await _add_analytics_data(db, test_investigation.id)
    private_investigation = Investigation(
        title="Admin Only",
        owner_id=admin_user.id,
        authorization_statement=VALID_AUTH_STATEMENT,
        status="active",
    )
    db.add(private_investigation)
    await db.flush()
    db.add(
        InvestigationMember(
            investigation_id=private_investigation.id,
            user_id=admin_user.id,
            role="owner",
        )
    )
    await db.commit()

    analyst_response = await client.get(
        "/api/v1/dashboard/analytics",
        headers=analyst_headers,
    )
    admin_response = await client.get(
        "/api/v1/dashboard/analytics",
        headers=admin_headers,
    )

    assert analyst_response.status_code == 200
    analyst_parsed = DashboardAnalyticsResponse.model_validate(
        analyst_response.json()
    )
    assert analyst_parsed.investigation_summary.total == 1
    assert analyst_parsed.findings_summary.total == 1
    assert analyst_parsed.report_summary.total == 1
    assert analyst_parsed.open_high_risk_items[0].title == "High VT reputation"

    assert admin_response.status_code == 200
    admin_parsed = DashboardAnalyticsResponse.model_validate(admin_response.json())
    assert admin_parsed.investigation_summary.total == 2
    assert admin_parsed.investigation_summary.active == 2


async def test_dashboard_analytics_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/dashboard/analytics")

    assert response.status_code == 401


async def test_admin_can_access_investigation_analytics(
    client: AsyncClient,
    admin_headers: dict[str, str],
    test_investigation,
) -> None:
    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/analytics",
        headers=admin_headers,
    )

    assert response.status_code == 200


async def _add_analytics_data(db: AsyncSession, investigation_id) -> None:
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
    ip_address = ReconEntity(
        investigation_id=investigation_id,
        entity_type="IPAddress",
        value="93.184.216.34",
        properties={"provider": "Example CDN"},
        source="dns",
    )
    technology = ReconEntity(
        investigation_id=investigation_id,
        entity_type="Technology",
        value="nginx",
        properties={},
        source="http",
    )
    db.add_all([domain, app, ip_address, technology])
    await db.flush()
    db.add_all(
        [
            ReconRelationship(
                investigation_id=investigation_id,
                source_entity_id=domain.id,
                target_entity_id=ip_address.id,
                relationship_type="RESOLVES_TO",
                source="dns",
            ),
            ReconRelationship(
                investigation_id=investigation_id,
                source_entity_id=app.id,
                target_entity_id=ip_address.id,
                relationship_type="RESOLVES_TO",
                source="dns",
            ),
        ]
    )
    target = Target(
        investigation_id=investigation_id,
        target_type="domain",
        target_value="example.com",
    )
    finding = Finding(
        investigation_id=investigation_id,
        title="High VT reputation",
        description="VirusTotal reputation indicates a high-risk signal.",
        severity="high",
        confidence_score=90,
        risk_score=72,
        source="virustotal",
        raw_data={},
        normalized_data={"affected_targets": ["app.example.com"]},
        status="open",
    )
    threat_finding = ThreatFinding(
        investigation_id=investigation_id,
        recon_entity_id=ip_address.id,
        target_type="ip",
        target_value="93.184.216.34",
        provider="abuseipdb",
        status="completed",
        risk_score=88,
        confidence="high",
        verdict="high",
        signals=["abuse_confidence:88"],
        normalized_data={},
        raw_data={},
    )
    report = Report(
        investigation_id=investigation_id,
        generated_by=None,
        title="Executive Report",
        report_type="executive",
        report_format="html",
        status="ready",
        html_content="<html></html>",
        markdown_content="- [knowledge:local-nist] response guidance\n",
        report_metadata={"knowledge_citation_count": 1},
    )
    db.add_all([target, finding, threat_finding, report])
    await db.flush()
    db.add(
        AiAnalysis(
            target_id=target.id,
            finding_ids=[finding.id],
            analysis_text="Stored analysis artifact.",
            risk_assessment="high",
            framework_mappings={},
            recommendations=[],
            rag_sources=[],
            model_used="mock",
        )
    )
    await db.commit()
