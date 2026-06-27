from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.models.user import User
from app.schemas.audit import AuditLogListResponse
from app.schemas.governance import (
    AdminOverviewResponse,
    AdminSettingsResponse,
    AdminSettingsUpdate,
    FeatureAvailabilityResponse,
    FeatureFlagUpdate,
    RetentionStatusResponse,
    RetentionUpdate,
)
from app.schemas.qa import AdminQaStatusResponse, DemoSeedResponse
from app.services.admin import get_health_status, get_platform_stats
from app.services.audit import list_audit_events, to_audit_response
from app.services.demo import clear_demo_workspace, set_demo_workspace_enabled
from app.services.governance import (
    get_admin_overview,
    get_admin_settings,
    get_feature_availability,
    get_retention_status,
    update_admin_settings,
    update_feature_flags,
    update_retention,
)
from app.services.qa import get_qa_status

router = APIRouter()


@router.get("/features", response_model=FeatureAvailabilityResponse)
async def feature_availability(
    _current_user: User = Depends(require_role("admin", "analyst")),
    db: AsyncSession = Depends(get_db),
) -> FeatureAvailabilityResponse:
    return await get_feature_availability(db)


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


@router.get("/admin/settings", response_model=AdminSettingsResponse)
async def admin_settings(
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AdminSettingsResponse:
    return await get_admin_settings(db)


@router.patch("/admin/settings", response_model=AdminSettingsResponse)
async def update_settings(
    body: AdminSettingsUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AdminSettingsResponse:
    return await update_admin_settings(db, current_user, body)


@router.get("/admin/feature-flags", response_model=FeatureAvailabilityResponse)
async def admin_feature_flags(
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> FeatureAvailabilityResponse:
    return await get_feature_availability(db)


@router.patch("/admin/feature-flags", response_model=FeatureAvailabilityResponse)
async def update_admin_feature_flags(
    body: FeatureFlagUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> FeatureAvailabilityResponse:
    return await update_feature_flags(db, current_user, body.feature_flags)


@router.get("/admin/retention", response_model=RetentionStatusResponse)
async def admin_retention(
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> RetentionStatusResponse:
    return await get_retention_status(db)


@router.patch("/admin/retention", response_model=RetentionStatusResponse)
async def update_admin_retention(
    body: RetentionUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> RetentionStatusResponse:
    return await update_retention(db, current_user, body)


@router.get("/admin/overview", response_model=AdminOverviewResponse)
async def admin_overview(
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AdminOverviewResponse:
    return await get_admin_overview(db)


@router.get("/admin/qa/status", response_model=AdminQaStatusResponse)
async def admin_qa_status(
    request: Request,
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AdminQaStatusResponse:
    return await get_qa_status(db, request.app.state.redis)


@router.post("/admin/demo/seed", response_model=DemoSeedResponse)
async def seed_demo_workspace(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> DemoSeedResponse:
    availability = await get_feature_availability(db)
    if not availability.feature_flags.enable_demo_mode:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "feature_disabled",
                "message": (
                    "Demo mode is disabled. Enable it in Admin Settings first."
                ),
            },
        )
    return await set_demo_workspace_enabled(db, current_user, enabled=True)


@router.delete("/admin/demo/clear", response_model=DemoSeedResponse)
async def clear_demo_workspace_endpoint(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> DemoSeedResponse:
    return await clear_demo_workspace(db, current_user)
