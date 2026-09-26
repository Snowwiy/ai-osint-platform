from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import settings
from app.models.action_gateway import ActionApproval, ActionProposal
from app.models.background_job import BackgroundJob
from app.models.lan_monitoring import LanAsset
from app.models.notification import Notification
from app.services.ai.tool_gateway import (
    NativeInventory,
    ToolCall,
    execute_model_tool_calls,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _service_snapshot(
    *, name: str = "RavenTechTestService", state: str = "running", pid: int = 4321
) -> dict[str, object]:
    return {
        "name": name,
        "display_name": "RavenTech Test Service",
        "state": state,
        "pid": pid,
        "start_type": "manual",
        "action_available": True,
    }


def _process_snapshot(
    *, pid: int = 24680, ticks: str = "123456789"
) -> dict[str, object]:
    return {
        "pid": pid,
        "name": "safe-fixture-process.exe",
        "started_at_unix": 1_750_000_000,
        "creation_ticks": ticks,
        "action_available": True,
    }


@pytest.mark.asyncio
async def test_action_registry_capabilities_are_fixed_and_model_has_no_execution_tools(
    client, admin_headers
):
    response = await client.get("/api/v1/actions/capabilities", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert len(data["actions"]) == 12
    assert all(item["approval_required"] is True for item in data["actions"])
    assert data["action_proposal_tools"] == 1
    assert data["execution_tools_exposed_to_model"] == 0
    assert all(
        item["executor"] in {"backend_fixed", "desktop_native"}
        for item in data["actions"]
    )


@pytest.mark.asyncio
async def test_ai_can_create_only_pending_proposal_after_specific_request(
    db: AsyncSession, admin_user
):
    alert = Notification(
        user_id=admin_user.id,
        entity_type="monitoring_alert",
        notification_type="monitoring_alert",
        severity="warning",
        title="Synthetic AI proposal alert",
        message="Isolated test record.",
        status="unread",
        event_metadata={},
    )
    db.add(alert)
    await db.commit()
    args = {
        "action_id": "raventech.alert.acknowledge",
        "target_id": str(alert.id),
        "reason": "Operator explicitly requested a proposal for this alert.",
    }
    result = await execute_model_tool_calls(
        db,
        admin_user,
        [ToolCall(tool="raventech.actions.propose", arguments=args)],
        allow_action_proposals=True,
        action_request_text="Please prepare a proposal to acknowledge this alert.",
    )
    assert result[0]["success"] is True
    assert result[0]["proposal_card"]["status"] == "awaiting_approval"
    proposals = (
        await db.execute(
            select(ActionProposal).where(
                ActionProposal.action_id == "raventech.alert.acknowledge"
            )
        )
    ).scalars().all()
    assert len(proposals) == 1
    approvals = (
        await db.execute(
            select(ActionApproval).where(ActionApproval.proposal_id == proposals[0].id)
        )
    ).scalars().all()
    assert approvals == []
    await db.refresh(alert)
    assert alert.status == "unread"

    no_request = await execute_model_tool_calls(
        db,
        admin_user,
        [ToolCall(tool="raventech.actions.propose", arguments=args)],
        allow_action_proposals=True,
        action_request_text="yes",
    )
    assert no_request[0]["safe_error_code"] == "proposal_not_requested"
    self_execute = await execute_model_tool_calls(
        db,
        admin_user,
        [
            ToolCall(
                tool="raventech.actions.execute",
                arguments={"proposal_id": str(proposals[0].id)},
            )
        ],
        allow_action_proposals=True,
        action_request_text="Please approve and execute the action.",
    )
    assert self_execute[0]["safe_error_code"] == "unknown_tool"


@pytest.mark.asyncio
async def test_ai_native_proposal_uses_supplied_inventory_and_refuses_protected_target(
    db: AsyncSession, admin_user
):
    inventory = NativeInventory.model_validate(
        {
            "available": True,
            "services": [
                {
                    "name": "RavenTechTestService",
                    "displayName": "RavenTech Test Service",
                    "state": "running",
                    "startType": "manual",
                    "pid": 4321,
                    "actionAvailable": True,
                },
                {
                    "name": "RpcSs",
                    "displayName": "Remote Procedure Call",
                    "state": "running",
                    "startType": "automatic",
                    "pid": 1000,
                    "actionAvailable": False,
                },
            ],
        }
    )
    arguments = {
        "action_id": "raventech.service.restart",
        "target_id": "RavenTechTestService",
        "reason": "Operator requested a proposal for a local service restart.",
        "target_snapshot": {"invented": "snapshot"},
    }
    result = await execute_model_tool_calls(
        db,
        admin_user,
        [ToolCall(tool="raventech.actions.propose", arguments=arguments)],
        native_inventory=inventory,
        allow_action_proposals=True,
        action_request_text="Please restart RavenTechTestService.",
    )
    assert result[0]["success"] is True
    proposal = (
        await db.execute(
            select(ActionProposal).where(
                ActionProposal.action_id == "raventech.service.restart"
            )
        )
    ).scalar_one()
    assert proposal.target_snapshot == {
        "name": "RavenTechTestService",
        "display_name": "RavenTech Test Service",
        "state": "running",
        "pid": 4321,
        "start_type": "manual",
        "action_available": True,
    }
    assert proposal.status == "awaiting_approval"
    assert (
        await db.execute(
            select(ActionApproval).where(ActionApproval.proposal_id == proposal.id)
        )
    ).scalar_one_or_none() is None

    protected = await execute_model_tool_calls(
        db,
        admin_user,
        [
            ToolCall(
                tool="raventech.actions.propose",
                arguments={
                    **arguments,
                    "target_id": "RpcSs",
                },
            )
        ],
        native_inventory=inventory,
        allow_action_proposals=True,
        action_request_text="Please restart RpcSs.",
    )
    assert protected[0]["safe_error_code"] == "local_target_unavailable"


@pytest.mark.asyncio
async def test_native_service_proposal_requires_exact_human_approval_and_one_use_claim(
    client, admin_headers
):
    created = await client.post(
        "/api/v1/actions/proposals",
        headers=admin_headers,
        json={
            "action_id": "raventech.service.restart",
            "target_id": "RavenTechTestService",
            "target_display_name": "RavenTech Test Service (RavenTechTestService)",
            "reason": "The local service requires an operator initiated restart.",
            "target_snapshot": _service_snapshot(),
        },
    )
    assert created.status_code == 201
    proposal = created.json()
    assert proposal["status"] == "awaiting_approval"
    assert proposal["risk_level"] == "medium"
    assert len(proposal["proposal_hash"]) == 64

    approved = await client.post(
        f"/api/v1/actions/proposals/{proposal['id']}/approve",
        headers=admin_headers,
        json={
            "confirmation_text": None,
            "current_snapshot": _service_snapshot(),
        },
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    claim = await client.post(
        f"/api/v1/actions/proposals/{proposal['id']}/claim-local",
        headers=admin_headers,
        json={"current_snapshot": _service_snapshot()},
    )
    assert claim.status_code == 200
    assert claim.json()["expected_result"] == "running"
    replay = await client.post(
        f"/api/v1/actions/proposals/{proposal['id']}/claim-local",
        headers=admin_headers,
        json={"current_snapshot": _service_snapshot()},
    )
    assert replay.status_code == 409
    complete = await client.post(
        f"/api/v1/actions/proposals/{proposal['id']}/complete-local",
        headers=admin_headers,
        json={"success": True, "observed_state": "running"},
    )
    assert complete.status_code == 200
    assert complete.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_local_approval_requires_fresh_matching_snapshot(client, admin_headers):
    created = await client.post(
        "/api/v1/actions/proposals",
        headers=admin_headers,
        json={
            "action_id": "raventech.service.restart",
            "target_id": "RavenTechTestService",
            "reason": "The local service needs a reviewed restart proposal.",
            "target_snapshot": _service_snapshot(),
        },
    )
    proposal_id = created.json()["id"]
    missing = await client.post(
        f"/api/v1/actions/proposals/{proposal_id}/approve",
        headers=admin_headers,
        json={},
    )
    assert missing.status_code == 409
    assert missing.json()["detail"]["code"] == "current_snapshot_required"

    changed = await client.post(
        f"/api/v1/actions/proposals/{proposal_id}/approve",
        headers=admin_headers,
        json={"current_snapshot": _service_snapshot(state="stopped")},
    )
    assert changed.status_code == 409
    assert changed.json()["detail"]["code"] == "state_changed_since_proposal"


@pytest.mark.asyncio
async def test_legacy_direct_writes_are_denied(client, db, admin_user, admin_headers):
    asset = LanAsset(
        ip_address="192.168.50.213",
        hostname="synthetic-gateway-safety-test",
        source="host_neighbor_table",
        is_authorized=False,
    )
    alert = Notification(
        user_id=admin_user.id,
        entity_type="monitoring_alert",
        notification_type="monitoring_alert",
        severity="warning",
        title="Synthetic direct-write test alert",
        message="Isolated alert record.",
        status="unread",
        event_metadata={},
    )
    db.add_all([asset, alert])
    await db.commit()

    direct_calls = [
        client.post(
            "/api/v1/monitoring/local-host/authorize",
            headers=admin_headers,
            json={
                "action": "service_restart",
                "target": "RavenTechTestService",
                "confirmed": True,
            },
        ),
        client.post(
            "/api/v1/monitoring/local-host/result",
            headers=admin_headers,
            json={
                "action": "service_restart",
                "target": "RavenTechTestService",
                "success": True,
                "previous_state": "running",
                "resulting_state": "running",
            },
        ),
        client.post(
            "/api/v1/monitoring/lan/discover", headers=admin_headers, json={}
        ),
        client.patch(
            f"/api/v1/monitoring/lan/assets/{asset.id}",
            headers=admin_headers,
            json={"is_authorized": True},
        ),
        client.post(
            f"/api/v1/monitoring/lan/assets/{asset.id}/service-check",
            headers=admin_headers,
        ),
        client.post(
            f"/api/v1/operations/background-jobs/{uuid.uuid4()}/retry",
            headers=admin_headers,
        ),
        client.patch(
            f"/api/v1/notifications/{alert.id}/read", headers=admin_headers
        ),
        client.patch(
            f"/api/v1/notifications/{alert.id}/dismiss", headers=admin_headers
        ),
    ]
    responses = await asyncio.gather(*direct_calls)
    assert all(response.status_code == 403 for response in responses)
    await db.refresh(asset)
    await db.refresh(alert)
    assert asset.is_authorized is False
    assert alert.status == "unread"


@pytest.mark.asyncio
async def test_protected_service_and_analyst_local_control_are_denied(
    client, admin_headers, analyst_headers
):
    protected = await client.post(
        "/api/v1/actions/proposals",
        headers=admin_headers,
        json={
            "action_id": "raventech.service.stop",
            "target_id": "RpcSs",
            "reason": "A model said to stop this service.",
            "target_snapshot": {
                **_service_snapshot(name="RpcSs"),
                "action_available": False,
            },
        },
    )
    assert protected.status_code == 403

    denied = await client.post(
        "/api/v1/actions/proposals",
        headers=analyst_headers,
        json={
            "action_id": "raventech.service.restart",
            "target_id": "RavenTechTestService",
            "reason": "Restart requested.",
            "target_snapshot": _service_snapshot(),
        },
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_process_identity_revalidation_refuses_pid_reuse(client, admin_headers):
    created = await client.post(
        "/api/v1/actions/proposals",
        headers=admin_headers,
        json={
            "action_id": "raventech.process.terminate",
            "target_id": "24680",
            "target_display_name": "safe-fixture-process.exe (24680)",
            "reason": "Operator selected one temporary safe test process.",
            "target_snapshot": _process_snapshot(),
        },
    )
    assert created.status_code == 201
    proposal = created.json()
    confirmation = proposal["approval_confirmation"]
    approved = await client.post(
        f"/api/v1/actions/proposals/{proposal['id']}/approve",
        headers=admin_headers,
        json={
            "confirmation_text": confirmation,
            "current_snapshot": _process_snapshot(),
        },
    )
    assert approved.status_code == 200
    reused = await client.post(
        f"/api/v1/actions/proposals/{proposal['id']}/claim-local",
        headers=admin_headers,
        json={"current_snapshot": _process_snapshot(ticks="987654321")},
    )
    assert reused.status_code == 409
    assert reused.json()["detail"]["code"] == "state_changed_since_approval"


@pytest.mark.asyncio
async def test_high_risk_action_requires_typed_confirmation(client, admin_headers):
    created = await client.post(
        "/api/v1/actions/proposals",
        headers=admin_headers,
        json={
            "action_id": "raventech.service.stop",
            "target_id": "RavenTechTestService",
            "target_display_name": "RavenTech Test Service (RavenTechTestService)",
            "reason": "A deterministic test requires a service stop proposal.",
            "target_snapshot": _service_snapshot(),
        },
    )
    assert created.status_code == 201
    proposal = created.json()
    missing = await client.post(
        f"/api/v1/actions/proposals/{proposal['id']}/approve",
        headers=admin_headers,
        json={
            "confirmation_text": "yes",
            "current_snapshot": _service_snapshot(),
        },
    )
    assert missing.status_code == 422
    accepted = await client.post(
        f"/api/v1/actions/proposals/{proposal['id']}/approve",
        headers=admin_headers,
        json={
            "confirmation_text": proposal["approval_confirmation"],
            "current_snapshot": _service_snapshot(),
        },
    )
    assert accepted.status_code == 200


@pytest.mark.asyncio
async def test_proposal_mutation_invalidates_approval(client, db, admin_headers):
    created = await client.post(
        "/api/v1/actions/proposals",
        headers=admin_headers,
        json={
            "action_id": "raventech.service.restart",
            "target_id": "RavenTechTestService",
            "reason": "Restart a synthetic safe service.",
            "target_snapshot": _service_snapshot(),
        },
    )
    proposal_id = uuid.UUID(created.json()["id"])
    approved = await client.post(
        f"/api/v1/actions/proposals/{proposal_id}/approve",
        headers=admin_headers,
        json={"current_snapshot": _service_snapshot()},
    )
    assert approved.status_code == 200
    proposal = await db.get(ActionProposal, proposal_id)
    assert proposal is not None
    proposal.reason = "Mutated after approval."
    await db.commit()
    claim = await client.post(
        f"/api/v1/actions/proposals/{proposal_id}/claim-local",
        headers=admin_headers,
        json={"current_snapshot": _service_snapshot()},
    )
    assert claim.status_code == 409
    assert claim.json()["detail"]["code"] == "proposal_hash_mismatch"


@pytest.mark.asyncio
async def test_expired_approval_is_refused(client, db, admin_headers):
    created = await client.post(
        "/api/v1/actions/proposals",
        headers=admin_headers,
        json={
            "action_id": "raventech.service.restart",
            "target_id": "RavenTechTestService",
            "reason": "Restart a synthetic safe service.",
            "target_snapshot": _service_snapshot(),
        },
    )
    proposal_id = uuid.UUID(created.json()["id"])
    await client.post(
        f"/api/v1/actions/proposals/{proposal_id}/approve",
        headers=admin_headers,
        json={"current_snapshot": _service_snapshot()},
    )
    approval = (
        await db.execute(
            select(ActionApproval).where(ActionApproval.proposal_id == proposal_id)
        )
    ).scalar_one()
    approval.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db.commit()
    response = await client.post(
        f"/api/v1/actions/proposals/{proposal_id}/claim-local",
        headers=admin_headers,
        json={"current_snapshot": _service_snapshot()},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "approval_expired"


@pytest.mark.asyncio
async def test_global_disable_invalidates_pending_proposals(client, admin_headers):
    created = await client.post(
        "/api/v1/actions/proposals",
        headers=admin_headers,
        json={
            "action_id": "raventech.service.restart",
            "target_id": "RavenTechTestService",
            "reason": "Restart a synthetic safe service.",
            "target_snapshot": _service_snapshot(),
        },
    )
    proposal_id = uuid.UUID(created.json()["id"])
    response = await client.patch(
        "/api/v1/actions/policy", headers=admin_headers, json={"enabled": False}
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    proposal = await client.get(
        f"/api/v1/actions/proposals/{proposal_id}", headers=admin_headers
    )
    assert proposal.json()["status"] == "cancelled"
    denied = await client.post(
        f"/api/v1/actions/proposals/{proposal_id}/approve",
        headers=admin_headers,
        json={},
    )
    assert denied.status_code == 403
    await client.patch(
        "/api/v1/actions/policy", headers=admin_headers, json={"enabled": True}
    )


@pytest.mark.asyncio
async def test_alert_acknowledgement_uses_approved_existing_notification(
    client, db: AsyncSession, analyst_user, analyst_headers
):
    alert = Notification(
        user_id=analyst_user.id,
        entity_type="monitoring_alert",
        notification_type="monitoring_alert",
        severity="warning",
        title="Synthetic monitoring alert",
        message="A synthetic isolated test alert.",
        status="unread",
        event_metadata={},
    )
    db.add(alert)
    await db.commit()
    created = await client.post(
        "/api/v1/actions/proposals",
        headers=analyst_headers,
        json={
            "action_id": "raventech.alert.acknowledge",
            "target_id": str(alert.id),
            "reason": "Operator reviewed this synthetic alert.",
        },
    )
    assert created.status_code == 201
    proposal_id = created.json()["id"]
    assert (
        await client.post(
            f"/api/v1/actions/proposals/{proposal_id}/approve",
            headers=analyst_headers,
            json={},
        )
    ).status_code == 200
    executed = await client.post(
        f"/api/v1/actions/proposals/{proposal_id}/execute", headers=analyst_headers
    )
    assert executed.status_code == 200
    assert executed.json()["status"] == "completed"
    await db.refresh(alert)
    assert alert.status == "read"


@pytest.mark.asyncio
async def test_asset_authorization_and_discovery_are_bounded_registered_actions(
    client, db: AsyncSession, admin_headers, monkeypatch
):
    asset = LanAsset(
        ip_address="192.168.50.212",
        hostname="synthetic-test-device",
        source="host_neighbor_table",
        is_authorized=False,
    )
    db.add(asset)
    await db.commit()
    created = await client.post(
        "/api/v1/actions/proposals",
        headers=admin_headers,
        json={
            "action_id": "raventech.lan.asset.authorize",
            "target_id": str(asset.id),
            "reason": "Operator reviewed this synthetic LAN asset.",
        },
    )
    assert created.status_code == 201
    proposal_id = created.json()["id"]
    assert (
        await client.post(
            f"/api/v1/actions/proposals/{proposal_id}/approve",
            headers=admin_headers,
            json={},
        )
    ).status_code == 200
    result = await client.post(
        f"/api/v1/actions/proposals/{proposal_id}/execute", headers=admin_headers
    )
    assert result.status_code == 200
    await db.refresh(asset)
    assert asset.is_authorized is True

    monkeypatch.setattr(settings, "LAN_MONITORING_ENABLED", True)
    discovery = await client.post(
        "/api/v1/actions/proposals",
        headers=admin_headers,
        json={
            "action_id": "raventech.lan.discovery.run",
            "reason": "Operator requested configured bounded discovery.",
        },
    )
    assert discovery.status_code == 201
    discovery_id = discovery.json()["id"]
    assert (
        await client.post(
            f"/api/v1/actions/proposals/{discovery_id}/approve",
            headers=admin_headers,
            json={},
        )
    ).status_code == 200
    dispatched = await client.post(
        f"/api/v1/actions/proposals/{discovery_id}/execute", headers=admin_headers
    )
    assert dispatched.status_code == 200
    jobs = (
        (
            await db.execute(
                select(BackgroundJob).where(
                    BackgroundJob.job_type == "monitoring.lan_discovery"
                )
            )
        )
        .scalars()
        .all()
    )
    assert any(
        job.status in {"queued", "scheduled", "running", "completed"} for job in jobs
    )


@pytest.mark.asyncio
async def test_unknown_shell_action_and_sensitive_reason_are_refused(
    client, admin_headers
):
    unsupported = await client.post(
        "/api/v1/actions/proposals",
        headers=admin_headers,
        json={"action_id": "shell.execute", "reason": "Run an arbitrary command."},
    )
    assert unsupported.status_code == 422
    secret = await client.post(
        "/api/v1/actions/proposals",
        headers=admin_headers,
        json={
            "action_id": "raventech.lan.discovery.run",
            "reason": "token=temporary-secret-value",
        },
    )
    assert secret.status_code == 422
