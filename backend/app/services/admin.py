from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_analysis import AiAnalysis
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.scan_job import ScanJob
from app.models.target import Target
from app.models.user import User

logger = logging.getLogger(__name__)


async def get_health_status(db: AsyncSession, redis: Any) -> dict[str, str]:
    db_status = "ok"
    redis_status = "ok"

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check database ping failed")
        db_status = "error"

    try:
        await redis.ping()
    except Exception:
        logger.exception("Health check Redis ping failed")
        redis_status = "error"

    return {
        "status": "healthy"
        if db_status == "ok" and redis_status == "ok"
        else "unhealthy",
        "database": db_status,
        "redis": redis_status,
        "timestamp": datetime.now(UTC).isoformat(),
    }


async def get_platform_stats(db: AsyncSession) -> dict[str, dict[str, int]]:
    async def count(model: type[object]) -> int:
        result = await db.execute(select(func.count()).select_from(model))
        return int(result.scalar_one())

    return {
        "users": {"total": await count(User)},
        "investigations": {"total": await count(Investigation)},
        "targets": {"total": await count(Target)},
        "findings": {"total": await count(Finding)},
        "scans": {"total": await count(ScanJob)},
        "ai_analyses": {"total": await count(AiAnalysis)},
    }
