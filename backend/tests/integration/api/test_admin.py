from __future__ import annotations

from httpx import AsyncClient


async def test_health_check_returns_200_and_healthy_status(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/admin/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database"] == "ok"
    assert body["redis"] == "ok"
    assert "timestamp" in body


async def test_health_check_response_shape(client: AsyncClient) -> None:
    response = await client.get("/api/v1/admin/health")
    assert set(response.json().keys()) == {"status", "database", "redis", "timestamp"}


async def test_health_check_requires_no_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/admin/health")
    assert response.status_code == 200
