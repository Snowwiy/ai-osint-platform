from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.finding import FindingSeverity, FindingStatus
from app.schemas.recon import (
    EntityType,
    JsonProperties,
    ReconStatus,
    RelationshipType,
    TargetType,
)


class InvestigationCreate(BaseModel):
    title: str
    description: str | None = None
    authorization_statement: str
    scope_definition: str | None = None

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
    status: str | None = None
    scope_definition: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        allowed = ("draft", "active", "completed", "archived")
        if value is not None and value not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return value


class InvestigationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    status: str
    owner_id: uuid.UUID
    authorization_statement: str
    scope_definition: str | None
    created_at: datetime
    updated_at: datetime


class InvestigationListResponse(BaseModel):
    total: int
    items: list[InvestigationResponse]


class MemberAddRequest(BaseModel):
    user_id: uuid.UUID
    role: str = "collaborator"

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, value: str) -> str:
        if value not in ("owner", "collaborator"):
            raise ValueError("role must be 'owner' or 'collaborator'")
        return value


class MemberUpdateRequest(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, value: str) -> str:
        if value not in ("owner", "collaborator"):
            raise ValueError("role must be 'owner' or 'collaborator'")
        return value


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    investigation_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    added_at: datetime


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
