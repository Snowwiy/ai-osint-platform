from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

TriageStatus = Literal["new", "triaged", "investigating", "muted", "resolved", "false_positive"]
TriageSeverity = Literal["info", "success", "warning", "critical"]


class MonitoringTriageItem(BaseModel):
    alert_id: uuid.UUID
    status: TriageStatus
    owner_id: uuid.UUID | None
    owner_name: str | None
    severity: TriageSeverity
    source: str
    related_asset_id: uuid.UUID | None
    related_finding_id: uuid.UUID | None
    title: str
    description: str
    action_url: str | None
    first_seen: datetime
    last_seen: datetime
    notes: str | None
    resolution_summary: str | None
    suppressed: bool
    suppressed_due_to_maintenance: bool


class MonitoringTriageListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[MonitoringTriageItem]


class MonitoringTriageUpdate(BaseModel):
    status: TriageStatus | None = None
    notes: str | None = Field(default=None, max_length=4000)
    resolution_summary: str | None = Field(default=None, max_length=4000)

    @field_validator("notes", "resolution_summary")
    @classmethod
    def safe_text(cls, value: str | None) -> str | None:
        return _safe_operator_text(value)

    @model_validator(mode="after")
    def require_change(self) -> MonitoringTriageUpdate:
        if not self.model_fields_set:
            raise ValueError("at least one triage field is required")
        return self


class MonitoringTriageAssign(BaseModel):
    owner_id: uuid.UUID | None


class MonitoringTriageResolution(BaseModel):
    resolution_summary: str = Field(min_length=3, max_length=4000)

    @field_validator("resolution_summary")
    @classmethod
    def safe_text(cls, value: str) -> str:
        cleaned = _safe_operator_text(value)
        if not cleaned:
            raise ValueError("a resolution summary is required")
        return cleaned


class MonitoringTriageMute(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("reason")
    @classmethod
    def safe_text(cls, value: str) -> str:
        cleaned = _safe_operator_text(value)
        if not cleaned:
            raise ValueError("a mute reason is required")
        return cleaned


def _safe_operator_text(value: str | None) -> str | None:
    if value is None:
        return None
    forbidden = ("password", "secret", "token", "credential", "database_url", "invite code", "api key")
    if any(term in value.lower() for term in forbidden):
        raise ValueError("triage text must not contain secrets or credentials")
    return value.strip()
