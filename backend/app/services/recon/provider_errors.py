from __future__ import annotations

import json

import httpx


def provider_error_code(exc: Exception) -> str:
    """Return a stable, sanitized provider failure code."""
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return "provider_timeout"
    if isinstance(exc, json.JSONDecodeError):
        return "provider_parse_error"
    if isinstance(exc, (httpx.HTTPStatusError, httpx.RequestError)):
        return "provider_http_error"
    return "provider_error"
