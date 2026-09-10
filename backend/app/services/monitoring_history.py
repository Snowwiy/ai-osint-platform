from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.lan_monitoring import LanAsset, LanAssetTelemetry, LanServiceObservation
from app.models.monitoring_history import (
    MonitoringChangeEvent,
    ServiceObservationHistory,
)
from app.models.monitoring_policy import MonitoringPolicy
from app.models.user import User
from app.schemas.lan_monitoring import LanServiceInput
from app.schemas.monitoring_history import (
    AssetHistoryResponse,
    ChangeSeverity,
    MonitoringChangeAcknowledgeResponse,
    MonitoringChangeListResponse,
    MonitoringChangeOverviewResponse,
    MonitoringChangeResponse,
    ServiceHistoryListResponse,
    ServiceHistoryResponse,
)
from app.services.audit import record_event

ChangeAcknowledgement = Literal["acknowledged", "unacknowledged"]
_FORBIDDEN_METADATA = (
    "password",
    "secret",
    "token",
    "credential",
    "authorization",
    "key",
)


class MonitoringChangeNotFoundError(Exception):
    pass


class MonitoringHistoryAssetNotFoundError(Exception):
    pass


class MonitoringChangeAlreadyAcknowledgedError(Exception):
    pass


async def record_change(
    db: AsyncSession,
    *,
    asset_id: uuid.UUID | None,
    event_type: str,
    severity: ChangeSeverity,
    title: str,
    description: str,
    source: str,
    old_value: str | None = None,
    new_value: str | None = None,
    metadata: dict[str, Any] | None = None,
    detected_at: datetime | None = None,
) -> MonitoringChangeEvent:
    item = MonitoringChangeEvent(
        asset_id=asset_id,
        event_type=event_type[:80],
        severity=severity,
        title=title[:255],
        description=description,
        old_value=_safe_value(old_value),
        new_value=_safe_value(new_value),
        source=source[:80],
        detected_at=detected_at or datetime.now(UTC),
        event_metadata=_safe_metadata(metadata),
    )
    db.add(item)
    await db.flush()
    return item


async def record_service_observation(
    db: AsyncSession,
    *,
    asset: LanAsset,
    observation: LanServiceInput,
    source: str,
    observed_at: datetime,
) -> LanServiceObservation:
    previous = (
        (
            await db.execute(
                select(LanServiceObservation)
                .where(
                    LanServiceObservation.lan_asset_id == asset.id,
                    LanServiceObservation.port == observation.port,
                    LanServiceObservation.protocol == observation.protocol,
                )
                .order_by(LanServiceObservation.observed_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    current = LanServiceObservation(
        lan_asset_id=asset.id,
        ip_address=asset.ip_address,
        port=observation.port,
        protocol=observation.protocol,
        service_name=_safe_value(observation.service_name, 100),
        service_label=_safe_value(observation.service_label, 160),
        confidence=observation.confidence,
        banner_hint=(
            "SSH protocol banner detected"
            if observation.banner_hint == "SSH protocol banner detected"
            else None
        ),
        non_standard_ssh=observation.non_standard_ssh,
        status=observation.status,
        observed_at=observed_at,
        source=source[:40],
    )
    db.add(current)
    db.add(
        ServiceObservationHistory(
            asset_id=asset.id,
            port=observation.port,
            protocol=observation.protocol,
            previous_status=previous.status if previous else None,
            current_status=observation.status,
            service_name=_safe_value(observation.service_name, 100),
            confidence=observation.confidence,
            observed_at=observed_at,
            source=source[:80],
        )
    )
    await _record_service_changes(db, asset, previous, observation, source, observed_at)
    return current


async def record_asset_observation_changes(
    db: AsyncSession,
    *,
    asset: LanAsset,
    created: bool,
    old_status: str | None,
    old_hostname: str | None,
    old_mac: str | None,
    source: str,
    detected_at: datetime,
) -> None:
    if created:
        await record_change(
            db,
            asset_id=asset.id,
            event_type="asset_discovered",
            severity="medium" if not asset.is_authorized else "info",
            title="New LAN asset discovered",
            description="A new asset was recorded inside an approved private LAN range.",
            source=source,
            new_value=asset.ip_address,
            metadata={
                "authorized": asset.is_authorized,
                "risk_indicator": not asset.is_authorized,
            },
            detected_at=detected_at,
        )
    elif old_status == "offline":
        await record_change(
            db,
            asset_id=asset.id,
            event_type="asset_online",
            severity="info",
            title="LAN asset came back online",
            description="An authorized observation resumed for this LAN asset.",
            source=source,
            old_value="offline",
            new_value="online",
            detected_at=detected_at,
        )
    if old_hostname and asset.hostname and old_hostname != asset.hostname:
        await record_change(
            db,
            asset_id=asset.id,
            event_type="hostname_changed",
            severity="low",
            title="LAN asset hostname changed",
            description="The observed hostname changed for this LAN asset.",
            source=source,
            old_value=old_hostname,
            new_value=asset.hostname,
            detected_at=detected_at,
        )
    if old_mac and asset.mac_address and old_mac != asset.mac_address:
        await record_change(
            db,
            asset_id=asset.id,
            event_type="mac_changed",
            severity="medium",
            title="LAN asset MAC address changed",
            description="The observed MAC address changed and should be reviewed.",
            source=source,
            old_value=old_mac,
            new_value=asset.mac_address,
            detected_at=detected_at,
        )


async def record_agent_telemetry_changes(
    db: AsyncSession,
    asset: LanAsset,
    previous: LanAssetTelemetry | None,
    current: LanAssetTelemetry,
) -> None:
    now = datetime.now(UTC)
    if previous and previous.collected_at < now - timedelta(
        minutes=settings.LAN_AGENT_MAX_STALE_MINUTES
    ):
        await record_change(
            db,
            asset_id=asset.id,
            event_type="agent_resumed",
            severity="info",
            title="Endpoint agent resumed reporting",
            description="Fresh authorized endpoint telemetry was received after a stale interval.",
            source="endpoint_agent",
            old_value="stale",
            new_value="reporting",
            detected_at=current.collected_at,
        )
    policies = {
        item.rule_key: item.threshold_value
        for item in (
            await db.execute(
                select(MonitoringPolicy).where(
                    MonitoringPolicy.rule_key.in_(
                        ("cpu_threshold", "memory_threshold", "disk_threshold")
                    )
                )
            )
        )
        .scalars()
        .all()
    }
    for field, rule, label in (
        ("cpu_percent", "cpu_threshold", "CPU"),
        ("memory_percent", "memory_threshold", "Memory"),
        ("disk_percent", "disk_threshold", "Disk"),
    ):
        threshold = float(policies.get(rule) or 90)
        old = getattr(previous, field) if previous else None
        new = getattr(current, field)
        if new is None or old is None:
            continue
        if old < threshold <= new:
            await record_change(
                db,
                asset_id=asset.id,
                event_type=f"{field}_threshold_crossed",
                severity="high",
                title=f"{label} crossed monitoring threshold",
                description=f"Authorized endpoint telemetry crossed the configured {label.lower()} threshold.",
                source="endpoint_agent",
                old_value=f"{old:.1f}%",
                new_value=f"{new:.1f}%",
                metadata={"threshold_percent": threshold},
                detected_at=current.collected_at,
            )
        elif old >= threshold > new:
            await record_change(
                db,
                asset_id=asset.id,
                event_type=f"{field}_threshold_recovered",
                severity="info",
                title=f"{label} returned below monitoring threshold",
                description=f"Authorized endpoint telemetry returned below the configured {label.lower()} threshold.",
                source="endpoint_agent",
                old_value=f"{old:.1f}%",
                new_value=f"{new:.1f}%",
                metadata={"threshold_percent": threshold},
                detected_at=current.collected_at,
            )


async def reconcile_asset_state_changes(db: AsyncSession) -> None:
    now = datetime.now(UTC)
    assets = list(
        (
            await db.execute(
                select(LanAsset).where(
                    LanAsset.is_authorized.is_(True),
                    LanAsset.monitoring_enabled.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    for asset in assets:
        stale_after = timedelta(
            seconds=max(settings.LAN_DISCOVERY_INTERVAL_SECONDS * 2, 600)
        )
        if (
            asset.last_seen
            and asset.last_seen < now - stale_after
            and asset.status != "offline"
        ):
            asset.status = "offline"
            await record_change(
                db,
                asset_id=asset.id,
                event_type="asset_offline",
                severity="critical" if asset.criticality == "critical" else "medium",
                title="LAN asset went offline",
                description="No authorized observation arrived within the configured stale interval.",
                source="monitoring_reconciliation",
                old_value="online",
                new_value="offline",
                detected_at=now,
            )
        if asset.source != "agent":
            continue
        latest = (
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
        if latest and latest.collected_at < now - timedelta(
            minutes=settings.LAN_AGENT_MAX_STALE_MINUTES
        ):
            last_agent_event = (
                await db.execute(
                    select(MonitoringChangeEvent.event_type)
                    .where(
                        MonitoringChangeEvent.asset_id == asset.id,
                        MonitoringChangeEvent.event_type.in_(
                            ("agent_stale", "agent_resumed")
                        ),
                    )
                    .order_by(MonitoringChangeEvent.detected_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if last_agent_event != "agent_stale":
                await record_change(
                    db,
                    asset_id=asset.id,
                    event_type="agent_stale",
                    severity="high",
                    title="Endpoint agent stopped reporting",
                    description="The endpoint agent exceeded the configured stale threshold.",
                    source="monitoring_reconciliation",
                    old_value="reporting",
                    new_value="stale",
                    detected_at=now,
                )


async def list_changes(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    asset_id: uuid.UUID | None = None,
    event_type: str | None = None,
    severity: ChangeSeverity | None = None,
    acknowledgement: ChangeAcknowledgement | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> MonitoringChangeListResponse:
    await reconcile_asset_state_changes(db)
    filters: list[Any] = []
    if asset_id:
        filters.append(MonitoringChangeEvent.asset_id == asset_id)
    if event_type:
        filters.append(MonitoringChangeEvent.event_type == event_type)
    if severity:
        filters.append(MonitoringChangeEvent.severity == severity)
    if acknowledgement == "acknowledged":
        filters.append(MonitoringChangeEvent.acknowledged_at.is_not(None))
    elif acknowledgement == "unacknowledged":
        filters.append(MonitoringChangeEvent.acknowledged_at.is_(None))
    if date_from:
        filters.append(MonitoringChangeEvent.detected_at >= _aware(date_from))
    if date_to:
        filters.append(MonitoringChangeEvent.detected_at <= _aware(date_to))
    total = int(
        (
            await db.execute(
                select(func.count()).select_from(MonitoringChangeEvent).where(*filters)
            )
        ).scalar_one()
    )
    rows = list(
        (
            await db.execute(
                select(MonitoringChangeEvent)
                .where(*filters)
                .order_by(MonitoringChangeEvent.detected_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return MonitoringChangeListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_change_response(item) for item in rows],
    )


async def changes_overview(db: AsyncSession) -> MonitoringChangeOverviewResponse:
    await reconcile_asset_state_changes(db)
    rows = list((await db.execute(select(MonitoringChangeEvent))).scalars().all())
    return MonitoringChangeOverviewResponse(
        total=len(rows),
        unacknowledged=sum(item.acknowledged_at is None for item in rows),
        critical=sum(item.severity == "critical" for item in rows),
        high=sum(item.severity == "high" for item in rows),
        new_assets=sum(item.event_type == "asset_discovered" for item in rows),
        port_changes=sum(
            item.event_type
            in {
                "port_opened",
                "port_closed",
                "service_changed",
                "ssh_detected",
                "ssh_nonstandard_detected",
            }
            for item in rows
        ),
        agent_changes=sum(
            item.event_type in {"agent_stale", "agent_resumed"} for item in rows
        ),
        baseline_changes=sum(
            item.event_type in {"baseline_finding_opened", "baseline_finding_resolved"}
            for item in rows
        ),
    )


async def acknowledge_change(
    db: AsyncSession, user: User, change_id: uuid.UUID
) -> MonitoringChangeAcknowledgeResponse:
    item = await db.get(MonitoringChangeEvent, change_id)
    if item is None:
        raise MonitoringChangeNotFoundError
    if item.acknowledged_at is not None:
        raise MonitoringChangeAlreadyAcknowledgedError
    item.acknowledged_at = datetime.now(UTC)
    await record_event(
        db,
        action="monitoring.change_acknowledged",
        actor_id=user.id,
        resource_type="monitoring_change",
        resource_id=item.id,
        metadata={"event_type": item.event_type},
    )
    await db.flush()
    return MonitoringChangeAcknowledgeResponse(
        id=item.id, acknowledged_at=item.acknowledged_at
    )


async def asset_history(
    db: AsyncSession, asset_id: uuid.UUID, limit: int, offset: int
) -> AssetHistoryResponse:
    if await db.get(LanAsset, asset_id) is None:
        raise MonitoringHistoryAssetNotFoundError
    changes = await list_changes(db, limit=limit, offset=offset, asset_id=asset_id)
    rows = list(
        (
            await db.execute(
                select(LanAssetTelemetry)
                .where(LanAssetTelemetry.lan_asset_id == asset_id)
                .order_by(LanAssetTelemetry.collected_at.desc())
            )
        )
        .scalars()
        .all()
    )
    latest = rows[0] if rows else None
    return AssetHistoryResponse(
        asset_id=asset_id,
        changes=changes,
        telemetry_samples=len(rows),
        telemetry_first_at=rows[-1].collected_at if rows else None,
        telemetry_last_at=latest.collected_at if latest else None,
        latest_cpu_percent=latest.cpu_percent if latest else None,
        latest_memory_percent=latest.memory_percent if latest else None,
        latest_disk_percent=latest.disk_percent if latest else None,
    )


async def service_history(
    db: AsyncSession, asset_id: uuid.UUID, limit: int, offset: int
) -> ServiceHistoryListResponse:
    if await db.get(LanAsset, asset_id) is None:
        raise MonitoringHistoryAssetNotFoundError
    predicate = ServiceObservationHistory.asset_id == asset_id
    total = int(
        (
            await db.execute(
                select(func.count())
                .select_from(ServiceObservationHistory)
                .where(predicate)
            )
        ).scalar_one()
    )
    rows = list(
        (
            await db.execute(
                select(ServiceObservationHistory)
                .where(predicate)
                .order_by(ServiceObservationHistory.observed_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return ServiceHistoryListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[ServiceHistoryResponse.model_validate(item) for item in rows],
    )


async def _record_service_changes(
    db: AsyncSession,
    asset: LanAsset,
    previous: LanServiceObservation | None,
    current: LanServiceInput,
    source: str,
    observed_at: datetime,
) -> None:
    old_status = previous.status if previous else None
    if current.status == "open" and old_status != "open":
        risky = (
            current.port in {23, 445, 3389, 5432, 5900, 6379}
            or current.non_standard_ssh
        )
        await record_change(
            db,
            asset_id=asset.id,
            event_type="port_opened",
            severity="high" if risky else "medium",
            title="New open TCP port observed",
            description="An authorized TCP connect observation found a newly open port.",
            source=source,
            old_value=old_status,
            new_value=f"{current.port}/tcp open",
            metadata={
                "port": current.port,
                "service_name": current.service_name,
                "risk_indicator": risky,
            },
            detected_at=observed_at,
        )
    elif old_status == "open" and current.status != "open":
        await record_change(
            db,
            asset_id=asset.id,
            event_type="port_closed",
            severity="info",
            title="Previously open TCP port closed",
            description="A current authorized observation no longer found the port open.",
            source=source,
            old_value=f"{current.port}/tcp open",
            new_value=current.status,
            metadata={"port": current.port},
            detected_at=observed_at,
        )
    if previous and previous.service_name != current.service_name:
        await record_change(
            db,
            asset_id=asset.id,
            event_type="service_changed",
            severity="medium",
            title="Service guess changed",
            description="The bounded service classification changed for an observed TCP port.",
            source=source,
            old_value=previous.service_name,
            new_value=current.service_name,
            metadata={"port": current.port, "confidence": current.confidence},
            detected_at=observed_at,
        )
    if (
        current.status == "open"
        and current.non_standard_ssh
        and not (previous and previous.status == "open" and previous.non_standard_ssh)
    ):
        await record_change(
            db,
            asset_id=asset.id,
            event_type="ssh_nonstandard_detected",
            severity="high",
            title="SSH detected on a non-standard port",
            description="A minimal protocol banner identified possible SSH on an approved non-standard port; no authentication was attempted.",
            source=source,
            new_value=f"{current.port}/tcp ssh",
            metadata={
                "port": current.port,
                "confidence": current.confidence,
                "risk_indicator": True,
            },
            detected_at=observed_at,
        )
    elif (
        current.status == "open"
        and current.service_name == "ssh"
        and not (
            previous and previous.status == "open" and previous.service_name == "ssh"
        )
    ):
        await record_change(
            db,
            asset_id=asset.id,
            event_type="ssh_detected",
            severity="medium",
            title="SSH detected on an observed port",
            description="A bounded service observation identified possible SSH; no authentication was attempted.",
            source=source,
            new_value=f"{current.port}/tcp ssh",
            metadata={"port": current.port, "confidence": current.confidence},
            detected_at=observed_at,
        )


def _change_response(item: MonitoringChangeEvent) -> MonitoringChangeResponse:
    return MonitoringChangeResponse.model_validate(item)


def _safe_value(value: str | None, limit: int = 255) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if any(term in cleaned.lower() for term in _FORBIDDEN_METADATA):
        return "[redacted]"
    return cleaned[:limit]


def _safe_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
    if not value:
        return {}
    safe: dict[str, Any] = {}
    for key, item in list(value.items())[:16]:
        if any(term in key.lower() for term in _FORBIDDEN_METADATA):
            continue
        if isinstance(item, (str, int, float, bool)) or item is None:
            safe[key[:80]] = item[:255] if isinstance(item, str) else item
    return safe


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
