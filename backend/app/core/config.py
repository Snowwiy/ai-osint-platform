from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

EnvironmentName = Literal["development", "staging", "production"]


class Settings(BaseSettings):
    APP_SECRET_KEY: str = Field(
        default="dev-only-change-me-raventech-secret-key",
        validation_alias=AliasChoices("APP_SECRET_KEY", "SECRET_KEY"),
        exclude=True,
    )
    APP_ENVIRONMENT: EnvironmentName = "development"
    FRONTEND_URL: str = "http://localhost:5173"
    APP_ALLOWED_ORIGINS: str = Field(
        default="http://localhost:5173",
        validation_alias=AliasChoices("APP_ALLOWED_ORIGINS", "CORS_ORIGINS"),
    )
    MAX_REQUEST_BODY_BYTES: int = 2_000_000
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    AUTH_FAILURE_LIMIT: int = 5
    AUTH_FAILURE_WINDOW_SECONDS: int = 900
    LOG_LEVEL: str = "DEBUG"
    REQUEST_ID_HEADER: str = "X-Request-ID"

    DATABASE_URL: str = (
        "postgresql+asyncpg://raventech:raventech_dev@localhost:5432/raventech"
    )
    TEST_DATABASE_URL: str = ""
    DATABASE_CONNECT_RETRIES: int = 5
    DATABASE_CONNECT_RETRY_SECONDS: float = 1.0
    DATABASE_STATEMENT_TIMEOUT_MS: int = 30_000

    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CONNECT_RETRIES: int = 5
    REDIS_CONNECT_RETRY_SECONDS: float = 1.0
    CELERY_TASK_MAX_RETRIES: int = 3
    CELERY_TASK_RETRY_BACKOFF_MAX_SECONDS: int = 300
    CELERY_WORKER_CONCURRENCY: int = 2

    CHROMA_DATA_PATH: str = "/data/chroma"

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"
    OPENAI_API_KEY: str = ""
    OBSIDIAN_WIKI_PATH: str = ""

    REPORT_COMPANY_NAME: str = "RavenTech"
    REPORT_LOGO_PATH: str = ""
    REPORT_PRIMARY_COLOR: str = "#7C3AED"
    REPORT_SECONDARY_COLOR: str = "#111827"

    SHODAN_API_KEY: str = ""
    VT_API_KEY: str = ""
    ABUSEIPDB_API_KEY: str = ""
    OTX_API_KEY: str = ""
    URLSCAN_API_KEY: str = ""
    SECURITYTRAILS_API_KEY: str = ""
    CENSYS_API_ID: str = ""
    CENSYS_SECRET: str = ""
    HIBP_API_KEY: str = ""
    GITHUB_TOKEN: str = ""

    ADMIN_USERNAME: str = "admin"
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""

    @property
    def allowed_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.APP_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def is_production(self) -> bool:
        return self.APP_ENVIRONMENT == "production"

    @property
    def is_staging(self) -> bool:
        return self.APP_ENVIRONMENT == "staging"

    @property
    def debug_enabled(self) -> bool:
        return self.APP_ENVIRONMENT == "development"

    @property
    def sync_database_url(self) -> str:
        return self.DATABASE_URL.replace("+asyncpg", "+psycopg2")

    @property
    def async_test_database_url(self) -> str:
        return self.TEST_DATABASE_URL or self.DATABASE_URL

    @property
    def sync_test_database_url(self) -> str:
        return self.async_test_database_url.replace("+asyncpg", "+psycopg2")

    def startup_errors(self) -> list[str]:
        errors: list[str] = []
        required_values = {
            "SECRET_KEY/APP_SECRET_KEY": self.APP_SECRET_KEY,
            "DATABASE_URL": self.DATABASE_URL,
            "REDIS_URL": self.REDIS_URL,
            "FRONTEND_URL": self.FRONTEND_URL,
            "CORS_ORIGINS/APP_ALLOWED_ORIGINS": self.APP_ALLOWED_ORIGINS,
        }
        for name, value in required_values.items():
            if not value.strip():
                errors.append(f"{name} is required.")
        if self.ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
            errors.append("ACCESS_TOKEN_EXPIRE_MINUTES must be greater than zero.")
        if self.MAX_REQUEST_BODY_BYTES < 64_000:
            errors.append("MAX_REQUEST_BODY_BYTES is too low for normal API usage.")
        if self.is_production:
            if self.APP_SECRET_KEY.startswith(("dev-", "change-me")):
                errors.append("SECRET_KEY must be replaced for production.")
            if len(self.APP_SECRET_KEY) < 32:
                errors.append("SECRET_KEY must be at least 32 characters.")
            if "*" in self.allowed_origins_list:
                errors.append("CORS_ORIGINS cannot contain '*' in production.")
            if self.FRONTEND_URL not in self.allowed_origins_list:
                errors.append("FRONTEND_URL must be listed in CORS_ORIGINS.")
        return errors

    def startup_warnings(self) -> list[str]:
        warnings: list[str] = []
        if not self.is_production and self.APP_SECRET_KEY.startswith("dev-"):
            warnings.append("Using development SECRET_KEY; do not use this in production.")
        if self.is_staging and self.debug_enabled:
            warnings.append("Staging should not run with debug behavior enabled.")
        if not self.ANTHROPIC_API_KEY:
            warnings.append("ANTHROPIC_API_KEY is empty; AI analysis returns fallback status.")
        if not self.REPORT_LOGO_PATH:
            warnings.append("REPORT_LOGO_PATH is empty; report exports use text branding.")
        return warnings

    def validate_for_startup(self) -> None:
        errors = self.startup_errors()
        if errors:
            joined = " ".join(errors)
            raise RuntimeError(f"Invalid application configuration. {joined}")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
