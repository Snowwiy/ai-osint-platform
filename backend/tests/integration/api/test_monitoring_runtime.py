from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.lan_monitoring import LanAsset


async def test_monitoring_startup_requires_authentication_and_loads_safe_summary(
    client,
    analyst_headers,
    analyst_user,
    db,
    test_investigation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "DESKTOP_AUTO_MONITORING_ENABLED", True)
    monkeypatch.setattr(settings, "MONITORING_AUTO_REFRESH_ENABLED", True)
    monkeypatch.setattr(settings, "MONITORING_AUTO_REFRESH_SECONDS", 30)
    monkeypatch.setattr(settings, "LAN_MONITORING_ENABLED", False)
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_ENABLED", False)
    monkeypatch.setattr(settings, "LAN_ALLOWED_CIDRS", "192.168.50.0/24")
    monkeypatch.setattr(settings, "LAN_GATEWAY_HINT", "192.168.50.1")
    monkeypatch.setattr(settings, "LAN_AUTO_DISCOVERY_ON_START", False)
    monkeypatch.setattr(settings, "LAN_AUTO_SERVICE_CHECK_ON_START", False)
    observed_at = datetime.now(UTC)
    db.add(
        LanAsset(
            ip_address="192.168.50.10",
            hostname="qa-endpoint",
            source="router",
            status="online",
            last_seen=observed_at,
            is_authorized=True,
        )
    )
    db.add_all(
        [
            AuditLog(
                user_id=analyst_user.id,
                actor_id=analyst_user.id,
                action=action,
                resource_type="lan_monitoring",
            )
            for action in ("lan.discovery.executed", "lan.service_check.executed")
        ]
    )
    await db.commit()

    anonymous = await client.get("/api/v1/monitoring/startup")
    response = await client.get(
        "/api/v1/monitoring/startup", headers=analyst_headers
    )

    assert anonymous.status_code == 401
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "loaded"
    assert payload["message"] == (
        "Monitoring ready, LAN discovery disabled by configuration."
    )
    assert payload["auto_refresh_enabled"] is True
    assert payload["auto_refresh_seconds"] == 30
    assert payload["lan_monitoring_enabled"] is False
    assert payload["service_check_enabled"] is False
    assert payload["lan_auto_discovery_on_start"] is False
    assert payload["lan_auto_service_check_on_start"] is False
    assert payload["release_version"] == "5.0.0-rc6"
    assert payload["allowed_cidrs"] == ["192.168.50.0/24"]
    assert payload["gateway_hint"] == "192.168.50.1"
    assert payload["last_discovery_at"] is not None
    assert payload["last_service_check_at"] is not None
    assert payload["assets_total"] == 1
    assert payload["assets_online"] == 1
    assert payload["static_router_observations"] == 1
    assert payload["host_metrics_source"] in {
        "container",
        "server_endpoint_agent",
        "backend_host_agent",
    }
    assert payload["baseline_total"] >= 0
    assert payload["triage_total"] >= 0
    assert payload["next_refresh_at"] is not None
    serialized = json.dumps(payload).lower()
    for forbidden in (
        "database_url",
        "password",
        "access_token",
        "lan_agent_token",
        settings.APP_SECRET_KEY.lower(),
    ):
        assert forbidden not in serialized
    assert "public scan" in serialized


async def test_monitoring_startup_active_flags_require_parent_safety_flags(
    client,
    analyst_headers,
    test_investigation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LAN_MONITORING_ENABLED", False)
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_ENABLED", True)
    monkeypatch.setattr(settings, "LAN_AUTO_DISCOVERY_ON_START", True)
    monkeypatch.setattr(settings, "LAN_AUTO_SERVICE_CHECK_ON_START", True)

    response = await client.get(
        "/api/v1/monitoring/startup", headers=analyst_headers
    )

    assert response.status_code == 200
    assert response.json()["lan_auto_discovery_on_start"] is False
    assert response.json()["lan_auto_service_check_on_start"] is False
