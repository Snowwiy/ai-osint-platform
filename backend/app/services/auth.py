from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User

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
    pass


class TokenError(AuthError):
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
    if not user.is_active:
        raise InactiveUserError("Account disabled")
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
