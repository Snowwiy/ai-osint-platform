from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding import Finding
from app.models.investigation_evidence import InvestigationEvidence
from app.models.investigation_note import InvestigationNote
from app.models.investigation_task import InvestigationTask
from app.models.user import User
from app.schemas.case_management import (
    InvestigationEvidenceCreate,
    InvestigationEvidenceReviewUpdate,
    InvestigationEvidenceUpdate,
    InvestigationNoteCreate,
    InvestigationNoteUpdate,
    InvestigationTaskCreate,
    InvestigationTaskStatusUpdate,
    InvestigationTaskUpdate,
)
from app.services.audit import record_event
from app.services.investigation import (
    CASE_ADMIN_ROLES,
    MUTATION_ROLES,
    ForbiddenError,
    MemberValidationError,
    ensure_investigation_permission,
    ensure_user_is_member,
    get_investigation,
)


class CaseItemNotFoundError(Exception):
    pass


class CaseItemValidationError(Exception):
    pass


async def list_notes(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    *,
    include_archived: bool = False,
    note_type: str | None = None,
    search: str | None = None,
) -> list[InvestigationNote]:
    await get_investigation(db, user, investigation_id)
    stmt = select(InvestigationNote).where(
        InvestigationNote.investigation_id == investigation_id
    )
    if not include_archived:
        stmt = stmt.where(InvestigationNote.archived.is_(False))
    if note_type:
        stmt = stmt.where(InvestigationNote.note_type == note_type)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                InvestigationNote.title.ilike(pattern),
                InvestigationNote.content.ilike(pattern),
            )
        )
    result = await db.execute(
        stmt.order_by(
            InvestigationNote.pinned.desc(),
            InvestigationNote.updated_at.desc(),
        )
    )
    return list(result.scalars().all())


async def create_note(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    data: InvestigationNoteCreate,
) -> InvestigationNote:
    await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot create notes",
    )
    note = InvestigationNote(
        investigation_id=investigation_id,
        created_by=user.id,
        updated_by=user.id,
        title=_sanitize_text(data.title),
        content=_sanitize_markdown(data.content),
        note_type=data.note_type,
        pinned=data.pinned,
    )
    db.add(note)
    await db.flush()
    await record_event(
        db,
        action="note.created",
        actor_id=user.id,
        resource_type="note",
        resource_id=note.id,
        investigation_id=investigation_id,
        metadata={
            "note_type": note.note_type,
            "pinned": note.pinned,
            "title": note.title,
        },
    )
    await db.refresh(note)
    return note


async def update_note(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    note_id: uuid.UUID,
    data: InvestigationNoteUpdate,
) -> InvestigationNote:
    note = await _get_note(db, user, investigation_id, note_id)
    await _ensure_note_mutation_allowed(db, user, investigation_id, note)
    updates = data.model_dump(exclude_unset=True)
    was_archived = note.archived
    if "title" in updates and updates["title"] is not None:
        note.title = _sanitize_text(str(updates["title"]))
    if "content" in updates and updates["content"] is not None:
        note.content = _sanitize_markdown(str(updates["content"]))
    if "note_type" in updates and updates["note_type"] is not None:
        note.note_type = str(updates["note_type"])
    if "pinned" in updates and updates["pinned"] is not None:
        note.pinned = bool(updates["pinned"])
    if "archived" in updates and updates["archived"] is not None:
        note.archived = bool(updates["archived"])
    note.updated_by = user.id
    db.add(note)
    await db.flush()
    action = "note.archived" if not was_archived and note.archived else "note.updated"
    await record_event(
        db,
        action=action,
        actor_id=user.id,
        resource_type="note",
        resource_id=note.id,
        investigation_id=investigation_id,
        metadata={
            "note_type": note.note_type,
            "pinned": note.pinned,
            "archived": note.archived,
            "title": note.title,
        },
    )
    await db.refresh(note)
    return note


async def delete_note(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    note_id: uuid.UUID,
) -> None:
    note = await _get_note(db, user, investigation_id, note_id)
    await _ensure_note_mutation_allowed(db, user, investigation_id, note)
    if note.archived:
        return
    note.archived = True
    note.updated_by = user.id
    db.add(note)
    await record_event(
        db,
        action="note.archived",
        actor_id=user.id,
        resource_type="note",
        resource_id=note.id,
        investigation_id=investigation_id,
        metadata={"note_type": note.note_type, "title": note.title},
    )


async def list_tasks(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> list[InvestigationTask]:
    await get_investigation(db, user, investigation_id)
    result = await db.execute(
        select(InvestigationTask)
        .where(InvestigationTask.investigation_id == investigation_id)
        .order_by(InvestigationTask.created_at.desc())
    )
    return list(result.scalars().all())


async def create_task(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    data: InvestigationTaskCreate,
) -> InvestigationTask:
    await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot create tasks",
    )
    await _validate_task_links(db, investigation_id, data)
    if data.assigned_to is not None:
        await _ensure_assignment_member(db, investigation_id, data.assigned_to)
    task = InvestigationTask(
        id=uuid.uuid4(),
        investigation_id=investigation_id,
        title=_sanitize_text(data.title),
        description=_sanitize_markdown(data.description)
        if data.description is not None
        else None,
        status=data.status,
        priority=data.priority,
        assigned_to=data.assigned_to,
        due_date=data.due_date,
        remediation_link=data.remediation_link,
        finding_id=data.finding_id,
        evidence_reference_ids=data.evidence_reference_ids,
        created_by=user.id,
        completed_at=_now() if data.status == "completed" else None,
    )
    db.add(task)
    await record_event(
        db,
        action="task.assigned" if task.assigned_to else "task.created",
        actor_id=user.id,
        resource_type="task",
        resource_id=task.id,
        investigation_id=investigation_id,
        metadata={
            "assigned_to": str(task.assigned_to) if task.assigned_to else None,
            "priority": task.priority,
            "status": task.status,
        },
    )
    await db.flush()
    await db.refresh(task)
    return task


async def update_task(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    task_id: uuid.UUID,
    data: InvestigationTaskUpdate,
) -> InvestigationTask:
    task = await _get_task(db, user, investigation_id, task_id)
    await _ensure_task_mutation_allowed(db, user, investigation_id, task)
    updates = data.model_dump(exclude_unset=True)
    evidence_reference_ids = (
        updates.get("evidence_reference_ids", task.evidence_reference_ids) or []
    )
    candidate = _TaskLinks(
        finding_id=updates.get("finding_id", task.finding_id),
        evidence_reference_ids=evidence_reference_ids,
    )
    await _validate_task_links(db, investigation_id, candidate)
    if updates.get("assigned_to") is not None:
        await _ensure_assignment_member(db, investigation_id, updates["assigned_to"])
    if "title" in updates and updates["title"] is not None:
        task.title = _sanitize_text(str(updates["title"]))
    if "description" in updates:
        description = updates["description"]
        task.description = (
            _sanitize_markdown(str(description)) if description is not None else None
        )
    if "status" in updates and updates["status"] is not None:
        task.status = str(updates["status"])
        task.completed_at = _now() if task.status == "completed" else None
    if "priority" in updates and updates["priority"] is not None:
        task.priority = str(updates["priority"])
    if "assigned_to" in updates:
        previous_assignee = task.assigned_to
        task.assigned_to = updates["assigned_to"]
        if previous_assignee != task.assigned_to:
            await record_event(
                db,
                action="task.assigned" if previous_assignee is None else "task.reassigned",
                actor_id=user.id,
                resource_type="task",
                resource_id=task.id,
                investigation_id=investigation_id,
                metadata={
                    "previous_assignee": (
                        str(previous_assignee) if previous_assignee else None
                    ),
                    "assigned_to": str(task.assigned_to) if task.assigned_to else None,
                },
            )
    if "due_date" in updates:
        task.due_date = updates["due_date"]
    if "remediation_link" in updates:
        task.remediation_link = (
            _sanitize_text(str(updates["remediation_link"]))
            if updates["remediation_link"] is not None
            else None
        )
    if "finding_id" in updates:
        task.finding_id = updates["finding_id"]
    if (
        "evidence_reference_ids" in updates
        and updates["evidence_reference_ids"] is not None
    ):
        task.evidence_reference_ids = list(updates["evidence_reference_ids"])
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return task


async def delete_task(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    task_id: uuid.UUID,
) -> None:
    task = await _get_task(db, user, investigation_id, task_id)
    await _ensure_task_delete_allowed(db, user, investigation_id, task)
    await db.delete(task)


async def create_task_global(
    db: AsyncSession,
    user: User,
    data: InvestigationTaskCreate,
) -> InvestigationTask:
    if data.investigation_id is None:
        raise CaseItemValidationError("investigation_id is required")
    return await create_task(db, user, data.investigation_id, data)


async def update_task_global(
    db: AsyncSession,
    user: User,
    task_id: uuid.UUID,
    data: InvestigationTaskUpdate,
) -> InvestigationTask:
    task = await _get_task_by_id(db, user, task_id)
    return await update_task(db, user, task.investigation_id, task_id, data)


async def update_task_status_global(
    db: AsyncSession,
    user: User,
    task_id: uuid.UUID,
    data: InvestigationTaskStatusUpdate,
) -> InvestigationTask:
    task = await _get_task_by_id(db, user, task_id)
    return await update_task(
        db,
        user,
        task.investigation_id,
        task_id,
        InvestigationTaskUpdate(status=data.status),
    )


async def list_evidence(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> list[InvestigationEvidence]:
    await get_investigation(db, user, investigation_id)
    result = await db.execute(
        select(InvestigationEvidence)
        .where(InvestigationEvidence.investigation_id == investigation_id)
        .order_by(InvestigationEvidence.created_at.desc())
    )
    return list(result.scalars().all())


async def create_evidence(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    data: InvestigationEvidenceCreate,
) -> InvestigationEvidence:
    await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot create evidence",
    )
    await _validate_evidence_links(db, investigation_id, data)
    evidence = InvestigationEvidence(
        investigation_id=investigation_id,
        finding_id=data.finding_id,
        note_id=data.note_id,
        task_id=data.task_id,
        title=_sanitize_text(data.title),
        description=_sanitize_markdown(data.description)
        if data.description is not None
        else None,
        evidence_type=data.evidence_type,
        source=_sanitize_text(data.source),
        confidence=data.confidence,
        tags=data.tags,
        analyst_comment=_sanitize_markdown(data.analyst_comment)
        if data.analyst_comment is not None
        else None,
        created_by=user.id,
    )
    db.add(evidence)
    await db.flush()
    await db.refresh(evidence)
    return evidence


async def update_evidence(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    evidence_id: uuid.UUID,
    data: InvestigationEvidenceUpdate,
) -> InvestigationEvidence:
    evidence = await _get_evidence(db, user, investigation_id, evidence_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot update evidence",
    )
    updates = data.model_dump(exclude_unset=True)
    candidate = _EvidenceLinks(
        finding_id=updates.get("finding_id", evidence.finding_id),
        note_id=updates.get("note_id", evidence.note_id),
        task_id=updates.get("task_id", evidence.task_id),
    )
    await _validate_evidence_links(db, investigation_id, candidate)
    if "title" in updates and updates["title"] is not None:
        evidence.title = _sanitize_text(str(updates["title"]))
    if "description" in updates:
        description = updates["description"]
        evidence.description = (
            _sanitize_markdown(str(description)) if description is not None else None
        )
    if "evidence_type" in updates and updates["evidence_type"] is not None:
        evidence.evidence_type = str(updates["evidence_type"])
    if "source" in updates and updates["source"] is not None:
        evidence.source = _sanitize_text(str(updates["source"]))
    if "confidence" in updates and updates["confidence"] is not None:
        evidence.confidence = int(updates["confidence"])
    if "tags" in updates and updates["tags"] is not None:
        evidence.tags = list(updates["tags"])
    if "analyst_comment" in updates:
        comment = updates["analyst_comment"]
        evidence.analyst_comment = (
            _sanitize_markdown(str(comment)) if comment is not None else None
        )
    if "finding_id" in updates:
        evidence.finding_id = updates["finding_id"]
    if "note_id" in updates:
        evidence.note_id = updates["note_id"]
    if "task_id" in updates:
        evidence.task_id = updates["task_id"]
    db.add(evidence)
    await db.flush()
    await db.refresh(evidence)
    return evidence


async def delete_evidence(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    evidence_id: uuid.UUID,
) -> None:
    evidence = await _get_evidence(db, user, investigation_id, evidence_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot archive evidence",
    )
    evidence.review_status = "dismissed"
    evidence.archived_at = _now()
    db.add(evidence)


async def review_evidence_by_id(
    db: AsyncSession,
    user: User,
    evidence_id: uuid.UUID,
    data: InvestigationEvidenceReviewUpdate,
) -> InvestigationEvidence:
    evidence = await _get_evidence_by_id(db, user, evidence_id)
    await ensure_investigation_permission(
        db,
        user,
        evidence.investigation_id,
        MUTATION_ROLES,
        "Viewers cannot review evidence",
    )
    evidence.review_status = data.review_status
    evidence.reviewed_by = user.id
    evidence.reviewed_at = _now()
    if data.analyst_note is not None:
        evidence.analyst_note = _sanitize_markdown(data.analyst_note)
    if data.confidence_score is not None:
        evidence.confidence_score = data.confidence_score
    db.add(evidence)
    await db.flush()
    await db.refresh(evidence)
    return evidence


async def _get_note(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    note_id: uuid.UUID,
) -> InvestigationNote:
    await get_investigation(db, user, investigation_id)
    note = await db.get(InvestigationNote, note_id)
    if note is None or note.investigation_id != investigation_id:
        raise CaseItemNotFoundError("Note not found")
    return note


async def _get_task(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    task_id: uuid.UUID,
) -> InvestigationTask:
    await get_investigation(db, user, investigation_id)
    task = await db.get(InvestigationTask, task_id)
    if task is None or task.investigation_id != investigation_id:
        raise CaseItemNotFoundError("Task not found")
    return task


async def _get_task_by_id(
    db: AsyncSession,
    user: User,
    task_id: uuid.UUID,
) -> InvestigationTask:
    task = await db.get(InvestigationTask, task_id)
    if task is None:
        raise CaseItemNotFoundError("Task not found")
    await get_investigation(db, user, task.investigation_id)
    return task


async def _get_evidence(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    evidence_id: uuid.UUID,
) -> InvestigationEvidence:
    await get_investigation(db, user, investigation_id)
    evidence = await db.get(InvestigationEvidence, evidence_id)
    if evidence is None or evidence.investigation_id != investigation_id:
        raise CaseItemNotFoundError("Evidence not found")
    return evidence


async def _get_evidence_by_id(
    db: AsyncSession,
    user: User,
    evidence_id: uuid.UUID,
) -> InvestigationEvidence:
    evidence = await db.get(InvestigationEvidence, evidence_id)
    if evidence is None:
        raise CaseItemNotFoundError("Evidence not found")
    await get_investigation(db, user, evidence.investigation_id)
    return evidence


async def _ensure_note_mutation_allowed(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    note: InvestigationNote,
) -> None:
    membership = await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot modify notes",
    )
    if user.role == "admin" or membership is None or membership.role in CASE_ADMIN_ROLES:
        return
    if note.created_by != user.id:
        raise ForbiddenError("Analysts can only edit or delete their own notes")


async def _ensure_task_mutation_allowed(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    task: InvestigationTask,
) -> None:
    membership = await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot modify tasks",
    )
    if user.role == "admin" or membership is None or membership.role in CASE_ADMIN_ROLES:
        return
    if task.assigned_to != user.id and task.created_by != user.id:
        raise ForbiddenError("Analysts can only update assigned or created tasks")


async def _ensure_task_delete_allowed(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    task: InvestigationTask,
) -> None:
    membership = await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot delete tasks",
    )
    if user.role == "admin" or membership is None or membership.role in CASE_ADMIN_ROLES:
        return
    if task.created_by != user.id:
        raise ForbiddenError("Analysts can only delete tasks they created")


async def _ensure_assignment_member(
    db: AsyncSession,
    investigation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    try:
        await ensure_user_is_member(
            db,
            investigation_id,
            user_id,
            "Task assignee must be an investigation member",
        )
    except MemberValidationError as exc:
        raise CaseItemValidationError(str(exc)) from exc


class _EvidenceLinks:
    def __init__(
        self,
        *,
        finding_id: uuid.UUID | None,
        note_id: uuid.UUID | None,
        task_id: uuid.UUID | None,
    ) -> None:
        self.finding_id = finding_id
        self.note_id = note_id
        self.task_id = task_id


class _TaskLinks:
    def __init__(
        self,
        *,
        finding_id: uuid.UUID | None,
        evidence_reference_ids: list[uuid.UUID],
    ) -> None:
        self.finding_id = finding_id
        self.evidence_reference_ids = evidence_reference_ids


async def _validate_evidence_links(
    db: AsyncSession,
    investigation_id: uuid.UUID,
    data: InvestigationEvidenceCreate | InvestigationEvidenceUpdate | _EvidenceLinks,
) -> None:
    if data.finding_id is not None:
        finding = await db.get(Finding, data.finding_id)
        if finding is None or finding.investigation_id != investigation_id:
            raise CaseItemValidationError("finding_id is not in this investigation")
    if data.note_id is not None:
        note = await db.get(InvestigationNote, data.note_id)
        if note is None or note.investigation_id != investigation_id:
            raise CaseItemValidationError("note_id is not in this investigation")
    if data.task_id is not None:
        task = await db.get(InvestigationTask, data.task_id)
        if task is None or task.investigation_id != investigation_id:
            raise CaseItemValidationError("task_id is not in this investigation")


async def _validate_task_links(
    db: AsyncSession,
    investigation_id: uuid.UUID,
    data: InvestigationTaskCreate | InvestigationTaskUpdate | _TaskLinks,
) -> None:
    if data.finding_id is not None:
        finding = await db.get(Finding, data.finding_id)
        if finding is None or finding.investigation_id != investigation_id:
            raise CaseItemValidationError("finding_id is not in this investigation")
    for evidence_id in data.evidence_reference_ids or []:
        evidence = await db.get(InvestigationEvidence, evidence_id)
        if evidence is None or evidence.investigation_id != investigation_id:
            raise CaseItemValidationError(
                "evidence_reference_ids must be in this investigation"
            )


def _sanitize_markdown(value: str) -> str:
    clean = _SCRIPT_RE.sub("", value.strip())
    clean = _EVENT_HANDLER_RE.sub("", clean)
    clean = clean.replace("javascript:", "")
    return clean


def _sanitize_text(value: str) -> str:
    return _sanitize_markdown(value).replace("\n", " ").strip()


def _now() -> datetime:
    return datetime.now(UTC)


_SCRIPT_RE = re.compile(r"<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>", re.I)
_EVENT_HANDLER_RE = re.compile(r"\s+on[a-z]+\s*=\s*(['\"]).*?\1", re.I)
