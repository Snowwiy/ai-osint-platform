from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ExecutionMode = Literal["free_only", "local_only", "any_configured"]
KnowledgeContextPolicy = Literal["verified_only", "trusted_plus", "all_allowed"]
PromptHandoffKind = Literal["recommendation", "asset", "investigation"]


class AiRuntimeStatus(BaseModel):
    available: bool
    status: Literal["available", "server_stopped", "not_installed", "unsupported"]
    version: str | None = None
    integration: str = "OpenCode local server"
    loopback_only: bool = True
    message: str


class AiOperationsStatus(BaseModel):
    dependency: Literal["optional"] = "optional"
    runtime_status: str
    runtime_available: bool
    available_models: int = Field(ge=0)
    local_providers: int = Field(ge=0)
    remote_providers: int = Field(ge=0)
    selected_model_id: str | None = None
    last_model_refresh: datetime | None = None
    last_successful_inference: datetime | None = None
    degraded: bool
    message: str


class AiProvider(BaseModel):
    id: str
    name: str
    category: str
    connected: bool
    local: bool
    remote: bool
    status: str


class AiModel(BaseModel):
    id: str
    provider_id: str
    model_id: str
    display_name: str
    available: bool
    local: bool
    remote: bool
    free_status: Literal["provider_reported_free", "paid", "unknown", "local"]
    context_window: int | None = None
    supports_tools: bool | None = None
    supports_vision: bool | None = None
    supports_reasoning: bool | None = None
    supports_streaming: bool | None = None
    metadata_source: str
    last_discovered_at: datetime


class AiCatalogResponse(BaseModel):
    runtime: AiRuntimeStatus
    providers: list[AiProvider]
    models: list[AiModel]
    refreshed_at: datetime
    warning: str | None = None
    recommended_model_id: str | None = None


class AiPreferences(BaseModel):
    selected_model_id: str | None = None
    preferred_local_model_id: str | None = None
    preferred_free_model_id: str | None = None
    execution_mode: ExecutionMode = "free_only"


class AiPreferencesUpdate(AiPreferences):
    pass


class AiSessionCreate(BaseModel):
    model_id: str = Field(min_length=3, max_length=300)
    title: str = Field(default="New AI chat", min_length=1, max_length=120)
    context_policy: KnowledgeContextPolicy = "verified_only"

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        return value.strip()


class AiSessionRename(BaseModel):
    title: str = Field(min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def trim_title(cls, value: str) -> str:
        return value.strip()


class AiMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=12_000)
    knowledge_citation_ids: list[str] = Field(default_factory=list, max_length=5)
    context_policy: KnowledgeContextPolicy = "verified_only"

    @field_validator("content")
    @classmethod
    def trim_content(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Message cannot be blank.")
        return clean


class AiContextPreviewRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    policy: KnowledgeContextPolicy = "verified_only"


class AiContextExcerpt(BaseModel):
    citation_id: str
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    title: str
    source: str
    trust_level: str
    verification_status: str
    excerpt: str


class AiContextPreviewResponse(BaseModel):
    policy: KnowledgeContextPolicy
    items: list[AiContextExcerpt]
    total_included: int
    message: str


class AiCitationValidation(BaseModel):
    supplied: list[str]
    matched_response_references: list[str]
    unverified_response_references: list[str]


class AiMessageView(BaseModel):
    id: uuid.UUID
    sequence: int
    role: Literal["user", "assistant"]
    content: str
    status: str
    provider_id: str | None = None
    model_id: str | None = None
    execution_type: str | None = None
    context_sources: list[dict[str, Any]] = Field(default_factory=list)
    supplied_citations: list[str] = Field(default_factory=list)
    citation_validation: AiCitationValidation | None = None
    created_at: datetime


class AiSessionView(BaseModel):
    id: uuid.UUID
    title: str
    provider_id: str
    model_id: str
    execution_type: Literal["local", "remote"]
    context_policy: KnowledgeContextPolicy
    status: Literal["ready", "running", "failed", "cancelled"]
    archived: bool
    created_at: datetime
    updated_at: datetime
    messages: list[AiMessageView] = Field(default_factory=list)


class AiMessageResult(BaseModel):
    session_id: uuid.UUID
    user_message: AiMessageView
    assistant_message: AiMessageView
    sources: list[AiContextExcerpt]


class AiModelTestRequest(BaseModel):
    model_id: str = Field(min_length=3, max_length=300)


class AiModelTestResponse(BaseModel):
    available: bool
    latency_ms: int | None = None
    model_id: str
    response: str | None = None
    error: str | None = None


class AiPromptHandoffRequest(BaseModel):
    kind: PromptHandoffKind
    title: str = Field(min_length=1, max_length=200)
    facts: dict[str, str] = Field(default_factory=dict, max_length=16)
    citations: list[str] = Field(default_factory=list, max_length=20)
    model_id: str | None = Field(default=None, max_length=300)


class AiPromptHandoffResponse(BaseModel):
    prompt: str
    command: str | None = None
    citations: list[str]
    content_hash: str


class AiPromptCopyAuditRequest(BaseModel):
    content_hash: str = Field(min_length=64, max_length=64)
    content_type: Literal["prompt", "command"] = "prompt"
