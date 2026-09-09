from __future__ import annotations

from app.core.security import create_access_token
from app.models.audit_log import AuditLog
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.investigation_member import InvestigationMember
from app.models.saved_view import SavedView
from app.models.user import User
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import VALID_AUTH_STATEMENT


async def test_unauthenticated_user_cannot_search(client: AsyncClient) -> None:
    response = await client.get("/api/v1/search?q=test")

    assert response.status_code == 401


async def test_search_returns_allowed_investigations_and_findings(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation: Investigation,
    db: AsyncSession,
) -> None:
    finding = Finding(
        investigation_id=test_investigation.id,
        title="Unique Search Finding",
        description="Evidence-backed finding for internal global search.",
        severity="high",
        source="manual_review",
        status="open",
    )
    db.add(finding)
    await db.commit()

    investigation_response = await client.get(
        "/api/v1/search?q=Test Investigation&type=investigation",
        headers=analyst_headers,
    )
    finding_response = await client.get(
        "/api/v1/search?q=Unique Search Finding&type=finding",
        headers=analyst_headers,
    )

    assert investigation_response.status_code == 200
    assert investigation_response.json()["items"][0]["type"] == "investigation"
    assert investigation_response.json()["items"][0]["id"] == str(test_investigation.id)
    assert finding_response.status_code == 200
    assert finding_response.json()["items"][0]["type"] == "finding"
    assert finding_response.json()["items"][0]["id"] == str(finding.id)


async def test_search_respects_investigation_rbac(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    other_user: User,
    db: AsyncSession,
) -> None:
    hidden = Investigation(
        title="Hidden Client Review",
        owner_id=other_user.id,
        authorization_statement=VALID_AUTH_STATEMENT,
        status="active",
    )
    db.add(hidden)
    await db.flush()
    db.add(
        InvestigationMember(
            investigation_id=hidden.id,
            user_id=other_user.id,
            role="owner",
        )
    )
    await db.commit()

    response = await client.get(
        "/api/v1/search?q=Hidden Client Review&type=investigation",
        headers=analyst_headers,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0


async def test_user_search_is_admin_only_and_sanitized(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    admin_headers: dict[str, str],
    admin_user: User,
) -> None:
    analyst_response = await client.get(
        f"/api/v1/search?q={admin_user.username}&type=user",
        headers=analyst_headers,
    )
    admin_response = await client.get(
        f"/api/v1/search?q={admin_user.username}&type=user",
        headers=admin_headers,
    )

    assert analyst_response.status_code == 200
    assert analyst_response.json()["total"] == 0
    assert admin_response.status_code == 200
    item = admin_response.json()["items"][0]
    assert item["type"] == "user"
    assert item["title"] == admin_user.username
    assert "password" not in str(item).lower()
    assert "hashed_password" not in str(item).lower()


async def test_saved_view_crud_pin_default_and_audit(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
) -> None:
    create_response = await client.post(
        "/api/v1/saved-views",
        headers=analyst_headers,
        json={
            "name": "High Risk Findings",
            "view_type": "findings",
            "route": "/investigations/demo/findings",
            "filters": {"severity": "high", "password": "should-not-store"},
            "sort": {"updated": "desc"},
            "is_pinned": False,
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["filters"] == {"severity": "high"}

    duplicate = await client.post(
        "/api/v1/saved-views",
        headers=analyst_headers,
        json={
            "name": "High Risk Findings",
            "view_type": "findings",
            "route": "/findings",
        },
    )
    assert duplicate.status_code == 409

    pin_response = await client.post(
        f"/api/v1/saved-views/{created['id']}/pin",
        headers=analyst_headers,
    )
    assert pin_response.status_code == 200
    assert pin_response.json()["is_pinned"] is True

    default_response = await client.post(
        f"/api/v1/saved-views/{created['id']}/set-default",
        headers=analyst_headers,
    )
    assert default_response.status_code == 200
    assert default_response.json()["is_default"] is True

    update_response = await client.patch(
        f"/api/v1/saved-views/{created['id']}",
        headers=analyst_headers,
        json={"name": "High Risk Findings Today", "filters": {"severity": "critical"}},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "High Risk Findings Today"
    assert update_response.json()["filters"] == {"severity": "critical"}

    list_response = await client.get(
        "/api/v1/saved-views?view_type=findings&pinned=true",
        headers=analyst_headers,
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    delete_response = await client.delete(
        f"/api/v1/saved-views/{created['id']}",
        headers=analyst_headers,
    )
    assert delete_response.status_code == 204

    actions = (
        await db.execute(
            select(AuditLog.action).where(
                AuditLog.action.in_(
                    [
                        "saved_view.created",
                        "saved_view.updated",
                        "saved_view.deleted",
                        "saved_view.pinned",
                        "saved_view.default_set",
                    ]
                )
            )
        )
    ).scalars().all()
    assert "saved_view.created" in actions
    assert "saved_view.updated" in actions
    assert "saved_view.deleted" in actions
    assert "saved_view.pinned" in actions
    assert "saved_view.default_set" in actions


async def test_saved_view_ownership_and_invalid_route(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    other_user: User,
    db: AsyncSession,
) -> None:
    other_view = SavedView(
        user_id=other_user.id,
        name="Other Analyst View",
        view_type="reports",
        route="/reports",
        filters={},
    )
    db.add(other_view)
    await db.commit()
    await db.refresh(other_view)

    missing = await client.get(
        f"/api/v1/saved-views/{other_view.id}",
        headers=analyst_headers,
    )
    invalid = await client.post(
        "/api/v1/saved-views",
        headers=analyst_headers,
        json={
            "name": "Unsafe Redirect",
            "view_type": "search",
            "route": "https://example.invalid",
        },
    )

    assert missing.status_code == 404
    assert invalid.status_code == 422


async def test_saved_view_user_cannot_access_another_users_view_with_token(
    client: AsyncClient,
    other_user: User,
    db: AsyncSession,
    analyst_user: User,
) -> None:
    view = SavedView(
        user_id=analyst_user.id,
        name="Private View",
        view_type="dashboard",
        route="/dashboard",
        filters={},
    )
    db.add(view)
    await db.commit()
    await db.refresh(view)
    token = create_access_token(user_id=str(other_user.id), role=other_user.role)

    response = await client.delete(
        f"/api/v1/saved-views/{view.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
