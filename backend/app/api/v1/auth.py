from __future__ import annotations

import hashlib

from fastapi import (
    APIRouter,
    Body,
    Cookie,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db, get_redis
from app.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    LogoutRequest,
    PasswordChangeRequest,
    RefreshRequest,
    TokenResponse,
    UserBrief,
    UserProfile,
)
from app.services.audit import record_event
from app.services.auth import (
    InactiveUserError,
    InvalidCredentialsError,
    RedisLike,
    TokenError,
    change_password,
    login,
    logout,
    refresh_tokens,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        max_age=7 * 24 * 60 * 60,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    response_model_exclude_none=True,
)
async def login_endpoint(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: RedisLike = Depends(get_redis),
) -> TokenResponse:
    identifier = str(body.email or body.username)
    await _enforce_auth_bruteforce(redis, identifier, request, db)
    try:
        user, access_token, refresh_token = await login(
            db,
            redis,
            identifier,
            body.password,
        )
    except InactiveUserError as exc:
        await _record_failed_login(redis, identifier, request)
        raise HTTPException(status_code=403, detail="Account disabled") from exc
    except InvalidCredentialsError as exc:
        await _record_failed_login(redis, identifier, request)
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password.",
        ) from exc

    await _clear_failed_login(redis, identifier, request)
    _set_refresh_cookie(response, refresh_token)
    await record_event(
        db,
        action="auth.login_success",
        actor_id=user.id,
        resource_type="auth",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"identifier": identifier},
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserBrief.model_validate(user),
    )


async def _enforce_auth_bruteforce(
    redis: RedisLike,
    identifier: str,
    request: Request,
    db: AsyncSession,
) -> None:
    attempts = await _failed_login_attempts(redis, identifier, request)
    if attempts < settings.AUTH_FAILURE_LIMIT:
        return
    await record_event(
        db,
        action="auth.bruteforce_blocked",
        resource_type="auth",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={"identifier": _identifier_fingerprint(identifier), "attempts": attempts},
    )
    raise HTTPException(
        status_code=429,
        detail="Too many failed login attempts. Try again later.",
    )


async def _record_failed_login(
    redis: RedisLike,
    identifier: str,
    request: Request,
) -> None:
    key = _failed_login_key(identifier, request)
    attempts = await _failed_login_attempts(redis, identifier, request)
    await redis.setex(
        key,
        settings.AUTH_FAILURE_WINDOW_SECONDS,
        str(attempts + 1),
    )


async def _clear_failed_login(
    redis: RedisLike,
    identifier: str,
    request: Request,
) -> None:
    await redis.delete(_failed_login_key(identifier, request))


async def _failed_login_attempts(
    redis: RedisLike,
    identifier: str,
    request: Request,
) -> int:
    raw_attempts = await redis.get(_failed_login_key(identifier, request))
    try:
        return int(raw_attempts or "0")
    except ValueError:
        return 0


def _failed_login_key(identifier: str, request: Request) -> str:
    ip_address = request.client.host if request.client else "unknown"
    return f"auth:failed:{ip_address}:{_identifier_fingerprint(identifier)}"


def _identifier_fingerprint(identifier: str) -> str:
    normalized = identifier.strip().lower().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:24]


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    response_model_exclude_none=True,
)
async def refresh_endpoint(
    response: Response,
    body: RefreshRequest | None = Body(default=None),
    refresh_cookie: str | None = Cookie(default=None, alias="refresh_token"),
    db: AsyncSession = Depends(get_db),
    redis: RedisLike = Depends(get_redis),
) -> AccessTokenResponse:
    refresh_token = (body.refresh_token if body else None) or refresh_cookie
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token required")
    try:
        access_token, new_refresh_token = await refresh_tokens(db, redis, refresh_token)
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    _set_refresh_cookie(response, new_refresh_token)
    return AccessTokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_endpoint(
    response: Response,
    body: LogoutRequest | None = Body(default=None),
    refresh_cookie: str | None = Cookie(default=None, alias="refresh_token"),
    redis: RedisLike = Depends(get_redis),
) -> None:
    refresh_token = (body.refresh_token if body else None) or refresh_cookie
    if refresh_token:
        await logout(redis, refresh_token)
    response.delete_cookie("refresh_token")
    return None


@router.get("/me", response_model=UserProfile)
async def me_endpoint(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password_endpoint(
    body: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await change_password(
            db,
            current_user,
            body.current_password,
            body.new_password,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect",
        ) from exc
