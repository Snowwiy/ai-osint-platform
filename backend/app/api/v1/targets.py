from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.target import Target
from app.models.user import User
from app.schemas.target import TargetCreate, TargetListResponse, TargetResponse
from app.services.investigation import ForbiddenError, InvestigationNotFoundError
from app.services.target import (
    TargetConflictError,
    TargetNotFoundError,
    TargetValidationError,
    create_target,
    delete_target,
    get_target,
    list_targets,
)

router = APIRouter(prefix="/targets", tags=["targets"])


@router.get("/", response_model=TargetListResponse)
async def list_targets_endpoint(
    investigation_id: uuid.UUID,
    target_type: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    try:
        total, items = await list_targets(
            db,
            current_user,
            investigation_id=investigation_id,
            target_type=target_type,
            skip=skip,
            limit=limit,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    return {"total": total, "items": items}


@router.post(
    "/",
    response_model=TargetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_target_endpoint(
    body: TargetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Target:
    try:
        return await create_target(db, current_user, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except TargetValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TargetConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{target_id}", response_model=TargetResponse)
async def get_target_endpoint(
    target_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Target:
    try:
        return await get_target(db, current_user, target_id)
    except (TargetNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Target not found") from exc


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target_endpoint(
    target_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_target(db, current_user, target_id)
    except (TargetNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Target not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
