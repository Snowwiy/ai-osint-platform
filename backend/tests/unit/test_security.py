from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest
from app.core.config import settings
from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_password_produces_bcrypt_hash() -> None:
    hashed = hash_password("SecurePass123!")
    assert hashed.startswith("$2b$")
    assert hashed != "SecurePass123!"


def test_hash_password_is_different_each_call() -> None:
    h1 = hash_password("SamePassword1!")
    h2 = hash_password("SamePassword1!")
    assert h1 != h2


def test_verify_password_correct_password() -> None:
    hashed = hash_password("CorrectPass123!")
    assert verify_password("CorrectPass123!", hashed) is True


def test_verify_password_wrong_password() -> None:
    hashed = hash_password("CorrectPass123!")
    assert verify_password("WrongPass456!", hashed) is False


def test_verify_password_empty_string_fails() -> None:
    hashed = hash_password("ValidPass123!")
    assert verify_password("", hashed) is False


def test_create_access_token_has_required_claims() -> None:
    token = create_access_token(user_id="user-abc", role="analyst")
    payload = decode_token(token)
    assert payload["sub"] == "user-abc"
    assert payload["role"] == "analyst"
    assert payload["type"] == "access"
    assert "jti" in payload
    assert "exp" in payload
    assert "iat" in payload


def test_create_access_token_expires_in_30_minutes() -> None:
    token = create_access_token(user_id="user-abc", role="admin")
    payload = decode_token(token)
    now = datetime.now(UTC)
    expected_exp = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    assert abs(payload["exp"] - expected_exp.timestamp()) < 5


def test_create_access_token_unique_jti_each_call() -> None:
    t1 = create_access_token("user-1", "analyst")
    t2 = create_access_token("user-1", "analyst")
    p1 = decode_token(t1)
    p2 = decode_token(t2)
    assert p1["jti"] != p2["jti"]


def test_create_refresh_token_returns_token_and_jti() -> None:
    token, jti = create_refresh_token(user_id="user-xyz")
    assert isinstance(token, str)
    assert isinstance(jti, str)
    assert len(jti) == 36


def test_refresh_token_jti_matches_payload() -> None:
    token, jti = create_refresh_token(user_id="user-xyz")
    payload = decode_token(token)
    assert payload["jti"] == jti


def test_refresh_token_type_is_refresh() -> None:
    token, _ = create_refresh_token(user_id="user-xyz")
    payload = decode_token(token)
    assert payload["type"] == "refresh"
    assert "role" not in payload


def test_decode_token_raises_on_expired_token() -> None:
    expired = pyjwt.encode(
        {
            "sub": "user-1",
            "type": "access",
            "exp": datetime.now(UTC) - timedelta(seconds=1),
        },
        settings.APP_SECRET_KEY,
        algorithm="HS256",
    )
    with pytest.raises(pyjwt.ExpiredSignatureError):
        decode_token(expired)


def test_decode_token_raises_on_tampered_signature() -> None:
    token = create_access_token("user-1", "analyst")
    tampered = token[:-8] + "XXXXXXXX"
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_token(tampered)


def test_decode_token_raises_on_wrong_secret() -> None:
    token = pyjwt.encode(
        {"sub": "user-1", "exp": datetime.now(UTC) + timedelta(hours=1)},
        "wrong-secret-key",
        algorithm="HS256",
    )
    with pytest.raises(pyjwt.InvalidSignatureError):
        decode_token(token)
