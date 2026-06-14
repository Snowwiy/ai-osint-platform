from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.playbook import (
    DefensivePlaybookResponse,
    FindingPlaybookRecommendation,
    FindingRemediationResponse,
    FindingRemediationUpdate,
    PlaybookRunResponse,
    PlaybookRunStepUpdate,
    PlaybookRunUpdate,
)
from app.services.investigation import (
    ForbiddenError,
    InvestigationNotFoundError,
    MemberValidationError,
)
from app.services.playbook import (
    PlaybookNotFoundError,
    PlaybookValidationError,
    get_playbook,
    get_playbook_run,
    list_playbook_runs,
    list_playbooks,
    recommended_playbooks_for_finding,
    start_playbook_run,
    update_finding_remediation,
    update_playbook_run,
    update_playbook_run_step,
)

router = APIRouter(tags=["playbooks"])


@router.get("/playbooks", response_model=list[DefensivePlaybookResponse])
async def list_playbooks_endpoint(
    active_only: bool = Query(default=True),
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DefensivePlaybookResponse]:
    return await list_playbooks(db, active_only=active_only)


@router.get("/playbooks/{playbook_id}", response_model=DefensivePlaybookResponse)
async def get_playbook_endpoint(
    playbook_id: uuid.UUID,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DefensivePlaybookResponse:
    try:
        return await get_playbook(db, playbook_id)
    except PlaybookNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/findings/{finding_id}/playbooks",
    response_model=list[FindingPlaybookRecommendation],
)
async def finding_playbooks_endpoint(
    finding_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FindingPlaybookRecommendation]:
    try:
        return await recommended_playbooks_for_finding(db, current_user, finding_id)
    except (PlaybookNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Finding not found") from exc


@router.post(
    "/findings/{finding_id}/playbooks/{playbook_id}/start",
    response_model=PlaybookRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_playbook_endpoint(
    finding_id: uuid.UUID,
    playbook_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlaybookRunResponse:
    try:
        return await start_playbook_run(
            db,
            current_user,
            finding_id,
            playbook_id,
        )
    except (PlaybookNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get(
    "/investigations/{investigation_id}/playbook-runs",
    response_model=list[PlaybookRunResponse],
)
async def list_playbook_runs_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlaybookRunResponse]:
    try:
        return await list_playbook_runs(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.get("/playbook-runs/{run_id}", response_model=PlaybookRunResponse)
async def get_playbook_run_endpoint(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlaybookRunResponse:
    try:
        return await get_playbook_run(db, current_user, run_id)
    except (PlaybookNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Playbook run not found") from exc


@router.patch("/playbook-runs/{run_id}", response_model=PlaybookRunResponse)
async def update_playbook_run_endpoint(
    run_id: uuid.UUID,
    body: PlaybookRunUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlaybookRunResponse:
    try:
        return await update_playbook_run(db, current_user, run_id, body)
    except (PlaybookNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Playbook run not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except PlaybookValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch(
    "/playbook-runs/{run_id}/steps/{step_id}",
    response_model=PlaybookRunResponse,
)
async def update_playbook_step_endpoint(
    run_id: uuid.UUID,
    step_id: uuid.UUID,
    body: PlaybookRunStepUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlaybookRunResponse:
    try:
        return await update_playbook_run_step(
            db,
            current_user,
            run_id,
            step_id,
            body,
        )
    except (PlaybookNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except PlaybookValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch(
    "/findings/{finding_id}/remediation",
    response_model=FindingRemediationResponse,
)
async def update_remediation_endpoint(
    finding_id: uuid.UUID,
    body: FindingRemediationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FindingRemediationResponse:
    try:
        return await update_finding_remediation(db, current_user, finding_id, body)
    except (PlaybookNotFoundError, InvestigationNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Finding not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except MemberValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PlaybookValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
