from __future__ import annotations

import hashlib
import ipaddress
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent_management import (
    AgentEnrollmentToken,
    AssetGroup,
    AssetGroupMembership,
    ExpectedServiceBaseline,
)
from app.models.lan_monitoring import LanAsset, LanServiceObservation
from app.models.user import User
from app.schemas.agent_management import (
    AgentCoverage,
    AgentInventoryItem,
    AgentInventoryResponse,
    AgentUpdate,
    AssetGroupCreate,
    AssetGroupListResponse,
    AssetGroupResponse,
    AssetGroupUpdate,
    EnrollmentTokenCreate,
    EnrollmentTokenCreated,
    EnrollmentTokenListResponse,
    EnrollmentTokenResponse,
    GroupCoverage,
    ServiceBaselineCreate,
    ServiceBaselineIndicator,
    ServiceBaselineListResponse,
    ServiceBaselineResponse,
    ServiceBaselineUpdate,
)
from app.services.audit import record_event
from app.services.lan_monitoring import LanConfigurationError, validate_allowed_cidr
from app.services.notification import create_admin_notification


class AgentManagementNotFoundError(Exception):
    pass


class AgentManagementConflictError(Exception):
    pass


class AgentCredentialError(Exception):
    def __init__(self, reason: str = "invalid") -> None:
        self.reason = reason


def _hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _token_status(item: AgentEnrollmentToken, now: datetime | None = None) -> str:
    current = now or datetime.now(UTC)
    if item.revoked_at:
        return "revoked"
    if item.expires_at <= current:
        return "expired"
    if (
        item.max_enrollments is not None
        and item.enrollment_count >= item.max_enrollments
    ):
        return "exhausted"
    return "active"


def _token_response(item: AgentEnrollmentToken) -> EnrollmentTokenResponse:
    return EnrollmentTokenResponse(
        id=item.id,
        name=item.name,
        description=item.description,
        token_hint=item.token_hint,
        allowed_cidr=item.allowed_cidr,
        max_enrollments=item.max_enrollments,
        enrollment_count=item.enrollment_count,
        expires_at=item.expires_at,
        created_by=item.created_by,
        created_at=item.created_at,
        revoked_at=item.revoked_at,
        status=cast(
            Literal["active", "expired", "revoked", "exhausted"], _token_status(item)
        ),
    )


async def create_enrollment_token(
    db: AsyncSession, user: User, body: EnrollmentTokenCreate
) -> EnrollmentTokenCreated:
    now = datetime.now(UTC)
    expires = (
        body.expires_at
        if body.expires_at.tzinfo
        else body.expires_at.replace(tzinfo=UTC)
    )
    if expires <= now or expires > now + timedelta(days=365):
        raise AgentManagementConflictError("expiration")
    allowed_cidr: str | None = None
    if body.allowed_cidr:
        try:
            network = validate_allowed_cidr(body.allowed_cidr)
        except (ValueError, LanConfigurationError) as exc:
            raise AgentManagementConflictError("cidr") from exc
        allowed_cidr = str(network)
    raw = f"rae_{secrets.token_urlsafe(32)}"
    item = AgentEnrollmentToken(
        name=_required_clean(body.name),
        description=_clean(body.description),
        token_hash=_hash_token(raw),
        token_hint=f"{raw[:7]}…{raw[-4:]}",
        allowed_cidr=allowed_cidr,
        max_enrollments=body.max_enrollments,
        expires_at=expires,
        created_by=user.id,
    )
    db.add(item)
    await db.flush()
    await record_event(
        db,
        action="monitoring.agent_token_created",
        actor_id=user.id,
        resource_type="agent_enrollment_token",
        resource_id=item.id,
        metadata={
            "name": item.name,
            "expires_at": expires.isoformat(),
            "allowed_cidr": allowed_cidr,
        },
    )
    response = _token_response(item).model_dump()
    return EnrollmentTokenCreated(**response, token=raw)


async def list_enrollment_tokens(db: AsyncSession) -> EnrollmentTokenListResponse:
    items = list(
        (
            await db.execute(
                select(AgentEnrollmentToken).order_by(
                    AgentEnrollmentToken.created_at.desc()
                )
            )
        )
        .scalars()
        .all()
    )
    return EnrollmentTokenListResponse(
        total=len(items), items=[_token_response(item) for item in items]
    )


async def revoke_enrollment_token(
    db: AsyncSession, user: User, token_id: uuid.UUID
) -> EnrollmentTokenResponse:
    item = await db.get(AgentEnrollmentToken, token_id)
    if item is None:
        raise AgentManagementNotFoundError
    if item.revoked_at:
        raise AgentManagementConflictError("revoked")
    item.revoked_at = datetime.now(UTC)
    await record_event(
        db,
        action="monitoring.agent_token_revoked",
        actor_id=user.id,
        resource_type="agent_enrollment_token",
        resource_id=item.id,
        metadata={"name": item.name},
    )
    await db.flush()
    return _token_response(item)


async def rotate_enrollment_token(
    db: AsyncSession, user: User, token_id: uuid.UUID
) -> EnrollmentTokenCreated:
    old = await db.get(AgentEnrollmentToken, token_id)
    if old is None:
        raise AgentManagementNotFoundError
    if old.revoked_at:
        raise AgentManagementConflictError("revoked")
    old.revoked_at = datetime.now(UTC)
    replacement = await create_enrollment_token(
        db,
        user,
        EnrollmentTokenCreate(
            name=old.name,
            description=old.description,
            allowed_cidr=old.allowed_cidr,
            max_enrollments=old.max_enrollments,
            expires_at=max(old.expires_at, datetime.now(UTC) + timedelta(days=1)),
        ),
    )
    await record_event(
        db,
        action="monitoring.agent_token_rotated",
        actor_id=user.id,
        resource_type="agent_enrollment_token",
        resource_id=token_id,
        metadata={"replacement_id": str(replacement.id)},
    )
    return replacement


async def validate_agent_credential(
    db: AsyncSession,
    provided: str | None,
    ip_address: str | None = None,
    asset_id: uuid.UUID | None = None,
) -> AgentEnrollmentToken | None:
    if not settings.LAN_MONITORING_ENABLED:
        raise AgentCredentialError("disabled")
    if not provided:
        raise AgentCredentialError
    if settings.LAN_AGENT_TOKEN and secrets.compare_digest(
        provided, settings.LAN_AGENT_TOKEN
    ):
        return None
    item = (
        await db.execute(
            select(AgentEnrollmentToken)
            .where(AgentEnrollmentToken.token_hash == _hash_token(provided))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if item is None:
        raise AgentCredentialError
    state = _token_status(item)
    if state != "active":
        if state == "revoked":
            await create_admin_notification(
                db,
                notification_type="monitoring_alert",
                severity="critical",
                title="Revoked agent token usage attempt",
                message=f"A revoked enrollment credential labeled '{item.name}' was rejected.",
                entity_type="agent_enrollment_token",
                entity_id=item.id,
                action_url="/monitoring",
                metadata={"rule": "revoked_agent_token_attempt"},
                dedupe_key_prefix=f"revoked-agent-token:{item.id}:{datetime.now(UTC).date()}",
            )
            await db.commit()
        raise AgentCredentialError(state)
    if ip_address and item.allowed_cidr:
        try:
            if ipaddress.ip_address(ip_address) not in ipaddress.ip_network(
                item.allowed_cidr
            ):
                raise AgentCredentialError("cidr")
        except ValueError as exc:
            raise AgentCredentialError("cidr") from exc
    if asset_id:
        asset = await db.get(LanAsset, asset_id)
        if asset is None or (
            asset.enrollment_token_id and asset.enrollment_token_id != item.id
        ):
            raise AgentCredentialError
    return item


async def consume_enrollment(item: AgentEnrollmentToken | None) -> None:
    if item is not None:
        item.enrollment_count += 1


async def list_agents(db: AsyncSession) -> AgentInventoryResponse:
    from app.services.lan_monitoring import (
        _asset_response,
        _latest_services,
        _latest_telemetry,
    )

    now = datetime.now(UTC)
    assets = list(
        (
            await db.execute(
                select(LanAsset).order_by(LanAsset.hostname, LanAsset.ip_address)
            )
        )
        .scalars()
        .all()
    )
    telemetry = await _latest_telemetry(db)
    services = await _latest_services(db)
    memberships = list(
        (
            await db.execute(
                select(AssetGroupMembership, AssetGroup).join(
                    AssetGroup, AssetGroup.id == AssetGroupMembership.group_id
                )
            )
        ).all()
    )
    group_map: dict[uuid.UUID, list[AssetGroup]] = {}
    for membership, group in memberships:
        group_map.setdefault(membership.asset_id, []).append(group)
    tokens = {
        item.id: item
        for item in (await db.execute(select(AgentEnrollmentToken))).scalars().all()
    }
    responses = [
        _asset_response(asset, telemetry.get(asset.id), services.get(asset.id, []), now)
        for asset in assets
    ]
    agents: list[AgentInventoryItem] = []
    for asset, response in zip(assets, responses, strict=True):
        if asset.source != "agent":
            continue
        sample = telemetry.get(asset.id)
        groups = group_map.get(asset.id, [])
        token = (
            tokens.get(asset.enrollment_token_id) if asset.enrollment_token_id else None
        )
        agents.append(
            AgentInventoryItem(
                **response.model_dump(),
                os_name=sample.os_name if sample else None,
                os_version=sample.os_version if sample else None,
                agent_version=sample.agent_version if sample else None,
                telemetry_fresh=response.agent_connected,
                enrollment_token_label=token.name if token else "Legacy local token",
                group_ids=[group.id for group in groups],
                group_names=[group.name for group in groups],
            )
        )
    coverage = await _coverage(db, assets, responses, group_map)
    return AgentInventoryResponse(total=len(agents), coverage=coverage, items=agents)


async def get_agent(db: AsyncSession, agent_id: uuid.UUID) -> AgentInventoryItem:
    inventory = await list_agents(db)
    item = next(
        (candidate for candidate in inventory.items if candidate.id == agent_id), None
    )
    if item is None:
        raise AgentManagementNotFoundError
    return item


async def update_agent(
    db: AsyncSession, user: User, agent_id: uuid.UUID, body: AgentUpdate
) -> AgentInventoryItem:
    asset = await db.get(LanAsset, agent_id)
    if asset is None or asset.source != "agent":
        raise AgentManagementNotFoundError
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(asset, key, _clean(value) if isinstance(value, str) else value)
    await record_event(
        db,
        action="monitoring.agent_updated",
        actor_id=user.id,
        resource_type="lan_asset",
        resource_id=asset.id,
        metadata={"fields": sorted(body.model_fields_set)},
    )
    await db.flush()
    await db.refresh(asset)
    return await get_agent(db, agent_id)


async def list_groups(db: AsyncSession) -> AssetGroupListResponse:
    groups = list(
        (await db.execute(select(AssetGroup).order_by(AssetGroup.name))).scalars().all()
    )
    return AssetGroupListResponse(
        total=len(groups), items=[await _group_response(db, item) for item in groups]
    )


async def create_group(
    db: AsyncSession, user: User, body: AssetGroupCreate
) -> AssetGroupResponse:
    if (
        await db.execute(
            select(AssetGroup).where(
                func.lower(AssetGroup.name) == body.name.strip().lower()
            )
        )
    ).scalar_one_or_none():
        raise AgentManagementConflictError("name")
    await _require_assets(db, body.asset_ids)
    item = AssetGroup(
        name=_required_clean(body.name),
        description=_clean(body.description),
        created_by=user.id,
    )
    db.add(item)
    await db.flush()
    db.add_all(
        [
            AssetGroupMembership(asset_id=asset_id, group_id=item.id)
            for asset_id in set(body.asset_ids)
        ]
    )
    await record_event(
        db,
        action="monitoring.asset_group_created",
        actor_id=user.id,
        resource_type="asset_group",
        resource_id=item.id,
        metadata={"asset_count": len(set(body.asset_ids))},
    )
    await db.flush()
    await db.refresh(item)
    return await _group_response(db, item)


async def update_group(
    db: AsyncSession, user: User, group_id: uuid.UUID, body: AssetGroupUpdate
) -> AssetGroupResponse:
    item = await db.get(AssetGroup, group_id)
    if item is None:
        raise AgentManagementNotFoundError
    if body.name is not None:
        duplicate = (
            await db.execute(
                select(AssetGroup).where(
                    func.lower(AssetGroup.name) == body.name.strip().lower(),
                    AssetGroup.id != group_id,
                )
            )
        ).scalar_one_or_none()
        if duplicate:
            raise AgentManagementConflictError("name")
        item.name = _required_clean(body.name)
    if "description" in body.model_fields_set:
        item.description = _clean(body.description)
    if body.asset_ids is not None:
        await _require_assets(db, body.asset_ids)
        await db.execute(
            delete(AssetGroupMembership).where(
                AssetGroupMembership.group_id == group_id
            )
        )
        db.add_all(
            [
                AssetGroupMembership(asset_id=value, group_id=group_id)
                for value in set(body.asset_ids)
            ]
        )
    await record_event(
        db,
        action="monitoring.asset_group_updated",
        actor_id=user.id,
        resource_type="asset_group",
        resource_id=item.id,
        metadata={"fields": sorted(body.model_fields_set)},
    )
    await db.flush()
    await db.refresh(item)
    return await _group_response(db, item)


async def delete_group(db: AsyncSession, user: User, group_id: uuid.UUID) -> None:
    item = await db.get(AssetGroup, group_id)
    if item is None:
        raise AgentManagementNotFoundError
    await record_event(
        db,
        action="monitoring.asset_group_deleted",
        actor_id=user.id,
        resource_type="asset_group",
        resource_id=item.id,
        metadata={"name": item.name},
    )
    await db.delete(item)
    await db.flush()


async def list_baselines(db: AsyncSession) -> ServiceBaselineListResponse:
    items = list(
        (
            await db.execute(
                select(ExpectedServiceBaseline).order_by(ExpectedServiceBaseline.name)
            )
        )
        .scalars()
        .all()
    )
    return ServiceBaselineListResponse(
        total=len(items), items=[await _baseline_response(db, item) for item in items]
    )


async def create_baseline(
    db: AsyncSession, user: User, body: ServiceBaselineCreate
) -> ServiceBaselineResponse:
    await _require_scope(db, body.asset_id, body.group_id)
    item = ExpectedServiceBaseline(
        name=_required_clean(body.name),
        description=_clean(body.description),
        asset_id=body.asset_id,
        group_id=body.group_id,
        expected_ports=body.expected_ports,
        allowed_ports=body.allowed_ports,
        created_by=user.id,
    )
    db.add(item)
    await db.flush()
    await record_event(
        db,
        action="monitoring.service_baseline_created",
        actor_id=user.id,
        resource_type="service_baseline",
        resource_id=item.id,
        metadata={
            "scope": "asset" if item.asset_id else "group",
            "expected_count": len(item.expected_ports),
            "allowed_count": len(item.allowed_ports),
        },
    )
    return await _baseline_response(db, item)


async def update_baseline(
    db: AsyncSession, user: User, baseline_id: uuid.UUID, body: ServiceBaselineUpdate
) -> ServiceBaselineResponse:
    item = await db.get(ExpectedServiceBaseline, baseline_id)
    if item is None:
        raise AgentManagementNotFoundError
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(item, key, _clean(value) if isinstance(value, str) else value)
    await record_event(
        db,
        action="monitoring.service_baseline_updated",
        actor_id=user.id,
        resource_type="service_baseline",
        resource_id=item.id,
        metadata={"fields": sorted(body.model_fields_set)},
    )
    await db.flush()
    await db.refresh(item)
    return await _baseline_response(db, item)


async def delete_baseline(db: AsyncSession, user: User, baseline_id: uuid.UUID) -> None:
    item = await db.get(ExpectedServiceBaseline, baseline_id)
    if item is None:
        raise AgentManagementNotFoundError
    await record_event(
        db,
        action="monitoring.service_baseline_deleted",
        actor_id=user.id,
        resource_type="service_baseline",
        resource_id=item.id,
        metadata={"name": item.name},
    )
    await db.delete(item)
    await db.flush()


async def baseline_alerts(db: AsyncSession):
    from app.schemas.monitoring import MonitoringAlert

    items = (await list_baselines(db)).items
    alerts = []
    expired_tokens = list(
        (
            await db.execute(
                select(AgentEnrollmentToken).where(
                    AgentEnrollmentToken.revoked_at.is_(None),
                    AgentEnrollmentToken.expires_at <= datetime.now(UTC),
                )
            )
        )
        .scalars()
        .all()
    )
    for token in expired_tokens:
        alerts.append(
            MonitoringAlert(
                key=f"coverage:agent-token-expired:{token.id}",
                severity="warning",
                title="Endpoint enrollment token expired",
                message=f"Enrollment token '{token.name}' expired and can no longer enroll agents.",
                category="coverage",
                source="agent_enrollment",
                action_url="/monitoring",
            )
        )
    for baseline in items:
        for indicator in baseline.indicators:
            alerts.append(
                MonitoringAlert(
                    key=f"service-baseline:{baseline.id}:{indicator.asset_id}:{indicator.indicator_type}:{indicator.port}",
                    severity=indicator.severity,
                    title="Expected service baseline changed",
                    message=indicator.detail,
                    category="service_baseline",
                    source="expected_service_baseline",
                    action_url="/monitoring",
                )
            )
    coverage = (await list_agents(db)).coverage
    if coverage.critical_assets_without_telemetry:
        alerts.append(
            MonitoringAlert(
                key="coverage:critical-without-agent",
                severity="critical",
                title="Critical assets lack fresh endpoint telemetry",
                message=f"{coverage.critical_assets_without_telemetry} critical asset(s) need a fresh agent heartbeat.",
                category="coverage",
                action_url="/monitoring",
            )
        )
    for group in coverage.groups:
        fresh = group.monitored_by_agent - group.stale_agents
        if group.total_assets and fresh * 2 < group.total_assets:
            alerts.append(
                MonitoringAlert(
                    key=f"coverage:group:{group.group_id}",
                    severity="warning",
                    title=f"Weak agent coverage in {group.group_name}",
                    message=f"{fresh} of {group.total_assets} assets have fresh endpoint telemetry.",
                    category="coverage",
                    action_url="/monitoring",
                )
            )
    return alerts


async def _baseline_response(
    db: AsyncSession, item: ExpectedServiceBaseline
) -> ServiceBaselineResponse:
    asset_ids = (
        [item.asset_id]
        if item.asset_id
        else list(
            (
                await db.execute(
                    select(AssetGroupMembership.asset_id).where(
                        AssetGroupMembership.group_id == item.group_id
                    )
                )
            )
            .scalars()
            .all()
        )
    )
    indicators: list[ServiceBaselineIndicator] = []
    for asset_id in asset_ids:
        if asset_id is None:
            continue
        latest = await _latest_port_status(db, asset_id)
        open_ports = {port for port, status in latest.items() if status == "open"}
        allowed = set(item.allowed_ports) | set(item.expected_ports)
        asset = await db.get(LanAsset, asset_id)
        for port in sorted(set(item.expected_ports) - open_ports):
            indicators.append(
                ServiceBaselineIndicator(
                    asset_id=asset_id,
                    port=port,
                    indicator_type="missing_expected_service",
                    severity="critical"
                    if asset and asset.criticality == "critical"
                    else "warning",
                    detail=f"Expected TCP/{port} is not currently observed open on {asset.ip_address if asset else 'the asset'}.",
                )
            )
        for port in sorted(open_ports - allowed):
            indicators.append(
                ServiceBaselineIndicator(
                    asset_id=asset_id,
                    port=port,
                    indicator_type="unexpected_open_service",
                    severity="critical"
                    if not asset or not asset.is_authorized
                    else "warning",
                    detail=f"Unexpected TCP/{port} is observed open on {asset.ip_address if asset else 'the asset'}; this is a risk indicator, not exploit validation.",
                )
            )
    return ServiceBaselineResponse(
        id=item.id,
        name=item.name,
        description=item.description,
        asset_id=item.asset_id,
        group_id=item.group_id,
        expected_ports=item.expected_ports,
        allowed_ports=item.allowed_ports,
        indicators=indicators,
        created_by=item.created_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def _latest_port_status(db: AsyncSession, asset_id: uuid.UUID) -> dict[int, str]:
    rows = list(
        (
            await db.execute(
                select(LanServiceObservation)
                .where(LanServiceObservation.lan_asset_id == asset_id)
                .order_by(LanServiceObservation.observed_at.desc())
            )
        )
        .scalars()
        .all()
    )
    result: dict[int, str] = {}
    for row in rows:
        result.setdefault(row.port, row.status)
    return result


async def _coverage(
    db: AsyncSession,
    assets: list[LanAsset],
    responses,
    group_map: dict[uuid.UUID, list[AssetGroup]],
) -> AgentCoverage:
    by_id = {item.id: item for item in responses}
    group_rows = list((await db.execute(select(AssetGroup))).scalars().all())
    groups: list[GroupCoverage] = []
    for group in group_rows:
        members = [asset for asset in assets if group in group_map.get(asset.id, [])]
        groups.append(
            GroupCoverage(
                group_id=group.id,
                group_name=group.name,
                total_assets=len(members),
                monitored_by_agent=sum(
                    1 for asset in members if asset.source == "agent"
                ),
                stale_agents=sum(
                    1
                    for asset in members
                    if asset.source == "agent" and not by_id[asset.id].agent_connected
                ),
                risk_indicators=sum(
                    len(by_id[asset.id].risk_indicators) for asset in members
                ),
            )
        )
    return AgentCoverage(
        total_lan_assets=len(assets),
        monitored_by_agent=sum(1 for asset in assets if asset.source == "agent"),
        missing_agent=sum(1 for asset in assets if asset.source != "agent"),
        stale_agents=sum(
            1
            for asset, item in zip(assets, responses, strict=True)
            if asset.source == "agent" and not item.agent_connected
        ),
        unauthorized_assets=sum(1 for asset in assets if not asset.is_authorized),
        critical_assets_without_telemetry=sum(
            1
            for asset, item in zip(assets, responses, strict=True)
            if asset.criticality == "critical" and not item.agent_connected
        ),
        groups=groups,
    )


async def _group_response(db: AsyncSession, item: AssetGroup) -> AssetGroupResponse:
    ids = list(
        (
            await db.execute(
                select(AssetGroupMembership.asset_id).where(
                    AssetGroupMembership.group_id == item.id
                )
            )
        )
        .scalars()
        .all()
    )
    inventory = await list_agents(db)
    coverage = next(
        (value for value in inventory.coverage.groups if value.group_id == item.id),
        GroupCoverage(
            group_id=item.id,
            group_name=item.name,
            total_assets=0,
            monitored_by_agent=0,
            stale_agents=0,
            risk_indicators=0,
        ),
    )
    return AssetGroupResponse(
        id=item.id,
        name=item.name,
        description=item.description,
        asset_ids=ids,
        total_assets=coverage.total_assets,
        monitored_by_agent=coverage.monitored_by_agent,
        stale_agents=coverage.stale_agents,
        risk_indicators=coverage.risk_indicators,
        created_by=item.created_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def _require_assets(db: AsyncSession, ids: list[uuid.UUID]) -> None:
    if not ids:
        return
    count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(LanAsset)
                .where(LanAsset.id.in_(set(ids)))
            )
        ).scalar_one()
    )
    if count != len(set(ids)):
        raise AgentManagementNotFoundError


async def _require_scope(
    db: AsyncSession, asset_id: uuid.UUID | None, group_id: uuid.UUID | None
) -> None:
    target = (
        await db.get(LanAsset, asset_id)
        if asset_id
        else await db.get(AssetGroup, group_id)
    )
    if target is None:
        raise AgentManagementNotFoundError


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = value.lower()
    if any(
        term in lowered
        for term in (
            "password=",
            "secret=",
            "token=",
            "credential=",
            "api_key=",
            "database_url=",
        )
    ):
        raise AgentManagementConflictError("secret")
    return value.strip() or None


def _required_clean(value: str) -> str:
    cleaned = _clean(value)
    if not cleaned:
        raise AgentManagementConflictError("value")
    return cleaned
