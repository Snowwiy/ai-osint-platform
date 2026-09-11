from __future__ import annotations

from httpx import AsyncClient


async def test_release_endpoint_returns_rc5_metadata_without_secrets(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/release")

    assert response.status_code == 200
    body = response.json()
    assert body["app_name"] == "RavenTech OSINT"
    assert body["version"] == "5.0.0-rc6"
    assert body["release_channel"] == "release-candidate"
    assert body["environment"] in {"development", "staging", "production"}
    assert body["migration_version"]
    assert body["generated_at"]

    serialized = response.text.casefold()
    for forbidden in (
        "app_secret_key",
        "anthropic_api_key",
        "database_url",
        "password",
        "token",
    ):
        assert forbidden not in serialized
