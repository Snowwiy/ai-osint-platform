from __future__ import annotations

import httpx
import pytest
from app.services.recon import rdap_service


async def test_rdap_domain_success_parses_core_fields() -> None:
    payload = {
        "ldhName": "example.com",
        "events": [
            {"eventAction": "registration", "eventDate": "2020-01-01T00:00:00Z"},
            {"eventAction": "expiration", "eventDate": "2030-01-01T00:00:00Z"},
        ],
        "entities": [
            {
                "roles": ["registrar"],
                "vcardArray": ["vcard", [["fn", {}, "text", "Example Registrar"]]],
            },
            {
                "roles": ["abuse"],
                "vcardArray": ["vcard", [["email", {}, "text", "abuse@example.net"]]],
            },
            {
                "roles": ["registrant"],
                "vcardArray": ["vcard", [["org", {}, "text", "Example Org"]]],
            },
        ],
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/domain/example.com"
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await rdap_service.collect_rdap_intelligence(
            "example.com",
            target_type="domain",
            client=client,
        )

    assert result.source == "rdap"
    assert result.registrar == "Example Registrar"
    assert result.abuse_contacts == ["abuse@example.net"]
    assert result.organizations == ["Example Org"]


async def test_rdap_falls_back_to_whois_for_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_rdap(_value: str, _target_type: str, _client: httpx.AsyncClient):
        return None

    async def fake_whois(_domain: str):
        return rdap_service.WhoisFallbackData(
            registrar="Fallback Registrar",
            registration_date="2021-02-03T00:00:00Z",
            expiration_date="2031-02-03T00:00:00Z",
            abuse_contacts=["abuse@fallback.example"],
            organizations=["Fallback Org"],
        )

    monkeypatch.setattr(rdap_service, "_fetch_rdap_payload", fake_rdap)
    monkeypatch.setattr(rdap_service, "_lookup_whois_domain", fake_whois)

    result = await rdap_service.collect_rdap_intelligence(
        "example.com",
        target_type="domain",
    )

    assert result.source == "whois"
    assert result.registrar == "Fallback Registrar"
    assert result.organizations == ["Fallback Org"]
