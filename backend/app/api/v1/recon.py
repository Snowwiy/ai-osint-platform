from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.recon import ReconRequest, ReconResponse
from app.services.audit import record_event
from app.services.investigation import ForbiddenError, InvestigationNotFoundError
from app.services.recon.recon_service import run_recon_for_request
from app.services.target import TargetValidationError

router = APIRouter(prefix="/recon", tags=["recon"])


@router.post("/domain", response_model=ReconResponse)
async def recon_domain(
    body: ReconRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReconResponse:
    try:
        response = await run_recon_for_request(
            db,
            current_user,
            body,
            target_type="domain",
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TargetValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _record_recon_audit(db, request, current_user, body, "domain", response)
    return response


@router.post("/ip", response_model=ReconResponse)
async def recon_ip(
    body: ReconRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReconResponse:
    try:
        response = await run_recon_for_request(db, current_user, body, target_type="ip")
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TargetValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _record_recon_audit(db, request, current_user, body, "ip", response)
    return response


@router.post("/url", response_model=ReconResponse)
async def recon_url(
    body: ReconRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReconResponse:
    try:
        response = await run_recon_for_request(db, current_user, body, target_type="url")
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TargetValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _record_recon_audit(db, request, current_user, body, "url", response)
    return response


async def _record_recon_audit(
    db: AsyncSession,
    request: Request,
    user: User,
    body: ReconRequest,
    target_type: str,
    response: ReconResponse,
) -> None:
    await record_event(
        db,
        action="recon.executed",
        actor_id=user.id,
        resource_type="recon",
        resource_id=response.enrichment_id,
        investigation_id=body.investigation_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata={
            "target_type": target_type,
            "target": body.target,
            "status": response.status,
            "entity_count": len(response.entities),
            "relationship_count": len(response.relationships),
        },
    )
