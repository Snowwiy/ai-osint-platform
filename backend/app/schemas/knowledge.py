from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

KnowledgeSourceType = Literal[
    "security_notes",
    "frameworks",
    "playbooks",
    "osint_notes",
]
KnowledgeSearchMode = Literal["keyword", "semantic", "hybrid"]


class KnowledgeIndexRequest(BaseModel):
    source_type: KnowledgeSourceType = "security_notes"
    paths: list[str] = Field(default_factory=list)

    @field_validator("paths")
    @classmethod
    def strip_paths(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class KnowledgeIndexResponse(BaseModel):
    documents_seen: int
    documents_indexed: int
    documents_skipped: int
    chunks_indexed: int


class KnowledgeDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_type: KnowledgeSourceType
    file_path: str
    title: str
    hash: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentListResponse(BaseModel):
    total: int
    items: list[KnowledgeDocumentResponse]


class KnowledgeSearchResult(BaseModel):
    document_id: uuid.UUID
    title: str
    source_type: KnowledgeSourceType
    file_path: str
    chunk: str
    score: float
    tags: list[str]


class KnowledgeSearchResponse(BaseModel):
    query: str
    mode: KnowledgeSearchMode
    total: int
    items: list[KnowledgeSearchResult]
