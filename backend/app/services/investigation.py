from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finding import Finding
from app.models.finding_evidence import FindingEvidence
from app.models.investigation import Investigation
from app.models.investigation_enrichment import InvestigationEnrichment
from app.models.investigation_member import InvestigationMember
from app.models.investigation_workflow_event import InvestigationWorkflowEvent
from app.models.recon_entity import ReconEntity
from app.models.recon_relationship import ReconRelationship
from app.models.user import User
from app.schemas.investigation import (
    InvestigationCreate,
    InvestigationGraphEdge,
    InvestigationGraphFinding,
    InvestigationGraphFindingEdge,
    InvestigationGraphNode,
    InvestigationGraphResponse,
    InvestigationGraphRiskSummary,
    InvestigationGraphTimelineEvent,
    InvestigationUpdate,
    MemberResponse,
)
from app.schemas.recon import EntityType, RelationshipType
from app.services.audit import record_event

_RECON_ENTITY_TYPES: tuple[EntityType, ...] = (
    "Domain",
    "Subdomain",
    "IPAddress",
    "ASN",
    "Certificate",
    "Organization",
    "Service",
    "Technology",
)


class InvestigationNotFoundError(Exception):
    pass


class ForbiddenError(Exception):
    pass


class MemberAlreadyExistsError(Exception):
    pass


class LastOwnerError(Exception):
    pass


class InvalidWorkflowTransitionError(Exception):
    pass


class MemberValidationError(Exception):
    pass


INVESTIGATION_ROLES: tuple[str, ...] = ("owner", "admin", "analyst", "viewer")
MUTATION_ROLES: frozenset[str] = frozenset({"owner", "admin", "analyst"})
CASE_ADMIN_ROLES: frozenset[str] = frozenset({"owner", "admin"})
OWNER_ROLES: frozenset[str] = frozenset({"owner"})
ROLE_RANK: dict[str, int] = {
    "viewer": 10,
    "analyst": 20,
    "admin": 30,
    "owner": 40,
}


_ALLOWED_WORKFLOW_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"active"},
    "active": {"triage", "review"},
    "triage": {"monitoring", "remediation"},
    "monitoring": {"remediation"},
    "remediation": {"validated"},
    "validated": {"archived"},
    "review": {"remediated", "archived"},
    "remediated": {"archived"},
    "archived": set(),
}


async def _get_membership(
    db: AsyncSession,
    investigation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> InvestigationMember | None:
    result = await db.execute(
        select(InvestigationMember).where(
            InvestigationMember.investigation_id == investigation_id,
            InvestigationMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_membership(
    db: AsyncSession,
    investigation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> InvestigationMember | None:
    return await _get_membership(db, investigation_id, user_id)


async def _get_member_by_id(
    db: AsyncSession,
    investigation_id: uuid.UUID,
    member_id: uuid.UUID,
) -> InvestigationMember | None:
    result = await db.execute(
        select(InvestigationMember).where(
            InvestigationMember.investigation_id == investigation_id,
            InvestigationMember.id == member_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is not None:
        return member
    return await _get_membership(db, investigation_id, member_id)


async def ensure_investigation_permission(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    allowed_roles: frozenset[str] | set[str],
    message: str,
) -> InvestigationMember | None:
    if user.role == "admin":
        return None
    membership = await _get_membership(db, investigation_id, user.id)
    if membership is None:
        raise InvestigationNotFoundError("Investigation not found")
    if membership.role not in allowed_roles:
        await record_event(
            db,
            action="permission.denied",
            actor_id=user.id,
            resource_type="investigation",
            resource_id=investigation_id,
            investigation_id=investigation_id,
            metadata={
                "required_roles": sorted(allowed_roles),
                "actual_role": membership.role,
                "reason": message,
            },
        )
        raise ForbiddenError(message)
    return membership


async def ensure_mutation_permission(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    message: str,
) -> InvestigationMember | None:
    return await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        MUTATION_ROLES,
        message,
    )


async def ensure_case_admin_permission(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    message: str,
) -> InvestigationMember | None:
    return await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        CASE_ADMIN_ROLES,
        message,
    )


async def ensure_owner_permission(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    message: str,
) -> InvestigationMember | None:
    return await ensure_investigation_permission(
        db,
        user,
        investigation_id,
        OWNER_ROLES,
        message,
    )


async def _ensure_owner_or_admin(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    message: str,
) -> None:
    await ensure_owner_permission(db, user, investigation_id, message)


async def create_investigation(
    db: AsyncSession,
    user: User,
    data: InvestigationCreate,
) -> Investigation:
    investigation = Investigation(
        title=data.title,
        description=data.description,
        owner_id=user.id,
        status="draft",
        authorization_statement=data.authorization_statement,
        scope_definition=data.scope_definition,
    )
    db.add(investigation)
    await db.flush()
    _record_workflow_event(
        db,
        investigation_id=investigation.id,
        actor_id=user.id,
        from_status=None,
        to_status=investigation.status,
        reason="Investigation created",
    )

    db.add(
        InvestigationMember(
            investigation_id=investigation.id,
            user_id=user.id,
            role="owner",
            invited_by=user.id,
        )
    )
    await db.flush()
    await db.refresh(investigation)
    return investigation


async def list_investigations(
    db: AsyncSession,
    user: User,
    *,
    status: str | None = None,
    scope: str = "all",
    skip: int = 0,
    limit: int = 20,
) -> tuple[int, list[Investigation]]:
    filters = []
    if status is not None:
        filters.append(Investigation.status == status)
    if scope == "active":
        filters.append(Investigation.status != "archived")
    elif scope == "archived":
        filters.append(Investigation.status == "archived")
    elif scope == "needs_review":
        filters.append(Investigation.status.in_(("triage", "review", "validated")))

    if user.role == "admin":
        base = select(Investigation).where(*filters)
        count_stmt = select(func.count()).select_from(Investigation).where(*filters)
    else:
        member_filters = [InvestigationMember.user_id == user.id]
        if scope == "owned_by_me":
            member_filters.append(InvestigationMember.role == "owner")
        elif scope == "viewer_only":
            member_filters.append(InvestigationMember.role == "viewer")
        elif scope == "assigned_to_me":
            filters.append(
                (Investigation.owner_id == user.id)
                | (Investigation.reviewer_id == user.id)
            )
        base = (
            select(Investigation)
            .join(
                InvestigationMember,
                Investigation.id == InvestigationMember.investigation_id,
            )
            .where(*member_filters, *filters)
        )
        count_stmt = (
            select(func.count())
            .select_from(Investigation)
            .join(
                InvestigationMember,
                Investigation.id == InvestigationMember.investigation_id,
            )
            .where(*member_filters, *filters)
        )

    total = int((await db.execute(count_stmt)).scalar_one())
    result = await db.execute(
        base.order_by(Investigation.created_at.desc()).offset(skip).limit(limit)
    )
    return total, list(result.scalars().all())


async def get_investigation(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> Investigation:
    investigation = await db.get(Investigation, investigation_id)
    if investigation is None:
        raise InvestigationNotFoundError("Investigation not found")
    if user.role != "admin":
        membership = await _get_membership(db, investigation_id, user.id)
        if membership is None:
            raise InvestigationNotFoundError("Investigation not found")
    return investigation


async def update_investigation(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    data: InvestigationUpdate,
) -> Investigation:
    investigation = await get_investigation(db, user, investigation_id)
    await ensure_case_admin_permission(
        db,
        user,
        investigation_id,
        "Only investigation owners or admins can update investigations",
    )
    updates = data.model_dump(exclude_unset=True)
    if "status" in updates and updates["status"] != investigation.status:
        target_status = str(updates["status"])
        await _apply_status_transition(
            db,
            user=user,
            investigation=investigation,
            target_status=target_status,
            reason="Investigation workflow status updated",
        )
    if "reviewer_id" in updates and updates["reviewer_id"] is not None:
        await ensure_user_is_member(
            db,
            investigation_id,
            updates["reviewer_id"],
            "Reviewer must be an investigation member",
        )
        await record_event(
            db,
            action="analyst.assigned",
            actor_id=user.id,
            resource_type="investigation",
            resource_id=investigation.id,
            investigation_id=investigation.id,
            metadata={"reviewer_id": str(updates["reviewer_id"])},
        )
    for field, value in updates.items():
        setattr(investigation, field, value)
    db.add(investigation)
    await db.flush()
    await db.refresh(investigation)
    return investigation


async def update_investigation_status(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    target_status: str,
    *,
    reason: str | None = None,
) -> Investigation:
    investigation = await get_investigation(db, user, investigation_id)
    await ensure_case_admin_permission(
        db,
        user,
        investigation_id,
        "Only investigation owners or admins can update investigation status",
    )
    if target_status != investigation.status:
        await _apply_status_transition(
            db,
            user=user,
            investigation=investigation,
            target_status=target_status,
            reason=reason or "Investigation workflow status updated",
        )
        investigation.status = target_status
    db.add(investigation)
    await db.flush()
    await db.refresh(investigation)
    return investigation


async def archive_investigation(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> None:
    investigation = await get_investigation(db, user, investigation_id)
    await ensure_owner_permission(
        db,
        user,
        investigation_id,
        "Only owners can archive investigations",
    )
    previous_status = investigation.status
    investigation.status = "archived"
    db.add(investigation)
    _record_workflow_event(
        db,
        investigation_id=investigation.id,
        actor_id=user.id,
        from_status=previous_status,
        to_status="archived",
        reason="Investigation archived",
    )
    await record_event(
        db,
        action="workflow.status_changed",
        actor_id=user.id,
        resource_type="investigation",
        resource_id=investigation.id,
        investigation_id=investigation.id,
        metadata={
            "from_status": previous_status,
            "to_status": "archived",
        },
    )


async def list_members(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> list[InvestigationMember]:
    await get_investigation(db, user, investigation_id)
    result = await db.execute(
        select(InvestigationMember)
        .where(InvestigationMember.investigation_id == investigation_id)
        .order_by(InvestigationMember.created_at)
    )
    return list(result.scalars().all())


async def list_member_responses(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> list[MemberResponse]:
    members = await list_members(db, user, investigation_id)
    return await _member_responses(db, members)


async def get_investigation_graph(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    *,
    entity_types: list[EntityType] | None = None,
    relationship_types: list[RelationshipType] | None = None,
) -> InvestigationGraphResponse:
    await get_investigation(db, user, investigation_id)

    entity_stmt = select(ReconEntity).where(
        ReconEntity.investigation_id == investigation_id
    )
    if entity_types:
        entity_stmt = entity_stmt.where(ReconEntity.entity_type.in_(entity_types))
    entity_stmt = entity_stmt.order_by(ReconEntity.entity_type, ReconEntity.value)
    entity_result = await db.execute(entity_stmt)
    nodes = list(entity_result.scalars().all())
    node_ids = {node.id for node in nodes}

    edges: list[ReconRelationship] = []
    if node_ids:
        relationship_stmt = select(ReconRelationship).where(
            ReconRelationship.investigation_id == investigation_id,
            ReconRelationship.source_entity_id.in_(node_ids),
            ReconRelationship.target_entity_id.in_(node_ids),
        )
        if relationship_types:
            relationship_stmt = relationship_stmt.where(
                ReconRelationship.relationship_type.in_(relationship_types)
            )
        relationship_stmt = relationship_stmt.order_by(
            ReconRelationship.relationship_type,
            ReconRelationship.created_at,
        )
        relationship_result = await db.execute(relationship_stmt)
        edges = list(relationship_result.scalars().all())

    timeline_result = await db.execute(
        select(InvestigationEnrichment)
        .where(InvestigationEnrichment.investigation_id == investigation_id)
        .order_by(InvestigationEnrichment.created_at.desc())
    )
    timeline = list(timeline_result.scalars().all())
    graph_findings, finding_edges = await _graph_findings(db, investigation_id)

    return InvestigationGraphResponse(
        investigation_id=investigation_id,
        nodes=[InvestigationGraphNode.model_validate(node) for node in nodes],
        edges=[InvestigationGraphEdge.model_validate(edge) for edge in edges],
        risk_summary=_build_graph_risk_summary(nodes),
        timeline=[
            InvestigationGraphTimelineEvent.model_validate(event) for event in timeline
        ],
        findings=graph_findings,
        finding_edges=finding_edges,
    )


def _build_graph_risk_summary(
    entities: list[ReconEntity],
) -> InvestigationGraphRiskSummary:
    counts: dict[EntityType, int] = {
        entity_type: 0 for entity_type in _RECON_ENTITY_TYPES
    }
    for entity in entities:
        if entity.entity_type in counts:
            counts[entity.entity_type] += 1

    signals: list[str] = [
        "Phase 1C placeholder only: risk scoring is not performed yet."
    ]
    service_count = counts["Service"]
    ip_count = counts["IPAddress"]
    certificate_count = counts["Certificate"]
    if service_count:
        signals.append(f"{service_count} service entities are present in the graph.")
    if ip_count:
        signals.append(f"{ip_count} IP address entities are present in the graph.")
    if certificate_count:
        signals.append(
            f"{certificate_count} certificate entities are present in the graph."
        )

    return InvestigationGraphRiskSummary(
        total_entities=len(entities),
        entity_counts=counts,
        risk_level="not_assessed",
        signals=signals,
    )


async def _graph_findings(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> tuple[list[InvestigationGraphFinding], list[InvestigationGraphFindingEdge]]:
    finding_result = await db.execute(
        select(Finding)
        .where(Finding.investigation_id == investigation_id)
        .order_by(Finding.risk_score.desc(), Finding.created_at.desc())
    )
    findings = list(finding_result.scalars().all())
    if not findings:
        return [], []

    finding_ids = [finding.id for finding in findings]
    evidence_result = await db.execute(
        select(FindingEvidence).where(FindingEvidence.finding_id.in_(finding_ids))
    )
    evidence_by_finding: dict[uuid.UUID, list[FindingEvidence]] = {}
    edges: list[InvestigationGraphFindingEdge] = []
    for evidence in evidence_result.scalars().all():
        evidence_by_finding.setdefault(evidence.finding_id, []).append(evidence)
        if (
            evidence.recon_entity_id is not None
            or evidence.threat_finding_id is not None
        ):
            edges.append(
                InvestigationGraphFindingEdge(
                    finding_id=evidence.finding_id,
                    entity_id=evidence.recon_entity_id,
                    threat_finding_id=evidence.threat_finding_id,
                )
            )

    graph_findings: list[InvestigationGraphFinding] = []
    for finding in findings:
        evidence_items = evidence_by_finding.get(finding.id, [])
        graph_findings.append(
            InvestigationGraphFinding(
                id=finding.id,
                title=finding.title,
                severity=finding.severity,  # type: ignore[arg-type]
                status=finding.status,  # type: ignore[arg-type]
                risk_score=finding.risk_score,
                source=finding.source,
                linked_entity_ids=[
                    item.recon_entity_id
                    for item in evidence_items
                    if item.recon_entity_id is not None
                ],
                threat_finding_ids=[
                    item.threat_finding_id
                    for item in evidence_items
                    if item.threat_finding_id is not None
                ],
            )
        )
    return graph_findings, edges


def _ensure_valid_workflow_transition(
    current_status: str,
    target_status: str,
) -> None:
    allowed = _ALLOWED_WORKFLOW_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise InvalidWorkflowTransitionError(
            f"Invalid workflow transition from {current_status} to {target_status}"
        )


async def _apply_status_transition(
    db: AsyncSession,
    *,
    user: User,
    investigation: Investigation,
    target_status: str,
    reason: str,
) -> None:
    _ensure_valid_workflow_transition(investigation.status, target_status)
    _record_workflow_event(
        db,
        investigation_id=investigation.id,
        actor_id=user.id,
        from_status=investigation.status,
        to_status=target_status,
        reason=reason,
    )
    await record_event(
        db,
        action="workflow.status_changed",
        actor_id=user.id,
        resource_type="investigation",
        resource_id=investigation.id,
        investigation_id=investigation.id,
        metadata={
            "from_status": investigation.status,
            "to_status": target_status,
            "reason": reason,
        },
    )


def _record_workflow_event(
    db: AsyncSession,
    *,
    investigation_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    from_status: str | None,
    to_status: str,
    reason: str,
) -> None:
    db.add(
        InvestigationWorkflowEvent(
            investigation_id=investigation_id,
            actor_id=actor_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
        )
    )


async def add_member(
    db: AsyncSession,
    requesting_user: User,
    investigation_id: uuid.UUID,
    target_user_id: uuid.UUID | None,
    role: str,
    *,
    email: str | None = None,
    username: str | None = None,
) -> MemberResponse:
    await get_investigation(db, requesting_user, investigation_id)
    await ensure_owner_permission(
        db,
        requesting_user,
        investigation_id,
        "Only investigation owners can add members",
    )

    target_user = await _resolve_member_user(
        db,
        user_id=target_user_id,
        email=email,
        username=username,
    )
    if target_user is None:
        raise InvestigationNotFoundError("User not found")
    persisted_role = "analyst" if role == "collaborator" else role
    if target_user.id == requesting_user.id and persisted_role != "viewer":
        raise MemberValidationError("Users cannot promote themselves")

    existing = await _get_membership(db, investigation_id, target_user.id)
    if existing is not None:
        raise MemberAlreadyExistsError("User is already a member")

    member = InvestigationMember(
        id=uuid.uuid4(),
        investigation_id=investigation_id,
        user_id=target_user.id,
        role=persisted_role,
        invited_by=requesting_user.id,
    )
    db.add(member)
    _record_workflow_event(
        db,
        investigation_id=investigation_id,
        actor_id=requesting_user.id,
        from_status=None,
        to_status="active",
        reason=f"Member added: {target_user.username} as {persisted_role}",
    )
    await record_event(
        db,
        action="investigation.member_added",
        actor_id=requesting_user.id,
        resource_type="investigation_member",
        resource_id=member.id,
        investigation_id=investigation_id,
        metadata={
            "target_user": str(target_user.id),
            "after_role": persisted_role,
            "actor": str(requesting_user.id),
        },
    )
    await db.flush()
    await db.refresh(member)
    response = (await _member_responses(db, [member]))[0]
    if role == "collaborator":
        return response.model_copy(update={"role": "collaborator"})
    return response


async def update_member_role(
    db: AsyncSession,
    requesting_user: User,
    investigation_id: uuid.UUID,
    member_id: uuid.UUID,
    role: str | None,
    *,
    transfer_ownership: bool = False,
) -> MemberResponse:
    await get_investigation(db, requesting_user, investigation_id)
    await ensure_owner_permission(
        db,
        requesting_user,
        investigation_id,
        "Only investigation owners can change member roles",
    )
    member = await _get_member_by_id(db, investigation_id, member_id)
    if member is None:
        raise InvestigationNotFoundError("Member not found")
    if role is None:
        role = member.role
    if member.user_id == requesting_user.id and _role_rank(role) > _role_rank(member.role):
        raise MemberValidationError("Users cannot promote themselves")
    if member.role == "owner" and role != "owner":
        await _ensure_not_last_owner(db, investigation_id)
    previous_role = member.role
    member.role = role
    if transfer_ownership or role == "owner":
        investigation = await db.get(Investigation, investigation_id)
        if investigation is not None and investigation.owner_id != member.user_id:
            previous_owner = investigation.owner_id
            investigation.owner_id = member.user_id
            db.add(investigation)
            await record_event(
                db,
                action="investigation.owner_transferred",
                actor_id=requesting_user.id,
                resource_type="investigation",
                resource_id=investigation_id,
                investigation_id=investigation_id,
                metadata={
                    "previous_owner": str(previous_owner),
                    "target_user": str(member.user_id),
                    "actor": str(requesting_user.id),
                },
            )
    db.add(member)
    _record_workflow_event(
        db,
        investigation_id=investigation_id,
        actor_id=requesting_user.id,
        from_status=None,
        to_status="active",
        reason=f"Member role changed from {previous_role} to {role}",
    )
    await record_event(
        db,
        action="investigation.member_role_changed",
        actor_id=requesting_user.id,
        resource_type="investigation_member",
        resource_id=member.id,
        investigation_id=investigation_id,
        metadata={
            "before_role": previous_role,
            "after_role": role,
            "target_user": str(member.user_id),
            "actor": str(requesting_user.id),
        },
    )
    await db.flush()
    await db.refresh(member)
    return (await _member_responses(db, [member]))[0]


async def remove_member(
    db: AsyncSession,
    requesting_user: User,
    investigation_id: uuid.UUID,
    member_id: uuid.UUID,
) -> None:
    await get_investigation(db, requesting_user, investigation_id)
    await ensure_owner_permission(
        db,
        requesting_user,
        investigation_id,
        "Only investigation owners can remove members",
    )
    member = await _get_member_by_id(db, investigation_id, member_id)
    if member is None:
        raise InvestigationNotFoundError("Member not found")
    if member.role == "owner":
        await _ensure_not_last_owner(db, investigation_id)
    if member.user_id == requesting_user.id and member.role == "owner":
        await _ensure_not_last_owner(db, investigation_id)
    await record_event(
        db,
        action="investigation.member_removed",
        actor_id=requesting_user.id,
        resource_type="investigation_member",
        resource_id=member.id,
        investigation_id=investigation_id,
        metadata={
            "before_role": member.role,
            "target_user": str(member.user_id),
            "actor": str(requesting_user.id),
        },
    )
    _record_workflow_event(
        db,
        investigation_id=investigation_id,
        actor_id=requesting_user.id,
        from_status=None,
        to_status="active",
        reason=f"Member removed: {member.user_id}",
    )
    await db.delete(member)


async def ensure_user_is_member(
    db: AsyncSession,
    investigation_id: uuid.UUID,
    user_id: uuid.UUID,
    message: str = "User must be an investigation member",
) -> InvestigationMember:
    member = await _get_membership(db, investigation_id, user_id)
    if member is None:
        raise MemberValidationError(message)
    return member


async def _resolve_member_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    email: str | None,
    username: str | None,
) -> User | None:
    if user_id is not None:
        return await db.get(User, user_id)
    if email:
        result = await db.execute(select(User).where(User.email == email.strip()))
        return result.scalar_one_or_none()
    if username:
        result = await db.execute(
            select(User).where(User.username == username.strip())
        )
        return result.scalar_one_or_none()
    raise MemberValidationError("user_id, email, or username is required")


async def _member_responses(
    db: AsyncSession,
    members: list[InvestigationMember],
) -> list[MemberResponse]:
    if not members:
        return []
    user_ids = {member.user_id for member in members}
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users = {user.id: user for user in users_result.scalars().all()}
    responses: list[MemberResponse] = []
    for member in members:
        user = users.get(member.user_id)
        responses.append(
            MemberResponse(
                id=member.id,
                investigation_id=member.investigation_id,
                user_id=member.user_id,
                username=user.username if user else str(member.user_id),
                email=user.email if user else "",
                role=member.role,  # type: ignore[arg-type]
                invited_by=member.invited_by,
                created_at=member.created_at,
                updated_at=member.updated_at,
            )
        )
    return responses


def _role_rank(role: str) -> int:
    return ROLE_RANK.get(role, 0)


async def _ensure_not_last_owner(
    db: AsyncSession,
    investigation_id: uuid.UUID,
) -> None:
    result = await db.execute(
        select(func.count())
        .select_from(InvestigationMember)
        .where(
            InvestigationMember.investigation_id == investigation_id,
            InvestigationMember.role == "owner",
        )
    )
    if int(result.scalar_one()) <= 1:
        raise LastOwnerError("Cannot remove or demote the last owner")
