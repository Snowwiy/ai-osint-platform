from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CaseReviewStatus = Literal[
    "not_submitted",
    "pending_review",
    "changes_requested",
    "approved",
    "rejected",
    "closed",
]
CaseReviewDecision = Literal["approve", "reject", "request_changes"]
ChecklistStatus = Literal["passed", "warning", "failed", "not_applicable"]
CompletenessLabel = Literal["incomplete", "partial", "adequate", "strong", "complete"]
ReportApprovalStatus = Literal[
    "draft",
    "pending_approval",
    "approved",
    "rejected",
    "archived",
]
ReportApprovalDecision = Literal["approve", "reject"]
RemediationValidationStatus = Literal[
    "not_validated",
    "validation_pending",
    "validated",
    "validation_failed",
    "accepted_risk",
]
RemediationValidationDecision = Literal["validate", "fail", "accept_risk"]


class CaseReviewChecklistItem(BaseModel):
    key: str
    label: str
    status: ChecklistStatus
    detail: str


class EvidenceCompletenessResponse(BaseModel):
    investigation_id: uuid.UUID
    score: int = Field(ge=0, le=100)
    label: CompletenessLabel
    contributors: dict[str, int]
    explanation: list[str]
    generated_at: datetime


class CaseReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    review_status: CaseReviewStatus
    submitted_by: uuid.UUID | None
    submitted_at: datetime | None
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    review_notes: str | None
    decision: str | None
    closed_by: uuid.UUID | None
    closed_at: datetime | None
    closure_reason: str | None
    override_reason: str | None
    checklist: list[CaseReviewChecklistItem]
    evidence_completeness_score: int = Field(ge=0, le=100)
    evidence_completeness_label: CompletenessLabel
    evidence_completeness_contributors: dict[str, int]
    created_at: datetime
    updated_at: datetime


class CaseReviewSubmitRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class CaseReviewDecisionRequest(BaseModel):
    decision: CaseReviewDecision
    notes: str = Field(min_length=3, max_length=4000)

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str) -> str:
        return value.strip()


class CaseCloseRequest(BaseModel):
    closure_reason: str = Field(min_length=3, max_length=4000)
    override_reason: str | None = Field(default=None, max_length=4000)

    @field_validator("closure_reason", "override_reason")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()


class ReportApprovalSubmitRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=4000)


class ReportApprovalDecisionRequest(BaseModel):
    decision: ReportApprovalDecision
    notes: str = Field(min_length=3, max_length=4000)


class ReportApprovalResponse(BaseModel):
    report_id: uuid.UUID
    investigation_id: uuid.UUID
    approval_status: ReportApprovalStatus
    approval_submitted_by: uuid.UUID | None
    approval_submitted_at: datetime | None
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    approval_notes: str | None
    rejection_reason: str | None


class RemediationValidationSubmitRequest(BaseModel):
    validation_owner: uuid.UUID | None = None
    validation_notes: str | None = Field(default=None, max_length=4000)


class RemediationValidationDecisionRequest(BaseModel):
    decision: RemediationValidationDecision
    notes: str = Field(min_length=3, max_length=4000)
    failure_reason: str | None = Field(default=None, max_length=4000)


class RemediationValidationResponse(BaseModel):
    finding_id: uuid.UUID
    investigation_id: uuid.UUID
    validation_status: RemediationValidationStatus
    validation_owner: uuid.UUID | None
    validation_notes: str | None
    validated_by: uuid.UUID | None
    validated_at: datetime | None
    failure_reason: str | None


class ReviewBoardItem(BaseModel):
    item_type: Literal[
        "case_review",
        "report_approval",
        "remediation_validation",
        "changes_requested",
        "closure_ready",
    ]
    id: str
    investigation_id: uuid.UUID
    investigation_title: str
    title: str
    status: str
    priority: str
    risk: str
    due_date: str | None = None
    assigned_reviewer: uuid.UUID | None = None
    created_at: datetime | None = None
    detail: str


class ReviewBoardResponse(BaseModel):
    generated_at: datetime
    total: int
    pending_case_reviews: int = Field(ge=0)
    pending_report_approvals: int = Field(ge=0)
    pending_remediation_validations: int = Field(ge=0)
    changes_requested: int = Field(ge=0)
    ready_for_closure: int = Field(ge=0)
    items: list[ReviewBoardItem]
