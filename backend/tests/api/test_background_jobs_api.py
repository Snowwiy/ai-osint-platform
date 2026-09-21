from __future__ import annotations

import pytest
from app.models.audit_log import AuditLog
from app.services.background_jobs import enqueue_job
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_jobs_are_admin_only_and_cancellable(
    client: AsyncClient,
    db: AsyncSession,
    admin_headers: dict[str, str],
    analyst_headers: dict[str, str],
) -> None:
    job = await enqueue_job(db, "monitoring.refresh", {})
    await db.commit()
    denied = await client.get(
        "/api/v1/operations/background-jobs", headers=analyst_headers
    )
    assert denied.status_code == 403
    listed = await client.get(
        "/api/v1/operations/background-jobs", headers=admin_headers
    )
    assert listed.status_code == 200
    assert any(item["id"] == str(job.id) for item in listed.json()["jobs"])
    row = next(item for item in listed.json()["jobs"] if item["id"] == str(job.id))
    assert row["can_cancel"] is True
    assert row["can_retry"] is False
    cancelled = await client.post(
        f"/api/v1/operations/background-jobs/{job.id}/cancel", headers=admin_headers
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    conflict = await client.post(
        f"/api/v1/operations/background-jobs/{job.id}/cancel", headers=admin_headers
    )
    assert conflict.status_code == 409
    actions = (await db.execute(select(AuditLog.action).where(
        AuditLog.resource_id == job.id
    ))).scalars().all()
    assert "background_job.created" in actions
    assert "background_job.cancelled" in actions
