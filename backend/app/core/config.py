from __future__ import annotations

import secrets
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_SECRET_KEY: str = Field(
        default_factory=lambda: secrets.token_hex(64),
        exclude=True,
    )
    APP_ENVIRONMENT: Literal["development", "production"] = "development"
    APP_ALLOWED_ORIGINS: str = "http://localhost:5173"

    DATABASE_URL: str = (
        "postgresql+asyncpg://raventech:raventech_dev@localhost:5432/raventech"
    )
    TEST_DATABASE_URL: str = ""

    REDIS_URL: str = "redis://localhost:6379/0"

    CHROMA_DATA_PATH: str = "/data/chroma"

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"
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
    def sync_database_url(self) -> str:
        return self.DATABASE_URL.replace("+asyncpg", "+psycopg2")

    @property
    def async_test_database_url(self) -> str:
        return self.TEST_DATABASE_URL or self.DATABASE_URL

    @property
    def sync_test_database_url(self) -> str:
        return self.async_test_database_url.replace("+asyncpg", "+psycopg2")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
