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
