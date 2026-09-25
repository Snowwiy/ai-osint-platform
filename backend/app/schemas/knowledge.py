from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

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
    source_id: uuid.UUID | None = None
    relative_name: str | None = None
    category: str = "Other"
    content_type: str = "text/markdown"
    language: str | None = None
    trust_level: str = "unknown"
    verification_status: str = "unverified"
    document_status: str = "ready"
    size_bytes: int = 0
    indexed_at: datetime | None = None
    knowledge_metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeDocumentListResponse(BaseModel):
    total: int
    items: list[KnowledgeDocumentResponse]


class KnowledgeSourceResponse(BaseModel):
    id: uuid.UUID
    name: str
    source_type: str
    display_location: str
    category: str
    platform: str | None
    availability: str
    status: str
    trust_level: str
    verification_status: str
    language: str | None
    publisher: str | None
    canonical_url: str | None
    publication_date: str | None
    version_label: str | None
    notes: str | None
    content_hash: str | None = None
    last_indexed_at: datetime | None
    last_seen_at: datetime | None
    document_count: int
    chunk_count: int
    error_summary: str | None
    scan_counts: dict[str, int] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class KnowledgeSourceListResponse(BaseModel):
    total: int
    items: list[KnowledgeSourceResponse]


class KnowledgeSourcePatch(BaseModel):
    category: str | None = Field(default=None, max_length=80)
    trust_level: (
        Literal["authoritative", "trusted", "internal", "community", "unknown"] | None
    ) = None
    verification_status: (
        Literal["verified", "reviewed", "unverified", "stale", "rejected"] | None
    ) = None
    notes: str | None = Field(default=None, max_length=2000)
    publisher: str | None = Field(default=None, max_length=200)
    canonical_url: str | None = Field(default=None, max_length=1000)
    publication_date: str | None = Field(default=None, max_length=40)
    version_label: str | None = Field(default=None, max_length=120)
    language: str | None = Field(default=None, max_length=16)
    status: Literal["enabled", "disabled"] | None = None


class KnowledgeStatsResponse(BaseModel):
    sources: int
    documents: int
    chunks: int
    verified_sources: int
    unverified_sources: int
    failed_documents: int
    offline_sources: int
    active_jobs: int
    last_sync_at: datetime | None = None


class KnowledgeSearchResult(BaseModel):
    document_id: uuid.UUID
    title: str
    source_type: KnowledgeSourceType
    file_path: str
    citation_id: str = ""
    source_id: uuid.UUID | None = None
    source_name: str | None = None
    relative_name: str | None = None
    section: str | None = None
    page_number: int | None = None
    modified_at: datetime | None = None
    indexed_at: datetime | None = None
    language: str | None = None
    trust_level: str = "unknown"
    verification_status: str = "unverified"
    sensitive_content_warning: bool = False
    duplicate_of_document_id: uuid.UUID | None = None
    chunk: str
    score: float
    tags: list[str]
    category: str = "Defensive Guidance"
    framework: KnowledgeFramework | None = None
    severity_relevance: Literal["informational", "low", "medium", "high"] = (
        "informational"
    )
    defensive_explanation: str = ""
    references: list[str] = Field(default_factory=list)
    related_findings: list[str] = Field(default_factory=list)
    mitre_relevance: str | None = None
    sigma_relevance: str | None = None
    remediation_guidance: list[str] = Field(default_factory=list)
    why_this_matters: str = ""


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
    framework: str
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
