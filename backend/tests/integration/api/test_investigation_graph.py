from __future__ import annotations

from app.models.investigation import Investigation
from app.models.investigation_enrichment import InvestigationEnrichment
from app.models.recon_entity import ReconEntity
from app.models.recon_relationship import ReconRelationship
from app.schemas.investigation import InvestigationGraphResponse
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import VALID_AUTH_STATEMENT


async def test_graph_requires_auth(
    client: AsyncClient,
    test_investigation,
) -> None:
    response = await client.get(f"/api/v1/investigations/{test_investigation.id}/graph")

    assert response.status_code == 401


async def test_graph_non_member_gets_404(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    admin_user,
) -> None:
    investigation = Investigation(
        title="Private Graph",
        owner_id=admin_user.id,
        authorization_statement=VALID_AUTH_STATEMENT,
        status="active",
    )
    db.add(investigation)
    await db.commit()
    await db.refresh(investigation)

    response = await client.get(
        f"/api/v1/investigations/{investigation.id}/graph",
        headers=analyst_headers,
    )

    assert response.status_code == 404


async def test_admin_can_access_any_investigation_graph(
    client: AsyncClient,
    admin_headers: dict[str, str],
    test_investigation,
) -> None:
    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/graph",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["investigation_id"] == str(test_investigation.id)


async def test_empty_graph_returns_empty_projection(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
) -> None:
    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/graph",
        headers=analyst_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["nodes"] == []
    assert body["edges"] == []
    assert body["risk_summary"]["total_entities"] == 0
    assert body["risk_summary"]["risk_level"] == "not_assessed"
    assert body["timeline"] == []


async def test_populated_graph_returns_nodes_edges_timeline_and_risk_summary(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    await _add_graph_data(db, test_investigation.id)

    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/graph",
        headers=analyst_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert {node["entity_type"] for node in body["nodes"]} == {
        "Domain",
        "IPAddress",
        "Certificate",
    }
    assert {edge["relationship_type"] for edge in body["edges"]} == {
        "RESOLVES_TO",
        "USES_CERTIFICATE",
    }
    assert body["risk_summary"]["total_entities"] == 3
    assert body["risk_summary"]["entity_counts"]["Domain"] == 1
    assert body["risk_summary"]["entity_counts"]["IPAddress"] == 1
    assert body["timeline"][0]["target_type"] == "domain"
    assert body["timeline"][0]["target_value"] == "example.com"


async def test_graph_filters_entities_and_relationships_by_type(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    await _add_graph_data(db, test_investigation.id)

    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/graph",
        headers=analyst_headers,
        params=[
            ("entity_type", "Domain"),
            ("entity_type", "IPAddress"),
            ("relationship_type", "RESOLVES_TO"),
        ],
    )

    assert response.status_code == 200
    body = response.json()
    assert {node["entity_type"] for node in body["nodes"]} == {
        "Domain",
        "IPAddress",
    }
    assert [edge["relationship_type"] for edge in body["edges"]] == ["RESOLVES_TO"]
    assert body["risk_summary"]["entity_counts"]["Certificate"] == 0


async def test_graph_response_schema_validates(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    await _add_graph_data(db, test_investigation.id)

    response = await client.get(
        f"/api/v1/investigations/{test_investigation.id}/graph",
        headers=analyst_headers,
    )

    assert response.status_code == 200
    parsed = InvestigationGraphResponse.model_validate(response.json())
    assert parsed.investigation_id == test_investigation.id
    assert len(parsed.nodes) == 3
    assert len(parsed.edges) == 2


async def _add_graph_data(db: AsyncSession, investigation_id) -> None:
    domain = ReconEntity(
        investigation_id=investigation_id,
        entity_type="Domain",
        value="example.com",
        display_name="example.com",
        properties={"source_target": True},
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
    db.add_all([domain, ip_address, certificate])
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
                source_entity_id=domain.id,
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
                summary={
                    "entity_count": 3,
                    "relationship_count": 2,
                    "error_count": 0,
                },
                result={"target_type": "domain", "target_value": "example.com"},
            ),
        ]
    )
    await db.commit()
