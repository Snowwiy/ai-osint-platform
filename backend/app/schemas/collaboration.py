from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.case_management import InvestigationWorkflowStatus

EscalationLevel = Literal[
    "informational",
    "analyst_review",
    "senior_review",
    "urgent_review",
]
CollaborationScope = Literal["owned", "assigned", "watching"]


class CollaborationUser(BaseModel):
    id: uuid.UUID
    username: str
    email: str


class InvestigationOwnershipUpdate(BaseModel):
    owner_id: uuid.UUID | None = None
    assigned_analyst_ids: list[uuid.UUID] | None = Field(
        default=None,
        max_length=100,
    )
    watcher_ids: list[uuid.UUID] | None = Field(default=None, max_length=100)
    reason: str | None = Field(default=None, max_length=2000)


class InvestigationOwnershipResponse(BaseModel):
    investigation_id: uuid.UUID
    owner: CollaborationUser
    assigned_analysts: list[CollaborationUser] = Field(default_factory=list)
    watchers: list[CollaborationUser] = Field(default_factory=list)


class InvestigationStateUpdate(BaseModel):
    state: InvestigationWorkflowStatus
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("reason cannot be blank")
        return clean


class InvestigationHandoffCreate(BaseModel):
    new_owner_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=4000)
    context_transfer: str | None = Field(default=None, max_length=10_000)
    pending_work_summary: str | None = Field(default=None, max_length=10_000)
    unresolved_findings_summary: str | None = Field(
        default=None,
        max_length=10_000,
    )
    remediation_status_summary: str | None = Field(
        default=None,
        max_length=10_000,
    )

    @field_validator(
        "reason",
        "context_transfer",
        "pending_work_summary",
        "unresolved_findings_summary",
        "remediation_status_summary",
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None


class InvestigationHandoffResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    previous_owner_id: uuid.UUID
    new_owner_id: uuid.UUID
    initiated_by: uuid.UUID | None
    reason: str
    context_transfer: str | None
    pending_work_summary: str | None
    unresolved_findings_summary: str | None
    remediation_status_summary: str | None
    created_at: datetime


class EscalationCreate(BaseModel):
    level: EscalationLevel
    reason: str = Field(min_length=1, max_length=4000)

    @field_validator("reason")
    @classmethod
    def strip_escalation_reason(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("reason cannot be blank")
        return clean


class EscalationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    level: EscalationLevel
    reason: str
    created_by: uuid.UUID | None
    created_at: datetime


class CollaborationInvestigation(BaseModel):
    id: uuid.UUID
    title: str
    state: InvestigationWorkflowStatus
    priority: str
    scope: CollaborationScope
    owner_id: uuid.UUID
    open_tasks: int = Field(ge=0)
    blocked_tasks: int = Field(ge=0)
    overdue_tasks: int = Field(ge=0)
    urgent_findings: int = Field(ge=0)
    escalation_count: int = Field(ge=0)
    updated_at: datetime


class CollaborationActivity(BaseModel):
    id: int
    investigation_id: uuid.UUID
    investigation_title: str
    actor_id: uuid.UUID | None
    action: str
    timestamp: datetime
    metadata: dict[str, object] = Field(default_factory=dict)


class CollaborationDashboardResponse(BaseModel):
    generated_at: datetime
    owned: list[CollaborationInvestigation] = Field(default_factory=list)
    assigned: list[CollaborationInvestigation] = Field(default_factory=list)
    watching: list[CollaborationInvestigation] = Field(default_factory=list)
    needs_attention: list[CollaborationInvestigation] = Field(default_factory=list)
    recent_coordination: list[CollaborationActivity] = Field(default_factory=list)
