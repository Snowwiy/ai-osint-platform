from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.user import User
from tests.conftest import TEST_PASSWORD


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


async def test_non_admin_cannot_list_admin_users(
    client: AsyncClient,
    analyst_headers: dict[str, str],
) -> None:
    response = await client.get("/api/v1/admin/users", headers=analyst_headers)
    assert response.status_code == 403


async def test_admin_can_list_users_without_password_hash(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user,
) -> None:
    response = await client.get("/api/v1/admin/users", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    first = body["items"][0]
    assert "hashed_password" not in first
    assert "password" not in first
    assert {item["id"] for item in body["items"]} == {str(admin_user.id)}


async def test_admin_can_approve_pending_user(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user,
    db: AsyncSession,
) -> None:
    pending = await _create_user(db, "pending_admin", "pending.admin@raventech.dev")

    response = await client.post(
        f"/api/v1/admin/users/{pending.id}/approve",
        headers=admin_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["status"] == "active"
    assert body["user"]["is_active"] is True
    assert body["user"]["approved_by"] == str(admin_user.id)
    assert await _audit_exists(db, "user.approved", pending.id)


async def test_admin_can_reject_pending_user(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
) -> None:
    pending = await _create_user(db, "reject_me", "reject.me@raventech.dev")

    response = await client.post(
        f"/api/v1/admin/users/{pending.id}/reject",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["user"]["status"] == "rejected"
    assert response.json()["user"]["is_active"] is False
    assert await _audit_exists(db, "user.rejected", pending.id)


async def test_admin_can_disable_and_reactivate_user(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
) -> None:
    analyst = await _create_user(
        db,
        "managed_analyst",
        "managed.analyst@raventech.dev",
        is_active=True,
        status="active",
    )

    disabled = await client.post(
        f"/api/v1/admin/users/{analyst.id}/disable",
        headers=admin_headers,
    )
    reactivated = await client.post(
        f"/api/v1/admin/users/{analyst.id}/reactivate",
        headers=admin_headers,
    )

    assert disabled.status_code == 200
    assert disabled.json()["user"]["status"] == "disabled"
    assert reactivated.status_code == 200
    assert reactivated.json()["user"]["status"] == "active"
    assert await _audit_exists(db, "user.disabled", analyst.id)
    assert await _audit_exists(db, "user.reactivated", analyst.id)


async def test_admin_can_change_role_safely(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
) -> None:
    analyst = await _create_user(
        db,
        "role_change",
        "role.change@raventech.dev",
        is_active=True,
        status="active",
    )

    response = await client.patch(
        f"/api/v1/admin/users/{analyst.id}/role",
        headers=admin_headers,
        json={"role": "admin"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"
    assert await _audit_exists(db, "user.role_changed", analyst.id)


async def test_admin_cannot_disable_last_active_admin(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user,
) -> None:
    response = await client.post(
        f"/api/v1/admin/users/{admin_user.id}/disable",
        headers=admin_headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "At least one active administrator account must remain."
    )


async def test_admin_cannot_demote_last_active_admin(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user,
) -> None:
    response = await client.patch(
        f"/api/v1/admin/users/{admin_user.id}/role",
        headers=admin_headers,
        json={"role": "analyst"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "At least one active administrator account must remain."
    )


async def _create_user(
    db: AsyncSession,
    username: str,
    email: str,
    *,
    is_active: bool = False,
    status: str = "pending",
) -> User:
    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(TEST_PASSWORD),
        role="analyst",
        is_active=is_active,
        account_status=status,
        registration_source="public_registration",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _audit_exists(
    db: AsyncSession,
    action: str,
    user_id,
) -> bool:
    result = await db.execute(
        select(AuditLog).where(
            AuditLog.action == action,
            AuditLog.resource_type == "user",
            AuditLog.resource_id == user_id,
        )
    )
    return result.scalar_one_or_none() is not None
