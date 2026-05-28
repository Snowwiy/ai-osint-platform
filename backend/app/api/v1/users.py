from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.user import UserCreate, UserCreateResponse, UserResponse, UserUpdate
from app.services.user import (
    SelfDeactivateError,
    UserConflictError,
    UserNotFoundError,
    create_user,
    deactivate_user,
    get_user,
    list_users,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=PaginatedResponse[UserResponse])
async def list_users_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    role: str | None = None,
    is_active: bool | None = None,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    total, items = await list_users(
        db,
        skip=skip,
        limit=limit,
        role=role,
        is_active=is_active,
    )
    return {"total": total, "items": items}


@router.post(
    "/",
    response_model=UserCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_endpoint(
    body: UserCreate,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        return await create_user(db, body)
    except UserConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_endpoint(
    user_id: uuid.UUID,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        return await get_user(db, user_id)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc


@router.put("/{user_id}", response_model=UserResponse)
async def update_user_endpoint(
    user_id: uuid.UUID,
    body: UserUpdate,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        return await update_user(db, user_id, body)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user_endpoint(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await deactivate_user(db, user_id=user_id, current_user_id=current_user.id)
    except SelfDeactivateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
