from __future__ import annotations

from app.core.config import Settings


def test_local_placeholder_secret_emits_warning() -> None:
    local_settings = Settings(
        _env_file=None,
        APP_ENVIRONMENT="development",
        APP_SECRET_KEY="change-me-before-any-production-use-12345",
    )

    assert local_settings.has_weak_secret_key is True
    assert any("placeholder SECRET_KEY" in item for item in local_settings.startup_warnings())


def test_production_placeholder_secret_is_rejected() -> None:
    production_settings = Settings(
        _env_file=None,
        APP_ENVIRONMENT="production",
        APP_SECRET_KEY="replace-with-a-unique-production-key-123",
        APP_ALLOWED_ORIGINS="https://example.test",
        FRONTEND_URL="https://example.test",
    )

    assert "SECRET_KEY must be replaced for production." in production_settings.startup_errors()


def test_production_cors_wildcard_is_rejected() -> None:
    production_settings = Settings(
        _env_file=None,
        APP_ENVIRONMENT="production",
        APP_SECRET_KEY="unique-production-signing-key-value-123456789",
        APP_ALLOWED_ORIGINS="*",
        FRONTEND_URL="https://example.test",
    )

    assert "CORS_ORIGINS cannot contain '*' in production." in production_settings.startup_errors()


def test_lan_monitoring_defaults_are_non_intrusive() -> None:
    local_settings = Settings(_env_file=None)

    assert local_settings.APP_MODE == "local"
    assert local_settings.DESKTOP_MODE_ENABLED is False
    assert local_settings.LOCAL_FRONTEND_URL == "http://localhost:5173"
    assert local_settings.LOCAL_BACKEND_URL == "http://localhost:8000"
    assert local_settings.LOCAL_OPERATOR_OPEN_BROWSER is True
    assert local_settings.LAN_MONITORING_ENABLED is False
    assert local_settings.LAN_DISCOVERY_PING_ENABLED is False
    assert local_settings.LAN_SERVICE_CHECK_ENABLED is False
    assert local_settings.LAN_AGENT_TOKEN == ""
    assert "LAN_AGENT_TOKEN" not in local_settings.model_dump()


def test_local_desktop_origins_are_exact_and_production_is_unchanged() -> None:
    local_settings = Settings(_env_file=None, APP_ALLOWED_ORIGINS="http://localhost:5173")
    production_settings = Settings(
        _env_file=None,
        APP_MODE="hosted",
        APP_ENVIRONMENT="production",
        APP_SECRET_KEY="unique-production-signing-key-value-123456789",
        APP_ALLOWED_ORIGINS="https://example.test",
        FRONTEND_URL="https://example.test",
    )

    assert local_settings.allowed_origins_list == [
        "http://localhost:5173",
        "http://tauri.localhost",
        "tauri://localhost",
    ]
    assert production_settings.allowed_origins_list == ["https://example.test"]


def test_public_lan_cidr_is_rejected_at_startup() -> None:
    local_settings = Settings(_env_file=None, LAN_ALLOWED_CIDRS="8.8.8.0/24")

    assert "LAN_ALLOWED_CIDRS accepts private IPv4 CIDRs only." in local_settings.startup_errors()
