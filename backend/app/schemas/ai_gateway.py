from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ExecutionMode = Literal["local_first", "free_only", "local_only", "any_configured"]
RoutingMode = Literal["manual", "recommended", "automatic_local"]
TaskProfile = Literal[
    "fast_triage",
    "general_analyst",
    "deep_analysis",
    "knowledge_rag",
    "tool_calling",
    "structured_reports",
    "bilingual",
    "offline",
]
KnowledgeContextPolicy = Literal["verified_only", "trusted_plus", "all_allowed"]
PromptHandoffKind = Literal["recommendation", "asset", "investigation"]
RuntimeState = Literal[
    "available",
    "unavailable",
    "starting",
    "degraded",
    "incompatible",
    "authentication_required",
    "no_models",
    "unknown",
]
CapabilityState = Literal["supported", "unsupported", "unknown"]
ModelFitState = Literal[
    "excellent_fit",
    "good_fit",
    "marginal",
    "cpu_fallback",
    "insufficient_memory",
    "unknown",
]


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
    tool_gateway_status: Literal["healthy", "degraded"] = "healthy"
    registered_tools: int = 0
    read_only_tool_count: int = 0
    write_tool_count: Literal[0] = 0
    action_proposal_tool_count: int = Field(default=0, ge=0, le=1)
    execution_tool_count: Literal[0] = 0
    last_tool_activity: datetime | None = None
    last_successful_tool: datetime | None = None
    last_tool_error: str | None = Field(default=None, max_length=60)
    tool_requests_last_hour: int = Field(default=0, ge=0)
    denied_tool_attempts: int = Field(default=0, ge=0)
    offline_ai_enabled: bool = False
    routing_mode: RoutingMode = "manual"
    installed_local_models: int = Field(default=0, ge=0)
    available_local_runtimes: int = Field(default=0, ge=0)
    last_benchmark_at: datetime | None = None


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
    runtime_id: str | None = None
    installed: bool = True
    size_bytes: int | None = Field(default=None, ge=0)
    parameter_count: int | None = Field(default=None, ge=0)
    quantization: str | None = None
    architecture: str | None = None
    capabilities: dict[str, CapabilityState] = Field(default_factory=dict)
    fit: ModelFitState = "unknown"
    fit_reason: str = (
        "Hardware fit is unknown because reported model metadata is incomplete."
    )
    estimated_memory_bytes: int | None = Field(default=None, ge=0)
    estimate_label: str = "Approximate"


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
    execution_mode: ExecutionMode = "local_first"
    offline_ai_enabled: bool = False
    routing_mode: RoutingMode = "manual"
    task_model_routes: dict[str, str] = Field(default_factory=dict, max_length=8)

    @field_validator("task_model_routes")
    @classmethod
    def validate_task_model_routes(cls, value: dict[str, str]) -> dict[str, str]:
        allowed = {
            "fast_triage",
            "general_analyst",
            "deep_analysis",
            "knowledge_rag",
            "tool_calling",
            "structured_reports",
            "bilingual",
            "offline",
        }
        if any(key not in allowed for key in value):
            raise ValueError("Task routing contains an unsupported profile.")
        if any(
            not isinstance(model_id, str) or len(model_id) > 300
            for model_id in value.values()
        ):
            raise ValueError("Task routing model identifier is invalid.")
        return value


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
    task_profile: TaskProfile | None = None
    workflow: (
        Literal[
            "analyze_server",
            "analyze_resource_usage",
            "analyze_services",
            "analyze_ports",
            "analyze_lan",
            "analyze_asset",
            "explain_posture",
            "explain_alert",
            "analyze_investigation",
        ]
        | None
    ) = None
    workflow_scope_id: uuid.UUID | None = None
    desktop_inventory: dict[str, Any] | None = Field(default=None, max_length=5)
    allow_remote_tool_context: bool = False

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
    requested_model_id: str | None = None
    routing_reason: str | None = None
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
    tool_activity: list[dict[str, Any]] = Field(default_factory=list)


class AiMessageResult(BaseModel):
    session_id: uuid.UUID
    user_message: AiMessageView
    assistant_message: AiMessageView
    sources: list[AiContextExcerpt]


class AiToolExecuteRequest(BaseModel):
    tool_id: str = Field(min_length=1, max_length=100)
    arguments: dict[str, Any] = Field(default_factory=dict, max_length=20)
    desktop_inventory: dict[str, Any] | None = Field(default=None, max_length=5)


class AiModelTestRequest(BaseModel):
    model_id: str = Field(min_length=3, max_length=300)


class AiModelTestResponse(BaseModel):
    available: bool
    latency_ms: int | None = None
    model_id: str
    response: str | None = None
    error: str | None = None
    streaming: CapabilityState = "unknown"
    structured_output: CapabilityState = "unknown"
    tools: CapabilityState = "unknown"


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


class AiGpuProfile(BaseModel):
    gpu_id: str
    vendor: str | None = None
    model: str | None = None
    vram_total_bytes: int | None = Field(default=None, ge=0)
    vram_available_bytes: int | None = Field(default=None, ge=0)
    driver_version: str | None = None
    compute_backend: str | None = None
    metadata_source: str


class AiHardwareProfile(BaseModel):
    os_name: str
    os_version: str | None = None
    architecture: str
    cpu_model: str | None = None
    physical_cores: int | None = Field(default=None, ge=0)
    logical_cores: int | None = Field(default=None, ge=0)
    system_memory_total_bytes: int | None = Field(default=None, ge=0)
    system_memory_available_bytes: int | None = Field(default=None, ge=0)
    disk_free_bytes: int | None = Field(default=None, ge=0)
    gpus: list[AiGpuProfile] = Field(default_factory=list)
    readiness: Literal[
        "cpu_only_capable", "entry_local_ai", "moderate_local_ai", "high_local_ai"
    ]
    readiness_reason: str
    profile_hash: str
    sampled_at: datetime


class AiLocalRuntime(BaseModel):
    id: str
    provider_id: str
    name: str
    status: RuntimeState
    endpoint: str
    version: str | None = None
    model_count: int = Field(default=0, ge=0)
    loopback_only: bool = True
    endpoint_classification: Literal["loopback", "network", "unknown"] = "loopback"
    capabilities: dict[str, CapabilityState] = Field(default_factory=dict)
    message: str


class AiModelFit(BaseModel):
    model_id: str
    fit: ModelFitState
    fit_reason: str
    estimated_memory_bytes: int | None = Field(default=None, ge=0)
    estimate_label: str = "Approximate"


class AiLocalAiStatus(BaseModel):
    hardware: AiHardwareProfile
    runtimes: list[AiLocalRuntime]
    models: list[AiModel]
    installed_model_count: int = Field(ge=0)
    available_runtime_count: int = Field(ge=0)
    recommended_model_id: str | None = None
    offline_ai_enabled: bool = False


class AiBenchmarkCreateRequest(BaseModel):
    model_id: str = Field(min_length=3, max_length=300)
    include_warmup: bool = True


class AiBenchmarkResult(BaseModel):
    id: uuid.UUID
    model_id: str
    runtime_id: str
    hardware_hash: str
    profile_version: str
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    started_at: datetime
    completed_at: datetime | None = None
    startup_latency_ms: int | None = Field(default=None, ge=0)
    ttft_ms: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    elapsed_ms: int | None = Field(default=None, ge=0)
    tokens_per_second: float | None = Field(default=None, ge=0)
    generated_tokens: int | None = Field(default=None, ge=0)
    memory_delta_bytes: int | None = None
    scores: dict[str, float | None] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
