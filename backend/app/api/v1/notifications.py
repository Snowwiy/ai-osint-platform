from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.notification import (
    NotificationActionResponse,
    NotificationListResponse,
    NotificationMarkAllReadResponse,
    NotificationUnreadCountResponse,
    WorkflowAlertRebuildResponse,
)
from app.services.notification import (
    NotificationNotFoundError,
    dismiss_notification,
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    rebuild_workflow_alerts,
    unread_count,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications_endpoint(
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    notification_type: str | None = Query(default=None),
    investigation_id: uuid.UUID | None = Query(default=None),
    engagement_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    return await list_notifications(
        db,
        current_user,
        status=status,
        severity=severity,
        notification_type=notification_type,
        investigation_id=investigation_id,
        engagement_id=engagement_id,
        limit=limit,
        offset=offset,
    )


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
async def unread_count_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationUnreadCountResponse:
    return NotificationUnreadCountResponse(unread=await unread_count(db, current_user))


@router.patch("/{notification_id}/read", response_model=NotificationActionResponse)
async def mark_notification_read_endpoint(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationActionResponse:
    try:
        return await mark_notification_read(db, current_user, notification_id)
    except NotificationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Notification not found") from exc


@router.patch("/{notification_id}/dismiss", response_model=NotificationActionResponse)
async def dismiss_notification_endpoint(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationActionResponse:
    try:
        return await dismiss_notification(db, current_user, notification_id)
    except NotificationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Notification not found") from exc


@router.post("/mark-all-read", response_model=NotificationMarkAllReadResponse)
async def mark_all_read_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationMarkAllReadResponse:
    return await mark_all_notifications_read(db, current_user)


@router.post(
    "/rebuild-workflow-alerts",
    response_model=WorkflowAlertRebuildResponse,
)
async def rebuild_workflow_alerts_endpoint(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> WorkflowAlertRebuildResponse:
    return await rebuild_workflow_alerts(db, current_user)
