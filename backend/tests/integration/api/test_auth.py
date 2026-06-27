from __future__ import annotations

from httpx import AsyncClient

from app.core.config import settings

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


async def test_registration_disabled_returns_clean_403(
    monkeypatch,
    client: AsyncClient,
) -> None:
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", False)

    response = await client.post(
        "/api/v1/auth/register",
        json=_registration_payload("disabled_user", "disabled@raventech.dev"),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Public registration is currently disabled."


async def test_registration_enabled_creates_active_non_admin_user(
    monkeypatch,
    client: AsyncClient,
) -> None:
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", True)
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRES_APPROVAL", False)
    monkeypatch.setattr(settings, "REGISTRATION_INVITE_CODE", "")
    monkeypatch.setattr(settings, "DEFAULT_REGISTERED_USER_ROLE", "viewer")

    response = await client.post(
        "/api/v1/auth/register",
        json=_registration_payload("active_user", "active@raventech.dev"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["is_active"] is True
    assert body["account_status"] == "active"
    assert body["role"] == "analyst"
    assert body["role"] != "admin"
    assert "hashed_password" not in body

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "active@raventech.dev", "password": TEST_PASSWORD},
    )
    assert login.status_code == 200


async def test_registration_requires_approval_creates_pending_user(
    monkeypatch,
    client: AsyncClient,
) -> None:
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", True)
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRES_APPROVAL", True)
    monkeypatch.setattr(settings, "REGISTRATION_INVITE_CODE", "")

    response = await client.post(
        "/api/v1/auth/register",
        json=_registration_payload("pending_user", "pending@raventech.dev"),
    )

    assert response.status_code == 201
    assert response.json()["is_active"] is False
    assert response.json()["account_status"] == "pending"

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "pending@raventech.dev", "password": TEST_PASSWORD},
    )
    assert login.status_code == 403
    assert login.json()["detail"] == (
        "Account pending approval. Contact an administrator if needed."
    )


async def test_registration_duplicate_email_and_username_return_409(
    monkeypatch,
    client: AsyncClient,
) -> None:
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", True)
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRES_APPROVAL", False)
    monkeypatch.setattr(settings, "REGISTRATION_INVITE_CODE", "")

    created = await client.post(
        "/api/v1/auth/register",
        json=_registration_payload("duplicate_user", "duplicate@raventech.dev"),
    )
    duplicate_email = await client.post(
        "/api/v1/auth/register",
        json=_registration_payload("duplicate_other", "duplicate@raventech.dev"),
    )
    duplicate_username = await client.post(
        "/api/v1/auth/register",
        json=_registration_payload("duplicate_user", "duplicate2@raventech.dev"),
    )

    assert created.status_code == 201
    assert duplicate_email.status_code == 409
    assert duplicate_email.json()["detail"] == "A user with that email already exists."
    assert duplicate_username.status_code == 409
    assert duplicate_username.json()["detail"] == (
        "A user with that username already exists."
    )


async def test_registration_weak_password_returns_422(
    monkeypatch,
    client: AsyncClient,
) -> None:
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", True)
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRES_APPROVAL", False)

    response = await client.post(
        "/api/v1/auth/register",
        json={
            **_registration_payload("weak_user", "weak@raventech.dev"),
            "password": "weak",
        },
    )

    assert response.status_code == 422


async def test_registration_invite_code_is_required_when_configured(
    monkeypatch,
    client: AsyncClient,
) -> None:
    monkeypatch.setattr(settings, "PUBLIC_REGISTRATION_ENABLED", True)
    monkeypatch.setattr(settings, "REGISTRATION_REQUIRES_APPROVAL", False)
    monkeypatch.setattr(settings, "REGISTRATION_INVITE_CODE", "invite-123")

    missing = await client.post(
        "/api/v1/auth/register",
        json=_registration_payload("invite_user", "invite@raventech.dev"),
    )
    accepted = await client.post(
        "/api/v1/auth/register",
        json={
            **_registration_payload("invite_user", "invite@raventech.dev"),
            "invite_code": "invite-123",
        },
    )

    assert missing.status_code == 403
    assert missing.json()["detail"] == "Registration invite code is invalid."
    assert accepted.status_code == 201


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


def _registration_payload(username: str, email: str) -> dict[str, str]:
    return {
        "username": username,
        "email": email,
        "password": TEST_PASSWORD,
        "full_name": "Registration Test User",
    }
