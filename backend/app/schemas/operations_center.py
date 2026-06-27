from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

OperationalStatus = Literal["healthy", "degraded", "unavailable"]
ValidationStatus = Literal["configured", "missing", "misconfigured"]
ExportFormat = Literal["json", "zip"]


class OperationsComponentStatus(BaseModel):
    status: OperationalStatus
    detail: str = ""
    metadata: dict[str, str | bool | int | None] = Field(default_factory=dict)


class ReleaseInfo(BaseModel):
    app_name: str
    version: str
    release_channel: str
    build_date: str
    git_commit: str
    build: str
    environment: str
    current_migration: str
    head_migration: str
    migration_status: str
    database_version: str


class StorageMetrics(BaseModel):
    investigations_count: int = Field(ge=0)
    findings_count: int = Field(ge=0)
    reports_count: int = Field(ge=0)
    templates_count: int = Field(ge=0)
    audit_events_count: int = Field(ge=0)
    knowledge_documents_count: int = Field(ge=0)
    report_storage_bytes: int = Field(ge=0)
    database_size_bytes: int = Field(ge=0)


class RecentOperationEvent(BaseModel):
    action: str
    resource_type: str | None = None
    created_at: datetime


class OperationsStatusResponse(BaseModel):
    generated_at: datetime
    status: OperationalStatus
    uptime_seconds: int = Field(ge=0)
    release: ReleaseInfo
    components: dict[str, OperationsComponentStatus]
    storage: StorageMetrics
    recent_operations: list[RecentOperationEvent]


class EnvironmentValidationItem(BaseModel):
    name: str
    scope: Literal["backend", "frontend", "reports", "ai", "storage"]
    status: ValidationStatus
    required: bool
    detail: str


class EnvironmentValidationResponse(BaseModel):
    generated_at: datetime
    items: list[EnvironmentValidationItem]


class DiagnosticsPackageResponse(BaseModel):
    schema_version: str
    generated_at: datetime
    health: dict[str, Any]
    release: ReleaseInfo
    environment_validation: EnvironmentValidationResponse
    enabled_modules: dict[str, bool]
    retention_config: dict[str, Any]
    governance_config: dict[str, Any]
    report_configuration: dict[str, Any]
    storage: StorageMetrics


class BackupPackageResponse(BaseModel):
    schema_version: str
    generated_at: datetime
    app_version: str
    manifest: dict[str, Any]
    records: dict[str, Any]


class RestoreValidationRequest(BaseModel):
    dry_run: bool = True
    backup: dict[str, Any] | None = None
    archive_base64: str | None = None


class RestoreValidationResponse(BaseModel):
    dry_run: bool
    valid: bool
    schema_version: str | None = None
    compatible: bool
    corruption_detected: bool
    record_counts: dict[str, int]
    warnings: list[str]
    errors: list[str]
