from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.models.user import User
from app.services.admin import get_health_status, get_platform_stats

router = APIRouter()


@router.get("/admin/health")
async def health_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    return await get_health_status(db, request.app.state.redis)


@router.get("/admin/stats")
async def stats(
    _current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, dict[str, int]]:
    return await get_platform_stats(db)
