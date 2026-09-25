"""Run with ``python -m app.worker``. PostgreSQL is the only queue dependency."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import socket
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.models.background_job import BackgroundJob, NativeWorkerHeartbeat
from app.services.background_jobs import (
    JobValidationError,
    QueueFullError,
    cancel_running_job,
    claim_job,
    complete_job,
    fail_job,
    mark_progress,
    recover_stale_jobs,
    schedule_lan_discovery_cycle,
    schedule_native_cycle,
    schedule_service_observation_cycle,
    validate_payload,
)
from app.services.endpoint_posture import EndpointPostureNotFoundError

logger = logging.getLogger(__name__)
Handler = Callable[[AsyncSession, dict[str, str]], Awaitable[str]]


async def _posture(db: AsyncSession, payload: dict[str, str]) -> str:
    from app.services.endpoint_posture import refresh_asset_posture_if_due

    await refresh_asset_posture_if_due(db, uuid.UUID(payload["asset_id"]))
    return "Posture and recommendations refreshed if due."


async def _monitoring(db: AsyncSession, payload: dict[str, str]) -> str:
    from sqlalchemy import func

    from app.models.lan_monitoring import LanAsset

    count = (await db.execute(select(func.count()).select_from(LanAsset))).scalar_one()
    return f"Monitoring summary refreshed for {count} LAN assets."


async def _lan_discovery(db: AsyncSession, payload: dict[str, str]) -> str:
    from app.services.lan_monitoring import run_native_lan_discovery

    return await run_native_lan_discovery(db)


async def _service_observation(db: AsyncSession, payload: dict[str, str]) -> str:
    from app.services.lan_monitoring import run_native_service_observation

    return await run_native_service_observation(db)


async def _knowledge_source_sync(db: AsyncSession, payload: dict[str, str]) -> str:
    from app.services.knowledge.source_service import sync_knowledge_source

    result = await sync_knowledge_source(db, uuid.UUID(payload["source_id"]))
    return (
        f"Knowledge source sync completed: {result['indexed']} indexed, "
        f"{result['unchanged']} unchanged, {result['failed']} failed."
    )


HANDLERS: dict[str, Handler] = {
    "posture.recompute": _posture,
    "recommendations.recompute": _posture,
    "monitoring.refresh": _monitoring,
    "monitoring.lan_discovery": _lan_discovery,
    "monitoring.service_observation": _service_observation,
    "knowledge.source.sync": _knowledge_source_sync,
}
HANDLER_TIMEOUT_SECONDS = {
    "monitoring.refresh": 30,
    "posture.recompute": 90,
    "recommendations.recompute": 90,
    "monitoring.lan_discovery": 600,
    "monitoring.service_observation": 600,
    "knowledge.source.sync": 600,
}


async def _heartbeat(
    worker_id: str, job_id: uuid.UUID | None = None, *, stopping: bool = False
) -> bool:
    async with AsyncSessionLocal() as db:
        now = datetime.now(UTC)
        statement = (
            insert(NativeWorkerHeartbeat)
            .values(
                worker_id=worker_id,
                started_at=now,
                heartbeat_at=now,
                stopping=stopping,
            )
            .on_conflict_do_update(
                index_elements=[NativeWorkerHeartbeat.worker_id],
                set_={"heartbeat_at": now, "stopping": stopping},
            )
        )
        await db.execute(statement)
        cancelled = False
        if job_id is not None:
            job = (
                await db.execute(
                    select(BackgroundJob).where(
                        BackgroundJob.id == job_id,
                        BackgroundJob.worker_id == worker_id,
                    )
                )
            ).scalar_one_or_none()
            if job is not None:
                job.heartbeat_at = now
                cancelled = job.cancel_requested
        await db.commit()
        return cancelled


async def process_one(worker_id: str) -> bool:
    async with AsyncSessionLocal() as db:
        job = await claim_job(db, worker_id)
        if job is None:
            await db.rollback()
            return False
        job_id = job.id
        job_type = job.job_type
        payload = job.payload
        await db.commit()
    handler = HANDLERS.get(job_type)
    beat_stop = asyncio.Event()

    async def beat() -> None:
        while not beat_stop.is_set():
            try:
                await asyncio.wait_for(
                    beat_stop.wait(), timeout=settings.NATIVE_WORKER_HEARTBEAT_SECONDS
                )
            except TimeoutError:
                await _heartbeat(worker_id, job_id)

    beat_task = asyncio.create_task(beat())
    try:
        clean = validate_payload(job_type, payload)
        if handler is None:
            raise JobValidationError("Unknown registered handler.")
        if await _heartbeat(worker_id, job_id):
            async with AsyncSessionLocal() as db:
                job = await db.get(BackgroundJob, job_id)
                if job:
                    await cancel_running_job(db, job)
                    await db.commit()
            return True
        async with AsyncSessionLocal() as db:
            job = await db.get(BackgroundJob, job_id)
            if job is None:
                return True
            if job.cancel_requested:
                await cancel_running_job(db, job)
                await db.commit()
                return True
            await mark_progress(db, job, 50)
            await db.commit()
        cancelled_after_handler = False
        async with AsyncSessionLocal() as db:
            job = await db.get(BackgroundJob, job_id)
            if job is None:
                return True
            if job.cancel_requested:
                await cancel_running_job(db, job)
                await db.commit()
                return True
            result = await asyncio.wait_for(
                handler(db, clean), timeout=HANDLER_TIMEOUT_SECONDS[job_type]
            )
            # Lock final state before deciding whether handler writes may commit.
            await db.refresh(job, with_for_update=True)
            if job.cancel_requested:
                cancelled_after_handler = True
                await db.rollback()
            else:
                await complete_job(db, job, result)
                await db.commit()
        if cancelled_after_handler:
            async with AsyncSessionLocal() as db:
                job = await db.get(BackgroundJob, job_id)
                if job:
                    await cancel_running_job(db, job)
                    await db.commit()
    except JobValidationError:
        async with AsyncSessionLocal() as db:
            job = await db.get(BackgroundJob, job_id)
            if job:
                await fail_job(db, job, "validation_error", retryable=False)
                await db.commit()
    except (ValueError, EndpointPostureNotFoundError):
        async with AsyncSessionLocal() as db:
            job = await db.get(BackgroundJob, job_id)
            if job:
                await fail_job(db, job, "validation_error", retryable=False)
                await db.commit()
    except TimeoutError:
        async with AsyncSessionLocal() as db:
            job = await db.get(BackgroundJob, job_id)
            if job:
                if job.cancel_requested:
                    await cancel_running_job(db, job)
                else:
                    await fail_job(db, job, "timeout", retryable=True)
                await db.commit()
    except Exception:
        logger.warning("Native job failed: type=%s id=%s", job_type, job_id)
        async with AsyncSessionLocal() as db:
            job = await db.get(BackgroundJob, job_id)
            if job:
                await fail_job(db, job, "temporary_failure", retryable=True)
                await db.commit()
    finally:
        beat_stop.set()
        await beat_task
    return True


async def run_worker() -> None:
    if settings.background_engine != "native" or not settings.NATIVE_WORKER_ENABLED:
        raise RuntimeError("Native worker mode is not enabled.")
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (
            NotImplementedError
        ):  # Windows event loop does not support signal handlers.
            pass
    await _heartbeat(worker_id)
    sem = asyncio.Semaphore(settings.NATIVE_WORKER_CONCURRENCY)
    active: set[asyncio.Task[None]] = set()

    async def run_slot() -> None:
        try:
            await process_one(worker_id)
        finally:
            sem.release()

    try:
        while not stop.is_set():
            stop_file = os.getenv("RAVENTECH_DESKTOP_STOP_FILE")
            if stop_file and Path(stop_file).is_file():
                stop.set()
                break
            await _heartbeat(worker_id)
            async with AsyncSessionLocal() as db:
                await recover_stale_jobs(db)
                try:
                    await schedule_native_cycle(db)
                    await schedule_lan_discovery_cycle(db, worker_id)
                    await schedule_service_observation_cycle(db, worker_id)
                except QueueFullError:
                    logger.debug("Native scheduler deferred: queue is full.")
                await db.commit()
            while not stop.is_set() and not sem.locked():
                await sem.acquire()
                task = asyncio.create_task(run_slot())
                active.add(task)
                task.add_done_callback(active.discard)
                # Bound polling; idle slots exit quickly without busy looping.
                if len(active) >= settings.NATIVE_WORKER_CONCURRENCY:
                    break
                await asyncio.sleep(0)
            try:
                await asyncio.wait_for(
                    stop.wait(), timeout=settings.NATIVE_WORKER_POLL_SECONDS
                )
            except TimeoutError:
                if stop_file and Path(stop_file).is_file():
                    stop.set()
    finally:
        if active:
            await asyncio.gather(*active, return_exceptions=True)
        await _heartbeat(worker_id, stopping=True)
        await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
