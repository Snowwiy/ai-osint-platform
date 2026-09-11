from __future__ import annotations

from httpx import AsyncClient


async def test_local_operator_status_is_safe_and_reports_rc5(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    response = await client.get("/api/v1/operations/status", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"healthy", "degraded", "unavailable"}
    assert body["release"]["version"] == "5.0.0-rc5"
    assert body["components"]["database"]["status"] in {
        "healthy",
        "degraded",
        "unavailable",
    }

    serialized = response.text.casefold()
    for forbidden in (
        "app_secret_key",
        "database_url",
        "redis_url",
        "password",
        "token",
    ):
        assert forbidden not in serialized
