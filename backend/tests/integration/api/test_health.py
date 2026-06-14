from __future__ import annotations

from httpx import AsyncClient


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
