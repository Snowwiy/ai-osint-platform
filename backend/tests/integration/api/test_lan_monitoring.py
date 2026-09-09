from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.lan_monitoring import LanAsset
from app.models.notification import Notification
from app.models.user import User
from app.schemas.monitoring import (
    MonitoringAssetsResponse,
    MonitoringServicesResponse,
    MonitoringSystemResponse,
)
from app.services.lan_monitoring import (
    LanConfigurationError,
    validate_allowed_cidr,
)
from app.services.local_monitoring import get_monitoring_alerts
from httpx import AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def test_lan_monitoring_is_disabled_by_default(
    client: AsyncClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LAN_MONITORING_ENABLED", False)

    listing = await client.get("/api/v1/monitoring/lan/assets", headers=admin_headers)
    discovery = await client.post(
        "/api/v1/monitoring/lan/discover", headers=admin_headers, json={}
    )
    agent = await client.post(
        "/api/v1/monitoring/agent/register",
        headers={"X-LAN-Agent-Token": "not-configured"},
        json=_registration_payload(),
    )

    assert listing.status_code == 200
    assert listing.json()["enabled"] is False
    assert listing.json()["docker_limited"] is True
    assert "agent_token" not in json.dumps(listing.json()).lower()
    assert discovery.status_code == 409
    assert agent.status_code == 503


def test_lan_cidr_validation_rejects_public_ranges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LAN_ALLOWED_CIDRS", "192.168.0.0/24")

    assert str(validate_allowed_cidr("192.168.0.0/25")) == "192.168.0.0/25"
    with pytest.raises(LanConfigurationError):
        validate_allowed_cidr("8.8.8.0/24")
    with pytest.raises(LanConfigurationError):
        validate_allowed_cidr("192.168.1.0/24")


async def test_admin_can_create_and_update_authorized_lan_asset(
    client: AsyncClient,
    admin_headers: dict[str, str],
    analyst_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_lan(monkeypatch)
    discovery = await client.post(
        "/api/v1/monitoring/lan/discover",
        headers=admin_headers,
        json={
            "cidr": "192.168.0.0/24",
            "observations": [
                {
                    "ip_address": "192.168.0.20",
                    "mac_address": "00-11-22-33-44-55",
                    "hostname": "lab-endpoint",
                    "source": "router",
                }
            ],
        },
    )
    assert discovery.status_code == 200
    assert discovery.json()["assets_created"] == 1

    listing = await client.get("/api/v1/monitoring/lan/assets", headers=admin_headers)
    analyst_listing = await client.get(
        "/api/v1/monitoring/lan/assets", headers=analyst_headers
    )
    missing = await client.get(
        f"/api/v1/monitoring/lan/assets/{uuid.uuid4()}", headers=admin_headers
    )
    asset = listing.json()["items"][0]
    forbidden = await client.patch(
        f"/api/v1/monitoring/lan/assets/{asset['id']}",
        headers=analyst_headers,
        json={"is_authorized": True},
    )
    updated = await client.patch(
        f"/api/v1/monitoring/lan/assets/{asset['id']}",
        headers=admin_headers,
        json={"is_authorized": True, "notes": "Approved lab endpoint."},
    )

    assert forbidden.status_code == 403
    assert analyst_listing.status_code == 403
    assert missing.status_code == 404
    assert updated.status_code == 200
    assert updated.json()["is_authorized"] is True
    assert updated.json()["notes"] == "Approved lab endpoint."


async def test_agent_token_registration_and_telemetry(
    client: AsyncClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_lan(monkeypatch)
    monkeypatch.setattr(settings, "LAN_AGENT_TOKEN", "test-agent-token-value")
    invalid = await client.post(
        "/api/v1/monitoring/agent/register",
        headers={"X-LAN-Agent-Token": "wrong"},
        json=_registration_payload(),
    )
    registered = await client.post(
        "/api/v1/monitoring/agent/register",
        headers={"X-LAN-Agent-Token": "test-agent-token-value"},
        json=_registration_payload(),
    )
    assert invalid.status_code == 401
    assert registered.status_code == 202
    asset_id = registered.json()["asset_id"]
    assert "token" not in json.dumps(registered.json()).lower()

    rejected_metadata = await client.post(
        "/api/v1/monitoring/agent/telemetry",
        headers={"X-LAN-Agent-Token": "test-agent-token-value"},
        json={**_telemetry_payload(asset_id), "metadata": {"access_token": "unsafe"}},
    )
    accepted = await client.post(
        "/api/v1/monitoring/agent/telemetry",
        headers={"X-LAN-Agent-Token": "test-agent-token-value"},
        json=_telemetry_payload(asset_id),
    )
    telemetry = await client.get(
        f"/api/v1/monitoring/lan/assets/{asset_id}/telemetry",
        headers=admin_headers,
    )
    detail = await client.get(
        f"/api/v1/monitoring/lan/assets/{asset_id}", headers=admin_headers
    )

    assert rejected_metadata.status_code == 422
    assert accepted.status_code == 202
    assert telemetry.status_code == 200
    assert telemetry.json()["items"][0]["cpu_percent"] == 12.5
    assert detail.json()["agent_connected"] is True


async def test_lan_alerts_are_deduplicated(
    db: AsyncSession,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_lan(monkeypatch)
    asset = LanAsset(
        ip_address="192.168.0.44",
        status="unknown",
        source="static",
        is_authorized=False,
        monitoring_enabled=True,
    )
    db.add(asset)
    await db.commit()
    services = MonitoringServicesResponse(
        generated_at=datetime.now(UTC), status="healthy", items=[]
    )
    system = MonitoringSystemResponse(
        generated_at=datetime.now(UTC),
        source="container",
        metric_scope="test",
        available=True,
        stale=False,
        platform="test",
        cpu_percent=1,
        memory_percent=1,
        disk_percent=1,
        detail="test",
    )
    investigation_assets = MonitoringAssetsResponse(
        generated_at=datetime.now(UTC),
        stale_after_days=30,
        investigations=0,
        targets=0,
        healthy_assets=0,
        assets_needing_review=0,
        stale_assets=0,
        high_risk_assets=0,
        out_of_scope_assets=0,
        unresolved_high=0,
        unresolved_critical=0,
        findings_by_severity={},
        authorization_risks=0,
        repeated_report_failures=0,
        repeated_ai_degraded=0,
        items=[],
    )

    first = await get_monitoring_alerts(
        db, admin_user, services=services, system=system, assets=investigation_assets
    )
    second = await get_monitoring_alerts(
        db, admin_user, services=services, system=system, assets=investigation_assets
    )
    count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Notification)
                .where(Notification.notification_type == "monitoring_alert")
            )
        ).scalar_one()
    )
    assert first.notifications_created == 2
    assert second.notifications_created == 0
    assert count == 2


async def test_docker_fallback_and_risky_service_indicator(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_lan(monkeypatch)
    from app.services import lan_monitoring

    monkeypatch.setattr(lan_monitoring, "_read_container_arp", lambda _network: [])
    empty = await client.post(
        "/api/v1/monitoring/lan/discover", headers=admin_headers, json={}
    )
    assert empty.status_code == 200
    assert "Docker" in empty.json()["limitation"]

    # Clear the persisted rate-limit event to run a deterministic supplied observation.
    await db.execute(delete(AuditLog).where(AuditLog.action == "lan.discovery.executed"))
    await db.commit()
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_ENABLED", True)
    observed = await client.post(
        "/api/v1/monitoring/lan/discover",
        headers=admin_headers,
        json={
            "observations": [
                {
                    "ip_address": "192.168.0.88",
                    "source": "router",
                    "services": [{"port": 3389, "protocol": "tcp", "status": "open"}],
                }
            ]
        },
    )
    assert observed.status_code == 200
    listing = await client.get("/api/v1/monitoring/lan/assets", headers=admin_headers)
    indicators = listing.json()["items"][0]["risk_indicators"]
    assert any(item["key"] == "risky_service_3389" for item in indicators)


def _enable_lan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LAN_MONITORING_ENABLED", True)
    monkeypatch.setattr(settings, "LAN_ALLOWED_CIDRS", "192.168.0.0/24")


def _registration_payload() -> dict[str, object]:
    return {
        "ip_address": "192.168.0.30",
        "mac_address": "00:11:22:33:44:66",
        "hostname": "agent-endpoint",
        "os_name": "Windows",
        "os_version": "11",
        "agent_version": "1.0.0",
    }


def _telemetry_payload(asset_id: str) -> dict[str, object]:
    return {
        "asset_id": asset_id,
        "collected_at": datetime.now(UTC).isoformat(),
        "cpu_percent": 12.5,
        "memory_percent": 40,
        "disk_percent": 55,
        "uptime_seconds": 3600,
        "os_name": "Windows",
        "os_version": "11",
        "agent_version": "1.0.0",
        "metadata": {"collection_mode": "local"},
    }
