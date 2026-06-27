from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class QaComponentStatus(BaseModel):
    status: str
    detail: str


class AdminQaStatusResponse(BaseModel):
    app_version: str
    environment: str
    generated_at: datetime
    current_migration: str
    head_migration: str
    migration_status: str
    feature_flags: dict[str, bool]
    report_templates_count: int = Field(ge=0)
    active_investigations_count: int = Field(ge=0)
    archived_investigations_count: int = Field(ge=0)
    audit_count: int = Field(ge=0)
    demo_mode_enabled: bool
    demo_investigation_ready: bool
    demo_investigation_id: uuid.UUID | None
    components: dict[str, QaComponentStatus]
    warnings: list[str]


class DemoSeedResponse(BaseModel):
    enabled: bool
    ready: bool
    investigation_id: uuid.UUID | None
    message: str
