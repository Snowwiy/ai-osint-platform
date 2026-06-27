from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import RegisterRequest, RegisterResponse

_REFRESH_TTL = int(timedelta(days=7).total_seconds())


class RedisLike(Protocol):
    async def setex(self, key: str, time: int, value: str) -> Any: ...

    async def get(self, key: str) -> str | None: ...

    async def delete(self, key: str) -> Any: ...


class AuthError(Exception):
    pass


class InvalidCredentialsError(AuthError):
    pass


class InactiveUserError(AuthError):
    def __init__(
        self,
        message: str,
        *,
        account_status: str,
        user_id: uuid.UUID | None,
    ) -> None:
        super().__init__(message)
        self.account_status = account_status
        self.user_id = user_id


class TokenError(AuthError):
    pass


class RegistrationDisabledError(AuthError):
    pass


class RegistrationInviteError(AuthError):
    pass


class RegistrationConflictError(AuthError):
    pass


async def get_user_by_identifier(db: AsyncSession, identifier: str) -> User | None:
    normalized = identifier.strip().lower()
    result = await db.execute(
        select(User).where((User.email == normalized) | (User.username == normalized))
    )
    return result.scalar_one_or_none()


async def authenticate_user(
    db: AsyncSession,
    identifier: str,
    password: str,
) -> User:
    user = await get_user_by_identifier(db, identifier)
    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Invalid credentials")
    if not user.is_active or user.account_status != "active":
        raise InactiveUserError(
            _inactive_login_message(user.account_status),
            account_status=user.account_status,
            user_id=user.id,
        )
    return user


async def login(
    db: AsyncSession,
    redis: RedisLike,
    identifier: str,
    password: str,
) -> tuple[User, str, str]:
    user = await authenticate_user(db, identifier, password)
    user.last_login = datetime.now(UTC)
    db.add(user)

    access_token = create_access_token(str(user.id), user.role)
    refresh_token, jti = create_refresh_token(str(user.id))
    await redis.setex(f"rt:{jti}", _REFRESH_TTL, str(user.id))
    return user, access_token, refresh_token


async def refresh_tokens(
    db: AsyncSession,
    redis: RedisLike,
    refresh_token: str,
) -> tuple[str, str]:
    try:
        payload = decode_token(refresh_token)
    except Exception as exc:
        raise TokenError("Invalid token") from exc

    if payload.get("type") != "refresh":
        raise TokenError("Not a refresh token")

    jti = payload.get("jti")
    user_id = payload.get("sub")
    if not jti or not user_id:
        raise TokenError("Invalid token")

    stored = await redis.get(f"rt:{jti}")
    if not stored:
        raise TokenError("Token revoked or expired")

    user = await db.get(User, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise TokenError("User unavailable")

    await redis.delete(f"rt:{jti}")
    new_access = create_access_token(str(user.id), user.role)
    new_refresh, new_jti = create_refresh_token(str(user.id))
    await redis.setex(f"rt:{new_jti}", _REFRESH_TTL, str(user.id))
    return new_access, new_refresh


async def logout(redis: RedisLike, refresh_token: str) -> None:
    try:
        payload = decode_token(refresh_token)
        jti = payload.get("jti")
        if jti:
            await redis.delete(f"rt:{jti}")
    except Exception:
        return


async def change_password(
    db: AsyncSession,
    user: User,
    current_password: str,
    new_password: str,
) -> None:
    if not verify_password(current_password, user.hashed_password):
        raise InvalidCredentialsError("Current password is incorrect")
    user.hashed_password = hash_password(new_password)
    db.add(user)


def registration_policy() -> dict[str, object]:
    return {
        "public_registration_enabled": settings.PUBLIC_REGISTRATION_ENABLED,
        "requires_approval": settings.REGISTRATION_REQUIRES_APPROVAL,
        "invite_code_required": bool(settings.REGISTRATION_INVITE_CODE.strip()),
        "default_role": settings.effective_registered_user_role,
    }


async def register_user(
    db: AsyncSession,
    data: RegisterRequest,
) -> RegisterResponse:
    if not settings.PUBLIC_REGISTRATION_ENABLED:
        raise RegistrationDisabledError("Public registration is currently disabled.")

    configured_invite = settings.REGISTRATION_INVITE_CODE.strip()
    if configured_invite and data.invite_code != configured_invite:
        raise RegistrationInviteError("Registration invite code is invalid.")

    username = data.username.strip().lower()
    email = str(data.email).strip().lower()
    existing = await db.execute(
        select(User).where((User.email == email) | (User.username == username))
    )
    user = existing.scalar_one_or_none()
    if user is not None:
        if user.email == email:
            raise RegistrationConflictError("A user with that email already exists.")
        raise RegistrationConflictError("A user with that username already exists.")

    role = settings.effective_registered_user_role
    is_active = not settings.REGISTRATION_REQUIRES_APPROVAL
    registered = User(
        username=username,
        email=email,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=role,
        is_active=is_active,
        account_status="active" if is_active else "pending",
        registration_source="public_registration",
        approved_at=datetime.now(UTC) if is_active else None,
    )
    db.add(registered)
    await db.flush()
    await db.refresh(registered)
    status: Literal["active", "pending"] = (
        "active" if registered.is_active else "pending"
    )
    message = (
        "Account created. You can sign in now."
        if registered.is_active
        else "Account created and pending administrator approval."
    )
    return RegisterResponse(
        id=registered.id,
        username=registered.username,
        email=registered.email,
        role=registered.role,
        is_active=registered.is_active,
        account_status=status,
        message=message,
    )


def _inactive_login_message(account_status: str) -> str:
    if account_status == "pending":
        return "Account pending approval. Contact an administrator if needed."
    if account_status == "rejected":
        return "Account registration was not approved. Contact an administrator."
    return "Account disabled. Contact an administrator."
