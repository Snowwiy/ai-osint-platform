from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.investigation import InvestigationReadinessResponse
from app.schemas.productivity import (
    EvidenceBookmarkCreate,
    EvidenceBookmarkListResponse,
    EvidenceBookmarkResponse,
    InvestigationPriorityResponse,
    InvestigationPriorityUpdate,
    InvestigationSummaryResponse,
    InvestigationTagCreate,
    InvestigationTagListResponse,
    InvestigationTagResponse,
    InvestigationTagsUpdate,
)
from app.services.investigation import ForbiddenError, InvestigationNotFoundError
from app.services.productivity import (
    BookmarkAlreadyExistsError,
    ProductivityItemNotFoundError,
    ProductivityValidationError,
    bookmark_response,
    create_bookmark,
    create_tag,
    delete_bookmark,
    generate_investigation_summary,
    get_investigation_readiness,
    get_investigation_tags,
    list_bookmarks,
    list_tags,
    update_investigation_priority,
    update_investigation_tags,
)

router = APIRouter(tags=["productivity"])


@router.get(
    "/investigations/{investigation_id}/readiness",
    response_model=InvestigationReadinessResponse,
)
async def investigation_readiness_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationReadinessResponse:
    try:
        return await get_investigation_readiness(
            db,
            current_user,
            investigation_id,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.get(
    "/investigations/{investigation_id}/bookmarks",
    response_model=EvidenceBookmarkListResponse,
)
async def list_bookmarks_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvidenceBookmarkListResponse:
    try:
        bookmarks = await list_bookmarks(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    return EvidenceBookmarkListResponse(
        total=len(bookmarks),
        items=[bookmark_response(item) for item in bookmarks],
    )


@router.post(
    "/investigations/{investigation_id}/bookmarks",
    response_model=EvidenceBookmarkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_bookmark_endpoint(
    investigation_id: uuid.UUID,
    body: EvidenceBookmarkCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvidenceBookmarkResponse:
    try:
        bookmark = await create_bookmark(db, current_user, investigation_id, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except BookmarkAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProductivityValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return bookmark_response(bookmark)


@router.delete(
    "/bookmarks/{bookmark_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_bookmark_endpoint(
    bookmark_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_bookmark(db, current_user, bookmark_id)
    except (ProductivityItemNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Bookmark not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/tags", response_model=InvestigationTagListResponse)
async def list_tags_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationTagListResponse:
    del current_user
    tags = await list_tags(db)
    return InvestigationTagListResponse(
        total=len(tags),
        items=[InvestigationTagResponse.model_validate(tag) for tag in tags],
    )


@router.post(
    "/tags",
    response_model=InvestigationTagResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tag_endpoint(
    body: InvestigationTagCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationTagResponse:
    try:
        tag = await create_tag(db, current_user, body)
    except ProductivityValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return InvestigationTagResponse.model_validate(tag)


@router.get(
    "/investigations/{investigation_id}/tags",
    response_model=InvestigationTagListResponse,
)
async def get_investigation_tags_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationTagListResponse:
    try:
        tags = await get_investigation_tags(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    return InvestigationTagListResponse(
        total=len(tags),
        items=[InvestigationTagResponse.model_validate(tag) for tag in tags],
    )


@router.patch(
    "/investigations/{investigation_id}/tags",
    response_model=InvestigationTagListResponse,
)
async def update_investigation_tags_endpoint(
    investigation_id: uuid.UUID,
    body: InvestigationTagsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationTagListResponse:
    try:
        tags = await update_investigation_tags(
            db,
            current_user,
            investigation_id,
            body,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ProductivityValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return InvestigationTagListResponse(
        total=len(tags),
        items=[InvestigationTagResponse.model_validate(tag) for tag in tags],
    )


@router.patch(
    "/investigations/{investigation_id}/priority",
    response_model=InvestigationPriorityResponse,
)
async def update_investigation_priority_endpoint(
    investigation_id: uuid.UUID,
    body: InvestigationPriorityUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationPriorityResponse:
    try:
        return await update_investigation_priority(
            db,
            current_user,
            investigation_id,
            body,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post(
    "/investigations/{investigation_id}/summary",
    response_model=InvestigationSummaryResponse,
)
async def generate_investigation_summary_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationSummaryResponse:
    try:
        return await generate_investigation_summary(
            db,
            current_user,
            investigation_id,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
