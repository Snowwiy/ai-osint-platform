from __future__ import annotations

import asyncio
import ipaddress
import re
import shutil
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.lan_monitoring import LanAsset, LanAssetTelemetry, LanServiceObservation
from app.models.user import User
from app.schemas.lan_monitoring import (
    LanAgentRegistration,
    LanAgentRegistrationResponse,
    LanAgentTelemetryIngest,
    LanAgentTelemetryResponse,
    LanAssetListResponse,
    LanAssetResponse,
    LanAssetStatus,
    LanAssetUpdate,
    LanDiscoveryObservation,
    LanDiscoveryRequest,
    LanDiscoveryResponse,
    LanRiskIndicator,
    LanRiskSeverity,
    LanServiceInput,
    LanServiceListResponse,
    LanServiceResponse,
    LanTelemetryListResponse,
    LanTelemetryResponse,
)
from app.schemas.monitoring import MonitoringAlert
from app.services.audit import record_event
from app.services.notification import create_admin_notification

RFC1918_NETWORKS: tuple[ipaddress.IPv4Network, ...] = tuple(
    ipaddress.IPv4Network(value)
    for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)
RISKY_PORTS = {
    23: "Telnet",
    445: "SMB",
    3389: "Remote Desktop",
    5900: "VNC",
}
CURRENT_AGENT_VERSION = "1.0.0"


class LanMonitoringDisabledError(Exception):
    pass


class LanConfigurationError(Exception):
    pass


class LanAssetNotFoundError(Exception):
    pass


class LanDiscoveryRateLimitedError(Exception):
    pass


def configured_networks() -> list[ipaddress.IPv4Network]:
    networks: list[ipaddress.IPv4Network] = []
    for value in settings.LAN_ALLOWED_CIDRS.split(","):
        if not value.strip():
            continue
        network = ipaddress.ip_network(value.strip(), strict=False)
        if not isinstance(network, ipaddress.IPv4Network) or not _is_rfc1918_network(network):
            raise LanConfigurationError("Only private RFC1918 IPv4 networks are allowed.")
        networks.append(network)
    if not networks:
        raise LanConfigurationError("No authorized LAN CIDR is configured.")
    return networks


def validate_allowed_cidr(value: str) -> ipaddress.IPv4Network:
    try:
        network = ipaddress.ip_network(value, strict=False)
    except ValueError as exc:
        raise LanConfigurationError("The selected LAN CIDR is invalid.") from exc
    if not isinstance(network, ipaddress.IPv4Network) or not _is_rfc1918_network(network):
        raise LanConfigurationError("The selected CIDR must be private RFC1918 IPv4 space.")
    if network.num_addresses > 256:
        raise LanConfigurationError("Discovery ranges are limited to /24 or smaller.")
    if not any(network.subnet_of(allowed) for allowed in configured_networks()):
        raise LanConfigurationError("The selected CIDR is outside LAN_ALLOWED_CIDRS.")
    return network


def validate_allowed_ip(value: str) -> ipaddress.IPv4Address:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise LanConfigurationError("The LAN asset IP address is invalid.") from exc
    if not isinstance(address, ipaddress.IPv4Address) or not any(
        address in network for network in RFC1918_NETWORKS
    ):
        raise LanConfigurationError("LAN assets must use private RFC1918 IPv4 addresses.")
    if not any(address in network for network in configured_networks()):
        raise LanConfigurationError("The LAN asset IP is outside LAN_ALLOWED_CIDRS.")
    return address


async def list_lan_assets(db: AsyncSession) -> LanAssetListResponse:
    assets = list((await db.execute(select(LanAsset).order_by(LanAsset.ip_address))).scalars().all())
    telemetry = await _latest_telemetry(db)
    services = await _latest_services(db)
    now = datetime.now(UTC)
    items = [_asset_response(item, telemetry.get(item.id), services.get(item.id, []), now) for item in assets]
    return LanAssetListResponse(
        generated_at=now,
        enabled=settings.LAN_MONITORING_ENABLED,
        allowed_cidrs=[str(item) for item in configured_networks()],
        discovery_interval_seconds=settings.LAN_DISCOVERY_INTERVAL_SECONDS,
        ping_enabled=settings.LAN_DISCOVERY_PING_ENABLED,
        service_check_enabled=settings.LAN_SERVICE_CHECK_ENABLED,
        limitation=(
            "The backend container does not receive privileged host neighbor or Docker access. "
            "Use supplied static/router observations or the optional endpoint agent."
        ),
        total=len(items),
        online=sum(item.status == "online" for item in items),
        offline=sum(item.status == "offline" for item in items),
        unauthorized=sum(not item.is_authorized for item in items),
        agent_connected=sum(item.agent_connected for item in items),
        items=items,
    )


async def get_lan_asset(db: AsyncSession, asset_id: uuid.UUID) -> LanAssetResponse:
    asset = await db.get(LanAsset, asset_id)
    if asset is None:
        raise LanAssetNotFoundError
    telemetry = await _latest_telemetry(db, asset_id)
    services = await _latest_services(db, asset_id)
    return _asset_response(asset, telemetry.get(asset.id), services.get(asset.id, []), datetime.now(UTC))


async def update_lan_asset(
    db: AsyncSession, user: User, asset_id: uuid.UUID, body: LanAssetUpdate
) -> LanAssetResponse:
    asset = await db.get(LanAsset, asset_id)
    if asset is None:
        raise LanAssetNotFoundError
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(asset, field, value.strip() if isinstance(value, str) else value)
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
    if not observations:
        observations = _read_container_arp(network)
        if settings.LAN_DISCOVERY_PING_ENABLED:
            observations = _merge_observations(
                observations, await _ping_network(network)
            )
        if settings.LAN_SERVICE_CHECK_ENABLED and observations:
            await _observe_configured_services(observations)
    if any(item.services for item in observations) and not settings.LAN_SERVICE_CHECK_ENABLED:
        raise LanConfigurationError("Service observations require LAN_SERVICE_CHECK_ENABLED=true.")

    created = updated = services_created = 0
    now = datetime.now(UTC)
    for observation in observations:
        address = validate_allowed_ip(observation.ip_address)
        if address not in network:
            raise LanConfigurationError("An observed asset is outside the selected CIDR.")
        asset, was_created = await _upsert_observation(db, user, observation, now)
        created += int(was_created)
        updated += int(not was_created)
        for service in observation.services:
            db.add(_service_observation(asset.id, service, observation.source, now))
            services_created += 1
        if was_created:
            await _notify_new_asset(db, user, asset)

    limitation = None
    if not observations:
        limitation = (
            "No accessible neighbor observations were available inside Docker. "
            "No ping or TCP checks were attempted."
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
            "docker_limited": limitation is not None,
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


async def register_agent(
    db: AsyncSession, body: LanAgentRegistration
) -> LanAgentRegistrationResponse:
    _ensure_enabled()
    address = validate_allowed_ip(body.ip_address)
    now = datetime.now(UTC)
    asset = await _asset_by_ip(db, str(address))
    created = asset is None
    if asset is None:
        asset = LanAsset(
            ip_address=str(address),
            first_seen=now,
            confidence=95,
            source="agent",
        )
        db.add(asset)
    asset.mac_address = body.mac_address or asset.mac_address
    asset.hostname = _clean(body.hostname) or asset.hostname
    asset.asset_type = body.asset_type
    asset.source = "agent"
    asset.status = "online"
    asset.last_seen = now
    asset.last_checked_at = now
    asset.is_authorized = True
    asset.monitoring_enabled = True
    await db.flush()
    await record_event(
        db,
        action="lan.agent.registered",
        resource_type="lan_asset",
        resource_id=asset.id,
        metadata={"created": created, "agent_version": body.agent_version},
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
    if asset is None or asset.source != "agent" or not asset.is_authorized:
        raise LanAssetNotFoundError
    received_at = datetime.now(UTC)
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
        event_metadata=body.metadata,
    )
    db.add(telemetry)
    asset.status = "online"
    asset.last_seen = body.collected_at
    asset.last_checked_at = received_at
    await record_event(
        db,
        action="lan.agent.telemetry_ingested",
        resource_type="lan_asset",
        resource_id=asset.id,
        metadata={"agent_version": body.agent_version, "metric_count": _metric_count(body)},
    )
    await db.flush()
    return LanAgentTelemetryResponse(
        accepted=True,
        asset_id=asset.id,
        received_at=received_at,
        message="Endpoint telemetry accepted.",
    )


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
        ).scalars().all()
    )
    return LanTelemetryListResponse(
        total=len(rows),
        items=[_telemetry_response(item) for item in rows],
    )


async def list_asset_services(
    db: AsyncSession, asset_id: uuid.UUID, limit: int
) -> LanServiceListResponse:
    await _require_asset(db, asset_id)
    rows = list(
        (
            await db.execute(
                select(LanServiceObservation)
                .where(LanServiceObservation.lan_asset_id == asset_id)
                .order_by(LanServiceObservation.observed_at.desc())
                .limit(limit)
            )
        ).scalars().all()
    )
    return LanServiceListResponse(
        total=len(rows),
        service_checks_enabled=settings.LAN_SERVICE_CHECK_ENABLED,
        items=[_service_response(item) for item in rows],
    )


async def get_lan_alerts(db: AsyncSession) -> list[MonitoringAlert]:
    if not settings.LAN_MONITORING_ENABLED:
        return []
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
) -> LanAssetResponse:
    connected = _agent_connected(asset, telemetry, now)
    status = _effective_status(asset, telemetry, now)
    return LanAssetResponse(
        id=asset.id,
        ip_address=asset.ip_address,
        mac_address=asset.mac_address,
        hostname=asset.hostname,
        vendor=asset.vendor,
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
        agent_connected=connected,
        response_latency_ms=asset.response_latency_ms,
        risk_indicators=_risk_indicators(asset, telemetry, services, status, connected),
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


def _risk_indicators(
    asset: LanAsset,
    telemetry: LanAssetTelemetry | None,
    services: list[LanServiceObservation],
    status: str,
    connected: bool,
) -> list[LanRiskIndicator]:
    indicators: list[LanRiskIndicator] = []
    if not asset.is_authorized:
        indicators.append(_indicator("unauthorized", "critical", "Unauthorized asset", "The asset has not been approved by an administrator."))
    if status == "offline" and asset.monitoring_enabled:
        indicators.append(_indicator("offline", "warning", "Asset offline", "No recent authorized observation is available."))
    if asset.source == "agent" and not connected:
        indicators.append(_indicator("agent_stale", "warning", "Agent not reporting", "Endpoint telemetry is missing or stale."))
    if asset.source != "agent" and asset.monitoring_enabled:
        indicators.append(_indicator("unmanaged", "info", "Unmanaged asset", "No endpoint agent is registered for this asset."))
    if telemetry and telemetry.agent_version and telemetry.agent_version != CURRENT_AGENT_VERSION:
        indicators.append(_indicator("agent_version", "warning", "Agent version review", "The reporting agent version differs from the current local script."))
    if telemetry:
        for key, label, value in (("cpu", "CPU pressure", telemetry.cpu_percent), ("memory", "Memory pressure", telemetry.memory_percent), ("disk", "Disk pressure", telemetry.disk_percent)):
            if value is not None and value >= 85:
                indicators.append(_indicator(f"high_{key}", "critical" if value >= 95 else "warning", label, f"Latest reported utilization is {value:.1f}%."))
    for service in services:
        if service.status == "open" and service.port in RISKY_PORTS:
            indicators.append(_indicator(f"risky_service_{service.port}", "warning", "Risky exposed service", f"{RISKY_PORTS[service.port]} on {service.protocol}/{service.port} was observed. This is a risk indicator, not a confirmed vulnerability."))
    if asset.monitoring_enabled and asset.last_seen is None:
        indicators.append(_indicator("coverage", "warning", "Weak monitoring coverage", "The asset has never produced a successful observation."))
    return indicators


def _indicator(
    key: str, severity: LanRiskSeverity, label: str, detail: str
) -> LanRiskIndicator:
    return LanRiskIndicator(key=key, severity=severity, label=label, detail=detail)


async def _upsert_observation(
    db: AsyncSession, user: User, observation: LanDiscoveryObservation, now: datetime
) -> tuple[LanAsset, bool]:
    address = str(validate_allowed_ip(observation.ip_address))
    asset = await _asset_by_ip(db, address)
    created = asset is None
    if asset is None:
        asset = LanAsset(ip_address=address, first_seen=now, created_by=user.id)
        db.add(asset)
    asset.mac_address = observation.mac_address or asset.mac_address
    asset.hostname = _clean(observation.hostname) or asset.hostname
    asset.vendor = _clean(observation.vendor) or asset.vendor
    asset.asset_type = observation.asset_type
    asset.source = observation.source
    asset.status = "online"
    asset.last_seen = now
    asset.last_checked_at = now
    asset.response_latency_ms = observation.latency_ms
    asset.confidence = 80 if observation.source == "router" else 70
    await db.flush()
    return asset, created


def _service_observation(
    asset_id: uuid.UUID, service: LanServiceInput, source: str, now: datetime
) -> LanServiceObservation:
    return LanServiceObservation(
        lan_asset_id=asset_id,
        port=service.port,
        protocol=service.protocol,
        service_name=_clean(service.service_name),
        status=service.status,
        observed_at=now,
        source=source,
    )


async def _latest_telemetry(
    db: AsyncSession, asset_id: uuid.UUID | None = None
) -> dict[uuid.UUID, LanAssetTelemetry]:
    statement = select(LanAssetTelemetry).order_by(LanAssetTelemetry.collected_at.desc())
    if asset_id:
        statement = statement.where(LanAssetTelemetry.lan_asset_id == asset_id)
    rows = list((await db.execute(statement)).scalars().all())
    latest: dict[uuid.UUID, LanAssetTelemetry] = {}
    for row in rows:
        latest.setdefault(row.lan_asset_id, row)
    return latest


async def _latest_services(
    db: AsyncSession, asset_id: uuid.UUID | None = None
) -> dict[uuid.UUID, list[LanServiceObservation]]:
    statement = select(LanServiceObservation).order_by(LanServiceObservation.observed_at.desc())
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
    if asset.source == "agent":
        return "online" if _agent_connected(asset, telemetry, now) else "offline"
    stale_seconds = max(settings.LAN_DISCOVERY_INTERVAL_SECONDS * 2, 600)
    if asset.last_seen and now - asset.last_seen <= timedelta(seconds=stale_seconds):
        return "online"
    return "offline" if asset.last_seen else "unknown"


def _agent_connected(
    asset: LanAsset, telemetry: LanAssetTelemetry | None, now: datetime
) -> bool:
    return bool(
        asset.source == "agent"
        and telemetry
        and now - telemetry.collected_at <= timedelta(minutes=settings.LAN_AGENT_MAX_STALE_MINUTES)
    )


async def _asset_by_ip(db: AsyncSession, ip_address: str) -> LanAsset | None:
    return (await db.execute(select(LanAsset).where(LanAsset.ip_address == ip_address))).scalar_one_or_none()


async def _require_asset(db: AsyncSession, asset_id: uuid.UUID) -> LanAsset:
    asset = await db.get(LanAsset, asset_id)
    if asset is None:
        raise LanAssetNotFoundError
    return asset


async def _enforce_discovery_interval(db: AsyncSession) -> None:
    last = (
        await db.execute(
            select(func.max(AuditLog.created_at)).where(AuditLog.action == "lan.discovery.executed")
        )
    ).scalar_one_or_none()
    if last and datetime.now(UTC) - last < timedelta(seconds=settings.LAN_DISCOVERY_INTERVAL_SECONDS):
        raise LanDiscoveryRateLimitedError


def _read_container_arp(network: ipaddress.IPv4Network) -> list[LanDiscoveryObservation]:
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


async def _ping_network(
    network: ipaddress.IPv4Network,
) -> list[LanDiscoveryObservation]:
    executable = shutil.which("ping")
    if executable is None:
        return []
    semaphore = asyncio.Semaphore(16)

    async def check(address: ipaddress.IPv4Address) -> LanDiscoveryObservation | None:
        async with semaphore:
            try:
                process = await asyncio.create_subprocess_exec(
                    executable,
                    "-c",
                    "1",
                    "-W",
                    "1",
                    str(address),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                output, _ = await asyncio.wait_for(process.communicate(), timeout=2)
            except (OSError, TimeoutError):
                return None
            if process.returncode != 0:
                return None
            match = re.search(rb"time[=<]([0-9.]+)\s*ms", output)
            latency = float(match.group(1)) if match else None
            return LanDiscoveryObservation(
                ip_address=str(address), source="ping", latency_ms=latency
            )

    results = await asyncio.gather(*(check(address) for address in network.hosts()))
    return [item for item in results if item is not None]


async def _observe_configured_services(
    observations: list[LanDiscoveryObservation],
) -> None:
    ports = [
        int(value.strip())
        for value in settings.LAN_SERVICE_CHECK_PORTS.split(",")
        if value.strip()
    ][:32]
    semaphore = asyncio.Semaphore(16)

    async def check(observation: LanDiscoveryObservation, port: int) -> None:
        async with semaphore:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(observation.ip_address, port), timeout=0.5
                )
                del reader
                writer.close()
                await writer.wait_closed()
                observation.services.append(
                    LanServiceInput(port=port, protocol="tcp", status="open")
                )
            except (OSError, TimeoutError):
                return

    await asyncio.gather(
        *(check(observation, port) for observation in observations for port in ports)
    )


def _merge_observations(
    first: list[LanDiscoveryObservation], second: list[LanDiscoveryObservation]
) -> list[LanDiscoveryObservation]:
    merged = {item.ip_address: item for item in first}
    for item in second:
        merged.setdefault(item.ip_address, item)
    return list(merged.values())


async def _notify_new_asset(db: AsyncSession, user: User, asset: LanAsset) -> None:
    await create_admin_notification(
        db,
        notification_type="monitoring_alert",
        severity="warning",
        title="New LAN asset observed",
        message=f"A new private LAN asset at {asset.ip_address} requires authorization review.",
        entity_type="lan_asset",
        actor_user_id=user.id,
        entity_id=asset.id,
        action_url="/monitoring",
        metadata={"rule": "lan_new_asset"},
        dedupe_key_prefix=f"lan:new:{asset.id}",
    )


async def _notify_discovery_limitation(db: AsyncSession, user: User) -> None:
    day = datetime.now(UTC).date().isoformat()
    await create_admin_notification(
        db,
        notification_type="monitoring_alert",
        severity="warning",
        title="LAN discovery is Docker-limited",
        message="The backend container could not access local neighbor observations; no active probes were attempted.",
        entity_type="lan_monitoring",
        actor_user_id=user.id,
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


def _service_response(item: LanServiceObservation) -> LanServiceResponse:
    return LanServiceResponse(
        id=item.id,
        lan_asset_id=item.lan_asset_id,
        port=item.port,
        protocol=item.protocol,
        service_name=item.service_name,
        status=item.status,
        observed_at=item.observed_at,
        source=item.source,
    )


def _metric_count(body: LanAgentTelemetryIngest) -> int:
    return sum(
        value is not None
        for value in (
            body.cpu_percent,
            body.memory_percent,
            body.disk_percent,
            body.uptime_seconds,
        )
    )


def _ensure_enabled() -> None:
    if not settings.LAN_MONITORING_ENABLED:
        raise LanMonitoringDisabledError


def _is_rfc1918_network(network: ipaddress.IPv4Network) -> bool:
    return any(network.subnet_of(private) for private in RFC1918_NETWORKS)


def _clean(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None
