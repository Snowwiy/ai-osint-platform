from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.models.background_job import BackgroundJobEvent
from app.services.background_jobs import (
    JobValidationError,
    cancel_running_job,
    claim_job,
    complete_job,
    enqueue_job,
    fail_job,
    mark_progress,
    recover_stale_jobs,
    request_cancellation,
    validate_payload,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.mark.asyncio
async def test_enqueue_claim_complete_and_dedupe(db: AsyncSession) -> None:
    job = await enqueue_job(
        db,
        "monitoring.refresh",
        {},
        dedupe_key="monitoring:summary",
    )
    assert (
        await enqueue_job(db, "monitoring.refresh", {}, dedupe_key="monitoring:summary")
    ).id == job.id
    await db.commit()
    claimed = await claim_job(db, "test-worker")
    assert claimed is not None and claimed.id == job.id
    assert claimed.attempt_count == 1
    await mark_progress(db, claimed, 50)
    await complete_job(db, claimed, "Finished safely.")
    await db.commit()
    assert (await claim_job(db, "test-worker")) is None
    assert job.status == "completed" and job.progress == 100
    events = (
        (
            await db.execute(
                select(BackgroundJobEvent.event_type).where(
                    BackgroundJobEvent.job_id == job.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert {"queued", "claimed", "started", "completed"}.issubset(set(events))


def test_knowledge_job_payload_is_allowlisted_and_path_free() -> None:
    source_id = uuid.uuid4()
    assert validate_payload("knowledge.source.sync", {"source_id": str(source_id)}) == {
        "source_id": str(source_id)
    }
    with pytest.raises(JobValidationError):
        validate_payload(
            "knowledge.source.sync",
            {"source_id": str(source_id), "path": "C:/private/vault"},
        )


@pytest.mark.asyncio
async def test_priority_retry_and_exhaustion(db: AsyncSession) -> None:
    low = await enqueue_job(db, "monitoring.refresh", {}, priority=20)
    high = await enqueue_job(db, "monitoring.refresh", {}, priority=90, max_attempts=2)
    await db.commit()
    claimed = await claim_job(db, "worker")
    assert claimed is not None and claimed.id == high.id
    await fail_job(db, claimed, "temporary", retryable=True)
    await db.commit()
    assert high.status == "retry_wait" and high.next_retry_at is not None
    assert (await claim_job(db, "worker")).id == low.id  # type: ignore[union-attr]
    high.next_retry_at = datetime.now(UTC) - timedelta(seconds=1)
    high.scheduled_at = high.next_retry_at
    await db.commit()
    claimed = await claim_job(db, "worker")
    assert claimed is not None and claimed.id == high.id
    await fail_job(db, claimed, "temporary", retryable=True)
    await db.commit()
    assert high.status == "failed" and high.attempt_count == 2


@pytest.mark.asyncio
async def test_cancel_and_stale_recovery(db: AsyncSession) -> None:
    job = await enqueue_job(db, "monitoring.refresh", {})
    await request_cancellation(db, job, None)
    assert job.status == "cancelled"
    running = await enqueue_job(db, "monitoring.refresh", {})
    await db.commit()
    claimed = await claim_job(db, "gone-worker")
    assert claimed is not None and claimed.id == running.id
    await db.commit()
    claimed.heartbeat_at = datetime.now(UTC) - timedelta(hours=1)
    await db.commit()
    assert await recover_stale_jobs(db) == 1
    await db.commit()
    assert claimed.status == "retry_wait" and claimed.last_error_code == "worker_stale"
    claimed.status = "running"
    await request_cancellation(db, claimed, None)
    await cancel_running_job(db, claimed)
    assert claimed.status == "cancelled"


def test_payload_registry_rejects_secrets_and_unknown_jobs() -> None:
    with pytest.raises(JobValidationError):
        validate_payload("arbitrary.module", {})
    with pytest.raises(JobValidationError):
        validate_payload(
            "posture.recompute", {"asset_id": str(uuid.uuid4()), "secret": "x"}
        )
    with pytest.raises(JobValidationError):
        validate_payload("posture.recompute", {"asset_id": "not-a-uuid"})
    assert validate_payload("monitoring.refresh", {}) == {}


@pytest.mark.asyncio
async def test_native_worker_processes_without_redis(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import worker

    job = await enqueue_job(db, "monitoring.refresh", {})
    await db.commit()
    assert db.bind is not None
    factory = async_sessionmaker(db.bind, expire_on_commit=False)
    monkeypatch.setattr(worker, "AsyncSessionLocal", factory)
    assert await worker.process_one("test-native-worker") is True
    await db.refresh(job)
    assert job.status == "completed"
    assert job.result_summary is not None


@pytest.mark.asyncio
async def test_concurrent_claims_never_share_a_job(db: AsyncSession) -> None:
    job = await enqueue_job(db, "monitoring.refresh", {})
    await db.commit()
    assert db.bind is not None
    factory = async_sessionmaker(db.bind, expire_on_commit=False)

    async def claim(worker_id: str) -> uuid.UUID | None:
        async with factory() as session:
            found = await claim_job(session, worker_id)
            await session.commit()
            return found.id if found else None

    results = await asyncio.gather(claim("worker-a"), claim("worker-b"))
    assert results.count(job.id) == 1
    assert results.count(None) == 1


@pytest.mark.asyncio
async def test_future_scheduled_job_waits_until_due(db: AsyncSession) -> None:
    future = datetime.now(UTC) + timedelta(minutes=5)
    job = await enqueue_job(db, "monitoring.refresh", {}, scheduled_at=future)
    await db.commit()
    assert job.status == "scheduled"
    assert await claim_job(db, "worker") is None
    job.scheduled_at = datetime.now(UTC) - timedelta(seconds=1)
    await db.commit()
    assert (await claim_job(db, "worker")).id == job.id  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_completed_job_cooldown_limits_refresh(db: AsyncSession) -> None:
    job = await enqueue_job(db, "monitoring.refresh", {}, dedupe_key="summary")
    await db.commit()
    claimed = await claim_job(db, "worker")
    assert claimed is not None
    await complete_job(db, claimed, "Done")
    await db.commit()
    repeated = await enqueue_job(
        db, "monitoring.refresh", {}, dedupe_key="summary", cooldown_seconds=30
    )
    assert repeated.id == job.id
