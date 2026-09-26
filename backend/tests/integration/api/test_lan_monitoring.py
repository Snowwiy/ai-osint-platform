from __future__ import annotations

import ipaddress
import json
import uuid
from datetime import UTC, datetime

import pytest
from app.core.config import settings
from app.models.agent_management import ExpectedServiceBaseline
from app.models.background_job import BackgroundJob
from app.models.lan_monitoring import LanAsset, LanServiceObservation
from app.models.monitoring_history import MonitoringChangeEvent
from app.models.notification import Notification
from app.models.user import User
from app.schemas.lan_monitoring import LanDiscoveryObservation, LanServiceInput
from app.schemas.monitoring import (
    MonitoringAssetsResponse,
    MonitoringServicesResponse,
    MonitoringSystemResponse,
)
from app.services import lan_monitoring
from app.services.lan_monitoring import (
    LanAssetIdentityConflictError,
    LanConfigurationError,
    _classify_service,
    _upsert_observation,
    list_lan_assets,
    normalize_private_cidr,
    run_native_lan_discovery,
    validate_allowed_cidr,
    validate_allowed_ip,
)
from app.services.local_monitoring import get_monitoring_alerts
from app.services.monitoring_history import record_service_observation
from app.services.native_lan_provider import (
    NativeInterface,
    NativeLanSnapshot,
    NativeNeighbor,
    NativeRoute,
)
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def test_lan_monitoring_is_disabled_by_default(
    client: AsyncClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LAN_MONITORING_ENABLED", False)

    listing = await client.get("/api/v1/monitoring/lan/assets", headers=admin_headers)
    discovery = await client.post(
        "/api/v1/monitoring/lan/discover", headers=admin_headers, json={}
    )
    agent = await client.post(
        "/api/v1/monitoring/agent/register",
        headers={"X-LAN-Agent-Token": "not-configured"},
        json=_registration_payload(),
    )

    assert listing.status_code == 200
    assert listing.json()["enabled"] is False
    assert listing.json()["docker_limited"] is True
    assert "agent_token" not in json.dumps(listing.json()).lower()
    assert discovery.status_code == 403
    assert discovery.json()["detail"]["code"] == "human_approval_gateway_required"
    assert agent.status_code == 503


def test_lan_cidr_validation_rejects_public_ranges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LAN_ALLOWED_CIDRS", "192.168.0.0/24")

    assert str(validate_allowed_cidr("192.168.0.0/25")) == "192.168.0.0/25"
    with pytest.raises(LanConfigurationError):
        validate_allowed_cidr("8.8.8.0/24")
    with pytest.raises(LanConfigurationError):
        validate_allowed_cidr("192.168.1.0/24")


def test_lan_cidr_normalizes_host_bits_and_preserves_gateway_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_MAX_HOSTS", 256)
    network, gateway = normalize_private_cidr("192.168.50.1/24")

    assert str(network) == "192.168.50.0/24"
    assert str(gateway) == "192.168.50.1"
    with pytest.raises(LanConfigurationError, match="private RFC1918"):
        normalize_private_cidr("8.8.8.8/24")
    with pytest.raises(LanConfigurationError, match="invalid"):
        normalize_private_cidr("not-a-cidr")
    with pytest.raises(LanConfigurationError, match="MAX_HOSTS"):
        normalize_private_cidr("192.168.0.1/16")


def test_network_broadcast_and_out_of_cidr_assets_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LAN_ALLOWED_CIDRS", "192.168.50.0/24")

    assert str(validate_allowed_ip("192.168.50.1")) == "192.168.50.1"
    with pytest.raises(LanConfigurationError, match="network and broadcast"):
        validate_allowed_ip("192.168.50.0")
    with pytest.raises(LanConfigurationError, match="network and broadcast"):
        validate_allowed_ip("192.168.50.255")
    with pytest.raises(LanConfigurationError, match="outside"):
        validate_allowed_ip("192.168.51.10")


async def test_manual_router_observation_fields_are_validated_and_persisted(
    client: AsyncClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LAN_MONITORING_ENABLED", True)
    monkeypatch.setattr(settings, "LAN_ALLOWED_CIDRS", "192.168.50.0/24")
    response = await client.post(
        "/api/v1/monitoring/lan/discover",
        headers=admin_headers,
        json={
            "cidr": "192.168.50.1/24",
            "observations": [{
                "ip_address": "192.168.50.22",
                "hostname": "approved-phone",
                "mac_address": "00:11:22:33:44:66",
                "source": "router",
                "interface_name": "wifi",
                "connection_type": "wireless",
                "is_authorized": True,
                "notes": "Observed manually in the approved router UI.",
            }],
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "human_approval_gateway_required"
    listing = await client.get(
        "/api/v1/monitoring/lan/assets", headers=admin_headers
    )
    assert "192.168.50.22" not in {
        value["ip_address"] for value in listing.json()["items"]
    }


async def test_native_observation_preserves_manual_asset_fields_and_ip_conflicts(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "LAN_ALLOWED_CIDRS", "192.168.50.0/24")
    manual = LanAsset(
        ip_address="192.168.50.61",
        mac_address="02:11:22:33:44:61",
        hostname="operator-name",
        source="static",
        is_authorized=True,
        criticality="high",
        notes="keep operator notes",
    )
    db.add(manual)
    await db.flush()

    observed, created = await _upsert_observation(
        db,
        None,
        LanDiscoveryObservation(
            ip_address="192.168.50.61",
            mac_address="02:11:22:33:44:61",
            hostname="discovered-name",
            source="host_neighbor_table",
        ),
        datetime.now(UTC),
    )
    assert not created
    assert observed.id == manual.id
    assert observed.hostname == "operator-name"
    assert observed.source == "static"
    assert observed.is_authorized is True
    assert observed.criticality == "high"
    assert observed.notes == "keep operator notes"

    with pytest.raises(LanAssetIdentityConflictError):
        await _upsert_observation(
            db,
            None,
            LanDiscoveryObservation(
                ip_address="192.168.50.61",
                mac_address="02:11:22:33:44:62",
                source="host_neighbor_table",
            ),
            datetime.now(UTC),
        )


async def test_native_discovery_registers_host_and_agentless_neighbor(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "RUNTIME_PROFILE", "desktop")
    monkeypatch.setattr(settings, "LAN_MONITORING_ENABLED", True)
    monkeypatch.setattr(settings, "LAN_ALLOWED_CIDRS", "192.168.50.0/24")
    monkeypatch.setattr(settings, "LAN_DISCOVERY_PING_ENABLED", False)
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_ENABLED", False)
    network = ipaddress.IPv4Network("192.168.50.0/24")
    sampled = datetime.now(UTC)
    snapshot = NativeLanSnapshot(
        available=True,
        hostname="raventech-host",
        os_name="Windows",
        os_version="11",
        architecture="AMD64",
        sampled_at=sampled,
        interfaces=(
            NativeInterface("Ethernet", "192.168.50.37", network, "02:11:22:33:44:37"),
        ),
        reachable_networks=(NativeRoute("Ethernet", network),),
        neighbors=(
            NativeNeighbor(
                "192.168.50.61", "02:11:22:33:44:61", "Ethernet", "reachable"
            ),
        ),
        primary_address="192.168.50.37",
        primary_mac="02:11:22:33:44:37",
        limitation=None,
    )
    monkeypatch.setattr(
        lan_monitoring, "collect_native_snapshot", lambda _nets: snapshot
    )

    result = await run_native_lan_discovery(db)
    host = await lan_monitoring._asset_by_ip(db, "192.168.50.37")
    peer = await lan_monitoring._asset_by_ip(db, "192.168.50.61")
    listing = await list_lan_assets(db)

    assert "2 created" in result
    assert host is not None and host.source == "native_server_host"
    assert host.is_authorized is True
    assert host.device_type == "server"
    assert peer is not None and peer.source == "host_neighbor_table"
    assert peer.is_authorized is False
    assert peer.status == "online"
    assert listing.runtime_profile == "desktop"
    assert listing.provider_source == "native_host_provider"
    assert listing.provider_status == "available"
    assert listing.neighbor_collector_status == "available"
    assert listing.discovered_asset_count == 2


async def test_native_lan_scheduler_starts_once_and_deduplicates(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.background_jobs import schedule_lan_discovery_cycle

    monkeypatch.setattr(settings, "RUNTIME_PROFILE", "desktop")
    monkeypatch.setattr(settings, "BACKGROUND_JOB_BACKEND", "native")
    monkeypatch.setattr(settings, "LAN_MONITORING_ENABLED", True)
    monkeypatch.setattr(settings, "LAN_AUTO_DISCOVERY_ON_START", True)
    first = await schedule_lan_discovery_cycle(db, "phase5bq-test-worker")
    assert first is not None
    assert first.job_type == "monitoring.lan_discovery"
    assert first.dedupe_key == "scheduler:lan-discovery"
    await db.commit()

    second = await schedule_lan_discovery_cycle(db, "phase5bq-test-worker")
    assert second is None


async def test_legacy_asset_discovery_and_trust_writes_require_action_gateway(
    client: AsyncClient,
    db: AsyncSession,
    admin_headers: dict[str, str],
    analyst_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_lan(monkeypatch)
    discovery = await client.post(
        "/api/v1/monitoring/lan/discover",
        headers=admin_headers,
        json={
            "cidr": "192.168.0.0/24",
            "observations": [
                {
                    "ip_address": "192.168.0.20",
                    "mac_address": "00-11-22-33-44-55",
                    "hostname": "lab-endpoint",
                    "source": "router",
                }
            ],
        },
    )
    assert discovery.status_code == 403
    assert discovery.json()["detail"]["code"] == "human_approval_gateway_required"

    asset_record = LanAsset(
        ip_address="192.168.0.20",
        mac_address="00:11:22:33:44:55",
        hostname="lab-endpoint",
        source="host_neighbor_table",
        is_authorized=False,
        monitoring_enabled=False,
        status="online",
    )
    db.add(asset_record)
    await db.commit()

    listing = await client.get("/api/v1/monitoring/lan/assets", headers=admin_headers)
    analyst_listing = await client.get(
        "/api/v1/monitoring/lan/assets", headers=analyst_headers
    )
    missing = await client.get(
        f"/api/v1/monitoring/lan/assets/{uuid.uuid4()}", headers=admin_headers
    )
    asset = next(
        item for item in listing.json()["items"] if item["id"] == str(asset_record.id)
    )
    forbidden = await client.patch(
        f"/api/v1/monitoring/lan/assets/{asset['id']}",
        headers=analyst_headers,
        json={"is_authorized": True},
    )
    updated = await client.patch(
        f"/api/v1/monitoring/lan/assets/{asset['id']}",
        headers=admin_headers,
        json={"is_authorized": True, "notes": "Approved lab endpoint."},
    )
    notes_update = await client.patch(
        f"/api/v1/monitoring/lan/assets/{asset['id']}",
        headers=admin_headers,
        json={"notes": "Reviewed lab endpoint."},
    )

    assert forbidden.status_code == 403
    assert analyst_listing.status_code == 403
    assert missing.status_code == 404
    assert updated.status_code == 403
    assert updated.json()["detail"]["code"] == "human_approval_gateway_required"
    assert notes_update.status_code == 200
    assert notes_update.json()["is_authorized"] is False
    assert notes_update.json()["notes"] == "Reviewed lab endpoint."


async def test_agent_token_registration_and_telemetry(
    client: AsyncClient,
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_lan(monkeypatch)
    monkeypatch.setattr(settings, "LAN_AGENT_TOKEN", "test-agent-token-value")
    invalid = await client.post(
        "/api/v1/monitoring/agent/register",
        headers={"X-LAN-Agent-Token": "wrong"},
        json=_registration_payload(),
    )
    registered = await client.post(
        "/api/v1/monitoring/agent/register",
        headers={"X-LAN-Agent-Token": "test-agent-token-value"},
        json=_registration_payload(),
    )
    assert invalid.status_code == 401
    assert registered.status_code == 202
    asset_id = registered.json()["asset_id"]
    assert "token" not in json.dumps(registered.json()).lower()

    rejected_metadata = await client.post(
        "/api/v1/monitoring/agent/telemetry",
        headers={"X-LAN-Agent-Token": "test-agent-token-value"},
        json={**_telemetry_payload(asset_id), "metadata": {"access_token": "unsafe"}},
    )
    accepted = await client.post(
        "/api/v1/monitoring/agent/telemetry",
        headers={"X-LAN-Agent-Token": "test-agent-token-value"},
        json=_telemetry_payload(asset_id),
    )
    telemetry = await client.get(
        f"/api/v1/monitoring/lan/assets/{asset_id}/telemetry",
        headers=admin_headers,
    )
    detail = await client.get(
        f"/api/v1/monitoring/lan/assets/{asset_id}", headers=admin_headers
    )

    assert rejected_metadata.status_code == 422
    assert accepted.status_code == 202
    assert telemetry.status_code == 200
    assert telemetry.json()["items"][0]["cpu_percent"] == 12.5
    assert telemetry.json()["items"][0]["metadata"]["firewall_status"] == "enabled"
    assert telemetry.json()["items"][0]["metadata"]["listening_tcp_ports"] == [22, 443]
    assert detail.json()["agent_connected"] is True
    assert detail.json()["source"] == "endpoint_agent"


async def test_lan_endpoint_registration_preserves_manual_authorization(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_lan(monkeypatch)
    monkeypatch.setattr(settings, "LAN_AGENT_TOKEN", "test-agent-token-value")
    manual = LanAsset(
        ip_address="192.168.0.30",
        hostname="Operator assigned name",
        status="online",
        source="router",
        is_authorized=False,
        monitoring_enabled=True,
    )
    db.add(manual)
    await db.commit()

    registered = await client.post(
        "/api/v1/monitoring/agent/register",
        headers={"X-LAN-Agent-Token": "test-agent-token-value"},
        json=_registration_payload(),
    )
    detail = await client.get(
        f"/api/v1/monitoring/lan/assets/{manual.id}", headers=admin_headers
    )
    telemetry = await client.post(
        "/api/v1/monitoring/agent/telemetry",
        headers={"X-LAN-Agent-Token": "test-agent-token-value"},
        json=_telemetry_payload(str(manual.id)),
    )

    assert registered.status_code == 202
    assert detail.status_code == 200
    assert detail.json()["hostname"] == "Operator assigned name"
    assert detail.json()["is_authorized"] is False
    assert detail.json()["source"] == "endpoint_agent"
    assert telemetry.status_code == 202


async def test_current_service_summary_reports_first_last_and_state_change(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_lan(monkeypatch)
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_ENABLED", True)
    asset = LanAsset(
        ip_address="192.168.0.81",
        status="online",
        source="static",
        is_authorized=True,
        monitoring_enabled=True,
    )
    db.add(asset)
    await db.flush()
    first = datetime(2026, 1, 1, tzinfo=UTC)
    second = datetime(2026, 1, 2, tzinfo=UTC)
    await record_service_observation(
        db,
        asset=asset,
        observation=LanServiceInput(
            port=2222,
            status="open",
            service_name="ssh",
            banner_hint="SSH protocol banner detected",
            non_standard_ssh=True,
            confidence=95,
        ),
        source="test_safe_tcp",
        observed_at=first,
    )
    await record_service_observation(
        db,
        asset=asset,
        observation=LanServiceInput(
            port=2222,
            status="closed",
            service_name="ssh",
            confidence=80,
        ),
        source="test_safe_tcp",
        observed_at=second,
    )
    await db.commit()

    response = await client.get(
        f"/api/v1/monitoring/lan/assets/{asset.id}/services",
        headers=admin_headers,
    )
    changes = set(
        (
            await db.execute(
                select(MonitoringChangeEvent.event_type).where(
                    MonitoringChangeEvent.asset_id == asset.id
                )
            )
        ).scalars()
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    item = response.json()["items"][0]
    assert item["first_observed_at"].startswith("2026-01-01")
    assert item["observed_at"].startswith("2026-01-02")
    assert item["previous_status"] == "open"
    assert item["changed_from_previous"] is True
    assert item["banner_hint"] is None
    assert {"port_opened", "port_closed", "ssh_nonstandard_detected"} <= changes
    assert {"service_opened", "service_closed", "service_recovered"} <= changes


async def test_service_baseline_classification_and_event_dedupe(
    client: AsyncClient, admin_headers: dict[str, str], db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_lan(monkeypatch)
    asset = LanAsset(
        ip_address="192.168.0.82", status="online", source="static",
        device_type="server", os_family="linux", is_authorized=True,
        monitoring_enabled=True,
    )
    db.add(asset)
    await db.flush()
    db.add(ExpectedServiceBaseline(
        name="Test server baseline", asset_id=asset.id,
        expected_ports=[443], allowed_ports=[22], critical_ports=[6379],
    ))
    await db.flush()
    for port in (443, 6379):
        for sample in (1, 2):
            await record_service_observation(
                db,
                asset=asset,
                observation=LanServiceInput(
                    port=port, status="open", confidence=75
                ),
                source="test_safe_tcp",
                observed_at=datetime(2026, 1, sample, tzinfo=UTC),
            )
    await db.commit()
    response = await client.get(
        f"/api/v1/monitoring/lan/assets/{asset.id}/services",
        headers=admin_headers,
    )
    assert response.status_code == 200
    items = {item["port"]: item for item in response.json()["items"]}
    assert (items[443]["expectation"], items[443]["advisory_severity"]) == (
        "expected",
        "healthy",
    )
    assert (items[6379]["expectation"], items[6379]["advisory_severity"]) == (
        "unexpected",
        "critical",
    )
    assert "policy explicitly" in items[6379]["advisory_reason"]
    assert all(item["banner_hint"] is None for item in items.values())
    events = list(
        (
            await db.execute(
                select(MonitoringChangeEvent).where(
                    MonitoringChangeEvent.asset_id == asset.id,
                    MonitoringChangeEvent.event_type == "service_opened",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 2
    critical_events = list((await db.execute(select(MonitoringChangeEvent).where(
        MonitoringChangeEvent.asset_id == asset.id,
        MonitoringChangeEvent.event_type == "service_became_critical",
    ))).scalars().all())
    assert len(critical_events) == 1


async def test_lan_alerts_are_deduplicated(
    db: AsyncSession,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_lan(monkeypatch)
    asset = LanAsset(
        ip_address="192.168.0.44",
        status="unknown",
        source="static",
        is_authorized=False,
        monitoring_enabled=True,
    )
    db.add(asset)
    await db.commit()
    services = MonitoringServicesResponse(
        generated_at=datetime.now(UTC), status="healthy", items=[]
    )
    system = MonitoringSystemResponse(
        generated_at=datetime.now(UTC),
        source="container",
        metric_scope="test",
        available=True,
        stale=False,
        platform="test",
        cpu_percent=1,
        memory_percent=1,
        disk_percent=1,
        detail="test",
    )
    investigation_assets = MonitoringAssetsResponse(
        generated_at=datetime.now(UTC),
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
        db, admin_user, services=services, system=system, assets=investigation_assets
    )
    second = await get_monitoring_alerts(
        db, admin_user, services=services, system=system, assets=investigation_assets
    )
    count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Notification)
                .where(Notification.notification_type == "monitoring_alert")
            )
        ).scalar_one()
    )
    assert first.notifications_created == 2
    assert second.notifications_created == 0
    assert count == 2


async def test_legacy_discovery_is_gated_and_risky_service_indicator_remains_visible(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_lan(monkeypatch)
    gated = await client.post(
        "/api/v1/monitoring/lan/discover", headers=admin_headers, json={}
    )
    assert gated.status_code == 403
    assert gated.json()["detail"]["code"] == "human_approval_gateway_required"
    asset = LanAsset(
        ip_address="192.168.0.88",
        status="online",
        source="router",
        is_authorized=True,
        monitoring_enabled=True,
    )
    db.add(asset)
    await db.flush()
    await record_service_observation(
        db,
        asset=asset,
        observation=LanServiceInput(
            port=3389,
            protocol="tcp",
            status="open",
            service_name="rdp",
            confidence=95,
        ),
        source="test_safe_tcp",
        observed_at=datetime.now(UTC),
    )
    await db.commit()
    listing = await client.get("/api/v1/monitoring/lan/assets", headers=admin_headers)
    item = next(
        value
        for value in listing.json()["items"]
        if value["id"] == str(asset.id)
    )
    indicators = item["risk_indicators"]
    assert any(item["key"] == "risky_service_3389" for item in indicators)


async def test_manual_discovery_endpoint_requires_approved_action_gateway(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_lan(monkeypatch)
    monkeypatch.setattr(settings, "LAN_DISCOVERY_PING_ENABLED", True)
    observed = LanAsset(
        ip_address="192.168.0.91",
        mac_address="AA:BB:CC:DD:EE:91",
        status="online",
        source="host_neighbor_table",
        is_authorized=False,
        monitoring_enabled=True,
        last_seen=datetime.now(UTC),
    )
    db.add(observed)
    await db.commit()
    response = await client.post(
        "/api/v1/monitoring/lan/discover", headers=admin_headers, json={}
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "human_approval_gateway_required"
    await db.refresh(observed)
    assert observed.last_seen is not None


async def test_manual_service_check_is_disabled_by_default_and_admin_only(
    client: AsyncClient,
    admin_headers: dict[str, str],
    analyst_headers: dict[str, str],
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_lan(monkeypatch)
    asset = LanAsset(
        ip_address="192.168.0.71",
        status="online",
        source="static",
        is_authorized=True,
        monitoring_enabled=True,
    )
    db.add(asset)
    await db.commit()

    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_ENABLED", False)
    disabled = await client.post(
        f"/api/v1/monitoring/lan/assets/{asset.id}/service-check",
        headers=admin_headers,
    )
    forbidden = await client.post(
        f"/api/v1/monitoring/lan/assets/{asset.id}/service-check",
        headers=analyst_headers,
    )

    assert disabled.status_code == 403
    assert disabled.json()["detail"]["code"] == "human_approval_gateway_required"
    assert forbidden.status_code == 403
    assert "secret" not in json.dumps(disabled.json()).lower()


async def test_service_observation_refresh_requires_approved_action_gateway(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_lan(monkeypatch)
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_ENABLED", True)
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_PORTS", "22,2222")
    asset = LanAsset(
        ip_address="192.168.0.72",
        status="online",
        source="static",
        is_authorized=True,
        monitoring_enabled=True,
    )
    db.add(asset)
    await db.commit()

    checked = await client.post(
        f"/api/v1/monitoring/lan/assets/{asset.id}/service-check",
        headers=admin_headers,
    )
    assert checked.status_code == 403
    assert checked.json()["detail"]["code"] == "human_approval_gateway_required"

    proposal = await client.post(
        "/api/v1/actions/proposals",
        headers=admin_headers,
        json={
            "action_id": "raventech.lan.services.refresh",
            "target_id": str(asset.id),
            "parameters": {"asset_id": str(asset.id)},
            "reason": "Operator requested a bounded service observation proposal.",
        },
    )
    assert proposal.status_code == 201
    proposal_id = proposal.json()["id"]
    approved = await client.post(
        f"/api/v1/actions/proposals/{proposal_id}/approve",
        headers=admin_headers,
        json={},
    )
    assert approved.status_code == 200
    dispatched = await client.post(
        f"/api/v1/actions/proposals/{proposal_id}/execute",
        headers=admin_headers,
    )
    assert dispatched.status_code == 200
    job = (
        await db.execute(
            select(BackgroundJob).where(
                BackgroundJob.job_type == "monitoring.service_observation.asset",
                BackgroundJob.asset_id == asset.id,
            )
        )
    ).scalar_one()
    assert job.status in {"queued", "scheduled", "running", "completed"}
    services = await client.get(
        f"/api/v1/monitoring/lan/assets/{asset.id}/services",
        headers=admin_headers,
    )
    observations = list(
        (
            await db.execute(
                select(LanServiceObservation).where(
                    LanServiceObservation.lan_asset_id == asset.id
                )
            )
        )
        .scalars()
        .all()
    )

    assert services.status_code == 200
    assert services.json()["total"] == 0
    assert observations == []


async def test_approved_service_observation_is_limited_to_target_asset(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_lan(monkeypatch)
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_ENABLED", True)
    monkeypatch.setattr(settings, "RUNTIME_PROFILE", "docker")
    target = LanAsset(
        ip_address="192.168.0.74",
        status="online",
        source="static",
        is_authorized=True,
        monitoring_enabled=True,
    )
    other = LanAsset(
        ip_address="192.168.0.75",
        status="online",
        source="static",
        is_authorized=True,
        monitoring_enabled=True,
    )
    db.add_all([target, other])
    await db.flush()
    observed_asset_ids: list[uuid.UUID] = []

    async def allow_cycle(_db: AsyncSession, _lock_id: int) -> bool:
        return True

    async def observe_configured_ports(
        observations: list[LanDiscoveryObservation],
    ) -> None:
        for observation in observations:
            observation.services.append(
                LanServiceInput(port=22, service_name="ssh", status="open")
            )

    async def record_for_asset(
        _db: AsyncSession,
        *,
        asset: LanAsset,
        observation: LanServiceInput,
        source: str,
        observed_at: datetime,
    ) -> None:
        observed_asset_ids.append(asset.id)

    monkeypatch.setattr(lan_monitoring, "_try_advisory_lock", allow_cycle)
    monkeypatch.setattr(
        lan_monitoring, "_observe_configured_services", observe_configured_ports
    )
    monkeypatch.setattr(
        lan_monitoring, "record_service_observation", record_for_asset
    )

    await lan_monitoring.run_native_service_observation(db, asset_id=target.id)

    assert observed_asset_ids == [target.id]


def test_ssh_classification_standard_and_nonstandard_ports() -> None:
    standard = _classify_service(22, b"")
    nonstandard = _classify_service(2022, b"SSH-2.0-OpenSSH_9.0 token=unsafe")

    assert standard.service_name == "ssh"
    assert standard.non_standard_ssh is False
    assert nonstandard.service_name == "ssh"
    assert nonstandard.non_standard_ssh is True
    assert nonstandard.confidence >= 90
    assert nonstandard.banner_hint == "SSH protocol banner detected"
    assert "token" not in nonstandard.banner_hint


def _enable_lan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LAN_MONITORING_ENABLED", True)
    monkeypatch.setattr(settings, "LAN_ALLOWED_CIDRS", "192.168.0.0/24")


def _registration_payload() -> dict[str, object]:
    return {
        "ip_address": "192.168.0.30",
        "mac_address": "00:11:22:33:44:66",
        "hostname": "agent-endpoint",
        "os_name": "Windows",
        "os_version": "11",
        "agent_version": "1.1.0",
        "capabilities": [
            "basic_telemetry",
            "os_basics",
            "security_posture",
            "patch_awareness",
            "listening_ports",
        ],
    }


def _telemetry_payload(asset_id: str) -> dict[str, object]:
    return {
        "asset_id": asset_id,
        "collected_at": datetime.now(UTC).isoformat(),
        "cpu_percent": 12.5,
        "memory_percent": 40,
        "disk_percent": 55,
        "uptime_seconds": 3600,
        "os_name": "Windows",
        "os_version": "11",
        "agent_version": "1.1.0",
        "os_build": "26100",
        "disk_free_gb": 120.5,
        "firewall_status": "enabled",
        "antivirus_status": "enabled",
        "patch_status": "current",
        "latest_patch_date": "2026-09-01",
        "recent_hotfix_count": 4,
        "pending_reboot": False,
        "listening_tcp_ports": [443, 22, 443],
        "metadata": {"collection_mode": "local"},
    }
