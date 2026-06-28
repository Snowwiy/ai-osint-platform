from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.case_closure import (
    CaseClosureChecklistItemResponse,
    CaseClosureChecklistUpdate,
    CaseClosureCloseRequest,
    CaseClosureResponse,
    CaseClosureSubmitRequest,
    CaseClosureUpdate,
    CaseDeliverableCreate,
    CaseDeliverableListResponse,
    CaseDeliverableResponse,
    CaseDeliverableUpdate,
    CasePackageManifestResponse,
)
from app.services.case_closure import (
    CaseClosureNotFoundError,
    CaseClosureValidationError,
    CaseDeliverableNotFoundError,
    approve_case_closure,
    archive_case_deliverable,
    close_case_closure,
    create_case_deliverable,
    create_case_package_manifest,
    generate_closure_checklist,
    get_case_closure,
    get_closure_checklist,
    list_case_deliverables,
    reopen_case_closure,
    submit_case_closure_review,
    update_case_closure,
    update_case_deliverable,
    update_closure_checklist_item,
)
from app.services.investigation import ForbiddenError, InvestigationNotFoundError

router = APIRouter(tags=["case-closure"])


@router.get(
    "/investigations/{investigation_id}/closure",
    response_model=CaseClosureResponse,
)
async def get_case_closure_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseClosureResponse:
    try:
        return await get_case_closure(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.post(
    "/investigations/{investigation_id}/closure/generate-checklist",
    response_model=CaseClosureResponse,
)
async def generate_closure_checklist_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseClosureResponse:
    try:
        return await generate_closure_checklist(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.patch(
    "/investigations/{investigation_id}/closure",
    response_model=CaseClosureResponse,
)
async def update_case_closure_endpoint(
    investigation_id: uuid.UUID,
    body: CaseClosureUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseClosureResponse:
    try:
        return await update_case_closure(db, current_user, investigation_id, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post(
    "/investigations/{investigation_id}/closure/submit-review",
    response_model=CaseClosureResponse,
)
async def submit_case_closure_review_endpoint(
    investigation_id: uuid.UUID,
    body: CaseClosureSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseClosureResponse:
    try:
        return await submit_case_closure_review(
            db,
            current_user,
            investigation_id,
            body,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CaseClosureValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/investigations/{investigation_id}/closure/approve",
    response_model=CaseClosureResponse,
)
async def approve_case_closure_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseClosureResponse:
    try:
        return await approve_case_closure(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CaseClosureValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/investigations/{investigation_id}/closure/close",
    response_model=CaseClosureResponse,
)
async def close_case_closure_endpoint(
    investigation_id: uuid.UUID,
    body: CaseClosureCloseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseClosureResponse:
    try:
        return await close_case_closure(db, current_user, investigation_id, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CaseClosureValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/investigations/{investigation_id}/closure/reopen",
    response_model=CaseClosureResponse,
)
async def reopen_case_closure_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseClosureResponse:
    try:
        return await reopen_case_closure(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CaseClosureValidationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/investigations/{investigation_id}/closure/checklist",
    response_model=list[CaseClosureChecklistItemResponse],
)
async def get_closure_checklist_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CaseClosureChecklistItemResponse]:
    try:
        return await get_closure_checklist(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.patch(
    "/investigations/{investigation_id}/closure/checklist/{item_id}",
    response_model=CaseClosureChecklistItemResponse,
)
async def update_closure_checklist_item_endpoint(
    investigation_id: uuid.UUID,
    item_id: uuid.UUID,
    body: CaseClosureChecklistUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseClosureChecklistItemResponse:
    try:
        return await update_closure_checklist_item(
            db,
            current_user,
            investigation_id,
            item_id,
            body,
        )
    except (InvestigationNotFoundError, CaseClosureNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get(
    "/investigations/{investigation_id}/deliverables",
    response_model=CaseDeliverableListResponse,
)
async def list_case_deliverables_endpoint(
    investigation_id: uuid.UUID,
    include_archived: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseDeliverableListResponse:
    try:
        return await list_case_deliverables(
            db,
            current_user,
            investigation_id,
            include_archived=include_archived,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc


@router.post(
    "/investigations/{investigation_id}/deliverables",
    response_model=CaseDeliverableResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_case_deliverable_endpoint(
    investigation_id: uuid.UUID,
    body: CaseDeliverableCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseDeliverableResponse:
    try:
        return await create_case_deliverable(db, current_user, investigation_id, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CaseClosureValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch(
    "/investigations/{investigation_id}/deliverables/{deliverable_id}",
    response_model=CaseDeliverableResponse,
)
async def update_case_deliverable_endpoint(
    investigation_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    body: CaseDeliverableUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseDeliverableResponse:
    try:
        return await update_case_deliverable(
            db,
            current_user,
            investigation_id,
            deliverable_id,
            body,
        )
    except (InvestigationNotFoundError, CaseDeliverableNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CaseClosureValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete(
    "/investigations/{investigation_id}/deliverables/{deliverable_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def archive_case_deliverable_endpoint(
    investigation_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await archive_case_deliverable(
            db,
            current_user,
            investigation_id,
            deliverable_id,
        )
    except (InvestigationNotFoundError, CaseDeliverableNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post(
    "/investigations/{investigation_id}/deliverables/package",
    response_model=CasePackageManifestResponse,
)
async def create_case_package_manifest_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CasePackageManifestResponse:
    try:
        return await create_case_package_manifest(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
