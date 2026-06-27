from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.correlation import (
    CorrelationResponse,
    CrossInvestigationCorrelationResponse,
    CrossInvestigationSignalType,
)
from app.schemas.finding import FindingSeverity
from app.schemas.timeline import TimelineEventType, TimelineResponse
from app.services.correlation.service import (
    get_cross_investigation_correlations,
    get_investigation_correlations,
)
from app.services.investigation import InvestigationNotFoundError
from app.services.timeline.service import (
    TimelineFilters,
    get_investigation_timeline,
)

router = APIRouter(tags=["timeline"])


@router.get(
    "/investigations/{investigation_id}/timeline",
    response_model=TimelineResponse,
)
async def get_timeline_endpoint(
    investigation_id: uuid.UUID,
    severity: FindingSeverity | None = Query(default=None),
    event_type: TimelineEventType | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    source: str | None = Query(default=None, min_length=1, max_length=50),
    analyst_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TimelineResponse:
    try:
        return await get_investigation_timeline(
            db,
            current_user,
            investigation_id,
            filters=TimelineFilters(
                severity=severity,
                event_type=event_type,
                start_date=start_date,
                end_date=end_date,
                source=source,
                actor_id=analyst_id,
            ),
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.get(
    "/investigations/{investigation_id}/correlations",
    response_model=CorrelationResponse,
)
async def get_correlations_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CorrelationResponse:
    try:
        return await get_investigation_correlations(
            db,
            current_user,
            investigation_id,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.get(
    "/correlations/cross-investigation",
    response_model=CrossInvestigationCorrelationResponse,
)
async def get_cross_investigation_correlations_endpoint(
    signal_type: CrossInvestigationSignalType | None = Query(default=None),
    top_k: int = Query(default=100, ge=1, le=250),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CrossInvestigationCorrelationResponse:
    return await get_cross_investigation_correlations(
        db,
        current_user,
        signal_type=signal_type,
        top_k=top_k,
    )
