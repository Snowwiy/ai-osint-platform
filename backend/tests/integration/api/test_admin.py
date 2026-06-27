from __future__ import annotations

from app.models.audit_log import AuditLog
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


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


async def test_audit_events_normalize_inet_and_metadata(
    client: AsyncClient,
    db: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    db.add(
        AuditLog(
            action="recon.executed",
            resource_type="investigation",
            ip_address="127.0.0.1",
            details=["legacy"],
            event_metadata=["legacy"],
        )
    )
    await db.commit()

    response = await client.get(
        "/api/v1/admin/audit?limit=50&offset=0",
        headers=admin_headers,
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["ip_address"] == "127.0.0.1"
    assert item["metadata"] == {}
