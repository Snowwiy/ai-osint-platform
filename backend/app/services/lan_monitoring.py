from __future__ import annotations

import asyncio
import ipaddress
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Literal, cast
from urllib.parse import urlparse

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.agent_management import AgentEnrollmentToken
from app.models.endpoint_posture import EndpointSecurityPosture
from app.models.lan_monitoring import LanAsset, LanAssetTelemetry, LanServiceObservation
from app.models.monitoring_history import MonitoringChangeEvent
from app.models.target import Target
from app.models.user import User
from app.schemas.lan_monitoring import (
    LanAgentRegistration,
    LanAgentRegistrationResponse,
    LanAgentTelemetryIngest,
    LanAgentTelemetryResponse,
    LanAssetListResponse,
    AssetCriticality,
    LanAssetResponse,
    LanAssetStatus,
    LanAssetUpdate,
    LanDiscoveryObservation,
    LanDiscoveryRequest,
    LanDiscoveryResponse,
    LanRiskIndicator,
    LanRiskSeverity,
    LanServiceInput,
    LanServiceCheckResponse,
    LanServiceListResponse,
    LanOpenPortsResponse,
    MonitoringActivationStatus,
    TargetServiceCheckStatus,
    LanServiceResponse,
    LanTelemetryListResponse,
    LanTelemetryResponse,
)
from app.schemas.monitoring import AgentTelemetryIngest, HostNeighborObservation, MonitoringAlert
from app.services.audit import record_event
from app.services.device_classification import classify
from app.services.service_health import LanServiceBaseline, assess_lan_service, lan_baseline
from app.services.notification import create_admin_notification
from app.services.monitoring_history import (
    record_agent_telemetry_changes,
    record_asset_observation_changes,
    record_service_observation,
    reconcile_asset_state_changes,
)
from app.services.native_lan_provider import (
    NativeLanSnapshot,
    collect_native_snapshot,
)

RFC1918_NETWORKS: tuple[ipaddress.IPv4Network, ...] = tuple(
    ipaddress.IPv4Network(value)
    for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)
RISKY_PORTS = {
    23: "Telnet",
    445: "SMB",
    3389: "Remote Desktop",
    5900: "VNC",
    5432: "PostgreSQL",
    6379: "Redis",
}
SERVICE_GUESSES = {
    22: "ssh",
    80: "http",
    443: "https",
    445: "smb",
    3389: "rdp",
    5432: "postgresql",
    6379: "redis",
    8080: "http",
    8443: "https",
    3000: "http",
    8000: "http",
}
CURRENT_AGENT_VERSION = "1.1.0"
AGENT_ASSET_SOURCES = {"agent", "endpoint_agent"}


class LanMonitoringDisabledError(Exception):
    pass


class LanConfigurationError(Exception):
    pass


class LanAssetNotFoundError(Exception):
    pass


class LanDiscoveryRateLimitedError(Exception):
    pass


def get_monitoring_activation() -> MonitoringActivationStatus:
    allowed_cidrs = [str(item) for item in configured_networks()]
    ports = configured_service_ports()
    native_profile = settings.RUNTIME_PROFILE == "desktop"
    if native_profile:
        provider_source: Literal[
            "native_host_provider",
            "container_neighbor_table",
            "server_host_agent",
        ] = "native_host_provider"
    elif settings.RUNTIME_PROFILE == "docker":
        provider_source = "container_neighbor_table"
    else:
        provider_source = "server_host_agent"
    limited_message = (
        "Limited LAN visibility. RavenTech uses the native host provider; network "
        "segmentation, client isolation, firewall policy, or inactive devices may "
        "limit observations."
        if native_profile
        else "Docker could not read host LAN neighbors. Use the ServerHost agent or "
        "imported router observations."
    )
    return MonitoringActivationStatus(
        desktop_auto_monitoring_enabled=settings.DESKTOP_AUTO_MONITORING_ENABLED,
        auto_refresh_enabled=settings.MONITORING_AUTO_REFRESH_ENABLED,
        auto_refresh_seconds=settings.MONITORING_AUTO_REFRESH_SECONDS,
        server_host_metrics_enabled=settings.SERVER_HOST_METRICS_ENABLED,
        server_host_metrics_interval_seconds=settings.SERVER_HOST_METRICS_INTERVAL_SECONDS,
        lan_endpoint_agent_interval_seconds=settings.LAN_ENDPOINT_AGENT_INTERVAL_SECONDS,
        posture_recompute_interval_seconds=settings.POSTURE_RECOMPUTE_INTERVAL_SECONDS,
        lan_monitoring_enabled=settings.LAN_MONITORING_ENABLED,
        service_check_enabled=settings.LAN_SERVICE_CHECK_ENABLED,
        lan_auto_discovery_on_start=(
            settings.LAN_MONITORING_ENABLED and settings.LAN_AUTO_DISCOVERY_ON_START
        ),
        lan_auto_service_check_on_start=(
            settings.LAN_MONITORING_ENABLED
            and settings.LAN_SERVICE_CHECK_ENABLED
            and settings.LAN_AUTO_SERVICE_CHECK_ON_START
        ),
        lan_auto_discovery_interval_seconds=settings.LAN_AUTO_DISCOVERY_INTERVAL_SECONDS,
        lan_auto_service_check_interval_seconds=settings.LAN_AUTO_SERVICE_CHECK_INTERVAL_SECONDS,
        allowed_cidrs=allowed_cidrs,
        gateway_hint=settings.LAN_GATEWAY_HINT,
        service_ports=ports,
        discovery_disabled_reason=(
            None
            if settings.LAN_MONITORING_ENABLED
            else "LAN discovery is disabled because LAN_MONITORING_ENABLED is false."
        ),
        service_check_disabled_reason=(
            None
            if settings.LAN_SERVICE_CHECK_ENABLED
            else "TCP service checks are disabled because LAN_SERVICE_CHECK_ENABLED is false."
        ),
        env_lines=[
            "DESKTOP_AUTO_MONITORING_ENABLED=true",
            "MONITORING_AUTO_REFRESH_ENABLED=true",
            "MONITORING_AUTO_REFRESH_SECONDS=30",
            "SERVER_HOST_METRICS_ENABLED=true",
            "SERVER_HOST_METRICS_INTERVAL_SECONDS=30",
            "LAN_ENDPOINT_AGENT_INTERVAL_SECONDS=30",
            "POSTURE_RECOMPUTE_INTERVAL_SECONDS=300",
            "LAN_MONITORING_ENABLED=true",
            f"LAN_ALLOWED_CIDRS={','.join(allowed_cidrs)}",
            f"LAN_GATEWAY_HINT={settings.LAN_GATEWAY_HINT}",
            "LAN_DISCOVERY_PING_ENABLED=true",
            "LAN_SERVICE_CHECK_ENABLED=true",
            f"LAN_AUTO_DISCOVERY_ON_START={str(settings.LAN_AUTO_DISCOVERY_ON_START).lower()}",
            f"LAN_AUTO_SERVICE_CHECK_ON_START={str(settings.LAN_AUTO_SERVICE_CHECK_ON_START).lower()}",
            f"LAN_AUTO_DISCOVERY_INTERVAL_SECONDS={settings.LAN_AUTO_DISCOVERY_INTERVAL_SECONDS}",
            f"LAN_AUTO_SERVICE_CHECK_INTERVAL_SECONDS={settings.LAN_AUTO_SERVICE_CHECK_INTERVAL_SECONDS}",
            f"LAN_DISCOVERY_CONCURRENCY={settings.LAN_DISCOVERY_CONCURRENCY}",
            f"LAN_SERVICE_CHECK_PORTS={','.join(str(port) for port in ports)}",
            f"LAN_SERVICE_CHECK_TIMEOUT_SECONDS={settings.LAN_SERVICE_CHECK_TIMEOUT_SECONDS:g}",
            f"LAN_SERVICE_CHECK_MAX_HOSTS={settings.LAN_SERVICE_CHECK_MAX_HOSTS}",
            f"LAN_SERVICE_CHECK_MAX_PORTS={settings.LAN_SERVICE_CHECK_MAX_PORTS}",
            "LAN_REJECT_PUBLIC_CIDRS=true",
            "LAN_SSH_BANNER_DETECTION_ENABLED=true",
        ],
        restart_commands=(
            []
            if native_profile
            else [
                "docker compose up -d --force-recreate backend celery-worker",
                "docker compose ps",
            ]
        ),
        windows_firewall_note=(
            "If another approved LAN device must reach the backend, allow inbound TCP 8000 "
            "only from the configured private CIDR in Windows Defender Firewall."
        ),
        docker_limitation=limited_message,
        optional_telemetry_note=(
            "Missing endpoint-agent telemetry is an optional coverage gap, not a platform failure."
        ),
        agent_setup_steps=[
            "Create a short-lived enrollment token as an administrator.",
            "Run the supplied Windows PowerShell or Linux Python helper manually.",
            "Use the approved private backend URL and a 10-3600 second interval.",
            "Stop the helper with Ctrl+C; no persistence or remote commands are installed.",
        ],
        token_enrollment_steps=[
            "Copy the token from its one-time creation or rotation reveal.",
            "Paste it only into the agent's secure prompt, never into a command argument.",
            "Confirm the endpoint appears in inventory, then close the reveal.",
            "Revoke or rotate the credential when enrollment is complete.",
        ],
        auto_registration_enabled=settings.LAN_MONITORING_ENABLED,
        host_neighbor_collection_enabled=(
            settings.LAN_MONITORING_ENABLED and settings.LAN_REJECT_PUBLIC_CIDRS
        ),
        host_neighbor_guidance=(
            "Native host provider reads local interfaces, routes, and the OS neighbor "
            "table. Limited visibility can result from segmentation, isolation, "
            "firewall policy, or inactive devices."
            if native_profile
            else limited_message
        ),
        runtime_profile=settings.RUNTIME_PROFILE,
        configuration_source=(
            "native_desktop"
            if native_profile
            else "docker_compose"
            if settings.RUNTIME_PROFILE == "docker"
            else "environment"
        ),
        provider_source=provider_source,
        provider_status=(
            "available"
            if native_profile and settings.LAN_MONITORING_ENABLED
            else "disabled"
            if not settings.LAN_MONITORING_ENABLED
            else "limited"
        ),
    )


class LanServiceCheckDisabledError(Exception):
    pass


def configured_networks() -> list[ipaddress.IPv4Network]:
    networks: list[ipaddress.IPv4Network] = []
    for value in settings.LAN_ALLOWED_CIDRS.split(","):
        if not value.strip():
            continue
        network = ipaddress.ip_network(value.strip(), strict=False)
        if not isinstance(network, ipaddress.IPv4Network) or not _is_rfc1918_network(
            network
        ):
            raise LanConfigurationError(
                "Only private RFC1918 IPv4 networks are allowed."
            )
        networks.append(network)
    if not networks:
        raise LanConfigurationError("No authorized LAN CIDR is configured.")
    return networks


def validate_allowed_cidr(value: str) -> ipaddress.IPv4Network:
    network, _gateway = normalize_private_cidr(value)
    if not any(network.subnet_of(allowed) for allowed in configured_networks()):
        raise LanConfigurationError("The selected CIDR is outside LAN_ALLOWED_CIDRS.")
    return network


def normalize_private_cidr(
    value: str, gateway_hint: str | None = None
) -> tuple[ipaddress.IPv4Network, ipaddress.IPv4Address]:
    try:
        interface = ipaddress.ip_interface(value)
        network = interface.network
    except ValueError as exc:
        raise LanConfigurationError("The selected LAN CIDR is invalid.") from exc
    if not isinstance(network, ipaddress.IPv4Network) or not _is_rfc1918_network(
        network
    ):
        raise LanConfigurationError(
            "The selected CIDR must be private RFC1918 IPv4 space."
        )
    if network.num_addresses > settings.LAN_SERVICE_CHECK_MAX_HOSTS:
        raise LanConfigurationError(
            "The selected discovery range exceeds LAN_SERVICE_CHECK_MAX_HOSTS."
        )
    try:
        gateway = ipaddress.ip_address(gateway_hint) if gateway_hint else interface.ip
    except ValueError as exc:
        raise LanConfigurationError("The gateway hint is not a valid IPv4 address.") from exc
    if not isinstance(gateway, ipaddress.IPv4Address) or gateway not in network:
        raise LanConfigurationError("The gateway hint must be inside the selected private CIDR.")
    return network, gateway


def validate_allowed_ip(value: str) -> ipaddress.IPv4Address:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise LanConfigurationError("The LAN asset IP address is invalid.") from exc
    if not isinstance(address, ipaddress.IPv4Address) or not any(
        address in network for network in RFC1918_NETWORKS
    ):
        raise LanConfigurationError(
            "LAN assets must use private RFC1918 IPv4 addresses."
        )
    matching_network = next(
        (network for network in configured_networks() if address in network), None
    )
    if matching_network is None:
        raise LanConfigurationError("The LAN asset IP is outside LAN_ALLOWED_CIDRS.")
    if address in {matching_network.network_address, matching_network.broadcast_address}:
        raise LanConfigurationError(
            "LAN network and broadcast addresses cannot be registered as assets."
        )
    return address


async def list_lan_assets(db: AsyncSession) -> LanAssetListResponse:
    assets = list(
        (await db.execute(select(LanAsset).order_by(LanAsset.ip_address)))
        .scalars()
        .all()
    )
    telemetry = await _latest_telemetry(db)
    services = await _latest_services(db)
    postures = {
        item.lan_asset_id: item
        for item in (
            (await db.execute(select(EndpointSecurityPosture))).scalars().all()
        )
    }
    neighbor_diagnostics = await _latest_neighbor_diagnostics(db)
    now = datetime.now(UTC)
    activation = get_monitoring_activation()
    latest_discovery = (
        await db.execute(
            select(AuditLog)
            .where(AuditLog.action == "lan.discovery.executed")
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
    ).scalars().first()
    last_discovery = latest_discovery.created_at if latest_discovery else None
    discovery_metadata = (
        latest_discovery.event_metadata
        if latest_discovery and isinstance(latest_discovery.event_metadata, dict)
        else {}
    )
    last_service_observation = (
        await db.execute(
            select(func.max(AuditLog.created_at)).where(
                AuditLog.action == "lan.service_check.executed"
            )
        )
    ).scalar_one_or_none()
    native_profile = settings.RUNTIME_PROFILE == "desktop"
    native_peer_evidence = bool(
        discovery_metadata.get("neighbors_read", 0)
        or discovery_metadata.get("tcp_hosts_responded", 0)
    )
    baselines = {item.id: await lan_baseline(db, item.id) for item in assets}
    items = [
        _asset_response(
            item,
            telemetry.get(item.id),
            services.get(item.id, []),
            now,
            postures.get(item.id),
            baselines[item.id],
        )
        for item in assets
    ]
    return LanAssetListResponse(
        generated_at=now,
        runtime_profile=settings.RUNTIME_PROFILE,
        enabled=settings.LAN_MONITORING_ENABLED,
        allowed_cidrs=[str(item) for item in configured_networks()],
        discovery_interval_seconds=settings.LAN_DISCOVERY_INTERVAL_SECONDS,
        ping_enabled=settings.LAN_DISCOVERY_PING_ENABLED,
        service_check_enabled=settings.LAN_SERVICE_CHECK_ENABLED,
        service_ports=configured_service_ports(),
        limitation=(
            "Limited LAN visibility: no peers are currently present in the native "
            "neighbor table. TCP reachability observations may still be available. "
            "Network segmentation, client isolation, firewall policy, or inactive "
            "devices may limit visibility."
            if native_profile
            and settings.LAN_MONITORING_ENABLED
            and latest_discovery is not None
            and not native_peer_evidence
            else activation.docker_limitation
            if not native_profile
            else ""
        ),
        docker_limited=not native_profile,
        provider_source=activation.provider_source,
        provider_status=(
            "disabled"
            if not settings.LAN_MONITORING_ENABLED
            else "available"
            if native_profile
            and (
                any(item.source == "native_server_host" for item in assets)
                or (
                    latest_discovery is not None
                    and discovery_metadata.get("interfaces_read", 0) > 0
                    and discovery_metadata.get("reachable_networks", 0) > 0
                )
            )
            else "limited"
            if native_profile and latest_discovery is not None
            else "unavailable"
            if native_profile
            else "limited"
        ),
        neighbor_collector_status=(
            "disabled"
            if not settings.LAN_MONITORING_ENABLED
            else "available"
            if native_profile
            and discovery_metadata.get("provider") == "native_host_provider"
            and discovery_metadata.get("neighbors_read", 0) > 0
            else "empty"
            if native_profile
            and discovery_metadata.get("provider") == "native_host_provider"
            else "unavailable"
            if native_profile
            else "available"
            if neighbor_diagnostics.get("accepted_observations", 0) > 0
            else "empty"
            if neighbor_diagnostics.get("raw_observations", 0) > 0
            else "unavailable"
        ),
        last_discovery_at=last_discovery,
        next_discovery_at=(
            last_discovery
            + timedelta(seconds=settings.LAN_AUTO_DISCOVERY_INTERVAL_SECONDS)
            if last_discovery and settings.LAN_MONITORING_ENABLED
            else now
            if (
                settings.LAN_MONITORING_ENABLED
                and settings.LAN_AUTO_DISCOVERY_ON_START
            )
            else None
        ),
        last_service_observation_at=last_service_observation,
        next_service_observation_at=(
            last_service_observation
            + timedelta(seconds=settings.LAN_AUTO_SERVICE_CHECK_INTERVAL_SECONDS)
            if last_service_observation
            and settings.LAN_MONITORING_ENABLED
            and settings.LAN_SERVICE_CHECK_ENABLED
            else now
            if (
                settings.LAN_MONITORING_ENABLED
                and settings.LAN_SERVICE_CHECK_ENABLED
                and settings.LAN_AUTO_SERVICE_CHECK_ON_START
            )
            else None
        ),
        discovered_asset_count=sum(
            item.source
            in {
                "native_server_host",
                "host_neighbor_table",
                "tcp_connect",
                "arp",
                "ping",
                "router",
                "agent",
                "endpoint_agent",
            }
            for item in assets
        ),
        total=len(items),
        online=sum(item.status == "online" for item in items),
        offline=sum(item.status == "offline" for item in items),
        authorized=sum(item.is_authorized for item in items),
        unauthorized=sum(item.trust_state == "unauthorized" for item in items),
        agent_connected=sum(item.agent_connected for item in items),
        missing_agent=sum(item.source not in AGENT_ASSET_SOURCES for item in items),
        service_observations=sum(item.observed_services for item in items),
        open_service_observations=sum(
            service.status == "open"
            for asset_services in services.values()
            for service in asset_services
        ),
        auto_registration_enabled=settings.LAN_MONITORING_ENABLED,
        agent_self_registered=sum(item.source in AGENT_ASSET_SOURCES for item in items),
        host_neighbor_observations=sum(
            item.source == "host_neighbor_table" for item in items
        ),
        manual_router_observations=sum(
            item.source in {"static", "router"} for item in items
        ),
        needs_review=sum(
            item.trust_state in {"needs_review", "gateway"} for item in items
        ),
        last_host_neighbor_sample=max(
            (
                item.last_seen
                for item in items
                if item.source == "host_neighbor_table" and item.last_seen is not None
            ),
            default=None,
        ),
        server_host_agent_connected=any(
            item.asset_type == "server_host" and item.agent_connected for item in items
        ),
        neighbor_collector_active=any(
            item.asset_type == "server_host" and item.agent_connected for item in items
        ),
        neighbor_raw_observations=neighbor_diagnostics["neighbor_raw_observations"],
        neighbor_accepted_observations=neighbor_diagnostics[
            "neighbor_accepted_observations"
        ],
        neighbor_rejected_observations=neighbor_diagnostics[
            "neighbor_rejected_observations"
        ],
        neighbor_deduplicated_observations=neighbor_diagnostics[
            "neighbor_deduplicated_observations"
        ],
        neighbor_out_of_cidr_observations=neighbor_diagnostics[
            "neighbor_out_of_cidr_observations"
        ],
        neighbor_assets_created=neighbor_diagnostics["neighbor_assets_created"],
        neighbor_assets_updated=neighbor_diagnostics["neighbor_assets_updated"],
        items=items,
    )


async def get_lan_asset(db: AsyncSession, asset_id: uuid.UUID) -> LanAssetResponse:
    asset = await db.get(LanAsset, asset_id)
    if asset is None:
        raise LanAssetNotFoundError
    telemetry = await _latest_telemetry(db, asset_id)
    services = await _latest_services(db, asset_id)
    posture = (
        await db.execute(
            select(EndpointSecurityPosture).where(
                EndpointSecurityPosture.lan_asset_id == asset_id
            )
        )
    ).scalar_one_or_none()
    return _asset_response(
        asset,
        telemetry.get(asset.id),
        services.get(asset.id, []),
        datetime.now(UTC),
        posture,
        await lan_baseline(db, asset_id),
    )


async def update_lan_asset(
    db: AsyncSession, user: User, asset_id: uuid.UUID, body: LanAssetUpdate
) -> LanAssetResponse:
    asset = await db.get(LanAsset, asset_id)
    if asset is None:
        raise LanAssetNotFoundError
    old_hostname = asset.hostname
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "device_type":
            asset.manual_device_type = value if value != "unknown" else None
            continue
        if field == "connection_medium":
            asset.connection_medium = value
            asset.connection_medium_source = "operator" if value != "unknown" else None
            asset.connection_medium_confidence = "high" if value != "unknown" else "low"
            continue
        setattr(asset, field, value.strip() if isinstance(value, str) else value)
    if "vendor" in body.model_fields_set:
        asset.vendor_source = "operator" if asset.vendor else None
        asset.vendor_confidence = "high" if asset.vendor else "low"
    _classify_asset(asset)
    if asset.is_authorized and old_hostname and asset.hostname != old_hostname:
        await record_asset_observation_changes(
            db,
            asset=asset,
            created=False,
            old_status=asset.status,
            old_hostname=old_hostname,
            old_mac=asset.mac_address,
            source="asset_update",
            detected_at=datetime.now(UTC),
        )
    await record_event(
        db,
        action="lan.asset.updated",
        actor_id=user.id,
        resource_type="lan_asset",
        resource_id=asset.id,
        metadata={"fields": sorted(body.model_fields_set)},
    )
    await db.flush()
    await db.refresh(asset)
    return await get_lan_asset(db, asset.id)


async def discover_lan(
    db: AsyncSession, user: User, body: LanDiscoveryRequest
) -> LanDiscoveryResponse:
    _ensure_enabled()
    network = validate_allowed_cidr(body.cidr or str(configured_networks()[0]))
    await _enforce_discovery_interval(db)
    observations = list(body.observations)
    native_snapshot: NativeLanSnapshot | None = None
    if not observations:
        if settings.RUNTIME_PROFILE == "desktop":
            native_snapshot = await asyncio.to_thread(
                collect_native_snapshot, tuple(configured_networks())
            )
            observations = _native_neighbor_observations(native_snapshot, network)
        else:
            observations = await _stored_host_neighbor_observations(db, network)
            observations = _merge_observations(
                observations, _read_container_arp(network)
            )
        if settings.LAN_DISCOVERY_PING_ENABLED:
            candidate_networks = (
                [
                    item.network
                    for item in native_snapshot.reachable_networks
                    if item.network.overlaps(network)
                ]
                if native_snapshot is not None
                else [network]
            )
            observations = _merge_observations(
                observations,
                await _tcp_discovery(
                    candidate_networks,
                    _snapshot_local_addresses(native_snapshot),
                ),
            )
        if settings.LAN_SERVICE_CHECK_ENABLED and observations:
            eligible: list[LanDiscoveryObservation] = []
            for observation in observations:
                existing = await _asset_by_ip_or_mac(
                    db, observation.ip_address, observation.mac_address
                )
                if existing and existing.is_authorized and existing.monitoring_enabled:
                    eligible.append(observation)
            await _observe_configured_services(eligible)
    if (
        any(item.services for item in observations)
        and not settings.LAN_SERVICE_CHECK_ENABLED
    ):
        raise LanConfigurationError(
            "Service observations require LAN_SERVICE_CHECK_ENABLED=true."
        )

    created = updated = services_created = duplicates_avoided = 0
    now = datetime.now(UTC)
    for observation in observations:
        address = validate_allowed_ip(observation.ip_address)
        if address not in network:
            raise LanConfigurationError(
                "An observed asset is outside the selected CIDR."
            )
        try:
            previous_asset = await _asset_by_ip_or_mac(
                db, observation.ip_address, observation.mac_address
            )
        except LanAssetIdentityConflictError:
            duplicates_avoided += 1
            continue
        old_status = previous_asset.status if previous_asset else None
        old_hostname = previous_asset.hostname if previous_asset else None
        old_mac = previous_asset.mac_address if previous_asset else None
        old_ip = previous_asset.ip_address if previous_asset else None
        try:
            asset, was_created = await _upsert_observation(db, user, observation, now)
        except LanAssetIdentityConflictError:
            duplicates_avoided += 1
            continue
        await record_asset_observation_changes(
            db,
            asset=asset,
            created=was_created,
            old_status=old_status,
            old_hostname=old_hostname,
            old_mac=old_mac,
            source=observation.source,
            detected_at=now,
            old_ip=old_ip,
        )
        created += int(was_created)
        updated += int(not was_created)
        for service in observation.services:
            await record_service_observation(
                db,
                asset=asset,
                observation=service,
                source=observation.source,
                observed_at=now,
            )
            services_created += 1

    limitation = None
    if not observations:
        limitation = (
            native_snapshot.limitation
            if native_snapshot is not None
            else get_monitoring_activation().docker_limitation
        )
        await _notify_discovery_limitation(db, user)
    await record_event(
        db,
        action="lan.discovery.executed",
        actor_id=user.id,
        resource_type="lan_monitoring",
        metadata={
            "cidr": str(network),
            "observations": len(observations),
            "created": created,
            "updated": updated,
            "duplicates_avoided": duplicates_avoided,
            "provider": "native_host_provider"
            if settings.RUNTIME_PROFILE == "desktop"
            else "container_neighbor_table",
            "docker_limited": settings.RUNTIME_PROFILE != "desktop",
        },
    )
    await db.flush()
    return LanDiscoveryResponse(
        enabled=True,
        cidr=str(network),
        observations_received=len(observations),
        assets_created=created,
        assets_updated=updated,
        service_observations_created=services_created,
        limitation=limitation,
        message=(
            "Authorized LAN observations were processed."
            if observations
            else "Discovery completed safely with no accessible observations."
        ),
    )


class LanAssetIdentityConflictError(Exception):
    """A current private IP is associated with conflicting stable MAC evidence."""


def _normalized_os_family(os_name: str) -> str:
    normalized = os_name.casefold()
    if "windows" in normalized:
        return "windows"
    if "linux" in normalized or "debian" in normalized:
        return "linux"
    if "mac" in normalized or "darwin" in normalized:
        return "macos"
    return "unknown"


def _snapshot_local_addresses(snapshot: NativeLanSnapshot | None) -> set[str]:
    if snapshot is None:
        return set()
    return {item.address for item in snapshot.interfaces}


def _native_neighbor_observations(
    snapshot: NativeLanSnapshot, selected_network: ipaddress.IPv4Network | None = None
) -> list[LanDiscoveryObservation]:
    allowed = [item.network for item in snapshot.reachable_networks]
    observations: list[LanDiscoveryObservation] = []
    for item in snapshot.neighbors:
        try:
            address = validate_allowed_ip(item.ip_address)
        except LanConfigurationError:
            continue
        if not any(address in network for network in allowed):
            continue
        if selected_network is not None and address not in selected_network:
            continue
        observations.append(
            LanDiscoveryObservation(
                ip_address=str(address),
                mac_address=item.mac_address,
                interface_name=item.interface,
                source="host_neighbor_table",
                evidence_state=(
                    "online"
                    if item.state in {"reachable", "permanent"}
                    else "unknown"
                ),
            )
        )
    return observations[: settings.LAN_SERVICE_CHECK_MAX_HOSTS]


async def _tcp_discovery(
    networks: list[ipaddress.IPv4Network], local_addresses: set[str]
) -> list[LanDiscoveryObservation]:
    """Bounded connect-only liveness checks over configured ports, never shell ping."""
    if (
        not settings.LAN_DISCOVERY_PING_ENABLED
        or not settings.LAN_SERVICE_CHECK_ENABLED
        or not networks
    ):
        return []
    candidates = _bounded_tcp_candidates(networks, local_addresses)
    ports = configured_service_ports()

    async def probe_port(address: ipaddress.IPv4Address, port: int) -> bool:
        try:
            _reader, writer = await asyncio.wait_for(
                asyncio.open_connection(str(address), port),
                timeout=settings.LAN_SERVICE_CHECK_TIMEOUT_SECONDS,
            )
        except ConnectionRefusedError:
            return True
        except (OSError, TimeoutError):
            return False
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass
        return True

    queue: asyncio.Queue[ipaddress.IPv4Address] = asyncio.Queue()
    for candidate in candidates:
        queue.put_nowait(candidate)
    responsive: set[str] = set()

    async def worker() -> None:
        while True:
            try:
                address = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                for port in ports:
                    if await probe_port(address, port):
                        responsive.add(str(address))
                        break
            finally:
                queue.task_done()

    worker_count = min(settings.LAN_DISCOVERY_CONCURRENCY, len(candidates))
    if worker_count:
        await asyncio.gather(*(worker() for _ in range(worker_count)))
    return [
        LanDiscoveryObservation(
            ip_address=address,
            source="tcp_connect",
            evidence_state="online",
        )
        for address in sorted(responsive, key=ipaddress.IPv4Address)
    ]


def _bounded_tcp_candidates(
    networks: list[ipaddress.IPv4Network], local_addresses: set[str]
) -> list[ipaddress.IPv4Address]:
    """Return a deterministic, host-capped candidate set inside authorized ranges."""
    candidates: list[ipaddress.IPv4Address] = []
    seen: set[str] = set()
    for network in networks:
        for address in network.hosts():
            text_address = str(address)
            if text_address in local_addresses or text_address in seen:
                continue
            if address in {network.network_address, network.broadcast_address}:
                continue
            try:
                validate_allowed_ip(text_address)
            except LanConfigurationError:
                continue
            seen.add(text_address)
            candidates.append(address)
            if len(candidates) >= settings.LAN_SERVICE_CHECK_MAX_HOSTS:
                break
        if len(candidates) >= settings.LAN_SERVICE_CHECK_MAX_HOSTS:
            break
    return candidates


async def run_native_lan_discovery(db: AsyncSession) -> str:
    """Collect native host evidence and persist assets without frontend credentials."""
    if not settings.LAN_MONITORING_ENABLED:
        return "LAN discovery is disabled by configuration."
    if not await _try_advisory_lock(db, 4):
        return "A bounded LAN discovery cycle is already running."
    started = monotonic()
    snapshot = await asyncio.to_thread(
        collect_native_snapshot, tuple(configured_networks())
    )
    now = datetime.now(UTC)
    created = updated = duplicates_avoided = 0
    if settings.RUNTIME_PROFILE == "desktop" and snapshot.primary_address:
        host = LanDiscoveryObservation(
            ip_address=snapshot.primary_address,
            mac_address=snapshot.primary_mac,
            hostname=snapshot.hostname,
            asset_type="server_host",
            source="native_host_provider",
            # A new RavenTech host is trusted below; an existing operator
            # authorization decision must remain authoritative.
            is_authorized=None,
            evidence_state="online",
        )
        try:
            prior = await _asset_by_ip_or_mac(
                db, host.ip_address, host.mac_address
            )
            old_status = prior.status if prior else None
            old_hostname = prior.hostname if prior else None
            old_mac = prior.mac_address if prior else None
            old_ip = prior.ip_address if prior else None
            asset, was_created = await _upsert_observation(db, None, host, now)
            asset.asset_type = "server_host"
            asset.source = "native_server_host"
            if was_created or (
                prior is not None
                and prior.source
                in {"host_neighbor_table", "tcp_connect", "ping", "arp"}
            ):
                asset.is_authorized = True
            asset.os_name = snapshot.os_name
            asset.os_version = snapshot.os_version
            asset.os_family = _normalized_os_family(snapshot.os_name)
            asset.architecture = snapshot.architecture
            asset.device_type = "server"
            asset.classification_source = "native_server_host"
            asset.classification_confidence = "high"
            asset.classification_evidence = [
                "native RavenTech desktop host provider",
                "local OS metadata",
            ]
            asset.capabilities = [
                "host_metrics",
                "native_interfaces",
                "neighbor_table",
                "local_service_inventory",
            ]
            await record_asset_observation_changes(
                db,
                asset=asset,
                created=was_created,
                old_status=old_status,
                old_hostname=old_hostname,
                old_mac=old_mac,
                old_ip=old_ip,
                source="native_server_host",
                detected_at=now,
            )
            created += int(was_created)
            updated += int(not was_created)
        except LanAssetIdentityConflictError:
            duplicates_avoided += 1

    observations = _native_neighbor_observations(snapshot)
    tcp_candidates: list[ipaddress.IPv4Address] = []
    tcp_observations: list[LanDiscoveryObservation] = []
    if settings.LAN_DISCOVERY_PING_ENABLED:
        known_addresses = _snapshot_local_addresses(snapshot) | {
            item.ip_address for item in snapshot.neighbors
        }
        candidate_networks = [item.network for item in snapshot.reachable_networks]
        tcp_candidates = _bounded_tcp_candidates(candidate_networks, known_addresses)
        tcp_observations = await _tcp_discovery(
            candidate_networks,
            known_addresses,
        )
        observations = _merge_observations(observations, tcp_observations)
    for observation in observations[: settings.LAN_SERVICE_CHECK_MAX_HOSTS]:
        try:
            previous = await _asset_by_ip_or_mac(
                db, observation.ip_address, observation.mac_address
            )
            old_status = previous.status if previous else None
            old_hostname = previous.hostname if previous else None
            old_mac = previous.mac_address if previous else None
            old_ip = previous.ip_address if previous else None
            asset, was_created = await _upsert_observation(
                db, None, observation, now
            )
        except LanAssetIdentityConflictError:
            duplicates_avoided += 1
            continue
        await record_asset_observation_changes(
            db,
            asset=asset,
            created=was_created,
            old_status=old_status,
            old_hostname=old_hostname,
            old_mac=old_mac,
            old_ip=old_ip,
            source=observation.source,
            detected_at=now,
        )
        created += int(was_created)
        updated += int(not was_created)
        if was_created or old_status != asset.status:
            from app.services.background_jobs import enqueue_job

            await enqueue_job(
                db,
                "posture.recompute",
                {"asset_id": str(asset.id)},
                priority=20,
                dedupe_key=f"lan-discovery-posture:{asset.id}",
                cooldown_seconds=300,
            )

    await record_event(
        db,
        action="lan.discovery.executed",
        resource_type="lan_monitoring",
        metadata={
            "provider": "native_host_provider",
            "neighbors_read": len(snapshot.neighbors),
            "interfaces_read": len(snapshot.interfaces),
            "reachable_networks": len(snapshot.reachable_networks),
            "candidate_hosts": len(tcp_candidates),
            "hosts_contacted": len(tcp_candidates),
            "tcp_hosts_responded": len(tcp_observations),
            "assets_created": created,
            "assets_updated": updated,
            "duplicates_avoided": duplicates_avoided,
            "visibility_limited": bool(snapshot.limitation)
            and not tcp_observations,
            "duration_ms": max(0, int((monotonic() - started) * 1000)),
        },
    )
    await db.flush()
    return (
        f"Native host discovery completed: {created} created, {updated} updated, "
        f"{len(snapshot.neighbors)} neighbor observations, "
        f"{len(tcp_observations)} TCP-responsive hosts across "
        f"{len(snapshot.reachable_networks)} reachable authorized networks; "
        f"{duplicates_avoided} identity conflicts were skipped."
    )


async def register_agent(
    db: AsyncSession,
    body: LanAgentRegistration,
    credential: AgentEnrollmentToken | None = None,
) -> LanAgentRegistrationResponse:
    _ensure_enabled()
    address = validate_allowed_ip(body.ip_address)
    now = datetime.now(UTC)
    asset = await _asset_by_ip(db, str(address))
    created = asset is None
    new_enrollment = asset is None or asset.source not in AGENT_ASSET_SOURCES
    old_status = asset.status if asset else None
    old_hostname = asset.hostname if asset else None
    old_mac = asset.mac_address if asset else None
    if asset is None:
        asset = LanAsset(
            ip_address=str(address),
            first_seen=now,
            confidence=95,
            source="endpoint_agent",
            is_authorized=True,
        )
        db.add(asset)
    asset.mac_address = body.mac_address or asset.mac_address
    if not asset.hostname or asset.source in AGENT_ASSET_SOURCES:
        asset.hostname = _clean(body.hostname) or asset.hostname
    if asset.classification_source != "operator":
        asset.asset_type = body.asset_type
    asset.os_name = _clean(body.os_name)
    asset.os_version = _clean(body.os_version)
    asset.architecture = _clean(body.architecture)
    asset.agent_mode = body.agent_mode
    asset.agent_form_factor = body.form_factor
    asset.source = "endpoint_agent"
    _classify_asset(asset, agent_family=body.os_family, agent_form_factor=body.form_factor)
    asset.status = "online"
    asset.last_seen = now
    asset.last_checked_at = now
    asset.monitoring_enabled = True
    asset.enrolled_at = asset.enrolled_at or now
    asset.enrollment_token_id = (
        credential.id if credential else asset.enrollment_token_id
    )
    asset.capabilities = body.capabilities
    if new_enrollment and credential is not None:
        credential.enrollment_count += 1
    await db.flush()
    await record_asset_observation_changes(
        db,
        asset=asset,
        created=created,
        old_status=old_status,
        old_hostname=old_hostname,
        old_mac=old_mac,
        source="endpoint_agent",
        detected_at=now,
    )
    await record_event(
        db,
        action="lan.agent.registered",
        resource_type="lan_asset",
        resource_id=asset.id,
        metadata={"created": created, "agent_version": body.agent_version},
    )
    if new_enrollment:
        await create_admin_notification(
            db,
            notification_type="monitoring_alert",
            severity="success",
            title="Endpoint agent enrolled",
            message=f"An endpoint agent enrolled for authorized asset {asset.ip_address}.",
            entity_type="lan_asset",
            entity_id=asset.id,
            action_url="/monitoring",
            metadata={"rule": "agent_enrolled"},
            dedupe_key_prefix=f"agent-enrolled:{asset.id}",
        )
    return LanAgentRegistrationResponse(
        accepted=True,
        asset_id=asset.id,
        monitoring_enabled=True,
        message="Endpoint agent registered for authorized LAN telemetry.",
    )


async def ingest_agent_telemetry(
    db: AsyncSession, body: LanAgentTelemetryIngest
) -> LanAgentTelemetryResponse:
    _ensure_enabled()
    asset = await db.get(LanAsset, body.asset_id)
    if asset is None or asset.source not in AGENT_ASSET_SOURCES:
        raise LanAssetNotFoundError
    received_at = datetime.now(UTC)
    old_status = asset.status
    previous = (
        (
            await db.execute(
                select(LanAssetTelemetry)
                .where(LanAssetTelemetry.lan_asset_id == asset.id)
                .order_by(LanAssetTelemetry.collected_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    telemetry = LanAssetTelemetry(
        lan_asset_id=asset.id,
        cpu_percent=body.cpu_percent,
        memory_percent=body.memory_percent,
        disk_percent=body.disk_percent,
        uptime_seconds=body.uptime_seconds,
        os_name=_clean(body.os_name),
        os_version=_clean(body.os_version),
        agent_version=body.agent_version,
        collected_at=body.collected_at,
        event_metadata={
            **body.metadata,
            "os_build": body.os_build,
            "disk_free_gb": body.disk_free_gb,
            "firewall_status": body.firewall_status,
            "antivirus_status": body.antivirus_status,
            "patch_status": body.patch_status,
            "latest_patch_date": body.latest_patch_date,
            "recent_hotfix_count": body.recent_hotfix_count,
            "pending_reboot": body.pending_reboot,
            "listening_tcp_ports": body.listening_tcp_ports,
        },
    )
    db.add(telemetry)
    asset.status = "online"
    asset.last_seen = body.collected_at
    asset.last_checked_at = received_at
    if body.os_name:
        asset.os_name = _clean(body.os_name)
    if body.os_version:
        asset.os_version = _clean(body.os_version)
    _classify_asset(asset)
    if old_status == "offline":
        await record_asset_observation_changes(
            db,
            asset=asset,
            created=False,
            old_status=old_status,
            old_hostname=asset.hostname,
            old_mac=asset.mac_address,
            source="endpoint_agent",
            detected_at=body.collected_at,
        )
    await record_agent_telemetry_changes(db, asset, previous, telemetry)
    await record_event(
        db,
        action="lan.agent.telemetry_ingested",
        resource_type="lan_asset",
        resource_id=asset.id,
        metadata={
            "agent_version": body.agent_version,
            "metric_count": _metric_count(body),
        },
    )
    await db.flush()
    from app.services.job_dispatch import dispatcher

    await dispatcher().dispatch_job(
        db, "posture.recompute", {"asset_id": str(asset.id)},
        dedupe_key=f"posture:{asset.id}",
    )
    return LanAgentTelemetryResponse(
        accepted=True,
        asset_id=asset.id,
        received_at=received_at,
        message="Endpoint telemetry accepted.",
    )


async def ingest_server_host_observations(
    db: AsyncSession,
    user: User,
    body: AgentTelemetryIngest,
) -> tuple[LanAsset | None, int, int]:
    """Persist only authorized ServerHost identity and read-only neighbor observations."""
    if (
        body.agent_role != "server_host"
        or not settings.LAN_MONITORING_ENABLED
        or not settings.LAN_REJECT_PUBLIC_CIDRS
    ):
        return None, 0, len(body.neighbor_observations)

    now = datetime.now(UTC)
    touched: set[uuid.UUID] = set()
    server_asset: LanAsset | None = None
    if body.ip_address:
        try:
            address = validate_allowed_ip(body.ip_address)
        except LanConfigurationError:
            address = None
        if address is not None:
            server_asset = await _asset_by_ip_or_mac(
                db, str(address), body.mac_address
            )
            created = server_asset is None
            old_status = server_asset.status if server_asset else None
            old_hostname = server_asset.hostname if server_asset else None
            old_mac = server_asset.mac_address if server_asset else None
            old_ip = server_asset.ip_address if server_asset else None
            if server_asset is None:
                server_asset = LanAsset(
                    ip_address=str(address),
                    first_seen=body.collected_at,
                    source="endpoint_agent",
                    is_authorized=True,
                    confidence=95,
                    created_by=user.id,
                )
                db.add(server_asset)
            elif server_asset.ip_address != str(address):
                server_asset.ip_address = str(address)
            server_asset.mac_address = body.mac_address or server_asset.mac_address
            if not server_asset.hostname or server_asset.source in AGENT_ASSET_SOURCES:
                server_asset.hostname = _clean(body.hostname) or server_asset.hostname
            server_asset.asset_type = "server_host"
            server_asset.source = "endpoint_agent"
            server_asset.os_name = _clean(body.os_name)
            server_asset.os_version = _clean(body.os_version)
            server_asset.agent_mode = "ServerHost"
            server_asset.agent_form_factor = "server"
            _classify_asset(server_asset, agent_form_factor="server")
            server_asset.status = "online"
            server_asset.last_seen = body.collected_at
            server_asset.last_checked_at = now
            server_asset.monitoring_enabled = True
            server_asset.enrolled_at = server_asset.enrolled_at or now
            server_asset.capabilities = [
                "basic_telemetry",
                "host_metrics",
                "host_neighbor_observations",
                "server_host",
            ]
            await db.flush()
            await record_asset_observation_changes(
                db,
                asset=server_asset,
                created=created,
                old_status=old_status,
                old_hostname=old_hostname,
                old_mac=old_mac,
                source="endpoint_agent",
                detected_at=body.collected_at,
                old_ip=old_ip,
            )
            telemetry = LanAssetTelemetry(
                lan_asset_id=server_asset.id,
                cpu_percent=body.cpu_percent,
                memory_percent=body.memory_percent,
                disk_percent=body.disk_percent,
                uptime_seconds=body.uptime_seconds,
                os_name=_clean(body.os_name),
                os_version=_clean(body.os_version),
                agent_version=CURRENT_AGENT_VERSION,
                collected_at=body.collected_at,
                event_metadata={
                    "agent_id": body.agent_id,
                    "agent_mode": "server_host",
                    "os_build": body.os_build,
                    "listening_tcp_ports": body.listening_tcp_ports,
                },
            )
            db.add(telemetry)
            touched.add(server_asset.id)

    accepted = 0
    rejected = 0
    assets_created = 0
    assets_updated = 0
    deduped_observations = _dedupe_host_neighbors(body.neighbor_observations)
    for observation in deduped_observations:
        try:
            validate_allowed_ip(observation.ip_address)
        except LanConfigurationError:
            rejected += 1
            continue
        lan_observation = LanDiscoveryObservation(
            ip_address=observation.ip_address,
            mac_address=observation.mac_address,
            source="host_neighbor_table",
            interface_name=observation.interface_name,
            notes=f"Host neighbor state: {observation.state}",
        )
        previous = await _asset_by_ip_or_mac(
            db, lan_observation.ip_address, lan_observation.mac_address
        )
        old_status = previous.status if previous else None
        old_hostname = previous.hostname if previous else None
        old_mac = previous.mac_address if previous else None
        old_ip = previous.ip_address if previous else None
        asset, created = await _upsert_observation(db, user, lan_observation, observation.observed_at)
        if observation.state == "unreachable":
            asset.status = "offline"
        elif observation.state in {"stale", "incomplete", "unknown"}:
            asset.status = "unknown"
        await record_asset_observation_changes(
            db,
            asset=asset,
            created=created,
            old_status=old_status,
            old_hostname=old_hostname,
            old_mac=old_mac,
            source="host_neighbor_table",
            detected_at=observation.observed_at,
            old_ip=old_ip,
        )
        touched.add(asset.id)
        accepted += 1
        assets_created += int(created)
        assets_updated += int(not created)

    await record_event(
        db,
        action="lan.host_neighbors.ingested",
        actor_id=user.id,
        resource_type="lan_monitoring",
        resource_id=server_asset.id if server_asset else None,
        metadata={
            "agent_id": body.agent_id,
            "received": len(body.neighbor_observations),
            "accepted": accepted,
            "rejected": rejected,
            "deduplicated": len(body.neighbor_observations)
            - len(deduped_observations),
            "out_of_cidr": rejected,
            "assets_created": assets_created,
            "assets_updated": assets_updated,
        },
    )
    await db.flush()
    from app.services.job_dispatch import dispatcher

    for asset_id in touched:
        await dispatcher().dispatch_job(
            db, "posture.recompute", {"asset_id": str(asset_id)},
            dedupe_key=f"posture:{asset_id}",
        )
    return server_asset, accepted, rejected


async def list_asset_telemetry(
    db: AsyncSession, asset_id: uuid.UUID, limit: int
) -> LanTelemetryListResponse:
    await _require_asset(db, asset_id)
    rows = list(
        (
            await db.execute(
                select(LanAssetTelemetry)
                .where(LanAssetTelemetry.lan_asset_id == asset_id)
                .order_by(LanAssetTelemetry.collected_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return LanTelemetryListResponse(
        total=len(rows),
        items=[_telemetry_response(item) for item in rows],
    )


async def list_asset_services(
    db: AsyncSession, asset_id: uuid.UUID, limit: int
) -> LanServiceListResponse:
    asset = await _require_asset(db, asset_id)
    baseline = await lan_baseline(db, asset_id)
    rows = list(
        (
            await db.execute(
                select(LanServiceObservation)
                .where(LanServiceObservation.lan_asset_id == asset_id)
                .order_by(LanServiceObservation.observed_at.desc())
                .limit(min(max(limit * 100, 1_000), 10_000))
            )
        )
        .scalars()
        .all()
    )
    summaries = _service_summary_responses(list(reversed(rows)), asset=asset, baseline=baseline)[:limit]
    return LanServiceListResponse(
        total=len(summaries),
        service_checks_enabled=settings.LAN_SERVICE_CHECK_ENABLED,
        items=summaries,
    )


async def list_open_ports(db: AsyncSession, limit: int = 500) -> LanOpenPortsResponse:
    rows = list(
        (
            await db.execute(
                select(LanServiceObservation)
                .where(LanServiceObservation.status == "open")
                .order_by(LanServiceObservation.observed_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return LanOpenPortsResponse(
        total=len(rows), items=[_service_response(item) for item in rows]
    )


async def check_asset_services(
    db: AsyncSession, user: User, asset_id: uuid.UUID
) -> LanServiceCheckResponse:
    _ensure_enabled()
    if not settings.LAN_SERVICE_CHECK_ENABLED:
        raise LanServiceCheckDisabledError
    asset = await _require_asset(db, asset_id)
    validate_allowed_ip(asset.ip_address)
    if not asset.is_authorized or not asset.monitoring_enabled:
        raise LanConfigurationError(
            "Service checks require an authorized asset with monitoring enabled."
        )
    if not await _try_advisory_lock(db, 5):
        raise LanDiscoveryRateLimitedError
    last = (
        await db.execute(
            select(func.max(AuditLog.created_at)).where(
                AuditLog.action == "lan.service_check.executed",
                AuditLog.resource_id == asset.id,
            )
        )
    ).scalar_one_or_none()
    if last and datetime.now(UTC) - last < timedelta(
        seconds=settings.LAN_DISCOVERY_INTERVAL_SECONDS
    ):
        raise LanDiscoveryRateLimitedError
    ports = configured_service_ports()
    observations = await asyncio.gather(
        *(_tcp_service_observation(asset.ip_address, port) for port in ports)
    )
    now = datetime.now(UTC)
    for service in observations:
        await record_service_observation(
            db,
            asset=asset,
            observation=service,
            source="tcp_connect",
            observed_at=now,
        )
    asset.last_checked_at = now
    await record_event(
        db,
        action="lan.service_check.executed",
        actor_id=user.id,
        resource_type="lan_asset",
        resource_id=asset.id,
        metadata={
            "ports_checked": len(ports),
            "open_ports": sum(item.status == "open" for item in observations),
            "tcp_connect_only": True,
        },
    )
    await db.flush()
    return LanServiceCheckResponse(
        asset_id=asset.id,
        ip_address=asset.ip_address,
        ports_checked=len(ports),
        observations_created=len(observations),
        open_ports=sum(item.status == "open" for item in observations),
        message="Authorized TCP connect service check completed without authentication or exploit activity.",
    )


async def get_target_service_check_status(
    db: AsyncSession, target: Target
) -> TargetServiceCheckStatus:
    asset = await _target_lan_asset(db, target)
    ports = configured_service_ports()
    reason = _target_service_check_reason(asset)
    observations: list[LanServiceResponse] = []
    last_check: datetime | None = None
    if asset is not None:
        rows = list(
            (
                await db.execute(
                    select(LanServiceObservation)
                    .where(LanServiceObservation.lan_asset_id == asset.id)
                    .order_by(LanServiceObservation.observed_at.desc())
                )
            )
            .scalars()
            .all()
        )
        latest_by_port: dict[int, LanServiceObservation] = {}
        for row in rows:
            latest_by_port.setdefault(row.port, row)
        observations = [
            _service_response(item)
            for item in sorted(latest_by_port.values(), key=lambda item: item.port)
        ]
        last_check = (
            await db.execute(
                select(func.max(AuditLog.created_at)).where(
                    AuditLog.action == "lan.service_check.executed",
                    AuditLog.resource_id == asset.id,
                )
            )
        ).scalar_one_or_none()
    return TargetServiceCheckStatus(
        target_id=target.id,
        target_type=target.target_type,
        target_is_url_service=target.target_type == "url",
        eligible=reason.startswith("Eligible:"),
        reason=reason,
        lan_asset_id=asset.id if asset else None,
        ip_address=asset.ip_address if asset else None,
        configured_ports=ports,
        last_service_check_at=last_check,
        observations=observations,
    )


async def check_target_services(
    db: AsyncSession, user: User, target: Target
) -> LanServiceCheckResponse:
    status = await get_target_service_check_status(db, target)
    if not status.eligible or status.lan_asset_id is None:
        raise LanConfigurationError(status.reason)
    return await check_asset_services(db, user, status.lan_asset_id)


async def _target_lan_asset(db: AsyncSession, target: Target) -> LanAsset | None:
    candidate = target.target_value.strip()
    if target.target_type == "url":
        candidate = urlparse(candidate).hostname or ""
    if target.target_type in {"ip", "url"}:
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            pass
        else:
            if not isinstance(address, ipaddress.IPv4Address) or not any(
                address in network for network in RFC1918_NETWORKS
            ):
                return None
            return await _asset_by_ip(db, str(address))
    normalized_host = candidate.rstrip(".").lower()
    if not normalized_host:
        return None
    return (
        await db.execute(
            select(LanAsset).where(func.lower(LanAsset.hostname) == normalized_host)
        )
    ).scalar_one_or_none()


def _target_service_check_reason(asset: LanAsset | None) -> str:
    if not settings.LAN_MONITORING_ENABLED:
        return "Ineligible: LAN monitoring is disabled in local configuration."
    if not settings.LAN_SERVICE_CHECK_ENABLED:
        return "Ineligible: authorized TCP service checks are disabled in local configuration."
    if asset is None:
        return "Ineligible: no existing private LAN asset matches this target IP or hostname."
    try:
        validate_allowed_ip(asset.ip_address)
    except LanConfigurationError:
        return "Ineligible: the matched asset is outside the configured private LAN allowlist."
    if not asset.is_authorized:
        return "Ineligible: the matched LAN asset is not authorized."
    if not asset.monitoring_enabled:
        return "Ineligible: monitoring is disabled for the matched LAN asset."
    return "Eligible: this target maps to an authorized, monitored private LAN asset."


def configured_service_ports() -> list[int]:
    ports = sorted(
        {
            int(value.strip())
            for value in settings.LAN_SERVICE_CHECK_PORTS.split(",")
            if value.strip()
        }
    )
    if (
        not ports
        or len(ports) > settings.LAN_SERVICE_CHECK_MAX_PORTS
        or any(port < 1 or port > 65535 for port in ports)
    ):
        raise LanConfigurationError(
            "Configured service ports must contain 1-32 valid TCP ports."
        )
    return ports


async def _tcp_service_observation(ip_address: str, port: int) -> LanServiceInput:
    writer: asyncio.StreamWriter | None = None
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip_address, port),
            timeout=settings.LAN_SERVICE_CHECK_TIMEOUT_SECONDS,
        )
        banner = b""
        if settings.LAN_SSH_BANNER_DETECTION_ENABLED:
            try:
                banner = await asyncio.wait_for(
                    reader.read(96),
                    timeout=min(0.3, settings.LAN_SERVICE_CHECK_TIMEOUT_SECONDS),
                )
            except (TimeoutError, OSError):
                pass
        return _classify_service(port, banner)
    except TimeoutError:
        return LanServiceInput(
            port=port,
            status="timeout",
            service_name=SERVICE_GUESSES.get(port),
            confidence=20,
        )
    except ConnectionRefusedError:
        return LanServiceInput(
            port=port,
            status="closed",
            service_name=SERVICE_GUESSES.get(port),
            confidence=80,
        )
    except OSError:
        return LanServiceInput(
            port=port,
            status="filtered",
            service_name=SERVICE_GUESSES.get(port),
            confidence=20,
        )
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass


def _classify_service(port: int, banner: bytes) -> LanServiceInput:
    ssh = banner.lstrip().upper().startswith(b"SSH-")
    service = "ssh" if ssh else SERVICE_GUESSES.get(port)
    label = "possible SSH service" if ssh or port == 22 else "HTTPS-like" if port == 8443 and service == "https" else service
    confidence = 95 if ssh else 75 if service else 50
    hint = "SSH protocol banner detected" if ssh else None
    return LanServiceInput(
        port=port,
        status="open",
        service_name=service,
        service_label=label,
        confidence=confidence,
        banner_hint=hint,
        non_standard_ssh=ssh and port != 22,
    )


async def get_lan_alerts(db: AsyncSession) -> list[MonitoringAlert]:
    if not settings.LAN_MONITORING_ENABLED:
        return []
    await reconcile_asset_state_changes(db)
    assets = await list_lan_assets(db)
    alerts: list[MonitoringAlert] = []
    for asset in assets.items:
        for indicator in asset.risk_indicators:
            if indicator.severity == "info":
                continue
            alerts.append(
                MonitoringAlert(
                    key=f"lan:{asset.id}:{indicator.key}",
                    severity=indicator.severity,
                    title=f"LAN risk indicator: {indicator.label}",
                    message=f"{asset.ip_address}: {indicator.detail}",
                    category="lan",
                    action_url="/monitoring",
                )
            )
    recent_changes = list(
        (
            await db.execute(
                select(MonitoringChangeEvent).where(
                    MonitoringChangeEvent.acknowledged_at.is_(None),
                    MonitoringChangeEvent.detected_at
                    >= datetime.now(UTC) - timedelta(hours=24),
                    MonitoringChangeEvent.event_type.in_(
                        ("port_closed", "service_changed", "baseline_finding_opened")
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    alerts.extend(
        MonitoringAlert(
            key=f"lan:{item.asset_id}:change:{item.id}",
            severity="critical" if item.severity == "critical" else "warning",
            title=item.title,
            message=item.description,
            category=(
                "baseline"
                if item.event_type == "baseline_finding_opened"
                else "lan_change"
            ),
            source=item.source,
            observed_at=item.detected_at,
            action_url="/monitoring",
        )
        for item in recent_changes
    )
    from app.services.agent_management import baseline_alerts

    alerts.extend(await baseline_alerts(db))
    return alerts[:100]


async def notify_discovery_failure(db: AsyncSession, user: User) -> None:
    day = datetime.now(UTC).date().isoformat()
    await create_admin_notification(
        db,
        notification_type="monitoring_alert",
        severity="warning",
        title="LAN discovery failed",
        message="Authorized LAN discovery failed safely. Review local backend logs and configuration.",
        entity_type="lan_monitoring",
        actor_user_id=user.id,
        action_url="/monitoring",
        metadata={"rule": "lan_discovery_failed"},
        dedupe_key_prefix=f"lan:discovery-failed:{day}",
    )


def _asset_response(
    asset: LanAsset,
    telemetry: LanAssetTelemetry | None,
    services: list[LanServiceObservation],
    now: datetime,
    posture: EndpointSecurityPosture | None = None,
    baseline: LanServiceBaseline | None = None,
) -> LanAssetResponse:
    connection_medium = cast(
        Literal["ethernet", "wifi", "unknown"],
        asset.connection_medium
        if asset.connection_medium in {"ethernet", "wifi"}
        else "unknown",
    )
    connection_medium_confidence = cast(
        Literal["high", "medium", "low"],
        asset.connection_medium_confidence
        if asset.connection_medium_confidence in {"high", "medium"}
        else "low",
    )
    connected = _agent_connected(asset, telemetry, now)
    status = _effective_status(asset, telemetry, now)
    agent_asset = asset.source in AGENT_ASSET_SOURCES
    policy = baseline or LanServiceBaseline()
    summaries = [_service_response(item, asset=asset, baseline=policy) for item in services]
    service_eligible = bool(
        settings.LAN_MONITORING_ENABLED
        and settings.LAN_SERVICE_CHECK_ENABLED
        and asset.is_authorized
        and asset.monitoring_enabled
    )
    if not settings.LAN_MONITORING_ENABLED:
        service_reason = "LAN_MONITORING_ENABLED is false."
    elif not settings.LAN_SERVICE_CHECK_ENABLED:
        service_reason = "LAN_SERVICE_CHECK_ENABLED is false."
    elif not asset.is_authorized:
        service_reason = "Asset requires operator authorization before TCP checks."
    elif not asset.monitoring_enabled:
        service_reason = "Asset monitoring is disabled."
    else:
        service_reason = "Eligible for bounded configured-port TCP connect checks."
    return LanAssetResponse(
        id=asset.id,
        ip_address=asset.ip_address,
        mac_address=asset.mac_address,
        hostname=asset.hostname,
        vendor=asset.vendor,
        vendor_source=asset.vendor_source,
        vendor_confidence=asset.vendor_confidence or "low",
        os_family=asset.os_family or "unknown",
        os_name=asset.os_name,
        os_version=asset.os_version,
        architecture=asset.architecture,
        agent_mode=asset.agent_mode,
        device_type=asset.device_type or "unknown",
        connection_medium=connection_medium,
        connection_medium_source=asset.connection_medium_source,
        connection_medium_confidence=connection_medium_confidence,
        manual_device_type=asset.manual_device_type,
        classification_source=asset.classification_source or "insufficient_evidence",
        classification_confidence=asset.classification_confidence or "low",
        classification_evidence=asset.classification_evidence or [],
        asset_type=asset.asset_type,
        status=status,
        source=asset.source,
        first_seen=asset.first_seen,
        last_seen=asset.last_seen,
        last_checked_at=asset.last_checked_at,
        confidence=asset.confidence,
        notes=asset.notes,
        is_authorized=asset.is_authorized,
        monitoring_enabled=asset.monitoring_enabled,
        criticality=cast(AssetCriticality, asset.criticality),
        owner=asset.owner,
        business_function=asset.business_function,
        environment=asset.environment,
        enrolled_at=asset.enrolled_at,
        capabilities=asset.capabilities,
        agent_connected=connected,
        trust_state=_trust_state(asset),
        telemetry_freshness=(
            "fresh"
            if connected
            else "stale"
            if agent_asset and telemetry is not None
            else "missing"
        ),
        service_check_eligible=service_eligible,
        service_check_reason=service_reason,
        observed_services=len(services),
        observed_service_preview=[f"{item.port}/{item.protocol} {item.service_label or item.service_name or 'Unknown TCP service'} {item.status}" for item in sorted(services, key=lambda value: value.port)[:8]],
        service_healthy=sum(item.advisory_severity == "healthy" for item in summaries),
        service_warnings=sum(item.advisory_severity == "warning" for item in summaries),
        service_critical=sum(item.advisory_severity == "critical" for item in summaries),
        service_expected=sum(item.expectation == "expected" for item in summaries),
        service_unexpected=sum(item.expectation == "unexpected" for item in summaries),
        posture_status=cast(
            Literal["healthy", "needs_review", "at_risk", "critical", "unknown"],
            posture.posture_status if posture else "unknown",
        ),
        recommendation_count=posture.recommendation_count if posture else 0,
        response_latency_ms=asset.response_latency_ms,
        risk_indicators=_risk_indicators(asset, telemetry, services, status, connected, policy),
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


def _classify_asset(
    asset: LanAsset, *, agent_family: str | None = None,
    agent_form_factor: str | None = None,
) -> None:
    result = classify(
        os_name=asset.os_name,
        agent_family=agent_family,
        agent_form_factor=agent_form_factor or asset.agent_form_factor,
        agent_mode=asset.agent_mode if asset.source in AGENT_ASSET_SOURCES else None,
        manual_type=asset.manual_device_type,
        gateway=asset.ip_address == settings.LAN_GATEWAY_HINT or asset.asset_type == "gateway",
        hostname=asset.hostname,
        vendor=asset.vendor,
    )
    asset.os_family = result.os_family
    asset.device_type = result.device_type
    asset.classification_source = result.source
    asset.classification_confidence = result.confidence
    asset.classification_evidence = list(result.evidence)


def _trust_state(
    asset: LanAsset,
) -> Literal["authorized", "needs_review", "unauthorized", "known_agent", "gateway"]:
    if asset.asset_type == "gateway" and not asset.is_authorized:
        return "gateway"
    if asset.source in AGENT_ASSET_SOURCES and asset.is_authorized:
        return "known_agent"
    if asset.is_authorized:
        return "authorized"
    if asset.source == "host_neighbor_table":
        return "needs_review"
    return "unauthorized"


def _risk_indicators(
    asset: LanAsset,
    telemetry: LanAssetTelemetry | None,
    services: list[LanServiceObservation],
    status: str,
    connected: bool,
    baseline: LanServiceBaseline | None = None,
) -> list[LanRiskIndicator]:
    indicators: list[LanRiskIndicator] = []
    if not asset.is_authorized:
        indicators.append(
            _indicator(
                "unauthorized",
                "critical",
                "Unauthorized asset",
                "The asset has not been approved by an administrator.",
            )
        )
    if status == "offline" and asset.monitoring_enabled:
        indicators.append(
            _indicator(
                "offline",
                "critical" if asset.criticality == "critical" else "warning",
                "Asset offline",
                "No recent authorized observation is available.",
            )
        )
    if asset.source in AGENT_ASSET_SOURCES and not connected:
        indicators.append(
            _indicator(
                "agent_stale",
                "warning",
                "Agent not reporting",
                "Endpoint telemetry is missing or stale.",
            )
        )
    if asset.source not in AGENT_ASSET_SOURCES and asset.monitoring_enabled:
        indicators.append(
            _indicator(
                "unmanaged",
                "info",
                "Unmanaged asset",
                "No endpoint agent is registered for this asset.",
            )
        )
    if (
        telemetry
        and telemetry.agent_version
        and telemetry.agent_version != CURRENT_AGENT_VERSION
    ):
        indicators.append(
            _indicator(
                "agent_version",
                "warning",
                "Agent version review",
                "The reporting agent version differs from the current local script.",
            )
        )
    if telemetry:
        for key, label, value in (
            ("cpu", "CPU pressure", telemetry.cpu_percent),
            ("memory", "Memory pressure", telemetry.memory_percent),
            ("disk", "Disk pressure", telemetry.disk_percent),
        ):
            if value is not None and value >= 85:
                indicators.append(
                    _indicator(
                        f"high_{key}",
                        "critical" if value >= 95 else "warning",
                        label,
                        f"Latest reported utilization is {value:.1f}%.",
                    )
                )
    for service in services:
        if service.status != "open":
            continue
        policy = baseline or LanServiceBaseline()
        assessment = assess_lan_service(
            port=service.port, status=service.status, device_type=asset.device_type,
            os_family=asset.os_family, trust_state=_trust_state(asset),
            service_name=service.service_name, non_standard_ssh=service.non_standard_ssh,
            expected_ports=set(policy.expected_ports), allowed_ports=set(policy.allowed_ports),
            has_baseline=policy.configured, critical_ports=set(policy.critical_ports),
        )
        if assessment.severity in {"warning", "critical"}:
            indicators.append(
                _indicator(
                    f"risky_service_{service.port}" if service.port in RISKY_PORTS else f"service_exposure_{service.port}",
                    assessment.severity,
                    f"TCP/{service.port} requires review",
                    assessment.reason,
                )
            )
        if not asset.is_authorized:
            indicators.append(
                _indicator(
                    f"unauthorized_open_{service.port}",
                    "critical",
                    "Open service on unauthorized asset",
                    f"TCP/{service.port} is open on an asset awaiting authorization review.",
                )
            )
    if asset.monitoring_enabled and asset.last_seen is None:
        indicators.append(
            _indicator(
                "coverage",
                "warning",
                "Weak monitoring coverage",
                "The asset has never produced a successful observation.",
            )
        )
    return indicators


def _indicator(
    key: str, severity: LanRiskSeverity, label: str, detail: str
) -> LanRiskIndicator:
    return LanRiskIndicator(key=key, severity=severity, label=label, detail=detail)


async def _upsert_observation(
    db: AsyncSession,
    user: User | None,
    observation: LanDiscoveryObservation,
    now: datetime,
) -> tuple[LanAsset, bool]:
    address = str(validate_allowed_ip(observation.ip_address))
    asset = await _asset_by_ip_or_mac(db, address, observation.mac_address)
    current_ip_asset = await _asset_by_ip(db, address)
    if (
        current_ip_asset is not None
        and observation.mac_address
        and current_ip_asset.mac_address
        and observation.mac_address.upper() != current_ip_asset.mac_address.upper()
    ):
        # The IP lookup can return the occupied row after the MAC lookup misses.
        # Treat that as DHCP/IP reuse instead of silently keeping the old identity.
        raise LanAssetIdentityConflictError
    if asset is None and current_ip_asset is not None:
        asset = current_ip_asset
    elif asset is not None and asset.ip_address != address:
        if current_ip_asset is not None and current_ip_asset.id != asset.id:
            raise LanAssetIdentityConflictError
    created = asset is None
    if asset is None:
        asset = LanAsset(
            ip_address=address,
            first_seen=now,
            created_by=user.id if user else None,
            is_authorized=False,
        )
        db.add(asset)
    elif asset.ip_address != address:
        asset.ip_address = address
    asset.mac_address = asset.mac_address or observation.mac_address
    asset.hostname = asset.hostname or _clean(observation.hostname)
    if observation.vendor and not asset.vendor:
        asset.vendor = _clean(observation.vendor)
        asset.vendor_source = observation.source
        asset.vendor_confidence = "medium" if observation.source == "router" else "low"
    if observation.source == "router" and observation.connection_type:
        medium_hint = observation.connection_type.strip().casefold().replace("_", "-")
        reliable_medium = (
            "wifi"
            if medium_hint in {"wifi", "wi-fi", "wireless"}
            else "ethernet"
            if medium_hint in {"ethernet", "wired", "cable"}
            else None
        )
        if reliable_medium and asset.connection_medium_source != "operator":
            asset.connection_medium = reliable_medium
            asset.connection_medium_source = "router_observation"
            asset.connection_medium_confidence = "high"
    if observation.asset_type != "unknown" or asset.asset_type == "unknown":
        asset.asset_type = observation.asset_type
    if address == settings.LAN_GATEWAY_HINT:
        asset.asset_type = "gateway"
        asset.hostname = asset.hostname or "Likely gateway/router"
    _classify_asset(asset)
    if asset.source not in AGENT_ASSET_SOURCES and asset.source not in {
        "static",
        "router",
    }:
        asset.source = observation.source
    if observation.evidence_state == "online":
        asset.status = "online"
    elif created:
        asset.status = "unknown"
    if observation.evidence_state == "online":
        asset.last_seen = now
    asset.last_checked_at = now
    asset.response_latency_ms = observation.latency_ms
    asset.confidence = 80 if observation.source == "router" else 70
    if observation.is_authorized is not None:
        asset.is_authorized = observation.is_authorized
    context = [
        value
        for value in (
            f"Interface: {observation.interface_name}" if observation.interface_name else None,
            f"Connection: {observation.connection_type}" if observation.connection_type else None,
            _clean(observation.notes),
        )
        if value
    ]
    if context:
        additions = [item for item in context if not asset.notes or item not in asset.notes]
        if additions:
            asset.notes = " | ".join(
                value for value in (asset.notes, *additions) if value
            )
    await db.flush()
    return asset, created


def _service_observation(
    asset_id: uuid.UUID,
    ip_address: str,
    service: LanServiceInput,
    source: str,
    now: datetime,
) -> LanServiceObservation:
    return LanServiceObservation(
        lan_asset_id=asset_id,
        ip_address=ip_address,
        port=service.port,
        protocol=service.protocol,
        service_name=_clean(service.service_name),
        service_label=_clean(service.service_label),
        confidence=service.confidence,
        banner_hint=_clean(service.banner_hint),
        non_standard_ssh=service.non_standard_ssh,
        status=service.status,
        observed_at=now,
        source=source,
    )


async def _latest_telemetry(
    db: AsyncSession, asset_id: uuid.UUID | None = None
) -> dict[uuid.UUID, LanAssetTelemetry]:
    statement = select(LanAssetTelemetry).order_by(
        LanAssetTelemetry.collected_at.desc()
    )
    if asset_id:
        statement = statement.where(LanAssetTelemetry.lan_asset_id == asset_id)
    rows = list((await db.execute(statement)).scalars().all())
    latest: dict[uuid.UUID, LanAssetTelemetry] = {}
    for row in rows:
        latest.setdefault(row.lan_asset_id, row)
    return latest


async def _latest_neighbor_diagnostics(db: AsyncSession) -> dict[str, int]:
    latest = (
        (
            await db.execute(
                select(AuditLog)
                .where(AuditLog.action == "lan.host_neighbors.ingested")
                .order_by(AuditLog.created_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    metadata = (
        latest.event_metadata
        if latest is not None and isinstance(latest.event_metadata, dict)
        else {}
    )

    def count(key: str) -> int:
        value = metadata.get(key, 0)
        return value if isinstance(value, int) and value >= 0 else 0

    return {
        "neighbor_raw_observations": count("received"),
        "neighbor_accepted_observations": count("accepted"),
        "neighbor_rejected_observations": count("rejected"),
        "neighbor_deduplicated_observations": count("deduplicated"),
        "neighbor_out_of_cidr_observations": count("out_of_cidr"),
        "neighbor_assets_created": count("assets_created"),
        "neighbor_assets_updated": count("assets_updated"),
    }


async def _latest_services(
    db: AsyncSession, asset_id: uuid.UUID | None = None
) -> dict[uuid.UUID, list[LanServiceObservation]]:
    statement = select(LanServiceObservation).order_by(
        LanServiceObservation.observed_at.desc()
    )
    if asset_id:
        statement = statement.where(LanServiceObservation.lan_asset_id == asset_id)
    rows = list((await db.execute(statement)).scalars().all())
    grouped: dict[uuid.UUID, list[LanServiceObservation]] = {}
    seen: set[tuple[uuid.UUID, int, str]] = set()
    for row in rows:
        key = (row.lan_asset_id, row.port, row.protocol)
        if key in seen:
            continue
        seen.add(key)
        grouped.setdefault(row.lan_asset_id, []).append(row)
    return grouped


def _effective_status(
    asset: LanAsset, telemetry: LanAssetTelemetry | None, now: datetime
) -> LanAssetStatus:
    if not asset.monitoring_enabled:
        return "unknown"
    if asset.status == "offline":
        return "offline"
    if (
        asset.status == "unknown"
        and asset.last_checked_at is not None
        and (asset.last_seen is None or asset.last_checked_at >= asset.last_seen)
    ):
        return "unknown"
    if asset.source in AGENT_ASSET_SOURCES:
        return "online" if _agent_connected(asset, telemetry, now) else "offline"
    if asset.source == "host_neighbor_table" and asset.status in {"offline", "unknown"}:
        return "offline" if asset.status == "offline" else "unknown"
    stale_seconds = max(settings.LAN_DISCOVERY_INTERVAL_SECONDS * 2, 600)
    if asset.last_seen and now - asset.last_seen <= timedelta(seconds=stale_seconds):
        return "online"
    return "offline" if asset.last_seen else "unknown"


def _agent_connected(
    asset: LanAsset, telemetry: LanAssetTelemetry | None, now: datetime
) -> bool:
    return bool(
        asset.source in AGENT_ASSET_SOURCES
        and telemetry
        and now - telemetry.collected_at
        <= timedelta(minutes=settings.LAN_AGENT_MAX_STALE_MINUTES)
    )


async def _asset_by_ip(db: AsyncSession, ip_address: str) -> LanAsset | None:
    return (
        await db.execute(select(LanAsset).where(LanAsset.ip_address == ip_address))
    ).scalar_one_or_none()


async def _asset_by_ip_or_mac(
    db: AsyncSession, ip_address: str, mac_address: str | None
) -> LanAsset | None:
    if mac_address:
        asset = (
            await db.execute(
                select(LanAsset).where(
                    func.upper(LanAsset.mac_address) == mac_address.upper()
                )
            )
        ).scalars().first()
        if asset is not None:
            return asset
    return await _asset_by_ip(db, ip_address)


def _dedupe_host_neighbors(
    observations: list[HostNeighborObservation],
) -> list[HostNeighborObservation]:
    deduped: list[HostNeighborObservation] = []
    positions_by_ip: dict[str, int] = {}
    positions_by_mac: dict[str, int] = {}
    for item in observations:
        position = positions_by_ip.get(item.ip_address)
        if position is None and item.mac_address:
            position = positions_by_mac.get(item.mac_address)
        if position is not None:
            deduped[position] = item
            positions_by_ip[item.ip_address] = position
            if item.mac_address:
                positions_by_mac[item.mac_address] = position
            continue
        position = len(deduped)
        deduped.append(item)
        positions_by_ip[item.ip_address] = position
        if item.mac_address:
            positions_by_mac[item.mac_address] = position
    return deduped


async def _require_asset(db: AsyncSession, asset_id: uuid.UUID) -> LanAsset:
    asset = await db.get(LanAsset, asset_id)
    if asset is None:
        raise LanAssetNotFoundError
    return asset


async def _enforce_discovery_interval(db: AsyncSession) -> None:
    if not await _try_advisory_lock(db, 4):
        raise LanDiscoveryRateLimitedError
    last = (
        await db.execute(
            select(func.max(AuditLog.created_at)).where(
                AuditLog.action == "lan.discovery.executed"
            )
        )
    ).scalar_one_or_none()
    if last and datetime.now(UTC) - last < timedelta(
        seconds=settings.LAN_DISCOVERY_INTERVAL_SECONDS
    ):
        raise LanDiscoveryRateLimitedError


async def _try_advisory_lock(db: AsyncSession, lock_id: int) -> bool:
    return bool(
        (
            await db.execute(
                text("SELECT pg_try_advisory_xact_lock(50211, :lock_id)"),
                {"lock_id": lock_id},
            )
        ).scalar_one()
    )


def _read_container_arp(
    network: ipaddress.IPv4Network,
) -> list[LanDiscoveryObservation]:
    path = Path("/proc/net/arp")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[1:]
    except OSError:
        return []
    observations: list[LanDiscoveryObservation] = []
    for line in lines[:512]:
        fields = line.split()
        if len(fields) < 4:
            continue
        try:
            address = validate_allowed_ip(fields[0])
            if address not in network or fields[3] == "00:00:00:00:00:00":
                continue
            observations.append(
                LanDiscoveryObservation(
                    ip_address=str(address), mac_address=fields[3], source="arp"
                )
            )
        except (LanConfigurationError, ValueError):
            continue
    return observations


async def _stored_host_neighbor_observations(
    db: AsyncSession, network: ipaddress.IPv4Network
) -> list[LanDiscoveryObservation]:
    cutoff = datetime.now(UTC) - timedelta(
        seconds=max(settings.LAN_DISCOVERY_INTERVAL_SECONDS * 2, 600)
    )
    rows = list(
        (
            await db.execute(
                select(LanAsset)
                .where(
                    LanAsset.source == "host_neighbor_table",
                    LanAsset.last_seen >= cutoff,
                )
                .order_by(LanAsset.last_seen.desc())
                .limit(settings.LAN_SERVICE_CHECK_MAX_HOSTS)
            )
        )
        .scalars()
        .all()
    )
    observations: list[LanDiscoveryObservation] = []
    for item in rows:
        try:
            address = validate_allowed_ip(item.ip_address)
        except LanConfigurationError:
            continue
        if address not in network:
            continue
        observations.append(
            LanDiscoveryObservation(
                ip_address=item.ip_address,
                mac_address=item.mac_address,
                source="host_neighbor_table",
            )
        )
    return observations


async def _ping_network(
    network: ipaddress.IPv4Network,
) -> list[LanDiscoveryObservation]:
    # Keep the legacy helper name for compatibility with internal call sites,
    # but discovery is now TCP-connect-only and never launches a ping executable.
    return await _tcp_discovery([network], set())


async def _observe_configured_services(
    observations: list[LanDiscoveryObservation],
) -> None:
    ports = configured_service_ports()
    bounded = observations[: settings.LAN_SERVICE_CHECK_MAX_HOSTS]
    queue: asyncio.Queue[LanDiscoveryObservation] = asyncio.Queue()
    for observation in bounded:
        queue.put_nowait(observation)

    async def worker() -> None:
        while True:
            try:
                observation = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                for port in ports:
                    try:
                        result = await _tcp_service_observation(
                            observation.ip_address, port
                        )
                    except (OSError, TimeoutError):
                        result = LanServiceInput(port=port, status="unknown")
                    observation.services.append(result)
            finally:
                queue.task_done()

    worker_count = min(settings.LAN_DISCOVERY_CONCURRENCY, len(bounded))
    if worker_count:
        await asyncio.gather(*(worker() for _ in range(worker_count)))
    for observation in bounded:
        observation.services.sort(key=lambda item: item.port)


async def run_native_service_observation(db: AsyncSession) -> str:
    """Check configured TCP ports on explicitly authorized, monitored assets only."""
    if not settings.LAN_MONITORING_ENABLED or not settings.LAN_SERVICE_CHECK_ENABLED:
        return "Configured TCP service observations are disabled."
    if not await _try_advisory_lock(db, 5):
        return "A bounded service observation cycle is already running."
    authorized = tuple(configured_networks())
    if settings.RUNTIME_PROFILE == "desktop":
        snapshot = await asyncio.to_thread(collect_native_snapshot, authorized)
        authorized = tuple(item.network for item in snapshot.reachable_networks)
    if not authorized:
        return (
            "Service observations are limited because no authorized route is "
            "available."
        )
    rows = list(
        (
            await db.execute(
                select(LanAsset)
                .where(
                    LanAsset.is_authorized.is_(True),
                    LanAsset.monitoring_enabled.is_(True),
                )
                .order_by(LanAsset.last_seen.desc().nullslast())
                .limit(settings.LAN_SERVICE_CHECK_MAX_HOSTS * 2)
            )
        )
        .scalars()
        .all()
    )
    observations: list[LanDiscoveryObservation] = []
    for asset in rows:
        try:
            address = validate_allowed_ip(asset.ip_address)
        except LanConfigurationError:
            continue
        if not any(address in network for network in authorized):
            continue
        observations.append(
            LanDiscoveryObservation(
                ip_address=str(address),
                mac_address=asset.mac_address,
                source="host_neighbor_table",
            )
        )
        if len(observations) >= settings.LAN_SERVICE_CHECK_MAX_HOSTS:
            break
    await _observe_configured_services(observations)
    observed_at = datetime.now(UTC)
    created = 0
    for observation in observations:
        service_asset = await _asset_by_ip(db, observation.ip_address)
        if service_asset is None:
            continue
        for service in observation.services:
            await record_service_observation(
                db,
                asset=service_asset,
                observation=service,
                source="scheduled_native_service_check",
                observed_at=observed_at,
            )
            created += 1
    await record_event(
        db,
        action="lan.service_check.executed",
        resource_type="lan_monitoring",
        metadata={
            "provider": "native_host_provider"
            if settings.RUNTIME_PROFILE == "desktop"
            else "authorized_asset_inventory",
            "assets_checked": len(observations),
            "ports_configured": len(configured_service_ports()),
            "observations_created": created,
        },
    )
    await db.flush()
    return (
        "Configured TCP observations completed for "
        f"{len(observations)} authorized assets; "
        f"{created} observations recorded."
    )


def _merge_observations(
    first: list[LanDiscoveryObservation], second: list[LanDiscoveryObservation]
) -> list[LanDiscoveryObservation]:
    merged = {item.ip_address: item for item in first}
    for item in second:
        merged.setdefault(item.ip_address, item)
    return list(merged.values())


async def _notify_discovery_limitation(db: AsyncSession, user: User | None) -> None:
    day = datetime.now(UTC).date().isoformat()
    await create_admin_notification(
        db,
        notification_type="monitoring_alert",
        severity="info",
        title="LAN visibility is limited",
        message=(
            "RavenTech found no peers in the available authorized network "
            "observations. Segmentation, client isolation, firewall policy, or "
            "inactive devices may limit visibility."
        ),
        entity_type="lan_monitoring",
        actor_user_id=user.id if user else None,
        action_url="/monitoring",
        metadata={"rule": "lan_discovery_limited"},
        dedupe_key_prefix=f"lan:discovery-limited:{day}",
    )


def _telemetry_response(item: LanAssetTelemetry) -> LanTelemetryResponse:
    return LanTelemetryResponse(
        id=item.id,
        lan_asset_id=item.lan_asset_id,
        cpu_percent=item.cpu_percent,
        memory_percent=item.memory_percent,
        disk_percent=item.disk_percent,
        uptime_seconds=item.uptime_seconds,
        os_name=item.os_name,
        os_version=item.os_version,
        agent_version=item.agent_version,
        collected_at=item.collected_at,
        metadata=item.event_metadata if isinstance(item.event_metadata, dict) else {},
    )


def _service_response(
    item: LanServiceObservation,
    *,
    first_observed_at: datetime | None = None,
    previous_status: str | None = None,
    asset: LanAsset | None = None,
    baseline: LanServiceBaseline | None = None,
) -> LanServiceResponse:
    policy = baseline or LanServiceBaseline()
    assessment = assess_lan_service(
        port=item.port, status=item.status,
        device_type=asset.device_type if asset else "unknown",
        os_family=asset.os_family if asset else "unknown",
        trust_state=_trust_state(asset) if asset else "needs_review",
        service_name=item.service_name,
        non_standard_ssh=item.non_standard_ssh,
        expected_ports=set(policy.expected_ports),
        allowed_ports=set(policy.allowed_ports),
        has_baseline=policy.configured,
        critical_ports=set(policy.critical_ports),
    )
    return LanServiceResponse(
        id=item.id,
        lan_asset_id=item.lan_asset_id,
        ip_address=item.ip_address,
        port=item.port,
        protocol=item.protocol,
        service_name=item.service_name,
        service_label=item.service_label,
        confidence=item.confidence,
        banner_hint=item.banner_hint,
        non_standard_ssh=item.non_standard_ssh,
        status=item.status,
        observed_at=item.observed_at,
        first_observed_at=first_observed_at or item.observed_at,
        previous_status=previous_status,
        changed_from_previous=(
            previous_status is not None and previous_status != item.status
        ),
        source=item.source,
        expectation=assessment.expectation,
        advisory_severity=assessment.severity,
        advisory_reason=assessment.reason,
        identification_confidence="high" if item.confidence >= 85 else "medium" if item.confidence >= 60 else "low",
    )


def _service_summary_responses(
    rows: list[LanServiceObservation],
    *, asset: LanAsset | None = None, baseline: LanServiceBaseline | None = None,
) -> list[LanServiceResponse]:
    grouped: dict[tuple[int, str], list[LanServiceObservation]] = {}
    for item in rows:
        grouped.setdefault((item.port, item.protocol), []).append(item)
    summaries = [
        _service_response(
            history[-1],
            first_observed_at=history[0].observed_at,
            previous_status=history[-2].status if len(history) > 1 else None,
            asset=asset, baseline=baseline,
        )
        for history in grouped.values()
    ]
    return sorted(summaries, key=lambda item: (item.port, item.protocol))


def _metric_count(body: LanAgentTelemetryIngest) -> int:
    return sum(
        value is not None
        for value in (
            body.cpu_percent,
            body.memory_percent,
            body.disk_percent,
            body.uptime_seconds,
            body.firewall_status,
            body.antivirus_status,
            body.patch_status,
            body.pending_reboot,
        )
    )


def _ensure_enabled() -> None:
    if not settings.LAN_MONITORING_ENABLED:
        raise LanMonitoringDisabledError


def _is_rfc1918_network(network: ipaddress.IPv4Network) -> bool:
    return any(network.subnet_of(private) for private in RFC1918_NETWORKS)


def _clean(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None
