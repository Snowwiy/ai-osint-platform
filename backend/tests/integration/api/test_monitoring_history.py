from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.lan_monitoring import LanAsset, LanAssetTelemetry
from app.models.monitoring_history import MonitoringChangeEvent
from app.models.monitoring_policy import MaintenanceWindow
from app.models.user import User
from app.schemas.lan_monitoring import LanServiceInput
from app.schemas.monitoring import (
    MonitoringAssetsResponse,
    MonitoringServicesResponse,
    MonitoringSystemResponse,
)
from app.services.local_monitoring import get_monitoring_alerts
from app.services.monitoring_history import (
    record_agent_telemetry_changes,
    record_asset_observation_changes,
    record_change,
    record_service_observation,
    reconcile_asset_state_changes,
)


async def test_new_asset_change_event_and_history_rbac(
    client: AsyncClient,
    admin_headers: dict[str, str],
    analyst_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_lan(monkeypatch)
    response = await client.post(
        "/api/v1/monitoring/lan/discover",
        headers=admin_headers,
        json={"observations": [{"ip_address": "192.168.0.160", "source": "static"}]},
    )
    assert response.status_code == 200

    changes = await client.get(
        "/api/v1/monitoring/changes?event_type=asset_discovered",
        headers=analyst_headers,
    )
    item = changes.json()["items"][0]
    forbidden = await client.get(
        f"/api/v1/monitoring/lan/assets/{item['asset_id']}/history",
        headers=analyst_headers,
    )
    allowed = await client.get(
        f"/api/v1/monitoring/lan/assets/{item['asset_id']}/history",
        headers=admin_headers,
    )

    assert changes.status_code == 200
    assert item["event_type"] == "asset_discovered"
    assert forbidden.status_code == 403
    assert allowed.status_code == 200
    assert (await client.get("/api/v1/monitoring/changes")).status_code in {401, 403}


async def test_open_closed_and_nonstandard_ssh_history(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
) -> None:
    asset = await _asset(db, "192.168.0.161")
    first_at = datetime.now(UTC) - timedelta(seconds=2)
    await record_service_observation(
        db,
        asset=asset,
        observation=LanServiceInput(
            port=2222,
            status="open",
            service_name="ssh",
            service_label="possible SSH service",
            confidence=95,
            banner_hint="SSH protocol banner detected",
            non_standard_ssh=True,
        ),
        source="test_fake",
        observed_at=first_at,
    )
    await record_service_observation(
        db,
        asset=asset,
        observation=LanServiceInput(
            port=2222, status="closed", service_name="ssh", confidence=80
        ),
        source="test_fake",
        observed_at=datetime.now(UTC),
    )
    await db.commit()

    changes = await client.get(
        f"/api/v1/monitoring/changes?asset_id={asset.id}", headers=admin_headers
    )
    history = await client.get(
        f"/api/v1/monitoring/lan/assets/{asset.id}/service-history",
        headers=admin_headers,
    )
    event_types = {item["event_type"] for item in changes.json()["items"]}

    assert changes.status_code == 200
    assert {"port_opened", "port_closed", "ssh_nonstandard_detected"} <= event_types
    assert history.status_code == 200
    assert history.json()["total"] == 2
    assert history.json()["items"][0]["previous_status"] == "open"
    assert "banner" not in json.dumps(history.json()).lower()


async def test_agent_stale_and_resumed_changes(db: AsyncSession) -> None:
    asset = await _asset(db, "192.168.0.162", source="agent")
    stale = LanAssetTelemetry(
        lan_asset_id=asset.id,
        cpu_percent=20,
        collected_at=datetime.now(UTC)
        - timedelta(minutes=settings.LAN_AGENT_MAX_STALE_MINUTES + 2),
    )
    db.add(stale)
    await db.flush()

    await reconcile_asset_state_changes(db)
    current = LanAssetTelemetry(
        lan_asset_id=asset.id, cpu_percent=95, collected_at=datetime.now(UTC)
    )
    db.add(current)
    await record_agent_telemetry_changes(db, asset, stale, current)
    await db.flush()

    event_types = set(
        (
            await db.execute(
                select(MonitoringChangeEvent.event_type).where(
                    MonitoringChangeEvent.asset_id == asset.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert {"agent_stale", "agent_resumed", "cpu_percent_threshold_crossed"} <= event_types


async def test_asset_offline_and_online_transitions(db: AsyncSession) -> None:
    asset = await _asset(db, "192.168.0.164")
    asset.last_seen = datetime.now(UTC) - timedelta(hours=1)
    await reconcile_asset_state_changes(db)
    assert asset.status == "offline"

    observed_at = datetime.now(UTC)
    asset.status = "online"
    asset.last_seen = observed_at
    await record_asset_observation_changes(
        db,
        asset=asset,
        created=False,
        old_status="offline",
        old_hostname=asset.hostname,
        old_mac=asset.mac_address,
        source="test_fake",
        detected_at=observed_at,
    )
    event_types = set(
        (
            await db.execute(
                select(MonitoringChangeEvent.event_type).where(
                    MonitoringChangeEvent.asset_id == asset.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert {"asset_offline", "asset_online"} <= event_types


async def test_acknowledge_filters_and_secret_redaction(
    client: AsyncClient,
    analyst_headers: dict[str, str],
    db: AsyncSession,
) -> None:
    item = await record_change(
        db,
        asset_id=None,
        event_type="synthetic_change",
        severity="low",
        title="Safe synthetic monitoring change",
        description="No credential material is retained.",
        source="test",
        metadata={"port": 443, "access_token": "must-not-leak"},
    )
    await db.commit()
    acknowledged = await client.patch(
        f"/api/v1/monitoring/changes/{item.id}/acknowledge",
        headers=analyst_headers,
    )
    listing = await client.get(
        "/api/v1/monitoring/changes?acknowledgement=acknowledged",
        headers=analyst_headers,
    )
    duplicate = await client.patch(
        f"/api/v1/monitoring/changes/{item.id}/acknowledge",
        headers=analyst_headers,
    )

    assert acknowledged.status_code == 200
    assert acknowledged.json()["acknowledged_at"]
    assert duplicate.status_code == 409
    assert item.id.hex in {
        entry["id"].replace("-", "") for entry in listing.json()["items"]
    }
    assert "must-not-leak" not in json.dumps(listing.json())


async def test_change_alert_respects_maintenance_suppression(
    db: AsyncSession,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_lan(monkeypatch)
    asset = await _asset(db, "192.168.0.163")
    now = datetime.now(UTC)
    await record_change(
        db,
        asset_id=asset.id,
        event_type="service_changed",
        severity="medium",
        title="Service guess changed",
        description="The safe service classification changed.",
        source="test_fake",
        old_value="http",
        new_value="ssh",
        detected_at=now,
    )
    db.add(
        MaintenanceWindow(
            title="Approved LAN maintenance",
            start_time=now - timedelta(minutes=1),
            end_time=now + timedelta(hours=1),
            affected_assets=[str(asset.id)],
            affected_services=["lan_change"],
            suppress_alerts=True,
            reason="Approved service maintenance.",
            created_by=admin_user.id,
        )
    )
    response = await get_monitoring_alerts(
        db,
        admin_user,
        services=MonitoringServicesResponse(
            generated_at=now, status="healthy", items=[]
        ),
        system=MonitoringSystemResponse(
            generated_at=now,
            source="container",
            metric_scope="test",
            available=True,
            stale=False,
            platform="test",
            detail="test",
        ),
        assets=MonitoringAssetsResponse(
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
        ),
    )
    alert = next(item for item in response.items if item.category == "lan_change")
    assert alert.suppressed is True
    assert alert.suppressed_due_to_maintenance is True


async def _asset(
    db: AsyncSession, ip_address: str, *, source: str = "static"
) -> LanAsset:
    item = LanAsset(
        ip_address=ip_address,
        status="online",
        source=source,
        is_authorized=True,
        monitoring_enabled=True,
        last_seen=datetime.now(UTC),
    )
    db.add(item)
    await db.flush()
    return item


def _enable_lan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LAN_MONITORING_ENABLED", True)
    monkeypatch.setattr(settings, "LAN_ALLOWED_CIDRS", "192.168.0.0/24")
