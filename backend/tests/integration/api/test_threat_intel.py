from __future__ import annotations

from app.models.investigation import Investigation
from app.models.recon_entity import ReconEntity
from app.models.threat_finding import ThreatFinding
from app.schemas.threat_intel import ProviderResult, ThreatIntelResponse
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import VALID_AUTH_STATEMENT


async def test_threat_intel_requires_auth(
    client: AsyncClient,
    test_investigation,
) -> None:
    response = await client.post(
        "/api/v1/threat-intel/ip",
        json={
            "investigation_id": str(test_investigation.id),
            "target": "8.8.8.8",
            "authorization_statement": VALID_AUTH_STATEMENT,
        },
    )

    assert response.status_code == 401


async def test_threat_intel_non_member_gets_404(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    admin_user,
) -> None:
    investigation = Investigation(
        title="Private Threat Intel",
        owner_id=admin_user.id,
        authorization_statement=VALID_AUTH_STATEMENT,
        status="active",
    )
    db.add(investigation)
    await db.commit()
    await db.refresh(investigation)

    response = await client.post(
        "/api/v1/threat-intel/domain",
        headers=analyst_headers,
        json={
            "investigation_id": str(investigation.id),
            "target": "example.com",
            "authorization_statement": VALID_AUTH_STATEMENT,
        },
    )

    assert response.status_code == 404


async def test_admin_can_access_any_investigation_threat_intel(
    monkeypatch,
    client: AsyncClient,
    admin_headers: dict[str, str],
    test_investigation,
) -> None:
    from app.services.threat_intel import threat_service

    async def fake_virustotal(*args, **kwargs) -> ProviderResult:
        return ProviderResult(
            provider="virustotal",
            status="completed",
            risk_score=10,
            confidence="low",
            verdict="low",
            signals=["suspicious:1"],
            normalized={"malicious": 0, "suspicious": 1},
        )

    monkeypatch.setattr(
        threat_service,
        "check_virustotal_reputation",
        fake_virustotal,
    )

    response = await client.post(
        "/api/v1/threat-intel/domain",
        headers=admin_headers,
        json={
            "investigation_id": str(test_investigation.id),
            "target": "example.com",
            "authorization_statement": VALID_AUTH_STATEMENT,
        },
    )

    assert response.status_code == 200
    assert response.json()["investigation_id"] == str(test_investigation.id)


async def test_missing_api_keys_return_provider_unavailable(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
) -> None:
    response = await client.post(
        "/api/v1/threat-intel/domain",
        headers=analyst_headers,
        json={
            "investigation_id": str(test_investigation.id),
            "target": "example.com",
            "authorization_statement": VALID_AUTH_STATEMENT,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "provider_unavailable"
    assert body["risk_level"] == "unknown"
    assert body["provider_results"] == [
        {
            "provider": "virustotal",
            "status": "provider_unavailable",
            "risk_score": 0,
            "confidence": "low",
            "verdict": "unknown",
            "signals": [],
            "normalized": {},
            "raw_data": {},
            "error_message": "missing_api_key",
        }
    ]


async def test_ip_threat_intel_persists_findings_with_partial_provider_failure(
    monkeypatch,
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    from app.services.threat_intel import threat_service

    async def fake_abuseipdb(*args, **kwargs) -> ProviderResult:
        return ProviderResult(
            provider="abuseipdb",
            status="completed",
            risk_score=80,
            confidence="high",
            verdict="high_risk",
            signals=["abuse_confidence_score:80"],
            normalized={"abuse_confidence_score": 80, "total_reports": 12},
        )

    async def fake_virustotal(*args, **kwargs) -> ProviderResult:
        return ProviderResult(
            provider="virustotal",
            status="rate_limited",
            risk_score=0,
            confidence="low",
            verdict="unknown",
            signals=[],
            error_message="rate_limited",
        )

    monkeypatch.setattr(threat_service, "check_abuseipdb_ip", fake_abuseipdb)
    monkeypatch.setattr(
        threat_service,
        "check_virustotal_reputation",
        fake_virustotal,
    )

    response = await client.post(
        "/api/v1/threat-intel/ip",
        headers=analyst_headers,
        json={
            "investigation_id": str(test_investigation.id),
            "target": "8.8.8.8",
            "authorization_statement": VALID_AUTH_STATEMENT,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    assert body["overall_risk_score"] == 80
    assert body["risk_level"] == "high"
    assert len(body["provider_results"]) == 2

    findings = (
        (
            await db.execute(
                select(ThreatFinding).where(
                    ThreatFinding.investigation_id == test_investigation.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(findings) == 2
    assert {finding.provider for finding in findings} == {
        "abuseipdb",
        "virustotal",
    }
    entity = await db.get(ReconEntity, findings[0].recon_entity_id)
    assert entity is not None
    assert entity.entity_type == "IPAddress"
    assert entity.value == "8.8.8.8"


async def test_domain_threat_intel_uses_existing_recon_entity(
    monkeypatch,
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
    test_investigation,
) -> None:
    from app.services.threat_intel import threat_service

    entity = ReconEntity(
        investigation_id=test_investigation.id,
        entity_type="Domain",
        value="example.com",
        source="dns",
        properties={},
    )
    db.add(entity)
    await db.commit()
    await db.refresh(entity)

    async def fake_virustotal(*args, **kwargs) -> ProviderResult:
        return ProviderResult(
            provider="virustotal",
            status="completed",
            risk_score=30,
            confidence="medium",
            verdict="medium_risk",
            signals=["malicious:1"],
            normalized={"malicious": 1, "suspicious": 1},
        )

    monkeypatch.setattr(
        threat_service,
        "check_virustotal_reputation",
        fake_virustotal,
    )

    response = await client.post(
        "/api/v1/threat-intel/domain",
        headers=analyst_headers,
        json={
            "investigation_id": str(test_investigation.id),
            "target": "Example.COM",
            "authorization_statement": VALID_AUTH_STATEMENT,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["entity_id"] == str(entity.id)
    assert body["target_value"] == "example.com"
    assert body["overall_risk_score"] == 30


async def test_url_threat_intel_response_schema_validates(
    monkeypatch,
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
) -> None:
    from app.services.threat_intel import threat_service

    async def fake_virustotal(*args, **kwargs) -> ProviderResult:
        return ProviderResult(
            provider="virustotal",
            status="completed",
            risk_score=0,
            confidence="low",
            verdict="clean",
            signals=[],
            normalized={"malicious": 0, "suspicious": 0},
        )

    monkeypatch.setattr(
        threat_service,
        "check_virustotal_reputation",
        fake_virustotal,
    )

    response = await client.post(
        "/api/v1/threat-intel/url",
        headers=analyst_headers,
        json={
            "investigation_id": str(test_investigation.id),
            "target": "https://example.com/login",
            "authorization_statement": VALID_AUTH_STATEMENT,
        },
    )

    assert response.status_code == 200
    parsed = ThreatIntelResponse.model_validate(response.json())
    assert parsed.target_type == "url"
    assert parsed.target_value == "https://example.com/login"
    assert parsed.risk_level == "low"
