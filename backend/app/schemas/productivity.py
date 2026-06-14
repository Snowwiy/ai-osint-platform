from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.investigation import InvestigationPriority

BookmarkType = Literal["entity", "finding", "report"]


class EvidenceBookmarkCreate(BaseModel):
    entity_id: uuid.UUID | None = None
    finding_id: uuid.UUID | None = None
    report_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    note: str | None = Field(default=None, max_length=5000)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("title cannot be blank")
        return clean

    @model_validator(mode="after")
    def has_one_reference(self) -> "EvidenceBookmarkCreate":
        references = (self.entity_id, self.finding_id, self.report_id)
        if sum(item is not None for item in references) != 1:
            raise ValueError("exactly one evidence reference is required")
        return self


class EvidenceBookmarkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    entity_id: uuid.UUID | None
    finding_id: uuid.UUID | None
    report_id: uuid.UUID | None
    bookmark_type: BookmarkType
    title: str
    note: str | None
    created_by: uuid.UUID | None
    created_at: datetime


class EvidenceBookmarkListResponse(BaseModel):
    total: int
    items: list[EvidenceBookmarkResponse]


class InvestigationTagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    color: str = Field(default="slate", min_length=1, max_length=20)

    @field_validator("name", "color")
    @classmethod
    def clean_text(cls, value: str) -> str:
        clean = value.strip().lower()
        if not clean:
            raise ValueError("value cannot be blank")
        return clean


class InvestigationTagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    color: str
    created_at: datetime


class InvestigationTagListResponse(BaseModel):
    total: int
    items: list[InvestigationTagResponse]


class InvestigationTagsUpdate(BaseModel):
    tag_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)

    @field_validator("tag_ids")
    @classmethod
    def unique_tags(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        return list(dict.fromkeys(value))


class InvestigationPriorityUpdate(BaseModel):
    priority: InvestigationPriority
    business_impact: str | None = Field(default=None, max_length=5000)
    due_date: date | None = None

    @field_validator("business_impact")
    @classmethod
    def clean_business_impact(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None


class InvestigationPriorityResponse(BaseModel):
    investigation_id: uuid.UUID
    priority: InvestigationPriority
    business_impact: str | None
    owner_id: uuid.UUID
    due_date: date | None
    overdue: bool


class SummaryFinding(BaseModel):
    id: uuid.UUID
    title: str
    severity: str
    status: str
    risk_score: int


class RemediationProgress(BaseModel):
    total_findings: int
    remediated: int
    accepted_risk: int
    unresolved: int
    completion_percent: int


class InvestigationSummaryResponse(BaseModel):
    investigation_id: uuid.UUID
    scope: str
    observed_defensive_concerns: list[str]
    highest_priority_findings: list[SummaryFinding]
    remediation_progress: RemediationProgress
    next_recommended_analyst_actions: list[str]
    evidence_references: list[str]
