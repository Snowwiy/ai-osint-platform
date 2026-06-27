from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db as get_db
from app.models.user import User
from app.schemas.governance import FeatureFlagName

_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except jwt.InvalidTokenError:
        raise credentials_exception from None

    if payload.get("type") != "access" or not payload.get("jti"):
        raise credentials_exception

    sub = payload.get("sub")
    if not sub:
        raise credentials_exception

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise credentials_exception from None

    user = await db.get(User, user_id)
    if user is None:
        raise credentials_exception
    if not user.is_active or user.account_status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_inactive_account_message(user.account_status),
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def _inactive_account_message(account_status: str) -> str:
    if account_status == "pending":
        return "Account pending approval. Contact an administrator if needed."
    if account_status == "rejected":
        return "Account registration was not approved. Contact an administrator."
    return "Account disabled. Contact an administrator."


def require_role(*roles: str) -> Callable[..., Awaitable[User]]:
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of these roles: {list(roles)}",
            )
        return current_user

    return _check


def require_feature(feature: FeatureFlagName) -> Callable[..., Awaitable[None]]:
    async def _check(db: AsyncSession = Depends(get_db)) -> None:
        from app.services.governance import (
            FeatureDisabledError,
            ensure_feature_enabled,
        )

        try:
            await ensure_feature_enabled(db, feature)
        except FeatureDisabledError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "feature_disabled",
                    "message": str(exc),
                    "feature": feature,
                },
            ) from exc

    return _check


async def get_redis(request: Request) -> Any:
    return request.app.state.redis
