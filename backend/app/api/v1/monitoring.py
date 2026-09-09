from __future__ import annotations

import logging
import secrets
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.models.user import User
from app.core.config import settings
from app.schemas.lan_monitoring import (
    LanAgentRegistration,
    LanAgentRegistrationResponse,
    LanAgentTelemetryIngest,
    LanAgentTelemetryResponse,
    LanAssetListResponse,
    LanAssetResponse,
    LanAssetUpdate,
    LanDiscoveryRequest,
    LanDiscoveryResponse,
    LanServiceListResponse,
    LanTelemetryListResponse,
)
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
from app.services.lan_monitoring import (
    LanAssetNotFoundError,
    LanConfigurationError,
    LanDiscoveryRateLimitedError,
    LanMonitoringDisabledError,
    discover_lan,
    get_lan_asset,
    ingest_agent_telemetry as ingest_lan_agent_telemetry,
    list_asset_services,
    list_asset_telemetry,
    list_lan_assets,
    notify_discovery_failure,
    register_agent,
    update_lan_asset,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/monitoring", tags=["monitoring"])


def _require_lan_agent_token(
    provided: str | None = Header(default=None, alias="X-LAN-Agent-Token"),
) -> None:
    configured = settings.LAN_AGENT_TOKEN
    if not settings.LAN_MONITORING_ENABLED or not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LAN endpoint telemetry is disabled.",
        )
    if provided is None or not secrets.compare_digest(provided, configured):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid endpoint agent token.",
        )


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


@router.get("/lan/assets", response_model=LanAssetListResponse)
async def lan_assets_endpoint(
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> LanAssetListResponse:
    return await _safe_lan_call(list_lan_assets, db)


@router.get("/lan/assets/{asset_id}", response_model=LanAssetResponse)
async def lan_asset_endpoint(
    asset_id: uuid.UUID,
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> LanAssetResponse:
    return await _safe_lan_call(get_lan_asset, db, asset_id)


@router.post("/lan/discover", response_model=LanDiscoveryResponse)
async def lan_discover_endpoint(
    body: LanDiscoveryRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> LanDiscoveryResponse:
    try:
        return await _safe_lan_call(discover_lan, db, current_user, body)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            await db.rollback()
            try:
                await notify_discovery_failure(db, current_user)
                await db.flush()
                await db.commit()
            except Exception:
                logger.exception("monitoring.lan failure notification skipped")
        raise


@router.patch("/lan/assets/{asset_id}", response_model=LanAssetResponse)
async def lan_asset_update_endpoint(
    asset_id: uuid.UUID,
    body: LanAssetUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> LanAssetResponse:
    return await _safe_lan_call(update_lan_asset, db, current_user, asset_id, body)


@router.get("/lan/assets/{asset_id}/telemetry", response_model=LanTelemetryListResponse)
async def lan_asset_telemetry_endpoint(
    asset_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> LanTelemetryListResponse:
    return await _safe_lan_call(list_asset_telemetry, db, asset_id, limit)


@router.get("/lan/assets/{asset_id}/services", response_model=LanServiceListResponse)
async def lan_asset_services_endpoint(
    asset_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> LanServiceListResponse:
    return await _safe_lan_call(list_asset_services, db, asset_id, limit)


@router.post(
    "/agent/register",
    response_model=LanAgentRegistrationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def lan_agent_register_endpoint(
    body: LanAgentRegistration,
    _agent_token: None = Depends(_require_lan_agent_token),
    db: AsyncSession = Depends(get_db),
) -> LanAgentRegistrationResponse:
    return await _safe_lan_call(register_agent, db, body)


@router.post(
    "/agent/telemetry",
    response_model=LanAgentTelemetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def lan_agent_telemetry_ingest_endpoint(
    body: LanAgentTelemetryIngest,
    _agent_token: None = Depends(_require_lan_agent_token),
    db: AsyncSession = Depends(get_db),
) -> LanAgentTelemetryResponse:
    return await _safe_lan_call(ingest_lan_agent_telemetry, db, body)


def _monitoring_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Monitoring data is temporarily unavailable.",
    )


async def _safe_lan_call(
    function: Callable[..., Awaitable[Any]], *args: Any
) -> Any:
    try:
        return await function(*args)
    except LanMonitoringDisabledError as exc:
        raise HTTPException(status_code=409, detail="LAN monitoring is disabled.") from exc
    except LanConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LanAssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="LAN asset not found.") from exc
    except LanDiscoveryRateLimitedError as exc:
        raise HTTPException(
            status_code=429,
            detail="LAN discovery is rate limited. Wait for the configured interval.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("monitoring.lan operation failed")
        raise _monitoring_unavailable() from exc
