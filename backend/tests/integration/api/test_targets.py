from __future__ import annotations

from httpx import AsyncClient


async def test_create_domain_target_success(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
) -> None:
    response = await client.post(
        "/api/v1/targets/",
        headers=analyst_headers,
        json={
            "investigation_id": str(test_investigation.id),
            "target_type": "domain",
            "target_value": "Example.COM",
            "label": "Main domain",
        },
    )
    assert response.status_code == 201
    assert response.json()["target_value"] == "example.com"


async def test_create_rejects_private_ip(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
) -> None:
    response = await client.post(
        "/api/v1/targets/",
        headers=analyst_headers,
        json={
            "investigation_id": str(test_investigation.id),
            "target_type": "ip",
            "target_value": "192.168.1.10",
        },
    )
    assert response.status_code == 400


async def test_duplicate_target_returns_409(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
) -> None:
    payload = {
        "investigation_id": str(test_investigation.id),
        "target_type": "domain",
        "target_value": "example.com",
    }
    await client.post("/api/v1/targets/", headers=analyst_headers, json=payload)
    response = await client.post(
        "/api/v1/targets/",
        headers=analyst_headers,
        json=payload,
    )
    assert response.status_code == 409


async def test_list_targets_for_investigation(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
) -> None:
    await client.post(
        "/api/v1/targets/",
        headers=analyst_headers,
        json={
            "investigation_id": str(test_investigation.id),
            "target_type": "domain",
            "target_value": "example.com",
        },
    )
    response = await client.get(
        f"/api/v1/targets/?investigation_id={test_investigation.id}",
        headers=analyst_headers,
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
