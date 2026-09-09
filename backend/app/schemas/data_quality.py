from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DataQualitySeverity = Literal["info", "warning", "high", "critical"]
DataQualityStatus = Literal["open", "acknowledged", "resolved", "ignored"]
DataQualityEntityType = Literal[
    "investigation",
    "engagement",
    "scope_item",
    "finding",
    "evidence",
    "report",
    "deliverable",
    "closure",
    "notification",
    "saved_view",
    "user",
    "audit_log",
    "demo_data",
    "system",
]


class DataQualityIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issue_type: str
    severity: DataQualitySeverity
    status: DataQualityStatus
    entity_type: DataQualityEntityType
    entity_id: uuid.UUID | None = None
    related_entity_type: str | None = None
    related_entity_id: uuid.UUID | None = None
    title: str
    description: str
    recommendation: str
    action_url: str | None = None
    detected_at: datetime
    resolved_at: datetime | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by: uuid.UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class DataQualityIssueListResponse(BaseModel):
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    items: list[DataQualityIssueResponse]


class DataQualityOverviewResponse(BaseModel):
    total_issues: int = Field(ge=0)
    open_issues: int = Field(ge=0)
    critical_issues: int = Field(ge=0)
    high_issues: int = Field(ge=0)
    warning_issues: int = Field(ge=0)
    acknowledged_issues: int = Field(ge=0)
    resolved_issues: int = Field(ge=0)
    ignored_issues: int = Field(ge=0)
    by_entity_type: dict[str, int] = Field(default_factory=dict)
    by_issue_type: dict[str, int] = Field(default_factory=dict)
    last_scan_at: datetime | None = None
    scan_status: Literal["not_run", "healthy", "attention", "critical"]


class DataQualityScanResponse(BaseModel):
    scanned_at: datetime
    detected: int = Field(ge=0)
    created: int = Field(ge=0)
    existing: int = Field(ge=0)
    scan_limit: int = Field(ge=1)
    overview: DataQualityOverviewResponse


class MaintenanceDryRunResponse(BaseModel):
    generated_at: datetime
    would_detect: int = Field(ge=0)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_entity_type: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    destructive_changes: bool = False


class StaleNotificationArchiveRequest(BaseModel):
    older_than_days: int = Field(default=90, ge=30, le=3650)


class StaleNotificationArchiveResponse(BaseModel):
    archived: int = Field(ge=0)
    older_than_days: int = Field(ge=30)
    message: str
