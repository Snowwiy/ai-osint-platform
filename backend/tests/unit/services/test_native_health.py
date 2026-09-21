from __future__ import annotations

from typing import Any

import pytest
from app.services import health


@pytest.mark.asyncio
async def test_native_readiness_does_not_ping_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def ok() -> dict[str, Any]:
        return {"status": "ok"}

    async def redis_forbidden(_value: Any) -> dict[str, Any]:
        raise AssertionError("Native mode must not contact Redis")

    monkeypatch.setattr(health.settings, "BACKGROUND_JOB_BACKEND", "native")
    monkeypatch.setattr(health.settings, "RUNTIME_PROFILE", "desktop")
    monkeypatch.setattr(health.settings, "NATIVE_WORKER_ENABLED", True)
    monkeypatch.setattr(health, "_database_check", ok)
    monkeypatch.setattr(health, "_migration_check", ok)
    monkeypatch.setattr(health, "_native_worker_check", ok)
    monkeypatch.setattr(health, "_storage_check", lambda: {"status": "ok"})
    monkeypatch.setattr(health, "_redis_check", redis_forbidden)
    snapshot = await health.health_snapshot(None, include_ready=True)
    assert snapshot["status"] == "ok"
    assert snapshot["background_job_backend"] == "native"
    assert snapshot["runtime_profile"] == "desktop"
    assert snapshot["required_dependencies"] == [
        "database", "migrations", "storage", "worker"
    ]
    assert snapshot["optional_dependencies"] == ["redis", "celery"]
    assert snapshot["checks"]["redis"]["status"] == "not_required"
    assert snapshot["checks"]["celery"]["status"] == "not_required"
