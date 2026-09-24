"""PostgreSQL-backed, allowlisted background jobs. No executable payloads."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.background_job import (
    BackgroundJob,
    BackgroundJobEvent,
    NativeWorkerHeartbeat,
)
from app.services.audit import record_event

ACTIVE = ("queued", "scheduled", "running", "retry_wait", "cancel_requested")
WAITING = ("queued", "scheduled", "retry_wait")
PRIORITIES = {"low": 20, "normal": 50, "high": 70, "critical": 90}
ALLOWED_TYPES = {
    "posture.recompute": {"asset_id"},
    "recommendations.recompute": {"asset_id"},
    "monitoring.refresh": set(),
    "monitoring.lan_discovery": set(),
    "monitoring.service_observation": set(),
}
FORBIDDEN_KEYS = (
    "password",
    "secret",
    "token",
    "key",
    "credential",
    "command",
    "script",
    "path",
    "env",
    "banner",
)


class JobValidationError(ValueError):
    pass


class QueueFullError(JobValidationError):
    pass


def validate_payload(job_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = ALLOWED_TYPES.get(job_type)
    if allowed is None:
        raise JobValidationError("Job type is not registered for native execution.")
    if not isinstance(payload, dict) or set(payload) != allowed:
        raise JobValidationError("Job payload does not match the registered schema.")
    if any(
        any(blocked in key.lower() for blocked in FORBIDDEN_KEYS) for key in payload
    ):
        raise JobValidationError("Job payload contains a prohibited field.")
    if "asset_id" in allowed:
        try:
            return {"asset_id": str(uuid.UUID(str(payload["asset_id"])))}
        except (ValueError, TypeError, KeyError) as exc:
            raise JobValidationError("A valid asset identifier is required.") from exc
    return {}


def _event(db: AsyncSession, job: BackgroundJob, kind: str, detail: str) -> None:
    db.add(
        BackgroundJobEvent(
            job_id=job.id, event_type=kind, worker_id=job.worker_id, detail=detail[:255]
        )
    )


async def enqueue_job(
    db: AsyncSession,
    job_type: str,
    payload: dict[str, Any],
    *,
    priority: int = 50,
    scheduled_at: datetime | None = None,
    dedupe_key: str | None = None,
    requested_by_user_id: uuid.UUID | None = None,
    max_attempts: int | None = None,
    cooldown_seconds: int = 0,
) -> BackgroundJob:
    clean = validate_payload(job_type, payload)
    if (
        priority not in PRIORITIES.values()
        or dedupe_key is not None
        and (not dedupe_key or len(dedupe_key) > 160)
    ):
        raise JobValidationError("Invalid priority or dedupe key.")
    attempts = max_attempts
    if attempts is None:
        attempts = settings.NATIVE_WORKER_MAX_RETRIES + 1
    if not 1 <= attempts <= 11:
        raise JobValidationError("Max attempts must be between 1 and 11.")
    if not 0 <= cooldown_seconds <= 3600:
        raise JobValidationError("Cooldown must be between 0 and 3600 seconds.")
    if dedupe_key:
        existing = (
            await db.execute(
                select(BackgroundJob).where(
                    BackgroundJob.dedupe_key == dedupe_key,
                    BackgroundJob.status.in_(ACTIVE),
                )
            )
        ).scalar_one_or_none()
        if existing:
            return existing
        if cooldown_seconds:
            recent = (
                await db.execute(
                    select(BackgroundJob)
                    .where(
                        BackgroundJob.dedupe_key == dedupe_key,
                        BackgroundJob.status == "completed",
                        BackgroundJob.finished_at
                        >= datetime.now(UTC) - timedelta(seconds=cooldown_seconds),
                    )
                    .order_by(BackgroundJob.finished_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if recent is not None:
                return recent
    # Serialize admission across API processes so the queue bound is real.
    await db.execute(text("SELECT pg_advisory_xact_lock(50210, 1)"))
    if dedupe_key:
        concurrent = (
            await db.execute(
                select(BackgroundJob).where(
                    BackgroundJob.dedupe_key == dedupe_key,
                    BackgroundJob.status.in_(ACTIVE),
                )
            )
        ).scalar_one_or_none()
        if concurrent is not None:
            return concurrent
    depth = (
        await db.execute(
            select(func.count()).select_from(BackgroundJob).where(
                BackgroundJob.status.in_(WAITING)
            )
        )
    ).scalar_one()
    if depth >= settings.NATIVE_WORKER_MAX_QUEUE_DEPTH:
        raise QueueFullError("Native job queue is at its configured limit.")
    now = datetime.now(UTC)
    job = BackgroundJob(
        job_type=job_type,
        payload=clean,
        priority=priority,
        status="scheduled" if scheduled_at and scheduled_at > now else "queued",
        scheduled_at=scheduled_at or now,
        dedupe_key=dedupe_key,
        requested_by_user_id=requested_by_user_id,
        asset_id=uuid.UUID(clean["asset_id"]) if "asset_id" in clean else None,
        max_attempts=attempts,
    )
    try:
        async with db.begin_nested():
            db.add(job)
            await db.flush()
    except IntegrityError:
        if dedupe_key:
            existing = (
                await db.execute(
                    select(BackgroundJob).where(
                        BackgroundJob.dedupe_key == dedupe_key,
                        BackgroundJob.status.in_(ACTIVE),
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return existing
        raise
    _event(db, job, "queued", "Job accepted into PostgreSQL queue.")
    await record_event(
        db,
        action="background_job.created",
        actor_id=requested_by_user_id,
        resource_type="background_job",
        resource_id=job.id,
        metadata={"job_type": job_type},
    )
    return job


async def claim_job(db: AsyncSession, worker_id: str) -> BackgroundJob | None:
    now = datetime.now(UTC)
    candidates = (
        await db.execute(
            select(BackgroundJob)
            .where(
                BackgroundJob.status.in_(("queued", "scheduled", "retry_wait")),
                BackgroundJob.scheduled_at <= now,
                or_(
                    BackgroundJob.next_retry_at.is_(None),
                    BackgroundJob.next_retry_at <= now,
                ),
            )
            .order_by(
                BackgroundJob.priority.desc(),
                BackgroundJob.scheduled_at,
                BackgroundJob.created_at,
            )
            .with_for_update(skip_locked=True)
            .limit(20)
        )
    ).scalars().all()
    job = None
    for candidate in candidates:
        type_lock = (
            await db.execute(
                text("SELECT pg_try_advisory_xact_lock(50210, hashtext(:kind))"),
                {"kind": candidate.job_type},
            )
        ).scalar_one()
        if not type_lock:
            continue
        running = (
            await db.execute(
                select(func.count()).select_from(BackgroundJob).where(
                    BackgroundJob.job_type == candidate.job_type,
                    BackgroundJob.status.in_(("running", "cancel_requested")),
                )
            )
        ).scalar_one()
        if running < settings.NATIVE_WORKER_MAX_RUNNING_PER_TYPE:
            job = candidate
            break
    if job is None:
        return None
    job.status = "running"
    job.worker_id = worker_id
    job.started_at = now
    job.heartbeat_at = now
    job.attempt_count += 1
    job.next_retry_at = None
    _event(db, job, "claimed", "Worker claimed job.")
    _event(db, job, "started", "Job execution started.")
    await record_event(
        db,
        action="background_job.started",
        resource_type="background_job",
        resource_id=job.id,
        metadata={"job_type": job.job_type},
    )
    return job


async def mark_progress(db: AsyncSession, job: BackgroundJob, percent: int) -> None:
    if job.status != "running" or not 0 <= percent <= 100:
        raise JobValidationError("Progress update is invalid.")
    job.progress = percent
    job.heartbeat_at = datetime.now(UTC)
    # Progress events are coarse to avoid unbounded history.
    if percent in (0, 50, 100):
        _event(db, job, "progress", f"Progress reached {percent}%.")


async def complete_job(db: AsyncSession, job: BackgroundJob, summary: str) -> None:
    if job.status not in ("running", "cancel_requested"):
        raise JobValidationError("Job is not running.")
    if job.cancel_requested:
        await cancel_running_job(db, job)
        return
    job.status = "completed"
    job.progress = 100
    job.result_summary = summary[:255]
    job.finished_at = datetime.now(UTC)
    _event(db, job, "completed", "Job completed.")
    await record_event(
        db,
        action="background_job.completed",
        resource_type="background_job",
        resource_id=job.id,
        metadata={"job_type": job.job_type},
    )


async def fail_job(
    db: AsyncSession, job: BackgroundJob, code: str, *, retryable: bool
) -> None:
    now = datetime.now(UTC)
    job.last_error_code = code[:40]
    job.last_error_summary = (
        "Job failed; inspect worker diagnostics."
        if retryable
        else "Job cannot be retried automatically."
    )
    if retryable and job.attempt_count < job.max_attempts and not job.cancel_requested:
        job.status = "retry_wait"
        job.next_retry_at = now + timedelta(
            seconds=min(300, 2 ** min(job.attempt_count, 8))
        )
        job.scheduled_at = job.next_retry_at
        _event(db, job, "retry_scheduled", "Bounded retry scheduled.")
        action = "background_job.retry"
    else:
        job.status = "failed"
        job.finished_at = now
        _event(db, job, "failed", "Job failed.")
        action = "background_job.failed"
    await record_event(
        db,
        action=action,
        resource_type="background_job",
        resource_id=job.id,
        metadata={"job_type": job.job_type, "error_code": job.last_error_code},
    )


async def request_cancellation(
    db: AsyncSession, job: BackgroundJob, actor_id: uuid.UUID | None
) -> BackgroundJob:
    if job.status in ("queued", "scheduled", "retry_wait"):
        job.status = "cancelled"
        job.cancel_requested = True
        job.finished_at = datetime.now(UTC)
        _event(db, job, "cancelled", "Queued job cancelled.")
        action = "background_job.cancelled"
    elif job.status == "running":
        job.status = "cancel_requested"
        job.cancel_requested = True
        _event(db, job, "cancel_requested", "Cooperative cancellation requested.")
        action = "background_job.cancel_requested"
    else:
        raise JobValidationError("Job cannot be cancelled in its current state.")
    await record_event(
        db,
        action=action,
        actor_id=actor_id,
        resource_type="background_job",
        resource_id=job.id,
        metadata={"job_type": job.job_type},
    )
    return job


async def cancel_running_job(db: AsyncSession, job: BackgroundJob) -> None:
    job.status = "cancelled"
    job.finished_at = datetime.now(UTC)
    _event(db, job, "cancelled", "Job stopped at a safe boundary.")
    await record_event(
        db,
        action="background_job.cancelled",
        resource_type="background_job",
        resource_id=job.id,
        metadata={"job_type": job.job_type},
    )


async def recover_stale_jobs(db: AsyncSession) -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.NATIVE_WORKER_STALE_SECONDS)
    rows = (
        (
            await db.execute(
                select(BackgroundJob)
                .where(
                    BackgroundJob.status.in_(("running", "cancel_requested")),
                    BackgroundJob.heartbeat_at < cutoff,
                )
                .with_for_update(skip_locked=True)
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    for job in rows:
        if job.cancel_requested:
            await cancel_running_job(db, job)
        else:
            await fail_job(db, job, "worker_stale", retryable=True)
            _event(db, job, "recovered", "Stale worker lease recovered.")
        job.worker_id = None
    return len(rows)


async def queue_counts(db: AsyncSession) -> dict[str, int]:
    rows = (
        await db.execute(
            select(BackgroundJob.status, func.count()).group_by(BackgroundJob.status)
        )
    ).all()
    return {status: count for status, count in rows}


async def schedule_native_cycle(db: AsyncSession) -> BackgroundJob | None:
    """One bounded monitoring summary cycle; missed intervals never fan out."""
    if not settings.MONITORING_AUTO_REFRESH_ENABLED:
        return None
    locked = (
        await db.execute(text("SELECT pg_try_advisory_xact_lock(50211, 1)"))
    ).scalar_one()
    if not locked:
        return None
    last = (
        await db.execute(
            select(BackgroundJob.created_at)
            .where(
                BackgroundJob.job_type == "monitoring.refresh",
                BackgroundJob.dedupe_key == "scheduler:monitoring",
            )
            .order_by(BackgroundJob.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    interval = settings.MONITORING_AUTO_REFRESH_SECONDS
    if last is not None and last > datetime.now(UTC) - timedelta(seconds=interval):
        return None
    return await enqueue_job(
        db,
        "monitoring.refresh",
        {},
        priority=PRIORITIES["low"],
        dedupe_key="scheduler:monitoring",
        cooldown_seconds=interval,
    )


async def _schedule_periodic_lan_job(
    db: AsyncSession,
    *,
    worker_id: str,
    job_type: str,
    dedupe_key: str,
    interval: int,
    run_on_start: bool,
    lock_id: int,
) -> BackgroundJob | None:
    if not settings.LAN_MONITORING_ENABLED:
        return None
    locked = (
        await db.execute(
            text("SELECT pg_try_advisory_xact_lock(50211, :lock_id)"),
            {"lock_id": lock_id},
        )
    ).scalar_one()
    if not locked:
        return None
    worker_started = (
        await db.execute(
            select(NativeWorkerHeartbeat.started_at).where(
                NativeWorkerHeartbeat.worker_id == worker_id
            )
        )
    ).scalar_one_or_none()
    last_created = (
        await db.execute(
            select(BackgroundJob.created_at)
            .where(
                BackgroundJob.job_type == job_type,
                BackgroundJob.dedupe_key == dedupe_key,
            )
            .order_by(BackgroundJob.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if last_created is not None:
        due = last_created <= now - timedelta(seconds=interval)
    elif run_on_start:
        due = True
    else:
        due = worker_started is not None and worker_started <= now - timedelta(
            seconds=interval
        )
    if not due:
        return None
    return await enqueue_job(
        db,
        job_type,
        {},
        priority=PRIORITIES["low"],
        dedupe_key=dedupe_key,
        cooldown_seconds=interval,
    )


async def schedule_lan_discovery_cycle(
    db: AsyncSession, worker_id: str
) -> BackgroundJob | None:
    """Queue one bounded network cycle; never catch up in a burst."""
    if settings.background_engine != "native":
        return None
    return await _schedule_periodic_lan_job(
        db,
        worker_id=worker_id,
        job_type="monitoring.lan_discovery",
        dedupe_key="scheduler:lan-discovery",
        interval=settings.LAN_AUTO_DISCOVERY_INTERVAL_SECONDS,
        run_on_start=settings.LAN_AUTO_DISCOVERY_ON_START,
        lock_id=2,
    )


async def schedule_service_observation_cycle(
    db: AsyncSession, worker_id: str
) -> BackgroundJob | None:
    if settings.background_engine != "native" or not settings.LAN_SERVICE_CHECK_ENABLED:
        return None
    return await _schedule_periodic_lan_job(
        db,
        worker_id=worker_id,
        job_type="monitoring.service_observation",
        dedupe_key="scheduler:service-observation",
        interval=settings.LAN_AUTO_SERVICE_CHECK_INTERVAL_SECONDS,
        run_on_start=settings.LAN_AUTO_SERVICE_CHECK_ON_START,
        lock_id=3,
    )
