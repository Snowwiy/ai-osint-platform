from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.threat_workspace import (
    ThreatCampaignListResponse,
    ThreatGroupListResponse,
    ThreatIndicatorListResponse,
    ThreatInfrastructureResponse,
    ThreatOverviewResponse,
    ThreatTechniqueListResponse,
    ThreatTimelineResponse,
)
from app.services.audit import record_event
from app.services.threat_workspace import (
    get_threat_campaigns,
    get_threat_groups,
    get_threat_indicators,
    get_threat_infrastructure,
    get_threat_overview,
    get_threat_techniques,
    get_threat_timeline,
)

router = APIRouter(prefix="/threat", tags=["threat-workspace"])


@router.get("/overview", response_model=ThreatOverviewResponse)
async def threat_overview_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreatOverviewResponse:
    response = await get_threat_overview(db, current_user)
    await record_event(
        db,
        action="intelligence.viewed",
        actor_id=current_user.id,
        resource_type="threat_workspace",
        metadata={"endpoint": "/threat/overview"},
    )
    return response


@router.get("/timeline", response_model=ThreatTimelineResponse)
async def threat_timeline_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreatTimelineResponse:
    response = await get_threat_timeline(db, current_user)
    await record_event(
        db,
        action="intelligence.viewed",
        actor_id=current_user.id,
        resource_type="threat_timeline",
        metadata={"endpoint": "/threat/timeline"},
    )
    return response


@router.get("/indicators", response_model=ThreatIndicatorListResponse)
async def threat_indicators_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreatIndicatorListResponse:
    response = await get_threat_indicators(db, current_user)
    await record_event(
        db,
        action="intelligence.viewed",
        actor_id=current_user.id,
        resource_type="threat_indicator",
        metadata={"endpoint": "/threat/indicators"},
    )
    return response


@router.get("/campaigns", response_model=ThreatCampaignListResponse)
async def threat_campaigns_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreatCampaignListResponse:
    response = await get_threat_campaigns(db, current_user)
    await record_event(
        db,
        action="intelligence.viewed",
        actor_id=current_user.id,
        resource_type="threat_campaign",
        metadata={"endpoint": "/threat/campaigns"},
    )
    return response


@router.get("/groups", response_model=ThreatGroupListResponse)
async def threat_groups_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreatGroupListResponse:
    response = await get_threat_groups(db, current_user)
    await record_event(
        db,
        action="intelligence.viewed",
        actor_id=current_user.id,
        resource_type="threat_group",
        metadata={"endpoint": "/threat/groups"},
    )
    return response


@router.get("/techniques", response_model=ThreatTechniqueListResponse)
async def threat_techniques_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreatTechniqueListResponse:
    response = await get_threat_techniques(db, current_user)
    await record_event(
        db,
        action="intelligence.viewed",
        actor_id=current_user.id,
        resource_type="threat_technique",
        metadata={"endpoint": "/threat/techniques"},
    )
    return response


@router.get("/infrastructure", response_model=ThreatInfrastructureResponse)
async def threat_infrastructure_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreatInfrastructureResponse:
    response = await get_threat_infrastructure(db, current_user)
    await record_event(
        db,
        action="intelligence.viewed",
        actor_id=current_user.id,
        resource_type="threat_infrastructure",
        metadata={"endpoint": "/threat/infrastructure"},
    )
    return response
