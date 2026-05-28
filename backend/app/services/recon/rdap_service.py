from __future__ import annotations

import asyncio
from importlib import import_module
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

from app.schemas.recon import RDAPResult, ReconError

_RDAP_BASE_URL = "https://rdap.org"
_TIMEOUT_SECONDS = 8.0


@dataclass(frozen=True)
class WhoisFallbackData:
    registrar: str | None = None
    registration_date: str | None = None
    expiration_date: str | None = None
    abuse_contacts: list[str] = field(default_factory=list)
    organizations: list[str] = field(default_factory=list)


async def collect_rdap_intelligence(
    value: str,
    *,
    target_type: Literal["domain", "ip"],
    client: httpx.AsyncClient | None = None,
) -> RDAPResult:
    query = value.strip().lower().rstrip(".")
    errors: list[ReconError] = []
    owned_client = client is None

    if client is None:
        client = httpx.AsyncClient(base_url=_RDAP_BASE_URL, timeout=_TIMEOUT_SECONDS)

    try:
        payload = await _fetch_rdap_payload(query, target_type, client)
    except Exception as exc:
        payload = None
        errors.append(ReconError(source="rdap", message=_safe_error(exc)))
    finally:
        if owned_client:
            await client.aclose()

    if payload is not None:
        parsed = _parse_rdap_payload(query, target_type, payload)
        parsed.errors.extend(errors)
        return parsed

    if target_type == "domain":
        try:
            whois_data = await _lookup_whois_domain(query)
        except Exception as exc:
            errors.append(ReconError(source="whois", message=_safe_error(exc)))
        else:
            if whois_data is not None:
                return RDAPResult(
                    query=query,
                    target_type=target_type,
                    source="whois",
                    registrar=whois_data.registrar,
                    registration_date=whois_data.registration_date,
                    expiration_date=whois_data.expiration_date,
                    abuse_contacts=sorted(set(whois_data.abuse_contacts)),
                    organizations=sorted(set(whois_data.organizations)),
                    errors=errors,
                )

    return RDAPResult(
        query=query,
        target_type=target_type,
        source="none",
        errors=errors or [ReconError(source="rdap", message="No RDAP data returned")],
    )


async def _fetch_rdap_payload(
    value: str,
    target_type: str,
    client: httpx.AsyncClient,
) -> dict[str, Any] | None:
    response = await client.get(f"{_RDAP_BASE_URL}/{target_type}/{value}")
    if response.status_code >= 400:
        return None
    data = response.json()
    return data if isinstance(data, dict) else None


async def _lookup_whois_domain(domain: str) -> WhoisFallbackData | None:
    return await asyncio.to_thread(_lookup_whois_domain_sync, domain)


def _lookup_whois_domain_sync(domain: str) -> WhoisFallbackData | None:
    try:
        whois = import_module("whois")
    except Exception:
        return None

    data = whois.whois(domain)
    if not data:
        return None
    emails = _coerce_list(getattr(data, "emails", None))
    orgs = _coerce_list(
        getattr(data, "org", None) or getattr(data, "registrant_org", None)
    )
    return WhoisFallbackData(
        registrar=_string_or_none(getattr(data, "registrar", None)),
        registration_date=_date_or_none(getattr(data, "creation_date", None)),
        expiration_date=_date_or_none(getattr(data, "expiration_date", None)),
        abuse_contacts=[email for email in emails if "abuse" in email.lower()],
        organizations=orgs,
    )


def _parse_rdap_payload(
    query: str,
    target_type: Literal["domain", "ip"],
    payload: dict[str, Any],
) -> RDAPResult:
    entities = payload.get("entities")
    entity_list = entities if isinstance(entities, list) else []
    registrar = _first_entity_value(entity_list, "registrar", ("fn", "org"))
    organizations = sorted(
        {
            org
            for role in ("registrant", "administrative", "technical")
            for org in _entity_values(entity_list, role, ("org", "fn"))
        }
    )
    abuse_contacts = sorted(set(_entity_values(entity_list, "abuse", ("email",))))
    cidrs = _parse_cidrs(payload)
    asn_references = _parse_asn_references(payload)

    return RDAPResult(
        query=query,
        target_type=target_type,
        source="rdap",
        registrar=registrar,
        registration_date=_event_date(payload, ("registration", "last changed")),
        expiration_date=_event_date(payload, ("expiration",)),
        abuse_contacts=abuse_contacts,
        organizations=organizations,
        cidrs=cidrs,
        asn_references=asn_references,
        raw_handle=_string_or_none(payload.get("handle")),
    )


def _event_date(payload: dict[str, Any], names: tuple[str, ...]) -> str | None:
    events = payload.get("events")
    if not isinstance(events, list):
        return None
    for event in events:
        if not isinstance(event, dict):
            continue
        action = str(event.get("eventAction", "")).lower()
        if action in names and isinstance(event.get("eventDate"), str):
            return str(event["eventDate"])
    return None


def _entity_values(
    entities: list[Any],
    role: str,
    fields: tuple[str, ...],
) -> list[str]:
    values: list[str] = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        roles = entity.get("roles")
        if not isinstance(roles, list) or role not in roles:
            continue
        values.extend(_vcard_values(entity.get("vcardArray"), fields))
    return [_normalize_space(value) for value in values if value]


def _first_entity_value(
    entities: list[Any],
    role: str,
    fields: tuple[str, ...],
) -> str | None:
    values = _entity_values(entities, role, fields)
    return values[0] if values else None


def _vcard_values(vcard: Any, fields: tuple[str, ...]) -> list[str]:
    if not isinstance(vcard, list) or len(vcard) != 2 or not isinstance(vcard[1], list):
        return []
    values: list[str] = []
    for item in vcard[1]:
        if not isinstance(item, list) or len(item) < 4:
            continue
        if item[0] in fields and isinstance(item[3], str):
            values.append(item[3])
    return values


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


def _parse_asn_references(payload: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key, raw in payload.items():
        if "asn" not in key.lower() and "autnum" not in key.lower():
            continue
        if isinstance(raw, list):
            values.extend(str(item) for item in raw)
        elif isinstance(raw, str | int):
            values.append(str(raw))
    return sorted(set(values))


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list | tuple | set):
        return [_normalize_space(str(item)) for item in value if item]
    return [_normalize_space(str(value))]


def _date_or_none(value: Any) -> str | None:
    if isinstance(value, list | tuple):
        value = value[0] if value else None
    if value is None:
        return None
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return str(isoformat())
    return str(value)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    clean = _normalize_space(str(value))
    return clean or None


def _normalize_space(value: str) -> str:
    return " ".join(value.split())


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "RDAP request timed out"
    return exc.__class__.__name__
