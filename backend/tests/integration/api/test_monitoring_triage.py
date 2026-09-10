from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.monitoring_policy import AlertSuppression, MaintenanceWindow
from app.models.notification import Notification
from app.models.user import User
from app.services.notification import create_notification

pytestmark = pytest.mark.asyncio


async def _alert(db, user: User, *, severity: str = "warning", suffix: str = "one") -> Notification:
    result = await create_notification(
        db,
        user_id=user.id,
        actor_user_id=user.id,
        notification_type="monitoring_alert",
        severity=severity,
        title="Local monitoring condition",
        message="A defensive monitoring condition needs review.",
        entity_type="monitoring",
        metadata={"category": "local_health"},
        dedupe_key=f"test:triage:{user.id}:{suffix}",
    )
    await db.commit()
    return result.notification


async def test_triage_lifecycle_assignment_filters_and_audit(
    client, db, analyst_user: User, analyst_headers
) -> None:
    alert = await _alert(db, analyst_user)
    listing = await client.get("/api/v1/monitoring/triage", headers=analyst_headers)
    assert listing.status_code == 200
    assert listing.json()["items"][0]["status"] == "new"

    assigned = await client.post(
        f"/api/v1/monitoring/triage/{alert.id}/assign",
        headers=analyst_headers,
        json={"owner_id": str(analyst_user.id)},
    )
    assert assigned.status_code == 200
    assert assigned.json()["status"] == "triaged"
    assert assigned.json()["owner_id"] == str(analyst_user.id)

    investigating = await client.patch(
        f"/api/v1/monitoring/triage/{alert.id}",
        headers=analyst_headers,
        json={"status": "investigating", "notes": "Reviewing local telemetry."},
    )
    assert investigating.status_code == 200
    assert investigating.json()["status"] == "investigating"
    filtered = await client.get(
        "/api/v1/monitoring/triage?status=investigating&severity=warning&source=local_health",
        headers=analyst_headers,
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1

    resolved = await client.post(
        f"/api/v1/monitoring/triage/{alert.id}/resolve",
        headers=analyst_headers,
        json={"resolution_summary": "Service recovered after local review."},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    duplicate = await client.post(
        f"/api/v1/monitoring/triage/{alert.id}/resolve",
        headers=analyst_headers,
        json={"resolution_summary": "Repeated resolution request."},
    )
    assert duplicate.status_code == 409
    await db.rollback()
    actions = set((await db.execute(select(AuditLog.action))).scalars().all())
    assert {"monitoring.alert_assigned", "monitoring.alert_triaged", "monitoring.alert_resolved"} <= actions


async def test_false_positive_mute_unmute_and_suppression_visibility(
    client, db, admin_user: User, admin_headers
) -> None:
    muted_alert = await _alert(db, admin_user, suffix="mute")
    muted = await client.post(
        f"/api/v1/monitoring/triage/{muted_alert.id}/mute",
        headers=admin_headers,
        json={"reason": "Known approved maintenance activity."},
    )
    assert muted.status_code == 200
    assert muted.json()["status"] == "muted"
    assert muted.json()["suppressed"] is True
    unmuted = await client.patch(
        f"/api/v1/monitoring/triage/{muted_alert.id}",
        headers=admin_headers,
        json={"status": "triaged"},
    )
    assert unmuted.status_code == 200
    assert unmuted.json()["suppressed"] is False

    false_alert = await _alert(db, admin_user, suffix="false")
    false_positive = await client.post(
        f"/api/v1/monitoring/triage/{false_alert.id}/false-positive",
        headers=admin_headers,
        json={"resolution_summary": "Expected test fixture behavior."},
    )
    assert false_positive.status_code == 200
    assert false_positive.json()["status"] == "false_positive"
    await db.rollback()
    suppressions = list((await db.execute(select(AlertSuppression))).scalars().all())
    assert suppressions and all(not item.active for item in suppressions)
    actions = set((await db.execute(select(AuditLog.action))).scalars().all())
    assert {"monitoring.alert_muted", "monitoring.alert_unmuted", "monitoring.alert_false_positive"} <= actions


async def test_triage_rbac_maintenance_and_no_secret_exposure(
    client, db, admin_user: User, analyst_user: User, admin_headers, analyst_headers
) -> None:
    admin_alert = await _alert(db, admin_user, severity="critical", suffix="admin")
    assert (await client.get("/api/v1/monitoring/triage")).status_code == 401
    analyst_listing = await client.get("/api/v1/monitoring/triage", headers=analyst_headers)
    assert analyst_listing.status_code == 200
    assert analyst_listing.json()["total"] == 0
    denied = await client.post(
        f"/api/v1/monitoring/triage/{admin_alert.id}/assign",
        headers=analyst_headers,
        json={"owner_id": str(analyst_user.id)},
    )
    assert denied.status_code == 404

    now = datetime.now(UTC)
    db.add(
        MaintenanceWindow(
            title="Approved monitoring work",
            start_time=now - timedelta(minutes=5),
            end_time=now + timedelta(hours=1),
            affected_assets=[],
            affected_services=["system"],
            suppress_alerts=True,
            reason="Approved local maintenance.",
            created_by=admin_user.id,
        )
    )
    db.add(
        AlertSuppression(
            alert_id=admin_alert.id,
            source="maintenance",
            reason="Active approved maintenance window.",
            starts_at=now,
            ends_at=now + timedelta(hours=1),
            active=True,
            created_by=admin_user.id,
        )
    )
    await db.commit()
    admin_listing = await client.get("/api/v1/monitoring/triage", headers=admin_headers)
    item = admin_listing.json()["items"][0]
    assert item["suppressed"] is True
    assert item["suppressed_due_to_maintenance"] is True
    assert "password" not in str(item).lower()
    invalid = await client.patch(
        f"/api/v1/monitoring/triage/{admin_alert.id}",
        headers=admin_headers,
        json={"notes": "password=do-not-store"},
    )
    assert invalid.status_code == 422


async def test_critical_alert_requires_admin_to_mute_and_recovered_alert_auto_resolves(
    client, db, analyst_user: User, analyst_headers
) -> None:
    critical = await _alert(db, analyst_user, severity="critical", suffix="critical")
    denied = await client.post(
        f"/api/v1/monitoring/triage/{critical.id}/mute",
        headers=analyst_headers,
        json={"reason": "Analyst requested mute."},
    )
    assert denied.status_code == 403
    critical.event_metadata = {"category": "local_health", "recovered_at": datetime.now(UTC).isoformat()}
    await db.commit()
    listing = await client.get("/api/v1/monitoring/triage", headers=analyst_headers)
    item = listing.json()["items"][0]
    assert item["status"] == "resolved"
    assert item["resolution_summary"] == "Monitoring condition recovered automatically."
