from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.analysis import (
    AnalysisResponse,
    IocAnalysisRequest,
    InvestigationAnalysisRequest,
    ThreatContextAnalysisRequest,
)
from app.services.ai.analyst_service import (
    analyze_investigation,
    analyze_ioc,
    analyze_threat_context,
)
from app.services.investigation import InvestigationNotFoundError

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/investigation", response_model=AnalysisResponse)
async def analyze_investigation_endpoint(
    body: InvestigationAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    try:
        return await analyze_investigation(db, current_user, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.post("/ioc", response_model=AnalysisResponse)
async def analyze_ioc_endpoint(
    body: IocAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    try:
        return await analyze_ioc(db, current_user, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.post("/threat-context", response_model=AnalysisResponse)
async def analyze_threat_context_endpoint(
    body: ThreatContextAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    try:
        return await analyze_threat_context(db, current_user, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
