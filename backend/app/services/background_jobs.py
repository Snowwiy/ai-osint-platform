"""PostgreSQL-backed, allowlisted background jobs. No executable payloads."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.background_job import BackgroundJob, BackgroundJobEvent
from app.services.audit import record_event

ACTIVE = ("queued", "scheduled", "running", "retry_wait", "cancel_requested")
ALLOWED_TYPES = {
    "posture.recompute": {"asset_id"},
    "recommendations.recompute": {"asset_id"},
    "monitoring.refresh": set(),
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
        not 0 <= priority <= 100
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
    job = (
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
            .limit(1)
        )
    ).scalar_one_or_none()
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
