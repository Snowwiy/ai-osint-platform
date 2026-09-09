from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.monitoring import (
    AgentTelemetryIngest,
    AgentTelemetryIngestResponse,
    MonitoringAlertsResponse,
    MonitoringAssetsResponse,
    MonitoringOverviewResponse,
    MonitoringServicesResponse,
    MonitoringSystemResponse,
)
from app.services.local_monitoring import (
    get_asset_watch,
    get_monitoring_alerts,
    get_monitoring_overview,
    get_service_status,
    get_system_metrics,
    ingest_agent_telemetry,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/overview", response_model=MonitoringOverviewResponse)
async def monitoring_overview_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MonitoringOverviewResponse:
    try:
        return await get_monitoring_overview(db, request.app.state.redis, current_user)
    except Exception as exc:
        logger.exception("monitoring.overview failed")
        raise _monitoring_unavailable() from exc


@router.get("/services", response_model=MonitoringServicesResponse)
async def monitoring_services_endpoint(
    request: Request,
    _current_user: User = Depends(get_current_user),
) -> MonitoringServicesResponse:
    return await get_service_status(request.app.state.redis)


@router.get("/system", response_model=MonitoringSystemResponse)
async def monitoring_system_endpoint(
    _current_user: User = Depends(get_current_user),
) -> MonitoringSystemResponse:
    return get_system_metrics()


@router.get("/assets", response_model=MonitoringAssetsResponse)
async def monitoring_assets_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MonitoringAssetsResponse:
    try:
        return await get_asset_watch(db, current_user)
    except Exception as exc:
        logger.exception("monitoring.assets failed")
        raise _monitoring_unavailable() from exc


@router.get("/alerts", response_model=MonitoringAlertsResponse)
async def monitoring_alerts_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MonitoringAlertsResponse:
    try:
        services = await get_service_status(request.app.state.redis)
        system = get_system_metrics()
        assets = await get_asset_watch(db, current_user)
        return await get_monitoring_alerts(
            db,
            current_user,
            services=services,
            system=system,
            assets=assets,
        )
    except Exception as exc:
        logger.exception("monitoring.alerts failed")
        raise _monitoring_unavailable() from exc


@router.post(
    "/agent/ingest",
    response_model=AgentTelemetryIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def monitoring_agent_ingest_endpoint(
    body: AgentTelemetryIngest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> AgentTelemetryIngestResponse:
    return await ingest_agent_telemetry(db, current_user, body)


def _monitoring_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Monitoring data is temporarily unavailable.",
    )
