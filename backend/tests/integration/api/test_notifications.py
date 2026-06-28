from __future__ import annotations

import uuid

from app.core.security import hash_password
from app.models.audit_log import AuditLog
from app.models.case_closure import CaseClosure
from app.models.notification import Notification
from app.models.user import User
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TEST_PASSWORD


async def test_user_can_list_only_own_notifications(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    analyst_user: User,
    other_user: User,
    test_investigation,
    db: AsyncSession,
) -> None:
    own_notification = Notification(
        user_id=analyst_user.id,
        actor_user_id=analyst_user.id,
        investigation_id=test_investigation.id,
        entity_type="investigation",
        entity_id=test_investigation.id,
        notification_type="closure_review_pending",
        severity="warning",
        title="Review needed",
        message="A case review needs attention.",
        action_url=f"/investigations/{test_investigation.id}/closure",
        dedupe_key=f"test-own:{uuid.uuid4()}",
    )
    other_notification = Notification(
        user_id=other_user.id,
        actor_user_id=analyst_user.id,
        investigation_id=test_investigation.id,
        entity_type="investigation",
        entity_id=test_investigation.id,
        notification_type="scope_warning",
        severity="warning",
        title="Other alert",
        message="This alert belongs to another analyst.",
        dedupe_key=f"test-other:{uuid.uuid4()}",
    )
    db.add_all([own_notification, other_notification])
    await db.commit()

    response = await client.get("/api/v1/notifications", headers=analyst_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["unread"] == 1
    assert body["items"][0]["id"] == str(own_notification.id)
    assert body["items"][0]["metadata"] == {}


async def test_notification_actions_and_filters(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    analyst_user: User,
    db: AsyncSession,
) -> None:
    first = Notification(
        user_id=analyst_user.id,
        actor_user_id=analyst_user.id,
        entity_type="report",
        notification_type="report_ready",
        severity="success",
        title="Report ready",
        message="A report is ready.",
        dedupe_key=f"test-ready:{uuid.uuid4()}",
    )
    second = Notification(
        user_id=analyst_user.id,
        actor_user_id=analyst_user.id,
        entity_type="system",
        notification_type="governance_warning",
        severity="warning",
        title="Governance reminder",
        message="Review governance settings.",
        dedupe_key=f"test-warning:{uuid.uuid4()}",
    )
    db.add_all([first, second])
    await db.commit()

    unread = await client.get(
        "/api/v1/notifications/unread-count",
        headers=analyst_headers,
    )
    assert unread.status_code == 200
    assert unread.json()["unread"] == 2

    filtered = await client.get(
        "/api/v1/notifications?severity=warning&limit=10",
        headers=analyst_headers,
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["severity"] == "warning"

    read = await client.patch(
        f"/api/v1/notifications/{first.id}/read",
        headers=analyst_headers,
    )
    assert read.status_code == 200
    assert read.json()["notification"]["status"] == "read"

    dismissed = await client.patch(
        f"/api/v1/notifications/{second.id}/dismiss",
        headers=analyst_headers,
    )
    assert dismissed.status_code == 200
    assert dismissed.json()["notification"]["status"] == "dismissed"

    third = Notification(
        user_id=analyst_user.id,
        actor_user_id=analyst_user.id,
        entity_type="system",
        notification_type="system_health_warning",
        severity="info",
        title="Health notice",
        message="Platform health notice.",
        dedupe_key=f"test-health:{uuid.uuid4()}",
    )
    db.add(third)
    await db.commit()

    mark_all = await client.post(
        "/api/v1/notifications/mark-all-read",
        headers=analyst_headers,
    )
    assert mark_all.status_code == 200
    assert mark_all.json()["updated"] == 1
    assert mark_all.json()["unread"] == 0

    actions = (
        await db.execute(
            select(AuditLog.action).where(
                AuditLog.action.in_(
                    [
                        "notification.read",
                        "notification.dismissed",
                        "notification.mark_all_read",
                    ]
                )
            )
        )
    ).scalars().all()
    assert "notification.read" in actions
    assert "notification.dismissed" in actions
    assert "notification.mark_all_read" in actions


async def test_user_cannot_update_another_users_notification(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    analyst_user: User,
    other_user: User,
    db: AsyncSession,
) -> None:
    notification = Notification(
        user_id=other_user.id,
        actor_user_id=analyst_user.id,
        entity_type="system",
        notification_type="governance_warning",
        severity="warning",
        title="Private alert",
        message="This should remain private.",
        dedupe_key=f"test-private:{uuid.uuid4()}",
    )
    db.add(notification)
    await db.commit()

    response = await client.patch(
        f"/api/v1/notifications/{notification.id}/read",
        headers=analyst_headers,
    )

    assert response.status_code == 404


async def test_admin_rebuild_workflow_alerts_is_deduplicated(
    client: AsyncClient,
    admin_headers: dict[str, str],
    analyst_user: User,
    test_investigation,
    db: AsyncSession,
) -> None:
    pending_user = User(
        username="pending_notification",
        email="pending.notification@raventech.dev",
        hashed_password=hash_password(TEST_PASSWORD),
        role="analyst",
        is_active=False,
        account_status="pending",
        registration_source="public_registration",
    )
    closure = CaseClosure(
        investigation_id=test_investigation.id,
        status="in_review",
        closure_summary="Ready for administrator review.",
        reviewed_by=analyst_user.id,
    )
    db.add_all([pending_user, closure])
    await db.commit()

    first = await client.post(
        "/api/v1/notifications/rebuild-workflow-alerts",
        headers=admin_headers,
    )
    assert first.status_code == 200
    assert first.json()["created"] >= 2

    count_after_first = (
        await db.execute(select(func.count()).select_from(Notification))
    ).scalar_one()
    second = await client.post(
        "/api/v1/notifications/rebuild-workflow-alerts",
        headers=admin_headers,
    )
    count_after_second = (
        await db.execute(select(func.count()).select_from(Notification))
    ).scalar_one()

    assert second.status_code == 200
    assert second.json()["created"] == 0
    assert count_after_second == count_after_first

    actions = (
        await db.execute(
            select(AuditLog.action).where(
                AuditLog.action.in_(
                    [
                        "notification.created",
                        "notification.workflow_alert_generated",
                    ]
                )
            )
        )
    ).scalars().all()
    assert "notification.created" in actions
    assert "notification.workflow_alert_generated" in actions
