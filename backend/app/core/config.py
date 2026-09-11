from __future__ import annotations

import ipaddress
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

EnvironmentName = Literal["development", "staging", "production"]
RegisteredUserRole = Literal["viewer", "analyst"]


class Settings(BaseSettings):
    APP_NAME: str = "RavenTech OSINT"
    APP_VERSION: str = "5.0.0-rc6"
    APP_MODE: str = "local"
    DESKTOP_MODE_ENABLED: bool = False
    LOCAL_FRONTEND_URL: str = "http://localhost:5173"
    LOCAL_BACKEND_URL: str = "http://localhost:8000"
    LOCAL_OPERATOR_OPEN_BROWSER: bool = True
    APP_RELEASE_CHANNEL: str = Field(
        default="release-candidate",
        validation_alias=AliasChoices("APP_RELEASE_CHANNEL", "RELEASE_CHANNEL"),
    )
    APP_BUILD_DATE: str = "local"
    APP_GIT_COMMIT: str = ""
    APP_SECRET_KEY: str = Field(
        default="dev-only-change-me-raventech-secret-key",
        validation_alias=AliasChoices("APP_SECRET_KEY", "SECRET_KEY"),
        exclude=True,
    )
    APP_ENVIRONMENT: EnvironmentName = "development"
    FRONTEND_URL: str = "http://localhost:5173"
    APP_ALLOWED_ORIGINS: str = Field(
        default="http://localhost:5173",
        validation_alias=AliasChoices(
            "APP_ALLOWED_ORIGINS",
            "CORS_ORIGINS",
            "BACKEND_CORS_ORIGINS",
        ),
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
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    OPENAI_API_KEY: str = ""
    OBSIDIAN_WIKI_PATH: str = ""

    REPORT_COMPANY_NAME: str = "RavenTech"
    REPORT_LOGO_PATH: str = ""
    REPORT_PRIMARY_COLOR: str = "#7C3AED"
    REPORT_SECONDARY_COLOR: str = "#111827"
    ENABLE_DEMO_MODE: bool = False
    LAN_MONITORING_ENABLED: bool = False
    LAN_ALLOWED_CIDRS: str = "192.168.0.0/24"
    LAN_DISCOVERY_INTERVAL_SECONDS: int = 300
    LAN_DISCOVERY_PING_ENABLED: bool = False
    LAN_SERVICE_CHECK_ENABLED: bool = False
    LAN_SERVICE_CHECK_PORTS: str = "22,80,443,445,3389,8080,8443"
    LAN_SERVICE_CHECK_TIMEOUT_SECONDS: float = 2.0
    LAN_SERVICE_CHECK_MAX_HOSTS: int = 256
    LAN_SERVICE_CHECK_MAX_PORTS: int = 32
    LAN_REJECT_PUBLIC_CIDRS: bool = True
    LAN_SSH_BANNER_DETECTION_ENABLED: bool = True
    LAN_AGENT_TOKEN: str = Field(default="", exclude=True)
    LAN_AGENT_MAX_STALE_MINUTES: int = 10
    VULNERABILITY_BASELINE_ENABLED: bool = True
    VULNERABILITY_HIGH_RESOURCE_PERCENT: int = 90
    VULNERABILITY_RESOURCE_SUSTAINED_SAMPLES: int = 3
    VULNERABILITY_STALE_ASSET_HOURS: int = 24
    PUBLIC_REGISTRATION_ENABLED: bool = False
    REGISTRATION_REQUIRES_APPROVAL: bool = True
    REGISTRATION_INVITE_CODE: str = Field(default="", exclude=True)
    DEFAULT_REGISTERED_USER_ROLE: RegisteredUserRole = "viewer"

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
    def has_placeholder_secret_key(self) -> bool:
        normalized = self.APP_SECRET_KEY.strip().lower()
        return normalized.startswith(("dev-", "change-me", "replace-with"))

    @property
    def has_weak_secret_key(self) -> bool:
        return len(self.APP_SECRET_KEY.strip()) < 32 or self.has_placeholder_secret_key

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
        if self.LAN_DISCOVERY_INTERVAL_SECONDS < 60:
            errors.append("LAN_DISCOVERY_INTERVAL_SECONDS must be at least 60.")
        if self.LAN_AGENT_MAX_STALE_MINUTES < 2:
            errors.append("LAN_AGENT_MAX_STALE_MINUTES must be at least 2.")
        if not 0.2 <= self.LAN_SERVICE_CHECK_TIMEOUT_SECONDS <= 5:
            errors.append(
                "LAN_SERVICE_CHECK_TIMEOUT_SECONDS must be between 0.2 and 5."
            )
        if not 1 <= self.LAN_SERVICE_CHECK_MAX_HOSTS <= 256:
            errors.append("LAN_SERVICE_CHECK_MAX_HOSTS must be between 1 and 256.")
        if not 1 <= self.LAN_SERVICE_CHECK_MAX_PORTS <= 32:
            errors.append("LAN_SERVICE_CHECK_MAX_PORTS must be between 1 and 32.")
        if not 50 <= self.VULNERABILITY_HIGH_RESOURCE_PERCENT <= 100:
            errors.append(
                "VULNERABILITY_HIGH_RESOURCE_PERCENT must be between 50 and 100."
            )
        if not 2 <= self.VULNERABILITY_RESOURCE_SUSTAINED_SAMPLES <= 10:
            errors.append(
                "VULNERABILITY_RESOURCE_SUSTAINED_SAMPLES must be between 2 and 10."
            )
        if self.VULNERABILITY_STALE_ASSET_HOURS < 1:
            errors.append("VULNERABILITY_STALE_ASSET_HOURS must be at least 1.")
        try:
            networks = [
                ipaddress.ip_network(value.strip(), strict=False)
                for value in self.LAN_ALLOWED_CIDRS.split(",")
                if value.strip()
            ]
            private_networks = (
                ipaddress.IPv4Network("10.0.0.0/8"),
                ipaddress.IPv4Network("172.16.0.0/12"),
                ipaddress.IPv4Network("192.168.0.0/16"),
            )
            if not networks:
                errors.append(
                    "LAN_ALLOWED_CIDRS must contain at least one private CIDR."
                )
            elif any(
                network.version != 4
                or not any(network.subnet_of(private) for private in private_networks)
                for network in networks
            ):
                errors.append("LAN_ALLOWED_CIDRS accepts private IPv4 CIDRs only.")
        except ValueError:
            errors.append("LAN_ALLOWED_CIDRS contains an invalid CIDR.")
        try:
            ports = [
                int(value.strip())
                for value in self.LAN_SERVICE_CHECK_PORTS.split(",")
                if value.strip()
            ]
            if any(port < 1 or port > 65535 for port in ports):
                raise ValueError
            if len(ports) > self.LAN_SERVICE_CHECK_MAX_PORTS:
                errors.append(
                    "LAN_SERVICE_CHECK_PORTS exceeds LAN_SERVICE_CHECK_MAX_PORTS."
                )
        except ValueError:
            errors.append("LAN_SERVICE_CHECK_PORTS must contain valid TCP ports.")
        if self.is_production:
            if self.has_placeholder_secret_key:
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
        if not self.is_production and self.has_weak_secret_key:
            warnings.append(
                "Using a weak or placeholder SECRET_KEY; do not use this in production."
            )
        if self.is_staging and self.debug_enabled:
            warnings.append("Staging should not run with debug behavior enabled.")
        if not self.ANTHROPIC_API_KEY:
            warnings.append(
                "ANTHROPIC_API_KEY is empty; AI analysis returns fallback status."
            )
        if not self.REPORT_LOGO_PATH:
            warnings.append(
                "REPORT_LOGO_PATH is empty; report exports use text branding."
            )
        if self.is_production and self.ENABLE_DEMO_MODE:
            warnings.append(
                "ENABLE_DEMO_MODE is ignored in production; demo data remains disabled."
            )
        if self.is_production and self.PUBLIC_REGISTRATION_ENABLED:
            warnings.append(
                "PUBLIC_REGISTRATION_ENABLED is true in production; verify invite "
                "and approval policy before exposing the service."
            )
        if self.LAN_MONITORING_ENABLED and not self.LAN_AGENT_TOKEN:
            warnings.append(
                "LAN_AGENT_TOKEN is empty; endpoint-agent registration and telemetry are disabled."
            )
        return warnings

    def validate_for_startup(self) -> None:
        errors = self.startup_errors()
        if errors:
            joined = " ".join(errors)
            raise RuntimeError(f"Invalid application configuration. {joined}")

    @property
    def effective_registered_user_role(self) -> str:
        # Platform users currently support admin/analyst. Public registration never
        # creates admins; viewer access is represented at investigation membership.
        return "analyst"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
