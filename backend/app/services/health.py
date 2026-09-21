from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.background_job import NativeWorkerHeartbeat


async def health_snapshot(redis: Any, *, include_ready: bool) -> dict[str, Any]:
    native = settings.BACKGROUND_JOB_BACKEND == "native"
    checks = {
        "database": await _database_check(),
        "redis": {"status": "not_required", "detail": "Native mode uses PostgreSQL."}
        if native
        else await _redis_check(redis),
        "migrations": await _migration_check(),
        "storage": _storage_check(),
        "worker": await _native_worker_check()
        if native
        else await _worker_check(redis),
        "ai_provider": _ai_provider_check(),
    }
    status = _overall_status(checks, include_ready=include_ready)
    return {
        "status": status,
        "environment": settings.APP_ENVIRONMENT,
        "background_job_backend": settings.BACKGROUND_JOB_BACKEND,
        "checks": checks,
    }


async def liveness_snapshot() -> dict[str, Any]:
    return {"status": "ok", "environment": settings.APP_ENVIRONMENT}


async def _database_check() -> dict[str, Any]:
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        return {
            "status": "error",
            "detail": "Database connectivity check failed.",
        }


async def _redis_check(redis: Any) -> dict[str, Any]:
    try:
        await redis.ping()
        return {"status": "ok"}
    except Exception:
        return {
            "status": "error",
            "detail": "Redis connectivity check failed.",
        }


async def _migration_check() -> dict[str, Any]:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(text("SELECT version_num FROM alembic_version"))
            current = str(result.scalar_one_or_none() or "")
        head = _migration_head()
        return {
            "status": "ok" if current == head else "degraded",
            "current": current,
            "head": head,
        }
    except Exception:
        return {
            "status": "error",
            "detail": "Migration state check failed.",
        }


def _storage_check() -> dict[str, Any]:
    paths = {
        "reports": Path("/data/reports"),
        "chroma": Path(settings.CHROMA_DATA_PATH),
    }
    details: dict[str, str] = {}
    status = "ok"
    for name, path in paths.items():
        try:
            path.mkdir(parents=True, exist_ok=True)
            details[name] = "writable" if path.is_dir() else "missing"
            if details[name] != "writable":
                status = "degraded"
        except Exception:
            details[name] = "unavailable"
            status = "error"
    return {"status": status, "paths": details}


async def _worker_check(redis: Any) -> dict[str, Any]:
    try:
        await redis.ping()
        return {
            "status": "ok",
            "detail": "Redis broker reachable; Celery worker should be supervised.",
        }
    except Exception:
        return {"status": "error", "detail": "Redis broker connectivity check failed."}


async def _native_worker_check() -> dict[str, Any]:
    if not settings.NATIVE_WORKER_ENABLED:
        return {
            "status": "not_required",
            "detail": "Native worker is disabled by configuration.",
        }
    try:
        cutoff = datetime.now(UTC) - timedelta(
            seconds=settings.NATIVE_WORKER_STALE_SECONDS
        )
        async with AsyncSessionLocal() as db:
            count = (
                await db.execute(
                    select(func.count())
                    .select_from(NativeWorkerHeartbeat)
                    .where(
                        NativeWorkerHeartbeat.heartbeat_at >= cutoff,
                        NativeWorkerHeartbeat.stopping.is_(False),
                    )
                )
            ).scalar_one()
        return {
            "status": "ok" if count else "error",
            "active_workers": count,
            "detail": "Native PostgreSQL worker heartbeat is current."
            if count
            else "Native worker is not running or its heartbeat is stale.",
        }
    except Exception:
        return {"status": "error", "detail": "Native worker status is unavailable."}


def _ai_provider_check() -> dict[str, Any]:
    return {
        "status": "ok" if settings.ANTHROPIC_API_KEY else "degraded",
        "provider": "anthropic",
        "available": bool(settings.ANTHROPIC_API_KEY),
    }


def _migration_head() -> str:
    backend_root = Path(__file__).resolve().parents[2]
    script = ScriptDirectory(str(backend_root / "alembic"))
    return str(script.get_current_head())


def _overall_status(
    checks: dict[str, dict[str, Any]],
    *,
    include_ready: bool,
) -> str:
    required: tuple[str, ...] = ("database", "migrations", "storage")
    if settings.BACKGROUND_JOB_BACKEND == "celery":
        required += ("redis",)
    elif settings.NATIVE_WORKER_ENABLED:
        required += ("worker",)
    relevant = (
        {key: checks[key] for key in required}
        if include_ready
        else {"database": checks["database"]}
    )
    if any(check.get("status") == "error" for check in relevant.values()):
        return "error"
    if include_ready and any(checks[key].get("status") != "ok" for key in required):
        return "degraded"
    return "ok"
