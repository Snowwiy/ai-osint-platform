from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding import Finding
from app.models.playbook import (
    DefensivePlaybook,
    PlaybookRun,
    PlaybookRunStep,
    PlaybookStep,
)
from app.models.user import User
from app.schemas.finding import FindingSeverity
from app.schemas.playbook import (
    DefensivePlaybookResponse,
    FindingPlaybookRecommendation,
    FindingRemediationResponse,
    FindingRemediationUpdate,
    PlaybookCategory,
    PlaybookRunResponse,
    PlaybookRunStatus,
    PlaybookRunStepResponse,
    PlaybookRunStepStatus,
    PlaybookRunStepUpdate,
    PlaybookRunUpdate,
    PlaybookStepResponse,
    PlaybookStepType,
    RemediationStatus,
)
from app.services.audit import record_event
from app.services.investigation import (
    CASE_ADMIN_ROLES,
    MUTATION_ROLES,
    ForbiddenError,
    ensure_investigation_permission,
    ensure_user_is_member,
    get_investigation,
)


class PlaybookNotFoundError(Exception):
    pass


class PlaybookValidationError(Exception):
    pass


_RUN_TRANSITIONS: dict[str, set[str]] = {
    "open": {"in_progress", "blocked", "cancelled"},
    "in_progress": {"blocked", "completed", "cancelled"},
    "blocked": {"in_progress", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}
_REMEDIATION_TRANSITIONS: dict[str, set[str]] = {
    "not_started": {
        "validating",
        "remediation_planned",
        "accepted_risk",
        "false_positive",
    },
    "validating": {
        "remediation_planned",
        "accepted_risk",
        "false_positive",
    },
    "remediation_planned": {"in_progress", "accepted_risk"},
    "in_progress": {"pending_verification", "accepted_risk"},
    "pending_verification": {"in_progress", "remediated"},
    "remediated": set(),
    "accepted_risk": set(),
    "false_positive": set(),
}


async def list_playbooks(
    db: AsyncSession,
    *,
    active_only: bool = True,
) -> list[DefensivePlaybookResponse]:
    stmt = select(DefensivePlaybook).order_by(
        DefensivePlaybook.category,
        DefensivePlaybook.name,
    )
    if active_only:
        stmt = stmt.where(DefensivePlaybook.is_active.is_(True))
    result = await db.execute(stmt)
    return await _playbook_responses(db, list(result.scalars().all()))


async def get_playbook(
    db: AsyncSession,
    playbook_id: uuid.UUID,
) -> DefensivePlaybookResponse:
    playbook = await db.get(DefensivePlaybook, playbook_id)
    if playbook is None:
        raise PlaybookNotFoundError("Playbook not found")
    responses = await _playbook_responses(db, [playbook])
    return responses[0]


async def recommended_playbooks_for_finding(
    db: AsyncSession,
    user: User,
    finding_id: uuid.UUID,
) -> list[FindingPlaybookRecommendation]:
    finding = await _get_accessible_finding(db, user, finding_id)
    playbooks = await list_playbooks(db)
    recommendations: list[FindingPlaybookRecommendation] = []
    for playbook in playbooks:
        reason = _recommendation_reason(finding, playbook)
        if reason is not None:
            recommendations.append(
                FindingPlaybookRecommendation(
                    playbook=playbook,
                    reason=reason,
                )
            )
    if recommendations:
        return recommendations
    fallback = next(
        (
            playbook
            for playbook in playbooks
            if playbook.name == "Evidence Validation Review"
        ),
        None,
    )
    if fallback is None:
        return []
    return [
        FindingPlaybookRecommendation(
            playbook=fallback,
            reason="Validate stored evidence before selecting a remediation path.",
        )
    ]


async def start_playbook_run(
    db: AsyncSession,
    user: User,
    finding_id: uuid.UUID,
    playbook_id: uuid.UUID,
) -> PlaybookRunResponse:
    finding = await _get_accessible_finding(db, user, finding_id)
    await ensure_investigation_permission(
        db,
        user,
        finding.investigation_id,
        MUTATION_ROLES,
        "Viewers cannot start playbooks",
    )
    playbook = await db.get(DefensivePlaybook, playbook_id)
    if playbook is None or not playbook.is_active:
        raise PlaybookNotFoundError("Playbook not found")
    existing_result = await db.execute(
        select(PlaybookRun).where(
            PlaybookRun.finding_id == finding.id,
            PlaybookRun.playbook_id == playbook.id,
            PlaybookRun.status.in_(("open", "in_progress", "blocked")),
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        return await _run_response(db, existing)

    run = PlaybookRun(
        investigation_id=finding.investigation_id,
        finding_id=finding.id,
        playbook_id=playbook.id,
        status="open",
        started_by=user.id,
    )
    db.add(run)
    await db.flush()
    step_result = await db.execute(
        select(PlaybookStep)
        .where(PlaybookStep.playbook_id == playbook.id)
        .order_by(PlaybookStep.order_index)
    )
    for step in step_result.scalars().all():
        db.add(
            PlaybookRunStep(
                playbook_run_id=run.id,
                playbook_step_id=step.id,
                status="pending",
            )
        )
    await record_event(
        db,
        action="playbook.started",
        actor_id=user.id,
        resource_type="playbook_run",
        resource_id=run.id,
        investigation_id=finding.investigation_id,
        metadata={
            "finding_id": str(finding.id),
            "playbook_id": str(playbook.id),
            "playbook_name": playbook.name,
        },
    )
    await db.flush()
    await db.refresh(run)
    return await _run_response(db, run)


async def list_playbook_runs(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> list[PlaybookRunResponse]:
    await get_investigation(db, user, investigation_id)
    result = await db.execute(
        select(PlaybookRun)
        .where(PlaybookRun.investigation_id == investigation_id)
        .order_by(PlaybookRun.created_at.desc())
    )
    return [
        await _run_response(db, run)
        for run in result.scalars().all()
    ]


async def get_playbook_run(
    db: AsyncSession,
    user: User,
    run_id: uuid.UUID,
) -> PlaybookRunResponse:
    run = await _get_accessible_run(db, user, run_id)
    return await _run_response(db, run)


async def update_playbook_run(
    db: AsyncSession,
    user: User,
    run_id: uuid.UUID,
    body: PlaybookRunUpdate,
) -> PlaybookRunResponse:
    run = await _get_accessible_run(db, user, run_id)
    membership = await ensure_investigation_permission(
        db,
        user,
        run.investigation_id,
        MUTATION_ROLES,
        "Viewers cannot update playbook runs",
    )
    if (
        body.status == "cancelled"
        and user.role != "admin"
        and membership is not None
        and membership.role not in CASE_ADMIN_ROLES
    ):
        raise ForbiddenError("Only investigation owners or admins can cancel runs")
    if body.status == run.status:
        return await _run_response(db, run)
    _validate_transition(run.status, body.status, _RUN_TRANSITIONS, "playbook run")
    previous_status = run.status
    run.status = body.status
    action = "playbook.step_updated"
    if body.status == "completed":
        run.completed_by = user.id
        run.completed_at = datetime.now(UTC)
        action = "playbook.completed"
    elif body.status == "cancelled":
        run.completed_by = user.id
        run.completed_at = datetime.now(UTC)
        action = "playbook.cancelled"
    db.add(run)
    await record_event(
        db,
        action=action,
        actor_id=user.id,
        resource_type="playbook_run",
        resource_id=run.id,
        investigation_id=run.investigation_id,
        metadata={
            "finding_id": str(run.finding_id),
            "from_status": previous_status,
            "to_status": body.status,
        },
    )
    await db.flush()
    await db.refresh(run)
    return await _run_response(db, run)


async def update_playbook_run_step(
    db: AsyncSession,
    user: User,
    run_id: uuid.UUID,
    run_step_id: uuid.UUID,
    body: PlaybookRunStepUpdate,
) -> PlaybookRunResponse:
    run = await _get_accessible_run(db, user, run_id)
    await ensure_investigation_permission(
        db,
        user,
        run.investigation_id,
        MUTATION_ROLES,
        "Viewers cannot update playbook steps",
    )
    if run.status in {"completed", "cancelled"}:
        raise PlaybookValidationError("Closed playbook runs cannot be changed")
    result = await db.execute(
        select(PlaybookRunStep, PlaybookStep)
        .join(PlaybookStep, PlaybookRunStep.playbook_step_id == PlaybookStep.id)
        .where(
            PlaybookRunStep.id == run_step_id,
            PlaybookRunStep.playbook_run_id == run.id,
        )
    )
    row = result.one_or_none()
    if row is None:
        raise PlaybookNotFoundError("Playbook run step not found")
    run_step, step = row
    if body.status == "skipped" and step.required:
        raise PlaybookValidationError("Required playbook steps cannot be skipped")
    previous_status = run_step.status
    run_step.status = body.status
    if body.analyst_note is not None:
        run_step.analyst_note = body.analyst_note.strip() or None
    if body.status == "completed":
        run_step.completed_by = user.id
        run_step.completed_at = datetime.now(UTC)
    else:
        run_step.completed_by = None
        run_step.completed_at = None
    if run.status == "open" and body.status == "in_progress":
        run.status = "in_progress"
    db.add(run_step)
    db.add(run)
    await record_event(
        db,
        action="playbook.step_updated",
        actor_id=user.id,
        resource_type="playbook_run_step",
        resource_id=run_step.id,
        investigation_id=run.investigation_id,
        metadata={
            "playbook_run_id": str(run.id),
            "finding_id": str(run.finding_id),
            "step_title": step.title,
            "from_status": previous_status,
            "to_status": body.status,
        },
    )
    await db.flush()
    await _complete_run_if_ready(db, user, run)
    await db.refresh(run)
    return await _run_response(db, run)


async def update_finding_remediation(
    db: AsyncSession,
    user: User,
    finding_id: uuid.UUID,
    body: FindingRemediationUpdate,
) -> FindingRemediationResponse:
    finding = await _get_accessible_finding(db, user, finding_id)
    await ensure_investigation_permission(
        db,
        user,
        finding.investigation_id,
        MUTATION_ROLES,
        "Viewers cannot update remediation",
    )
    if body.remediation_owner is not None:
        await ensure_user_is_member(
            db,
            finding.investigation_id,
            body.remediation_owner,
            "Remediation owner must be an investigation member",
        )
    if body.verified_by is not None:
        await ensure_user_is_member(
            db,
            finding.investigation_id,
            body.verified_by,
            "Verifier must be an investigation member",
        )
    previous_status = finding.remediation_status
    if body.remediation_status != previous_status:
        _validate_transition(
            previous_status,
            body.remediation_status,
            _REMEDIATION_TRANSITIONS,
            "remediation",
        )
    if body.remediation_status == "remediated":
        if body.verified_by is None or not (body.verification_notes or "").strip():
            raise PlaybookValidationError(
                "Remediated findings require a verifier and verification notes"
            )
    if (
        body.remediation_status == "accepted_risk"
        and not (body.remediation_notes or "").strip()
    ):
        raise PlaybookValidationError(
            "Accepted risk requires remediation notes documenting the decision"
        )

    finding.remediation_status = body.remediation_status
    finding.remediation_owner = body.remediation_owner
    finding.remediation_due_date = body.remediation_due_date
    finding.remediation_notes = _clean_optional(body.remediation_notes)
    finding.verification_notes = _clean_optional(body.verification_notes)
    finding.verified_by = body.verified_by
    if body.remediation_status == "remediated":
        finding.verified_at = datetime.now(UTC)
    elif body.remediation_status != previous_status:
        finding.verified_at = None
    db.add(finding)
    action = "finding.remediation_updated"
    if body.remediation_status == "remediated":
        action = "finding.verified"
    elif body.remediation_status == "accepted_risk":
        action = "risk.accepted"
    await record_event(
        db,
        action=action,
        actor_id=user.id,
        resource_type="finding",
        resource_id=finding.id,
        investigation_id=finding.investigation_id,
        metadata={
            "from_status": previous_status,
            "to_status": body.remediation_status,
            "remediation_owner": (
                str(body.remediation_owner) if body.remediation_owner else None
            ),
            "verified_by": str(body.verified_by) if body.verified_by else None,
        },
    )
    await db.flush()
    await db.refresh(finding)
    return _remediation_response(finding)


async def _get_accessible_finding(
    db: AsyncSession,
    user: User,
    finding_id: uuid.UUID,
) -> Finding:
    finding = await db.get(Finding, finding_id)
    if finding is None:
        raise PlaybookNotFoundError("Finding not found")
    await get_investigation(db, user, finding.investigation_id)
    return finding


async def _get_accessible_run(
    db: AsyncSession,
    user: User,
    run_id: uuid.UUID,
) -> PlaybookRun:
    run = await db.get(PlaybookRun, run_id)
    if run is None:
        raise PlaybookNotFoundError("Playbook run not found")
    await get_investigation(db, user, run.investigation_id)
    return run


async def _playbook_responses(
    db: AsyncSession,
    playbooks: list[DefensivePlaybook],
) -> list[DefensivePlaybookResponse]:
    if not playbooks:
        return []
    result = await db.execute(
        select(PlaybookStep)
        .where(PlaybookStep.playbook_id.in_([item.id for item in playbooks]))
        .order_by(PlaybookStep.playbook_id, PlaybookStep.order_index)
    )
    steps_by_playbook: dict[uuid.UUID, list[PlaybookStepResponse]] = {}
    for step in result.scalars().all():
        steps_by_playbook.setdefault(step.playbook_id, []).append(
            _step_response(step)
        )
    return [
        DefensivePlaybookResponse(
            id=playbook.id,
            name=playbook.name,
            description=playbook.description,
            category=cast(PlaybookCategory, playbook.category),
            severity=cast(FindingSeverity, playbook.severity),
            framework=playbook.framework,
            is_active=playbook.is_active,
            created_by=playbook.created_by,
            created_at=playbook.created_at,
            updated_at=playbook.updated_at,
            steps=steps_by_playbook.get(playbook.id, []),
        )
        for playbook in playbooks
    ]


async def _run_response(
    db: AsyncSession,
    run: PlaybookRun,
) -> PlaybookRunResponse:
    playbook = await db.get(DefensivePlaybook, run.playbook_id)
    finding = await db.get(Finding, run.finding_id)
    if playbook is None or finding is None:
        raise PlaybookNotFoundError("Playbook run references unavailable data")
    result = await db.execute(
        select(PlaybookRunStep, PlaybookStep)
        .join(PlaybookStep, PlaybookRunStep.playbook_step_id == PlaybookStep.id)
        .where(PlaybookRunStep.playbook_run_id == run.id)
        .order_by(PlaybookStep.order_index)
    )
    steps = [
        PlaybookRunStepResponse(
            id=run_step.id,
            playbook_run_id=run_step.playbook_run_id,
            playbook_step_id=run_step.playbook_step_id,
            status=cast(PlaybookRunStepStatus, run_step.status),
            analyst_note=run_step.analyst_note,
            completed_by=run_step.completed_by,
            completed_at=run_step.completed_at,
            step=_step_response(step),
        )
        for run_step, step in result.all()
    ]
    return PlaybookRunResponse(
        id=run.id,
        investigation_id=run.investigation_id,
        finding_id=run.finding_id,
        finding_title=finding.title,
        playbook_id=run.playbook_id,
        playbook_name=playbook.name,
        status=cast(PlaybookRunStatus, run.status),
        started_by=run.started_by,
        completed_by=run.completed_by,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
        steps=steps,
    )


def _step_response(step: PlaybookStep) -> PlaybookStepResponse:
    return PlaybookStepResponse(
        id=step.id,
        playbook_id=step.playbook_id,
        order_index=step.order_index,
        title=step.title,
        description=step.description,
        expected_output=step.expected_output,
        step_type=cast(PlaybookStepType, step.step_type),
        required=step.required,
        created_at=step.created_at,
        updated_at=step.updated_at,
    )


async def _complete_run_if_ready(
    db: AsyncSession,
    user: User,
    run: PlaybookRun,
) -> None:
    result = await db.execute(
        select(PlaybookRunStep.status).where(
            PlaybookRunStep.playbook_run_id == run.id
        )
    )
    statuses = list(result.scalars().all())
    if statuses and all(status in {"completed", "skipped"} for status in statuses):
        run.status = "completed"
        run.completed_by = user.id
        run.completed_at = datetime.now(UTC)
        db.add(run)
        await record_event(
            db,
            action="playbook.completed",
            actor_id=user.id,
            resource_type="playbook_run",
            resource_id=run.id,
            investigation_id=run.investigation_id,
            metadata={"finding_id": str(run.finding_id)},
        )
        await db.flush()


def _recommendation_reason(
    finding: Finding,
    playbook: DefensivePlaybookResponse,
) -> str | None:
    content = " ".join(
        (
            finding.title,
            finding.description,
            finding.source,
            str(finding.normalized_data),
        )
    ).lower()
    if playbook.name == "DNS Email Security Review" and any(
        marker in content for marker in ("spf", "dmarc", "email security")
    ):
        return "Stored DNS evidence indicates an email security policy review."
    if playbook.name == "Public Exposure Review" and any(
        marker in content
        for marker in (
            "public service",
            "exposure",
            "port",
            "service",
            "cdn",
            "proxy",
            "asn",
            "provider",
        )
    ):
        return "Stored infrastructure evidence should be validated with its owner."
    if playbook.name == "Technology Disclosure Review" and any(
        marker in content
        for marker in ("technology", "server disclosure", "header", "version")
    ):
        return "Stored technology metadata indicates a disclosure review."
    if playbook.name == "Evidence Validation Review" and (
        finding.confidence_score < 75
        or "unvalidated" in content
        or finding.status in {"new", "under_review"}
    ):
        return "The finding requires evidence and confidence validation."
    if playbook.name == "Remediation Verification Checklist" and (
        finding.status in {"validated", "mitigated"}
        or finding.remediation_status in {
            "remediation_planned",
            "in_progress",
            "pending_verification",
        }
    ):
        return "The finding is ready for remediation tracking or verification."
    return None


def _validate_transition(
    current: str,
    target: str,
    transitions: dict[str, set[str]],
    label: str,
) -> None:
    if target not in transitions.get(current, set()):
        raise PlaybookValidationError(
            f"Invalid {label} transition from {current} to {target}"
        )


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _remediation_response(finding: Finding) -> FindingRemediationResponse:
    return FindingRemediationResponse(
        finding_id=finding.id,
        investigation_id=finding.investigation_id,
        remediation_status=cast(RemediationStatus, finding.remediation_status),
        remediation_owner=finding.remediation_owner,
        remediation_due_date=finding.remediation_due_date,
        remediation_notes=finding.remediation_notes,
        verification_notes=finding.verification_notes,
        verified_by=finding.verified_by,
        verified_at=finding.verified_at,
    )
