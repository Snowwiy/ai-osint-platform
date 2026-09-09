from __future__ import annotations

import json
import logging

from app.core.config import settings
from app.core.logging import JsonLogFormatter, _redact
from app.db.session import engine


def test_structured_fields_redact_nested_sensitive_values() -> None:
    payload = {
        "safe": "visible",
        "nested": {"access_token": "token-value", "count": 2},
    }

    assert _redact(payload) == {
        "safe": "visible",
        "nested": {"access_token": "[REDACTED]", "count": 2},
    }


def test_formatter_redacts_secrets_embedded_in_message(monkeypatch) -> None:
    secret_key = "unit-test-secret-key-that-must-not-appear"
    database_url = "postgresql+asyncpg://tester:db-password@database:5432/test"
    monkeypatch.setattr(settings, "APP_SECRET_KEY", secret_key)
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)
    record = logging.LogRecord(
        name="security-test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=(
            f"key={secret_key} db={database_url} "
            "Authorization: Bearer header-token password=plain-password"
        ),
        args=(),
        exc_info=None,
    )

    formatted = JsonLogFormatter().format(record)
    payload = json.loads(formatted)

    assert secret_key not in formatted
    assert "db-password" not in formatted
    assert "header-token" not in formatted
    assert "plain-password" not in formatted
    assert "[REDACTED]" in payload["message"]


def test_sqlalchemy_parameter_echo_is_disabled() -> None:
    assert engine.echo is False
