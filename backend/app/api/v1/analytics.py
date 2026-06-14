from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.analytics import (
    DashboardAnalyticsResponse,
    DashboardMetricsResponse,
    InvestigationAnalyticsResponse,
)
from app.services.analytics import (
    get_dashboard_analytics,
    get_dashboard_metrics,
    get_investigation_analytics,
)
from app.services.investigation import InvestigationNotFoundError

router = APIRouter(tags=["analytics"])


@router.get(
    "/investigations/{investigation_id}/analytics",
    response_model=InvestigationAnalyticsResponse,
)
async def investigation_analytics_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationAnalyticsResponse:
    try:
        return await get_investigation_analytics(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.get(
    "/dashboard/analytics",
    response_model=DashboardAnalyticsResponse,
)
async def dashboard_analytics_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardAnalyticsResponse:
    return await get_dashboard_analytics(db, current_user)


@router.get(
    "/dashboard/metrics",
    response_model=DashboardMetricsResponse,
)
async def dashboard_metrics_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardMetricsResponse:
    return await get_dashboard_metrics(db, current_user)
