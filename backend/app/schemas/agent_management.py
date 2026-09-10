from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.lan_monitoring import AssetCriticality, LanAssetResponse


class EnrollmentTokenCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    allowed_cidr: str | None = Field(default=None, max_length=43)
    max_enrollments: int | None = Field(default=None, ge=1, le=1000)
    expires_at: datetime


class EnrollmentTokenResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    token_hint: str
    allowed_cidr: str | None
    max_enrollments: int | None
    enrollment_count: int
    expires_at: datetime
    created_by: uuid.UUID | None
    created_at: datetime
    revoked_at: datetime | None
    status: Literal["active", "expired", "revoked", "exhausted"]


class EnrollmentTokenCreated(EnrollmentTokenResponse):
    token: str = Field(
        description="One-time enrollment secret; it is not stored in plaintext."
    )


class EnrollmentTokenListResponse(BaseModel):
    total: int
    items: list[EnrollmentTokenResponse]


class AgentUpdate(BaseModel):
    monitoring_enabled: bool | None = None
    is_authorized: bool | None = None
    owner: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)
    criticality: AssetCriticality | None = None

    @model_validator(mode="after")
    def require_change(self) -> AgentUpdate:
        if not self.model_fields_set:
            raise ValueError("at least one agent field is required")
        return self


class AgentInventoryItem(LanAssetResponse):
    os_name: str | None = None
    os_version: str | None = None
    agent_version: str | None = None
    telemetry_fresh: bool = False
    enrolled_at: datetime | None = None
    enrollment_token_label: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    group_ids: list[uuid.UUID] = Field(default_factory=list)
    group_names: list[str] = Field(default_factory=list)


class GroupCoverage(BaseModel):
    group_id: uuid.UUID
    group_name: str
    total_assets: int
    monitored_by_agent: int
    stale_agents: int
    risk_indicators: int


class AgentCoverage(BaseModel):
    total_lan_assets: int
    monitored_by_agent: int
    missing_agent: int
    stale_agents: int
    unauthorized_assets: int
    critical_assets_without_telemetry: int
    groups: list[GroupCoverage]


class AgentInventoryResponse(BaseModel):
    total: int
    coverage: AgentCoverage
    items: list[AgentInventoryItem]


class AssetGroupCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    asset_ids: list[uuid.UUID] = Field(default_factory=list, max_length=512)


class AssetGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    asset_ids: list[uuid.UUID] | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def require_change(self) -> AssetGroupUpdate:
        if not self.model_fields_set:
            raise ValueError("at least one group field is required")
        return self


class AssetGroupResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    asset_ids: list[uuid.UUID]
    total_assets: int
    monitored_by_agent: int
    stale_agents: int
    risk_indicators: int
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class AssetGroupListResponse(BaseModel):
    total: int
    items: list[AssetGroupResponse]


class ServiceBaselineCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    asset_id: uuid.UUID | None = None
    group_id: uuid.UUID | None = None
    expected_ports: list[int] = Field(default_factory=list, max_length=32)
    allowed_ports: list[int] = Field(default_factory=list, max_length=32)

    @field_validator("expected_ports", "allowed_ports")
    @classmethod
    def safe_ports(cls, value: list[int]) -> list[int]:
        if any(port < 1 or port > 65535 for port in value):
            raise ValueError("ports must be between 1 and 65535")
        return sorted(set(value))

    @model_validator(mode="after")
    def one_scope(self) -> ServiceBaselineCreate:
        if (self.asset_id is None) == (self.group_id is None):
            raise ValueError("exactly one asset_id or group_id is required")
        return self


class ServiceBaselineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    expected_ports: list[int] | None = Field(default=None, max_length=32)
    allowed_ports: list[int] | None = Field(default=None, max_length=32)

    @field_validator("expected_ports", "allowed_ports")
    @classmethod
    def safe_ports(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if any(port < 1 or port > 65535 for port in value):
            raise ValueError("ports must be between 1 and 65535")
        return sorted(set(value))

    @model_validator(mode="after")
    def require_change(self) -> ServiceBaselineUpdate:
        if not self.model_fields_set:
            raise ValueError("at least one baseline field is required")
        return self


class ServiceBaselineIndicator(BaseModel):
    asset_id: uuid.UUID
    port: int
    indicator_type: Literal["missing_expected_service", "unexpected_open_service"]
    severity: Literal["warning", "critical"]
    detail: str


class ServiceBaselineResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    asset_id: uuid.UUID | None
    group_id: uuid.UUID | None
    expected_ports: list[int]
    allowed_ports: list[int]
    indicators: list[ServiceBaselineIndicator]
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ServiceBaselineListResponse(BaseModel):
    total: int
    items: list[ServiceBaselineResponse]
