from __future__ import annotations

import ipaddress
import re
import uuid
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.target import Target
from app.models.user import User
from app.schemas.target import TargetCreate
from app.services.investigation import ForbiddenError, get_investigation

_DOMAIN_RE = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{2,50}$")


class TargetNotFoundError(Exception):
    pass


class TargetValidationError(Exception):
    pass


class TargetConflictError(Exception):
    pass


def validate_target_value(target_type: str, value: str) -> str:
    clean = value.strip()
    if target_type == "ip":
        return _validate_public_ip(clean)
    if target_type == "domain":
        return _validate_domain(clean)
    if target_type == "email":
        if "@" not in clean or len(clean) > 254:
            raise TargetValidationError("Invalid email address")
        local, domain = clean.rsplit("@", 1)
        if not local or not domain:
            raise TargetValidationError("Invalid email address")
        return f"{local.lower()}@{_validate_domain(domain)}"
    if target_type == "username":
        if not _USERNAME_RE.fullmatch(clean):
            raise TargetValidationError("Invalid username")
        return clean
    if target_type == "org":
        if not 2 <= len(clean) <= 200:
            raise TargetValidationError("Organization target must be 2-200 characters")
        return clean
    if target_type == "url":
        parsed = urlparse(clean)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise TargetValidationError("URL targets must be valid http/https URLs")
        _validate_hostname(parsed.hostname)
        return clean
    raise TargetValidationError("Invalid target_type")


def _validate_public_ip(value: str) -> str:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError as exc:
        raise TargetValidationError("Invalid IP address") from exc
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
        raise TargetValidationError(
            "Private or non-routable IP ranges are not permitted"
        )
    return str(ip)


def _validate_domain(value: str) -> str:
    lowered = value.lower().rstrip(".")
    try:
        ipaddress.ip_address(lowered)
    except ValueError:
        pass
    else:
        raise TargetValidationError("Domain target cannot be an IP address")
    if lowered == "localhost" or not _DOMAIN_RE.fullmatch(lowered):
        raise TargetValidationError("Invalid domain name format")
    return lowered


def _validate_hostname(hostname: str) -> None:
    try:
        _validate_public_ip(hostname)
    except TargetValidationError:
        _validate_domain(hostname)


async def create_target(
    db: AsyncSession,
    user: User,
    data: TargetCreate,
) -> Target:
    await get_investigation(db, user, data.investigation_id)
    normalized = validate_target_value(data.target_type, data.target_value)

    existing = await db.execute(
        select(Target).where(
            Target.investigation_id == data.investigation_id,
            Target.target_type == data.target_type,
            Target.target_value == normalized,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise TargetConflictError("Target already exists in this investigation")

    target = Target(
        investigation_id=data.investigation_id,
        target_type=data.target_type,
        target_value=normalized,
        label=data.label,
        notes=data.notes,
        created_by=user.id,
    )
    db.add(target)
    await db.flush()
    await db.refresh(target)
    return target


async def list_targets(
    db: AsyncSession,
    user: User,
    *,
    investigation_id: uuid.UUID,
    target_type: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[int, list[Target]]:
    await get_investigation(db, user, investigation_id)
    filters = [Target.investigation_id == investigation_id]
    if target_type is not None:
        filters.append(Target.target_type == target_type)
    total = int(
        (
            await db.execute(select(func.count()).select_from(Target).where(*filters))
        ).scalar_one()
    )
    result = await db.execute(
        select(Target)
        .where(*filters)
        .order_by(Target.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return total, list(result.scalars().all())


async def get_target(db: AsyncSession, user: User, target_id: uuid.UUID) -> Target:
    target = await db.get(Target, target_id)
    if target is None:
        raise TargetNotFoundError("Target not found")
    await get_investigation(db, user, target.investigation_id)
    return target


async def delete_target(db: AsyncSession, user: User, target_id: uuid.UUID) -> None:
    target = await get_target(db, user, target_id)
    investigation = await get_investigation(db, user, target.investigation_id)
    if user.role != "admin" and investigation.owner_id != user.id:
        raise ForbiddenError("Only investigation owners can remove targets")
    await db.delete(target)
