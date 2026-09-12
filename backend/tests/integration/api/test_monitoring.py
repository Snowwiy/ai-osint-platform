from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.engagement import Engagement
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.lan_monitoring import LanAsset
from app.models.notification import Notification
from app.models.report import Report
from app.models.target import Target
from app.models.user import User
from app.schemas.monitoring import (
    MonitoringAlertsResponse,
    MonitoringAssetsResponse,
    MonitoringServicesResponse,
    MonitoringServiceStatus,
    MonitoringSystemResponse,
)
from app.services.local_monitoring import (
    _overall_monitoring_status,
    _retire_recovered_alerts,
    _reset_agent_telemetry_for_tests,
    get_monitoring_alerts,
)
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def test_monitoring_endpoints_require_authentication(client: AsyncClient) -> None:
    for path in (
        "/api/v1/monitoring/overview",
        "/api/v1/monitoring/services",
        "/api/v1/monitoring/system",
        "/api/v1/monitoring/assets",
        "/api/v1/monitoring/alerts",
    ):
        response = await client.get(path)
        assert response.status_code in {401, 403}


async def test_monitoring_overview_and_services_are_safe(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    test_investigation: Investigation,
) -> None:
    _reset_agent_telemetry_for_tests()
    services = await client.get("/api/v1/monitoring/services", headers=analyst_headers)
    overview = await client.get("/api/v1/monitoring/overview", headers=analyst_headers)

    assert services.status_code == 200
    assert {item["key"] for item in services.json()["items"]} >= {
        "backend",
        "readiness",
        "release",
        "database",
        "redis",
        "worker",
        "migrations",
        "report_storage",
        "docker",
    }
    assert overview.status_code == 200
    body = overview.json()
    assert body["release_version"] == "5.0.0-rc6"
    assert body["recommended_polling_interval"] in body["polling_interval_options"]
    assert body["system"]["source"] == "container"
    assert body["system"]["metric_scope"] == "backend container"
    assert body["assets"]["investigations"] == 1
    serialized = json.dumps(body).lower()
    for forbidden in (
        "database_url",
        "redis_url",
        "authorization_header",
        "password_hash",
        "access_token",
        settings.APP_SECRET_KEY.lower(),
    ):
        assert forbidden not in serialized


def test_optional_container_telemetry_does_not_degrade_platform() -> None:
    services = MonitoringServicesResponse(
        generated_at=datetime.now(UTC), status="healthy", items=[]
    )
    alerts = MonitoringAlertsResponse(
        generated_at=datetime.now(UTC),
        total=1,
        notifications_created=0,
        notifications_existing=1,
        items=[],
    )

    assert _overall_monitoring_status(services, alerts) == "healthy"


async def test_recovered_overview_notification_is_retired(
    db: AsyncSession,
    analyst_user: User,
) -> None:
    notification = Notification(
        user_id=analyst_user.id,
        entity_type="local_monitoring",
        notification_type="monitoring_alert",
        severity="warning",
        title="Recovered synthetic condition",
        message="Synthetic alert for deterministic recovery testing.",
        status="unread",
        event_metadata={
            "rule": "service:database:degraded",
            "managed_by_overview": True,
        },
    )
    db.add(notification)
    await db.flush()

    await _retire_recovered_alerts(db, analyst_user, active_keys=set())

    assert notification.status == "dismissed"
    assert notification.dismissed_at is not None
    assert "recovered_at" in notification.event_metadata


async def test_asset_watch_respects_rbac_and_summarizes_risk(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    admin_headers: dict[str, str],
    analyst_user: User,
    other_user: User,
    test_investigation: Investigation,
    db: AsyncSession,
) -> None:
    engagement = Engagement(
        title="Expired synthetic authorization",
        client_name="Example Client",
        status="active",
        authorization_status="expired",
        created_by=analyst_user.id,
    )
    db.add(engagement)
    await db.flush()
    test_investigation.engagement_id = engagement.id
    test_investigation.scope_review_status = "out_of_scope"
    stale_target = Target(
        investigation_id=test_investigation.id,
        target_type="domain",
        target_value="stale.example.invalid",
        created_by=analyst_user.id,
        created_at=datetime.now(UTC) - timedelta(days=45),
    )
    critical = Finding(
        investigation_id=test_investigation.id,
        title="Synthetic critical review item",
        description="Stored defensive evidence needs analyst review.",
        severity="critical",
        source="manual",
        status="new",
        created_by=analyst_user.id,
    )
    hidden_investigation = Investigation(
        title="Other analyst private case",
        owner_id=other_user.id,
        authorization_statement=(
            "Written authorization for a separate synthetic defensive assessment "
            "owned by another analyst and not shared with the current user."
        ),
        status="active",
    )
    db.add_all([stale_target, critical, hidden_investigation])
    await db.commit()

    analyst = await client.get("/api/v1/monitoring/assets", headers=analyst_headers)
    admin = await client.get("/api/v1/monitoring/assets", headers=admin_headers)

    assert analyst.status_code == 200
    assert analyst.json()["investigations"] == 1
    assert analyst.json()["stale_assets"] == 1
    assert analyst.json()["unresolved_critical"] == 1
    assert analyst.json()["findings_by_severity"]["critical"] == 1
    assert analyst.json()["out_of_scope_assets"] == 1
    assert analyst.json()["authorization_risks"] == 1
    assert admin.status_code == 200
    assert admin.json()["investigations"] == 2


async def test_monitoring_alert_notifications_are_deduplicated(
    db: AsyncSession,
    analyst_user: User,
) -> None:
    services = MonitoringServicesResponse(
        generated_at=datetime.now(UTC),
        status="healthy",
        items=[
            MonitoringServiceStatus(
                key="database",
                label="PostgreSQL",
                status="healthy",
                detail="Database status is healthy.",
            )
        ],
    )
    system = MonitoringSystemResponse(
        generated_at=datetime.now(UTC),
        source="container",
        metric_scope="test container",
        available=True,
        stale=False,
        platform="test",
        collected_at=datetime.now(UTC),
        cpu_percent=10,
        memory_percent=20,
        disk_percent=30,
        detail="Deterministic test telemetry.",
    )
    assets = MonitoringAssetsResponse(
        generated_at=datetime.now(UTC),
        stale_after_days=30,
        investigations=1,
        targets=1,
        healthy_assets=0,
        assets_needing_review=1,
        stale_assets=1,
        high_risk_assets=1,
        out_of_scope_assets=0,
        unresolved_high=1,
        unresolved_critical=0,
        findings_by_severity={"high": 1},
        authorization_risks=0,
        repeated_report_failures=0,
        repeated_ai_degraded=0,
        items=[],
    )

    first = await get_monitoring_alerts(
        db, analyst_user, services=services, system=system, assets=assets
    )
    second = await get_monitoring_alerts(
        db, analyst_user, services=services, system=system, assets=assets
    )

    assert first.total == 2
    assert first.notifications_created == 2
    assert second.notifications_created == 0
    assert second.notifications_existing == 2
    count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Notification)
                .where(Notification.notification_type == "monitoring_alert")
            )
        ).scalar_one()
    )
    assert count == 2


async def test_agent_ingest_is_admin_only_and_validated(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    _reset_agent_telemetry_for_tests()
    payload = {
        "agent_id": "local-test",
        "platform": "windows",
        "agent_role": "server_host",
        "hostname": "RAVEN-SERVER",
        "os_name": "Windows",
        "os_version": "11",
        "os_build": "26100",
        "collected_at": datetime.now(UTC).isoformat(),
        "cpu_percent": 12.5,
        "memory_percent": 35.5,
        "disk_percent": 44.0,
        "process_count": 100,
        "uptime_seconds": 3600,
    }
    forbidden = await client.post(
        "/api/v1/monitoring/agent/ingest",
        headers=analyst_headers,
        json=payload,
    )
    invalid = await client.post(
        "/api/v1/monitoring/agent/ingest",
        headers=admin_headers,
        json={**payload, "cpu_percent": 101},
    )
    accepted = await client.post(
        "/api/v1/monitoring/agent/ingest",
        headers=admin_headers,
        json=payload,
    )
    system = await client.get("/api/v1/monitoring/system", headers=analyst_headers)

    assert forbidden.status_code == 403
    assert invalid.status_code == 422
    assert accepted.status_code == 202
    assert accepted.json()["accepted"] is True
    assert system.status_code == 200
    assert system.json()["source"] == "server_endpoint_agent"
    assert system.json()["agent_id"] == "local-test"
    assert system.json()["hostname"] == "RAVEN-SERVER"
    assert system.json()["cpu_percent"] == 12.5
    _reset_agent_telemetry_for_tests()


async def test_server_host_agent_precedes_backend_host_agent(
    client: AsyncClient,
    admin_headers: dict[str, str],
    analyst_headers: dict[str, str],
) -> None:
    _reset_agent_telemetry_for_tests()
    base = {
        "platform": "windows",
        "collected_at": datetime.now(UTC).isoformat(),
        "cpu_percent": 10,
    }
    backend = await client.post(
        "/api/v1/monitoring/agent/ingest",
        headers=admin_headers,
        json={**base, "agent_id": "backend-host", "agent_role": "backend_host"},
    )
    server = await client.post(
        "/api/v1/monitoring/agent/ingest",
        headers=admin_headers,
        json={**base, "agent_id": "server-host", "agent_role": "server_host"},
    )
    system = await client.get("/api/v1/monitoring/system", headers=analyst_headers)

    assert backend.status_code == 202
    assert server.status_code == 202
    assert system.json()["source"] == "server_endpoint_agent"
    assert system.json()["agent_id"] == "server-host"
    _reset_agent_telemetry_for_tests()


async def test_server_host_registers_asset_and_ingests_safe_neighbors(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LAN_MONITORING_ENABLED", True)
    monkeypatch.setattr(settings, "LAN_REJECT_PUBLIC_CIDRS", True)
    monkeypatch.setattr(settings, "LAN_ALLOWED_CIDRS", "192.168.50.0/24")
    monkeypatch.setattr(settings, "LAN_GATEWAY_HINT", "192.168.50.1")
    now = datetime.now(UTC).isoformat()
    payload = {
        "agent_id": "primary-server",
        "platform": "windows",
        "agent_role": "server_host",
        "hostname": "RAVEN-SERVER",
        "ip_address": "192.168.50.201",
        "mac_address": "00-11-22-33-44-55",
        "os_name": "Windows",
        "os_version": "11",
        "collected_at": now,
        "cpu_percent": 10,
        "neighbor_observations": [
            {
                "ip_address": "192.168.50.1",
                "mac_address": "AA-BB-CC-DD-EE-01",
                "interface_name": "Wi-Fi",
                "state": "reachable",
                "observed_at": now,
            },
            {
                "ip_address": "192.168.50.40",
                "mac_address": "AA-BB-CC-DD-EE-40",
                "interface_name": "Wi-Fi",
                "state": "stale",
                "observed_at": now,
            },
            {
                "ip_address": "192.168.50.41",
                "mac_address": "AA-BB-CC-DD-EE-40",
                "interface_name": "Wi-Fi",
                "state": "unreachable",
                "observed_at": now,
            },
            {
                "ip_address": "192.168.60.9",
                "mac_address": "AA-BB-CC-DD-EE-60",
                "state": "reachable",
                "observed_at": now,
            },
        ],
    }
    manual = LanAsset(
        ip_address="192.168.50.40",
        mac_address="AA:BB:CC:DD:EE:40",
        hostname="Operator workstation",
        status="online",
        source="router",
        is_authorized=True,
        monitoring_enabled=True,
    )
    db.add(manual)
    await db.commit()
    accepted = await client.post(
        "/api/v1/monitoring/agent/ingest", headers=admin_headers, json=payload
    )
    listing = await client.get(
        "/api/v1/monitoring/lan/assets", headers=admin_headers
    )
    posture = await client.get(
        "/api/v1/monitoring/posture/overview", headers=admin_headers
    )

    assert accepted.status_code == 202
    result = accepted.json()
    assert result["lan_asset_registered"] is True
    assert result["neighbor_observations_received"] == 4
    assert result["neighbor_observations_accepted"] == 2
    assert result["neighbor_observations_rejected"] == 1
    items = listing.json()["items"]
    server = next(item for item in items if item["ip_address"] == "192.168.50.201")
    gateway = next(item for item in items if item["ip_address"] == "192.168.50.1")
    deduped = next(item for item in items if item["mac_address"] == "AA:BB:CC:DD:EE:40")
    assert server["source"] == "endpoint_agent"
    assert server["asset_type"] == "server_host"
    assert server["agent_connected"] is True
    assert gateway["source"] == "host_neighbor_table"
    assert gateway["asset_type"] == "gateway"
    assert "gateway/router" in gateway["hostname"]
    assert gateway["is_authorized"] is False
    assert deduped["ip_address"] == "192.168.50.41"
    assert deduped["hostname"] == "Operator workstation"
    assert deduped["is_authorized"] is True
    assert deduped["status"] == "offline"
    assert "192.168.60.9" not in {item["ip_address"] for item in items}
    assert listing.json()["agent_self_registered"] == 1
    assert listing.json()["host_neighbor_observations"] == 2
    assert listing.json()["needs_review"] == 1
    assert listing.json()["server_host_agent_connected"] is True
    assert listing.json()["last_host_neighbor_sample"] is not None
    assert posture.status_code == 200
    assert posture.json()["assessed_assets"] >= 3
    assert posture.json()["open_recommendations"] >= 1
    assert "token" not in json.dumps(result).lower()
    assert await db.get(LanAsset, result["lan_asset_id"]) is not None


async def test_server_host_rejects_public_neighbor_payload(
    client: AsyncClient,
    admin_headers: dict[str, str],
) -> None:
    payload = {
        "agent_id": "public-neighbor-test",
        "platform": "windows",
        "agent_role": "server_host",
        "collected_at": datetime.now(UTC).isoformat(),
        "cpu_percent": 10,
        "neighbor_observations": [
            {
                "ip_address": "8.8.8.8",
                "state": "reachable",
                "observed_at": datetime.now(UTC).isoformat(),
            }
        ],
    }
    response = await client.post(
        "/api/v1/monitoring/agent/ingest", headers=admin_headers, json=payload
    )
    assert response.status_code == 422


async def test_asset_watch_counts_repeated_local_failures(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    analyst_user: User,
    test_investigation: Investigation,
    db: AsyncSession,
) -> None:
    reports = [
        Report(
            investigation_id=test_investigation.id,
            generated_by=analyst_user.id,
            title=f"Failed synthetic report {index}",
            report_type="technical",
            report_format="html",
            status="failed",
            failure_reason="Synthetic local export failure.",
        )
        for index in range(2)
    ]
    audits = [
        AuditLog(
            user_id=analyst_user.id,
            actor_id=analyst_user.id,
            action="ai_analysis.executed",
            resource_type="ai_analysis",
            investigation_id=test_investigation.id,
            details={"status": "provider_unavailable"},
            event_metadata={"status": "provider_unavailable"},
        )
        for _ in range(2)
    ]
    db.add_all([*reports, *audits])
    await db.commit()

    response = await client.get("/api/v1/monitoring/assets", headers=analyst_headers)

    assert response.status_code == 200
    assert response.json()["repeated_report_failures"] == 2
    assert response.json()["repeated_ai_degraded"] == 2
