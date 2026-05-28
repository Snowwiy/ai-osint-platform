from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import jwt as pyjwt
import pytest
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import create_access_token, create_refresh_token
from app.models.user import User
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials


def _make_user(*, role: str = "analyst", is_active: bool = True) -> User:
    return User(
        id=uuid.uuid4(),
        username="testuser",
        email="test@example.com",
        hashed_password="unused",
        role=role,
        is_active=is_active,
    )


async def _invoke_get_current_user(token: str, db_user: User | None) -> User:
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=db_user)
    return await get_current_user(credentials=credentials, db=mock_db)


async def test_get_current_user_returns_user_for_valid_token() -> None:
    user = _make_user()
    token = create_access_token(user_id=str(user.id), role="analyst")
    result = await _invoke_get_current_user(token, db_user=user)
    assert result is user


async def test_get_current_user_raises_401_for_expired_token() -> None:
    expired = pyjwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": "access",
            "exp": datetime.now(UTC) - timedelta(seconds=1),
        },
        settings.APP_SECRET_KEY,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc_info:
        await _invoke_get_current_user(expired, db_user=_make_user())
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


async def test_get_current_user_raises_401_for_refresh_token() -> None:
    token, _ = create_refresh_token(user_id=str(uuid.uuid4()))
    with pytest.raises(HTTPException) as exc_info:
        await _invoke_get_current_user(token, db_user=_make_user())
    assert exc_info.value.status_code == 401


async def test_get_current_user_raises_401_when_user_not_in_db() -> None:
    token = create_access_token(user_id=str(uuid.uuid4()), role="analyst")
    with pytest.raises(HTTPException) as exc_info:
        await _invoke_get_current_user(token, db_user=None)
    assert exc_info.value.status_code == 401


async def test_get_current_user_raises_401_for_inactive_user() -> None:
    user = _make_user(is_active=False)
    token = create_access_token(user_id=str(user.id), role="analyst")
    with pytest.raises(HTTPException) as exc_info:
        await _invoke_get_current_user(token, db_user=user)
    assert exc_info.value.status_code == 401
    assert "deactivated" in exc_info.value.detail.lower()
