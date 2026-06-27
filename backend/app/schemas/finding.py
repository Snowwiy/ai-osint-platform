from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.case_review import RemediationValidationStatus
from app.schemas.recon import JsonProperties

FindingSeverity = Literal["info", "low", "medium", "high", "critical"]
FindingStatus = Literal[
    "new",
    "under_review",
    "validated",
    "accepted_risk",
    "mitigated",
    "false_positive",
    "archived",
    "open",
    "resolved",
]
RiskBand = Literal["Low", "Medium", "High", "Critical"]


class FindingEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    finding_id: uuid.UUID
    recon_entity_id: uuid.UUID | None
    threat_finding_id: uuid.UUID | None
    evidence_type: str
    source: str
    description: str
    data: JsonProperties
    created_at: datetime


class FindingEvidenceChainItem(BaseModel):
    id: uuid.UUID
    source: str
    evidence_type: str
    description: str
    recon_entity_id: uuid.UUID | None = None
    threat_finding_id: uuid.UUID | None = None
    created_at: datetime


class FindingFrameworkMapping(BaseModel):
    framework: str
    control: str
    rationale: str
    citation_ids: list[str] = Field(default_factory=list)
    confidence: int | None = Field(default=None, ge=0, le=100)


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    title: str
    description: str
    severity: FindingSeverity
    confidence_score: int = Field(ge=0, le=100)
    risk_score: int = Field(ge=0, le=100)
    source: str
    status: FindingStatus
    assigned_to: uuid.UUID | None = None
    reviewed_by: uuid.UUID | None = None
    review_notes: str | None = None
    remediation_notes: str | None = None
    remediation_status: str
    remediation_owner: uuid.UUID | None = None
    remediation_due_date: date | None = None
    verification_notes: str | None = None
    verified_by: uuid.UUID | None = None
    verified_at: datetime | None = None
    validation_notes: str | None = None
    validation_status: RemediationValidationStatus = "not_validated"
    validation_owner: uuid.UUID | None = None
    validation_failure_reason: str | None = None
    confidence_reasoning: str | None = None
    evidence_summary: str | None = None
    review_history: list[dict[str, object]] = Field(default_factory=list)
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    evidence: list[FindingEvidenceResponse] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    summary: str
    evidence_chain: list[FindingEvidenceChainItem] = Field(default_factory=list)
    affected_targets: list[str] = Field(default_factory=list)
    framework_mappings: list[FindingFrameworkMapping] = Field(default_factory=list)
    remediation_guidance: list[str] = Field(default_factory=list)
    analyst_notes: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class FindingListResponse(BaseModel):
    items: list[FindingResponse]


class FindingSummaryResponse(BaseModel):
    investigation_id: uuid.UUID
    total: int
    by_severity: dict[FindingSeverity, int]
    by_status: dict[FindingStatus, int]
    by_source: dict[str, int]
    risk_score_v2: int = Field(ge=0, le=100)
    risk_level_v2: RiskBand
    risk_signals: list[str]


class FindingStatusUpdate(BaseModel):
    status: FindingStatus
    review_notes: str | None = Field(default=None, max_length=4000)
    remediation_notes: str | None = Field(default=None, max_length=4000)
    validation_notes: str | None = Field(default=None, max_length=4000)


class FindingAssignRequest(BaseModel):
    assigned_to: uuid.UUID | None = None
    reviewed_by: uuid.UUID | None = None
