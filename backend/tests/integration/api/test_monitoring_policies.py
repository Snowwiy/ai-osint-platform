from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.monitoring_policy import AlertSuppression, MaintenanceWindow
from app.models.notification import Notification
from app.models.user import User
from app.schemas.monitoring import (
    MonitoringAssetsResponse,
    MonitoringServicesResponse,
    MonitoringSystemResponse,
)
from app.services.local_monitoring import get_monitoring_alerts
from app.services.notification import create_notification

pytestmark = pytest.mark.asyncio


async def test_policy_read_create_update_and_admin_rbac(
    client, admin_headers, analyst_headers
) -> None:
    listing = await client.get("/api/v1/monitoring/policies", headers=analyst_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 10
    assert all("token" not in str(item).lower() for item in listing.json()["items"])

    denied = await client.post(
        "/api/v1/monitoring/policies",
        headers=analyst_headers,
        json={
            "rule_key": "custom.safe_rule",
            "title": "Safe custom rule",
            "description": "A local passive monitoring rule.",
            "cooldown_minutes": 120,
            "dedupe_key": "custom.safe_rule",
        },
    )
    assert denied.status_code == 403

    created = await client.post(
        "/api/v1/monitoring/policies",
        headers=admin_headers,
        json={
            "rule_key": "custom.safe_rule",
            "title": "Safe custom rule",
            "description": "A local passive monitoring rule.",
            "cooldown_minutes": 120,
            "dedupe_key": "custom.safe_rule",
        },
    )
    assert created.status_code == 201
    policy_id = created.json()["id"]
    updated = await client.patch(
        f"/api/v1/monitoring/policies/{policy_id}",
        headers=admin_headers,
        json={"cooldown_minutes": 360, "max_alerts_per_rule": 2},
    )
    assert updated.status_code == 200
    assert updated.json()["cooldown_minutes"] == 360
    missing = await client.patch(
        "/api/v1/monitoring/policies/00000000-0000-0000-0000-000000000000",
        headers=admin_headers,
        json={"enabled": False},
    )
    assert missing.status_code == 404


async def test_alert_suppression_unsuppression_and_audit(
    client, db, admin_user: User, admin_headers
) -> None:
    result = await create_notification(
        db,
        user_id=admin_user.id,
        actor_user_id=admin_user.id,
        notification_type="monitoring_alert",
        severity="critical",
        title="Critical local alert",
        message="Safe test alert.",
        entity_type="monitoring",
        dedupe_key="test:monitoring:suppression",
    )
    await db.commit()
    alert_id = result.notification.id
    suppressed = await client.post(
        f"/api/v1/monitoring/alerts/{alert_id}/suppress",
        headers=admin_headers,
        json={"reason": "Approved investigation window."},
    )
    assert suppressed.status_code == 200
    assert suppressed.json()["active"] is True
    duplicate = await client.post(
        f"/api/v1/monitoring/alerts/{alert_id}/suppress",
        headers=admin_headers,
        json={"reason": "Duplicate request."},
    )
    assert duplicate.status_code == 409
    unsuppressed = await client.post(
        f"/api/v1/monitoring/alerts/{alert_id}/unsuppress",
        headers=admin_headers,
    )
    assert unsuppressed.status_code == 200
    assert unsuppressed.json()["active"] is False
    actions = set((await db.execute(select(AuditLog.action))).scalars().all())
    assert "monitoring.alert_suppressed" in actions
    assert "monitoring.alert_unsuppressed" in actions


async def test_maintenance_window_suppresses_but_retains_alert(
    db, admin_user: User
) -> None:
    now = datetime.now(UTC)
    db.add(
        MaintenanceWindow(
            title="Database maintenance",
            start_time=now - timedelta(minutes=5),
            end_time=now + timedelta(hours=1),
            affected_assets=[],
            affected_services=["system"],
            suppress_alerts=True,
            reason="Approved database maintenance.",
            created_by=admin_user.id,
        )
    )
    services = MonitoringServicesResponse(generated_at=now, status="healthy", items=[])
    system = MonitoringSystemResponse(
        generated_at=now,
        source="container",
        metric_scope="test",
        available=True,
        stale=False,
        platform="test",
        cpu_percent=96,
        detail="Local test sample.",
    )
    assets = MonitoringAssetsResponse(
        generated_at=now,
        stale_after_days=30,
        investigations=0,
        targets=0,
        healthy_assets=0,
        assets_needing_review=0,
        stale_assets=0,
        high_risk_assets=0,
        out_of_scope_assets=0,
        unresolved_high=0,
        unresolved_critical=0,
        findings_by_severity={},
        authorization_risks=0,
        repeated_report_failures=0,
        repeated_ai_degraded=0,
        items=[],
    )
    response = await get_monitoring_alerts(
        db, admin_user, services=services, system=system, assets=assets
    )
    cpu = next(item for item in response.items if item.key.startswith("system:cpu"))
    assert cpu.id is not None
    assert cpu.suppressed is True
    assert cpu.suppressed_due_to_maintenance is True
    assert await db.get(Notification, cpu.id) is not None
    suppression = (
        await db.execute(
            select(AlertSuppression).where(AlertSuppression.alert_id == cpu.id)
        )
    ).scalar_one()
    assert suppression.source == "maintenance"


async def test_policy_cooldown_and_dedupe_limit_notifications(
    db, admin_user: User
) -> None:
    now = datetime.now(UTC)
    services = MonitoringServicesResponse(generated_at=now, status="healthy", items=[])
    system = MonitoringSystemResponse(
        generated_at=now,
        source="container",
        metric_scope="test",
        available=True,
        stale=False,
        platform="test",
        disk_percent=95,
        detail="Local test sample.",
    )
    assets = MonitoringAssetsResponse(
        generated_at=now,
        stale_after_days=30,
        investigations=0,
        targets=0,
        healthy_assets=0,
        assets_needing_review=0,
        stale_assets=0,
        high_risk_assets=0,
        out_of_scope_assets=0,
        unresolved_high=0,
        unresolved_critical=0,
        findings_by_severity={},
        authorization_risks=0,
        repeated_report_failures=0,
        repeated_ai_degraded=0,
        items=[],
    )
    first = await get_monitoring_alerts(
        db, admin_user, services=services, system=system, assets=assets
    )
    second = await get_monitoring_alerts(
        db, admin_user, services=services, system=system, assets=assets
    )
    assert first.notifications_created == 1
    assert second.notifications_created == 0
    assert second.notifications_existing == 1


async def test_maintenance_window_endpoints_validate_and_enforce_rbac(
    client, admin_headers, analyst_headers
) -> None:
    now = datetime.now(UTC)
    payload = {
        "title": "Local patching",
        "start_time": (now + timedelta(hours=1)).isoformat(),
        "end_time": (now + timedelta(hours=2)).isoformat(),
        "affected_assets": [],
        "affected_services": ["database"],
        "suppress_alerts": True,
        "reason": "Approved local database patching.",
    }
    assert (
        await client.post(
            "/api/v1/monitoring/maintenance-windows",
            headers=analyst_headers,
            json=payload,
        )
    ).status_code == 403
    created = await client.post(
        "/api/v1/monitoring/maintenance-windows", headers=admin_headers, json=payload
    )
    assert created.status_code == 201
    listing = await client.get(
        "/api/v1/monitoring/maintenance-windows", headers=analyst_headers
    )
    assert listing.status_code == 200
    assert listing.json()["items"][0]["created_by"]
    invalid = {**payload, "end_time": payload["start_time"]}
    assert (
        await client.post(
            "/api/v1/monitoring/maintenance-windows",
            headers=admin_headers,
            json=invalid,
        )
    ).status_code == 422
    assert (await client.get("/api/v1/monitoring/policies")).status_code == 401
