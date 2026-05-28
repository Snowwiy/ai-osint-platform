from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import TEST_PASSWORD


async def test_login_success(client: AsyncClient, analyst_user) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": analyst_user.email, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_login_with_username_success(client: AsyncClient, analyst_user) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": analyst_user.username, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_login_wrong_password(client: AsyncClient, analyst_user) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": analyst_user.email, "password": "WrongPassword999!"},
    )
    assert response.status_code == 401


async def test_login_inactive_user(client: AsyncClient, inactive_user) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": inactive_user.email, "password": TEST_PASSWORD},
    )
    assert response.status_code == 403


async def test_refresh_rotates_token(client: AsyncClient, analyst_user) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": analyst_user.email, "password": TEST_PASSWORD},
    )
    old_refresh = login.json()["refresh_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert response.status_code == 200
    assert response.json()["refresh_token"] != old_refresh

    old_token_reuse = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert old_token_reuse.status_code == 401


async def test_logout_revokes_refresh_token(client: AsyncClient, analyst_user) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": analyst_user.email, "password": TEST_PASSWORD},
    )
    refresh_token = login.json()["refresh_token"]
    logout = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout.status_code == 204

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 401


async def test_me_returns_current_user(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    analyst_user,
) -> None:
    response = await client.get("/api/v1/auth/me", headers=analyst_headers)
    assert response.status_code == 200
    assert response.json()["email"] == analyst_user.email
    assert "hashed_password" not in response.json()


async def test_me_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_change_password_rejects_wrong_current_password(
    client: AsyncClient,
    analyst_headers: dict[str, str],
) -> None:
    response = await client.put(
        "/api/v1/auth/me/password",
        headers=analyst_headers,
        json={
            "current_password": "WrongPassword999!",
            "new_password": "NewPassword123!",
        },
    )
    assert response.status_code == 400
