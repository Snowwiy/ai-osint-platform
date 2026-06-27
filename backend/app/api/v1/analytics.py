from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_feature
from app.models.user import User
from app.schemas.analytics import (
    DashboardAnalyticsResponse,
    DashboardMetricsResponse,
    InvestigationAnalyticsResponse,
)
from app.schemas.defensive_intelligence import (
    InvestigationCoverageResponse,
    InvestigationRecommendationsResponse,
)
from app.schemas.executive import (
    ExecutiveDashboardResponse,
    ExecutiveInvestigationSummaryResponse,
    ExecutivePostureResponse,
    ExecutiveRecommendationsResponse,
    ExecutiveTrendsResponse,
    InvestigationRiskScoreResponse,
)
from app.services.audit import record_event
from app.services.analytics import (
    get_dashboard_analytics,
    get_dashboard_metrics,
    get_investigation_analytics,
)
from app.services.defensive_intelligence import (
    get_investigation_coverage,
    get_investigation_recommendations,
)
from app.services.executive import (
    get_executive_dashboard,
    get_executive_investigation_summary,
    get_executive_posture,
    get_executive_recommendations,
    get_executive_trends,
    get_investigation_risk_score,
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
    _feature: None = Depends(require_feature("enable_advanced_dashboard")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardAnalyticsResponse:
    return await get_dashboard_analytics(db, current_user)


@router.get(
    "/dashboard/metrics",
    response_model=DashboardMetricsResponse,
)
async def dashboard_metrics_endpoint(
    _feature: None = Depends(require_feature("enable_advanced_dashboard")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardMetricsResponse:
    return await get_dashboard_metrics(db, current_user)


@router.get(
    "/investigations/{investigation_id}/executive-summary",
    response_model=ExecutiveInvestigationSummaryResponse,
)
async def executive_investigation_summary_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutiveInvestigationSummaryResponse:
    try:
        response = await get_executive_investigation_summary(
            db,
            current_user,
            investigation_id,
        )
        await record_event(
            db,
            action="executive.summary_generated",
            actor_id=current_user.id,
            resource_type="investigation",
            resource_id=investigation_id,
            investigation_id=investigation_id,
            metadata={"source": "executive_summary_endpoint"},
        )
        return response
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.get(
    "/investigations/{investigation_id}/risk-score",
    response_model=InvestigationRiskScoreResponse,
)
async def investigation_risk_score_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationRiskScoreResponse:
    try:
        return await get_investigation_risk_score(
            db,
            current_user,
            investigation_id,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.get(
    "/dashboard/executive",
    response_model=ExecutiveDashboardResponse,
)
async def executive_dashboard_endpoint(
    _feature: None = Depends(require_feature("enable_advanced_dashboard")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutiveDashboardResponse:
    return await get_executive_dashboard(db, current_user)


@router.get(
    "/executive/dashboard",
    response_model=ExecutiveDashboardResponse,
)
async def executive_dashboard_v1_endpoint(
    _feature: None = Depends(require_feature("enable_advanced_dashboard")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutiveDashboardResponse:
    response = await get_executive_dashboard(db, current_user)
    await record_event(
        db,
        action="executive.dashboard_viewed",
        actor_id=current_user.id,
        resource_type="executive_dashboard",
        metadata={"source": "executive_dashboard_endpoint"},
    )
    return response


@router.get(
    "/executive/posture",
    response_model=ExecutivePostureResponse,
)
async def executive_posture_endpoint(
    _feature: None = Depends(require_feature("enable_advanced_dashboard")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutivePostureResponse:
    return await get_executive_posture(db, current_user)


@router.get(
    "/executive/trends",
    response_model=ExecutiveTrendsResponse,
)
async def executive_trends_endpoint(
    _feature: None = Depends(require_feature("enable_advanced_dashboard")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutiveTrendsResponse:
    return await get_executive_trends(db, current_user)


@router.get(
    "/executive/recommendations",
    response_model=ExecutiveRecommendationsResponse,
)
async def executive_recommendations_endpoint(
    _feature: None = Depends(require_feature("enable_advanced_dashboard")),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExecutiveRecommendationsResponse:
    return await get_executive_recommendations(db, current_user)


@router.get(
    "/investigations/{investigation_id}/coverage",
    response_model=InvestigationCoverageResponse,
)
async def investigation_coverage_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationCoverageResponse:
    try:
        return await get_investigation_coverage(
            db,
            current_user,
            investigation_id,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.get(
    "/investigations/{investigation_id}/recommendations",
    response_model=InvestigationRecommendationsResponse,
)
async def investigation_recommendations_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationRecommendationsResponse:
    try:
        return await get_investigation_recommendations(
            db,
            current_user,
            investigation_id,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
