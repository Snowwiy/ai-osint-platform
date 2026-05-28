from __future__ import annotations

import base64
from typing import Literal

import httpx

from app.core.config import settings
from app.schemas.recon import JsonProperties
from app.schemas.threat_intel import ProviderResult
from app.services.threat_intel.scoring import confidence_from_score, verdict_from_score

_VT_BASE_URL = "https://www.virustotal.com/api/v3"
_TIMEOUT_SECONDS = 10.0
_SupportedTarget = Literal["domain", "ip", "url"]


async def check_virustotal_reputation(
    target_type: _SupportedTarget,
    target_value: str,
    *,
    api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> ProviderResult:
    key = settings.VT_API_KEY if api_key is None else api_key
    if not key:
        return _provider_error("provider_unavailable", "missing_api_key")

    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)
    try:
        response = await active_client.get(
            _vt_url(target_type, target_value),
            headers={"x-apikey": key, "Accept": "application/json"},
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
    attributes = _attributes(payload)
    stats = attributes.get("last_analysis_stats", {})
    malicious = _int_from_mapping(stats, "malicious")
    suspicious = _int_from_mapping(stats, "suspicious")
    harmless = _int_from_mapping(stats, "harmless")
    undetected = _int_from_mapping(stats, "undetected")
    score = min(100, malicious * 20 + suspicious * 10)
    normalized: JsonProperties = {
        "malicious": malicious,
        "suspicious": suspicious,
        "harmless": harmless,
        "undetected": undetected,
        "reputation": _int_or_none(attributes.get("reputation")),
    }
    signals = []
    if malicious:
        signals.append(f"malicious:{malicious}")
    if suspicious:
        signals.append(f"suspicious:{suspicious}")

    return ProviderResult(
        provider="virustotal",
        status="completed",
        risk_score=score,
        confidence=confidence_from_score(score),
        verdict=verdict_from_score(score),
        signals=signals,
        normalized=_drop_none(normalized),
        raw_data=payload if isinstance(payload, dict) else {},
    )


def _vt_url(target_type: _SupportedTarget, target_value: str) -> str:
    if target_type == "ip":
        return f"{_VT_BASE_URL}/ip_addresses/{target_value}"
    if target_type == "domain":
        return f"{_VT_BASE_URL}/domains/{target_value}"
    return f"{_VT_BASE_URL}/urls/{_url_identifier(target_value)}"


def _url_identifier(url: str) -> str:
    encoded = base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def _provider_error(status: str, message: str) -> ProviderResult:
    return ProviderResult(
        provider="virustotal",
        status=status,  # type: ignore[arg-type]
        risk_score=0,
        confidence="low",
        verdict="unknown",
        error_message=message,
    )


def _attributes(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return {}
    attributes = data.get("attributes", {})
    return attributes if isinstance(attributes, dict) else {}


def _int_from_mapping(value: object, key: str) -> int:
    if not isinstance(value, dict):
        return 0
    candidate = value.get(key)
    return candidate if isinstance(candidate, int) else 0


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _drop_none(properties: JsonProperties) -> JsonProperties:
    return {key: value for key, value in properties.items() if value is not None}
