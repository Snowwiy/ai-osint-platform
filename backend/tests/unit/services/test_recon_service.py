from __future__ import annotations

import pytest
from app.schemas.recon import (
    DNSResult,
    HTTPResult,
    IPResult,
    RDAPResult,
    ReconRequest,
)
from app.services.recon import recon_service
from tests.conftest import VALID_AUTH_STATEMENT


async def test_orchestrator_allows_partial_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import uuid
    from types import SimpleNamespace

    investigation_id = uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4(), role="analyst")

    async def dns_ok(_domain: str) -> DNSResult:
        return DNSResult(domain="example.com")

    async def rdap_fail(_target: str, *, target_type: str) -> RDAPResult:
        return RDAPResult(
            query=_target,
            target_type=target_type,
            errors=[{"source": "rdap", "message": "unavailable"}],
        )

    async def cert_fail(_domain: str):
        raise RuntimeError("crt unavailable")

    async def ip_ok(_ip: str) -> IPResult:
        return IPResult(ip_address=_ip)

    async def http_ok(_target: str) -> HTTPResult:
        return HTTPResult(url=_target, final_url=_target)

    async def fake_get_investigation(_db, _user, _investigation_id):
        return SimpleNamespace(id=_investigation_id)

    async def fake_persist(_db, _user, _body, response):
        response.enrichment_id = uuid.uuid4()

    monkeypatch.setattr(recon_service, "get_investigation", fake_get_investigation)
    monkeypatch.setattr(recon_service, "_persist_recon_result", fake_persist)
    monkeypatch.setattr(recon_service, "collect_dns_intelligence", dns_ok)
    monkeypatch.setattr(recon_service, "collect_rdap_intelligence", rdap_fail)
    monkeypatch.setattr(recon_service, "collect_certificate_intelligence", cert_fail)
    monkeypatch.setattr(recon_service, "collect_ip_intelligence", ip_ok)
    monkeypatch.setattr(recon_service, "inspect_http_metadata", http_ok)

    result = await recon_service.run_recon_for_request(
        SimpleNamespace(),
        user,
        ReconRequest(
            investigation_id=investigation_id,
            target="example.com",
            authorization_statement=VALID_AUTH_STATEMENT,
        ),
        target_type="domain",
    )

    assert result.status == "partial"
    assert result.errors
    assert result.enrichment_id is not None
