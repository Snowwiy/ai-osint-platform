from __future__ import annotations

import httpx
from app.services.recon.certificate_service import collect_certificate_intelligence


async def test_crtsh_parsing_deduplicates_subdomains() -> None:
    payload = [
        {
            "id": 123,
            "issuer_name": "CN=Example CA",
            "name_value": "www.example.com\napi.example.com\n*.api.example.com",
            "not_after": "2030-01-01T00:00:00",
        },
        {
            "id": 124,
            "issuer_name": "CN=Example CA",
            "name_value": "api.example.com\nother.test",
            "not_after": "2030-06-01T00:00:00",
        },
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/"
        assert request.url.params["output"] == "json"
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(
        base_url="https://crt.sh",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = await collect_certificate_intelligence("example.com", client=client)

    assert [cert.certificate_id for cert in result.certificates] == ["123", "124"]
    assert result.subdomains == ["api.example.com", "www.example.com"]
    assert result.errors == []
