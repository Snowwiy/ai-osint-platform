from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CaseClosureStatus = Literal["draft", "in_review", "approved", "closed", "reopened"]
CaseClosureChecklistStatus = Literal[
    "pending",
    "completed",
    "blocked",
    "not_applicable",
]
CaseFinalRiskRating = Literal[
    "low",
    "moderate",
    "elevated",
    "high",
    "critical",
    "not_assessed",
]
CaseDeliverableType = Literal[
    "executive_report",
    "technical_report",
    "evidence_appendix",
    "remediation_plan",
    "scope_summary",
    "audit_summary",
    "final_package",
]
CaseDeliverableStatus = Literal[
    "draft",
    "ready",
    "approved",
    "delivered",
    "archived",
]
CaseDeliverableFormat = Literal["pdf", "docx", "html", "md"]
PackageReadinessStatus = Literal[
    "ready",
    "ready_with_warnings",
    "missing_required_deliverables",
]


class CaseClosureUpdate(BaseModel):
    closure_summary: str | None = Field(default=None, max_length=6000)
    final_risk_rating: CaseFinalRiskRating | None = None

    @field_validator("closure_summary")
    @classmethod
    def clean_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class CaseClosureSubmitRequest(BaseModel):
    closure_summary: str | None = Field(default=None, max_length=6000)

    @field_validator("closure_summary")
    @classmethod
    def clean_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class CaseClosureCloseRequest(BaseModel):
    closure_summary: str = Field(min_length=3, max_length=6000)
    override_reason: str | None = Field(default=None, max_length=4000)

    @field_validator("closure_summary", "override_reason")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class CaseClosureChecklistUpdate(BaseModel):
    status: CaseClosureChecklistStatus
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class CaseClosureChecklistItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    closure_id: uuid.UUID | None
    key: str
    label: str
    description: str | None
    status: CaseClosureChecklistStatus
    required: bool
    completed_by: uuid.UUID | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CaseDeliverableCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    deliverable_type: CaseDeliverableType
    status: CaseDeliverableStatus = "draft"
    report_id: uuid.UUID | None = None
    export_format: CaseDeliverableFormat | None = None
    file_reference: str | None = Field(default=None, max_length=500)

    @field_validator("title", "file_reference")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class CaseDeliverableUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    deliverable_type: CaseDeliverableType | None = None
    status: CaseDeliverableStatus | None = None
    report_id: uuid.UUID | None = None
    export_format: CaseDeliverableFormat | None = None
    file_reference: str | None = Field(default=None, max_length=500)

    @field_validator("title", "file_reference")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class CaseDeliverableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    title: str
    deliverable_type: CaseDeliverableType
    status: CaseDeliverableStatus
    report_id: uuid.UUID | None
    export_format: CaseDeliverableFormat | None
    file_reference: str | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class CaseDeliverableListResponse(BaseModel):
    total: int = Field(ge=0)
    items: list[CaseDeliverableResponse]


class EvidencePackageSummary(BaseModel):
    evidence_count: int = Field(ge=0)
    findings_with_evidence: int = Field(ge=0)
    findings_without_evidence: int = Field(ge=0)
    high_risk_evidence_highlights: list[str] = Field(default_factory=list)
    source_summary: dict[str, int] = Field(default_factory=dict)
    evidence_chain_status: str
    scope_relation: str
    report_appendix_readiness: str


class CasePackageManifestResponse(BaseModel):
    package_id: uuid.UUID
    investigation_id: uuid.UUID
    engagement_id: uuid.UUID | None = None
    included_deliverables: list[CaseDeliverableResponse]
    missing_deliverables: list[CaseDeliverableType]
    warnings: list[str]
    readiness_status: PackageReadinessStatus
    evidence_package: EvidencePackageSummary
    generated_at: datetime
    generated_by: uuid.UUID | None


class CaseClosureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    status: CaseClosureStatus
    closure_summary: str | None
    final_risk_rating: CaseFinalRiskRating
    reviewed_by: uuid.UUID | None
    approved_by: uuid.UUID | None
    closed_by: uuid.UUID | None
    reviewed_at: datetime | None
    approved_at: datetime | None
    closed_at: datetime | None
    checklist: list[CaseClosureChecklistItemResponse]
    deliverables: list[CaseDeliverableResponse]
    evidence_package: EvidencePackageSummary
    warnings: list[str]
    blockers: list[str]
    created_at: datetime
    updated_at: datetime
