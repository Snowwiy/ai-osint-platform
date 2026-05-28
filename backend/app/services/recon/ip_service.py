from __future__ import annotations

import ipaddress
from typing import Any

import httpx

from app.schemas.recon import IPResult, ReconError

_RDAP_BASE_URL = "https://rdap.org"
_TIMEOUT_SECONDS = 8.0


async def collect_ip_intelligence(
    ip_address: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> IPResult:
    normalized = str(ipaddress.ip_address(ip_address.strip()))
    owned_client = client is None
    errors: list[ReconError] = []

    if client is None:
        client = httpx.AsyncClient(base_url=_RDAP_BASE_URL, timeout=_TIMEOUT_SECONDS)

    try:
        response = await client.get(f"/ip/{normalized}")
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        payload = {}
        errors.append(ReconError(source="ip-rdap", message=_safe_error(exc)))
    finally:
        if owned_client:
            await client.aclose()

    data = payload if isinstance(payload, dict) else {}
    cidrs = _parse_cidrs(data)
    start = _string_or_none(data.get("startAddress"))
    end = _string_or_none(data.get("endAddress"))
    network_range = (
        f"{start} - {end}" if start and end else (cidrs[0] if cidrs else None)
    )
    organization = _first_entity_org(data.get("entities"))

    return IPResult(
        ip_address=normalized,
        asn=_parse_asn(data),
        provider=_string_or_none(data.get("name")),
        organization=organization or _string_or_none(data.get("handle")),
        country=_string_or_none(data.get("country")),
        network_range=network_range,
        cidrs=cidrs,
        errors=errors,
    )


def _parse_cidrs(payload: dict[str, Any]) -> list[str]:
    cidrs = payload.get("cidr0_cidrs")
    if not isinstance(cidrs, list):
        return []
    result: list[str] = []
    for item in cidrs:
        if not isinstance(item, dict):
            continue
        prefix = item.get("v4prefix") or item.get("v6prefix")
        length = item.get("length")
        if prefix is not None and length is not None:
            result.append(f"{prefix}/{length}")
    return sorted(set(result))


def _parse_asn(payload: dict[str, Any]) -> str | None:
    for key, raw in payload.items():
        lowered = key.lower()
        if "asn" not in lowered and "autnum" not in lowered:
            continue
        if isinstance(raw, list) and raw:
            return f"AS{raw[0]}"
        if isinstance(raw, int | str):
            value = str(raw)
            return value if value.upper().startswith("AS") else f"AS{value}"
    return None


def _first_entity_org(entities: Any) -> str | None:
    if not isinstance(entities, list):
        return None
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        value = _vcard_first(entity.get("vcardArray"), ("org", "fn"))
        if value:
            return value
    return None


def _vcard_first(vcard: Any, fields: tuple[str, ...]) -> str | None:
    if not isinstance(vcard, list) or len(vcard) != 2 or not isinstance(vcard[1], list):
        return None
    for item in vcard[1]:
        if (
            isinstance(item, list)
            and len(item) >= 4
            and item[0] in fields
            and isinstance(item[3], str)
        ):
            return " ".join(item[3].split())
    return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    clean = str(value).strip()
    return clean or None


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "IP RDAP request timed out"
    return exc.__class__.__name__
