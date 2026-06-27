from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_feature
from app.models.user import User
from app.schemas.collaboration import (
    CollaborationDashboardResponse,
    EscalationCreate,
    EscalationResponse,
    InvestigationHandoffCreate,
    InvestigationHandoffResponse,
    InvestigationOwnershipResponse,
    InvestigationOwnershipUpdate,
)
from app.services.collaboration import (
    CollaborationValidationError,
    create_escalation,
    create_handoff,
    get_collaboration_dashboard,
    get_ownership,
    list_escalations,
    update_ownership,
)
from app.services.investigation import (
    ForbiddenError,
    InvestigationNotFoundError,
    MemberValidationError,
)

router = APIRouter(
    tags=["collaboration"],
    dependencies=[Depends(require_feature("enable_collaboration"))],
)


@router.get(
    "/investigations/{investigation_id}/ownership",
    response_model=InvestigationOwnershipResponse,
)
async def get_ownership_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationOwnershipResponse:
    try:
        return await get_ownership(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch(
    "/investigations/{investigation_id}/ownership",
    response_model=InvestigationOwnershipResponse,
)
async def update_ownership_endpoint(
    investigation_id: uuid.UUID,
    body: InvestigationOwnershipUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationOwnershipResponse:
    try:
        return await update_ownership(db, current_user, investigation_id, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (MemberValidationError, CollaborationValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/investigations/{investigation_id}/handoff",
    response_model=InvestigationHandoffResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_handoff_endpoint(
    investigation_id: uuid.UUID,
    body: InvestigationHandoffCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationHandoffResponse:
    try:
        handoff = await create_handoff(db, current_user, investigation_id, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (MemberValidationError, CollaborationValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return InvestigationHandoffResponse.model_validate(handoff)


@router.post(
    "/investigations/{investigation_id}/escalate",
    response_model=EscalationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_escalation_endpoint(
    investigation_id: uuid.UUID,
    body: EscalationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EscalationResponse:
    try:
        escalation = await create_escalation(
            db,
            current_user,
            investigation_id,
            body,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return EscalationResponse.model_validate(escalation)


@router.get(
    "/investigations/{investigation_id}/escalations",
    response_model=list[EscalationResponse],
)
async def list_escalations_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EscalationResponse]:
    try:
        items = await list_escalations(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [EscalationResponse.model_validate(item) for item in items]


@router.get(
    "/dashboard/collaboration",
    response_model=CollaborationDashboardResponse,
)
async def collaboration_dashboard_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CollaborationDashboardResponse:
    return await get_collaboration_dashboard(db, current_user)
