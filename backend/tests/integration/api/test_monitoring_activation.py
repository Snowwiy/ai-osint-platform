from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from app.core.config import settings
from app.models.lan_monitoring import LanAsset, LanServiceObservation
from app.models.target import Target


async def test_activation_status_is_authenticated_safe_and_explains_disabled(
    client, analyst_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "LAN_MONITORING_ENABLED", False)
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_ENABLED", False)
    monkeypatch.setattr(settings, "LAN_ALLOWED_CIDRS", "192.168.0.0/24")
    monkeypatch.setattr(settings, "LAN_GATEWAY_HINT", "192.168.0.1")
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_PORTS", "22,443,8443")

    anonymous = await client.get("/api/v1/monitoring/activation")
    response = await client.get(
        "/api/v1/monitoring/activation", headers=analyst_headers
    )

    assert anonymous.status_code == 401
    assert response.status_code == 200
    payload = response.json()
    assert payload["lan_monitoring_enabled"] is False
    assert payload["service_check_enabled"] is False
    assert payload["service_ports"] == [22, 443, 8443]
    assert payload["gateway_hint"] == "192.168.0.1"
    assert "LAN_MONITORING_ENABLED is false" in payload["discovery_disabled_reason"]
    assert "LAN_SERVICE_CHECK_ENABLED is false" in payload[
        "service_check_disabled_reason"
    ]
    assert "LAN_MONITORING_ENABLED=true" in payload["env_lines"]
    assert "MONITORING_AUTO_REFRESH_ENABLED=true" in payload["env_lines"]
    assert "LAN_GATEWAY_HINT=192.168.0.1" in payload["env_lines"]
    assert payload["auto_refresh_enabled"] is True
    assert payload["server_host_metrics_enabled"] is True
    assert payload["server_host_metrics_interval_seconds"] == 30
    assert payload["lan_endpoint_agent_interval_seconds"] == 30
    assert payload["posture_recompute_interval_seconds"] == 300
    assert payload["lan_auto_discovery_on_start"] is False
    assert payload["lan_auto_service_check_on_start"] is False
    assert "Docker could not read host LAN neighbors" in payload["docker_limitation"]
    assert "not a platform failure" in payload["optional_telemetry_note"]
    serialized = json.dumps(payload).lower()
    assert "lan_agent_token" not in serialized
    assert "rae_" not in serialized


async def test_authorized_url_target_maps_to_separate_lan_port_observations(
    client,
    db,
    admin_headers,
    analyst_headers,
    test_investigation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LAN_MONITORING_ENABLED", True)
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_ENABLED", True)
    monkeypatch.setattr(settings, "LAN_ALLOWED_CIDRS", "192.168.0.0/24")
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_PORTS", "22,2222,443")
    asset = LanAsset(
        ip_address="192.168.0.91",
        hostname="internal.example.test",
        source="static",
        status="online",
        is_authorized=True,
        monitoring_enabled=True,
        last_seen=datetime.now(UTC),
    )
    db.add(asset)
    await db.flush()
    target = Target(
        investigation_id=test_investigation.id,
        target_type="url",
        target_value="https://internal.example.test/admin",
        label="Internal HTTPS service",
        notes="Authorized internal target; port observations remain separate.",
        created_by=test_investigation.owner_id,
    )
    db.add(target)
    await db.flush()
    db.add(
        LanServiceObservation(
            lan_asset_id=asset.id,
            ip_address=asset.ip_address,
            port=2222,
            protocol="tcp",
            status="open",
            service_name="ssh",
            service_label="possible SSH service",
            confidence=95,
            banner_hint="SSH protocol banner detected",
            non_standard_ssh=True,
            observed_at=datetime.now(UTC),
            source="tcp_connect",
        )
    )
    await db.commit()

    response = await client.get(
        f"/api/v1/monitoring/targets/{target.id}/service-check",
        headers=analyst_headers,
    )
    denied = await client.post(
        f"/api/v1/monitoring/targets/{target.id}/service-check",
        headers=analyst_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["eligible"] is True
    assert payload["target_is_url_service"] is True
    assert payload["lan_asset_id"] == str(asset.id)
    assert payload["configured_ports"] == [22, 443, 2222]
    assert payload["observations"][0]["non_standard_ssh"] is True
    assert payload["observations"][0]["service_name"] == "ssh"
    assert denied.status_code == 403


async def test_target_without_private_lan_match_is_ineligible(
    client,
    db,
    analyst_headers,
    test_investigation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LAN_MONITORING_ENABLED", True)
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_ENABLED", True)
    target = Target(
        investigation_id=test_investigation.id,
        target_type="domain",
        target_value="public.example.test",
        created_by=test_investigation.owner_id,
    )
    db.add(target)
    await db.commit()
    response = await client.get(
        f"/api/v1/monitoring/targets/{target.id}/service-check",
        headers=analyst_headers,
    )
    assert response.status_code == 200
    assert response.json()["eligible"] is False
    assert "no existing private LAN asset" in response.json()["reason"]
