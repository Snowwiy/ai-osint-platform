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
KnowledgeFramework = Literal[
    "MITRE ATT&CK",
    "NIST CSF",
    "NIST 800-53",
    "CIS Controls",
    "OWASP Top 10",
    "Sigma",
    "YARA",
    "DFIR",
    "Threat Intelligence",
    "Secure Architecture",
    "Cloud Security",
]


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


class KnowledgeDocument(BaseModel):
    title: str
    source: str
    framework: KnowledgeFramework
    category: str
    content: str
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    created_at: datetime


class KnowledgeChunk(BaseModel):
    id: str
    document_id: str
    title: str
    source: str
    framework: KnowledgeFramework
    category: str
    content: str
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    created_at: datetime


class KnowledgeCitation(BaseModel):
    id: str
    document_id: str
    chunk_id: str
    title: str
    source: str
    framework: KnowledgeFramework
    category: str
    confidence: float = Field(ge=0, le=1)


class KnowledgeRetrievalRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    frameworks: list[KnowledgeFramework] | None = None
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("query cannot be blank")
        return clean


class KnowledgeRetrievalResponse(BaseModel):
    query: str
    matched_chunks: list[KnowledgeChunk]
    citation_ids: list[str]
    citations: list[KnowledgeCitation]
    frameworks: list[KnowledgeFramework]
    confidence: float = Field(ge=0, le=1)
