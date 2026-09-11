from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.lan_monitoring import LanAsset, LanServiceObservation
from app.models.notification import Notification
from app.models.user import User
from app.schemas.monitoring import (
    MonitoringAssetsResponse,
    MonitoringServicesResponse,
    MonitoringSystemResponse,
)
from app.services.lan_monitoring import (
    LanConfigurationError,
    _classify_service,
    normalize_private_cidr,
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


def test_lan_cidr_normalizes_host_bits_and_preserves_gateway_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_MAX_HOSTS", 256)
    network, gateway = normalize_private_cidr("192.168.50.1/24")

    assert str(network) == "192.168.50.0/24"
    assert str(gateway) == "192.168.50.1"
    with pytest.raises(LanConfigurationError, match="private RFC1918"):
        normalize_private_cidr("8.8.8.8/24")
    with pytest.raises(LanConfigurationError, match="invalid"):
        normalize_private_cidr("not-a-cidr")
    with pytest.raises(LanConfigurationError, match="MAX_HOSTS"):
        normalize_private_cidr("192.168.0.1/16")


async def test_manual_router_observation_fields_are_validated_and_persisted(
    client: AsyncClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LAN_MONITORING_ENABLED", True)
    monkeypatch.setattr(settings, "LAN_ALLOWED_CIDRS", "192.168.50.0/24")
    response = await client.post(
        "/api/v1/monitoring/lan/discover",
        headers=admin_headers,
        json={
            "cidr": "192.168.50.1/24",
            "observations": [{
                "ip_address": "192.168.50.22",
                "hostname": "approved-phone",
                "mac_address": "00:11:22:33:44:66",
                "source": "router",
                "interface_name": "wifi",
                "connection_type": "wireless",
                "is_authorized": True,
                "notes": "Observed manually in the approved router UI.",
            }],
        },
    )
    assert response.status_code == 200
    listing = await client.get("/api/v1/monitoring/lan/assets", headers=admin_headers)
    item = next(value for value in listing.json()["items"] if value["ip_address"] == "192.168.50.22")
    assert item["is_authorized"] is True
    assert "Interface: wifi" in item["notes"]
    assert "Connection: wireless" in item["notes"]


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
    assert telemetry.json()["items"][0]["metadata"]["firewall_status"] == "enabled"
    assert telemetry.json()["items"][0]["metadata"]["listening_tcp_ports"] == [22, 443]
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
    await db.execute(
        delete(AuditLog).where(AuditLog.action == "lan.discovery.executed")
    )
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


async def test_manual_service_check_is_disabled_by_default_and_admin_only(
    client: AsyncClient,
    admin_headers: dict[str, str],
    analyst_headers: dict[str, str],
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_lan(monkeypatch)
    asset = LanAsset(
        ip_address="192.168.0.71",
        status="online",
        source="static",
        is_authorized=True,
        monitoring_enabled=True,
    )
    db.add(asset)
    await db.commit()

    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_ENABLED", False)
    disabled = await client.post(
        f"/api/v1/monitoring/lan/assets/{asset.id}/service-check",
        headers=admin_headers,
    )
    forbidden = await client.post(
        f"/api/v1/monitoring/lan/assets/{asset.id}/service-check",
        headers=analyst_headers,
    )

    assert disabled.status_code == 409
    assert forbidden.status_code == 403
    assert "secret" not in json.dumps(disabled.json()).lower()


async def test_manual_service_check_records_safe_ssh_observations(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import lan_monitoring

    _enable_lan(monkeypatch)
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_ENABLED", True)
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_PORTS", "22,2222")
    asset = LanAsset(
        ip_address="192.168.0.72",
        status="online",
        source="static",
        is_authorized=True,
        monitoring_enabled=True,
    )
    db.add(asset)
    await db.commit()

    async def fake_observation(_ip_address: str, port: int):
        banner = b"SSH-2.0-test secret=must-not-leak" if port == 2222 else b""
        return _classify_service(port, banner)

    monkeypatch.setattr(lan_monitoring, "_tcp_service_observation", fake_observation)
    checked = await client.post(
        f"/api/v1/monitoring/lan/assets/{asset.id}/service-check",
        headers=admin_headers,
    )
    services = await client.get(
        f"/api/v1/monitoring/lan/assets/{asset.id}/services",
        headers=admin_headers,
    )
    observations = list(
        (
            await db.execute(
                select(LanServiceObservation).where(
                    LanServiceObservation.lan_asset_id == asset.id
                )
            )
        )
        .scalars()
        .all()
    )

    assert checked.status_code == 200
    assert checked.json()["ports_checked"] == 2
    assert services.status_code == 200
    assert {item["service_name"] for item in services.json()["items"]} == {"ssh"}
    nonstandard = next(
        item for item in services.json()["items"] if item["port"] == 2222
    )
    assert nonstandard["non_standard_ssh"] is True
    assert nonstandard["service_label"] == "possible SSH service"
    assert nonstandard["banner_hint"] == "SSH protocol banner detected"
    assert "must-not-leak" not in json.dumps(services.json())
    assert len(observations) == 2


def test_ssh_classification_standard_and_nonstandard_ports() -> None:
    standard = _classify_service(22, b"")
    nonstandard = _classify_service(2022, b"SSH-2.0-OpenSSH_9.0 token=unsafe")

    assert standard.service_name == "ssh"
    assert standard.non_standard_ssh is False
    assert nonstandard.service_name == "ssh"
    assert nonstandard.non_standard_ssh is True
    assert nonstandard.confidence >= 90
    assert nonstandard.banner_hint == "SSH protocol banner detected"
    assert "token" not in nonstandard.banner_hint


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
        "agent_version": "1.1.0",
        "capabilities": [
            "basic_telemetry",
            "os_basics",
            "security_posture",
            "patch_awareness",
            "listening_ports",
        ],
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
        "agent_version": "1.1.0",
        "os_build": "26100",
        "disk_free_gb": 120.5,
        "firewall_status": "enabled",
        "antivirus_status": "enabled",
        "patch_status": "current",
        "latest_patch_date": "2026-09-01",
        "recent_hotfix_count": 4,
        "pending_reboot": False,
        "listening_tcp_ports": [443, 22, 443],
        "metadata": {"collection_mode": "local"},
    }
