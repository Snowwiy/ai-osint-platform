from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AnalysisWorkflow = Literal[
    "host_current",
    "host_changes",
    "host_resource",
    "host_services",
    "host_ports",
    "lan_current",
    "lan_changes",
    "asset_current",
    "asset_changes",
    "alert_context",
    "posture_context",
    "investigation_context",
    "global_attention",
]
AnalysisWindow = Literal["15m", "1h", "6h", "12h", "24h", "7d"]
ResourceKind = Literal["cpu", "memory", "disk"]
Confidence = Literal["high", "medium", "low", "insufficient"]


class AnalysisProcess(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    pid: int = Field(ge=0, le=4_294_967_295)
    name: str = Field(max_length=160)
    cpu_percent: float = Field(alias="cpuPercent", ge=0, le=100)
    memory_bytes: int = Field(alias="memoryBytes", ge=0, le=2**63 - 1)
    started_at_unix: int = Field(alias="startedAtUnix", ge=0)
    runtime_seconds: int = Field(alias="runtimeSeconds", ge=0)


class AnalysisService(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    name: str = Field(max_length=256)
    display_name: str = Field(alias="displayName", max_length=256)
    state: str = Field(max_length=40)
    start_type: str | None = Field(default=None, alias="startType", max_length=40)
    pid: int | None = Field(default=None, ge=0, le=4_294_967_295)


class DesktopAnalysisInventory(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    available: bool = False
    processes: list[AnalysisProcess] = Field(default_factory=list, max_length=250)
    services: list[AnalysisService] = Field(default_factory=list, max_length=250)
    detail: str = Field(default="", max_length=200)


class EvidenceAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow: AnalysisWorkflow
    window: AnalysisWindow = "1h"
    resource: ResourceKind | None = None
    scope_id: uuid.UUID | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    desktop_inventory: DesktopAnalysisInventory | None = None

    @model_validator(mode="after")
    def validate_scope_and_window(self) -> EvidenceAnalysisRequest:
        scoped = {
            "asset_current",
            "asset_changes",
            "alert_context",
            "investigation_context",
            "posture_context",
        }
        if self.workflow in scoped and self.scope_id is None:
            raise ValueError("This workflow requires a selected record.")
        if self.workflow == "host_resource" and self.resource is None:
            raise ValueError("A resource type is required for resource analysis.")
        if (self.start_at is None) != (self.end_at is None):
            raise ValueError("Both explicit time bounds are required together.")
        if self.start_at is not None and self.end_at is not None:
            start = _aware(self.start_at)
            end = _aware(self.end_at)
            if end <= start or (end - start).total_seconds() > 7 * 24 * 60 * 60:
                raise ValueError(
                    "Explicit time window must be positive and at most 7 days."
                )
        return self


class EvidenceAnalysisView(BaseModel):
    id: uuid.UUID
    workflow: AnalysisWorkflow
    scope_type: str
    scope_id: str | None
    generated_at: datetime
    window: dict[str, Any]
    status: Literal["completed", "completed_with_warnings"]
    summary: str
    confidence: Confidence
    evidence_count: int = Field(ge=0)
    bundle_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    result: dict[str, Any]
    model_metadata: dict[str, Any] = Field(default_factory=dict)
    deduplicated: bool = False


class EvidenceAnalysisListItem(BaseModel):
    id: uuid.UUID
    workflow: str
    scope_type: str
    scope_id: str | None
    generated_at: datetime
    status: str
    summary: str
    confidence: Confidence
    evidence_count: int
    bundle_sha256: str


class AnalysisComparisonRequest(BaseModel):
    first_analysis_id: uuid.UUID
    second_analysis_id: uuid.UUID


class AnalysisComparisonResponse(BaseModel):
    first_analysis_id: uuid.UUID
    second_analysis_id: uuid.UUID
    same_bundle: bool
    summary: str
    differences: list[str] = Field(default_factory=list, max_length=30)


def _aware(value: datetime) -> datetime:
    from datetime import UTC

    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
