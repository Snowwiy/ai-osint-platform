from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ChangeSeverity = Literal["info", "low", "medium", "high", "critical"]


class MonitoringChangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_id: uuid.UUID | None
    event_type: str
    severity: ChangeSeverity
    title: str
    description: str
    old_value: str | None
    new_value: str | None
    source: str
    detected_at: datetime
    acknowledged_at: datetime | None
    metadata: dict[str, Any] = Field(
        default_factory=dict, validation_alias="event_metadata"
    )


class MonitoringChangeListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[MonitoringChangeResponse]


class MonitoringChangeOverviewResponse(BaseModel):
    total: int
    unacknowledged: int
    critical: int
    high: int
    new_assets: int
    port_changes: int
    agent_changes: int
    baseline_changes: int


class MonitoringChangeAcknowledgeResponse(BaseModel):
    id: uuid.UUID
    acknowledged_at: datetime


class ServiceHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_id: uuid.UUID
    port: int
    protocol: str
    previous_status: str | None
    current_status: str
    service_name: str | None
    confidence: int
    observed_at: datetime
    source: str


class ServiceHistoryListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ServiceHistoryResponse]


class AssetHistoryResponse(BaseModel):
    asset_id: uuid.UUID
    changes: MonitoringChangeListResponse
    telemetry_samples: int
    telemetry_first_at: datetime | None
    telemetry_last_at: datetime | None
    latest_cpu_percent: float | None
    latest_memory_percent: float | None
    latest_disk_percent: float | None
