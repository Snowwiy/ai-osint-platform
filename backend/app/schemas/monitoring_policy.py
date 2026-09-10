from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Severity = Literal["info", "warning", "critical"]


class MonitoringPolicyCreate(BaseModel):
    rule_key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9_.-]+$")
    title: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=2, max_length=1000)
    enabled: bool = True
    severity_override: Severity | None = None
    threshold_value: float | None = Field(default=None, ge=0, le=10080)
    threshold_unit: str | None = Field(default=None, max_length=30)
    cooldown_minutes: int = Field(default=240, ge=1, le=10080)
    dedupe_key: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9_.:-]+$")
    max_alerts_per_rule: int = Field(default=3, ge=1, le=100)
    acknowledge_behavior: Literal["keep_active", "suppress"] = "keep_active"


class MonitoringPolicyUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, min_length=2, max_length=1000)
    enabled: bool | None = None
    severity_override: Severity | None = None
    threshold_value: float | None = Field(default=None, ge=0, le=10080)
    threshold_unit: str | None = Field(default=None, max_length=30)
    cooldown_minutes: int | None = Field(default=None, ge=1, le=10080)
    dedupe_key: str | None = Field(
        default=None, min_length=2, max_length=120, pattern=r"^[a-z0-9_.:-]+$"
    )
    max_alerts_per_rule: int | None = Field(default=None, ge=1, le=100)
    acknowledge_behavior: Literal["keep_active", "suppress"] | None = None


class MonitoringPolicyResponse(MonitoringPolicyCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class MonitoringPolicyListResponse(BaseModel):
    total: int
    items: list[MonitoringPolicyResponse]


class MaintenanceWindowCreate(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    start_time: datetime
    end_time: datetime
    affected_assets: list[str] = Field(default_factory=list, max_length=200)
    affected_services: list[str] = Field(default_factory=list, max_length=100)
    suppress_alerts: bool = False
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("start_time", "end_time")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timezone information is required")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def valid_range(self) -> MaintenanceWindowCreate:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if self.end_time - self.start_time > __import__("datetime").timedelta(days=30):
            raise ValueError("maintenance windows cannot exceed 30 days")
        return self


class MaintenanceWindowUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    start_time: datetime | None = None
    end_time: datetime | None = None
    affected_assets: list[str] | None = Field(default=None, max_length=200)
    affected_services: list[str] | None = Field(default=None, max_length=100)
    suppress_alerts: bool | None = None
    reason: str | None = Field(default=None, min_length=3, max_length=1000)

    @field_validator("start_time", "end_time")
    @classmethod
    def timezone_required(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timezone information is required")
        return value.astimezone(UTC) if value else None


class MaintenanceWindowResponse(MaintenanceWindowCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    status: Literal["scheduled", "active", "completed"]


class MaintenanceWindowListResponse(BaseModel):
    total: int
    items: list[MaintenanceWindowResponse]


class AlertSuppressionCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
    ends_at: datetime | None = None

    @field_validator("ends_at")
    @classmethod
    def valid_end(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("timezone information is required")
        normalized = value.astimezone(UTC)
        if normalized <= datetime.now(UTC):
            raise ValueError("ends_at must be in the future")
        return normalized


class AlertSuppressionResponse(BaseModel):
    id: uuid.UUID
    alert_id: uuid.UUID
    source: Literal["manual", "maintenance"]
    reason: str
    starts_at: datetime
    ends_at: datetime | None
    active: bool
    suppressed_due_to_maintenance: bool
