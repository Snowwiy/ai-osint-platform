from __future__ import annotations

import ipaddress
import uuid
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.engagement import (
    AuthorizationEvidence,
    Engagement,
    EngagementScopeItem,
)
from app.models.investigation import Investigation
from app.models.user import User
from app.schemas.engagement import (
    AuthorizationEvidenceCreate,
    AuthorizationEvidenceUpdate,
    EngagementCreate,
    EngagementResponse,
    EngagementUpdate,
    ScopeCheckResponse,
    ScopeItemCreate,
    ScopeItemResponse,
    ScopeItemUpdate,
)
from app.services.audit import record_event

MUTATION_PLATFORM_ROLES = frozenset({"admin", "analyst"})


class EngagementNotFoundError(Exception):
    pass


class EngagementForbiddenError(Exception):
    pass


class EngagementConflictError(Exception):
    pass


class EngagementStateConflictError(Exception):
    pass


@dataclass(frozen=True)
class ScopeMatchResult:
    status: str
    matched_item: EngagementScopeItem | None
    warning: str
    recommended_action: str


def ensure_engagement_mutation_role(user: User) -> None:
    if user.role not in MUTATION_PLATFORM_ROLES:
        raise EngagementForbiddenError(
            "This action requires analyst or administrator permissions."
        )


async def list_engagements(
    db: AsyncSession,
    user: User,
    *,
    include_archived: bool = False,
    skip: int = 0,
    limit: int = 50,
) -> tuple[int, list[EngagementResponse]]:
    filters = []
    if not include_archived:
        filters.append(Engagement.status != "archived")
    count_stmt = select(func.count()).select_from(Engagement).where(*filters)
    total = int((await db.execute(count_stmt)).scalar_one())
    result = await db.execute(
        select(Engagement)
        .where(*filters)
        .order_by(Engagement.updated_at.desc(), Engagement.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = list(result.scalars().all())
    return total, [await engagement_response(db, engagement) for engagement in items]


async def get_engagement(
    db: AsyncSession,
    user: User,
    engagement_id: uuid.UUID,
) -> Engagement:
    engagement = await db.get(Engagement, engagement_id)
    if engagement is None:
        raise EngagementNotFoundError("Engagement not found")
    return engagement


async def get_engagement_response(
    db: AsyncSession,
    user: User,
    engagement_id: uuid.UUID,
) -> EngagementResponse:
    engagement = await get_engagement(db, user, engagement_id)
    return await engagement_response(db, engagement)


async def create_engagement(
    db: AsyncSession,
    user: User,
    body: EngagementCreate,
) -> EngagementResponse:
    ensure_engagement_mutation_role(user)
    engagement = Engagement(
        title=body.title,
        client_name=body.client_name,
        client_contact=body.client_contact,
        description=body.description,
        status=body.status,
        authorization_status=body.authorization_status,
        start_date=body.start_date,
        end_date=body.end_date,
        created_by=user.id,
    )
    db.add(engagement)
    await db.flush()
    await record_event(
        db,
        action="engagement.created",
        actor_id=user.id,
        resource_type="engagement",
        resource_id=engagement.id,
        metadata={
            "status": engagement.status,
            "authorization_status": engagement.authorization_status,
        },
    )
    await db.refresh(engagement)
    return await engagement_response(db, engagement)


async def update_engagement(
    db: AsyncSession,
    user: User,
    engagement_id: uuid.UUID,
    body: EngagementUpdate,
) -> EngagementResponse:
    ensure_engagement_mutation_role(user)
    engagement = await get_engagement(db, user, engagement_id)
    updates = body.model_dump(exclude_unset=True)
    previous = {
        "status": engagement.status,
        "authorization_status": engagement.authorization_status,
    }
    for field, value in updates.items():
        setattr(engagement, field, value)
    db.add(engagement)
    await db.flush()
    await record_event(
        db,
        action="engagement.updated",
        actor_id=user.id,
        resource_type="engagement",
        resource_id=engagement.id,
        metadata={
            "changed": sorted(updates),
            "old_status": previous["status"],
            "new_status": engagement.status,
            "old_authorization_status": previous["authorization_status"],
            "new_authorization_status": engagement.authorization_status,
        },
    )
    await db.refresh(engagement)
    return await engagement_response(db, engagement)


async def archive_engagement(
    db: AsyncSession,
    user: User,
    engagement_id: uuid.UUID,
) -> EngagementResponse:
    ensure_engagement_mutation_role(user)
    engagement = await get_engagement(db, user, engagement_id)
    previous = engagement.status
    engagement.status = "archived"
    db.add(engagement)
    await db.flush()
    await record_event(
        db,
        action="engagement.archived",
        actor_id=user.id,
        resource_type="engagement",
        resource_id=engagement.id,
        metadata={"old_status": previous, "new_status": "archived"},
    )
    await db.refresh(engagement)
    return await engagement_response(db, engagement)


async def list_scope_items(
    db: AsyncSession,
    user: User,
    engagement_id: uuid.UUID,
) -> list[EngagementScopeItem]:
    await get_engagement(db, user, engagement_id)
    result = await db.execute(
        select(EngagementScopeItem)
        .where(EngagementScopeItem.engagement_id == engagement_id)
        .order_by(
            EngagementScopeItem.status,
            EngagementScopeItem.scope_type,
            EngagementScopeItem.value,
        )
    )
    return list(result.scalars().all())


async def create_scope_item(
    db: AsyncSession,
    user: User,
    engagement_id: uuid.UUID,
    body: ScopeItemCreate,
) -> EngagementScopeItem:
    ensure_engagement_mutation_role(user)
    await get_engagement(db, user, engagement_id)
    item = EngagementScopeItem(
        engagement_id=engagement_id,
        scope_type=body.scope_type,
        value=normalize_scope_value(body.scope_type, body.value),
        description=body.description,
        status=body.status,
        created_by=user.id,
    )
    db.add(item)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise EngagementConflictError(
            "This scope value already exists for the engagement."
        ) from exc
    await record_event(
        db,
        action="engagement.scope_added",
        actor_id=user.id,
        resource_type="engagement_scope_item",
        resource_id=item.id,
        metadata=_scope_metadata(engagement_id, item),
    )
    await db.refresh(item)
    return item


async def update_scope_item(
    db: AsyncSession,
    user: User,
    engagement_id: uuid.UUID,
    scope_item_id: uuid.UUID,
    body: ScopeItemUpdate,
) -> EngagementScopeItem:
    ensure_engagement_mutation_role(user)
    item = await _get_scope_item(db, user, engagement_id, scope_item_id)
    previous = {"status": item.status, "value": item.value}
    updates = body.model_dump(exclude_unset=True)
    if "value" in updates and updates["value"] is not None:
        scope_type = str(updates.get("scope_type") or item.scope_type)
        updates["value"] = normalize_scope_value(scope_type, updates["value"])
    for field, value in updates.items():
        setattr(item, field, value)
    db.add(item)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise EngagementConflictError(
            "This scope value already exists for the engagement."
        ) from exc
    await record_event(
        db,
        action="engagement.scope_updated",
        actor_id=user.id,
        resource_type="engagement_scope_item",
        resource_id=item.id,
        metadata={
            **_scope_metadata(engagement_id, item),
            "old_status": previous["status"],
            "new_status": item.status,
            "old_value": previous["value"],
            "new_value": item.value,
        },
    )
    await db.refresh(item)
    return item


async def delete_scope_item(
    db: AsyncSession,
    user: User,
    engagement_id: uuid.UUID,
    scope_item_id: uuid.UUID,
) -> None:
    ensure_engagement_mutation_role(user)
    item = await _get_scope_item(db, user, engagement_id, scope_item_id)
    metadata = _scope_metadata(engagement_id, item)
    await db.delete(item)
    await db.flush()
    await record_event(
        db,
        action="engagement.scope_removed",
        actor_id=user.id,
        resource_type="engagement_scope_item",
        resource_id=scope_item_id,
        metadata=metadata,
    )


async def list_authorization_evidence(
    db: AsyncSession,
    user: User,
    engagement_id: uuid.UUID,
) -> list[AuthorizationEvidence]:
    await get_engagement(db, user, engagement_id)
    result = await db.execute(
        select(AuthorizationEvidence)
        .where(AuthorizationEvidence.engagement_id == engagement_id)
        .order_by(
            AuthorizationEvidence.status,
            AuthorizationEvidence.updated_at.desc(),
        )
    )
    return list(result.scalars().all())


async def create_authorization_evidence(
    db: AsyncSession,
    user: User,
    engagement_id: uuid.UUID,
    body: AuthorizationEvidenceCreate,
) -> AuthorizationEvidence:
    ensure_engagement_mutation_role(user)
    await get_engagement(db, user, engagement_id)
    evidence = AuthorizationEvidence(
        engagement_id=engagement_id,
        title=body.title,
        description=body.description,
        evidence_type=body.evidence_type,
        reference=body.reference,
        status=body.status,
        created_by=user.id,
    )
    db.add(evidence)
    await db.flush()
    await record_event(
        db,
        action="engagement.authorization_added",
        actor_id=user.id,
        resource_type="authorization_evidence",
        resource_id=evidence.id,
        metadata={
            "engagement_id": str(engagement_id),
            "status": evidence.status,
            "evidence_type": evidence.evidence_type,
        },
    )
    await db.refresh(evidence)
    return evidence


async def update_authorization_evidence(
    db: AsyncSession,
    user: User,
    engagement_id: uuid.UUID,
    evidence_id: uuid.UUID,
    body: AuthorizationEvidenceUpdate,
) -> AuthorizationEvidence:
    ensure_engagement_mutation_role(user)
    evidence = await _get_authorization_evidence(
        db,
        user,
        engagement_id,
        evidence_id,
    )
    previous_status = evidence.status
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(evidence, field, value)
    db.add(evidence)
    await db.flush()
    await record_event(
        db,
        action="engagement.authorization_updated",
        actor_id=user.id,
        resource_type="authorization_evidence",
        resource_id=evidence.id,
        metadata={
            "engagement_id": str(engagement_id),
            "old_status": previous_status,
            "new_status": evidence.status,
            "changed": sorted(updates),
        },
    )
    await db.refresh(evidence)
    return evidence


async def delete_authorization_evidence(
    db: AsyncSession,
    user: User,
    engagement_id: uuid.UUID,
    evidence_id: uuid.UUID,
) -> None:
    ensure_engagement_mutation_role(user)
    evidence = await _get_authorization_evidence(
        db,
        user,
        engagement_id,
        evidence_id,
    )
    metadata = {
        "engagement_id": str(engagement_id),
        "status": evidence.status,
        "evidence_type": evidence.evidence_type,
    }
    await db.delete(evidence)
    await db.flush()
    await record_event(
        db,
        action="engagement.authorization_removed",
        actor_id=user.id,
        resource_type="authorization_evidence",
        resource_id=evidence_id,
        metadata=metadata,
    )


async def check_scope_value(
    db: AsyncSession,
    user: User,
    engagement_id: uuid.UUID,
    *,
    value: str,
    scope_type: str | None,
) -> ScopeCheckResponse:
    await get_engagement(db, user, engagement_id)
    items = await list_scope_items(db, user, engagement_id)
    result = match_scope_value(value, scope_type, items)
    if result.status != "in_scope":
        await record_event(
            db,
            action="investigation.scope_warning_created",
            actor_id=user.id,
            resource_type="engagement",
            resource_id=engagement_id,
            metadata={
                "value": value,
                "scope_type": scope_type,
                "status": result.status,
                "matched_scope_item_id": (
                    str(result.matched_item.id) if result.matched_item else None
                ),
            },
        )
    return ScopeCheckResponse(
        status=cast(Any, result.status),
        matched_scope_item=(
            ScopeItemResponse.model_validate(result.matched_item)
            if result.matched_item
            else None
        ),
        warning=result.warning,
        recommended_action=result.recommended_action,
    )


def match_scope_value(
    value: str,
    scope_type: str | None,
    items: list[EngagementScopeItem],
) -> ScopeMatchResult:
    candidate_type, candidate = _candidate(value, scope_type)
    for item in items:
        if _item_matches(item, candidate, candidate_type):
            return _matched_result(item)
    return ScopeMatchResult(
        status="pending_review",
        matched_item=None,
        warning="No matching approved scope item was found for this value.",
        recommended_action=(
            "Pause and review the engagement scope before adding or assessing "
            "this target."
        ),
    )


def normalize_scope_value(scope_type: str, value: str) -> str:
    clean = value.strip()
    if scope_type in {"domain", "subdomain"}:
        return _host_value(clean).lower().rstrip(".")
    if scope_type in {"email", "username", "organization"}:
        return clean.lower()
    if scope_type == "ip":
        try:
            return str(ipaddress.ip_address(clean))
        except ValueError:
            return clean
    if scope_type == "cidr":
        try:
            return str(ipaddress.ip_network(clean, strict=False))
        except ValueError:
            return clean
    return clean


async def engagement_response(
    db: AsyncSession,
    engagement: Engagement,
) -> EngagementResponse:
    scope_counts = await _scope_counts(db, engagement.id)
    linked_count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Investigation)
                .where(Investigation.engagement_id == engagement.id)
            )
        ).scalar_one()
    )
    return EngagementResponse.model_validate(engagement).model_copy(
        update={
            "linked_investigations_count": linked_count,
            "scope_counts": scope_counts,
        }
    )


async def _get_scope_item(
    db: AsyncSession,
    user: User,
    engagement_id: uuid.UUID,
    scope_item_id: uuid.UUID,
) -> EngagementScopeItem:
    await get_engagement(db, user, engagement_id)
    result = await db.execute(
        select(EngagementScopeItem).where(
            EngagementScopeItem.id == scope_item_id,
            EngagementScopeItem.engagement_id == engagement_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise EngagementNotFoundError("Scope item not found")
    return item


async def _get_authorization_evidence(
    db: AsyncSession,
    user: User,
    engagement_id: uuid.UUID,
    evidence_id: uuid.UUID,
) -> AuthorizationEvidence:
    await get_engagement(db, user, engagement_id)
    result = await db.execute(
        select(AuthorizationEvidence).where(
            AuthorizationEvidence.id == evidence_id,
            AuthorizationEvidence.engagement_id == engagement_id,
        )
    )
    evidence = result.scalar_one_or_none()
    if evidence is None:
        raise EngagementNotFoundError("Authorization evidence not found")
    return evidence


async def _scope_counts(
    db: AsyncSession,
    engagement_id: uuid.UUID,
) -> dict[str, int]:
    result = await db.execute(
        select(EngagementScopeItem.status, func.count())
        .where(EngagementScopeItem.engagement_id == engagement_id)
        .group_by(EngagementScopeItem.status)
    )
    counts = {"in_scope": 0, "out_of_scope": 0, "pending_review": 0}
    for status, count in result.all():
        counts[str(status)] = int(count)
    return counts


def _scope_metadata(
    engagement_id: uuid.UUID,
    item: EngagementScopeItem,
) -> dict[str, Any]:
    return {
        "engagement_id": str(engagement_id),
        "scope_item_id": str(item.id),
        "scope_type": item.scope_type,
        "scope_value": item.value,
        "status": item.status,
    }


def _candidate(value: str, scope_type: str | None) -> tuple[str | None, str]:
    inferred = scope_type
    clean = value.strip()
    parsed = urlparse(clean)
    if parsed.scheme in {"http", "https"} and parsed.hostname:
        return "domain", parsed.hostname.lower().rstrip(".")
    if inferred:
        return inferred, normalize_scope_value(inferred, clean)
    try:
        return "ip", str(ipaddress.ip_address(clean))
    except ValueError:
        pass
    if "@" in clean:
        return "email", clean.lower()
    host = _host_value(clean)
    if "." in host:
        return "domain", host.lower().rstrip(".")
    return None, clean.lower()


def _host_value(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"//{value}")
    return parsed.hostname or value


def _item_matches(
    item: EngagementScopeItem,
    candidate: str,
    candidate_type: str | None,
) -> bool:
    item_value = normalize_scope_value(item.scope_type, item.value)
    if item.scope_type == "cidr":
        try:
            network = ipaddress.ip_network(item_value, strict=False)
            address = ipaddress.ip_address(candidate)
        except ValueError:
            return False
        return address in network
    if item.scope_type == "ip":
        return candidate_type == "ip" and item_value == candidate
    if item.scope_type == "domain":
        if candidate_type not in {"domain", "subdomain"}:
            return False
        return candidate == item_value or candidate.endswith(f".{item_value}")
    if item.scope_type == "subdomain":
        return candidate_type in {"domain", "subdomain"} and candidate == item_value
    if item.scope_type in {"email", "username", "organization"}:
        return candidate_type == item.scope_type and item_value == candidate
    return item_value.lower() == candidate.lower()


def _matched_result(item: EngagementScopeItem) -> ScopeMatchResult:
    if item.status == "in_scope":
        return ScopeMatchResult(
            status="in_scope",
            matched_item=item,
            warning="Value matches approved engagement scope.",
            recommended_action="Continue with the defensive workflow.",
        )
    if item.status == "out_of_scope":
        return ScopeMatchResult(
            status="out_of_scope",
            matched_item=item,
            warning="Value matches an out-of-scope item for this engagement.",
            recommended_action=(
                "Do not assess this value unless the engagement scope is updated "
                "and approved."
            ),
        )
    return ScopeMatchResult(
        status="pending_review",
        matched_item=item,
        warning="Value matches a scope item that is still pending review.",
        recommended_action=(
            "Ask an owner or administrator to validate the scope item before "
            "continuing."
        ),
    )
