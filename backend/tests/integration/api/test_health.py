from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services.health import _redis_check, _worker_check


async def test_root_liveness_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health/live")

    assert response.status_code == 200
    assert "x-request-id" in response.headers
    assert response.headers["x-frame-options"] == "DENY"
    body = response.json()
    assert body["status"] == "ok"
    assert "environment" in body


async def test_root_health_returns_structured_checks(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "checks" in body
    assert {"database", "redis", "migrations", "storage", "worker"}.issubset(
        body["checks"].keys()
    )


async def test_readiness_returns_ok_for_required_local_services(
    client: AsyncClient,
) -> None:
    response = await client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert all(
        body["checks"][name]["status"] == "ok"
        for name in ("database", "redis", "migrations", "storage")
    )


class _FailingRedis:
    async def ping(self) -> bool:
        raise RuntimeError("redis://user:secret@example.invalid/0")


@pytest.mark.parametrize(
    ("check", "expected_detail"),
    [
        (_redis_check, "Redis connectivity check failed."),
        (_worker_check, "Redis broker connectivity check failed."),
    ],
)
async def test_health_failures_do_not_expose_raw_connection_errors(
    check,
    expected_detail: str,
) -> None:
    result = await check(_FailingRedis())

    assert result == {"status": "error", "detail": expected_detail}
    assert "secret" not in result["detail"].casefold()
