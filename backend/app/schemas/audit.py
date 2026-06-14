from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: uuid.UUID | None = None
    action: str
    resource_type: str | None = None
    resource_id: uuid.UUID | None = None
    investigation_id: uuid.UUID | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AuditLogListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AuditLogResponse]
