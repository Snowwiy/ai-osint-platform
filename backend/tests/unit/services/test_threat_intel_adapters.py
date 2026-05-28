from __future__ import annotations

import json

import httpx
from app.services.threat_intel.abuseipdb_adapter import check_abuseipdb_ip
from app.services.threat_intel.virustotal_adapter import check_virustotal_reputation


async def test_abuseipdb_missing_api_key_is_provider_unavailable() -> None:
    result = await check_abuseipdb_ip("8.8.8.8", api_key="")

    assert result.provider == "abuseipdb"
    assert result.status == "provider_unavailable"
    assert result.risk_score == 0
    assert result.error_message == "missing_api_key"


async def test_virustotal_missing_api_key_is_provider_unavailable() -> None:
    result = await check_virustotal_reputation(
        "domain",
        "example.com",
        api_key="",
    )

    assert result.provider == "virustotal"
    assert result.status == "provider_unavailable"
    assert result.risk_score == 0
    assert result.error_message == "missing_api_key"


async def test_abuseipdb_success_parses_reputation_signals() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "data": {
                    "ipAddress": "8.8.8.8",
                    "abuseConfidenceScore": 62,
                    "totalReports": 5,
                    "countryCode": "US",
                    "isp": "Google LLC",
                    "usageType": "Data Center/Web Hosting/Transit",
                }
            },
        )
    )

    async with httpx.AsyncClient(transport=transport) as client:
        result = await check_abuseipdb_ip(
            "8.8.8.8",
            api_key="test-key",
            client=client,
        )

    assert result.status == "completed"
    assert result.risk_score == 62
    assert "abuse_confidence_score:62" in result.signals
    assert result.normalized["total_reports"] == 5


async def test_virustotal_domain_success_parses_last_analysis_stats() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "data": {
                    "id": "example.com",
                    "attributes": {
                        "reputation": -3,
                        "last_analysis_stats": {
                            "malicious": 2,
                            "suspicious": 1,
                            "harmless": 70,
                            "undetected": 10,
                        },
                    },
                }
            },
        )
    )

    async with httpx.AsyncClient(transport=transport) as client:
        result = await check_virustotal_reputation(
            "domain",
            "example.com",
            api_key="test-key",
            client=client,
        )

    assert result.provider == "virustotal"
    assert result.status == "completed"
    assert result.risk_score == 50
    assert result.normalized["malicious"] == 2
    assert result.normalized["suspicious"] == 1


async def test_virustotal_url_uses_url_identifier_and_handles_rate_limit() -> None:
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        return httpx.Response(429, content=json.dumps({"error": "rate limit"}))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await check_virustotal_reputation(
            "url",
            "https://example.com/login",
            api_key="test-key",
            client=client,
        )

    assert result.status == "rate_limited"
    assert result.error_message == "rate_limited"
    assert seen_paths == ["/api/v3/urls/aHR0cHM6Ly9leGFtcGxlLmNvbS9sb2dpbg"]
