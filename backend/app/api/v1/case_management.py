from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.investigation_note import InvestigationNote
from app.models.user import User
from app.schemas.case_management import (
    InvestigationEvidenceCreate,
    InvestigationEvidenceListResponse,
    InvestigationEvidenceReviewUpdate,
    InvestigationEvidenceResponse,
    InvestigationEvidenceUpdate,
    InvestigationNoteCreate,
    InvestigationNoteListResponse,
    InvestigationNoteResponse,
    InvestigationNoteUpdate,
    InvestigationTaskCreate,
    InvestigationTaskListResponse,
    InvestigationTaskResponse,
    InvestigationTaskStatusUpdate,
    InvestigationTaskUpdate,
    NoteType,
)
from app.services.audit import record_event
from app.services.case_management import (
    CaseItemNotFoundError,
    CaseItemValidationError,
    create_evidence,
    create_note,
    create_task,
    create_task_global,
    delete_evidence,
    delete_note,
    delete_task,
    list_evidence,
    list_notes,
    list_tasks,
    update_evidence,
    update_note,
    update_task,
    update_task_global,
    update_task_status_global,
    review_evidence_by_id,
)
from app.services.investigation import ForbiddenError, InvestigationNotFoundError

router = APIRouter(tags=["case-management"])


@router.get(
    "/investigations/{investigation_id}/notes",
    response_model=InvestigationNoteListResponse,
)
async def list_notes_endpoint(
    investigation_id: uuid.UUID,
    include_archived: bool = Query(default=False),
    note_type: NoteType | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationNoteListResponse:
    try:
        notes = await list_notes(
            db,
            current_user,
            investigation_id,
            include_archived=include_archived,
            note_type=note_type,
            search=search,
        )
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return InvestigationNoteListResponse(
        total=len(notes),
        items=[InvestigationNoteResponse.model_validate(note) for note in notes],
    )


@router.post(
    "/investigations/{investigation_id}/notes",
    response_model=InvestigationNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_note_endpoint(
    investigation_id: uuid.UUID,
    body: InvestigationNoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationNoteResponse:
    try:
        note = await create_note(db, current_user, investigation_id, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    response = InvestigationNoteResponse.model_validate(note)
    return response.model_copy(update={"note_type": body.note_type})


@router.patch(
    "/investigations/{investigation_id}/notes/{note_id}",
    response_model=InvestigationNoteResponse,
)
async def update_note_endpoint(
    investigation_id: uuid.UUID,
    note_id: uuid.UUID,
    body: InvestigationNoteUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationNoteResponse:
    try:
        note = await update_note(db, current_user, investigation_id, note_id, body)
    except (InvestigationNotFoundError, CaseItemNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Note not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    response = InvestigationNoteResponse.model_validate(note)
    if body.note_type is not None:
        return response.model_copy(update={"note_type": body.note_type})
    return response


@router.delete(
    "/investigations/{investigation_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_note_endpoint(
    investigation_id: uuid.UUID,
    note_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_note(db, current_user, investigation_id, note_id)
    except (InvestigationNotFoundError, CaseItemNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Note not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.patch("/notes/{note_id}", response_model=InvestigationNoteResponse)
async def update_note_by_id_endpoint(
    note_id: uuid.UUID,
    body: InvestigationNoteUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationNoteResponse:
    note = await db.get(InvestigationNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return await update_note_endpoint(
        note.investigation_id,
        note_id,
        body,
        current_user,
        db,
    )


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_note_by_id_endpoint(
    note_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    note = await db.get(InvestigationNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    await delete_note_endpoint(
        note.investigation_id,
        note_id,
        current_user,
        db,
    )


@router.get(
    "/investigations/{investigation_id}/tasks",
    response_model=InvestigationTaskListResponse,
)
async def list_tasks_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationTaskListResponse:
    try:
        tasks = await list_tasks(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return InvestigationTaskListResponse(
        total=len(tasks),
        items=[InvestigationTaskResponse.model_validate(task) for task in tasks],
    )


@router.post(
    "/tasks",
    response_model=InvestigationTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task_global_endpoint(
    body: InvestigationTaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationTaskResponse:
    try:
        task = await create_task_global(db, current_user, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except CaseItemValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return InvestigationTaskResponse.model_validate(task)


@router.patch("/tasks/{task_id}", response_model=InvestigationTaskResponse)
async def update_task_global_endpoint(
    task_id: uuid.UUID,
    body: InvestigationTaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationTaskResponse:
    try:
        task = await update_task_global(db, current_user, task_id, body)
    except (InvestigationNotFoundError, CaseItemNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    except CaseItemValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return InvestigationTaskResponse.model_validate(task)


@router.patch("/tasks/{task_id}/status", response_model=InvestigationTaskResponse)
async def update_task_status_global_endpoint(
    task_id: uuid.UUID,
    body: InvestigationTaskStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationTaskResponse:
    try:
        task = await update_task_status_global(db, current_user, task_id, body)
    except (InvestigationNotFoundError, CaseItemNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return InvestigationTaskResponse.model_validate(task)


@router.post(
    "/investigations/{investigation_id}/tasks",
    response_model=InvestigationTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task_endpoint(
    investigation_id: uuid.UUID,
    body: InvestigationTaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationTaskResponse:
    try:
        task = await create_task(db, current_user, investigation_id, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except CaseItemValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return InvestigationTaskResponse.model_validate(task)


@router.patch(
    "/investigations/{investigation_id}/tasks/{task_id}",
    response_model=InvestigationTaskResponse,
)
async def update_task_endpoint(
    investigation_id: uuid.UUID,
    task_id: uuid.UUID,
    body: InvestigationTaskUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationTaskResponse:
    try:
        task = await update_task(db, current_user, investigation_id, task_id, body)
    except (InvestigationNotFoundError, CaseItemNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    except CaseItemValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if body.status == "completed":
        await record_event(
            db,
            action="task.completed",
            actor_id=current_user.id,
            resource_type="task",
            resource_id=task_id,
            investigation_id=investigation_id,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            metadata={"status": body.status},
        )
    return InvestigationTaskResponse.model_validate(task)


@router.delete(
    "/investigations/{investigation_id}/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_task_endpoint(
    investigation_id: uuid.UUID,
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_task(db, current_user, investigation_id, task_id)
    except (InvestigationNotFoundError, CaseItemNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get(
    "/investigations/{investigation_id}/evidence",
    response_model=InvestigationEvidenceListResponse,
)
async def list_evidence_endpoint(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationEvidenceListResponse:
    try:
        evidence = await list_evidence(db, current_user, investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    return InvestigationEvidenceListResponse(
        total=len(evidence),
        items=[
            InvestigationEvidenceResponse.model_validate(item) for item in evidence
        ],
    )


@router.post(
    "/investigations/{investigation_id}/evidence",
    response_model=InvestigationEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_evidence_endpoint(
    investigation_id: uuid.UUID,
    body: InvestigationEvidenceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationEvidenceResponse:
    try:
        evidence = await create_evidence(db, current_user, investigation_id, body)
    except InvestigationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Investigation not found") from exc
    except CaseItemValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return InvestigationEvidenceResponse.model_validate(evidence)


@router.patch(
    "/investigations/{investigation_id}/evidence/{evidence_id}",
    response_model=InvestigationEvidenceResponse,
)
async def update_evidence_endpoint(
    investigation_id: uuid.UUID,
    evidence_id: uuid.UUID,
    body: InvestigationEvidenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationEvidenceResponse:
    try:
        evidence = await update_evidence(
            db,
            current_user,
            investigation_id,
            evidence_id,
            body,
        )
    except (InvestigationNotFoundError, CaseItemNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Evidence not found") from exc
    except CaseItemValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return InvestigationEvidenceResponse.model_validate(evidence)


@router.patch(
    "/evidence/{evidence_id}/review",
    response_model=InvestigationEvidenceResponse,
)
async def review_evidence_endpoint(
    evidence_id: uuid.UUID,
    body: InvestigationEvidenceReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvestigationEvidenceResponse:
    try:
        evidence = await review_evidence_by_id(db, current_user, evidence_id, body)
    except (InvestigationNotFoundError, CaseItemNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Evidence not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return InvestigationEvidenceResponse.model_validate(evidence)


@router.delete(
    "/investigations/{investigation_id}/evidence/{evidence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_evidence_endpoint(
    investigation_id: uuid.UUID,
    evidence_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await delete_evidence(db, current_user, investigation_id, evidence_id)
    except (InvestigationNotFoundError, CaseItemNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Evidence not found") from exc
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
