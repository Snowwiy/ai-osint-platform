from __future__ import annotations

import json

import pytest

from app.core.config import settings


async def test_monitoring_startup_requires_authentication_and_loads_safe_summary(
    client,
    analyst_headers,
    test_investigation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "DESKTOP_AUTO_MONITORING_ENABLED", True)
    monkeypatch.setattr(settings, "MONITORING_AUTO_REFRESH_ENABLED", True)
    monkeypatch.setattr(settings, "MONITORING_AUTO_REFRESH_SECONDS", 30)
    monkeypatch.setattr(settings, "LAN_MONITORING_ENABLED", False)
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_ENABLED", False)
    monkeypatch.setattr(settings, "LAN_AUTO_DISCOVERY_ON_START", False)
    monkeypatch.setattr(settings, "LAN_AUTO_SERVICE_CHECK_ON_START", False)

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
