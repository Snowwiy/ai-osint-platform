from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LanAssetStatus = Literal["online", "offline", "unknown"]
LanAssetSource = Literal["static", "arp", "ping", "router", "agent"]
LanRiskSeverity = Literal["info", "warning", "critical"]
AssetCriticality = Literal["low", "medium", "high", "critical"]
_MAC_PATTERN = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def _recent_timestamp(value: datetime) -> datetime:
    normalized = value if value.tzinfo else value.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    if normalized > now + timedelta(minutes=5):
        raise ValueError("timestamp cannot be more than five minutes ahead")
    if normalized < now - timedelta(days=1):
        raise ValueError("timestamp cannot be more than one day old")
    return normalized


class LanServiceInput(BaseModel):
    port: int = Field(ge=1, le=65535)
    protocol: Literal["tcp", "udp"] = "tcp"
    service_name: str | None = Field(default=None, max_length=100)
    status: Literal["open", "closed", "filtered", "timeout", "unknown"] = "open"
    service_label: str | None = Field(default=None, max_length=160)
    confidence: int = Field(default=40, ge=0, le=100)
    banner_hint: str | None = Field(default=None, max_length=160)
    non_standard_ssh: bool = False


class LanDiscoveryObservation(BaseModel):
    ip_address: str = Field(min_length=7, max_length=45)
    mac_address: str | None = Field(default=None, max_length=17)
    hostname: str | None = Field(default=None, max_length=255)
    vendor: str | None = Field(default=None, max_length=255)
    asset_type: str = Field(default="unknown", min_length=1, max_length=40)
    source: Literal["static", "arp", "ping", "router"] = "static"
    latency_ms: float | None = Field(default=None, ge=0, le=60_000)
    services: list[LanServiceInput] = Field(default_factory=list, max_length=32)

    @field_validator("mac_address")
    @classmethod
    def validate_mac(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip().replace("-", ":").upper()
        if not _MAC_PATTERN.fullmatch(normalized):
            raise ValueError("mac_address must use six hexadecimal octets")
        return normalized


class LanDiscoveryRequest(BaseModel):
    cidr: str | None = Field(default=None, max_length=43)
    observations: list[LanDiscoveryObservation] = Field(
        default_factory=list, max_length=512
    )


class LanAssetUpdate(BaseModel):
    hostname: str | None = Field(default=None, max_length=255)
    vendor: str | None = Field(default=None, max_length=255)
    asset_type: str | None = Field(default=None, min_length=1, max_length=40)
    notes: str | None = Field(default=None, max_length=2000)
    is_authorized: bool | None = None
    monitoring_enabled: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> LanAssetUpdate:
        if not self.model_fields_set:
            raise ValueError("at least one asset field is required")
        return self


class LanAssetCriticalityUpdate(BaseModel):
    criticality: AssetCriticality
    owner: str | None = Field(default=None, max_length=255)
    business_function: str | None = Field(default=None, max_length=255)
    environment: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=2000)


class LanAgentRegistration(BaseModel):
    ip_address: str = Field(min_length=7, max_length=45)
    mac_address: str | None = Field(default=None, max_length=17)
    hostname: str | None = Field(default=None, max_length=255)
    asset_type: str = Field(default="endpoint", min_length=1, max_length=40)
    os_name: str | None = Field(default=None, max_length=100)
    os_version: str | None = Field(default=None, max_length=100)
    agent_version: str = Field(min_length=1, max_length=40)
    capabilities: list[str] = Field(
        default_factory=lambda: ["basic_telemetry"], max_length=16
    )

    @field_validator("mac_address")
    @classmethod
    def validate_mac(cls, value: str | None) -> str | None:
        return LanDiscoveryObservation.validate_mac(value)

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, value: list[str]) -> list[str]:
        allowed = {"basic_telemetry", "os_basics"}
        if not value or any(item not in allowed for item in value):
            raise ValueError("unsupported endpoint capability")
        return sorted(set(value))


class LanAgentTelemetryIngest(BaseModel):
    asset_id: uuid.UUID
    collected_at: datetime
    cpu_percent: float | None = Field(default=None, ge=0, le=100)
    memory_percent: float | None = Field(default=None, ge=0, le=100)
    disk_percent: float | None = Field(default=None, ge=0, le=100)
    uptime_seconds: int | None = Field(default=None, ge=0, le=2_147_483_647)
    os_name: str | None = Field(default=None, max_length=100)
    os_version: str | None = Field(default=None, max_length=100)
    agent_version: str = Field(min_length=1, max_length=40)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @field_validator("collected_at")
    @classmethod
    def validate_collected_at(cls, value: datetime) -> datetime:
        return _recent_timestamp(value)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(
        cls, value: dict[str, str | int | float | bool | None]
    ) -> dict[str, str | int | float | bool | None]:
        if len(value) > 16:
            raise ValueError("metadata is limited to 16 safe fields")
        forbidden = ("password", "secret", "token", "credential", "authorization")
        if any(any(term in key.lower() for term in forbidden) for key in value):
            raise ValueError("metadata contains a forbidden field name")
        if any(isinstance(item, str) and len(item) > 255 for item in value.values()):
            raise ValueError("metadata string values are limited to 255 characters")
        return value

    @model_validator(mode="after")
    def require_metric(self) -> LanAgentTelemetryIngest:
        if all(
            value is None
            for value in (
                self.cpu_percent,
                self.memory_percent,
                self.disk_percent,
                self.uptime_seconds,
            )
        ):
            raise ValueError("at least one telemetry metric is required")
        return self


class LanRiskIndicator(BaseModel):
    key: str
    severity: LanRiskSeverity
    label: str
    detail: str


class LanAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ip_address: str
    mac_address: str | None
    hostname: str | None
    vendor: str | None
    asset_type: str
    status: LanAssetStatus
    source: str
    first_seen: datetime
    last_seen: datetime | None
    last_checked_at: datetime | None
    confidence: int
    notes: str | None
    is_authorized: bool
    monitoring_enabled: bool
    criticality: AssetCriticality
    owner: str | None
    business_function: str | None
    environment: str | None
    agent_connected: bool
    response_latency_ms: float | None = None
    risk_indicators: list[LanRiskIndicator]
    created_at: datetime
    updated_at: datetime
    enrolled_at: datetime | None = None
    capabilities: list[str] = Field(default_factory=list)


class LanAssetListResponse(BaseModel):
    generated_at: datetime
    enabled: bool
    allowed_cidrs: list[str]
    discovery_interval_seconds: int
    ping_enabled: bool
    service_check_enabled: bool
    docker_limited: bool = True
    limitation: str
    total: int
    online: int
    offline: int
    unauthorized: int
    agent_connected: int
    items: list[LanAssetResponse]


class LanTelemetryResponse(BaseModel):
    id: uuid.UUID
    lan_asset_id: uuid.UUID
    cpu_percent: float | None
    memory_percent: float | None
    disk_percent: float | None
    uptime_seconds: int | None
    os_name: str | None
    os_version: str | None
    agent_version: str | None
    collected_at: datetime
    metadata: dict[str, Any]


class LanTelemetryListResponse(BaseModel):
    total: int
    items: list[LanTelemetryResponse]


class LanServiceResponse(BaseModel):
    id: uuid.UUID
    lan_asset_id: uuid.UUID
    ip_address: str
    port: int
    protocol: str
    service_name: str | None
    service_label: str | None
    confidence: int = Field(ge=0, le=100)
    banner_hint: str | None
    non_standard_ssh: bool
    status: str
    observed_at: datetime
    source: str


class LanServiceListResponse(BaseModel):
    total: int
    service_checks_enabled: bool
    items: list[LanServiceResponse]


class LanServiceCheckResponse(BaseModel):
    asset_id: uuid.UUID
    ip_address: str
    ports_checked: int
    observations_created: int
    open_ports: int
    message: str


class LanOpenPortsResponse(BaseModel):
    total: int
    items: list[LanServiceResponse]


class MonitoringActivationStatus(BaseModel):
    lan_monitoring_enabled: bool
    service_check_enabled: bool
    allowed_cidrs: list[str]
    service_ports: list[int]
    discovery_disabled_reason: str | None
    service_check_disabled_reason: str | None
    env_lines: list[str]
    restart_commands: list[str]
    windows_firewall_note: str
    docker_limitation: str
    optional_telemetry_note: str
    agent_setup_steps: list[str]
    token_enrollment_steps: list[str]


class TargetServiceCheckStatus(BaseModel):
    target_id: uuid.UUID
    target_type: str
    target_is_url_service: bool
    eligible: bool
    reason: str
    lan_asset_id: uuid.UUID | None = None
    ip_address: str | None = None
    configured_ports: list[int]
    last_service_check_at: datetime | None = None
    observations: list[LanServiceResponse] = Field(default_factory=list)


class LanDiscoveryResponse(BaseModel):
    enabled: bool
    cidr: str
    observations_received: int
    assets_created: int
    assets_updated: int
    service_observations_created: int
    limitation: str | None = None
    message: str


class LanAgentRegistrationResponse(BaseModel):
    accepted: bool
    asset_id: uuid.UUID
    monitoring_enabled: bool
    message: str


class LanAgentTelemetryResponse(BaseModel):
    accepted: bool
    asset_id: uuid.UUID
    received_at: datetime
    message: str
