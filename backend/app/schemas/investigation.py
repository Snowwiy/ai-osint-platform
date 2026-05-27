from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


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
