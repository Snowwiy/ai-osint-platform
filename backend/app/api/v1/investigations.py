from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.investigation import Investigation
from app.models.user import User
from app.schemas.case_management import WorkflowTransitionRequest
from app.schemas.investigation import (
    InvestigationCreate,
    InvestigationGraphResponse,
    InvestigationListScope,
    InvestigationListResponse,
    InvestigationPurgeImpactResponse,
    InvestigationResponse,
    InvestigationStageUpdate,
    InvestigationUpdate,
    MemberAddRequest,
    MemberResponse,
    MemberUpdateRequest,
)
from app.schemas.recon import EntityType, RelationshipType
from app.services.investigation import (
    ForbiddenError,
    EngagementLinkNotFoundError,
    EngagementStateConflictError,
    InvestigationNotFoundError,
    InvestigationPurgeConflictError,
    InvalidWorkflowTransitionError,
    InvalidStageTransitionError,
    LastOwnerError,
    MemberAlreadyExistsError,
    MemberValidationError,
    add_member,
    archive_investigation,
    create_investigation,
    get_investigation,
    get_investigation_graph,
    get_investigation_purge_impact,
    list_investigations,
    list_member_responses,
    remove_member,
    purge_archived_investigation,
    update_investigation,
    update_investigation_status,
    update_investigation_stage,
    update_member_role,
)

router = APIRouter(prefix="/investigations", tags=["investigations"])


@router.post(
    "/",
    response_model=InvestigationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_endpoint(
    body: InvestigationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Investigation:
    try:
        return await create_investigation(db, current_user, body)
    except EngagementLinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Engagement not found") from exc
    except EngagementStateConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/", response_model=InvestigationListResponse)
async def list_endpoint(
    status_filter: str | None = Query(default=None, alias="status"),
    scope: InvestigationListScope = Query(default="all"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    total, items = await list_investigations(
        db,
        current_user,
        status=status_filter,
        scope=scope,
        skip=skip,
        limit=limit,
    )
    return {"total": total, "items": items}


@router.get("/{investigation_id}", response_model=InvestigationResponse)
async def get_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Investigation:
    try:
        return await get_investigation(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        ) from exc


@router.get("/{investigation_id}/graph", response_model=InvestigationGraphResponse)
async def get_graph_endpoint(
    investigation_id: uuid.UUID,
    entity_types: list[EntityType] | None = Query(default=None, alias="entity_type"),
    relationship_types: list[RelationshipType] | None = Query(
        default=None,
        alias="relationship_type",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationGraphResponse:
    try:
        return await get_investigation_graph(
            db,
            current_user,
            investigation_id,
            entity_types=entity_types,
            relationship_types=relationship_types,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        ) from exc


@router.put("/{investigation_id}", response_model=InvestigationResponse)
async def update_endpoint(
    investigation_id: uuid.UUID,
    body: InvestigationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Investigation:
    try:
        return await update_investigation(db, current_user, investigation_id, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except InvalidWorkflowTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except MemberValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EngagementLinkNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Engagement not found") from exc
    except EngagementStateConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/{investigation_id}/status", response_model=InvestigationResponse)
@router.patch("/{investigation_id}/state", response_model=InvestigationResponse)
async def update_status_endpoint(
    investigation_id: uuid.UUID,
    body: WorkflowTransitionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Investigation:
    try:
        return await update_investigation_status(
            db,
            current_user,
            investigation_id,
            body.status,
            reason=body.reason,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except InvalidWorkflowTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/{investigation_id}/stage", response_model=InvestigationResponse)
async def update_stage_endpoint(
    investigation_id: uuid.UUID,
    body: InvestigationStageUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Investigation:
    try:
        return await update_investigation_stage(
            db,
            current_user,
            investigation_id,
            body.stage,
            reason=body.reason,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except InvalidStageTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete(
    "/{investigation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await archive_investigation(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get(
    "/{investigation_id}/purge-impact",
    response_model=InvestigationPurgeImpactResponse,
)
async def purge_impact_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationPurgeImpactResponse:
    try:
        return await get_investigation_purge_impact(
            db,
            current_user,
            investigation_id,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.delete(
    "/{investigation_id}/purge",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def purge_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await purge_archived_investigation(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except InvestigationPurgeConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{investigation_id}/members", response_model=list[MemberResponse])
async def list_members_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MemberResponse]:
    try:
        return await list_member_responses(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.post(
    "/{investigation_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member_endpoint(
    investigation_id: uuid.UUID,
    body: MemberAddRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemberResponse:
    try:
        return await add_member(
            db,
            current_user,
            investigation_id,
            body.user_id,
            body.role,
            email=body.email,
            username=body.username,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except MemberAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except MemberValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch(
    "/{investigation_id}/members/{member_id}",
    response_model=MemberResponse,
)
@router.put(
    "/{investigation_id}/members/{member_id}",
    response_model=MemberResponse,
)
async def update_member_endpoint(
    investigation_id: uuid.UUID,
    member_id: uuid.UUID,
    body: MemberUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemberResponse:
    try:
        return await update_member_role(
            db,
            current_user,
            investigation_id,
            member_id,
            body.role,
            transfer_ownership=body.transfer_ownership,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LastOwnerError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except MemberValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/{investigation_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member_endpoint(
    investigation_id: uuid.UUID,
    member_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await remove_member(db, current_user, investigation_id, member_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LastOwnerError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
