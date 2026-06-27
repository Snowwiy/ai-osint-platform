from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import AccountStatus, PlatformRole, UserCreate, UserUpdate


class UserNotFoundError(Exception):
    pass


class UserConflictError(Exception):
    pass


class SelfDeactivateError(Exception):
    pass


class UnsafeUserChangeError(Exception):
    pass


async def list_users(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 50,
    role: str | None = None,
    is_active: bool | None = None,
    status: str | None = None,
    search: str | None = None,
) -> tuple[int, list[User]]:
    filters = []
    if role is not None:
        filters.append(User.role == role)
    if is_active is not None:
        filters.append(User.is_active == is_active)
    if status is not None:
        filters.append(User.account_status == status)
    if search:
        pattern = f"%{search.strip().lower()}%"
        filters.append(
            (func.lower(User.username).like(pattern))
            | (func.lower(User.email).like(pattern))
        )

    count_stmt = select(func.count()).select_from(User).where(*filters)
    total = int((await db.execute(count_stmt)).scalar_one())

    stmt = (
        select(User).where(*filters).offset(skip).limit(limit).order_by(User.username)
    )
    users = list((await db.execute(stmt)).scalars().all())
    return total, users


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise UserNotFoundError("User not found")
    return user


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    result = await db.execute(
        select(User).where(
            (User.email == data.email) | (User.username == data.username)
        )
    )
    if result.scalar_one_or_none() is not None:
        raise UserConflictError("A user with that email or username already exists")

    user = User(
        username=data.username,
        email=str(data.email).lower(),
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
        is_active=True,
        account_status="active",
        registration_source="admin_created",
        approved_at=datetime.now(UTC),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, user_id: uuid.UUID, data: UserUpdate) -> User:
    user = await get_user(db, user_id)
    updates = data.model_dump(exclude_unset=True)
    if user.role == "admin":
        next_role = updates.get("role", user.role)
        next_active = updates.get("is_active", user.is_active)
        if next_role != "admin" or next_active is False:
            await _ensure_another_active_admin(db, user)
    for field, value in updates.items():
        if field == "email" and value is not None:
            value = str(value).lower()
        if field == "is_active":
            user.account_status = "active" if value else "disabled"
        setattr(user, field, value)
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def deactivate_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    current_user_id: uuid.UUID,
) -> None:
    if user_id == current_user_id:
        raise SelfDeactivateError("Cannot deactivate your own account")
    user = await get_user(db, user_id)
    if user.role == "admin":
        await _ensure_another_active_admin(db, user)
    user.is_active = False
    user.account_status = "disabled"
    db.add(user)


async def set_user_status(
    db: AsyncSession,
    *,
    target_user_id: uuid.UUID,
    actor: User,
    status: AccountStatus,
) -> tuple[User, str, str]:
    user = await get_user(db, target_user_id)
    old_status = user.account_status
    if old_status == status:
        return user, old_status, user.account_status

    await _ensure_status_change_is_safe(db, user, actor, status)
    user.account_status = status
    user.is_active = status == "active"
    if status == "active":
        user.approved_at = datetime.now(UTC)
        user.approved_by = actor.id
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user, old_status, user.account_status


async def approve_user(
    db: AsyncSession,
    *,
    target_user_id: uuid.UUID,
    actor: User,
) -> tuple[User, str, str]:
    return await set_user_status(
        db,
        target_user_id=target_user_id,
        actor=actor,
        status="active",
    )


async def reject_user(
    db: AsyncSession,
    *,
    target_user_id: uuid.UUID,
    actor: User,
) -> tuple[User, str, str]:
    return await set_user_status(
        db,
        target_user_id=target_user_id,
        actor=actor,
        status="rejected",
    )


async def disable_user(
    db: AsyncSession,
    *,
    target_user_id: uuid.UUID,
    actor: User,
) -> tuple[User, str, str]:
    return await set_user_status(
        db,
        target_user_id=target_user_id,
        actor=actor,
        status="disabled",
    )


async def reactivate_user(
    db: AsyncSession,
    *,
    target_user_id: uuid.UUID,
    actor: User,
) -> tuple[User, str, str]:
    return await set_user_status(
        db,
        target_user_id=target_user_id,
        actor=actor,
        status="active",
    )


async def set_user_role(
    db: AsyncSession,
    *,
    target_user_id: uuid.UUID,
    actor: User,
    role: PlatformRole,
) -> tuple[User, str, str]:
    user = await get_user(db, target_user_id)
    old_role = user.role
    if old_role == role:
        return user, old_role, user.role
    if user.role == "admin" and role != "admin":
        await _ensure_another_active_admin(db, user)
    user.role = role
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user, old_role, user.role


async def _ensure_status_change_is_safe(
    db: AsyncSession,
    user: User,
    actor: User,
    status: AccountStatus,
) -> None:
    if user.role == "admin" and status != "active":
        await _ensure_another_active_admin(db, user)
    if user.id == actor.id and user.role == "admin" and status != "active":
        await _ensure_another_active_admin(db, user)


async def _ensure_another_active_admin(db: AsyncSession, user: User) -> None:
    result = await db.execute(
        select(func.count())
        .select_from(User)
        .where(
            User.role == "admin",
            User.is_active.is_(True),
            User.account_status == "active",
            User.id != user.id,
        )
    )
    if int(result.scalar_one()) < 1:
        raise UnsafeUserChangeError(
            "At least one active administrator account must remain."
        )
