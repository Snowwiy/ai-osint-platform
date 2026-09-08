from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlsplit

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.case_closure import (
    CaseClosure,
    CaseClosureChecklistItem,
    CaseDeliverable,
)
from app.models.data_quality import DataQualityIssue
from app.models.engagement import Engagement, EngagementScopeItem
from app.models.finding import Finding
from app.models.finding_evidence import FindingEvidence
from app.models.investigation import Investigation
from app.models.investigation_task import InvestigationTask
from app.models.ioc import IOC
from app.models.notification import Notification
from app.models.report import Report
from app.models.report_template import ReportTemplate
from app.models.saved_view import SavedView
from app.models.user import User
from app.schemas.data_quality import (
    DataQualityIssueResponse,
    DataQualityOverviewResponse,
    DataQualityScanResponse,
    MaintenanceDryRunResponse,
    StaleNotificationArchiveResponse,
)
from app.services.audit import record_event

SCAN_LIMIT = 2_000
STALE_INVESTIGATION_DAYS = 30
STALE_NOTIFICATION_DAYS = 30
STALE_PENDING_USER_DAYS = 14
STALE_APPROVED_CLOSURE_DAYS = 30
DEMO_INVESTIGATION_ID = uuid.UUID("70000000-0000-4000-8000-000000000001")
DEMO_EXPECTED_IDS = (
    ("finding", uuid.UUID("70000000-0000-4000-8000-000000000007")),
    ("report", uuid.UUID("70000000-0000-4000-8000-000000000010")),
    ("ioc", uuid.UUID("70000000-0000-4000-8000-000000000018")),
    ("engagement", uuid.UUID("70000000-0000-4000-8000-000000000031")),
    ("closure", uuid.UUID("70000000-0000-4000-8000-000000000035")),
    ("notification", uuid.UUID("70000000-0000-4000-8000-000000000041")),
    ("saved_view", uuid.UUID("70000000-0000-4000-8000-000000000046")),
)

Severity = Literal["info", "warning", "high", "critical"]
IssueStatus = Literal["open", "acknowledged", "resolved", "ignored"]


class DataQualityIssueNotFoundError(Exception):
    pass


class InvalidIssueTransitionError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class QualityCandidate:
    issue_type: str
    severity: Severity
    entity_type: str
    entity_id: uuid.UUID | None
    title: str
    description: str
    recommendation: str
    action_url: str | None = None
    related_entity_type: str | None = None
    related_entity_id: uuid.UUID | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        raw = ":".join(
            (
                self.issue_type,
                self.entity_type,
                str(self.entity_id or "global"),
                str(self.related_entity_type or ""),
                str(self.related_entity_id or ""),
            )
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def detect_quality_issues(db: AsyncSession) -> list[QualityCandidate]:
    now = datetime.now(UTC)
    today = now.date()
    investigations = list(
        (await db.scalars(select(Investigation).limit(SCAN_LIMIT))).all()
    )
    engagements = list((await db.scalars(select(Engagement).limit(SCAN_LIMIT))).all())
    scope_items = list(
        (await db.scalars(select(EngagementScopeItem).limit(SCAN_LIMIT))).all()
    )
    findings = list((await db.scalars(select(Finding).limit(SCAN_LIMIT))).all())
    evidence = list(
        (await db.scalars(select(FindingEvidence).limit(SCAN_LIMIT))).all()
    )
    reports = list((await db.scalars(select(Report).limit(SCAN_LIMIT))).all())
    templates = list(
        (await db.scalars(select(ReportTemplate).limit(SCAN_LIMIT))).all()
    )
    closures = list((await db.scalars(select(CaseClosure).limit(SCAN_LIMIT))).all())
    checklist_items = list(
        (await db.scalars(select(CaseClosureChecklistItem).limit(SCAN_LIMIT))).all()
    )
    deliverables = list(
        (await db.scalars(select(CaseDeliverable).limit(SCAN_LIMIT))).all()
    )
    notifications = list(
        (await db.scalars(select(Notification).limit(SCAN_LIMIT))).all()
    )
    saved_views = list((await db.scalars(select(SavedView).limit(SCAN_LIMIT))).all())
    users = list((await db.scalars(select(User).limit(SCAN_LIMIT))).all())
    tasks = list(
        (await db.scalars(select(InvestigationTask).limit(SCAN_LIMIT))).all()
    )
    iocs = list((await db.scalars(select(IOC).limit(SCAN_LIMIT))).all())

    candidates: list[QualityCandidate] = []
    investigation_ids = {item.id for item in investigations}
    engagement_ids = {item.id for item in engagements}
    report_ids = {item.id for item in reports}
    user_by_id = {item.id: item for item in users}
    findings_by_investigation: dict[uuid.UUID, list[Finding]] = defaultdict(list)
    for finding in findings:
        findings_by_investigation[finding.investigation_id].append(finding)
    evidence_finding_ids = {item.finding_id for item in evidence}
    checklist_by_investigation: dict[
        uuid.UUID, list[CaseClosureChecklistItem]
    ] = defaultdict(list)
    for checklist_item in checklist_items:
        checklist_by_investigation[checklist_item.investigation_id].append(
            checklist_item
        )

    _check_investigations(
        candidates,
        investigations,
        engagements,
        findings_by_investigation,
        now,
    )
    _check_engagements(candidates, engagements, scope_items, today)
    _check_findings(
        candidates,
        findings,
        evidence_finding_ids,
        user_by_id,
        closures,
    )
    _check_iocs(candidates, iocs)
    _check_reports(
        candidates,
        reports,
        investigation_ids,
        templates,
        closures,
    )
    _check_closures(
        candidates,
        closures,
        checklist_by_investigation,
        deliverables,
        report_ids,
        now,
    )
    _check_notifications(
        candidates,
        notifications,
        investigation_ids,
        engagement_ids,
        now,
    )
    _check_saved_views(candidates, saved_views)
    _check_users(candidates, users, findings, tasks, now)
    _check_demo_state(
        candidates,
        investigations,
        findings,
        reports,
        iocs,
        engagements,
        closures,
        notifications,
        saved_views,
    )
    _check_system_configuration(candidates)
    return _dedupe_candidates(candidates)


async def run_quality_scan(
    db: AsyncSession,
    actor: User,
) -> DataQualityScanResponse:
    scanned_at = datetime.now(UTC)
    await record_event(
        db,
        action="data_quality.scan_started",
        actor_id=actor.id,
        resource_type="data_quality",
        metadata={"scan_limit": SCAN_LIMIT},
    )
    candidates = await detect_quality_issues(db)
    fingerprints = [candidate.fingerprint for candidate in candidates]
    existing_items = list(
        (
            await db.scalars(
                select(DataQualityIssue).where(
                    DataQualityIssue.fingerprint.in_(fingerprints)
                )
            )
        ).all()
    ) if fingerprints else []
    existing = {item.fingerprint: item for item in existing_items}
    created = 0
    for candidate in candidates:
        issue = existing.get(candidate.fingerprint)
        if issue is None:
            issue = DataQualityIssue(
                fingerprint=candidate.fingerprint,
                issue_type=candidate.issue_type,
                severity=candidate.severity,
                status="open",
                entity_type=candidate.entity_type,
                entity_id=candidate.entity_id,
                related_entity_type=candidate.related_entity_type,
                related_entity_id=candidate.related_entity_id,
                title=candidate.title,
                description=candidate.description,
                recommendation=candidate.recommendation,
                action_url=candidate.action_url,
                detected_at=scanned_at,
                issue_metadata=_safe_metadata(candidate.metadata),
            )
            db.add(issue)
            created += 1
            continue
        issue.severity = candidate.severity
        issue.title = candidate.title
        issue.description = candidate.description
        issue.recommendation = candidate.recommendation
        issue.action_url = candidate.action_url
        issue.detected_at = scanned_at
        issue.issue_metadata = _safe_metadata(candidate.metadata)
        if issue.status == "resolved":
            issue.status = "open"
            issue.resolved_at = None
        db.add(issue)
    await db.flush()
    if created:
        await record_event(
            db,
            action="data_quality.issue_detected",
            actor_id=actor.id,
            resource_type="data_quality",
            metadata={"new_issues": created, "detected": len(candidates)},
        )
    await record_event(
        db,
        action="data_quality.scan_completed",
        actor_id=actor.id,
        resource_type="data_quality",
        metadata={
            "detected": len(candidates),
            "created": created,
            "existing": len(candidates) - created,
        },
    )
    await db.flush()
    overview = await get_quality_overview(db, last_scan_at=scanned_at)
    return DataQualityScanResponse(
        scanned_at=scanned_at,
        detected=len(candidates),
        created=created,
        existing=len(candidates) - created,
        scan_limit=SCAN_LIMIT,
        overview=overview,
    )


async def get_quality_overview(
    db: AsyncSession,
    *,
    last_scan_at: datetime | None = None,
) -> DataQualityOverviewResponse:
    issues = list(
        (
            await db.scalars(
                select(DataQualityIssue)
                .order_by(DataQualityIssue.detected_at.desc())
                .limit(10_000)
            )
        ).all()
    )
    status_counts = Counter(item.status for item in issues)
    active = [item for item in issues if item.status in {"open", "acknowledged"}]
    severity_counts = Counter(item.severity for item in active)
    entity_counts = Counter(item.entity_type for item in active)
    type_counts = Counter(item.issue_type for item in active)
    if last_scan_at is None:
        last_scan_at = await db.scalar(
            select(func.max(AuditLog.created_at)).where(
                AuditLog.action == "data_quality.scan_completed"
            )
        )
    scan_status: Literal["not_run", "healthy", "attention", "critical"]
    if last_scan_at is None:
        scan_status = "not_run"
    elif severity_counts["critical"]:
        scan_status = "critical"
    elif active:
        scan_status = "attention"
    else:
        scan_status = "healthy"
    return DataQualityOverviewResponse(
        total_issues=len(issues),
        open_issues=len(active),
        critical_issues=severity_counts["critical"],
        high_issues=severity_counts["high"],
        warning_issues=severity_counts["warning"],
        acknowledged_issues=status_counts["acknowledged"],
        resolved_issues=status_counts["resolved"],
        ignored_issues=status_counts["ignored"],
        by_entity_type=dict(entity_counts),
        by_issue_type=dict(type_counts),
        last_scan_at=last_scan_at,
        scan_status=scan_status,
    )


async def list_quality_issues(
    db: AsyncSession,
    *,
    severity: str | None,
    status: str | None,
    issue_type: str | None,
    entity_type: str | None,
    investigation_id: uuid.UUID | None,
    engagement_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[int, list[DataQualityIssue]]:
    stmt = select(DataQualityIssue)
    count_stmt = select(func.count()).select_from(DataQualityIssue)
    filters: list[Any] = []
    if severity:
        filters.append(DataQualityIssue.severity == severity)
    if status:
        filters.append(DataQualityIssue.status == status)
    if issue_type:
        filters.append(DataQualityIssue.issue_type == issue_type)
    if entity_type:
        filters.append(DataQualityIssue.entity_type == entity_type)
    if investigation_id:
        filters.append(
            and_(
                DataQualityIssue.entity_type == "investigation",
                DataQualityIssue.entity_id == investigation_id,
            )
            | and_(
                DataQualityIssue.related_entity_type == "investigation",
                DataQualityIssue.related_entity_id == investigation_id,
            )
        )
    if engagement_id:
        filters.append(
            and_(
                DataQualityIssue.entity_type == "engagement",
                DataQualityIssue.entity_id == engagement_id,
            )
            | and_(
                DataQualityIssue.related_entity_type == "engagement",
                DataQualityIssue.related_entity_id == engagement_id,
            )
        )
    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)
    total = int((await db.scalar(count_stmt)) or 0)
    items = list(
        (
            await db.scalars(
                stmt.order_by(
                    *_severity_order(),
                    DataQualityIssue.detected_at.desc(),
                )
                .offset(offset)
                .limit(limit)
            )
        ).all()
    )
    return total, items


async def get_quality_issue(
    db: AsyncSession,
    issue_id: uuid.UUID,
) -> DataQualityIssue:
    issue = await db.get(DataQualityIssue, issue_id)
    if issue is None:
        raise DataQualityIssueNotFoundError
    return issue


async def transition_quality_issue(
    db: AsyncSession,
    actor: User,
    issue_id: uuid.UUID,
    target_status: IssueStatus,
) -> DataQualityIssue:
    issue = await get_quality_issue(db, issue_id)
    allowed: dict[str, set[str]] = {
        "open": {"acknowledged", "ignored", "resolved"},
        "acknowledged": {"ignored", "resolved"},
        "ignored": {"resolved"},
        "resolved": set(),
    }
    if issue.status == target_status:
        return issue
    if target_status not in allowed.get(issue.status, set()):
        raise InvalidIssueTransitionError(
            f"Issue cannot move from {issue.status} to {target_status}."
        )
    old_status = issue.status
    now = datetime.now(UTC)
    issue.status = target_status
    if target_status == "acknowledged":
        issue.acknowledged_at = now
        issue.acknowledged_by = actor.id
    if target_status == "resolved":
        issue.resolved_at = now
    db.add(issue)
    await record_event(
        db,
        action=f"data_quality.issue_{target_status}",
        actor_id=actor.id,
        resource_type="data_quality_issue",
        resource_id=issue.id,
        metadata={
            "issue_type": issue.issue_type,
            "severity": issue.severity,
            "entity_type": issue.entity_type,
            "entity_id": str(issue.entity_id) if issue.entity_id else None,
            "old_status": old_status,
            "new_status": target_status,
        },
    )
    await db.flush()
    await db.refresh(issue)
    return issue


async def build_maintenance_dry_run(
    db: AsyncSession,
    actor: User,
) -> MaintenanceDryRunResponse:
    candidates = await detect_quality_issues(db)
    severity_counts = Counter(item.severity for item in candidates)
    entity_counts = Counter(item.entity_type for item in candidates)
    recommendations = list(dict.fromkeys(item.recommendation for item in candidates))[:10]
    await record_event(
        db,
        action="maintenance.dry_run_completed",
        actor_id=actor.id,
        resource_type="maintenance",
        metadata={"would_detect": len(candidates), "destructive_changes": False},
    )
    return MaintenanceDryRunResponse(
        generated_at=datetime.now(UTC),
        would_detect=len(candidates),
        by_severity={str(key): value for key, value in severity_counts.items()},
        by_entity_type=dict(entity_counts),
        recommendations=recommendations,
        destructive_changes=False,
    )


async def archive_stale_notifications(
    db: AsyncSession,
    actor: User,
    *,
    older_than_days: int,
) -> StaleNotificationArchiveResponse:
    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
    result = await db.execute(
        update(Notification)
        .where(
            Notification.status.in_(("read", "dismissed")),
            Notification.created_at < cutoff,
        )
        .values(status="archived", updated_at=datetime.now(UTC))
    )
    archived = int(getattr(result, "rowcount", 0) or 0)
    await record_event(
        db,
        action="maintenance.stale_notifications_archived",
        actor_id=actor.id,
        resource_type="notification",
        metadata={"archived": archived, "older_than_days": older_than_days},
    )
    return StaleNotificationArchiveResponse(
        archived=archived,
        older_than_days=older_than_days,
        message=f"Archived {archived} stale read or dismissed notifications.",
    )


def to_issue_response(issue: DataQualityIssue) -> DataQualityIssueResponse:
    return DataQualityIssueResponse(
        id=issue.id,
        issue_type=issue.issue_type,
        severity=issue.severity,  # type: ignore[arg-type]
        status=issue.status,  # type: ignore[arg-type]
        entity_type=issue.entity_type,  # type: ignore[arg-type]
        entity_id=issue.entity_id,
        related_entity_type=issue.related_entity_type,
        related_entity_id=issue.related_entity_id,
        title=issue.title,
        description=issue.description,
        recommendation=issue.recommendation,
        action_url=issue.action_url,
        detected_at=issue.detected_at,
        resolved_at=issue.resolved_at,
        acknowledged_at=issue.acknowledged_at,
        acknowledged_by=issue.acknowledged_by,
        metadata=_safe_metadata(issue.issue_metadata),
        created_at=issue.created_at,
        updated_at=issue.updated_at,
    )


def _check_investigations(
    output: list[QualityCandidate],
    investigations: list[Investigation],
    engagements: list[Engagement],
    findings_by_investigation: dict[uuid.UUID, list[Finding]],
    now: datetime,
) -> None:
    engagement_by_id = {item.id: item for item in engagements}
    grouped: dict[tuple[str, uuid.UUID, uuid.UUID | None], list[Investigation]] = (
        defaultdict(list)
    )
    for item in investigations:
        grouped[(item.title.strip().casefold(), item.owner_id, item.engagement_id)].append(
            item
        )
        action_url = f"/investigations/{item.id}"
        if item.status == "archived" and item.stage != "archived":
            output.append(
                _candidate(
                    "archived_investigation_state_mismatch",
                    "warning",
                    "investigation",
                    item.id,
                    "Archived investigation has an active lifecycle stage",
                    "The archive status and lifecycle stage do not agree.",
                    "Review the investigation lifecycle and archive state.",
                    action_url,
                )
            )
        age = now - _as_utc(item.created_at)
        if (
            item.status not in {"archived", "completed"}
            and age.days >= STALE_INVESTIGATION_DAYS
            and not findings_by_investigation.get(item.id)
        ):
            output.append(
                _candidate(
                    "stale_investigation_without_findings",
                    "info",
                    "investigation",
                    item.id,
                    "Investigation has no findings",
                    f"This active investigation is {age.days} days old and has no findings.",
                    "Review evidence collection or document why findings are not applicable.",
                    action_url,
                    metadata={"age_days": age.days},
                )
            )
        engagement = engagement_by_id.get(item.engagement_id) if item.engagement_id else None
        if engagement and engagement.authorization_status in {"expired", "revoked"}:
            output.append(
                _candidate(
                    "investigation_authorization_invalid",
                    "critical" if engagement.authorization_status == "revoked" else "high",
                    "investigation",
                    item.id,
                    "Investigation authorization requires review",
                    f"The linked engagement authorization is {engagement.authorization_status}.",
                    "Pause scope expansion and update authorization metadata before continuing.",
                    action_url,
                    "engagement",
                    engagement.id,
                    {"authorization_status": engagement.authorization_status},
                )
            )
        if item.status == "completed":
            unresolved = [
                finding
                for finding in findings_by_investigation.get(item.id, [])
                if finding.severity in {"high", "critical"}
                and finding.status not in {"mitigated", "resolved", "false_positive", "archived"}
            ]
            if unresolved:
                output.append(
                    _candidate(
                        "completed_investigation_unresolved_risk",
                        "high",
                        "investigation",
                        item.id,
                        "Completed investigation retains unresolved high risk",
                        f"{len(unresolved)} high or critical findings remain unresolved.",
                        "Review residual risk acceptance or reopen the investigation workflow.",
                        action_url,
                        metadata={"unresolved_count": len(unresolved)},
                    )
                )
    for items in grouped.values():
        if len(items) < 2:
            continue
        canonical = sorted(items, key=lambda item: item.created_at)[0]
        for duplicate in items[1:]:
            output.append(
                _candidate(
                    "duplicate_investigation",
                    "warning",
                    "investigation",
                    duplicate.id,
                    "Possible duplicate investigation",
                    "Another investigation has the same normalized title, owner, and engagement.",
                    "Compare scope and evidence before consolidating records manually.",
                    f"/investigations/{duplicate.id}",
                    "investigation",
                    canonical.id,
                    {"duplicate_count": len(items)},
                )
            )


def _check_engagements(
    output: list[QualityCandidate],
    engagements: list[Engagement],
    scope_items: list[EngagementScopeItem],
    today: date,
) -> None:
    scopes_by_engagement: dict[uuid.UUID, list[EngagementScopeItem]] = defaultdict(list)
    for item in scope_items:
        scopes_by_engagement[item.engagement_id].append(item)
    for engagement in engagements:
        action_url = f"/engagements?selected={engagement.id}"
        if engagement.status == "active" and engagement.authorization_status != "approved":
            output.append(
                _candidate(
                    "active_engagement_without_approved_authorization",
                    "high",
                    "engagement",
                    engagement.id,
                    "Active engagement lacks approved authorization",
                    f"Authorization is {engagement.authorization_status} while the engagement is active.",
                    "Review and approve, revoke, or pause the engagement authorization state.",
                    action_url,
                )
            )
        if engagement.status == "active" and engagement.end_date and engagement.end_date < today:
            output.append(
                _candidate(
                    "active_engagement_past_end_date",
                    "high",
                    "engagement",
                    engagement.id,
                    "Active engagement is past its end date",
                    "The engagement remains active after its recorded end date.",
                    "Review authorization validity and update the engagement lifecycle.",
                    action_url,
                    metadata={"end_date": engagement.end_date.isoformat()},
                )
            )
        pending = [
            item
            for item in scopes_by_engagement.get(engagement.id, [])
            if item.status == "pending_review"
        ]
        if engagement.status == "active" and pending:
            output.append(
                _candidate(
                    "active_engagement_pending_scope",
                    "warning",
                    "engagement",
                    engagement.id,
                    "Active engagement has pending scope items",
                    f"{len(pending)} scope items still require analyst review.",
                    "Review each pending scope item before using it for authorized work.",
                    action_url,
                    metadata={"pending_scope_count": len(pending)},
                )
            )
        grouped: dict[tuple[str, str], list[EngagementScopeItem]] = defaultdict(list)
        for item in scopes_by_engagement.get(engagement.id, []):
            grouped[(item.scope_type, item.value.strip().casefold())].append(item)
        for items in grouped.values():
            if len(items) > 1:
                output.append(
                    _candidate(
                        "duplicate_scope_item",
                        "warning",
                        "scope_item",
                        items[-1].id,
                        "Duplicate engagement scope item",
                        "The same normalized scope value appears more than once in this engagement.",
                        "Review and retain one authoritative scope record.",
                        action_url,
                        "scope_item",
                        items[0].id,
                        {"duplicate_count": len(items)},
                    )
                )


def _check_findings(
    output: list[QualityCandidate],
    findings: list[Finding],
    evidence_finding_ids: set[uuid.UUID],
    user_by_id: dict[uuid.UUID, User],
    closures: list[CaseClosure],
) -> None:
    grouped: dict[tuple[uuid.UUID, str, str, str], list[Finding]] = defaultdict(list)
    closed_investigations = {
        item.investigation_id for item in closures if item.status == "closed"
    }
    valid_remediation = {
        "not_started",
        "validating",
        "remediation_planned",
        "in_progress",
        "pending_verification",
        "remediated",
        "accepted_risk",
        "false_positive",
    }
    for finding in findings:
        grouped[
            (
                finding.investigation_id,
                finding.title.strip().casefold(),
                finding.severity,
                finding.source.strip().casefold(),
            )
        ].append(finding)
        action_url = f"/investigations/{finding.investigation_id}/findings"
        if (
            finding.severity in {"high", "critical"}
            and not (finding.evidence_summary or "").strip()
            and finding.id not in evidence_finding_ids
        ):
            output.append(
                _candidate(
                    "high_risk_finding_without_evidence",
                    "high",
                    "finding",
                    finding.id,
                    "High-risk finding lacks linked evidence",
                    "No evidence summary or structured evidence link is recorded.",
                    "Link evidence or document the basis for the evidence-backed finding.",
                    action_url,
                    "investigation",
                    finding.investigation_id,
                )
            )
        assignee = user_by_id.get(finding.assigned_to) if finding.assigned_to else None
        if assignee and (not assignee.is_active or assignee.account_status != "active"):
            output.append(
                _candidate(
                    "finding_assigned_to_inactive_user",
                    "high",
                    "finding",
                    finding.id,
                    "Finding is assigned to an unavailable user",
                    f"The assigned account is {assignee.account_status}.",
                    "Reassign the finding to an active analyst.",
                    action_url,
                    "user",
                    assignee.id,
                )
            )
        if finding.remediation_status not in valid_remediation:
            output.append(
                _candidate(
                    "invalid_finding_remediation_status",
                    "critical",
                    "finding",
                    finding.id,
                    "Finding has an invalid remediation status",
                    "The stored remediation status is outside the supported workflow.",
                    "Review the record and correct the status through the supported workflow.",
                    action_url,
                )
            )
        if (
            finding.investigation_id in closed_investigations
            and finding.validation_status in {"not_validated", "validation_pending", "validation_failed"}
            and finding.severity in {"high", "critical"}
        ):
            output.append(
                _candidate(
                    "closed_case_incomplete_finding_validation",
                    "high",
                    "finding",
                    finding.id,
                    "Closed case has incomplete high-risk validation",
                    f"Validation remains {finding.validation_status} for this finding.",
                    "Review validation evidence or document accepted residual risk.",
                    action_url,
                )
            )
    for items in grouped.values():
        if len(items) < 2:
            continue
        canonical = sorted(items, key=lambda item: item.created_at)[0]
        for duplicate in items[1:]:
            output.append(
                _candidate(
                    "duplicate_finding",
                    "warning",
                    "finding",
                    duplicate.id,
                    "Possible duplicate finding",
                    "Another finding has the same title, severity, source, and investigation.",
                    "Compare evidence and retain the records only if they describe distinct observations.",
                    f"/investigations/{duplicate.investigation_id}/findings",
                    "finding",
                    canonical.id,
                    {"duplicate_count": len(items)},
                )
            )


def _check_iocs(output: list[QualityCandidate], iocs: list[IOC]) -> None:
    grouped: dict[tuple[str, str], list[IOC]] = defaultdict(list)
    for item in iocs:
        grouped[(item.ioc_type, item.normalized_value.strip().casefold())].append(item)
    for items in grouped.values():
        if len(items) < 2:
            continue
        canonical = sorted(items, key=lambda item: item.created_at)[0]
        for duplicate in items[1:]:
            output.append(
                _candidate(
                    "duplicate_ioc",
                    "warning",
                    "evidence",
                    duplicate.id,
                    "Possible duplicate indicator",
                    "The same normalized indicator and type appear more than once.",
                    "Review internal IOC correlation before consolidating records.",
                    "/threat-intelligence",
                    "evidence",
                    canonical.id,
                    {"ioc_type": duplicate.ioc_type},
                )
            )


def _check_reports(
    output: list[QualityCandidate],
    reports: list[Report],
    investigation_ids: set[uuid.UUID],
    templates: list[ReportTemplate],
    closures: list[CaseClosure],
) -> None:
    templates_by_id = {item.id: item for item in templates}
    reopened = {item.investigation_id for item in closures if item.status == "reopened"}
    for report in reports:
        route = f"/investigations/{report.investigation_id}/reports"
        if report.investigation_id not in investigation_ids:
            output.append(
                _candidate(
                    "report_without_investigation",
                    "critical",
                    "report",
                    report.id,
                    "Report has no accessible investigation",
                    "The report references an investigation that is not present.",
                    "Review database integrity before using this export.",
                    "/reports",
                )
            )
        if report.status == "ready" and not any(
            (report.file_path, report.html_content, report.markdown_content)
        ):
            output.append(
                _candidate(
                    "report_ready_without_content",
                    "high",
                    "report",
                    report.id,
                    "Ready report has no generated content",
                    "The report is marked ready but no export content is recorded.",
                    "Retry report generation and verify export storage readiness.",
                    route,
                )
            )
        template = templates_by_id.get(report.template_id) if report.template_id else None
        if template and not template.is_active and report.status not in {"archived", "failed"}:
            output.append(
                _candidate(
                    "active_report_uses_disabled_template",
                    "warning",
                    "report",
                    report.id,
                    "Active report uses a disabled template",
                    "The report references a template that is no longer active.",
                    "Confirm the historical template is intentional or regenerate with an active template.",
                    route,
                    "system",
                    template.id,
                )
            )
        if report.approval_status == "approved" and report.investigation_id in reopened:
            output.append(
                _candidate(
                    "approved_report_on_reopened_case",
                    "warning",
                    "report",
                    report.id,
                    "Approved report belongs to a reopened case",
                    "The investigation changed state after report approval.",
                    "Review whether the report remains current before delivery.",
                    route,
                )
            )


def _check_closures(
    output: list[QualityCandidate],
    closures: list[CaseClosure],
    checklist_by_investigation: dict[uuid.UUID, list[CaseClosureChecklistItem]],
    deliverables: list[CaseDeliverable],
    report_ids: set[uuid.UUID],
    now: datetime,
) -> None:
    for closure in closures:
        route = f"/investigations/{closure.investigation_id}/closure"
        incomplete = [
            item
            for item in checklist_by_investigation.get(closure.investigation_id, [])
            if item.required and item.status not in {"completed", "not_applicable"}
        ]
        if closure.status == "closed" and incomplete:
            output.append(
                _candidate(
                    "closed_case_incomplete_checklist",
                    "critical",
                    "closure",
                    closure.id,
                    "Closed case has incomplete required checklist items",
                    f"{len(incomplete)} required closure items remain incomplete or blocked.",
                    "Review the closure decision and refresh the checklist.",
                    route,
                    "investigation",
                    closure.investigation_id,
                    {"incomplete_required": len(incomplete)},
                )
            )
        if (
            closure.status == "approved"
            and closure.approved_at
            and now - _as_utc(closure.approved_at) >= timedelta(days=STALE_APPROVED_CLOSURE_DAYS)
        ):
            output.append(
                _candidate(
                    "approved_closure_not_completed",
                    "info",
                    "closure",
                    closure.id,
                    "Approved closure has not been completed",
                    "The case has remained approved for closure for at least 30 days.",
                    "Confirm final deliverables and complete or reopen the closure workflow.",
                    route,
                )
            )
    for deliverable in deliverables:
        if deliverable.status not in {"ready", "approved", "delivered"}:
            continue
        linked_report_missing = deliverable.report_id is not None and deliverable.report_id not in report_ids
        lacks_link = (
            deliverable.report_id is None
            and not (deliverable.file_reference or "").strip()
            and deliverable.deliverable_type != "scope_summary"
        )
        if linked_report_missing or lacks_link:
            output.append(
                _candidate(
                    "deliverable_without_linkage",
                    "high" if linked_report_missing else "warning",
                    "deliverable",
                    deliverable.id,
                    "Ready deliverable lacks valid report or package linkage",
                    "The deliverable is ready but its supporting report or manifest is unavailable.",
                    "Link a generated report or create a package manifest before delivery.",
                    f"/investigations/{deliverable.investigation_id}/closure",
                    "investigation",
                    deliverable.investigation_id,
                )
            )


def _check_notifications(
    output: list[QualityCandidate],
    notifications: list[Notification],
    investigation_ids: set[uuid.UUID],
    engagement_ids: set[uuid.UUID],
    now: datetime,
) -> None:
    duplicate_groups: dict[tuple[uuid.UUID | None, str, str, uuid.UUID | None], list[Notification]] = defaultdict(list)
    for item in notifications:
        if item.status == "unread":
            duplicate_groups[
                (item.user_id, item.notification_type, item.entity_type, item.entity_id)
            ].append(item)
            age = now - _as_utc(item.created_at)
            if age.days >= STALE_NOTIFICATION_DAYS:
                output.append(
                    _candidate(
                        "stale_unread_notification",
                        "info",
                        "notification",
                        item.id,
                        "Unread notification is stale",
                        f"This notification has been unread for {age.days} days.",
                        "Review, dismiss, or mark the notification as read.",
                        "/notifications",
                        metadata={"age_days": age.days},
                    )
                )
        if item.action_url and not _valid_internal_route(item.action_url):
            output.append(
                _candidate(
                    "notification_broken_action_url",
                    "warning",
                    "notification",
                    item.id,
                    "Notification has an invalid internal action link",
                    "The action URL is not a supported in-app route.",
                    "Update or dismiss this notification; do not follow the invalid link.",
                    "/notifications",
                    metadata={"route_valid": False},
                )
            )
        missing = (
            item.entity_type == "investigation"
            and item.entity_id is not None
            and item.entity_id not in investigation_ids
        ) or (
            item.entity_type == "engagement"
            and item.entity_id is not None
            and item.entity_id not in engagement_ids
        )
        if missing:
            output.append(
                _candidate(
                    "notification_missing_entity",
                    "warning",
                    "notification",
                    item.id,
                    "Notification points to a missing entity",
                    "The referenced object is no longer available.",
                    "Dismiss or archive this notification after confirming the record lifecycle.",
                    "/notifications",
                )
            )
    for items in duplicate_groups.values():
        if len(items) > 1:
            output.append(
                _candidate(
                    "duplicate_unread_notification",
                    "info",
                    "notification",
                    items[-1].id,
                    "Duplicate unread workflow notifications",
                    f"{len(items)} unread notifications reference the same event type and entity.",
                    "Review notification deduplication and archive redundant read items manually.",
                    "/notifications",
                    "notification",
                    items[0].id,
                    {"duplicate_count": len(items)},
                )
            )


def _check_saved_views(
    output: list[QualityCandidate], saved_views: list[SavedView]
) -> None:
    grouped: dict[tuple[uuid.UUID, str], list[SavedView]] = defaultdict(list)
    for item in saved_views:
        grouped[(item.user_id, item.name.strip().casefold())].append(item)
        if not _valid_internal_route(item.route):
            output.append(
                _candidate(
                    "saved_view_invalid_route",
                    "warning",
                    "saved_view",
                    item.id,
                    "Saved view has an invalid route",
                    "The saved view no longer points to a supported internal page.",
                    "Edit or recreate the saved view with a valid application route.",
                    "/",
                )
            )
        if not isinstance(item.filters, dict) or (
            item.sort is not None and not isinstance(item.sort, dict)
        ):
            output.append(
                _candidate(
                    "saved_view_malformed_filters",
                    "warning",
                    "saved_view",
                    item.id,
                    "Saved view filters are malformed",
                    "Filters and sort settings must be JSON objects.",
                    "Recreate the saved view using the current page filters.",
                    item.route if _valid_internal_route(item.route) else "/",
                )
            )
    for items in grouped.values():
        if len(items) > 1:
            output.append(
                _candidate(
                    "duplicate_saved_view",
                    "info",
                    "saved_view",
                    items[-1].id,
                    "Duplicate saved view name",
                    "The same user has multiple saved views with this normalized name.",
                    "Rename or remove the redundant saved view after comparing filters.",
                    items[-1].route if _valid_internal_route(items[-1].route) else "/",
                    "saved_view",
                    items[0].id,
                    {"duplicate_count": len(items)},
                )
            )


def _check_users(
    output: list[QualityCandidate],
    users: list[User],
    findings: list[Finding],
    tasks: list[InvestigationTask],
    now: datetime,
) -> None:
    active_admins = [
        item
        for item in users
        if item.role == "admin" and item.is_active and item.account_status == "active"
    ]
    if not active_admins:
        output.append(
            _candidate(
                "no_active_admin",
                "critical",
                "system",
                None,
                "No active administrator account is available",
                "The platform has no active administrator for governance operations.",
                "Restore or approve an administrator account using the existing bootstrap procedure.",
                None,
            )
        )
    for user in users:
        age = now - _as_utc(user.created_at)
        if user.account_status == "pending" and age.days >= STALE_PENDING_USER_DAYS:
            output.append(
                _candidate(
                    "stale_pending_user",
                    "warning",
                    "user",
                    user.id,
                    "User approval has been pending for an extended period",
                    f"The account has remained pending for {age.days} days.",
                    "Approve or reject the registration from Admin Users.",
                    "/admin/users",
                    metadata={"age_days": age.days},
                )
            )
        if user.is_active and user.account_status == "active":
            continue
        assigned_findings = sum(1 for item in findings if item.assigned_to == user.id)
        assigned_tasks = sum(
            1
            for item in tasks
            if item.assigned_to == user.id and item.status != "completed"
        )
        if assigned_findings or assigned_tasks:
            output.append(
                _candidate(
                    "inactive_user_assigned_work",
                    "high",
                    "user",
                    user.id,
                    "Unavailable user retains active assignments",
                    f"The account has {assigned_findings} findings and {assigned_tasks} open tasks assigned.",
                    "Reassign active work to an available analyst.",
                    "/admin/users",
                    metadata={
                        "assigned_findings": assigned_findings,
                        "assigned_tasks": assigned_tasks,
                    },
                )
            )


def _check_demo_state(
    output: list[QualityCandidate],
    investigations: list[Investigation],
    findings: list[Finding],
    reports: list[Report],
    iocs: list[IOC],
    engagements: list[Engagement],
    closures: list[CaseClosure],
    notifications: list[Notification],
    saved_views: list[SavedView],
) -> None:
    ids_by_type = {
        "finding": {item.id for item in findings},
        "report": {item.id for item in reports},
        "ioc": {item.id for item in iocs},
        "engagement": {item.id for item in engagements},
        "closure": {item.id for item in closures},
        "notification": {item.id for item in notifications},
        "saved_view": {item.id for item in saved_views},
    }
    demo_exists = any(item.id == DEMO_INVESTIGATION_ID for item in investigations)
    any_component = any(item_id in ids_by_type[item_type] for item_type, item_id in DEMO_EXPECTED_IDS)
    if not demo_exists and not any_component:
        return
    missing = []
    if not demo_exists:
        missing.append("investigation")
    missing.extend(
        item_type
        for item_type, item_id in DEMO_EXPECTED_IDS
        if item_id not in ids_by_type[item_type]
    )
    if missing:
        output.append(
            _candidate(
                "incomplete_demo_data",
                "info",
                "demo_data",
                DEMO_INVESTIGATION_ID if demo_exists else None,
                "Synthetic demo workspace is only partially seeded",
                f"Missing demo components: {', '.join(sorted(set(missing)))}.",
                "Run the idempotent demo seed from Demo QA or clear the partial demo workspace.",
                "/admin/demo-checklist",
                metadata={"missing_components": sorted(set(missing)), "demo": True},
            )
        )


def _check_system_configuration(output: list[QualityCandidate]) -> None:
    if not settings.APP_NAME.strip() or not settings.APP_VERSION.strip():
        output.append(
            _candidate(
                "release_metadata_missing",
                "warning",
                "system",
                None,
                "Release metadata is incomplete",
                "Application name or version metadata is missing.",
                "Configure non-secret release metadata before demonstrations or releases.",
                "/admin/operations",
            )
        )
    if (
        settings.PUBLIC_REGISTRATION_ENABLED
        and not settings.REGISTRATION_REQUIRES_APPROVAL
        and not bool(settings.REGISTRATION_INVITE_CODE)
    ):
        output.append(
            _candidate(
                "risky_registration_configuration",
                "critical" if settings.is_production else "high",
                "system",
                None,
                "Public registration lacks approval and invite controls",
                "Public registration is enabled without approval or an invite code.",
                "Enable registration approval or configure a server-side invite code.",
                "/admin/settings",
                metadata={"environment": settings.APP_ENVIRONMENT},
            )
        )
    if settings.is_production and "*" in settings.allowed_origins_list:
        output.append(
            _candidate(
                "production_cors_wildcard",
                "critical",
                "system",
                None,
                "Production CORS configuration contains a wildcard",
                "A wildcard origin is unsafe for the authenticated production API.",
                "Configure explicit HTTPS frontend origins.",
                "/admin/operations",
            )
        )


def _candidate(
    issue_type: str,
    severity: Severity,
    entity_type: str,
    entity_id: uuid.UUID | None,
    title: str,
    description: str,
    recommendation: str,
    action_url: str | None,
    related_entity_type: str | None = None,
    related_entity_id: uuid.UUID | None = None,
    metadata: dict[str, object] | None = None,
) -> QualityCandidate:
    return QualityCandidate(
        issue_type=issue_type,
        severity=severity,
        entity_type=entity_type,
        entity_id=entity_id,
        title=title,
        description=description,
        recommendation=recommendation,
        action_url=action_url if action_url and _valid_internal_route(action_url) else None,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        metadata=metadata or {},
    )


def _dedupe_candidates(items: list[QualityCandidate]) -> list[QualityCandidate]:
    return list({item.fingerprint: item for item in items}.values())


def _valid_internal_route(route: str) -> bool:
    value = route.strip()
    if not value.startswith("/") or value.startswith("//"):
        return False
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.fragment:
        return False
    allowed_roots = {
        "",
        "admin",
        "engagements",
        "evidence-intelligence",
        "executive",
        "investigations",
        "knowledge",
        "notifications",
        "operations",
        "reports",
        "review-board",
        "threat-intelligence",
    }
    root = parsed.path.lstrip("/").split("/", 1)[0]
    return root in allowed_roots


def _safe_metadata(value: object) -> dict[str, Any]:
    blocked = {
        "password",
        "password_hash",
        "hashed_password",
        "token",
        "api_key",
        "secret",
        "authorization",
        "database_url",
        "invite_code",
    }
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key)[:80]
        if any(part in key.casefold() for part in blocked):
            continue
        if isinstance(raw_value, (str, int, float, bool)) or raw_value is None:
            safe[key] = raw_value if not isinstance(raw_value, str) else raw_value[:500]
        elif isinstance(raw_value, list):
            safe[key] = [
                item if isinstance(item, (int, float, bool)) else str(item)[:200]
                for item in raw_value[:50]
            ]
        elif isinstance(raw_value, dict):
            safe[key] = _safe_metadata(raw_value)
    return json.loads(json.dumps(safe, default=str))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _severity_order() -> tuple[Any, ...]:
    return (
        (DataQualityIssue.severity == "critical").desc(),
        (DataQualityIssue.severity == "high").desc(),
        (DataQualityIssue.severity == "warning").desc(),
    )
