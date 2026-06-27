from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.evidence_intelligence import (
    EvidenceIntelligenceEvidenceResponse,
    EvidenceIntelligenceIOCResponse,
    EvidenceIntelligenceOverviewResponse,
    EvidenceIntelligencePriorityResponse,
    EvidenceIntelligenceTimelineResponse,
)
from app.services.audit import record_event
from app.services.evidence_intelligence import (
    get_intelligence_evidence,
    get_intelligence_iocs,
    get_intelligence_overview,
    get_intelligence_priority,
    get_intelligence_timeline,
)

router = APIRouter(prefix="/intelligence", tags=["evidence-intelligence"])


@router.get("/overview", response_model=EvidenceIntelligenceOverviewResponse)
async def intelligence_overview_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvidenceIntelligenceOverviewResponse:
    response = await get_intelligence_overview(db, current_user)
    await record_event(
        db,
        action="intelligence.generated",
        actor_id=current_user.id,
        resource_type="evidence_intelligence",
        metadata={"endpoint": "/intelligence/overview"},
    )
    return response


@router.get("/evidence", response_model=EvidenceIntelligenceEvidenceResponse)
async def intelligence_evidence_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvidenceIntelligenceEvidenceResponse:
    response = await get_intelligence_evidence(db, current_user)
    await record_event(
        db,
        action="intelligence.viewed",
        actor_id=current_user.id,
        resource_type="evidence_intelligence",
        metadata={"endpoint": "/intelligence/evidence"},
    )
    return response


@router.get("/priority", response_model=EvidenceIntelligencePriorityResponse)
async def intelligence_priority_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvidenceIntelligencePriorityResponse:
    response = await get_intelligence_priority(db, current_user)
    await record_event(
        db,
        action="priority.recalculated",
        actor_id=current_user.id,
        resource_type="evidence_intelligence",
        metadata={"endpoint": "/intelligence/priority"},
    )
    return response


@router.get("/timeline", response_model=EvidenceIntelligenceTimelineResponse)
async def intelligence_timeline_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvidenceIntelligenceTimelineResponse:
    response = await get_intelligence_timeline(db, current_user)
    await record_event(
        db,
        action="intelligence.viewed",
        actor_id=current_user.id,
        resource_type="evidence_intelligence",
        metadata={"endpoint": "/intelligence/timeline"},
    )
    return response


@router.get("/iocs", response_model=EvidenceIntelligenceIOCResponse)
async def intelligence_iocs_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvidenceIntelligenceIOCResponse:
    response = await get_intelligence_iocs(db, current_user)
    await record_event(
        db,
        action="intelligence.viewed",
        actor_id=current_user.id,
        resource_type="evidence_intelligence",
        metadata={"endpoint": "/intelligence/iocs"},
    )
    return response
