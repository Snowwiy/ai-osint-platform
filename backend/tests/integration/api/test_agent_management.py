from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import settings
from app.models.agent_management import AgentEnrollmentToken
from app.models.lan_monitoring import LanAsset, LanServiceObservation

pytestmark = pytest.mark.asyncio


def _enable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LAN_MONITORING_ENABLED", True)
    monkeypatch.setattr(settings, "LAN_ALLOWED_CIDRS", "192.168.0.0/24")
    monkeypatch.setattr(settings, "LAN_AGENT_TOKEN", "")


def _registration() -> dict[str, object]:
    return {
        "ip_address": "192.168.0.88",
        "hostname": "lab-agent",
        "agent_version": "1.0.0",
        "os_name": "Test OS",
        "capabilities": ["basic_telemetry", "os_basics"],
    }


async def _create_token(client, admin_headers, **changes):
    payload = {
        "name": "Lab enrollment",
        "description": "One-time local endpoint enrollment.",
        "allowed_cidr": "192.168.0.0/24",
        "max_enrollments": 2,
        "expires_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        **changes,
    }
    return await client.post(
        "/api/v1/monitoring/agent-tokens", headers=admin_headers, json=payload
    )


async def test_token_create_one_time_reveal_expiry_and_rbac(
    client, db, admin_headers, analyst_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable(monkeypatch)
    denied = await client.post(
        "/api/v1/monitoring/agent-tokens", headers=analyst_headers, json={}
    )
    assert denied.status_code == 403
    created = await _create_token(client, admin_headers)
    assert created.status_code == 201
    assert created.json()["token"].startswith("rae_")
    token_id = created.json()["id"]
    listing = await client.get(
        "/api/v1/monitoring/agent-tokens", headers=analyst_headers
    )
    serialized = json.dumps(listing.json()).lower()
    assert listing.status_code == 403
    assert '"token"' not in serialized
    assert "token_hash" not in serialized

    item = await db.get(AgentEnrollmentToken, token_id)
    assert item is not None
    assert item.token_hash != created.json()["token"]
    item.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db.commit()
    expired = await client.get("/api/v1/monitoring/agent-tokens", headers=admin_headers)
    assert expired.json()["items"][0]["status"] == "expired"
    rejected = await client.post(
        "/api/v1/monitoring/agent/register",
        headers={"X-LAN-Agent-Token": created.json()["token"]},
        json=_registration(),
    )
    assert rejected.status_code == 401


async def test_agent_registration_heartbeat_revoke_and_inventory(
    client, db, admin_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable(monkeypatch)
    created = await _create_token(client, admin_headers)
    raw = created.json()["token"]
    registered = await client.post(
        "/api/v1/monitoring/agent/register",
        headers={"X-LAN-Agent-Token": raw},
        json=_registration(),
    )
    assert registered.status_code == 202
    asset_id = registered.json()["asset_id"]
    heartbeat = await client.post(
        "/api/v1/monitoring/agent/telemetry",
        headers={"X-LAN-Agent-Token": raw},
        json={
            "asset_id": asset_id,
            "collected_at": datetime.now(UTC).isoformat(),
            "cpu_percent": 10,
            "memory_percent": 20,
            "disk_percent": 30,
            "uptime_seconds": 100,
            "os_name": "Test OS",
            "agent_version": "1.0.0",
        },
    )
    assert heartbeat.status_code == 202
    posture = await client.get(
        f"/api/v1/monitoring/lan/assets/{asset_id}/posture",
        headers=admin_headers,
    )
    assert posture.status_code == 200
    assert posture.json()["agent_freshness"] == "fresh"
    inventory = await client.get("/api/v1/monitoring/agents", headers=admin_headers)
    assert inventory.status_code == 200
    assert inventory.json()["items"][0]["telemetry_fresh"] is True
    assert inventory.json()["items"][0]["enrollment_token_label"] == "Lab enrollment"
    assert raw not in json.dumps(inventory.json())
    updated = await client.patch(
        f"/api/v1/monitoring/agents/{asset_id}",
        headers=admin_headers,
        json={"owner": "Blue Team", "criticality": "critical", "monitoring_enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["owner"] == "Blue Team"
    assert updated.json()["monitoring_enabled"] is False

    revoked = await client.post(
        f"/api/v1/monitoring/agent-tokens/{created.json()['id']}/revoke",
        headers=admin_headers,
    )
    assert revoked.status_code == 200
    rejected = await client.post(
        "/api/v1/monitoring/agent/telemetry",
        headers={"X-LAN-Agent-Token": raw},
        json={
            "asset_id": asset_id,
            "collected_at": datetime.now(UTC).isoformat(),
            "cpu_percent": 11,
            "agent_version": "1.0.0",
        },
    )
    assert rejected.status_code == 401


async def test_asset_group_crud_and_coverage(
    client, db, admin_headers, analyst_headers
) -> None:
    asset = LanAsset(
        ip_address="192.168.0.50",
        hostname="grouped-server",
        source="static",
        status="online",
        is_authorized=True,
        monitoring_enabled=True,
        last_seen=datetime.now(UTC),
    )
    db.add(asset)
    await db.commit()
    created = await client.post(
        "/api/v1/monitoring/asset-groups",
        headers=admin_headers,
        json={
            "name": "Servers",
            "description": "Approved local servers.",
            "asset_ids": [str(asset.id)],
        },
    )
    assert created.status_code == 201
    assert created.json()["total_assets"] == 1
    listing = await client.get(
        "/api/v1/monitoring/asset-groups", headers=analyst_headers
    )
    assert listing.status_code == 403
    group_id = created.json()["id"]
    updated = await client.patch(
        f"/api/v1/monitoring/asset-groups/{group_id}",
        headers=admin_headers,
        json={"name": "Critical Servers"},
    )
    assert updated.status_code == 200
    denied = await client.delete(
        f"/api/v1/monitoring/asset-groups/{group_id}", headers=analyst_headers
    )
    assert denied.status_code == 403
    deleted = await client.delete(
        f"/api/v1/monitoring/asset-groups/{group_id}", headers=admin_headers
    )
    assert deleted.status_code == 204


async def test_service_baseline_missing_and_unexpected_indicators(
    client, db, admin_headers, analyst_headers
) -> None:
    asset = LanAsset(
        ip_address="192.168.0.60",
        hostname="baseline-server",
        source="static",
        status="online",
        is_authorized=True,
        monitoring_enabled=True,
        last_seen=datetime.now(UTC),
    )
    db.add(asset)
    await db.flush()
    db.add(
        LanServiceObservation(
            lan_asset_id=asset.id,
            ip_address=asset.ip_address,
            port=443,
            protocol="tcp",
            service_name="https",
            confidence=75,
            status="open",
            observed_at=datetime.now(UTC),
            source="static",
        )
    )
    await db.commit()
    created = await client.post(
        "/api/v1/monitoring/service-baselines",
        headers=admin_headers,
        json={
            "name": "SSH-only expectation",
            "asset_id": str(asset.id),
            "expected_ports": [22],
            "allowed_ports": [22],
        },
    )
    assert created.status_code == 201
    kinds = {item["indicator_type"] for item in created.json()["indicators"]}
    assert kinds == {"missing_expected_service", "unexpected_open_service"}
    listing = await client.get(
        "/api/v1/monitoring/service-baselines", headers=analyst_headers
    )
    assert listing.status_code == 200
    assert "exploit" not in json.dumps(listing.json()).lower().replace(
        "not exploit validation", ""
    )
    baseline_id = created.json()["id"]
    updated = await client.patch(
        f"/api/v1/monitoring/service-baselines/{baseline_id}",
        headers=admin_headers,
        json={"allowed_ports": [22, 443]},
    )
    assert updated.status_code == 200
    assert {item["indicator_type"] for item in updated.json()["indicators"]} == {
        "missing_expected_service"
    }
    assert (
        await client.delete(
            f"/api/v1/monitoring/service-baselines/{baseline_id}", headers=admin_headers
        )
    ).status_code == 204


async def test_invalid_agent_token_and_public_enrollment_cidr_rejected(
    client, admin_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable(monkeypatch)
    invalid = await client.post(
        "/api/v1/monitoring/agent/register",
        headers={"X-LAN-Agent-Token": "invalid"},
        json=_registration(),
    )
    assert invalid.status_code == 401
    public = await _create_token(client, admin_headers, allowed_cidr="8.8.8.0/24")
    assert public.status_code == 422


async def test_token_rotation_reveals_only_replacement_once(
    client, admin_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable(monkeypatch)
    created = await _create_token(client, admin_headers)
    rotated = await client.post(
        f"/api/v1/monitoring/agent-tokens/{created.json()['id']}/rotate",
        headers=admin_headers,
    )
    assert rotated.status_code == 200
    assert rotated.json()["token"] != created.json()["token"]
    listing = await client.get("/api/v1/monitoring/agent-tokens", headers=admin_headers)
    assert '"token"' not in json.dumps(listing.json()).lower()
    rejected = await client.post(
        "/api/v1/monitoring/agent/register",
        headers={"X-LAN-Agent-Token": created.json()["token"]},
        json=_registration(),
    )
    assert rejected.status_code == 401
