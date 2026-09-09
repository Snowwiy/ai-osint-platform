from __future__ import annotations

import json
import logging
import re
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings

_request_id: ContextVar[str] = ContextVar("request_id", default="")
_SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "api_key",
    "refresh_token",
    "access_token",
}
_SENSITIVE_VALUE_FIELDS = (
    "APP_SECRET_KEY",
    "DATABASE_URL",
    "REDIS_URL",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "REGISTRATION_INVITE_CODE",
    "ADMIN_PASSWORD",
    "SHODAN_API_KEY",
    "VT_API_KEY",
    "ABUSEIPDB_API_KEY",
    "OTX_API_KEY",
    "URLSCAN_API_KEY",
    "SECURITYTRAILS_API_KEY",
    "CENSYS_API_ID",
    "CENSYS_SECRET",
    "HIBP_API_KEY",
    "GITHUB_TOKEN",
)
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")
_AUTHORIZATION_PATTERN = re.compile(
    r"(?i)(\bauthorization\s*[:=]\s*)(?:bearer|basic)\s+[^\s,;]+"
)
_CREDENTIAL_URL_PATTERN = re.compile(
    r"(?i)(\b(?:postgres(?:ql)?(?:\+[a-z0-9]+)?|redis)://[^:/@\s]+:)"
    r"[^@/\s]+@"
)
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)(\b(?:password|secret(?:_key)?|api[_-]?key|token|invite[_-]?code)"
    r"\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)


def set_request_id(value: str) -> Token[str]:
    return _request_id.set(value)


def reset_request_id(token: Token[str]) -> None:
    _request_id.reset(token)


def get_request_id() -> str:
    return _request_id.get()


def configure_logging() -> None:
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id() or None,
        }
        for key in (
            "action",
            "duration_ms",
            "endpoint",
            "failure_reason",
            "investigation_id",
            "method",
            "status_code",
            "user_id",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(_redact(payload), default=str, sort_keys=True)


def _redact(value: object) -> object:
    if isinstance(value, dict):
        redacted: dict[str, object] = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(sensitive in lowered for sensitive in _SENSITIVE_KEYS)


def _redact_text(value: str) -> str:
    redacted = value
    for field_name in _SENSITIVE_VALUE_FIELDS:
        configured_value = getattr(settings, field_name, "")
        if configured_value and len(configured_value) >= 4:
            redacted = redacted.replace(configured_value, "[REDACTED]")
    redacted = _AUTHORIZATION_PATTERN.sub(r"\1[REDACTED]", redacted)
    redacted = _BEARER_PATTERN.sub("Bearer [REDACTED]", redacted)
    redacted = _CREDENTIAL_URL_PATTERN.sub(r"\1[REDACTED]@", redacted)
    return _SECRET_ASSIGNMENT_PATTERN.sub(r"\1[REDACTED]", redacted)
