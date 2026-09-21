from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import settings
from app.core.dependencies import get_redis
from app.core.security import decode_token
from app.main import app
from app.models.background_job import NativeAuthState
from app.services import native_auth_state
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import TEST_PASSWORD


async def test_desktop_auth_rotation_revocation_and_throttling_without_redis(
    client: AsyncClient,
    analyst_user,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert db.bind is not None
    monkeypatch.setattr(settings, "RUNTIME_PROFILE", "desktop")
    monkeypatch.setattr(
        native_auth_state,
        "AsyncSessionLocal",
        async_sessionmaker(db.bind, expire_on_commit=False),
    )
    store = native_auth_state.PostgresAuthState()
    app.dependency_overrides[get_redis] = lambda: store

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": analyst_user.email, "password": TEST_PASSWORD},
    )
    assert login.status_code == 200
    old_refresh = login.json()["refresh_token"]
    rotated = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert rotated.status_code == 200
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    ).status_code == 401
    new_refresh = rotated.json()["refresh_token"]
    assert (
        await client.post("/api/v1/auth/logout", json={"refresh_token": new_refresh})
    ).status_code == 204
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    ).status_code == 401

    expiry_login = await client.post(
        "/api/v1/auth/login",
        json={"email": analyst_user.email, "password": TEST_PASSWORD},
    )
    assert expiry_login.status_code == 200
    expiring_token = expiry_login.json()["refresh_token"]
    state = await db.get(NativeAuthState, f"rt:{decode_token(expiring_token)['jti']}")
    assert state is not None
    state.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db.commit()
    expired = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": expiring_token}
    )
    assert expired.status_code == 401

    for _ in range(settings.AUTH_FAILURE_LIMIT):
        wrong = await client.post(
            "/api/v1/auth/login",
            json={"email": analyst_user.email, "password": "IncorrectPassword123!"},
        )
        assert wrong.status_code == 401
    blocked = await client.post(
        "/api/v1/auth/login",
        json={"email": analyst_user.email, "password": TEST_PASSWORD},
    )
    assert blocked.status_code == 429
    registration = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "disabled_user",
            "email": "disabled@raventech.dev",
            "password": TEST_PASSWORD,
            "full_name": "Registration Policy Test",
        },
    )
    assert registration.status_code == 403
