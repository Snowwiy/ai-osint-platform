from __future__ import annotations

from app.models.audit_log import AuditLog
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import VALID_AUTH_STATEMENT


async def _create_engagement(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    title: str = "Authorized Client Review",
    client_name: str = "Demo Client",
) -> dict:
    response = await client.post(
        "/api/v1/engagements/",
        headers=headers,
        json={
            "title": title,
            "client_name": client_name,
            "description": "Documented defensive assessment scope.",
            "status": "active",
            "authorization_status": "approved",
        },
    )
    assert response.status_code == 201
    return response.json()


async def test_engagement_create_list_and_archive(
    client: AsyncClient,
    analyst_headers: dict[str, str],
) -> None:
    engagement = await _create_engagement(client, analyst_headers)

    list_response = await client.get(
        "/api/v1/engagements/",
        headers=analyst_headers,
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["items"][0]["id"] == engagement["id"]
    assert list_response.json()["items"][0]["scope_counts"]["in_scope"] == 0

    archive_response = await client.post(
        f"/api/v1/engagements/{engagement['id']}/archive",
        headers=analyst_headers,
    )
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "archived"


async def test_anonymous_user_cannot_modify_engagement(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/engagements/",
        json={"title": "Viewer Attempt", "client_name": "Client"},
    )
    assert response.status_code == 401


async def test_scope_item_crud_conflict_and_scope_checks(
    client: AsyncClient,
    analyst_headers: dict[str, str],
) -> None:
    engagement = await _create_engagement(client, analyst_headers)
    engagement_id = engagement["id"]

    scope_response = await client.post(
        f"/api/v1/engagements/{engagement_id}/scope",
        headers=analyst_headers,
        json={
            "scope_type": "domain",
            "value": "example.com",
            "description": "Approved domain and subdomains.",
            "status": "in_scope",
        },
    )
    assert scope_response.status_code == 201
    scope_item = scope_response.json()

    duplicate = await client.post(
        f"/api/v1/engagements/{engagement_id}/scope",
        headers=analyst_headers,
        json={"scope_type": "domain", "value": "example.com"},
    )
    assert duplicate.status_code == 409

    domain_check = await client.post(
        f"/api/v1/engagements/{engagement_id}/scope/check",
        headers=analyst_headers,
        json={"scope_type": "domain", "value": "sub.example.com"},
    )
    assert domain_check.status_code == 200
    assert domain_check.json()["status"] == "in_scope"
    assert domain_check.json()["matched_scope_item"]["id"] == scope_item["id"]

    cidr = await client.post(
        f"/api/v1/engagements/{engagement_id}/scope",
        headers=analyst_headers,
        json={"scope_type": "cidr", "value": "192.0.2.0/24", "status": "in_scope"},
    )
    assert cidr.status_code == 201
    ip_check = await client.post(
        f"/api/v1/engagements/{engagement_id}/scope/check",
        headers=analyst_headers,
        json={"scope_type": "ip", "value": "192.0.2.44"},
    )
    assert ip_check.status_code == 200
    assert ip_check.json()["status"] == "in_scope"

    unknown_check = await client.post(
        f"/api/v1/engagements/{engagement_id}/scope/check",
        headers=analyst_headers,
        json={"scope_type": "domain", "value": "outside.example.net"},
    )
    assert unknown_check.status_code == 200
    assert unknown_check.json()["status"] == "pending_review"

    delete_response = await client.delete(
        f"/api/v1/engagements/{engagement_id}/scope/{scope_item['id']}",
        headers=analyst_headers,
    )
    assert delete_response.status_code == 204


async def test_authorization_metadata_and_audit_events(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
) -> None:
    engagement = await _create_engagement(client, analyst_headers)
    evidence_response = await client.post(
        f"/api/v1/engagements/{engagement['id']}/authorization",
        headers=analyst_headers,
        json={
            "title": "Signed statement of work",
            "evidence_type": "statement_of_work",
            "reference": "SOW-2026-001",
            "status": "approved",
        },
    )
    assert evidence_response.status_code == 201

    actions = (
        await db.execute(
            select(AuditLog.action).where(
                AuditLog.action.in_(
                    [
                        "engagement.created",
                        "engagement.authorization_added",
                    ]
                )
            )
        )
    ).scalars().all()
    assert "engagement.created" in actions
    assert "engagement.authorization_added" in actions


async def test_investigation_can_link_engagement_and_reports_include_metadata(
    client: AsyncClient,
    analyst_headers: dict[str, str],
) -> None:
    engagement = await _create_engagement(client, analyst_headers)
    engagement_id = engagement["id"]
    scope_response = await client.post(
        f"/api/v1/engagements/{engagement_id}/scope",
        headers=analyst_headers,
        json={"scope_type": "domain", "value": "example.com"},
    )
    assert scope_response.status_code == 201

    investigation = await client.post(
        "/api/v1/investigations/",
        headers=analyst_headers,
        json={
            "title": "Scoped Investigation",
            "description": "A defensive client assessment.",
            "authorization_statement": VALID_AUTH_STATEMENT,
            "engagement_id": engagement_id,
            "scope_review_status": "in_scope",
            "scope_notes": "Matched against approved engagement scope.",
        },
    )
    assert investigation.status_code == 201
    investigation_id = investigation.json()["id"]
    assert investigation.json()["engagement_id"] == engagement_id
    assert investigation.json()["scope_review_status"] == "in_scope"

    report = await client.post(
        f"/api/v1/investigations/{investigation_id}/reports",
        headers=analyst_headers,
        json={"report_type": "technical"},
    )
    assert report.status_code == 200
    report_id = report.json()["id"]

    detail = await client.get(
        f"/api/v1/reports/{report_id}",
        headers=analyst_headers,
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["report_metadata"]["engagement_title"] == "Authorized Client Review"
    assert body["report_metadata"]["client_name"] == "Demo Client"
    assert "Engagement: Authorized Client Review" in body["markdown_content"]
