"""Compatibility boundary for work gradually moving from synchronous/Celery mode."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.background_job import BackgroundJob
from app.services.background_jobs import enqueue_job, request_cancellation


class NativeJobDispatcher:
    async def dispatch_job(
        self,
        db: AsyncSession,
        job_type: str,
        payload: dict[str, str],
        *,
        dedupe_key: str | None = None,
        requested_by_user_id: uuid.UUID | None = None,
    ) -> BackgroundJob:
        return await enqueue_job(
            db,
            job_type,
            payload,
            dedupe_key=dedupe_key,
            requested_by_user_id=requested_by_user_id,
            cooldown_seconds=30
            if job_type in ("monitoring.refresh", "posture.recompute")
            else 0,
        )

    async def schedule_job(
        self,
        db: AsyncSession,
        job_type: str,
        payload: dict[str, str],
        scheduled_at: datetime,
        *,
        dedupe_key: str | None = None,
    ) -> BackgroundJob:
        return await enqueue_job(
            db, job_type, payload, scheduled_at=scheduled_at, dedupe_key=dedupe_key
        )

    async def get_job_status(
        self, db: AsyncSession, job_id: uuid.UUID
    ) -> BackgroundJob | None:
        return (
            await db.execute(select(BackgroundJob).where(BackgroundJob.id == job_id))
        ).scalar_one_or_none()

    async def cancel_job(
        self, db: AsyncSession, job: BackgroundJob, actor_id: uuid.UUID | None = None
    ) -> BackgroundJob:
        return await request_cancellation(db, job, actor_id)


class CeleryJobDispatcher:
    """Legacy tasks remain synchronous so no existing work is dropped."""

    async def dispatch_job(
        self,
        db: AsyncSession,
        job_type: str,
        payload: dict[str, str],
        *,
        dedupe_key: str | None = None,
        requested_by_user_id: uuid.UUID | None = None,
    ) -> None:
        if job_type in ("posture.recompute", "recommendations.recompute"):
            from app.services.endpoint_posture import refresh_asset_posture_if_due

            await refresh_asset_posture_if_due(db, uuid.UUID(payload["asset_id"]))
            return
        if job_type == "monitoring.refresh":
            return  # Polling remains request-driven in legacy mode.
        raise ValueError("Job type is not supported in compatibility mode.")


def dispatcher() -> NativeJobDispatcher | CeleryJobDispatcher:
    return (
        NativeJobDispatcher()
        if settings.background_engine == "native"
        else CeleryJobDispatcher()
    )
