from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core import logging as logging_module
from app.core.config import settings
from app.core.logging import JsonLogFormatter, _redact
from app.db.session import engine
from app.native_runtime import NativePaths


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
    agent_token = "unit-test-lan-agent-token"
    monkeypatch.setattr(settings, "APP_SECRET_KEY", secret_key)
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)
    monkeypatch.setattr(settings, "LAN_AGENT_TOKEN", agent_token)
    record = logging.LogRecord(
        name="security-test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=(
            f"key={secret_key} db={database_url} agent={agent_token} "
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
    assert agent_token not in formatted
    assert "[REDACTED]" in payload["message"]


def test_sqlalchemy_parameter_echo_is_disabled() -> None:
    assert engine.echo is False


def test_native_components_use_separate_external_rotating_logs(
    monkeypatch, tmp_path: Path
) -> None:
    paths = NativePaths(
        config=tmp_path / "config", data=tmp_path / "data",
        state=tmp_path, logs=tmp_path / "logs",
        reports=tmp_path / "reports", runtime=tmp_path / "runtime",
    )
    monkeypatch.setattr(logging_module, "is_native_package", lambda: True)
    monkeypatch.setattr(logging_module, "native_paths", lambda: paths)
    root = logging.getLogger()
    old_handlers = root.handlers[:]
    old_level = root.level
    try:
        logging_module.configure_logging("backend")
        backend_handler = root.handlers[0]
        logging_module.configure_logging("worker")
        worker_handler = root.handlers[0]
        assert Path(backend_handler.baseFilename) == paths.logs / "backend.log"
        assert Path(worker_handler.baseFilename) == paths.logs / "worker.log"
        assert backend_handler.maxBytes == worker_handler.maxBytes == 2_000_000
    finally:
        for handler in root.handlers:
            handler.close()
        root.handlers = old_handlers
        root.setLevel(old_level)
