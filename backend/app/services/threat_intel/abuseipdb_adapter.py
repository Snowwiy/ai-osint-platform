from __future__ import annotations

import httpx

from app.core.config import settings
from app.schemas.recon import JsonProperties
from app.schemas.threat_intel import ProviderResult
from app.services.threat_intel.scoring import confidence_from_score, verdict_from_score

_ABUSEIPDB_URL = "https://api.abuseipdb.com/api/v2/check"
_TIMEOUT_SECONDS = 10.0


async def check_abuseipdb_ip(
    ip_address: str,
    *,
    api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> ProviderResult:
    key = settings.ABUSEIPDB_API_KEY if api_key is None else api_key
    if not key:
        return _provider_error("provider_unavailable", "missing_api_key")

    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)
    try:
        response = await active_client.get(
            _ABUSEIPDB_URL,
            params={"ipAddress": ip_address, "maxAgeInDays": "90"},
            headers={"Key": key, "Accept": "application/json"},
        )
    except httpx.TimeoutException:
        return _provider_error("failed", "timeout")
    except httpx.HTTPError as exc:
        return _provider_error("failed", exc.__class__.__name__)
    finally:
        if owns_client:
            await active_client.aclose()

    if response.status_code == 429:
        return _provider_error("rate_limited", "rate_limited")
    if response.status_code >= 400:
        return _provider_error("failed", f"http_{response.status_code}")

    payload = response.json()
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    score = _int_value(data.get("abuseConfidenceScore"))
    reports = _int_value(data.get("totalReports"))
    normalized: JsonProperties = {
        "abuse_confidence_score": score,
        "total_reports": reports,
        "country_code": _str_or_none(data.get("countryCode")),
        "isp": _str_or_none(data.get("isp")),
        "usage_type": _str_or_none(data.get("usageType")),
        "domain": _str_or_none(data.get("domain")),
    }
    signals = [f"abuse_confidence_score:{score}", f"total_reports:{reports}"]

    return ProviderResult(
        provider="abuseipdb",
        status="completed",
        risk_score=score,
        confidence=confidence_from_score(score),
        verdict=verdict_from_score(score),
        signals=signals,
        normalized=_drop_none(normalized),
        raw_data=payload if isinstance(payload, dict) else {},
    )


def _provider_error(status: str, message: str) -> ProviderResult:
    return ProviderResult(
        provider="abuseipdb",
        status=status,  # type: ignore[arg-type]
        risk_score=0,
        confidence="low",
        verdict="unknown",
        error_message=message,
    )


def _int_value(value: object) -> int:
    return value if isinstance(value, int) else 0


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _drop_none(properties: JsonProperties) -> JsonProperties:
    return {key: value for key, value in properties.items() if value is not None}
