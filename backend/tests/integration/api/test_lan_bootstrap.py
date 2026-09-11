from __future__ import annotations

import json

import pytest

from app.core.config import settings


async def test_lan_bootstrap_is_admin_only_normalized_and_non_scanning(
    client,
    admin_headers,
    analyst_headers,
    test_investigation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LAN_ALLOWED_CIDRS", "192.168.50.0/24")
    monkeypatch.setattr(settings, "LAN_GATEWAY_HINT", "192.168.50.1")
    monkeypatch.setattr(settings, "LAN_MONITORING_ENABLED", False)
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_ENABLED", False)
    monkeypatch.setattr(settings, "LOCAL_BACKEND_URL", "http://192.168.50.201:8000")

    denied = await client.post(
        "/api/v1/monitoring/lan/bootstrap/verify",
        headers=analyst_headers,
        json={"cidr": "192.168.50.1/24"},
    )
    response = await client.post(
        "/api/v1/monitoring/lan/bootstrap/verify",
        headers=admin_headers,
        json={"cidr": "192.168.50.1/24", "gateway_hint": "192.168.50.1"},
    )

    assert denied.status_code == 403
    assert response.status_code == 200
    payload = response.json()
    assert payload["normalized_cidr"] == "192.168.50.0/24"
    assert payload["gateway_hint"] == "192.168.50.1"
    assert payload["configured_cidr_matches"] is True
    assert payload["lan_monitoring_enabled"] is False
    assert payload["service_check_enabled"] is False
    assert payload["discovery_executed"] is False
    assert payload["service_checks_executed"] is False
    assert payload["release_version"] == "5.0.0-rc6"
    assert "<ENROLLMENT_TOKEN>" in payload["windows_agent_command"]
    assert "192.168.50.201:8000" in payload["windows_agent_command"]
    assert "LAN_ALLOWED_CIDRS=192.168.50.0/24" in payload["env_lines"]
    assert "LAN_GATEWAY_HINT=192.168.50.1" in payload["env_lines"]
    serialized = json.dumps(payload).lower()
    assert "rae_" not in serialized
    assert settings.APP_SECRET_KEY.lower() not in serialized


async def test_lan_bootstrap_agent_command_falls_back_to_localhost(
    client,
    admin_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LAN_ALLOWED_CIDRS", "192.168.50.0/24")
    monkeypatch.setattr(settings, "LOCAL_BACKEND_URL", "https://public.example.test")

    response = await client.post(
        "/api/v1/monitoring/lan/bootstrap/verify",
        headers=admin_headers,
        json={"cidr": "192.168.50.1/24"},
    )

    assert response.status_code == 200
    assert "http://localhost:8000" in response.json()["windows_agent_command"]


async def test_lan_bootstrap_rejects_public_invalid_and_oversized_ranges(
    client,
    admin_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_MAX_HOSTS", 256)
    for value in ("8.8.8.8/24", "not-a-cidr", "192.168.0.1/16"):
        response = await client.post(
            "/api/v1/monitoring/lan/bootstrap/verify",
            headers=admin_headers,
            json={"cidr": value},
        )
        assert response.status_code == 422
