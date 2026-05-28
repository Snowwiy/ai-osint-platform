from __future__ import annotations

from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.investigation_enrichment import InvestigationEnrichment
from app.models.recon_entity import ReconEntity
from app.models.threat_finding import ThreatFinding
from app.schemas.finding import FindingResponse, FindingSummaryResponse
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import VALID_AUTH_STATEMENT


async def test_findings_require_membership(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    admin_user,
) -> None:
    investigation = Investigation(
        title="Private Findings",
        owner_id=admin_user.id,
        authorization_statement=VALID_AUTH_STATEMENT,
        status="active",
    )
    db.add(investigation)
    await db.commit()
    await db.refresh(investigation)

    response = await client.get(
        f"/api/v1/investigations/{investigation.id}/findings",
        headers=analyst_headers,
    )

    assert response.status_code == 404


async def test_admin_can_list_findings_for_any_investigation(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    await _add_intelligence_data(db, test_investigation.id)

    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/findings",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()


async def test_findings_generated_from_recon_and_threat_intel(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    await _add_intelligence_data(db, test_investigation.id)

    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/findings",
        headers=analyst_headers,
    )

    assert response.status_code == 200
    parsed = [FindingResponse.model_validate(item) for item in response.json()]
    titles = {finding.title: finding for finding in parsed}
    assert titles["Expired TLS certificate for example.com"].severity == "medium"
    assert titles["Malicious VirusTotal reputation for example.com"].severity == "high"
    assert titles["High AbuseIPDB reputation for 8.8.8.8"].severity == "high"
    assert titles["Risky server disclosure for example.com"].severity == "low"
    assert titles["Exposed internal metadata for example.com"].severity == "medium"
    assert titles["Suspicious SPF policy for example.com"].severity == "low"


async def test_findings_filters_by_severity_status_and_source(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    await _add_intelligence_data(db, test_investigation.id)

    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/findings",
        headers=analyst_headers,
        params={"severity": "high", "status": "open", "source": "virustotal"},
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["title"] for item in body] == [
        "Malicious VirusTotal reputation for example.com"
    ]


async def test_findings_summary_returns_counts_and_risk_score(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    await _add_intelligence_data(db, test_investigation.id)

    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/findings/summary",
        headers=analyst_headers,
    )

    assert response.status_code == 200
    summary = FindingSummaryResponse.model_validate(response.json())
    assert summary.total == 6
    assert summary.by_severity["high"] == 2
    assert summary.risk_score_v2 >= 51
    assert summary.risk_level_v2 in ("High", "Critical")


async def test_patch_finding_status(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    await _add_intelligence_data(db, test_investigation.id)
    await client.get(
        f"/api/v1/investigations/{test_investigation.id}/findings",
        headers=analyst_headers,
    )
    finding = (
        (
            await db.execute(
                select(Finding).where(Finding.investigation_id == test_investigation.id)
            )
        )
        .scalars()
        .first()
    )
    assert finding is not None

    response = await client.patch(
        f"/api/v1/findings/{finding.id}/status",
        headers=analyst_headers,
        json={"status": "validated"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "validated"


async def test_graph_exposes_finding_relationships(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    await _add_intelligence_data(db, test_investigation.id)
    await client.get(
        f"/api/v1/investigations/{test_investigation.id}/findings",
        headers=analyst_headers,
    )

    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/graph",
        headers=analyst_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["findings"]
    assert body["finding_edges"]
    assert body["finding_edges"][0]["relationship_type"] == "EVIDENCED_BY"


async def _add_intelligence_data(db: AsyncSession, investigation_id) -> None:
    domain = ReconEntity(
        investigation_id=investigation_id,
        entity_type="Domain",
        value="example.com",
        display_name="example.com",
        properties={},
        source="dns",
    )
    ip_address = ReconEntity(
        investigation_id=investigation_id,
        entity_type="IPAddress",
        value="8.8.8.8",
        display_name="8.8.8.8",
        properties={},
        source="threat-intel",
    )
    db.add_all([domain, ip_address])
    await db.flush()
    vt = ThreatFinding(
        investigation_id=investigation_id,
        recon_entity_id=domain.id,
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
    abuse = ThreatFinding(
        investigation_id=investigation_id,
        recon_entity_id=ip_address.id,
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
                "headers": {
                    "x-powered-by": "Express",
                    "x-internal-env": "staging",
                },
                "security_headers": {"hsts": None, "csp": None},
                "certificate": {"not_after": "2020-01-01T00:00:00Z"},
            },
        },
    )
    db.add_all([vt, abuse, enrichment])
    await db.commit()
