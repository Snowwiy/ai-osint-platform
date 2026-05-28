from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.investigation import Investigation
from app.models.investigation_member import InvestigationMember
from app.models.user import User
from app.schemas.investigation import (
    InvestigationCreate,
    InvestigationGraphResponse,
    InvestigationListResponse,
    InvestigationResponse,
    InvestigationUpdate,
    MemberAddRequest,
    MemberResponse,
    MemberUpdateRequest,
)
from app.schemas.recon import EntityType, RelationshipType
from app.services.investigation import (
    ForbiddenError,
    InvestigationNotFoundError,
    LastOwnerError,
    MemberAlreadyExistsError,
    add_member,
    archive_investigation,
    create_investigation,
    get_investigation,
    get_investigation_graph,
    list_investigations,
    list_members,
    remove_member,
    update_investigation,
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
    return await create_investigation(db, current_user, body)


@router.get("/", response_model=InvestigationListResponse)
async def list_endpoint(
    status_filter: str | None = Query(default=None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    total, items = await list_investigations(
        db,
        current_user,
        status=status_filter,
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


@router.get("/{investigation_id}/members", response_model=list[MemberResponse])
async def list_members_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[InvestigationMember]:
    try:
        return await list_members(db, current_user, investigation_id)
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
) -> InvestigationMember:
    try:
        return await add_member(
            db,
            current_user,
            investigation_id,
            body.user_id,
            body.role,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except MemberAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put(
    "/{investigation_id}/members/{user_id}",
    response_model=MemberResponse,
)
async def update_member_endpoint(
    investigation_id: uuid.UUID,
    user_id: uuid.UUID,
    body: MemberUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationMember:
    try:
        return await update_member_role(
            db,
            current_user,
            investigation_id,
            user_id,
            body.role,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LastOwnerError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete(
    "/{investigation_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member_endpoint(
    investigation_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await remove_member(db, current_user, investigation_id, user_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LastOwnerError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
