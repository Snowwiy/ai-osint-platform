from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

_VALID_TARGET_TYPES = ("domain", "ip", "email", "username", "org", "url")


class TargetCreate(BaseModel):
    investigation_id: uuid.UUID
    target_type: str
    target_value: str
    label: str | None = None
    notes: str | None = None

    @field_validator("target_type")
    @classmethod
    def validate_target_type(cls, value: str) -> str:
        if value not in _VALID_TARGET_TYPES:
            raise ValueError(f"target_type must be one of {_VALID_TARGET_TYPES}")
        return value

    @field_validator("target_value")
    @classmethod
    def validate_target_value_not_empty(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("target_value cannot be blank")
        return clean


class TargetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    target_type: str
    target_value: str
    label: str | None
    notes: str | None
    created_by: uuid.UUID | None
    created_at: datetime


class TargetListResponse(BaseModel):
    total: int
    items: list[TargetResponse]
