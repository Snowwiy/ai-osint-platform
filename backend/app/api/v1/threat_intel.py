from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.threat_intel import ThreatIntelRequest, ThreatIntelResponse
from app.services.investigation import InvestigationNotFoundError
from app.services.target import TargetValidationError
from app.services.threat_intel.threat_service import run_threat_intel_for_request

router = APIRouter(prefix="/threat-intel", tags=["threat-intel"])


@router.post("/ip", response_model=ThreatIntelResponse)
async def enrich_ip_threat_intel(
    body: ThreatIntelRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreatIntelResponse:
    try:
        return await run_threat_intel_for_request(
            db,
            current_user,
            body,
            target_type="ip",
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except TargetValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/domain", response_model=ThreatIntelResponse)
async def enrich_domain_threat_intel(
    body: ThreatIntelRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreatIntelResponse:
    try:
        return await run_threat_intel_for_request(
            db,
            current_user,
            body,
            target_type="domain",
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except TargetValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/url", response_model=ThreatIntelResponse)
async def enrich_url_threat_intel(
    body: ThreatIntelRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreatIntelResponse:
    try:
        return await run_threat_intel_for_request(
            db,
            current_user,
            body,
            target_type="url",
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except TargetValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
