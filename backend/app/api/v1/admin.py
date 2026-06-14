from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.models.user import User
from app.schemas.audit import AuditLogListResponse
from app.services.admin import get_health_status, get_platform_stats
from app.services.audit import list_audit_events, to_audit_response

router = APIRouter()


@router.get("/admin/health")
async def health_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    return await get_health_status(db, request.app.state.redis)


@router.get("/admin/stats")
async def stats(
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, dict[str, int]]:
    return await get_platform_stats(db)


@router.get("/admin/audit", response_model=AuditLogListResponse)
async def audit_events(
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    actor_id: uuid.UUID | None = Query(default=None),
    investigation_id: uuid.UUID | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    try:
        total, events = await list_audit_events(
            db,
            action=action,
            resource_type=resource_type,
            actor_id=actor_id,
            investigation_id=investigation_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )
    except Exception:
        total, events = 0, []
    return AuditLogListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[to_audit_response(event) for event in events],
    )
