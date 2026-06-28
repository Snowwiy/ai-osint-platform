from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EngagementStatus = Literal["draft", "active", "completed", "archived"]
AuthorizationStatus = Literal[
    "not_provided",
    "pending_review",
    "approved",
    "expired",
    "revoked",
]
ScopeType = Literal[
    "domain",
    "subdomain",
    "ip",
    "cidr",
    "email",
    "username",
    "organization",
    "other",
]
ScopeStatus = Literal["in_scope", "out_of_scope", "pending_review"]
ScopeReviewStatus = Literal[
    "not_reviewed",
    "in_scope",
    "out_of_scope",
    "pending_review",
]
AuthorizationEvidenceType = Literal[
    "contract",
    "email_approval",
    "statement_of_work",
    "internal_authorization",
    "other",
]


class EngagementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    client_name: str = Field(min_length=1, max_length=255)
    client_contact: str | None = Field(default=None, max_length=255)
    description: str | None = None
    status: EngagementStatus = "draft"
    authorization_status: AuthorizationStatus = "not_provided"
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("title", "client_name", "client_contact", "description")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None

    @model_validator(mode="after")
    def date_order(self) -> "EngagementCreate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class EngagementUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    client_name: str | None = Field(default=None, min_length=1, max_length=255)
    client_contact: str | None = Field(default=None, max_length=255)
    description: str | None = None
    status: EngagementStatus | None = None
    authorization_status: AuthorizationStatus | None = None
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("title", "client_name", "client_contact", "description")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None


class EngagementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    client_name: str
    client_contact: str | None
    description: str | None
    status: EngagementStatus
    authorization_status: AuthorizationStatus
    start_date: date | None
    end_date: date | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    linked_investigations_count: int = 0
    scope_counts: dict[ScopeStatus, int] = Field(default_factory=dict)


class EngagementListResponse(BaseModel):
    total: int = Field(ge=0)
    items: list[EngagementResponse]


class ScopeItemCreate(BaseModel):
    scope_type: ScopeType
    value: str = Field(min_length=1, max_length=500)
    description: str | None = None
    status: ScopeStatus = "pending_review"

    @field_validator("value", "description")
    @classmethod
    def strip_scope_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None


class ScopeItemUpdate(BaseModel):
    scope_type: ScopeType | None = None
    value: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: ScopeStatus | None = None

    @field_validator("value", "description")
    @classmethod
    def strip_optional_scope_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None


class ScopeItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    engagement_id: uuid.UUID
    scope_type: ScopeType
    value: str
    description: str | None
    status: ScopeStatus
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class AuthorizationEvidenceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    evidence_type: AuthorizationEvidenceType
    reference: str | None = Field(default=None, max_length=500)
    status: AuthorizationStatus = "pending_review"

    @field_validator("title", "description", "reference")
    @classmethod
    def strip_evidence_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None


class AuthorizationEvidenceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    evidence_type: AuthorizationEvidenceType | None = None
    reference: str | None = Field(default=None, max_length=500)
    status: AuthorizationStatus | None = None

    @field_validator("title", "description", "reference")
    @classmethod
    def strip_optional_evidence_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        return clean or None


class AuthorizationEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    engagement_id: uuid.UUID
    title: str
    description: str | None
    evidence_type: AuthorizationEvidenceType
    reference: str | None
    status: AuthorizationStatus
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ScopeCheckRequest(BaseModel):
    value: str = Field(min_length=1, max_length=500)
    scope_type: ScopeType | None = None

    @field_validator("value")
    @classmethod
    def strip_value(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("value cannot be blank")
        return clean


class ScopeCheckResponse(BaseModel):
    status: ScopeStatus
    matched_scope_item: ScopeItemResponse | None = None
    warning: str
    recommended_action: str
