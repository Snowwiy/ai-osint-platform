from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(payload: dict[str, Any], expire_delta: timedelta) -> str:
    now = datetime.now(UTC)
    data = payload.copy()
    data.update({"iat": now, "exp": now + expire_delta})
    return jwt.encode(data, settings.APP_SECRET_KEY, algorithm="HS256")


def create_access_token(user_id: str, role: str) -> str:
    return _create_token(
        {
            "sub": user_id,
            "role": role,
            "type": "access",
            "jti": str(uuid.uuid4()),
        },
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: str) -> tuple[str, str]:
    jti = str(uuid.uuid4())
    token = _create_token(
        {"sub": user_id, "type": "refresh", "jti": jti},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return token, jti


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.APP_SECRET_KEY, algorithms=["HS256"])
