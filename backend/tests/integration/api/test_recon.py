from __future__ import annotations

import pytest
from app.api.v1 import recon as recon_api
from app.schemas.recon import ReconResponse
from httpx import AsyncClient

from tests.conftest import VALID_AUTH_STATEMENT


async def test_domain_recon_requires_auth(
    client: AsyncClient,
    test_investigation,
) -> None:
    response = await client.post(
        "/api/v1/recon/domain",
        json={
            "investigation_id": str(test_investigation.id),
            "target": "example.com",
            "authorization_statement": VALID_AUTH_STATEMENT,
        },
    )

    assert response.status_code == 401


async def test_domain_recon_requires_investigation_membership(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db,
    admin_user,
) -> None:
    from app.models.investigation import Investigation

    investigation = Investigation(
        title="Private Investigation",
        owner_id=admin_user.id,
        authorization_statement=VALID_AUTH_STATEMENT,
        status="active",
    )
    db.add(investigation)
    await db.commit()
    await db.refresh(investigation)

    response = await client.post(
        "/api/v1/recon/domain",
        headers=analyst_headers,
        json={
            "investigation_id": str(investigation.id),
            "target": "example.com",
            "authorization_statement": VALID_AUTH_STATEMENT,
        },
    )

    assert response.status_code == 404


async def test_domain_recon_endpoint_returns_schema(
    monkeypatch: pytest.MonkeyPatch,
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
) -> None:
    async def fake_run(_db, _user, body, *, target_type: str) -> ReconResponse:
        return ReconResponse(
            investigation_id=body.investigation_id,
            target_type=target_type,
            target_value=body.target,
            status="completed",
        )

    monkeypatch.setattr(recon_api, "run_recon_for_request", fake_run)

    response = await client.post(
        "/api/v1/recon/domain",
        headers=analyst_headers,
        json={
            "investigation_id": str(test_investigation.id),
            "target": "example.com",
            "authorization_statement": VALID_AUTH_STATEMENT,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["target_type"] == "domain"
    assert body["target_value"] == "example.com"
    assert body["status"] == "completed"


async def test_url_recon_rejects_non_http_url(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation,
) -> None:
    response = await client.post(
        "/api/v1/recon/url",
        headers=analyst_headers,
        json={
            "investigation_id": str(test_investigation.id),
            "target": "ftp://example.com/file",
            "authorization_statement": VALID_AUTH_STATEMENT,
        },
    )

    assert response.status_code == 400
