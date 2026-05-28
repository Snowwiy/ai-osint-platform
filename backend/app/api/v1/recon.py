from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.recon import ReconRequest, ReconResponse
from app.services.investigation import InvestigationNotFoundError
from app.services.recon.recon_service import run_recon_for_request
from app.services.target import TargetValidationError

router = APIRouter(prefix="/recon", tags=["recon"])


@router.post("/domain", response_model=ReconResponse)
async def recon_domain(
    body: ReconRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReconResponse:
    try:
        return await run_recon_for_request(db, current_user, body, target_type="domain")
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except TargetValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/ip", response_model=ReconResponse)
async def recon_ip(
    body: ReconRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReconResponse:
    try:
        return await run_recon_for_request(db, current_user, body, target_type="ip")
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except TargetValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/url", response_model=ReconResponse)
async def recon_url(
    body: ReconRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReconResponse:
    try:
        return await run_recon_for_request(db, current_user, body, target_type="url")
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except TargetValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
