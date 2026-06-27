from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.ioc import (
    IOCConfidence,
    IOCCorrelationResponse,
    IOCDetail,
    IOCListResponse,
    IOCType,
    InvestigationPrioritizationResponse,
)
from app.services.investigation import InvestigationNotFoundError
from app.services.ioc_intelligence import (
    get_investigation_prioritization,
    get_ioc_correlations,
    get_ioc_detail,
    list_investigation_iocs,
    list_iocs,
)

router = APIRouter(tags=["ioc-intelligence"])


@router.get("/iocs", response_model=IOCListResponse)
async def list_iocs_endpoint(
    ioc_type: IOCType | None = Query(default=None, alias="type"),
    confidence: IOCConfidence | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=500),
    recurring_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IOCListResponse:
    return await list_iocs(
        db,
        current_user,
        ioc_type=ioc_type,
        confidence=confidence,
        query=q,
        recurring_only=recurring_only,
        limit=limit,
        offset=offset,
    )


@router.get("/iocs/correlations", response_model=IOCCorrelationResponse)
async def ioc_correlations_endpoint(
    limit: int = Query(default=100, ge=1, le=250),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IOCCorrelationResponse:
    return await get_ioc_correlations(db, current_user, limit=limit)


@router.get("/iocs/{ioc_id}", response_model=IOCDetail)
async def ioc_detail_endpoint(
    ioc_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IOCDetail:
    try:
        return await get_ioc_detail(db, current_user, ioc_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="IOC not found") from exc


@router.get(
    "/investigations/{investigation_id}/iocs",
    response_model=IOCListResponse,
)
async def investigation_iocs_endpoint(
    investigation_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IOCListResponse:
    try:
        return await list_investigation_iocs(
            db,
            current_user,
            investigation_id,
            limit=limit,
            offset=offset,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.get(
    "/investigations/{investigation_id}/prioritization",
    response_model=InvestigationPrioritizationResponse,
)
async def investigation_prioritization_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationPrioritizationResponse:
    try:
        return await get_investigation_prioritization(
            db,
            current_user,
            investigation_id,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
