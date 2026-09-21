from __future__ import annotations

import asyncio

import pytest
from app import worker
from app.core.config import Settings, settings
from app.services.background_jobs import (
    QueueFullError,
    claim_job,
    complete_job,
    enqueue_job,
    schedule_native_cycle,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def test_runtime_profiles_keep_docker_compatibility() -> None:
    desktop = Settings(
        _env_file=None,
        RUNTIME_PROFILE="desktop",
        BACKGROUND_JOB_BACKEND="celery",
        REDIS_URL="",
    )
    docker = Settings(
        _env_file=None,
        RUNTIME_PROFILE="docker",
        BACKGROUND_JOB_BACKEND="celery",
        REDIS_URL="",
    )
    assert desktop.background_engine == "native"
    assert not any("REDIS_URL" in error for error in desktop.startup_errors())
    assert docker.background_engine == "celery"
    assert "REDIS_URL is required in celery mode." in docker.startup_errors()
    disabled_worker = Settings(
        _env_file=None, RUNTIME_PROFILE="desktop", NATIVE_WORKER_ENABLED=False
    )
    assert (
        "NATIVE_WORKER_ENABLED is required in desktop profile."
        in disabled_worker.startup_errors()
    )


async def test_queue_depth_is_bounded_and_dedupe_still_works(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "NATIVE_WORKER_MAX_QUEUE_DEPTH", 1)
    first = await enqueue_job(db, "monitoring.refresh", {}, dedupe_key="same")
    deduped = await enqueue_job(db, "monitoring.refresh", {}, dedupe_key="same")
    assert deduped.id == first.id
    with pytest.raises(QueueFullError):
        await enqueue_job(db, "monitoring.refresh", {})


async def test_running_per_type_cap(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "NATIVE_WORKER_MAX_RUNNING_PER_TYPE", 1)
    first = await enqueue_job(db, "monitoring.refresh", {})
    second = await enqueue_job(db, "monitoring.refresh", {})
    await db.commit()
    claimed = await claim_job(db, "worker-a")
    assert claimed is not None and claimed.id == first.id
    await db.commit()
    assert await claim_job(db, "worker-b") is None
    await complete_job(db, claimed, "Done")
    await db.commit()
    next_job = await claim_job(db, "worker-b")
    assert next_job is not None and next_job.id == second.id


async def test_concurrent_enqueue_uses_one_dedupe_key(db: AsyncSession) -> None:
    assert db.bind is not None
    factory = async_sessionmaker(db.bind, expire_on_commit=False)

    async def submit() -> str:
        async with factory() as session:
            job = await enqueue_job(
                session, "monitoring.refresh", {}, dedupe_key="one-cycle"
            )
            await session.commit()
            return str(job.id)

    first, second = await asyncio.gather(submit(), submit())
    assert first == second


async def test_scheduler_fires_once_per_interval(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MONITORING_AUTO_REFRESH_ENABLED", True)
    first = await schedule_native_cycle(db)
    assert first is not None and first.job_type == "monitoring.refresh"
    await db.commit()
    assert await schedule_native_cycle(db) is None


async def test_handler_timeout_is_safe_and_retryable(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = await enqueue_job(db, "monitoring.refresh", {})
    await db.commit()
    assert db.bind is not None
    monkeypatch.setattr(
        worker, "AsyncSessionLocal", async_sessionmaker(db.bind, expire_on_commit=False)
    )

    async def slow_handler(_db: AsyncSession, _payload: dict[str, str]) -> str:
        await asyncio.sleep(0.2)
        return "Never committed"

    monkeypatch.setitem(worker.HANDLERS, "monitoring.refresh", slow_handler)
    monkeypatch.setitem(worker.HANDLER_TIMEOUT_SECONDS, "monitoring.refresh", 0.01)
    assert await worker.process_one("timeout-worker") is True
    await db.refresh(job)
    assert job.status == "retry_wait"
    assert job.last_error_code == "timeout"
