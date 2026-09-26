from __future__ import annotations

import pytest
from app.models.audit_log import AuditLog
from app.models.monitoring_history import MonitoringChangeEvent
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def test_legacy_local_host_write_authorization_requires_action_gateway(
    client: AsyncClient,
    admin_headers: dict[str, str],
    analyst_headers: dict[str, str],
) -> None:
    path = "/api/v1/monitoring/local-host/authorize"
    body = {
        "action": "process_terminate",
        "target": "notepad.exe (200)",
        "confirmed": True,
    }
    assert (await client.post(path, json=body)).status_code in {401, 403}
    assert (
        await client.post(path, headers=analyst_headers, json=body)
    ).status_code == 403
    denied = await client.post(
        path, headers=admin_headers, json={**body, "confirmed": False}
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "human_approval_gateway_required"
    assert (
        await client.post(
            path, headers=admin_headers, json={**body, "action": "remote_terminate"}
        )
    ).status_code == 422
    assert (
        await client.post(path, headers=admin_headers, json=body)
    ).status_code == 403


async def test_inventory_admin_gate_and_legacy_result_endpoint_is_disabled(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
) -> None:
    authorize = await client.post(
        "/api/v1/monitoring/local-host/authorize",
        headers=admin_headers,
        json={"action": "service_inventory"},
    )
    assert authorize.status_code == 200
    viewed = (
        (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.action == "local_service_inventory.viewed"
                )
            )
        )
        .scalars()
        .first()
    )
    assert viewed is not None
    result = await client.post(
        "/api/v1/monitoring/local-host/result",
        headers=admin_headers,
        json={
            "action": "service_stop",
            "target": "Example (example)",
            "success": False,
            "previous_state": "running",
            "resulting_state": "failed",
        },
    )
    assert result.status_code == 403
    assert result.json()["detail"]["code"] == "human_approval_gateway_required"
    audit = (
        (
            await db.execute(
                select(AuditLog).where(AuditLog.action == "local_host.action_failed")
            )
        )
        .scalars()
        .first()
    )
    assert audit is None


@pytest.mark.parametrize("action", ["service_start", "service_stop", "service_restart"])
async def test_legacy_service_actions_require_action_gateway_proposal(
    client: AsyncClient,
    admin_headers: dict[str, str],
    analyst_headers: dict[str, str],
    action: str,
) -> None:
    path = "/api/v1/monitoring/local-host/authorize"
    body = {"action": action, "target": "Example (example)", "confirmed": True}
    assert (
        await client.post(path, headers=analyst_headers, json=body)
    ).status_code == 403
    response = await client.post(path, headers=admin_headers, json=body)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "human_approval_gateway_required"


@pytest.mark.parametrize(
    ("action", "event"),
    [
        ("service_start", "local_service.started"),
        ("service_stop", "local_service.stopped"),
        ("service_restart", "local_service.restarted"),
        ("process_terminate", "local_process.terminated"),
    ],
)
async def test_legacy_result_endpoint_cannot_forge_action_events(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
    action: str,
    event: str,
) -> None:
    response = await client.post(
        "/api/v1/monitoring/local-host/result",
        headers=admin_headers,
        json={
            "action": action,
            "target": "Example (200)",
            "success": True,
            "previous_state": "running",
            "resulting_state": "stopped",
        },
    )
    assert response.status_code == 403
    audit = (
        (await db.execute(select(AuditLog).where(AuditLog.action == event)))
        .scalars()
        .first()
    )
    assert audit is None
    assert not list(
        (
            await db.execute(
                select(MonitoringChangeEvent).where(
                    MonitoringChangeEvent.source == "local_desktop",
                )
            )
        )
        .scalars()
        .all()
    )
