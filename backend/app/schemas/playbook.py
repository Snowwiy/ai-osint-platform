from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.finding import FindingSeverity

PlaybookCategory = Literal[
    "exposure_review",
    "dns_email_security",
    "infrastructure_review",
    "technology_review",
    "access_control",
    "report_review",
    "remediation_tracking",
]
PlaybookStepType = Literal[
    "analyst_review",
    "evidence_validation",
    "remediation_task",
    "report_update",
    "stakeholder_review",
    "closure_check",
]
PlaybookRunStatus = Literal[
    "open",
    "in_progress",
    "blocked",
    "completed",
    "cancelled",
]
PlaybookRunStepStatus = Literal["pending", "in_progress", "completed", "skipped"]
RemediationStatus = Literal[
    "not_started",
    "validating",
    "remediation_planned",
    "in_progress",
    "pending_verification",
    "remediated",
    "accepted_risk",
    "false_positive",
]


class PlaybookStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    playbook_id: uuid.UUID
    order_index: int
    title: str
    description: str
    expected_output: str | None
    step_type: PlaybookStepType
    required: bool
    created_at: datetime
    updated_at: datetime


class DefensivePlaybookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    category: PlaybookCategory
    severity: FindingSeverity
    framework: str | None
    is_active: bool
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    steps: list[PlaybookStepResponse] = Field(default_factory=list)


class FindingPlaybookRecommendation(BaseModel):
    playbook: DefensivePlaybookResponse
    reason: str
    recommended: bool = True


class PlaybookRunStepResponse(BaseModel):
    id: uuid.UUID
    playbook_run_id: uuid.UUID
    playbook_step_id: uuid.UUID
    status: PlaybookRunStepStatus
    analyst_note: str | None
    completed_by: uuid.UUID | None
    completed_at: datetime | None
    step: PlaybookStepResponse


class PlaybookRunResponse(BaseModel):
    id: uuid.UUID
    investigation_id: uuid.UUID
    finding_id: uuid.UUID
    finding_title: str
    playbook_id: uuid.UUID
    playbook_name: str
    status: PlaybookRunStatus
    started_by: uuid.UUID | None
    completed_by: uuid.UUID | None
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    steps: list[PlaybookRunStepResponse] = Field(default_factory=list)


class PlaybookRunUpdate(BaseModel):
    status: PlaybookRunStatus


class PlaybookRunStepUpdate(BaseModel):
    status: PlaybookRunStepStatus
    analyst_note: str | None = Field(default=None, max_length=4000)


class FindingRemediationUpdate(BaseModel):
    remediation_status: RemediationStatus
    remediation_owner: uuid.UUID | None = None
    remediation_due_date: date | None = None
    remediation_notes: str | None = Field(default=None, max_length=8000)
    verification_notes: str | None = Field(default=None, max_length=8000)
    verified_by: uuid.UUID | None = None


class FindingRemediationResponse(BaseModel):
    finding_id: uuid.UUID
    investigation_id: uuid.UUID
    remediation_status: RemediationStatus
    remediation_owner: uuid.UUID | None
    remediation_due_date: date | None
    remediation_notes: str | None
    verification_notes: str | None
    verified_by: uuid.UUID | None
    verified_at: datetime | None
