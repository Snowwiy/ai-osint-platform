from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.engagement import AuthorizationEvidence, EngagementScopeItem
from app.models.user import User
from app.schemas.engagement import (
    AuthorizationEvidenceCreate,
    AuthorizationEvidenceResponse,
    AuthorizationEvidenceUpdate,
    EngagementCreate,
    EngagementListResponse,
    EngagementResponse,
    EngagementUpdate,
    ScopeCheckRequest,
    ScopeCheckResponse,
    ScopeItemCreate,
    ScopeItemResponse,
    ScopeItemUpdate,
)
from app.services.engagement import (
    EngagementConflictError,
    EngagementForbiddenError,
    EngagementNotFoundError,
    archive_engagement,
    check_scope_value,
    create_authorization_evidence,
    create_engagement,
    create_scope_item,
    delete_authorization_evidence,
    delete_scope_item,
    get_engagement_response,
    list_authorization_evidence,
    list_engagements,
    list_scope_items,
    update_authorization_evidence,
    update_engagement,
    update_scope_item,
)

router = APIRouter(prefix="/engagements", tags=["engagements"])


@router.get("/", response_model=EngagementListResponse)
async def list_engagements_endpoint(
    include_archived: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EngagementListResponse:
    total, items = await list_engagements(
        db,
        current_user,
        include_archived=include_archived,
        skip=skip,
        limit=limit,
    )
    return EngagementListResponse(total=total, items=items)


@router.post(
    "/",
    response_model=EngagementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_engagement_endpoint(
    body: EngagementCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EngagementResponse:
    try:
        return await create_engagement(db, current_user, body)
    except EngagementForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/{engagement_id}", response_model=EngagementResponse)
async def get_engagement_endpoint(
    engagement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EngagementResponse:
    try:
        return await get_engagement_response(db, current_user, engagement_id)
    except EngagementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Engagement not found") from exc


@router.patch("/{engagement_id}", response_model=EngagementResponse)
async def update_engagement_endpoint(
    engagement_id: uuid.UUID,
    body: EngagementUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EngagementResponse:
    try:
        return await update_engagement(db, current_user, engagement_id, body)
    except EngagementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Engagement not found") from exc
    except EngagementForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{engagement_id}/archive", response_model=EngagementResponse)
async def archive_engagement_endpoint(
    engagement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EngagementResponse:
    try:
        return await archive_engagement(db, current_user, engagement_id)
    except EngagementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Engagement not found") from exc
    except EngagementForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/{engagement_id}/scope", response_model=list[ScopeItemResponse])
async def list_scope_endpoint(
    engagement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EngagementScopeItem]:
    try:
        return await list_scope_items(db, current_user, engagement_id)
    except EngagementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Engagement not found") from exc


@router.post(
    "/{engagement_id}/scope",
    response_model=ScopeItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_scope_endpoint(
    engagement_id: uuid.UUID,
    body: ScopeItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EngagementScopeItem:
    try:
        return await create_scope_item(db, current_user, engagement_id, body)
    except EngagementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Engagement not found") from exc
    except EngagementForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except EngagementConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch(
    "/{engagement_id}/scope/{scope_item_id}",
    response_model=ScopeItemResponse,
)
async def update_scope_endpoint(
    engagement_id: uuid.UUID,
    scope_item_id: uuid.UUID,
    body: ScopeItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EngagementScopeItem:
    try:
        return await update_scope_item(
            db,
            current_user,
            engagement_id,
            scope_item_id,
            body,
        )
    except EngagementNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EngagementForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except EngagementConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete(
    "/{engagement_id}/scope/{scope_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_scope_endpoint(
    engagement_id: uuid.UUID,
    scope_item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_scope_item(db, current_user, engagement_id, scope_item_id)
    except EngagementNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EngagementForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get(
    "/{engagement_id}/authorization",
    response_model=list[AuthorizationEvidenceResponse],
)
async def list_authorization_endpoint(
    engagement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AuthorizationEvidence]:
    try:
        return await list_authorization_evidence(db, current_user, engagement_id)
    except EngagementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Engagement not found") from exc


@router.post(
    "/{engagement_id}/authorization",
    response_model=AuthorizationEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_authorization_endpoint(
    engagement_id: uuid.UUID,
    body: AuthorizationEvidenceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuthorizationEvidence:
    try:
        return await create_authorization_evidence(
            db,
            current_user,
            engagement_id,
            body,
        )
    except EngagementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Engagement not found") from exc
    except EngagementForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.patch(
    "/{engagement_id}/authorization/{evidence_id}",
    response_model=AuthorizationEvidenceResponse,
)
async def update_authorization_endpoint(
    engagement_id: uuid.UUID,
    evidence_id: uuid.UUID,
    body: AuthorizationEvidenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuthorizationEvidence:
    try:
        return await update_authorization_evidence(
            db,
            current_user,
            engagement_id,
            evidence_id,
            body,
        )
    except EngagementNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EngagementForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.delete(
    "/{engagement_id}/authorization/{evidence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_authorization_endpoint(
    engagement_id: uuid.UUID,
    evidence_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_authorization_evidence(
            db,
            current_user,
            engagement_id,
            evidence_id,
        )
    except EngagementNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EngagementForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/{engagement_id}/scope/check", response_model=ScopeCheckResponse)
async def check_scope_endpoint(
    engagement_id: uuid.UUID,
    body: ScopeCheckRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScopeCheckResponse:
    try:
        return await check_scope_value(
            db,
            current_user,
            engagement_id,
            value=body.value,
            scope_type=body.scope_type,
        )
    except EngagementNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Engagement not found") from exc
