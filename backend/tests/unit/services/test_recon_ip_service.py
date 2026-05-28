from __future__ import annotations

import httpx
from app.services.recon.ip_service import collect_ip_intelligence


async def test_ip_enrichment_parses_asn_and_network_metadata() -> None:
    payload = {
        "name": "EXAMPLE-NET",
        "handle": "NET-203-0-113-0-1",
        "country": "US",
        "startAddress": "203.0.113.0",
        "endAddress": "203.0.113.255",
        "cidr0_cidrs": [{"v4prefix": "203.0.113.0", "length": 24}],
        "arin_originas0_originautnums": [64500],
        "entities": [
            {
                "vcardArray": [
                    "vcard",
                    [["org", {}, "text", "Example Network Org"]],
                ]
            }
        ],
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/ip/203.0.113.10"
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(
        base_url="https://rdap.org",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = await collect_ip_intelligence("203.0.113.10", client=client)

    assert result.asn == "AS64500"
    assert result.provider == "EXAMPLE-NET"
    assert result.organization == "Example Network Org"
    assert result.network_range == "203.0.113.0 - 203.0.113.255"
    assert result.cidrs == ["203.0.113.0/24"]
