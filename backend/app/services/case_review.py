from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, date, datetime
from typing import Any, Literal, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.case_review import CaseReview
from app.models.evidence_bookmark import EvidenceBookmark
from app.models.finding import Finding
from app.models.finding_evidence import FindingEvidence
from app.models.investigation import Investigation
from app.models.investigation_evidence import InvestigationEvidence
from app.models.investigation_member import InvestigationMember
from app.models.investigation_note import InvestigationNote
from app.models.investigation_task import InvestigationTask
from app.models.recon_entity import ReconEntity
from app.models.report import Report
from app.models.target import Target
from app.models.user import User
from app.schemas.case_review import (
    CaseCloseRequest,
    CaseReviewChecklistItem,
    CaseReviewDecisionRequest,
    CaseReviewResponse,
    CaseReviewStatus,
    CaseReviewSubmitRequest,
    CompletenessLabel,
    EvidenceCompletenessResponse,
    RemediationValidationDecisionRequest,
    RemediationValidationResponse,
    RemediationValidationStatus,
    RemediationValidationSubmitRequest,
    ReportApprovalDecisionRequest,
    ReportApprovalResponse,
    ReportApprovalStatus,
    ReportApprovalSubmitRequest,
    ReviewBoardItem,
    ReviewBoardResponse,
)
from app.services.audit import record_event
from app.services.intelligence.findings_service import FindingNotFoundError
from app.services.investigation import (
    CASE_ADMIN_ROLES,
    MUTATION_ROLES,
    ForbiddenError,
    ensure_investigation_permission,
    get_investigation,
)
from app.services.report import get_report


class CaseReviewValidationError(Exception):
    pass


class CaseReviewNotFoundError(Exception):
    pass


_ReviewBoardItemType = Literal[
    "case_review",
    "report_approval",
    "remediation_validation",
    "changes_requested",
    "closure_ready",
]


async def get_case_review(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> CaseReviewResponse:
    investigation = await get_investigation(db, user, investigation_id)
    review = await _get_or_create_review(db, investigation_id)
    await _refresh_review_snapshot(db, investigation, review)
    await db.flush()
    await db.refresh(review)
    return _to_review_response(review)


async def submit_case_review(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    body: CaseReviewSubmitRequest,
) -> CaseReviewResponse:
    investigation = await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot submit cases for review",
    )
    review = await _get_or_create_review(db, investigation_id)
    if review.review_status == "closed":
        raise CaseReviewValidationError("Closed cases cannot be submitted")
    await _refresh_review_snapshot(db, investigation, review)
    review.review_status = "pending_review"
    review.submitted_by = user.id
    review.submitted_at = _now()
    review.review_notes = body.notes
    review.decision = "submitted"
    db.add(review)
    await db.flush()
    await db.refresh(review)
    await record_event(
        db,
        action="case.review_submitted",
        actor_id=user.id,
        resource_type="investigation",
        resource_id=investigation_id,
        investigation_id=investigation_id,
        metadata={
            "review_status": review.review_status,
            "completeness_score": review.evidence_completeness_score,
        },
    )
    return _to_review_response(review)


async def decide_case_review(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    body: CaseReviewDecisionRequest,
) -> CaseReviewResponse:
    investigation = await get_investigation(db, user, investigation_id)
    await _ensure_reviewer_permission(db, user, investigation)
    review = await _get_or_create_review(db, investigation_id)
    if review.review_status not in {"pending_review", "changes_requested"}:
        raise CaseReviewValidationError("Case is not pending review")
    status_by_decision = {
        "approve": "approved",
        "reject": "rejected",
        "request_changes": "changes_requested",
    }
    action_by_decision = {
        "approve": "case.review_approved",
        "reject": "case.review_rejected",
        "request_changes": "case.changes_requested",
    }
    await _refresh_review_snapshot(db, investigation, review)
    review.review_status = status_by_decision[body.decision]
    review.reviewed_by = user.id
    review.reviewed_at = _now()
    review.review_notes = body.notes
    review.decision = body.decision
    db.add(review)
    await db.flush()
    await db.refresh(review)
    await record_event(
        db,
        action=action_by_decision[body.decision],
        actor_id=user.id,
        resource_type="investigation",
        resource_id=investigation_id,
        investigation_id=investigation_id,
        metadata={"decision": body.decision, "review_status": review.review_status},
    )
    return _to_review_response(review)


async def close_case(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    body: CaseCloseRequest,
) -> CaseReviewResponse:
    investigation = await get_investigation(db, user, investigation_id)
    review = await _get_or_create_review(db, investigation_id)
    await _refresh_review_snapshot(db, investigation, review)
    override_reason = body.override_reason
    if review.review_status != "approved":
        if not override_reason:
            raise CaseReviewValidationError(
                "Case review must be approved before closure unless overridden"
            )
        await _ensure_case_owner_or_platform_admin(
            db,
            user,
            investigation_id,
            "Only owners or platform admins can override case closure",
        )
    else:
        await _ensure_reviewer_permission(db, user, investigation)
    review.review_status = "closed"
    review.closed_by = user.id
    review.closed_at = _now()
    review.closure_reason = body.closure_reason
    review.override_reason = override_reason
    review.decision = "closed"
    investigation.status = "completed"
    investigation.stage = "completed"
    db.add_all([review, investigation])
    await db.flush()
    await db.refresh(review)
    await record_event(
        db,
        action="case.closed",
        actor_id=user.id,
        resource_type="investigation",
        resource_id=investigation_id,
        investigation_id=investigation_id,
        metadata={
            "closure_reason": body.closure_reason,
            "override": bool(override_reason),
        },
    )
    if override_reason:
        await record_event(
            db,
            action="case.closure_overridden",
            actor_id=user.id,
            resource_type="investigation",
            resource_id=investigation_id,
            investigation_id=investigation_id,
            metadata={"override_reason": override_reason},
        )
    return _to_review_response(review)


async def get_evidence_completeness(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> EvidenceCompletenessResponse:
    investigation = await get_investigation(db, user, investigation_id)
    counts = await _evidence_counts(db, investigation.id)
    score, label, explanation = _completeness_score(counts)
    return EvidenceCompletenessResponse(
        investigation_id=investigation.id,
        score=score,
        label=label,
        contributors=counts,
        explanation=explanation,
        generated_at=_now(),
    )


async def submit_report_approval(
    db: AsyncSession,
    user: User,
    report_id: uuid.UUID,
    body: ReportApprovalSubmitRequest,
) -> ReportApprovalResponse:
    report = await get_report(db, user, report_id)
    await ensure_investigation_permission(
        db,
        user,
        report.investigation_id,
        MUTATION_ROLES,
        "Viewers cannot submit reports for approval",
    )
    if report.status == "archived":
        raise CaseReviewValidationError("Archived reports cannot be submitted")
    report.approval_status = "pending_approval"
    report.approval_submitted_by = user.id
    report.approval_submitted_at = _now()
    report.approval_notes = _clean_optional(body.notes)
    report.rejection_reason = None
    db.add(report)
    await db.flush()
    await db.refresh(report)
    await record_event(
        db,
        action="report.approval_submitted",
        actor_id=user.id,
        resource_type="report",
        resource_id=report.id,
        investigation_id=report.investigation_id,
    )
    return _report_approval_response(report)


async def decide_report_approval(
    db: AsyncSession,
    user: User,
    report_id: uuid.UUID,
    body: ReportApprovalDecisionRequest,
) -> ReportApprovalResponse:
    report = await get_report(db, user, report_id)
    investigation = await get_investigation(db, user, report.investigation_id)
    await _ensure_reviewer_permission(db, user, investigation)
    if report.approval_status != "pending_approval":
        raise CaseReviewValidationError("Report is not pending approval")
    report.approved_by = user.id
    report.approved_at = _now()
    if body.decision == "approve":
        report.approval_status = "approved"
        report.approval_notes = body.notes
        report.rejection_reason = None
        action = "report.approved"
    else:
        report.approval_status = "rejected"
        report.rejection_reason = body.notes
        action = "report.rejected"
    db.add(report)
    await db.flush()
    await db.refresh(report)
    await record_event(
        db,
        action=action,
        actor_id=user.id,
        resource_type="report",
        resource_id=report.id,
        investigation_id=report.investigation_id,
        metadata={"approval_status": report.approval_status},
    )
    return _report_approval_response(report)


async def submit_remediation_validation(
    db: AsyncSession,
    user: User,
    finding_id: uuid.UUID,
    body: RemediationValidationSubmitRequest,
) -> RemediationValidationResponse:
    finding = await db.get(Finding, finding_id)
    if finding is None:
        raise FindingNotFoundError("Finding not found")
    await get_investigation(db, user, finding.investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        finding.investigation_id,
        MUTATION_ROLES,
        "Viewers cannot submit remediation validation",
    )
    finding.validation_status = "validation_pending"
    finding.validation_owner = body.validation_owner or user.id
    finding.validation_notes = _clean_optional(body.validation_notes)
    finding.validation_failure_reason = None
    _append_finding_history(
        finding,
        actor_id=user.id,
        action="validation_submitted",
        metadata={"validation_owner": str(finding.validation_owner)},
    )
    db.add(finding)
    await db.flush()
    await db.refresh(finding)
    await record_event(
        db,
        action="remediation.validation_submitted",
        actor_id=user.id,
        resource_type="finding",
        resource_id=finding.id,
        investigation_id=finding.investigation_id,
        metadata={"validation_owner": str(finding.validation_owner)},
    )
    return _remediation_validation_response(finding)


async def decide_remediation_validation(
    db: AsyncSession,
    user: User,
    finding_id: uuid.UUID,
    body: RemediationValidationDecisionRequest,
) -> RemediationValidationResponse:
    finding = await db.get(Finding, finding_id)
    if finding is None:
        raise FindingNotFoundError("Finding not found")
    investigation = await get_investigation(db, user, finding.investigation_id)
    await _ensure_reviewer_permission(db, user, investigation)
    if finding.validation_status != "validation_pending":
        raise CaseReviewValidationError("Remediation is not pending validation")
    action_by_decision = {
        "validate": "remediation.validated",
        "fail": "remediation.validation_failed",
        "accept_risk": "remediation.accepted_risk",
    }
    status_by_decision = {
        "validate": "validated",
        "fail": "validation_failed",
        "accept_risk": "accepted_risk",
    }
    finding.validation_status = status_by_decision[body.decision]
    finding.verified_by = user.id
    finding.verified_at = _now()
    finding.validation_notes = body.notes
    finding.validation_failure_reason = (
        body.failure_reason if body.decision == "fail" else None
    )
    if body.decision == "validate":
        finding.remediation_status = "remediated"
    elif body.decision == "accept_risk":
        finding.remediation_status = "accepted_risk"
    _append_finding_history(
        finding,
        actor_id=user.id,
        action="validation_decision",
        metadata={"decision": body.decision},
    )
    db.add(finding)
    await db.flush()
    await db.refresh(finding)
    await record_event(
        db,
        action=action_by_decision[body.decision],
        actor_id=user.id,
        resource_type="finding",
        resource_id=finding.id,
        investigation_id=finding.investigation_id,
        metadata={"validation_status": finding.validation_status},
    )
    return _remediation_validation_response(finding)


async def get_review_board(
    db: AsyncSession,
    user: User,
    *,
    status: str | None = None,
    assigned_reviewer: uuid.UUID | None = None,
    priority: str | None = None,
    risk: str | None = None,
    due_date_before: date | None = None,
) -> ReviewBoardResponse:
    investigations = await _accessible_investigations(db, user)
    investigation_ids = [item.id for item in investigations]
    if not investigation_ids:
        return ReviewBoardResponse(
            generated_at=_now(),
            total=0,
            pending_case_reviews=0,
            pending_report_approvals=0,
            pending_remediation_validations=0,
            changes_requested=0,
            ready_for_closure=0,
            items=[],
        )
    reviews = await _reviews_for(db, investigation_ids)
    reports = await _reports_for(db, investigation_ids)
    findings = await _findings_for(db, investigation_ids)
    titles = {item.id: item.title for item in investigations}
    priorities = {item.id: item.priority for item in investigations}
    reviewers = {item.id: item.reviewer_id for item in investigations}
    due_dates = {
        item.id: item.due_date.isoformat() if item.due_date else None
        for item in investigations
    }
    review_by_investigation = {item.investigation_id: item for item in reviews}
    items: list[ReviewBoardItem] = []
    for review in reviews:
        if review.review_status in {"pending_review", "changes_requested"}:
            item_type: _ReviewBoardItemType = (
                "changes_requested"
                if review.review_status == "changes_requested"
                else "case_review"
            )
            items.append(
                ReviewBoardItem(
                    item_type=item_type,
                    id=str(review.id),
                    investigation_id=review.investigation_id,
                    investigation_title=titles.get(
                        review.investigation_id,
                        "Unknown investigation",
                    ),
                    title="Case review",
                    status=review.review_status,
                    priority=priorities.get(review.investigation_id, "medium"),
                    risk=_risk_from_score(review.evidence_completeness_score),
                    due_date=due_dates.get(review.investigation_id),
                    assigned_reviewer=reviewers.get(review.investigation_id),
                    created_at=review.submitted_at,
                    detail=review.review_notes or "Case requires reviewer action.",
                )
            )
    for report in reports:
        if report.approval_status == "pending_approval":
            items.append(
                ReviewBoardItem(
                    item_type="report_approval",
                    id=str(report.id),
                    investigation_id=report.investigation_id,
                    investigation_title=titles.get(
                        report.investigation_id,
                        "Unknown investigation",
                    ),
                    title=report.title or f"{report.report_type} report",
                    status=report.approval_status,
                    priority=priorities.get(report.investigation_id, "medium"),
                    risk="medium",
                    due_date=due_dates.get(report.investigation_id),
                    assigned_reviewer=reviewers.get(report.investigation_id),
                    created_at=report.approval_submitted_at,
                    detail="Report is pending stakeholder approval.",
                )
            )
    for finding in findings:
        if finding.validation_status == "validation_pending":
            items.append(
                ReviewBoardItem(
                    item_type="remediation_validation",
                    id=str(finding.id),
                    investigation_id=finding.investigation_id,
                    investigation_title=titles.get(
                        finding.investigation_id,
                        "Unknown investigation",
                    ),
                    title=finding.title,
                    status=finding.validation_status,
                    priority=priorities.get(finding.investigation_id, "medium"),
                    risk=finding.severity,
                    due_date=due_dates.get(finding.investigation_id),
                    assigned_reviewer=reviewers.get(finding.investigation_id),
                    created_at=finding.updated_at,
                    detail="Remediation validation is awaiting analyst review.",
                )
            )
    for investigation in investigations:
        case_review = review_by_investigation.get(investigation.id)
        if case_review and case_review.review_status == "approved":
            items.append(
                ReviewBoardItem(
                    item_type="closure_ready",
                    id=str(investigation.id),
                    investigation_id=investigation.id,
                    investigation_title=investigation.title,
                    title="Case ready for closure",
                    status="approved",
                    priority=investigation.priority,
                    risk=_risk_from_score(
                        case_review.evidence_completeness_score
                    ),
                    due_date=due_dates.get(investigation.id),
                    assigned_reviewer=investigation.reviewer_id,
                    created_at=case_review.reviewed_at,
                    detail="Review is approved. Owner or reviewer can close the case.",
                )
            )
    filtered = _filter_board_items(
        items,
        status=status,
        assigned_reviewer=assigned_reviewer,
        priority=priority,
        risk=risk,
        due_date_before=due_date_before,
    )
    counts = Counter(item.item_type for item in filtered)
    return ReviewBoardResponse(
        generated_at=_now(),
        total=len(filtered),
        pending_case_reviews=counts["case_review"],
        pending_report_approvals=counts["report_approval"],
        pending_remediation_validations=counts["remediation_validation"],
        changes_requested=counts["changes_requested"],
        ready_for_closure=counts["closure_ready"],
        items=sorted(
            filtered,
            key=lambda item: item.created_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        ),
    )


async def _get_or_create_review(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> CaseReview:
    result = await db.execute(
        select(CaseReview).where(CaseReview.investigation_id == investigation_id)
    )
    review = result.scalar_one_or_none()
    if review is not None:
        return review
    review = CaseReview(investigation_id=investigation_id)
    db.add(review)
    await db.flush()
    return review


async def _refresh_review_snapshot(
    db: AsyncSession,
    investigation: Investigation,
    review: CaseReview,
) -> None:
    counts = await _evidence_counts(db, investigation.id)
    checklist = await _review_checklist(db, investigation, counts)
    score, label, _explanation = _completeness_score(counts)
    review.checklist = [item.model_dump() for item in checklist]
    review.evidence_completeness_score = score
    review.evidence_completeness_label = label
    review.evidence_completeness_contributors = counts


async def _review_checklist(
    db: AsyncSession,
    investigation: Investigation,
    counts: dict[str, int],
) -> list[CaseReviewChecklistItem]:
    blockers = await _critical_blockers(db, investigation.id)
    return [
        _check(
            "authorization_statement",
            "Authorization statement exists",
            len(investigation.authorization_statement.strip()) >= 100,
            "Authorization statement meets the minimum length requirement.",
        ),
        _check("targets", "Targets exist", counts["targets"] > 0),
        _check("recon", "Recon was executed", counts["recon_entities"] > 0),
        _check("findings", "Findings generated", counts["findings"] > 0),
        _check("evidence", "Evidence linked", counts["evidence_links"] > 0),
        _check(
            "remediation",
            "Remediation reviewed",
            counts["remediation_tasks"] > 0 or counts["accepted_risk"] > 0,
        ),
        _check("reports", "Reports generated", counts["reports"] > 0),
        _check("audit", "Audit trail exists", counts["audit_events"] > 0),
        CaseReviewChecklistItem(
            key="critical_blockers",
            label="No unresolved critical blockers unless accepted risk",
            status="passed" if blockers == 0 else "failed",
            detail=(
                "No unresolved critical or high findings are blocking closure."
                if blockers == 0
                else f"{blockers} critical/high findings remain unresolved."
            ),
        ),
        _check(
            "executive_summary",
            "Executive summary exists",
            counts["executive_summaries"] > 0,
        ),
    ]


def _check(
    key: str,
    label: str,
    passed: bool,
    passed_detail: str | None = None,
) -> CaseReviewChecklistItem:
    return CaseReviewChecklistItem(
        key=key,
        label=label,
        status="passed" if passed else "failed",
        detail=passed_detail if passed and passed_detail else (
            f"{label}."
            if passed
            else f"{label} is incomplete or unavailable."
        ),
    )


async def _evidence_counts(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> dict[str, int]:
    findings = await _count(db, Finding, Finding.investigation_id == investigation_id)
    finding_ids = await _finding_ids(db, investigation_id)
    finding_evidence = (
        await _count(db, FindingEvidence, FindingEvidence.finding_id.in_(finding_ids))
        if finding_ids
        else 0
    )
    case_evidence = await _count(
        db,
        InvestigationEvidence,
        InvestigationEvidence.investigation_id == investigation_id,
    )
    reports = await _count(db, Report, Report.investigation_id == investigation_id)
    ready_reports = await _count(
        db,
        Report,
        Report.investigation_id == investigation_id,
        Report.status.in_(("ready", "archived")),
    )
    return {
        "targets": await _count(
            db,
            Target,
            Target.investigation_id == investigation_id,
        ),
        "recon_entities": await _count(
            db,
            ReconEntity,
            ReconEntity.investigation_id == investigation_id,
        ),
        "findings": findings,
        "citations": sum(await _report_citation_counts(db, investigation_id)),
        "evidence_chains": finding_evidence,
        "bookmarks": await _count(
            db,
            EvidenceBookmark,
            EvidenceBookmark.investigation_id == investigation_id,
        ),
        "notes": await _count(
            db,
            InvestigationNote,
            InvestigationNote.investigation_id == investigation_id,
            InvestigationNote.archived.is_(False),
        ),
        "reports": reports,
        "ready_reports": ready_reports,
        "remediation_tasks": await _count(
            db,
            InvestigationTask,
            InvestigationTask.investigation_id == investigation_id,
            InvestigationTask.archived_at.is_(None),
        ),
        "accepted_risk": await _count(
            db,
            Finding,
            Finding.investigation_id == investigation_id,
            Finding.remediation_status == "accepted_risk",
        ),
        "audit_events": await _count(
            db,
            AuditLog,
            AuditLog.investigation_id == investigation_id,
        ),
        "executive_summaries": await _count(
            db,
            InvestigationNote,
            InvestigationNote.investigation_id == investigation_id,
            InvestigationNote.note_type.in_(("executive", "executive_note")),
            InvestigationNote.archived.is_(False),
        ),
        "case_evidence": case_evidence,
        "evidence_links": finding_evidence + case_evidence,
    }


def _completeness_score(
    counts: dict[str, int],
) -> tuple[int, CompletenessLabel, list[str]]:
    weights = {
        "targets": 10,
        "recon_entities": 15,
        "findings": 15,
        "citations": 10,
        "evidence_chains": 15,
        "bookmarks": 5,
        "notes": 10,
        "reports": 10,
        "remediation_tasks": 10,
    }
    score = sum(weight for key, weight in weights.items() if counts.get(key, 0) > 0)
    label: CompletenessLabel = (
        "complete"
        if score >= 90
        else "strong"
        if score >= 75
        else "adequate"
        if score >= 55
        else "partial"
        if score >= 25
        else "incomplete"
    )
    explanation = [
        f"{key.replace('_', ' ')}: {counts.get(key, 0)}"
        for key in weights
    ]
    return score, label, explanation


async def _critical_blockers(db: AsyncSession, investigation_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Finding)
        .where(
            Finding.investigation_id == investigation_id,
            Finding.severity.in_(("critical", "high")),
            Finding.status.notin_(
                ("validated", "mitigated", "false_positive", "archived")
            ),
            Finding.remediation_status.notin_(("remediated", "accepted_risk")),
        )
    )
    return int(result.scalar_one())


async def _finding_ids(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[uuid.UUID]:
    result = await db.execute(
        select(Finding.id).where(Finding.investigation_id == investigation_id)
    )
    return list(result.scalars().all())


async def _report_citation_counts(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[int]:
    result = await db.execute(
        select(Report.report_metadata).where(
            Report.investigation_id == investigation_id
        )
    )
    counts: list[int] = []
    for metadata in result.scalars().all():
        if isinstance(metadata, dict):
            counts.append(int(metadata.get("knowledge_citation_count", 0) or 0))
    return counts


async def _count(db: AsyncSession, model: Any, *conditions: Any) -> int:
    statement = select(func.count()).select_from(model).where(*conditions)
    result = await db.execute(statement)
    return int(result.scalar_one())


async def _ensure_reviewer_permission(
    db: AsyncSession,
    user: User,
    investigation: Investigation,
) -> None:
    if user.role == "admin" or user.id in {
        investigation.owner_id,
        investigation.reviewer_id,
    }:
        return
    membership = await ensure_investigation_permission(
        db,
        user,
        investigation.id,
        CASE_ADMIN_ROLES,
        "Only case reviewers, owners, and admins can approve review workflow actions",
    )
    if membership is not None and membership.role in CASE_ADMIN_ROLES:
        return
    raise ForbiddenError(
        "Only case reviewers, owners, and admins can approve review workflow actions"
    )


async def _ensure_case_owner_or_platform_admin(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    message: str,
) -> None:
    if user.role == "admin":
        return
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        CASE_ADMIN_ROLES,
        message,
    )


async def _accessible_investigations(
    db: AsyncSession,
    user: User,
) -> list[Investigation]:
    if user.role == "admin":
        result = await db.execute(select(Investigation))
    else:
        result = await db.execute(
            select(Investigation)
            .outerjoin(
                InvestigationMember,
                InvestigationMember.investigation_id == Investigation.id,
            )
            .where(
                (Investigation.owner_id == user.id)
                | (InvestigationMember.user_id == user.id)
            )
        )
    return list(result.scalars().unique().all())


async def _reviews_for(
    db: AsyncSession,
    investigation_ids: list[uuid.UUID],
) -> list[CaseReview]:
    result = await db.execute(
        select(CaseReview).where(CaseReview.investigation_id.in_(investigation_ids))
    )
    return list(result.scalars().all())


async def _reports_for(
    db: AsyncSession,
    investigation_ids: list[uuid.UUID],
) -> list[Report]:
    result = await db.execute(
        select(Report).where(Report.investigation_id.in_(investigation_ids))
    )
    return list(result.scalars().all())


async def _findings_for(
    db: AsyncSession,
    investigation_ids: list[uuid.UUID],
) -> list[Finding]:
    result = await db.execute(
        select(Finding).where(Finding.investigation_id.in_(investigation_ids))
    )
    return list(result.scalars().all())


def _filter_board_items(
    items: list[ReviewBoardItem],
    *,
    status: str | None,
    assigned_reviewer: uuid.UUID | None,
    priority: str | None,
    risk: str | None,
    due_date_before: date | None,
) -> list[ReviewBoardItem]:
    return [
        item
        for item in items
        if (status is None or item.status == status)
        and (assigned_reviewer is None or item.assigned_reviewer == assigned_reviewer)
        and (priority is None or item.priority == priority)
        and (risk is None or item.risk == risk)
        and _matches_due_date(item.due_date, due_date_before)
    ]


def _matches_due_date(
    item_due_date: str | None,
    due_date_before: date | None,
) -> bool:
    if due_date_before is None:
        return True
    if item_due_date is None:
        return False
    try:
        return date.fromisoformat(item_due_date) <= due_date_before
    except ValueError:
        return False


def _to_review_response(review: CaseReview) -> CaseReviewResponse:
    return CaseReviewResponse(
        id=review.id,
        investigation_id=review.investigation_id,
        review_status=_case_review_status(review.review_status),
        submitted_by=review.submitted_by,
        submitted_at=review.submitted_at,
        reviewed_by=review.reviewed_by,
        reviewed_at=review.reviewed_at,
        review_notes=review.review_notes,
        decision=review.decision,
        closed_by=review.closed_by,
        closed_at=review.closed_at,
        closure_reason=review.closure_reason,
        override_reason=review.override_reason,
        checklist=[
            CaseReviewChecklistItem.model_validate(item)
            for item in _json_list(review.checklist)
        ],
        evidence_completeness_score=review.evidence_completeness_score,
        evidence_completeness_label=_completeness_label(
            review.evidence_completeness_label
        ),
        evidence_completeness_contributors={
            key: int(value)
            for key, value in _json_dict(
                review.evidence_completeness_contributors
            ).items()
            if isinstance(value, int)
        },
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


def _report_approval_response(report: Report) -> ReportApprovalResponse:
    return ReportApprovalResponse(
        report_id=report.id,
        investigation_id=report.investigation_id,
        approval_status=_report_approval_status(report.approval_status),
        approval_submitted_by=report.approval_submitted_by,
        approval_submitted_at=report.approval_submitted_at,
        approved_by=report.approved_by,
        approved_at=report.approved_at,
        approval_notes=report.approval_notes,
        rejection_reason=report.rejection_reason,
    )


def _remediation_validation_response(finding: Finding) -> RemediationValidationResponse:
    return RemediationValidationResponse(
        finding_id=finding.id,
        investigation_id=finding.investigation_id,
        validation_status=_remediation_validation_status(finding.validation_status),
        validation_owner=finding.validation_owner,
        validation_notes=finding.validation_notes,
        validated_by=finding.verified_by,
        validated_at=finding.verified_at,
        failure_reason=finding.validation_failure_reason,
    )


def _append_finding_history(
    finding: Finding,
    *,
    actor_id: uuid.UUID,
    action: str,
    metadata: dict[str, object],
) -> None:
    history = list(finding.review_history or [])
    history.append(
        {
            "action": action,
            "actor_id": str(actor_id),
            "created_at": _now().isoformat(),
            **metadata,
        }
    )
    finding.review_history = history[-50:]


def _risk_from_score(score: int) -> str:
    if score < 35:
        return "incomplete"
    if score < 60:
        return "medium"
    if score < 80:
        return "high"
    return "strong"


def _case_review_status(value: str) -> CaseReviewStatus:
    if value in {
        "not_submitted",
        "pending_review",
        "changes_requested",
        "approved",
        "rejected",
        "closed",
    }:
        return cast(CaseReviewStatus, value)
    return "not_submitted"


def _completeness_label(value: str) -> CompletenessLabel:
    if value in {"incomplete", "partial", "adequate", "strong", "complete"}:
        return cast(CompletenessLabel, value)
    return "incomplete"


def _report_approval_status(value: str) -> ReportApprovalStatus:
    if value in {"draft", "pending_approval", "approved", "rejected", "archived"}:
        return cast(ReportApprovalStatus, value)
    return "draft"


def _remediation_validation_status(value: str) -> RemediationValidationStatus:
    if value in {
        "not_validated",
        "validation_pending",
        "validated",
        "validation_failed",
        "accepted_risk",
    }:
        return cast(RemediationValidationStatus, value)
    return "not_validated"


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _json_list(value: object) -> list[dict[str, object]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _json_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _now() -> datetime:
    return datetime.now(UTC)
