from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.case_management import InvestigationWorkflowStatus
from app.schemas.finding import FindingSeverity, FindingStatus
from app.schemas.recon import (
    EntityType,
    JsonProperties,
    ReconStatus,
    RelationshipType,
    TargetType,
)

InvestigationMemberRole = Literal["owner", "admin", "analyst", "viewer"]
InvestigationMemberAddRole = Literal["owner", "admin", "collaborator", "viewer"]
InvestigationMemberResponseRole = InvestigationMemberRole | Literal["collaborator"]
InvestigationPriority = Literal["low", "medium", "high", "urgent"]
InvestigationScopeReviewStatus = Literal[
    "not_reviewed",
    "in_scope",
    "out_of_scope",
    "pending_review",
]
InvestigationStage = Literal[
    "intake",
    "scoping",
    "recon",
    "analysis",
    "remediation",
    "validation",
    "reporting",
    "completed",
    "archived",
]
InvestigationListScope = Literal[
    "all",
    "owned_by_me",
    "assigned_to_me",
    "member_of",
    "viewer_only",
    "active",
    "archived",
    "needs_review",
]


class InvestigationCreate(BaseModel):
    title: str
    description: str | None = None
    authorization_statement: str
    scope_definition: str | None = None
    engagement_id: uuid.UUID | None = None
    scope_review_status: InvestigationScopeReviewStatus = "not_reviewed"
    scope_notes: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("title cannot be blank")
        return clean

    @field_validator("authorization_statement")
    @classmethod
    def validate_authorization_statement(cls, value: str) -> str:
        if len(value.strip()) < 100:
            raise ValueError("authorization_statement must be at least 100 characters")
        return value


class InvestigationUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: InvestigationWorkflowStatus | None = None
    scope_definition: str | None = None
    reviewer_id: uuid.UUID | None = None
    engagement_id: uuid.UUID | None = None
    scope_review_status: InvestigationScopeReviewStatus | None = None
    scope_notes: str | None = None


class InvestigationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    status: InvestigationWorkflowStatus
    stage: InvestigationStage
    owner_id: uuid.UUID
    reviewer_id: uuid.UUID | None
    engagement_id: uuid.UUID | None
    authorization_statement: str
    scope_definition: str | None
    scope_review_status: InvestigationScopeReviewStatus
    scope_notes: str | None
    priority: InvestigationPriority
    business_impact: str | None
    due_date: date | None
    created_at: datetime
    updated_at: datetime


class InvestigationListResponse(BaseModel):
    total: int
    items: list[InvestigationResponse]


class InvestigationPurgeImpactResponse(BaseModel):
    investigation_id: uuid.UUID
    title: str
    status: InvestigationWorkflowStatus
    permanent_deletion_enabled: bool
    findings_count: int = Field(ge=0)
    notes_count: int = Field(ge=0)
    reports_count: int = Field(ge=0)
    tasks_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    members_count: int = Field(ge=0)


class MemberAddRequest(BaseModel):
    user_id: uuid.UUID | None = None
    email: str | None = None
    username: str | None = None
    role: InvestigationMemberAddRole = "collaborator"

    @field_validator("email", "username")
    @classmethod
    def strip_optional_lookup(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None

    @model_validator(mode="after")
    def has_lookup(self) -> "MemberAddRequest":
        if self.user_id is None and self.email is None and self.username is None:
            raise ValueError("user_id, email, or username is required")
        return self


class MemberUpdateRequest(BaseModel):
    role: InvestigationMemberRole | None = None
    transfer_ownership: bool = False

    @field_validator("role")
    @classmethod
    def role_required_for_non_transfer(cls, value: str | None) -> str | None:
        return value


class MemberResponse(BaseModel):
    id: uuid.UUID
    investigation_id: uuid.UUID
    user_id: uuid.UUID
    username: str
    email: str
    role: InvestigationMemberResponseRole
    invited_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime | None = None


class InvestigationStageUpdate(BaseModel):
    stage: InvestigationStage
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return value.strip()


class ReadinessComponent(BaseModel):
    key: str
    label: str
    points: int = Field(ge=0)
    max_points: int = Field(ge=0)
    complete: bool
    detail: str


class InvestigationReadinessResponse(BaseModel):
    investigation_id: uuid.UUID
    score: int = Field(ge=0, le=100)
    category: Literal[
        "Not Started",
        "Scoping",
        "Evidence Collection",
        "Analysis Ready",
        "Reporting Ready",
    ]
    stage: InvestigationStage
    components: list[ReadinessComponent]
    guidance: list[str]
    generated_at: datetime


class InvestigationGraphNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_type: EntityType
    value: str
    display_name: str | None
    properties: JsonProperties
    source: str | None
    first_seen: datetime
    last_seen: datetime


class InvestigationGraphEdge(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_entity_id: uuid.UUID
    target_entity_id: uuid.UUID
    relationship_type: RelationshipType
    properties: JsonProperties
    source: str | None
    created_at: datetime


class InvestigationGraphRiskSummary(BaseModel):
    total_entities: int
    entity_counts: dict[EntityType, int]
    risk_level: Literal["not_assessed"] = "not_assessed"
    signals: list[str]


class InvestigationGraphTimelineEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_type: TargetType
    target_value: str
    status: ReconStatus
    summary: JsonProperties
    created_at: datetime


class InvestigationGraphFinding(BaseModel):
    id: uuid.UUID
    title: str
    severity: FindingSeverity
    status: FindingStatus
    risk_score: int
    source: str
    linked_entity_ids: list[uuid.UUID]
    threat_finding_ids: list[uuid.UUID]


class InvestigationGraphFindingEdge(BaseModel):
    finding_id: uuid.UUID
    entity_id: uuid.UUID | None = None
    threat_finding_id: uuid.UUID | None = None
    relationship_type: Literal["EVIDENCED_BY"] = "EVIDENCED_BY"


class InvestigationGraphResponse(BaseModel):
    investigation_id: uuid.UUID
    nodes: list[InvestigationGraphNode]
    edges: list[InvestigationGraphEdge]
    risk_summary: InvestigationGraphRiskSummary
    timeline: list[InvestigationGraphTimelineEvent]
    findings: list[InvestigationGraphFinding] = Field(default_factory=list)
    finding_edges: list[InvestigationGraphFindingEdge] = Field(default_factory=list)
