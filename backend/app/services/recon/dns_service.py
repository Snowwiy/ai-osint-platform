from __future__ import annotations

import asyncio

import dns.exception
import dns.resolver

from app.schemas.recon import DNSRecordSet, DNSRecordType, DNSResult, ReconError

_DNS_RECORD_TYPES: tuple[DNSRecordType, ...] = ("A", "AAAA", "MX", "TXT", "NS", "CNAME")
_TIMEOUT_SECONDS = 4.0


async def collect_dns_intelligence(domain: str) -> DNSResult:
    normalized = domain.strip().lower().rstrip(".")
    records: list[DNSRecordSet] = []
    errors: list[ReconError] = []

    for record_type in _DNS_RECORD_TYPES:
        try:
            values = await _query_records(normalized, record_type)
        except Exception as exc:
            values = []
            errors.append(
                ReconError(source=f"dns:{record_type}", message=_safe_error(exc))
            )
        records.append(DNSRecordSet(record_type=record_type, values=values))

    txt_values = _values_for(records, "TXT")
    spf_records = [value for value in txt_values if value.lower().startswith("v=spf1")]
    dkim_indicators = [
        value
        for value in txt_values
        if "v=dkim1" in value.lower() or "_domainkey" in value.lower()
    ]

    try:
        dmarc_records = [
            value
            for value in await _query_txt_name(f"_dmarc.{normalized}")
            if value.lower().startswith("v=dmarc1")
        ]
    except Exception as exc:
        dmarc_records = []
        errors.append(ReconError(source="dns:DMARC", message=_safe_error(exc)))

    return DNSResult(
        domain=normalized,
        records=records,
        spf_records=sorted(set(spf_records)),
        dmarc_records=sorted(set(dmarc_records)),
        dkim_indicators=sorted(set(dkim_indicators)),
        errors=errors,
    )


async def _query_records(domain: str, record_type: DNSRecordType) -> list[str]:
    return await asyncio.to_thread(_query_records_sync, domain, record_type)


async def _query_txt_name(name: str) -> list[str]:
    return await asyncio.to_thread(_query_records_sync, name, "TXT")


def _query_records_sync(name: str, record_type: str) -> list[str]:
    resolver = dns.resolver.Resolver()
    resolver.timeout = _TIMEOUT_SECONDS
    resolver.lifetime = _TIMEOUT_SECONDS
    try:
        answer = resolver.resolve(name, record_type)
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        return []
    values: list[str] = []
    for record in answer:
        if record_type == "TXT":
            values.append(
                "".join(part.decode("utf-8", "replace") for part in record.strings)
            )
        else:
            values.append(record.to_text().strip())
    return sorted(set(values))


def _values_for(records: list[DNSRecordSet], record_type: DNSRecordType) -> list[str]:
    for record in records:
        if record.record_type == record_type:
            return record.values
    return []


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, dns.exception.Timeout):
        return "DNS query timed out"
    return exc.__class__.__name__
