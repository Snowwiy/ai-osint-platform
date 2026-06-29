from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

GlobalSearchType = Literal[
    "investigation",
    "engagement",
    "finding",
    "report",
    "deliverable",
    "notification",
    "scope_item",
    "user",
    "closure",
    "ioc",
    "threat_object",
    "evidence_summary",
]
SavedViewType = Literal[
    "investigation_list",
    "findings",
    "reports",
    "notifications",
    "engagements",
    "closure",
    "search",
    "dashboard",
]


class GlobalSearchResult(BaseModel):
    id: str
    type: GlobalSearchType
    title: str
    subtitle: str | None = None
    snippet: str | None = None
    status: str | None = None
    severity: str | None = None
    route: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    matched_fields: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: int = 0


class GlobalSearchResponse(BaseModel):
    query: str
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    items: list[GlobalSearchResult]
    result_types: list[str] = Field(default_factory=list)


class SavedViewBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    view_type: SavedViewType
    route: str = Field(min_length=1, max_length=500)
    filters: dict[str, Any] = Field(default_factory=dict)
    sort: dict[str, Any] | None = None
    is_default: bool = False
    is_pinned: bool = False

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return " ".join(value.strip().split())

    @field_validator("route")
    @classmethod
    def validate_route(cls, value: str) -> str:
        clean = value.strip()
        if not clean.startswith("/") or clean.startswith("//"):
            raise ValueError("route must be an internal application path")
        return clean

    @field_validator("filters", "sort")
    @classmethod
    def validate_json_safe(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _safe_json(value)


class SavedViewCreate(SavedViewBase):
    pass


class SavedViewUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    view_type: SavedViewType | None = None
    route: str | None = Field(default=None, min_length=1, max_length=500)
    filters: dict[str, Any] | None = None
    sort: dict[str, Any] | None = None
    is_default: bool | None = None
    is_pinned: bool | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.strip().split())

    @field_validator("route")
    @classmethod
    def validate_route(cls, value: str | None) -> str | None:
        if value is None:
            return None
        clean = value.strip()
        if not clean.startswith("/") or clean.startswith("//"):
            raise ValueError("route must be an internal application path")
        return clean

    @field_validator("filters", "sort")
    @classmethod
    def validate_json_safe(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _safe_json(value)


class SavedViewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    view_type: SavedViewType
    route: str
    filters: dict[str, Any]
    sort: dict[str, Any] | None
    is_default: bool
    is_pinned: bool
    created_at: datetime
    updated_at: datetime


class SavedViewListResponse(BaseModel):
    total: int = Field(ge=0)
    items: list[SavedViewResponse]


def _safe_json(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    blocked = {
        "password",
        "token",
        "api_key",
        "secret",
        "authorization",
        "database_url",
        "invite_code",
    }
    clean: dict[str, Any] = {}
    for key, item in value.items():
        key_text = str(key)
        if key_text.lower() in blocked:
            continue
        if isinstance(item, (str, int, float, bool)) or item is None:
            clean[key_text] = item
        elif isinstance(item, list):
            clean[key_text] = [
                entry
                for entry in item[:50]
                if isinstance(entry, (str, int, float, bool)) or entry is None
            ]
        elif isinstance(item, dict):
            clean[key_text] = {
                str(child_key): child_value
                for child_key, child_value in list(item.items())[:50]
                if isinstance(child_value, (str, int, float, bool))
                or child_value is None
            }
    return clean
