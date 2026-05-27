from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserNotFoundError(Exception):
    pass


class UserConflictError(Exception):
    pass


class SelfDeactivateError(Exception):
    pass


async def list_users(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 50,
    role: str | None = None,
    is_active: bool | None = None,
) -> tuple[int, list[User]]:
    filters = []
    if role is not None:
        filters.append(User.role == role)
    if is_active is not None:
        filters.append(User.is_active == is_active)

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
        hashed_password=hash_password(data.password),
        role=data.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, user_id: uuid.UUID, data: UserUpdate) -> User:
    user = await get_user(db, user_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "email" and value is not None:
            value = str(value).lower()
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
    user.is_active = False
    db.add(user)
