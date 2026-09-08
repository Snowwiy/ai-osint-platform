from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.engagement import Engagement
from app.models.finding import Finding
from app.models.notification import Notification
from app.models.saved_view import SavedView
from app.models.user import User
from tests.conftest import TEST_PASSWORD


async def test_data_quality_scan_is_admin_only(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    forbidden = await client.post(
        "/api/v1/admin/data-quality/run",
        headers=analyst_headers,
    )
    assert forbidden.status_code == 403

    allowed = await client.post(
        "/api/v1/admin/data-quality/run",
        headers=admin_headers,
    )
    assert allowed.status_code == 200
    body = allowed.json()
    assert body["detected"] >= 0
    assert body["created"] >= 0
    assert body["overview"]["scan_status"] in {
        "healthy",
        "attention",
        "critical",
    }


async def test_scan_detects_cross_workflow_quality_issues(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: User,
    analyst_user: User,
    test_investigation,
    db: AsyncSession,
) -> None:
    first = Finding(
        investigation_id=test_investigation.id,
        title="Repeated defensive observation",
        description="Synthetic finding used to verify deterministic duplicate checks.",
        severity="high",
        source="manual",
        created_by=analyst_user.id,
    )
    second = Finding(
        investigation_id=test_investigation.id,
        title="Repeated defensive observation",
        description="Second synthetic record for data quality review.",
        severity="high",
        source="manual",
        created_by=analyst_user.id,
    )
    pending_user = User(
        username="quality_pending",
        email="quality.pending@example.invalid",
        hashed_password=hash_password(TEST_PASSWORD),
        role="analyst",
        is_active=False,
        account_status="pending",
        registration_source="public_registration",
        created_at=datetime.now(UTC) - timedelta(days=20),
        updated_at=datetime.now(UTC) - timedelta(days=20),
    )
    expired_engagement = Engagement(
        title="Expired defensive engagement",
        client_name="Example Quality Client",
        status="active",
        authorization_status="expired",
        end_date=date.today() - timedelta(days=2),
        created_by=admin_user.id,
    )
    stale_notification = Notification(
        user_id=admin_user.id,
        actor_user_id=admin_user.id,
        entity_type="system",
        notification_type="governance_warning",
        severity="warning",
        title="Old governance reminder",
        message="Synthetic stale notification.",
        action_url="/admin/settings",
        status="unread",
        dedupe_key="quality-test-stale-notification",
        created_at=datetime.now(UTC) - timedelta(days=40),
        updated_at=datetime.now(UTC) - timedelta(days=40),
    )
    malformed_view = SavedView(
        user_id=admin_user.id,
        name="Malformed quality view",
        view_type="search",
        route="https://unsafe.example.invalid/redirect",
        filters=[],  # type: ignore[arg-type]
        is_pinned=True,
    )
    db.add_all(
        [
            first,
            second,
            pending_user,
            expired_engagement,
            stale_notification,
            malformed_view,
        ]
    )
    await db.commit()

    response = await client.post(
        "/api/v1/admin/data-quality/run",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["created"] >= 5

    issues = await client.get(
        "/api/v1/admin/data-quality/issues?limit=200",
        headers=admin_headers,
    )
    assert issues.status_code == 200
    body = issues.json()
    issue_types = {item["issue_type"] for item in body["items"]}
    assert "duplicate_finding" in issue_types
    assert "high_risk_finding_without_evidence" in issue_types
    assert "stale_pending_user" in issue_types
    assert "active_engagement_without_approved_authorization" in issue_types
    assert "active_engagement_past_end_date" in issue_types
    assert "stale_unread_notification" in issue_types
    assert "saved_view_invalid_route" in issue_types
    assert "saved_view_malformed_filters" in issue_types

    serialized = json.dumps(body).casefold()
    for forbidden_key in (
        "hashed_password",
        "invite_code",
        "database_url",
        "anthropic_api_key",
    ):
        assert forbidden_key not in serialized


async def test_issue_workflow_and_audit_events(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: User,
    db: AsyncSession,
) -> None:
    pending_user = User(
        username="quality_workflow_pending",
        email="quality.workflow@example.invalid",
        hashed_password=hash_password(TEST_PASSWORD),
        role="analyst",
        is_active=False,
        account_status="pending",
        created_at=datetime.now(UTC) - timedelta(days=30),
        updated_at=datetime.now(UTC) - timedelta(days=30),
    )
    db.add(pending_user)
    await db.commit()

    scan = await client.post(
        "/api/v1/admin/data-quality/run",
        headers=admin_headers,
    )
    assert scan.status_code == 200

    issues = await client.get(
        "/api/v1/admin/data-quality/issues?issue_type=stale_pending_user",
        headers=admin_headers,
    )
    issue_id = issues.json()["items"][0]["id"]

    acknowledged = await client.patch(
        f"/api/v1/admin/data-quality/issues/{issue_id}/acknowledge",
        headers=admin_headers,
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"

    resolved = await client.patch(
        f"/api/v1/admin/data-quality/issues/{issue_id}/resolve",
        headers=admin_headers,
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"

    invalid = await client.patch(
        f"/api/v1/admin/data-quality/issues/{issue_id}/ignore",
        headers=admin_headers,
    )
    assert invalid.status_code == 409

    actions = set(
        (
            await db.scalars(
                select(AuditLog.action).where(
                    AuditLog.action.in_(
                        [
                            "data_quality.scan_started",
                            "data_quality.scan_completed",
                            "data_quality.issue_detected",
                            "data_quality.issue_acknowledged",
                            "data_quality.issue_resolved",
                        ]
                    )
                )
            )
        ).all()
    )
    assert "data_quality.scan_started" in actions
    assert "data_quality.scan_completed" in actions
    assert "data_quality.issue_detected" in actions
    assert "data_quality.issue_acknowledged" in actions
    assert "data_quality.issue_resolved" in actions


async def test_maintenance_dry_run_and_safe_notification_archive(
    client: AsyncClient,
    admin_headers: dict[str, str],
    admin_user: User,
    db: AsyncSession,
) -> None:
    stale_read = Notification(
        user_id=admin_user.id,
        actor_user_id=admin_user.id,
        entity_type="system",
        notification_type="governance_warning",
        severity="info",
        title="Read maintenance notification",
        message="Synthetic maintenance record.",
        status="read",
        dedupe_key="quality-test-read-archive",
        created_at=datetime.now(UTC) - timedelta(days=120),
        updated_at=datetime.now(UTC) - timedelta(days=120),
    )
    current_unread = Notification(
        user_id=admin_user.id,
        actor_user_id=admin_user.id,
        entity_type="system",
        notification_type="system_health_warning",
        severity="info",
        title="Current unread notification",
        message="This record must remain unread.",
        status="unread",
        dedupe_key="quality-test-unread-preserved",
    )
    db.add_all([stale_read, current_unread])
    await db.commit()

    dry_run = await client.post(
        "/api/v1/admin/maintenance/dry-run",
        headers=admin_headers,
    )
    assert dry_run.status_code == 200
    assert dry_run.json()["destructive_changes"] is False

    archived = await client.post(
        "/api/v1/admin/maintenance/archive-stale-notifications",
        headers=admin_headers,
        json={"older_than_days": 90},
    )
    assert archived.status_code == 200
    assert archived.json()["archived"] == 1

    await db.refresh(stale_read)
    await db.refresh(current_unread)
    assert stale_read.status == "archived"
    assert current_unread.status == "unread"
