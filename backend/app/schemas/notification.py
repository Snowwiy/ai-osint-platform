from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

NotificationSeverity = Literal["info", "success", "warning", "critical"]
NotificationStatus = Literal["unread", "read", "dismissed", "archived"]
NotificationType = Literal[
    "user_approval_pending",
    "user_approved",
    "investigation_assigned",
    "finding_assigned",
    "report_ready",
    "report_approval_pending",
    "closure_review_pending",
    "closure_blocked",
    "closure_approved",
    "case_closed",
    "case_reopened",
    "scope_warning",
    "authorization_expired",
    "governance_warning",
    "ai_degraded",
    "system_health_warning",
    "deliverable_ready",
    "evidence_package_ready",
]


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    investigation_id: uuid.UUID | None
    engagement_id: uuid.UUID | None
    entity_type: str
    entity_id: uuid.UUID | None
    notification_type: str
    severity: NotificationSeverity
    title: str
    message: str
    action_url: str | None
    status: NotificationStatus
    created_at: datetime
    updated_at: datetime
    read_at: datetime | None
    dismissed_at: datetime | None
    expires_at: datetime | None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NotificationListResponse(BaseModel):
    total: int = Field(ge=0)
    unread: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    items: list[NotificationResponse]


class NotificationUnreadCountResponse(BaseModel):
    unread: int = Field(ge=0)


class NotificationActionResponse(BaseModel):
    notification: NotificationResponse
    message: str


class NotificationMarkAllReadResponse(BaseModel):
    updated: int = Field(ge=0)
    unread: int = Field(ge=0)
    message: str


class WorkflowAlertRebuildResponse(BaseModel):
    created: int = Field(ge=0)
    existing: int = Field(ge=0)
    total_unread: int = Field(ge=0)
    message: str
