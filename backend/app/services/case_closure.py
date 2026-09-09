from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.case_closure import (
    CaseClosure,
    CaseClosureChecklistItem,
    CaseDeliverable,
)
from app.models.engagement import Engagement
from app.models.finding import Finding
from app.models.finding_evidence import FindingEvidence
from app.models.investigation import Investigation
from app.models.investigation_evidence import InvestigationEvidence
from app.models.investigation_note import InvestigationNote
from app.models.investigation_task import InvestigationTask
from app.models.recon_entity import ReconEntity
from app.models.report import Report
from app.models.target import Target
from app.models.user import User
from app.schemas.case_closure import (
    CaseClosureChecklistItemResponse,
    CaseClosureChecklistStatus,
    CaseClosureChecklistUpdate,
    CaseClosureCloseRequest,
    CaseClosureResponse,
    CaseClosureStatus,
    CaseClosureSubmitRequest,
    CaseClosureUpdate,
    CaseDeliverableCreate,
    CaseDeliverableListResponse,
    CaseDeliverableResponse,
    CaseDeliverableStatus,
    CaseDeliverableType,
    CaseDeliverableUpdate,
    CaseFinalRiskRating,
    CasePackageManifestResponse,
    EvidencePackageSummary,
    PackageReadinessStatus,
)
from app.services.audit import record_event
from app.services.investigation import (
    CASE_ADMIN_ROLES,
    MUTATION_ROLES,
    ensure_investigation_permission,
    get_investigation,
)
from app.services.notification import (
    notify_case_closed,
    notify_case_reopened,
    notify_closure_approved,
    notify_closure_submitted,
    notify_deliverable_ready,
)


class CaseClosureValidationError(Exception):
    pass


class CaseClosureNotFoundError(Exception):
    pass


class CaseDeliverableNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class _ChecklistDefinition:
    key: str
    label: str
    description: str
    status: CaseClosureChecklistStatus
    required: bool = True


async def get_case_closure(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> CaseClosureResponse:
    investigation = await get_investigation(db, user, investigation_id)
    closure = await _get_or_create_closure(db, user, investigation)
    checklist = await _checklist_items(db, investigation.id)
    deliverables = await _deliverables(db, investigation.id)
    evidence_package = await build_evidence_package_summary(db, investigation)
    warnings, blockers = await _closure_warnings(
        db,
        investigation,
        checklist,
        deliverables,
    )
    return _closure_response(
        closure,
        checklist=checklist,
        deliverables=deliverables,
        evidence_package=evidence_package,
        warnings=warnings,
        blockers=blockers,
    )


async def generate_closure_checklist(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> CaseClosureResponse:
    investigation = await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot generate case closure checklists",
    )
    closure = await _get_or_create_closure(db, user, investigation)
    checklist = await _refresh_checklist(db, user, investigation, closure)
    deliverables = await _deliverables(db, investigation.id)
    evidence_package = await build_evidence_package_summary(db, investigation)
    warnings, blockers = await _closure_warnings(
        db,
        investigation,
        checklist,
        deliverables,
    )
    await record_event(
        db,
        action="closure.checklist_generated",
        actor_id=user.id,
        resource_type="case_closure",
        resource_id=closure.id,
        investigation_id=investigation.id,
        metadata={"blocked_items": len(blockers), "warning_count": len(warnings)},
    )
    await db.flush()
    return _closure_response(
        closure,
        checklist=checklist,
        deliverables=deliverables,
        evidence_package=evidence_package,
        warnings=warnings,
        blockers=blockers,
    )


async def update_case_closure(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    body: CaseClosureUpdate,
) -> CaseClosureResponse:
    investigation = await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot update case closure records",
    )
    closure = await _get_or_create_closure(db, user, investigation)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(closure, field, value)
    db.add(closure)
    await db.flush()
    await db.refresh(closure)
    await record_event(
        db,
        action="closure.updated",
        actor_id=user.id,
        resource_type="case_closure",
        resource_id=closure.id,
        investigation_id=investigation.id,
        metadata=updates,
    )
    return await get_case_closure(db, user, investigation_id)


async def submit_case_closure_review(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    body: CaseClosureSubmitRequest,
) -> CaseClosureResponse:
    investigation = await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot submit case closure for review",
    )
    closure = await _get_or_create_closure(db, user, investigation)
    if closure.status not in {"draft", "reopened"}:
        raise CaseClosureValidationError(
            f"Closure cannot move from {closure.status} to in_review"
        )
    if body.closure_summary:
        closure.closure_summary = body.closure_summary
    closure.status = "in_review"
    closure.reviewed_by = user.id
    closure.reviewed_at = _now()
    db.add(closure)
    await db.flush()
    await db.refresh(closure)
    await record_event(
        db,
        action="closure.submitted_for_review",
        actor_id=user.id,
        resource_type="case_closure",
        resource_id=closure.id,
        investigation_id=investigation.id,
        metadata={"status": closure.status},
    )
    await notify_closure_submitted(
        db,
        actor_user_id=user.id,
        investigation_id=investigation.id,
        closure_id=closure.id,
    )
    return await get_case_closure(db, user, investigation_id)


async def approve_case_closure(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> CaseClosureResponse:
    investigation = await get_investigation(db, user, investigation_id)
    await _ensure_closure_admin(
        db,
        user,
        investigation_id,
        "Only owners and admins can approve case closure",
    )
    closure = await _get_or_create_closure(db, user, investigation)
    if closure.status != "in_review":
        raise CaseClosureValidationError(
            f"Closure cannot move from {closure.status} to approved"
        )
    closure.status = "approved"
    closure.approved_by = user.id
    closure.approved_at = _now()
    db.add(closure)
    await db.flush()
    await db.refresh(closure)
    await record_event(
        db,
        action="closure.approved",
        actor_id=user.id,
        resource_type="case_closure",
        resource_id=closure.id,
        investigation_id=investigation.id,
    )
    await notify_closure_approved(
        db,
        actor_user_id=user.id,
        investigation_id=investigation.id,
        closure_id=closure.id,
    )
    return await get_case_closure(db, user, investigation_id)


async def close_case_closure(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    body: CaseClosureCloseRequest,
) -> CaseClosureResponse:
    investigation = await get_investigation(db, user, investigation_id)
    await _ensure_closure_admin(
        db,
        user,
        investigation_id,
        "Only owners and admins can close cases",
    )
    closure = await _get_or_create_closure(db, user, investigation)
    checklist = await _refresh_checklist(db, user, investigation, closure)
    deliverables = await _deliverables(db, investigation.id)
    _warnings, blockers = await _closure_warnings(
        db,
        investigation,
        checklist,
        deliverables,
    )
    if closure.status != "approved" and not body.override_reason:
        raise CaseClosureValidationError(
            "Closure must be approved before closing unless an override reason is provided"
        )
    if blockers and not body.override_reason:
        raise CaseClosureValidationError(
            "Required closure checklist items are incomplete or blocked"
        )
    closure.status = "closed"
    closure.closure_summary = body.closure_summary
    closure.closed_by = user.id
    closure.closed_at = _now()
    if closure.final_risk_rating == "not_assessed":
        closure.final_risk_rating = _final_risk_rating(await _findings(db, investigation.id))
    if investigation.status != "archived":
        investigation.status = "completed"
    if investigation.stage != "archived":
        investigation.stage = "completed"
    db.add_all([closure, investigation])
    await db.flush()
    await db.refresh(closure)
    await record_event(
        db,
        action="closure.closed",
        actor_id=user.id,
        resource_type="case_closure",
        resource_id=closure.id,
        investigation_id=investigation.id,
        metadata={
            "final_risk_rating": closure.final_risk_rating,
            "override": bool(body.override_reason),
            "blocker_count": len(blockers),
        },
    )
    if body.override_reason:
        await record_event(
            db,
            action="case.closure_overridden",
            actor_id=user.id,
            resource_type="case_closure",
            resource_id=closure.id,
            investigation_id=investigation.id,
            metadata={"override_reason": body.override_reason},
        )
    await notify_case_closed(
        db,
        actor_user_id=user.id,
        investigation_id=investigation.id,
        closure_id=closure.id,
    )
    return await get_case_closure(db, user, investigation_id)


async def reopen_case_closure(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> CaseClosureResponse:
    investigation = await get_investigation(db, user, investigation_id)
    await _ensure_closure_admin(
        db,
        user,
        investigation_id,
        "Only owners and admins can reopen cases",
    )
    closure = await _get_or_create_closure(db, user, investigation)
    if closure.status != "closed":
        raise CaseClosureValidationError("Only closed cases can be reopened")
    closure.status = "reopened"
    if investigation.status == "completed":
        investigation.status = "active"
    if investigation.stage == "completed":
        investigation.stage = "analysis"
    db.add_all([closure, investigation])
    await db.flush()
    await db.refresh(closure)
    await record_event(
        db,
        action="closure.reopened",
        actor_id=user.id,
        resource_type="case_closure",
        resource_id=closure.id,
        investigation_id=investigation.id,
    )
    await notify_case_reopened(
        db,
        actor_user_id=user.id,
        investigation_id=investigation.id,
        closure_id=closure.id,
    )
    return await get_case_closure(db, user, investigation_id)


async def get_closure_checklist(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> list[CaseClosureChecklistItemResponse]:
    await get_investigation(db, user, investigation_id)
    return [_checklist_response(item) for item in await _checklist_items(db, investigation_id)]


async def update_closure_checklist_item(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    item_id: uuid.UUID,
    body: CaseClosureChecklistUpdate,
) -> CaseClosureChecklistItemResponse:
    await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot update closure checklist items",
    )
    item = await db.get(CaseClosureChecklistItem, item_id)
    if item is None or item.investigation_id != investigation_id:
        raise CaseClosureNotFoundError("Checklist item not found")
    previous_status = item.status
    item.status = body.status
    if body.description is not None:
        item.description = body.description
    if body.status == "completed":
        item.completed_by = user.id
        item.completed_at = _now()
    elif previous_status == "completed" and body.status != "completed":
        item.completed_by = None
        item.completed_at = None
    db.add(item)
    await db.flush()
    await db.refresh(item)
    await record_event(
        db,
        action="closure.checklist_item_updated",
        actor_id=user.id,
        resource_type="case_closure_checklist_item",
        resource_id=item.id,
        investigation_id=investigation_id,
        metadata={"old_status": previous_status, "new_status": item.status},
    )
    return _checklist_response(item)


async def list_case_deliverables(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    *,
    include_archived: bool = False,
) -> CaseDeliverableListResponse:
    await get_investigation(db, user, investigation_id)
    deliverables = await _deliverables(
        db,
        investigation_id,
        include_archived=include_archived,
    )
    return CaseDeliverableListResponse(
        total=len(deliverables),
        items=[_deliverable_response(item) for item in deliverables],
    )


async def create_case_deliverable(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    body: CaseDeliverableCreate,
) -> CaseDeliverableResponse:
    await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot create case deliverables",
    )
    await _ensure_report_belongs_to_investigation(
        db,
        investigation_id,
        body.report_id,
    )
    deliverable = CaseDeliverable(
        investigation_id=investigation_id,
        title=body.title,
        deliverable_type=body.deliverable_type,
        status=body.status,
        report_id=body.report_id,
        export_format=body.export_format,
        file_reference=body.file_reference,
        created_by=user.id,
    )
    db.add(deliverable)
    await db.flush()
    await db.refresh(deliverable)
    await record_event(
        db,
        action="deliverable.created",
        actor_id=user.id,
        resource_type="case_deliverable",
        resource_id=deliverable.id,
        investigation_id=investigation_id,
        metadata={
            "deliverable_type": deliverable.deliverable_type,
            "status": deliverable.status,
        },
    )
    if deliverable.status == "ready":
        await notify_deliverable_ready(
            db,
            actor_user_id=user.id,
            investigation_id=investigation_id,
            deliverable_id=deliverable.id,
            title=deliverable.title,
            deliverable_type=deliverable.deliverable_type,
        )
    return _deliverable_response(deliverable)


async def update_case_deliverable(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    deliverable_id: uuid.UUID,
    body: CaseDeliverableUpdate,
) -> CaseDeliverableResponse:
    await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot update case deliverables",
    )
    deliverable = await _get_deliverable(db, investigation_id, deliverable_id)
    await _ensure_report_belongs_to_investigation(
        db,
        investigation_id,
        body.report_id,
    )
    previous_status = deliverable.status
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(deliverable, field, value)
    db.add(deliverable)
    await db.flush()
    await db.refresh(deliverable)
    action = "deliverable.approved" if deliverable.status == "approved" else "deliverable.updated"
    await record_event(
        db,
        action=action,
        actor_id=user.id,
        resource_type="case_deliverable",
        resource_id=deliverable.id,
        investigation_id=investigation_id,
        metadata={
            "old_status": previous_status,
            "new_status": deliverable.status,
            "deliverable_type": deliverable.deliverable_type,
        },
    )
    if previous_status != "ready" and deliverable.status == "ready":
        await notify_deliverable_ready(
            db,
            actor_user_id=user.id,
            investigation_id=investigation_id,
            deliverable_id=deliverable.id,
            title=deliverable.title,
            deliverable_type=deliverable.deliverable_type,
        )
    return _deliverable_response(deliverable)


async def archive_case_deliverable(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    deliverable_id: uuid.UUID,
) -> None:
    await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot archive case deliverables",
    )
    deliverable = await _get_deliverable(db, investigation_id, deliverable_id)
    previous_status = deliverable.status
    deliverable.status = "archived"
    db.add(deliverable)
    await record_event(
        db,
        action="deliverable.updated",
        actor_id=user.id,
        resource_type="case_deliverable",
        resource_id=deliverable.id,
        investigation_id=investigation_id,
        metadata={"old_status": previous_status, "new_status": "archived"},
    )
    await db.flush()


async def create_case_package_manifest(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> CasePackageManifestResponse:
    investigation = await get_investigation(db, user, investigation_id)
    await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        "Viewers cannot create deliverable packages",
    )
    deliverables = await _deliverables(db, investigation_id)
    evidence_package = await build_evidence_package_summary(db, investigation)
    included = [
        item
        for item in deliverables
        if item.status in {"ready", "approved", "delivered"}
        and item.deliverable_type != "final_package"
    ]
    missing = _missing_required_deliverables(included)
    warnings = _package_warnings(missing, evidence_package, investigation)
    readiness: PackageReadinessStatus = (
        "missing_required_deliverables"
        if missing
        else "ready_with_warnings"
        if warnings
        else "ready"
    )
    package = await _upsert_package_deliverable(
        db,
        user,
        investigation,
        readiness,
    )
    await db.flush()
    await db.refresh(package)
    await record_event(
        db,
        action="deliverable.packaged",
        actor_id=user.id,
        resource_type="case_deliverable",
        resource_id=package.id,
        investigation_id=investigation_id,
        metadata={
            "readiness_status": readiness,
            "included": len(included),
            "missing": [item for item in missing],
        },
    )
    if package.status == "ready":
        await notify_deliverable_ready(
            db,
            actor_user_id=user.id,
            investigation_id=investigation_id,
            deliverable_id=package.id,
            title=package.title,
            deliverable_type=package.deliverable_type,
        )
    return CasePackageManifestResponse(
        package_id=package.id,
        investigation_id=investigation.id,
        engagement_id=investigation.engagement_id,
        included_deliverables=[_deliverable_response(item) for item in included],
        missing_deliverables=missing,
        warnings=warnings,
        readiness_status=readiness,
        evidence_package=evidence_package,
        generated_at=_now(),
        generated_by=user.id,
    )


async def build_evidence_package_summary(
    db: AsyncSession,
    investigation: Investigation,
) -> EvidencePackageSummary:
    findings = await _findings(db, investigation.id)
    finding_ids = [finding.id for finding in findings]
    finding_evidence = await _finding_evidence(db, finding_ids)
    case_evidence = await _case_evidence(db, investigation.id)
    evidence_finding_ids = {
        item.finding_id for item in finding_evidence if item.finding_id is not None
    } | {item.finding_id for item in case_evidence if item.finding_id is not None}
    findings_with_evidence = sum(1 for finding in findings if finding.id in evidence_finding_ids)
    high_risk = [
        finding.title
        for finding in findings
        if finding.severity in {"critical", "high"} and finding.id in evidence_finding_ids
    ][:5]
    source_counter: Counter[str] = Counter(
        item.source for item in finding_evidence if item.source
    )
    source_counter.update(item.source for item in case_evidence if item.source)
    evidence_count = len(finding_evidence) + len(case_evidence)
    if evidence_count == 0:
        chain_status = "No linked evidence records are stored."
    elif findings and findings_with_evidence < len(findings):
        chain_status = "Some findings do not yet have linked evidence."
    else:
        chain_status = "Stored findings have linked evidence records."
    if investigation.engagement_id is None:
        scope_relation = "No engagement is linked to this investigation."
    else:
        scope_relation = (
            f"Investigation scope review status is "
            f"{investigation.scope_review_status}."
        )
    appendix_readiness = (
        "ready"
        if evidence_count and findings_with_evidence == len(findings)
        else "ready_with_warnings"
        if evidence_count
        else "missing_evidence"
    )
    return EvidencePackageSummary(
        evidence_count=evidence_count,
        findings_with_evidence=findings_with_evidence,
        findings_without_evidence=max(len(findings) - findings_with_evidence, 0),
        high_risk_evidence_highlights=high_risk,
        source_summary=dict(source_counter),
        evidence_chain_status=chain_status,
        scope_relation=scope_relation,
        report_appendix_readiness=appendix_readiness,
    )


async def closure_report_summary(
    db: AsyncSession,
    investigation: Investigation,
) -> list[str]:
    result = await db.execute(
        select(CaseClosure).where(CaseClosure.investigation_id == investigation.id)
    )
    closure = result.scalar_one_or_none()
    checklist = await _checklist_items(db, investigation.id)
    deliverables = await _deliverables(db, investigation.id)
    evidence_package = await build_evidence_package_summary(db, investigation)
    if closure is None:
        return [
            "Case closure workflow has not been prepared.",
            f"Evidence package readiness: {evidence_package.report_appendix_readiness}.",
        ]
    completed = sum(1 for item in checklist if item.status == "completed")
    required = sum(1 for item in checklist if item.required)
    ready_deliverables = sum(
        1 for item in deliverables if item.status in {"ready", "approved", "delivered"}
    )
    lines = [
        f"Closure status: {closure.status}.",
        f"Final risk rating: {closure.final_risk_rating}.",
        f"Closure checklist: {completed}/{max(required, 1)} required items completed.",
        f"Client deliverables ready: {ready_deliverables}.",
        f"Evidence package: {evidence_package.evidence_chain_status}",
    ]
    if closure.closure_summary:
        lines.append(f"Closure summary: {closure.closure_summary}")
    return lines


async def _get_or_create_closure(
    db: AsyncSession,
    user: User,
    investigation: Investigation,
) -> CaseClosure:
    result = await db.execute(
        select(CaseClosure).where(CaseClosure.investigation_id == investigation.id)
    )
    closure = result.scalar_one_or_none()
    if closure is not None:
        return closure
    closure = CaseClosure(
        investigation_id=investigation.id,
        final_risk_rating=_final_risk_rating(await _findings(db, investigation.id)),
    )
    db.add(closure)
    await db.flush()
    await db.refresh(closure)
    await record_event(
        db,
        action="closure.created",
        actor_id=user.id,
        resource_type="case_closure",
        resource_id=closure.id,
        investigation_id=investigation.id,
    )
    return closure


async def _refresh_checklist(
    db: AsyncSession,
    user: User,
    investigation: Investigation,
    closure: CaseClosure,
) -> list[CaseClosureChecklistItem]:
    definitions = await _build_checklist_definitions(db, investigation)
    existing = {
        item.key: item for item in await _checklist_items(db, investigation.id)
    }
    refreshed: list[CaseClosureChecklistItem] = []
    for definition in definitions:
        item = existing.get(definition.key)
        if item is None:
            item = CaseClosureChecklistItem(
                investigation_id=investigation.id,
                closure_id=closure.id,
                key=definition.key,
                label=definition.label,
                description=definition.description,
                status=definition.status,
                required=definition.required,
            )
        else:
            item.closure_id = closure.id
            item.label = definition.label
            item.description = definition.description
            item.required = definition.required
            if item.status != "completed" or definition.status == "blocked":
                item.status = definition.status
            if item.status == "completed" and item.completed_by is None:
                item.completed_by = user.id
                item.completed_at = _now()
        db.add(item)
        refreshed.append(item)
    await db.flush()
    return await _checklist_items(db, investigation.id)


async def _build_checklist_definitions(
    db: AsyncSession,
    investigation: Investigation,
) -> list[_ChecklistDefinition]:
    counts = await _closure_counts(db, investigation.id)
    engagement = (
        await db.get(Engagement, investigation.engagement_id)
        if investigation.engagement_id
        else None
    )
    unresolved_high = await _unresolved_high_risk_count(db, investigation.id)
    ready_deliverables = await _ready_deliverable_count(db, investigation.id)
    return [
        _definition(
            "case_overview",
            "Investigation overview is complete",
            bool(investigation.title and investigation.description),
            "Title and description are present.",
        ),
        _definition(
            "engagement_scope_reviewed",
            "Engagement and scope status reviewed",
            investigation.engagement_id is not None
            and investigation.scope_review_status in {"in_scope", "out_of_scope"},
            (
                "Linked engagement scope is reviewed."
                if investigation.engagement_id
                else "No engagement is linked; mark not applicable or link an engagement."
            ),
            required=investigation.engagement_id is not None,
            not_applicable=investigation.engagement_id is None,
        ),
        _definition(
            "authorization_reviewed",
            "Authorization status reviewed",
            engagement is not None and engagement.authorization_status == "approved",
            (
                f"Authorization status: {engagement.authorization_status}."
                if engagement is not None
                else "No engagement authorization metadata is linked."
            ),
            required=engagement is not None,
            not_applicable=engagement is None,
        ),
        _definition(
            "targets_recon_reviewed",
            "Targets and passive recon reviewed",
            counts["targets"] > 0 and counts["recon_entities"] > 0,
            f"Targets: {counts['targets']}; recon entities: {counts['recon_entities']}.",
        ),
        _definition(
            "findings_reviewed",
            "Findings reviewed",
            counts["findings"] > 0,
            f"Stored findings: {counts['findings']}.",
        ),
        _definition(
            "evidence_reviewed",
            "Evidence reviewed",
            counts["evidence"] > 0,
            f"Linked evidence records: {counts['evidence']}.",
        ),
        _definition(
            "remediation_reviewed",
            "Remediation status reviewed",
            counts["tasks"] > 0 or counts["accepted_risk"] > 0,
            (
                f"Tasks: {counts['tasks']}; accepted risks: "
                f"{counts['accepted_risk']}."
            ),
        ),
        _definition(
            "report_generated",
            "Final reports generated",
            counts["ready_reports"] > 0,
            f"Ready reports: {counts['ready_reports']}.",
        ),
        _definition(
            "executive_summary_available",
            "Executive summary available",
            counts["executive_summaries"] > 0,
            f"Executive summary notes: {counts['executive_summaries']}.",
            required=False,
        ),
        _definition(
            "unresolved_high_acknowledged",
            "Unresolved critical/high findings acknowledged",
            unresolved_high == 0,
            (
                "No unresolved critical/high findings are blocking closure."
                if unresolved_high == 0
                else f"{unresolved_high} unresolved critical/high findings remain."
            ),
            blocked=unresolved_high > 0,
        ),
        _definition(
            "audit_trail_available",
            "Audit trail available",
            counts["audit_events"] > 0,
            f"Audit events: {counts['audit_events']}.",
        ),
        _definition(
            "final_deliverables_prepared",
            "Final deliverables prepared",
            ready_deliverables > 0,
            f"Ready or approved deliverables: {ready_deliverables}.",
        ),
    ]


def _definition(
    key: str,
    label: str,
    passed: bool,
    description: str,
    *,
    required: bool = True,
    blocked: bool = False,
    not_applicable: bool = False,
) -> _ChecklistDefinition:
    status: CaseClosureChecklistStatus = (
        "not_applicable"
        if not_applicable
        else "completed"
        if passed
        else "blocked"
        if blocked
        else "pending"
    )
    return _ChecklistDefinition(
        key=key,
        label=label,
        description=description,
        status=status,
        required=required,
    )


async def _closure_warnings(
    db: AsyncSession,
    investigation: Investigation,
    checklist: list[CaseClosureChecklistItem],
    deliverables: list[CaseDeliverable],
) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    blockers = [
        item.label
        for item in checklist
        if item.required and item.status in {"pending", "blocked"}
    ]
    if investigation.engagement_id is None:
        warnings.append("No engagement is linked to this investigation.")
    else:
        engagement = await db.get(Engagement, investigation.engagement_id)
        if engagement is None:
            warnings.append("Linked engagement metadata is unavailable.")
        elif engagement.authorization_status != "approved":
            warnings.append(
                f"Engagement authorization is {engagement.authorization_status}."
            )
    unresolved = await _unresolved_high_risk_count(db, investigation.id)
    if unresolved:
        warnings.append(
            f"{unresolved} unresolved critical/high findings require acknowledgement."
        )
    missing = _missing_required_deliverables(deliverables)
    if missing:
        warnings.append(
            "Missing client-ready deliverables: "
            + ", ".join(item.replace("_", " ") for item in missing)
            + "."
        )
    return warnings, blockers


async def _closure_counts(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> dict[str, int]:
    findings = await _findings(db, investigation_id)
    finding_ids = [finding.id for finding in findings]
    finding_evidence = await _finding_evidence(db, finding_ids)
    case_evidence = await _case_evidence(db, investigation_id)
    return {
        "targets": await _count(db, Target, Target.investigation_id == investigation_id),
        "recon_entities": await _count(
            db,
            ReconEntity,
            ReconEntity.investigation_id == investigation_id,
        ),
        "findings": len(findings),
        "evidence": len(finding_evidence) + len(case_evidence),
        "tasks": await _count(
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
        "ready_reports": await _count(
            db,
            Report,
            Report.investigation_id == investigation_id,
            Report.status.in_(("ready", "archived")),
        ),
        "executive_summaries": await _count(
            db,
            InvestigationNote,
            InvestigationNote.investigation_id == investigation_id,
            InvestigationNote.note_type.in_(("executive", "executive_note")),
            InvestigationNote.archived.is_(False),
        ),
        "audit_events": await _count(
            db,
            AuditLog,
            AuditLog.investigation_id == investigation_id,
        ),
    }


async def _count(db: AsyncSession, model: Any, *conditions: Any) -> int:
    result = await db.execute(select(func.count()).select_from(model).where(*conditions))
    return int(result.scalar_one())


async def _findings(db: AsyncSession, investigation_id: uuid.UUID) -> list[Finding]:
    result = await db.execute(
        select(Finding)
        .where(Finding.investigation_id == investigation_id)
        .order_by(Finding.risk_score.desc(), Finding.created_at.desc())
    )
    return list(result.scalars().all())


async def _finding_evidence(
    db: AsyncSession,
    finding_ids: list[uuid.UUID],
) -> list[FindingEvidence]:
    if not finding_ids:
        return []
    result = await db.execute(
        select(FindingEvidence).where(FindingEvidence.finding_id.in_(finding_ids))
    )
    return list(result.scalars().all())


async def _case_evidence(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[InvestigationEvidence]:
    result = await db.execute(
        select(InvestigationEvidence).where(
            InvestigationEvidence.investigation_id == investigation_id,
            InvestigationEvidence.archived_at.is_(None),
        )
    )
    return list(result.scalars().all())


async def _checklist_items(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> list[CaseClosureChecklistItem]:
    result = await db.execute(
        select(CaseClosureChecklistItem)
        .where(CaseClosureChecklistItem.investigation_id == investigation_id)
        .order_by(CaseClosureChecklistItem.created_at, CaseClosureChecklistItem.key)
    )
    return list(result.scalars().all())


async def _deliverables(
    db: AsyncSession,
    investigation_id: uuid.UUID,
    *,
    include_archived: bool = False,
) -> list[CaseDeliverable]:
    statement = select(CaseDeliverable).where(
        CaseDeliverable.investigation_id == investigation_id
    )
    if not include_archived:
        statement = statement.where(CaseDeliverable.status != "archived")
    result = await db.execute(statement.order_by(CaseDeliverable.created_at.desc()))
    return list(result.scalars().all())


async def _get_deliverable(
    db: AsyncSession,
    investigation_id: uuid.UUID,
    deliverable_id: uuid.UUID,
) -> CaseDeliverable:
    deliverable = await db.get(CaseDeliverable, deliverable_id)
    if deliverable is None or deliverable.investigation_id != investigation_id:
        raise CaseDeliverableNotFoundError("Deliverable not found")
    return deliverable


async def _ensure_report_belongs_to_investigation(
    db: AsyncSession,
    investigation_id: uuid.UUID,
    report_id: uuid.UUID | None,
) -> None:
    if report_id is None:
        return
    report = await db.get(Report, report_id)
    if report is None or report.investigation_id != investigation_id:
        raise CaseClosureValidationError("Linked report does not belong to investigation")


async def _unresolved_high_risk_count(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Finding)
        .where(
            Finding.investigation_id == investigation_id,
            Finding.severity.in_(("critical", "high")),
            Finding.status.notin_(("mitigated", "false_positive", "archived")),
            Finding.remediation_status.notin_(("remediated", "accepted_risk")),
        )
    )
    return int(result.scalar_one())


async def _ready_deliverable_count(db: AsyncSession, investigation_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(CaseDeliverable)
        .where(
            CaseDeliverable.investigation_id == investigation_id,
            CaseDeliverable.status.in_(("ready", "approved", "delivered")),
            CaseDeliverable.deliverable_type != "final_package",
        )
    )
    return int(result.scalar_one())


def _missing_required_deliverables(
    deliverables: list[CaseDeliverable],
) -> list[CaseDeliverableType]:
    ready_types = {
        item.deliverable_type
        for item in deliverables
        if item.status in {"ready", "approved", "delivered"}
    }
    required: tuple[CaseDeliverableType, ...] = (
        "executive_report",
        "technical_report",
        "evidence_appendix",
    )
    return [item for item in required if item not in ready_types]


def _package_warnings(
    missing: list[CaseDeliverableType],
    evidence_package: EvidencePackageSummary,
    investigation: Investigation,
) -> list[str]:
    warnings: list[str] = []
    if missing:
        warnings.append(
            "Required deliverables are missing from the final package manifest."
        )
    if evidence_package.findings_without_evidence:
        warnings.append(
            f"{evidence_package.findings_without_evidence} findings do not have "
            "linked evidence records."
        )
    if investigation.engagement_id is None:
        warnings.append("No engagement is linked for client scope confirmation.")
    if investigation.scope_review_status in {"not_reviewed", "pending_review"}:
        warnings.append("Investigation scope review is not finalized.")
    return warnings


async def _upsert_package_deliverable(
    db: AsyncSession,
    user: User,
    investigation: Investigation,
    readiness: PackageReadinessStatus,
) -> CaseDeliverable:
    result = await db.execute(
        select(CaseDeliverable).where(
            CaseDeliverable.investigation_id == investigation.id,
            CaseDeliverable.deliverable_type == "final_package",
            CaseDeliverable.status != "archived",
        )
    )
    package = result.scalar_one_or_none()
    if package is None:
        package = CaseDeliverable(
            investigation_id=investigation.id,
            title="Final client deliverables package",
            deliverable_type="final_package",
            status="ready" if readiness != "missing_required_deliverables" else "draft",
            file_reference=f"manifest://investigations/{investigation.id}/deliverables/final-package",
            created_by=user.id,
        )
    else:
        package.status = "ready" if readiness != "missing_required_deliverables" else "draft"
        package.file_reference = (
            f"manifest://investigations/{investigation.id}/deliverables/final-package"
        )
    db.add(package)
    return package


def _final_risk_rating(findings: list[Finding]) -> CaseFinalRiskRating:
    severities = {finding.severity for finding in findings}
    if "critical" in severities:
        return "critical"
    if "high" in severities:
        return "high"
    if "medium" in severities:
        return "elevated"
    if "low" in severities:
        return "moderate"
    if "info" in severities:
        return "low"
    return "not_assessed"


async def _ensure_closure_admin(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    message: str,
) -> None:
    await ensure_investigation_permission(db, user, investigation_id, CASE_ADMIN_ROLES, message)


def _closure_response(
    closure: CaseClosure,
    *,
    checklist: list[CaseClosureChecklistItem],
    deliverables: list[CaseDeliverable],
    evidence_package: EvidencePackageSummary,
    warnings: list[str],
    blockers: list[str],
) -> CaseClosureResponse:
    return CaseClosureResponse(
        id=closure.id,
        investigation_id=closure.investigation_id,
        status=_closure_status(closure.status),
        closure_summary=closure.closure_summary,
        final_risk_rating=_risk_rating(closure.final_risk_rating),
        reviewed_by=closure.reviewed_by,
        approved_by=closure.approved_by,
        closed_by=closure.closed_by,
        reviewed_at=closure.reviewed_at,
        approved_at=closure.approved_at,
        closed_at=closure.closed_at,
        checklist=[_checklist_response(item) for item in checklist],
        deliverables=[_deliverable_response(item) for item in deliverables],
        evidence_package=evidence_package,
        warnings=warnings,
        blockers=blockers,
        created_at=closure.created_at,
        updated_at=closure.updated_at,
    )


def _checklist_response(
    item: CaseClosureChecklistItem,
) -> CaseClosureChecklistItemResponse:
    return CaseClosureChecklistItemResponse(
        id=item.id,
        investigation_id=item.investigation_id,
        closure_id=item.closure_id,
        key=item.key,
        label=item.label,
        description=item.description,
        status=_checklist_status(item.status),
        required=item.required,
        completed_by=item.completed_by,
        completed_at=item.completed_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _deliverable_response(item: CaseDeliverable) -> CaseDeliverableResponse:
    return CaseDeliverableResponse(
        id=item.id,
        investigation_id=item.investigation_id,
        title=item.title,
        deliverable_type=_deliverable_type(item.deliverable_type),
        status=_deliverable_status(item.status),
        report_id=item.report_id,
        export_format=cast(Any, item.export_format),
        file_reference=item.file_reference,
        created_by=item.created_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _closure_status(value: str) -> CaseClosureStatus:
    if value in {"draft", "in_review", "approved", "closed", "reopened"}:
        return cast(CaseClosureStatus, value)
    return "draft"


def _checklist_status(value: str) -> CaseClosureChecklistStatus:
    if value in {"pending", "completed", "blocked", "not_applicable"}:
        return cast(CaseClosureChecklistStatus, value)
    return "pending"


def _risk_rating(value: str) -> CaseFinalRiskRating:
    if value in {"low", "moderate", "elevated", "high", "critical", "not_assessed"}:
        return cast(CaseFinalRiskRating, value)
    return "not_assessed"


def _deliverable_type(value: str) -> CaseDeliverableType:
    if value in {
        "executive_report",
        "technical_report",
        "evidence_appendix",
        "remediation_plan",
        "scope_summary",
        "audit_summary",
        "final_package",
    }:
        return cast(CaseDeliverableType, value)
    return "final_package"


def _deliverable_status(value: str) -> CaseDeliverableStatus:
    if value in {"draft", "ready", "approved", "delivered", "archived"}:
        return cast(CaseDeliverableStatus, value)
    return "draft"


def _now() -> datetime:
    return datetime.now(UTC)
