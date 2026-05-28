from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import VALID_AUTH_STATEMENT

_VALID_AUTH = "A" * 100


async def test_create_investigation_success(
    client: AsyncClient,
    analyst_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/api/v1/investigations/",
        json={
            "title": "Test Investigation",
            "description": "For testing",
            "authorization_statement": _VALID_AUTH,
        },
        headers=analyst_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Investigation"
    assert data["status"] == "draft"


async def test_create_rejects_short_auth_statement(
    client: AsyncClient,
    analyst_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/api/v1/investigations/",
        json={
            "title": "Test",
            "description": "Test",
            "authorization_statement": "too short",
        },
        headers=analyst_headers,
    )
    assert response.status_code == 422


async def test_creator_is_automatically_owner(
    client: AsyncClient,
    analyst_headers: dict[str, str],
) -> None:
    investigation = await client.post(
        "/api/v1/investigations/",
        json={
            "title": "Ownership Test",
            "description": "Test",
            "authorization_statement": _VALID_AUTH,
        },
        headers=analyst_headers,
    )
    inv_id = investigation.json()["id"]
    members = await client.get(
        f"/api/v1/investigations/{inv_id}/members",
        headers=analyst_headers,
    )
    assert members.status_code == 200
    assert any(member["role"] == "owner" for member in members.json())


async def test_analyst_cannot_see_others_investigations(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    await client.post(
        "/api/v1/investigations/",
        json={
            "title": "Admin Only Investigation",
            "description": "Not for analyst",
            "authorization_statement": VALID_AUTH_STATEMENT,
        },
        headers=admin_headers,
    )
    response = await client.get("/api/v1/investigations/", headers=analyst_headers)
    titles = [item["title"] for item in response.json()["items"]]
    assert "Admin Only Investigation" not in titles


async def test_admin_sees_all_investigations(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    await client.post(
        "/api/v1/investigations/",
        json={
            "title": "Analyst Investigation",
            "description": "Analyst owns this",
            "authorization_statement": VALID_AUTH_STATEMENT,
        },
        headers=analyst_headers,
    )
    response = await client.get("/api/v1/investigations/", headers=admin_headers)
    titles = [item["title"] for item in response.json()["items"]]
    assert "Analyst Investigation" in titles


async def test_get_investigation_returns_404_for_non_member(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    investigation = await client.post(
        "/api/v1/investigations/",
        json={
            "title": "Private",
            "description": "Admin only",
            "authorization_statement": VALID_AUTH_STATEMENT,
        },
        headers=admin_headers,
    )
    inv_id = investigation.json()["id"]
    response = await client.get(
        f"/api/v1/investigations/{inv_id}",
        headers=analyst_headers,
    )
    assert response.status_code == 404


async def test_add_member_as_owner(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    admin_user,
) -> None:
    investigation = await client.post(
        "/api/v1/investigations/",
        json={
            "title": "Membership Test",
            "description": "Test",
            "authorization_statement": VALID_AUTH_STATEMENT,
        },
        headers=analyst_headers,
    )
    inv_id = investigation.json()["id"]
    response = await client.post(
        f"/api/v1/investigations/{inv_id}/members",
        json={"user_id": str(admin_user.id), "role": "collaborator"},
        headers=analyst_headers,
    )
    assert response.status_code == 201
    assert response.json()["role"] == "collaborator"


async def test_add_duplicate_member_returns_409(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    admin_user,
) -> None:
    investigation = await client.post(
        "/api/v1/investigations/",
        json={
            "title": "Dupe Member Test",
            "description": "Test",
            "authorization_statement": VALID_AUTH_STATEMENT,
        },
        headers=analyst_headers,
    )
    inv_id = investigation.json()["id"]
    payload = {"user_id": str(admin_user.id), "role": "collaborator"}
    await client.post(
        f"/api/v1/investigations/{inv_id}/members",
        json=payload,
        headers=analyst_headers,
    )
    response = await client.post(
        f"/api/v1/investigations/{inv_id}/members",
        json=payload,
        headers=analyst_headers,
    )
    assert response.status_code == 409


async def test_cannot_remove_last_owner(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    analyst_user,
) -> None:
    investigation = await client.post(
        "/api/v1/investigations/",
        json={
            "title": "Last Owner Test",
            "description": "Test",
            "authorization_statement": VALID_AUTH_STATEMENT,
        },
        headers=analyst_headers,
    )
    inv_id = investigation.json()["id"]
    response = await client.delete(
        f"/api/v1/investigations/{inv_id}/members/{analyst_user.id}",
        headers=analyst_headers,
    )
    assert response.status_code == 409


async def test_invalid_member_role_returns_422(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    admin_user,
) -> None:
    investigation = await client.post(
        "/api/v1/investigations/",
        json={
            "title": "Invalid Role Test",
            "description": "Test",
            "authorization_statement": VALID_AUTH_STATEMENT,
        },
        headers=analyst_headers,
    )
    inv_id = investigation.json()["id"]
    response = await client.post(
        f"/api/v1/investigations/{inv_id}/members",
        json={"user_id": str(admin_user.id), "role": "analyst"},
        headers=analyst_headers,
    )
    assert response.status_code == 422
