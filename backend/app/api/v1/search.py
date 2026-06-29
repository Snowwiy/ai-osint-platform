from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.search import (
    GlobalSearchResponse,
    GlobalSearchType,
    SavedViewCreate,
    SavedViewListResponse,
    SavedViewResponse,
    SavedViewUpdate,
)
from app.services.search import (
    SavedViewConflictError,
    SavedViewNotFoundError,
    create_saved_view,
    delete_saved_view,
    get_saved_view,
    global_search,
    list_saved_views,
    set_saved_view_default,
    set_saved_view_pin,
    update_saved_view,
)

router = APIRouter(tags=["search"])
saved_views_router = APIRouter(prefix="/saved-views", tags=["saved-views"])


@router.get("/search", response_model=GlobalSearchResponse)
async def global_search_endpoint(
    q: str = Query(default="", max_length=120),
    type: GlobalSearchType | None = Query(default=None),  # noqa: A002
    limit: int = Query(default=25, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    include_archived: bool = Query(default=False),
    investigation_id: uuid.UUID | None = Query(default=None),
    engagement_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GlobalSearchResponse:
    return await global_search(
        db,
        current_user,
        query=q,
        result_type=type,
        limit=limit,
        offset=offset,
        include_archived=include_archived,
        investigation_id=investigation_id,
        engagement_id=engagement_id,
    )


@saved_views_router.get("", response_model=SavedViewListResponse)
async def list_saved_views_endpoint(
    view_type: str | None = Query(default=None),
    pinned: bool | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedViewListResponse:
    return await list_saved_views(
        db,
        current_user,
        view_type=view_type,
        pinned=pinned,
    )


@saved_views_router.post(
    "",
    response_model=SavedViewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_saved_view_endpoint(
    body: SavedViewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedViewResponse:
    try:
        return await create_saved_view(db, current_user, body)
    except SavedViewConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@saved_views_router.get("/{saved_view_id}", response_model=SavedViewResponse)
async def get_saved_view_endpoint(
    saved_view_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedViewResponse:
    try:
        return await get_saved_view(db, current_user, saved_view_id)
    except SavedViewNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Saved view not found") from exc


@saved_views_router.patch("/{saved_view_id}", response_model=SavedViewResponse)
async def update_saved_view_endpoint(
    saved_view_id: uuid.UUID,
    body: SavedViewUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedViewResponse:
    try:
        return await update_saved_view(db, current_user, saved_view_id, body)
    except SavedViewNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Saved view not found") from exc
    except SavedViewConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@saved_views_router.delete(
    "/{saved_view_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_saved_view_endpoint(
    saved_view_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_saved_view(db, current_user, saved_view_id)
    except SavedViewNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Saved view not found") from exc


@saved_views_router.post("/{saved_view_id}/pin", response_model=SavedViewResponse)
async def pin_saved_view_endpoint(
    saved_view_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedViewResponse:
    try:
        return await set_saved_view_pin(db, current_user, saved_view_id, pinned=True)
    except SavedViewNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Saved view not found") from exc


@saved_views_router.post("/{saved_view_id}/unpin", response_model=SavedViewResponse)
async def unpin_saved_view_endpoint(
    saved_view_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedViewResponse:
    try:
        return await set_saved_view_pin(db, current_user, saved_view_id, pinned=False)
    except SavedViewNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Saved view not found") from exc


@saved_views_router.post(
    "/{saved_view_id}/set-default",
    response_model=SavedViewResponse,
)
async def set_default_saved_view_endpoint(
    saved_view_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedViewResponse:
    try:
        return await set_saved_view_default(db, current_user, saved_view_id)
    except SavedViewNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Saved view not found") from exc
