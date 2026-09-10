from __future__ import annotations

import json

import httpx

from app.services.recon.provider_errors import provider_error_code


def test_provider_failures_have_stable_sanitized_codes() -> None:
    request = httpx.Request("GET", "https://provider.example.test/resource")
    response = httpx.Response(503, request=request)

    assert (
        provider_error_code(httpx.ReadTimeout("slow", request=request))
        == "provider_timeout"
    )
    assert (
        provider_error_code(
            httpx.HTTPStatusError("unavailable", request=request, response=response)
        )
        == "provider_http_error"
    )
    assert (
        provider_error_code(json.JSONDecodeError("invalid", "not-json", 0))
        == "provider_parse_error"
    )
