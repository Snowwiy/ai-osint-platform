from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

MonitoringStatus = Literal["healthy", "degraded", "unavailable"]
MonitoringSeverity = Literal["info", "warning", "critical"]
TelemetrySource = Literal["container", "server_endpoint_agent", "backend_host_agent"]


class MonitoringServiceStatus(BaseModel):
    key: str
    label: str
    status: MonitoringStatus
    detail: str
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class MonitoringServicesResponse(BaseModel):
    generated_at: datetime
    status: MonitoringStatus
    items: list[MonitoringServiceStatus]


class AgentTelemetryIngest(BaseModel):
    agent_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    platform: Literal["windows", "linux", "macos", "other"] = "other"
    agent_role: Literal["server_host", "backend_host"] = "backend_host"
    hostname: str | None = Field(default=None, max_length=255)
    os_name: str | None = Field(default=None, max_length=100)
    os_version: str | None = Field(default=None, max_length=100)
    os_build: str | None = Field(default=None, max_length=100)
    collected_at: datetime
    cpu_percent: float | None = Field(default=None, ge=0, le=100)
    memory_percent: float | None = Field(default=None, ge=0, le=100)
    disk_percent: float | None = Field(default=None, ge=0, le=100)
    process_count: int | None = Field(default=None, ge=0, le=1_000_000)
    uptime_seconds: int | None = Field(default=None, ge=0)
    listening_tcp_ports: list[int] = Field(default_factory=list, max_length=64)

    @field_validator("listening_tcp_ports")
    @classmethod
    def validate_listening_ports(cls, value: list[int]) -> list[int]:
        if any(port < 1 or port > 65535 for port in value):
            raise ValueError("listening TCP ports must be between 1 and 65535")
        return sorted(set(value))

    @field_validator("collected_at")
    @classmethod
    def validate_collected_at(cls, value: datetime) -> datetime:
        normalized = value if value.tzinfo else value.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        if normalized > now + timedelta(minutes=5):
            raise ValueError("collected_at cannot be more than five minutes ahead")
        if normalized < now - timedelta(days=1):
            raise ValueError("collected_at cannot be more than one day old")
        return normalized

    @model_validator(mode="after")
    def require_metric(self) -> AgentTelemetryIngest:
        values = (
            self.cpu_percent,
            self.memory_percent,
            self.disk_percent,
            self.process_count,
            self.uptime_seconds,
        )
        if all(value is None for value in values):
            raise ValueError("at least one telemetry metric is required")
        return self


class MonitoringSystemResponse(BaseModel):
    generated_at: datetime
    source: TelemetrySource
    metric_scope: str
    available: bool
    stale: bool
    agent_id: str | None = None
    platform: str
    hostname: str | None = None
    os_name: str | None = None
    os_version: str | None = None
    os_build: str | None = None
    collected_at: datetime | None = None
    received_at: datetime | None = None
    cpu_percent: float | None = Field(default=None, ge=0, le=100)
    memory_percent: float | None = Field(default=None, ge=0, le=100)
    disk_percent: float | None = Field(default=None, ge=0, le=100)
    process_count: int | None = Field(default=None, ge=0)
    uptime_seconds: int | None = Field(default=None, ge=0)
    listening_tcp_ports: list[int] = Field(default_factory=list)
    freshness_seconds: int | None = Field(default=None, ge=0)
    fallback_reason: str | None = None
    detail: str


class AgentTelemetryIngestResponse(BaseModel):
    accepted: bool
    received_at: datetime
    source: Literal["local_agent"] = "local_agent"
    message: str


class MonitoringAssetItem(BaseModel):
    investigation_id: uuid.UUID
    title: str
    status: MonitoringStatus
    investigation_status: str
    scope_status: str
    authorization_status: str
    targets: int = Field(ge=0)
    stale_targets: int = Field(ge=0)
    unresolved_high: int = Field(ge=0)
    unresolved_critical: int = Field(ge=0)
    evidence_records: int = Field(ge=0)
    report_status: str
    closure_status: str
    action_url: str


class MonitoringAssetsResponse(BaseModel):
    generated_at: datetime
    stale_after_days: int = Field(ge=1)
    investigations: int = Field(ge=0)
    targets: int = Field(ge=0)
    healthy_assets: int = Field(ge=0)
    assets_needing_review: int = Field(ge=0)
    stale_assets: int = Field(ge=0)
    high_risk_assets: int = Field(ge=0)
    out_of_scope_assets: int = Field(ge=0)
    unresolved_high: int = Field(ge=0)
    unresolved_critical: int = Field(ge=0)
    findings_by_severity: dict[str, int]
    authorization_risks: int = Field(ge=0)
    repeated_report_failures: int = Field(ge=0)
    repeated_ai_degraded: int = Field(ge=0)
    items: list[MonitoringAssetItem]


class MonitoringAlert(BaseModel):
    id: uuid.UUID | None = None
    key: str
    severity: MonitoringSeverity
    title: str
    message: str
    category: str
    source: str = "local_monitoring"
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    action_url: str
    investigation_id: uuid.UUID | None = None
    count: int = Field(default=1, ge=1)
    suppressed: bool = False
    suppressed_due_to_maintenance: bool = False
    suppression_reason: str | None = None


class MonitoringAlertsResponse(BaseModel):
    generated_at: datetime
    total: int = Field(ge=0)
    notifications_created: int = Field(ge=0)
    notifications_existing: int = Field(ge=0)
    items: list[MonitoringAlert]


class MonitoringRecentError(BaseModel):
    category: str
    action: str
    occurred_at: datetime
    investigation_id: uuid.UUID | None = None


class MonitoringOverviewResponse(BaseModel):
    generated_at: datetime
    status: MonitoringStatus
    release_version: str
    polling_interval_options: list[int]
    recommended_polling_interval: int
    services: MonitoringServicesResponse
    system: MonitoringSystemResponse
    assets: MonitoringAssetsResponse
    alerts: MonitoringAlertsResponse
    recent_errors: list[MonitoringRecentError]


class MonitoringStartupStatus(BaseModel):
    generated_at: datetime
    next_refresh_at: datetime | None
    status: Literal["loaded", "disabled"]
    message: str
    platform_status: MonitoringStatus
    release_version: str
    desktop_auto_monitoring_enabled: bool
    auto_refresh_enabled: bool
    auto_refresh_seconds: int = Field(ge=15, le=300)
    server_host_metrics_enabled: bool
    server_host_metrics_interval_seconds: int = Field(ge=30, le=3600)
    lan_endpoint_agent_interval_seconds: int = Field(ge=30, le=3600)
    posture_recompute_interval_seconds: int = Field(ge=300, le=86_400)
    lan_monitoring_enabled: bool
    service_check_enabled: bool
    lan_auto_discovery_on_start: bool
    lan_auto_service_check_on_start: bool
    lan_auto_discovery_interval_seconds: int = Field(ge=300)
    lan_auto_service_check_interval_seconds: int = Field(ge=600)
    allowed_cidrs: list[str]
    service_ports: list[int]
    discovery_disabled_reason: str | None
    service_check_disabled_reason: str | None
    services_total: int = Field(ge=0)
    active_alerts: int = Field(ge=0)
    alerts_created: int = Field(ge=0)
    triage_total: int = Field(ge=0)
    agent_total: int | None = Field(default=None, ge=0)
    agent_covered: int | None = Field(default=None, ge=0)
    assessed_posture: int | None = Field(default=None, ge=0)
    open_recommendations: int | None = Field(default=None, ge=0)
    baseline_total: int = Field(ge=0)
    baseline_open: int = Field(ge=0)
    optional_telemetry: bool = True
    docker_limitation: str
    safety_notes: list[str]
