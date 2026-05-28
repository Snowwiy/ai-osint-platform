from __future__ import annotations

import dns.exception
import pytest
from app.services.recon import dns_service


async def test_collect_dns_intelligence_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_query(domain: str, record_type: str) -> list[str]:
        records = {
            "A": ["203.0.113.10"],
            "AAAA": ["2001:db8::10"],
            "MX": ["10 mail.example.com."],
            "TXT": ["v=spf1 include:_spf.example.net -all", "plain text"],
            "NS": ["ns1.example.com."],
            "CNAME": [],
        }
        return records[record_type]

    async def fake_txt(name: str) -> list[str]:
        if name == "_dmarc.example.com":
            return ["v=DMARC1; p=reject"]
        return []

    monkeypatch.setattr(dns_service, "_query_records", fake_query)
    monkeypatch.setattr(dns_service, "_query_txt_name", fake_txt)

    result = await dns_service.collect_dns_intelligence("Example.COM")

    assert result.domain == "example.com"
    assert result.record_values("A") == ["203.0.113.10"]
    assert result.spf_records == ["v=spf1 include:_spf.example.net -all"]
    assert result.dmarc_records == ["v=DMARC1; p=reject"]
    assert result.errors == []


async def test_collect_dns_intelligence_gracefully_records_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_query(_domain: str, record_type: str) -> list[str]:
        if record_type == "A":
            raise dns.exception.Timeout
        return []

    async def fake_txt(_name: str) -> list[str]:
        return []

    monkeypatch.setattr(dns_service, "_query_records", fake_query)
    monkeypatch.setattr(dns_service, "_query_txt_name", fake_txt)

    result = await dns_service.collect_dns_intelligence("example.com")

    assert result.record_values("A") == []
    assert result.errors
    assert result.errors[0].source == "dns:A"
