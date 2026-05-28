from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.investigation import Investigation
from app.models.investigation_member import InvestigationMember
from app.models.user import User
from app.schemas.investigation import InvestigationCreate, InvestigationUpdate


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
