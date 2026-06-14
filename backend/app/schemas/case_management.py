from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, cast

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

InvestigationWorkflowStatus = Literal[
    "draft",
    "active",
    "triage",
    "monitoring",
    "remediation",
    "validated",
    "archived",
    "review",
    "remediated",
]
NoteType = Literal[
    "analyst_note",
    "evidence_note",
    "remediation_note",
    "executive_note",
    "timeline_note",
]
LegacyNoteType = Literal[
    "analyst",
    "evidence",
    "recommendation",
    "executive",
    "remediation",
    "timeline",
]
NoteTypeInput = NoteType | LegacyNoteType
TaskStatus = Literal["open", "in_progress", "blocked", "completed", "cancelled", "todo"]
TaskPriority = Literal["critical", "high", "medium", "low", "urgent"]
EvidenceReviewStatus = Literal["collected", "reviewed", "validated", "dismissed"]
EvidenceType = Literal[
    "recon",
    "dns",
    "infrastructure",
    "screenshot",
    "report",
    "correlation",
    "finding",
    "threat_intel",
    "analyst_note",
]


class WorkflowTransitionRequest(BaseModel):
    status: InvestigationWorkflowStatus
    reason: str | None = Field(default=None, max_length=2000)


class WorkflowEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    actor_id: uuid.UUID | None
    from_status: str | None
    to_status: str
    reason: str | None
    created_at: datetime


class InvestigationNoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(
        min_length=1,
        validation_alias=AliasChoices("content", "note"),
    )
    note_type: NoteTypeInput = "analyst_note"
    pinned: bool = False

    @field_validator("title", "content")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("value cannot be blank")
        return clean


class InvestigationNoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(
        default=None,
        min_length=1,
        validation_alias=AliasChoices("content", "note"),
    )
    note_type: NoteTypeInput | None = None
    pinned: bool | None = None
    archived: bool | None = None

    @field_validator("title", "content")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        if not clean:
            raise ValueError("value cannot be blank")
        return clean


class InvestigationNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    author_id: uuid.UUID | None
    title: str
    content: str
    note: str
    note_type: NoteTypeInput
    pinned: bool
    archived: bool
    created_at: datetime
    updated_at: datetime


class InvestigationNoteListResponse(BaseModel):
    total: int
    items: list[InvestigationNoteResponse]


class InvestigationTaskCreate(BaseModel):
    investigation_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: TaskStatus = "open"
    priority: TaskPriority = "medium"
    assigned_to: uuid.UUID | None = None
    due_date: datetime | None = None
    remediation_link: str | None = Field(default=None, max_length=2000)
    finding_id: uuid.UUID | None = None
    evidence_reference_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("title cannot be blank")
        return clean


class InvestigationTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assigned_to: uuid.UUID | None = None
    due_date: datetime | None = None
    remediation_link: str | None = Field(default=None, max_length=2000)
    finding_id: uuid.UUID | None = None
    evidence_reference_ids: list[uuid.UUID] | None = None

    @field_validator("title")
    @classmethod
    def strip_optional_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        if not clean:
            raise ValueError("title cannot be blank")
        return clean


class InvestigationTaskStatusUpdate(BaseModel):
    status: TaskStatus


class InvestigationTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    assigned_to: uuid.UUID | None
    due_date: datetime | None
    remediation_link: str | None
    finding_id: uuid.UUID | None
    evidence_reference_ids: list[uuid.UUID]
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class InvestigationTaskListResponse(BaseModel):
    total: int
    items: list[InvestigationTaskResponse]


class InvestigationEvidenceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    evidence_type: EvidenceType
    source: str = Field(min_length=1, max_length=100)
    confidence: int = Field(default=50, ge=0, le=100)
    tags: list[str] = Field(default_factory=list)
    analyst_comment: str | None = None
    finding_id: uuid.UUID | None = None
    note_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None

    @field_validator("title", "source")
    @classmethod
    def strip_evidence_text(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("value cannot be blank")
        return clean

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class InvestigationEvidenceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    evidence_type: EvidenceType | None = None
    source: str | None = Field(default=None, min_length=1, max_length=100)
    confidence: int | None = Field(default=None, ge=0, le=100)
    tags: list[str] | None = None
    analyst_comment: str | None = None
    finding_id: uuid.UUID | None = None
    note_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None

    @field_validator("title", "source")
    @classmethod
    def strip_optional_evidence_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        if not clean:
            raise ValueError("value cannot be blank")
        return clean

    @field_validator("tags")
    @classmethod
    def clean_optional_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return sorted({item.strip() for item in value if item.strip()})


class InvestigationEvidenceReviewUpdate(BaseModel):
    review_status: EvidenceReviewStatus
    analyst_note: str | None = None
    confidence_score: int | None = Field(default=None, ge=0, le=100)


class InvestigationEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    finding_id: uuid.UUID | None
    note_id: uuid.UUID | None
    task_id: uuid.UUID | None
    title: str
    description: str | None
    evidence_type: EvidenceType
    source: str
    confidence: int = Field(ge=0, le=100)
    tags: list[str]
    analyst_comment: str | None
    review_status: EvidenceReviewStatus
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    analyst_note: str | None
    confidence_score: int = Field(ge=0, le=100)
    archived_at: datetime | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class InvestigationEvidenceListResponse(BaseModel):
    total: int
    items: list[InvestigationEvidenceResponse]


_NOTE_TYPE_ALIASES = {
    "analyst": "analyst_note",
    "evidence": "evidence_note",
    "recommendation": "analyst_note",
    "executive": "executive_note",
    "remediation": "remediation_note",
    "timeline": "timeline_note",
}


def normalize_note_type(value: NoteTypeInput) -> NoteType:
    return cast(NoteType, _NOTE_TYPE_ALIASES.get(value, value))
