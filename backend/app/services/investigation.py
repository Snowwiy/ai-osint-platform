from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.investigation import Investigation
from app.models.investigation_enrichment import InvestigationEnrichment
from app.models.investigation_member import InvestigationMember
from app.models.recon_entity import ReconEntity
from app.models.recon_relationship import ReconRelationship
from app.models.user import User
from app.schemas.investigation import (
    InvestigationCreate,
    InvestigationGraphEdge,
    InvestigationGraphNode,
    InvestigationGraphResponse,
    InvestigationGraphRiskSummary,
    InvestigationGraphTimelineEvent,
    InvestigationUpdate,
)
from app.schemas.recon import EntityType, RelationshipType

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


async def _ensure_owner_or_admin(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
    message: str,
) -> None:
    if user.role == "admin":
        return
    membership = await _get_membership(db, investigation_id, user.id)
    if membership is None or membership.role != "owner":
        raise ForbiddenError(message)


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

    db.add(
        InvestigationMember(
            investigation_id=investigation.id,
            user_id=user.id,
            role="owner",
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
    skip: int = 0,
    limit: int = 20,
) -> tuple[int, list[Investigation]]:
    filters = []
    if status is not None:
        filters.append(Investigation.status == status)

    if user.role == "admin":
        base = select(Investigation).where(*filters)
        count_stmt = select(func.count()).select_from(Investigation).where(*filters)
    else:
        base = (
            select(Investigation)
            .join(
                InvestigationMember,
                Investigation.id == InvestigationMember.investigation_id,
            )
            .where(InvestigationMember.user_id == user.id, *filters)
        )
        count_stmt = (
            select(func.count())
            .select_from(Investigation)
            .join(
                InvestigationMember,
                Investigation.id == InvestigationMember.investigation_id,
            )
            .where(InvestigationMember.user_id == user.id, *filters)
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
    await _ensure_owner_or_admin(
        db,
        user,
        investigation_id,
        "Only owners can update investigations",
    )
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(investigation, field, value)
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
    await _ensure_owner_or_admin(
        db,
        user,
        investigation_id,
        "Only owners can archive investigations",
    )
    investigation.status = "archived"
    db.add(investigation)


async def list_members(
    db: AsyncSession,
    user: User,
    investigation_id: uuid.UUID,
) -> list[InvestigationMember]:
    await get_investigation(db, user, investigation_id)
    result = await db.execute(
        select(InvestigationMember)
        .where(InvestigationMember.investigation_id == investigation_id)
        .order_by(InvestigationMember.added_at)
    )
    return list(result.scalars().all())


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

    return InvestigationGraphResponse(
        investigation_id=investigation_id,
        nodes=[InvestigationGraphNode.model_validate(node) for node in nodes],
        edges=[InvestigationGraphEdge.model_validate(edge) for edge in edges],
        risk_summary=_build_graph_risk_summary(nodes),
        timeline=[
            InvestigationGraphTimelineEvent.model_validate(event) for event in timeline
        ],
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


async def add_member(
    db: AsyncSession,
    requesting_user: User,
    investigation_id: uuid.UUID,
    target_user_id: uuid.UUID,
    role: str,
) -> InvestigationMember:
    await get_investigation(db, requesting_user, investigation_id)
    await _ensure_owner_or_admin(
        db,
        requesting_user,
        investigation_id,
        "Only owners can add members",
    )

    target_user = await db.get(User, target_user_id)
    if target_user is None:
        raise InvestigationNotFoundError("User not found")

    existing = await _get_membership(db, investigation_id, target_user_id)
    if existing is not None:
        raise MemberAlreadyExistsError("User is already a member")

    member = InvestigationMember(
        investigation_id=investigation_id,
        user_id=target_user_id,
        role=role,
    )
    db.add(member)
    await db.flush()
    await db.refresh(member)
    return member


async def update_member_role(
    db: AsyncSession,
    requesting_user: User,
    investigation_id: uuid.UUID,
    target_user_id: uuid.UUID,
    role: str,
) -> InvestigationMember:
    await get_investigation(db, requesting_user, investigation_id)
    await _ensure_owner_or_admin(
        db,
        requesting_user,
        investigation_id,
        "Only owners can change member roles",
    )
    member = await _get_membership(db, investigation_id, target_user_id)
    if member is None:
        raise InvestigationNotFoundError("Member not found")
    if member.role == "owner" and role != "owner":
        await _ensure_not_last_owner(db, investigation_id)
    member.role = role
    db.add(member)
    await db.flush()
    await db.refresh(member)
    return member


async def remove_member(
    db: AsyncSession,
    requesting_user: User,
    investigation_id: uuid.UUID,
    target_user_id: uuid.UUID,
) -> None:
    await get_investigation(db, requesting_user, investigation_id)
    await _ensure_owner_or_admin(
        db,
        requesting_user,
        investigation_id,
        "Only owners can remove members",
    )
    member = await _get_membership(db, investigation_id, target_user_id)
    if member is None:
        raise InvestigationNotFoundError("Member not found")
    if member.role == "owner":
        await _ensure_not_last_owner(db, investigation_id)
    await db.delete(member)


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
