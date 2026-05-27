from __future__ import annotations

from httpx import AsyncClient


async def test_admin_can_create_user(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/api/v1/users/",
        headers=admin_headers,
        json={
            "username": "new_analyst",
            "email": "new.analyst@test.raventech.mx",
            "password": "NewAnalyst123!",
            "role": "analyst",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "analyst"


async def test_analyst_cannot_create_user(
    client: AsyncClient,
    analyst_headers: dict[str, str],
) -> None:
    response = await client.post(
        "/api/v1/users/",
        headers=analyst_headers,
        json={
            "username": "blocked",
            "email": "blocked@test.raventech.mx",
            "password": "BlockedPass123!",
            "role": "analyst",
        },
    )
    assert response.status_code == 403


async def test_admin_cannot_deactivate_self(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user,
) -> None:
    response = await client.delete(
        f"/api/v1/users/{admin_user.id}",
        headers=admin_headers,
    )
    assert response.status_code == 400
