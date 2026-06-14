from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime
from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence_bookmark import EvidenceBookmark
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.investigation_tag import InvestigationTag, InvestigationTagLink
from app.models.playbook import PlaybookRun
from app.models.recon_entity import ReconEntity
from app.models.report import Report
from app.models.target import Target
from app.models.user import User
from app.schemas.productivity import (
    BookmarkType,
    EvidenceBookmarkCreate,
    EvidenceBookmarkResponse,
    InvestigationPriorityResponse,
    InvestigationPriorityUpdate,
    InvestigationSummaryResponse,
    InvestigationTagCreate,
    InvestigationTagsUpdate,
    RemediationProgress,
    SummaryFinding,
)
from app.schemas.investigation import InvestigationPriority
from app.services.audit import record_event
from app.services.investigation import (
    CASE_ADMIN_ROLES,
    MUTATION_ROLES,
    ForbiddenError,
    ensure_investigation_permission,
    get_investigation,
)


class ProductivityItemNotFoundError(Exception):
    pass


class ProductivityValidationError(Exception):
    pass


class BookmarkAlreadyExistsError(ProductivityValidationError):
    pass


async def list_bookmarks(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> list[EvidenceBookmark]:
    await get_investigation(db, user, investigation_id)
    result = await db.execute(
        select(EvidenceBookmark)
        .where(EvidenceBookmark.investigation_id == investigation_id)
        .order_by(EvidenceBookmark.created_at.desc())
    )
    return list(result.scalars().all())


async def create_bookmark(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    data: EvidenceBookmarkCreate,
) -> EvidenceBookmark:
    await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot create bookmarks",
    )
    await _validate_bookmark_reference(db, investigation_id, data)
    duplicate_stmt = select(EvidenceBookmark.id).where(
        EvidenceBookmark.investigation_id == investigation_id,
        EvidenceBookmark.entity_id == data.entity_id,
        EvidenceBookmark.finding_id == data.finding_id,
        EvidenceBookmark.report_id == data.report_id,
    )
    if (await db.execute(duplicate_stmt)).scalar_one_or_none() is not None:
        raise BookmarkAlreadyExistsError("This evidence is already bookmarked")
    bookmark = EvidenceBookmark(
        investigation_id=investigation_id,
        entity_id=data.entity_id,
        finding_id=data.finding_id,
        report_id=data.report_id,
        title=_sanitize_text(data.title),
        note=_sanitize_markdown(data.note) if data.note else None,
        created_by=user.id,
    )
    db.add(bookmark)
    await db.flush()
    await record_event(
        db,
        action="bookmark.created",
        actor_id=user.id,
        resource_type="bookmark",
        resource_id=bookmark.id,
        investigation_id=investigation_id,
        metadata={
            "bookmark_type": bookmark_type(bookmark),
            "reference_id": str(
                bookmark.entity_id or bookmark.finding_id or bookmark.report_id
            ),
            "title": bookmark.title,
        },
    )
    await db.refresh(bookmark)
    return bookmark


async def delete_bookmark(
    db: AsyncSession,
    user: User,
    bookmark_id: uuid.UUID,
) -> None:
    bookmark = await db.get(EvidenceBookmark, bookmark_id)
    if bookmark is None:
        raise ProductivityItemNotFoundError("Bookmark not found")
    membership = await ensure_investigation_permission(
        db,
        user,
        bookmark.investigation_id,
        MUTATION_ROLES,
        "Viewers cannot delete bookmarks",
    )
    can_delete_any = (
        user.role == "admin"
        or membership is None
        or membership.role in CASE_ADMIN_ROLES
    )
    if not can_delete_any and bookmark.created_by != user.id:
        raise ForbiddenError("Analysts can only delete their own bookmarks")
    await record_event(
        db,
        action="bookmark.deleted",
        actor_id=user.id,
        resource_type="bookmark",
        resource_id=bookmark.id,
        investigation_id=bookmark.investigation_id,
        metadata={
            "bookmark_type": bookmark_type(bookmark),
            "title": bookmark.title,
        },
    )
    await db.delete(bookmark)


def bookmark_response(bookmark: EvidenceBookmark) -> EvidenceBookmarkResponse:
    return EvidenceBookmarkResponse(
        id=bookmark.id,
        investigation_id=bookmark.investigation_id,
        entity_id=bookmark.entity_id,
        finding_id=bookmark.finding_id,
        report_id=bookmark.report_id,
        bookmark_type=bookmark_type(bookmark),
        title=bookmark.title,
        note=bookmark.note,
        created_by=bookmark.created_by,
        created_at=bookmark.created_at,
    )


def bookmark_type(bookmark: EvidenceBookmark) -> BookmarkType:
    if bookmark.entity_id is not None:
        return "entity"
    if bookmark.finding_id is not None:
        return "finding"
    return "report"


async def list_tags(db: AsyncSession) -> list[InvestigationTag]:
    result = await db.execute(
        select(InvestigationTag).order_by(InvestigationTag.name)
    )
    return list(result.scalars().all())


async def create_tag(
    db: AsyncSession,
    user: User,
    data: InvestigationTagCreate,
) -> InvestigationTag:
    if user.role != "admin":
        raise ForbiddenError("Only platform administrators can create tags")
    existing = await db.execute(
        select(InvestigationTag).where(InvestigationTag.name == data.name)
    )
    if existing.scalar_one_or_none() is not None:
        raise ProductivityValidationError("Tag already exists")
    tag = InvestigationTag(name=data.name, color=data.color)
    db.add(tag)
    await db.flush()
    await db.refresh(tag)
    return tag


async def get_investigation_tags(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> list[InvestigationTag]:
    await get_investigation(db, user, investigation_id)
    result = await db.execute(
        select(InvestigationTag)
        .join(
            InvestigationTagLink,
            InvestigationTagLink.tag_id == InvestigationTag.id,
        )
        .where(InvestigationTagLink.investigation_id == investigation_id)
        .order_by(InvestigationTag.name)
    )
    return list(result.scalars().all())


async def update_investigation_tags(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    data: InvestigationTagsUpdate,
) -> list[InvestigationTag]:
    await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        CASE_ADMIN_ROLES,
        "Only investigation owners and admins can update tags",
    )
    tags: list[InvestigationTag] = []
    if data.tag_ids:
        result = await db.execute(
            select(InvestigationTag).where(InvestigationTag.id.in_(data.tag_ids))
        )
        tags = list(result.scalars().all())
        if len(tags) != len(data.tag_ids):
            raise ProductivityValidationError("One or more tags do not exist")
    previous = await get_investigation_tags(db, user, investigation_id)
    await db.execute(
        delete(InvestigationTagLink).where(
            InvestigationTagLink.investigation_id == investigation_id
        )
    )
    for tag in tags:
        db.add(
            InvestigationTagLink(
                investigation_id=investigation_id,
                tag_id=tag.id,
            )
        )
    await record_event(
        db,
        action="investigation.tag_updated",
        actor_id=user.id,
        resource_type="investigation",
        resource_id=investigation_id,
        investigation_id=investigation_id,
        metadata={
            "before": [tag.name for tag in previous],
            "after": [tag.name for tag in tags],
        },
    )
    await db.flush()
    return sorted(tags, key=lambda item: item.name)


async def update_investigation_priority(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    data: InvestigationPriorityUpdate,
) -> InvestigationPriorityResponse:
    investigation = await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        CASE_ADMIN_ROLES,
        "Only investigation owners and admins can update priority",
    )
    before = {
        "priority": investigation.priority,
        "business_impact": investigation.business_impact,
        "due_date": (
            investigation.due_date.isoformat() if investigation.due_date else None
        ),
    }
    investigation.priority = data.priority
    investigation.business_impact = (
        _sanitize_markdown(data.business_impact)
        if data.business_impact is not None
        else None
    )
    investigation.due_date = data.due_date
    db.add(investigation)
    await record_event(
        db,
        action="investigation.priority_updated",
        actor_id=user.id,
        resource_type="investigation",
        resource_id=investigation_id,
        investigation_id=investigation_id,
        metadata={
            "before": before,
            "after": {
                "priority": investigation.priority,
                "business_impact": investigation.business_impact,
                "due_date": (
                    investigation.due_date.isoformat()
                    if investigation.due_date
                    else None
                ),
            },
        },
    )
    await db.flush()
    await db.refresh(investigation)
    return _priority_response(investigation)


async def generate_investigation_summary(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> InvestigationSummaryResponse:
    investigation = await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot generate investigation summaries",
    )
    findings = await _findings(db, investigation_id)
    targets = await _targets(db, investigation_id)
    reports = await _reports(db, investigation_id)
    playbook_runs = await _playbook_runs(db, investigation_id)
    response = _build_summary(
        investigation,
        findings,
        targets,
        reports,
        playbook_runs,
    )
    await record_event(
        db,
        action="summary.generated",
        actor_id=user.id,
        resource_type="investigation_summary",
        resource_id=investigation_id,
        investigation_id=investigation_id,
        metadata={
            "finding_count": len(findings),
            "target_count": len(targets),
            "report_count": len(reports),
        },
    )
    return response


async def _validate_bookmark_reference(
    db: AsyncSession,
    investigation_id: uuid.UUID,
    data: EvidenceBookmarkCreate,
) -> None:
    if data.entity_id is not None:
        entity = await db.get(ReconEntity, data.entity_id)
        if entity is None or entity.investigation_id != investigation_id:
            raise ProductivityValidationError(
                "entity_id is not in this investigation"
            )
    if data.finding_id is not None:
        finding = await db.get(Finding, data.finding_id)
        if finding is None or finding.investigation_id != investigation_id:
            raise ProductivityValidationError(
                "finding_id is not in this investigation"
            )
    if data.report_id is not None:
        report = await db.get(Report, data.report_id)
        if report is None or report.investigation_id != investigation_id:
            raise ProductivityValidationError(
                "report_id is not in this investigation"
            )


def _priority_response(
    investigation: Investigation,
) -> InvestigationPriorityResponse:
    return InvestigationPriorityResponse(
        investigation_id=investigation.id,
        priority=cast(InvestigationPriority, investigation.priority),
        business_impact=investigation.business_impact,
        owner_id=investigation.owner_id,
        due_date=investigation.due_date,
        overdue=_is_overdue(investigation.due_date),
    )


async def _findings(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[Finding]:
    result = await db.execute(
        select(Finding)
        .where(Finding.investigation_id == investigation_id)
        .order_by(
            Finding.risk_score.desc(),
            Finding.created_at.desc(),
            Finding.id,
        )
    )
    return list(result.scalars().all())


async def _targets(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[Target]:
    result = await db.execute(
        select(Target)
        .where(Target.investigation_id == investigation_id)
        .order_by(Target.target_type, Target.target_value)
    )
    return list(result.scalars().all())


async def _reports(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[Report]:
    result = await db.execute(
        select(Report)
        .where(Report.investigation_id == investigation_id)
        .order_by(Report.created_at.desc())
    )
    return list(result.scalars().all())


async def _playbook_runs(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[PlaybookRun]:
    result = await db.execute(
        select(PlaybookRun)
        .where(PlaybookRun.investigation_id == investigation_id)
        .order_by(PlaybookRun.created_at.desc())
    )
    return list(result.scalars().all())


def _build_summary(
    investigation: Investigation,
    findings: list[Finding],
    targets: list[Target],
    reports: list[Report],
    playbook_runs: list[PlaybookRun],
) -> InvestigationSummaryResponse:
    unresolved = [
        finding
        for finding in findings
        if finding.status
        not in {"mitigated", "resolved", "false_positive", "archived"}
        and finding.remediation_status
        not in {"remediated", "accepted_risk", "false_positive"}
    ]
    remediated = sum(
        finding.remediation_status == "remediated" for finding in findings
    )
    accepted_risk = sum(
        finding.remediation_status == "accepted_risk" for finding in findings
    )
    completed = remediated + accepted_risk
    completion_percent = (
        round((completed / len(findings)) * 100) if findings else 0
    )
    severity_counts = {
        severity: sum(finding.severity == severity for finding in unresolved)
        for severity in ("critical", "high", "medium", "low", "info")
    }
    concerns = [
        f"{count} unresolved {severity} finding(s)"
        for severity, count in severity_counts.items()
        if count
    ]
    if not concerns:
        concerns.append("No unresolved defensive findings are currently stored.")
    actions = _recommended_actions(
        findings,
        targets,
        reports,
        playbook_runs,
    )
    target_scope = ", ".join(
        f"{target.target_type}:{target.target_value}" for target in targets[:10]
    )
    scope = (
        target_scope
        or investigation.scope_definition
        or "No investigation targets are currently stored."
    )
    top_findings = findings[:5]
    evidence_references = [
        *(f"finding:{finding.id}" for finding in top_findings),
        *(f"target:{target.id}" for target in targets[:10]),
        *(f"report:{report.id}" for report in reports[:5]),
    ]
    return InvestigationSummaryResponse(
        investigation_id=investigation.id,
        scope=scope,
        observed_defensive_concerns=concerns,
        highest_priority_findings=[
            SummaryFinding(
                id=finding.id,
                title=finding.title,
                severity=finding.severity,
                status=finding.status,
                risk_score=finding.risk_score,
            )
            for finding in top_findings
        ],
        remediation_progress=RemediationProgress(
            total_findings=len(findings),
            remediated=remediated,
            accepted_risk=accepted_risk,
            unresolved=len(unresolved),
            completion_percent=completion_percent,
        ),
        next_recommended_analyst_actions=actions,
        evidence_references=evidence_references,
    )


def _recommended_actions(
    findings: list[Finding],
    targets: list[Target],
    reports: list[Report],
    playbook_runs: list[PlaybookRun],
) -> list[str]:
    actions: list[str] = []
    if not targets:
        actions.append("Add an authorized target to define investigation scope.")
    if not findings:
        actions.append(
            "Run passive recon and generate deterministic findings for stored targets."
        )
    if any(
        finding.severity in {"critical", "high"}
        and finding.status not in {"mitigated", "false_positive", "archived"}
        for finding in findings
    ):
        actions.append("Validate the highest-severity unresolved findings.")
    if any(
        finding.remediation_status == "pending_verification"
        for finding in findings
    ):
        actions.append("Complete verification for pending remediation items.")
    if any(run.status in {"open", "in_progress", "blocked"} for run in playbook_runs):
        actions.append("Advance open defensive playbook steps.")
    if not reports:
        actions.append("Generate a stored executive or technical report.")
    if not actions:
        actions.append("Continue passive monitoring and review new timeline activity.")
    return actions


def _is_overdue(due_date: date | None) -> bool:
    return due_date is not None and due_date < datetime.now(UTC).date()


def _sanitize_markdown(value: str) -> str:
    clean = _SCRIPT_RE.sub("", value.strip())
    clean = _EVENT_HANDLER_RE.sub("", clean)
    return clean.replace("javascript:", "")


def _sanitize_text(value: str) -> str:
    return _sanitize_markdown(value).replace("\n", " ").strip()


_SCRIPT_RE = re.compile(r"<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>", re.I)
_EVENT_HANDLER_RE = re.compile(r"\s+on[a-z]+\s*=\s*(['\"]).*?\1", re.I)
