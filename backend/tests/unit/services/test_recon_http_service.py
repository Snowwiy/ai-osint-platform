from __future__ import annotations

import httpx
from app.services.recon.http_service import inspect_http_metadata


async def test_http_metadata_success_collects_headers_and_security_fields() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "server": "nginx",
                "content-type": "text/html",
                "strict-transport-security": "max-age=31536000",
                "content-security-policy": "default-src 'self'",
                "set-cookie": "sid=abc; HttpOnly",
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await inspect_http_metadata("https://example.com", client=client)

    assert result.final_url == "https://example.com"
    assert result.server == "nginx"
    assert result.security_headers.hsts == "max-age=31536000"
    assert result.cookies[0].name == "sid"
    assert result.errors == []


async def test_http_metadata_timeout_is_graceful() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await inspect_http_metadata("https://example.com", client=client)

    assert result.status_code is None
    assert result.errors
    assert result.errors[0].source == "http"
