from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.endpoint_posture import (
    EndpointRemediationRecommendation,
    EndpointSecurityPosture,
)
from app.models.lan_monitoring import (
    LanAsset,
    LanAssetTelemetry,
    LanServiceObservation,
    VulnerabilityBaselineFinding,
)
from app.models.user import User
from app.schemas.endpoint_posture import (
    EndpointPostureOverviewResponse,
    EndpointRecommendationAction,
    EndpointRecommendationListResponse,
    EndpointRecommendationResponse,
    EndpointRecommendationUpdate,
    EndpointSecurityPostureResponse,
    EvidenceConfidence,
    PostureStatus,
    RecommendationSeverity,
    RecommendationStatus,
)
from app.services.agent_management import list_baselines
from app.services.audit import record_event

ACTIVE_FINDING_STATUSES = {"open", "acknowledged", "in_progress"}
ACTIVE_RECOMMENDATION_STATUSES = {"open", "acknowledged"}
RISKY_PORTS = {3389: "RDP", 445: "SMB", 5432: "PostgreSQL", 6379: "Redis"}


class EndpointPostureNotFoundError(Exception):
    pass


class EndpointRecommendationNotFoundError(Exception):
    pass


class EndpointRecommendationConflictError(Exception):
    pass


@dataclass(frozen=True)
class RecommendationSpec:
    key: str
    title: str
    severity: RecommendationSeverity
    reason: str
    action: str
    steps: list[str]
    isolation: bool
    source: str
    confidence: EvidenceConfidence
    metadata: dict[str, Any]


async def assess_asset_posture(
    db: AsyncSession, user: User, asset_id: uuid.UUID
) -> EndpointSecurityPostureResponse:
    asset = await db.get(LanAsset, asset_id)
    if asset is None:
        raise EndpointPostureNotFoundError
    telemetry_rows = list(
        (
            await db.execute(
                select(LanAssetTelemetry)
                .where(LanAssetTelemetry.lan_asset_id == asset_id)
                .order_by(LanAssetTelemetry.collected_at.desc())
                .limit(3)
            )
        )
        .scalars()
        .all()
    )
    latest = telemetry_rows[0] if telemetry_rows else None
    services = await _latest_services(db, asset_id)
    specs = await _recommendation_specs(db, asset, telemetry_rows, services)
    recommendations = await _sync_recommendations(db, asset, specs)
    score, posture_status = _score(asset, telemetry_rows, services, specs)
    metadata = _posture_metadata(latest, services)
    values = {
        "posture_score": score,
        "posture_status": posture_status,
        "firewall_status": _metadata_status(latest, "firewall_status"),
        "antivirus_status": _metadata_status(latest, "antivirus_status"),
        "patch_status": _metadata_status(latest, "patch_status"),
        "pending_reboot": _metadata_bool(latest, "pending_reboot"),
        "os_name": latest.os_name if latest else None,
        "os_version": _os_version(latest),
        "disk_health": _disk_health(latest),
        "agent_freshness": _agent_freshness(latest),
        "risky_services_count": _risky_service_count(services, latest),
        "recommendation_count": sum(
            item.status in ACTIVE_RECOMMENDATION_STATUSES for item in recommendations
        ),
        "assessed_at": datetime.now(UTC),
        "event_metadata": metadata,
    }
    posture = (
        await db.execute(
            select(EndpointSecurityPosture).where(
                EndpointSecurityPosture.lan_asset_id == asset_id
            )
        )
    ).scalar_one_or_none()
    if posture is None:
        posture = EndpointSecurityPosture(lan_asset_id=asset_id, **values)
        db.add(posture)
    else:
        for key, value in values.items():
            setattr(posture, key, value)
    await db.flush()
    await record_event(
        db,
        action="monitoring.endpoint_posture_assessed",
        actor_id=user.id,
        resource_type="lan_asset",
        resource_id=asset.id,
        metadata={
            "posture_status": posture_status,
            "posture_score": score,
            "recommendation_count": values["recommendation_count"],
        },
    )
    return _posture_response(posture, asset)


async def assess_all_postures(
    db: AsyncSession, user: User
) -> list[EndpointSecurityPostureResponse]:
    assets = list(
        (await db.execute(select(LanAsset).order_by(LanAsset.ip_address).limit(1000)))
        .scalars()
        .all()
    )
    return [await assess_asset_posture(db, user, asset.id) for asset in assets]


async def get_asset_posture(
    db: AsyncSession, asset_id: uuid.UUID
) -> EndpointSecurityPostureResponse:
    asset = await db.get(LanAsset, asset_id)
    if asset is None:
        raise EndpointPostureNotFoundError
    posture = (
        await db.execute(
            select(EndpointSecurityPosture).where(
                EndpointSecurityPosture.lan_asset_id == asset_id
            )
        )
    ).scalar_one_or_none()
    if posture is None:
        raise EndpointPostureNotFoundError
    return _posture_response(posture, asset)


async def get_posture_overview(
    db: AsyncSession, user: User, *, refresh: bool = False
) -> EndpointPostureOverviewResponse:
    if refresh:
        items = await assess_all_postures(db, user)
    else:
        rows = list(
            (
                await db.execute(
                    select(EndpointSecurityPosture, LanAsset)
                    .join(LanAsset, LanAsset.id == EndpointSecurityPosture.lan_asset_id)
                    .order_by(EndpointSecurityPosture.assessed_at.desc())
                    .limit(1000)
                )
            ).all()
        )
        items = [_posture_response(posture, asset) for posture, asset in rows]
    total_assets = int(
        (await db.execute(select(func.count()).select_from(LanAsset))).scalar_one()
    )
    active_recommendations = list(
        (
            await db.execute(
                select(EndpointRemediationRecommendation).where(
                    EndpointRemediationRecommendation.status.in_(
                        ACTIVE_RECOMMENDATION_STATUSES
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    action_counts = Counter(item.recommended_action for item in active_recommendations)
    return EndpointPostureOverviewResponse(
        generated_at=datetime.now(UTC),
        total_assets=total_assets,
        assessed_assets=len(items),
        healthy=sum(item.posture_status == "healthy" for item in items),
        needs_review=sum(item.posture_status == "needs_review" for item in items),
        at_risk=sum(item.posture_status == "at_risk" for item in items),
        critical=sum(item.posture_status == "critical" for item in items),
        unknown=sum(item.posture_status == "unknown" for item in items),
        firewall_covered=sum(
            item.firewall_status in {"enabled", "disabled"} for item in items
        ),
        antivirus_covered=sum(
            item.antivirus_status in {"enabled", "disabled"} for item in items
        ),
        patch_covered=sum(item.patch_status in {"current", "stale"} for item in items),
        unauthorized_assets=sum(not item.asset_authorized for item in items),
        open_recommendations=len(active_recommendations),
        isolation_recommendations=sum(
            item.isolation_recommended for item in active_recommendations
        ),
        top_actions=[item for item, _count in action_counts.most_common(5)],
        items=items,
        advisory="Posture results are defensive risk indicators based on stored local observations; no exploit validation is performed.",
    )


async def list_recommendations(
    db: AsyncSession,
    *,
    status: RecommendationStatus | None,
    severity: RecommendationSeverity | None,
    asset_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> EndpointRecommendationListResponse:
    filters = []
    if status:
        filters.append(EndpointRemediationRecommendation.status == status)
    if severity:
        filters.append(EndpointRemediationRecommendation.severity == severity)
    if asset_id:
        filters.append(EndpointRemediationRecommendation.lan_asset_id == asset_id)
    count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(EndpointRemediationRecommendation)
                .where(*filters)
            )
        ).scalar_one()
    )
    rows = list(
        (
            await db.execute(
                select(EndpointRemediationRecommendation, LanAsset)
                .join(
                    LanAsset,
                    LanAsset.id == EndpointRemediationRecommendation.lan_asset_id,
                )
                .where(*filters)
                .order_by(EndpointRemediationRecommendation.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    return EndpointRecommendationListResponse(
        total=count,
        limit=limit,
        offset=offset,
        items=[_recommendation_response(item, asset) for item, asset in rows],
    )


async def update_recommendation(
    db: AsyncSession,
    user: User,
    recommendation_id: uuid.UUID,
    body: EndpointRecommendationUpdate,
) -> EndpointRecommendationResponse:
    item, asset = await _recommendation(db, recommendation_id)
    if body.severity is not None:
        item.severity = body.severity
    if "notes" in body.model_fields_set:
        item.notes = body.notes
    await db.flush()
    await db.refresh(item)
    await _audit_recommendation(
        db, user, item, "monitoring.endpoint_recommendation_updated"
    )
    return _recommendation_response(item, asset)


async def acknowledge_recommendation(
    db: AsyncSession,
    user: User,
    recommendation_id: uuid.UUID,
    body: EndpointRecommendationAction,
) -> EndpointRecommendationResponse:
    item, asset = await _recommendation(db, recommendation_id)
    if item.status != "open":
        raise EndpointRecommendationConflictError
    item.status = "acknowledged"
    item.acknowledged_at = datetime.now(UTC)
    if body.notes is not None:
        item.notes = body.notes
    await db.flush()
    await db.refresh(item)
    await _audit_recommendation(
        db, user, item, "monitoring.endpoint_recommendation_acknowledged"
    )
    return _recommendation_response(item, asset)


async def resolve_recommendation(
    db: AsyncSession,
    user: User,
    recommendation_id: uuid.UUID,
    body: EndpointRecommendationAction,
) -> EndpointRecommendationResponse:
    item, asset = await _recommendation(db, recommendation_id)
    if item.status == "resolved":
        raise EndpointRecommendationConflictError
    item.status = "resolved"
    item.resolved_at = datetime.now(UTC)
    if body.notes is not None:
        item.notes = body.notes
    await db.flush()
    await db.refresh(item)
    await _audit_recommendation(
        db, user, item, "monitoring.endpoint_recommendation_resolved"
    )
    return _recommendation_response(item, asset)


async def posture_alerts(db: AsyncSession) -> list[Any]:
    from app.schemas.monitoring import MonitoringAlert

    rows = list(
        (
            await db.execute(
                select(EndpointRemediationRecommendation).where(
                    EndpointRemediationRecommendation.status.in_(
                        ACTIVE_RECOMMENDATION_STATUSES
                    ),
                    EndpointRemediationRecommendation.severity.in_(
                        ("high", "critical")
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    return [
        MonitoringAlert(
            key=f"posture:{item.dedupe_key}",
            severity="critical" if item.severity == "critical" else "warning",
            title=item.title,
            message=f"{item.reason} This is an advisory risk indicator.",
            category="endpoint_posture",
            source="endpoint_posture",
            action_url="/monitoring",
        )
        for item in rows
    ]


async def _recommendation_specs(
    db: AsyncSession,
    asset: LanAsset,
    telemetry_rows: list[LanAssetTelemetry],
    services: dict[int, LanServiceObservation],
) -> list[RecommendationSpec]:
    latest = telemetry_rows[0] if telemetry_rows else None
    specs: list[RecommendationSpec] = []

    def add(
        key: str,
        title: str,
        severity: RecommendationSeverity,
        reason: str,
        action: str,
        steps: list[str],
        source: str,
        confidence: EvidenceConfidence = "high",
        isolation: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        specs.append(
            RecommendationSpec(
                key=key,
                title=title,
                severity=severity,
                reason=reason,
                action=action,
                steps=steps,
                isolation=isolation,
                source=source,
                confidence=confidence,
                metadata=metadata or {},
            )
        )

    if not asset.is_authorized:
        add(
            "unauthorized_asset",
            "Review and isolate unknown asset",
            "critical" if asset.criticality == "critical" else "high",
            f"Asset {asset.ip_address} is present in local inventory without recorded authorization.",
            "Validate ownership and authorization; isolate manually if it is not approved.",
            [
                "Confirm the IP, hostname, and MAC with the asset owner.",
                "Review the approved asset register and change records.",
                "If unapproved, use an authorized router block or quarantine VLAN manually.",
                "Document the decision and monitor for recurrence.",
            ],
            "lan_inventory",
            isolation=True,
        )
    freshness = _agent_freshness(latest)
    if asset.criticality == "critical" and freshness == "missing":
        add(
            "critical_without_agent",
            "Add endpoint coverage to critical asset",
            "critical",
            "A critical asset has no enrolled endpoint telemetry.",
            "Enroll and manually run the approved local endpoint agent.",
            [
                "Confirm owner approval.",
                "Create a short-lived enrollment token.",
                "Run the helper manually and verify a fresh heartbeat.",
            ],
            "coverage",
        )
    elif freshness == "stale":
        add(
            "stale_agent",
            "Restore endpoint-agent reporting",
            "high" if asset.criticality == "critical" else "medium",
            "The endpoint agent has stopped reporting within the configured freshness window.",
            "Check backend reachability and restart the helper manually.",
            [
                "Verify local backend health.",
                "Confirm the enrollment credential remains active.",
                "Restart the agent manually; do not add persistence.",
            ],
            "endpoint_agent",
        )
    firewall = _metadata_status(latest, "firewall_status")
    if firewall == "disabled":
        add(
            "firewall_disabled",
            "Enable endpoint firewall",
            "high",
            "The endpoint agent reported a disabled firewall profile.",
            "Review approved firewall policy and enable the required profiles manually.",
            [
                "Confirm the observation locally.",
                "Review required inbound services.",
                "Enable the approved firewall profiles and reassess.",
            ],
            "endpoint_agent",
        )
    antivirus = _metadata_status(latest, "antivirus_status")
    if antivirus == "disabled":
        add(
            "antivirus_disabled",
            "Restore antivirus protection",
            "high",
            "The endpoint agent reported antivirus or Defender protection disabled.",
            "Restore the organization-approved endpoint protection manually.",
            [
                "Confirm the endpoint protection state locally.",
                "Review security policy and health events.",
                "Enable or repair approved protection, then reassess.",
            ],
            "endpoint_agent",
        )
    elif latest and antivirus in {None, "unknown", "unavailable"}:
        add(
            "antivirus_unknown",
            "Verify endpoint protection status",
            "low",
            "Endpoint protection status could not be confirmed.",
            "Verify the approved antivirus or Defender product locally.",
            [
                "Check the approved protection console or local status.",
                "Document the product and health state.",
                "Reassess after safe agent visibility is available.",
            ],
            "endpoint_agent",
            "low",
        )
    patch = _metadata_status(latest, "patch_status")
    if latest and patch in {"stale", "unknown", "unavailable", None}:
        add(
            "patch_stale" if patch == "stale" else "patch_unknown",
            "Review endpoint patch posture",
            "medium" if patch == "stale" else "low",
            "Recent patch status is stale or could not be confirmed.",
            "Review approved patch tooling and schedule updates through normal change control.",
            [
                "Check the endpoint's approved update source.",
                "Review recent security update history.",
                "Schedule updates and a reboot through change control if required.",
            ],
            "endpoint_agent",
            "medium" if patch == "stale" else "low",
        )
    if _metadata_bool(latest, "pending_reboot"):
        add(
            "pending_reboot",
            "Schedule pending reboot",
            "medium",
            "The endpoint reported a pending reboot that may delay completed updates.",
            "Schedule a controlled reboot in an approved maintenance window.",
            [
                "Confirm active work and service dependencies.",
                "Create or verify a maintenance window.",
                "Reboot manually and confirm agent recovery.",
            ],
            "endpoint_agent",
        )
    if latest and latest.disk_percent is not None and latest.disk_percent >= 90:
        add(
            "disk_pressure",
            "Reduce disk pressure",
            "high",
            f"Disk usage is {latest.disk_percent:.1f}%.",
            "Review safe storage usage and free capacity through approved operations procedures.",
            [
                "Confirm the affected volume locally.",
                "Identify approved cleanup or capacity actions without collecting files into RavenTech.",
                "Reassess after remediation.",
            ],
            "endpoint_agent",
        )
    for metric, label in (("cpu_percent", "CPU"), ("memory_percent", "memory")):
        values = [getattr(item, metric) for item in telemetry_rows]
        if len(values) >= 3 and all(
            value is not None and value >= 90 for value in values
        ):
            add(
                f"sustained_{metric}",
                f"Review sustained {label} pressure",
                "medium",
                f"Three recent endpoint samples report {label} at or above 90%.",
                "Review workload and capacity through approved local operations.",
                [
                    "Confirm the process or workload locally.",
                    "Review expected capacity and recent changes.",
                    "Apply an approved remediation and reassess.",
                ],
                "endpoint_agent",
            )

    open_ports = {port for port, item in services.items() if item.status == "open"}
    open_ports.update(_metadata_ports(latest))
    for port, service_name in RISKY_PORTS.items():
        if port not in open_ports:
            continue
        if port in {3389, 445} and asset.is_authorized:
            continue
        add(
            f"risky_service_{port}",
            f"Review exposed {service_name} service",
            "critical" if not asset.is_authorized else "high",
            f"TCP/{port} ({service_name}) is observed listening; this is a risk indicator, not proof of exploitation.",
            "Confirm business need and restrict network exposure manually.",
            [
                "Validate the service owner and purpose.",
                "Restrict access with an approved host firewall, VLAN, or router policy.",
                "Recheck the authorized observation after change control.",
            ],
            "service_observation",
            isolation=not asset.is_authorized,
            metadata={"port": port, "service": service_name},
        )
    for port, observation in services.items():
        if observation.status == "open" and observation.non_standard_ssh:
            add(
                f"nonstandard_ssh_{port}",
                "Review SSH on non-standard port",
                "medium",
                f"A sanitized SSH protocol hint was observed on TCP/{port}.",
                "Confirm the approved management port and restrict administrative access.",
                [
                    "Validate the service with the asset owner.",
                    "Limit source networks using approved firewall policy.",
                    "Document the non-standard port and monitor changes.",
                ],
                "service_observation",
                metadata={"port": port},
            )
    if (
        services.get(80)
        and services[80].status == "open"
        and services.get(443)
        and services[443].status != "open"
    ):
        add(
            "http_without_https",
            "Review HTTP without observed HTTPS",
            "medium",
            "TCP/80 is open while the checked TCP/443 state is not open.",
            "Confirm whether transport encryption is required and configure HTTPS through approved change control.",
            [
                "Validate the application and data sensitivity.",
                "Configure an approved certificate and HTTPS listener if required.",
                "Redirect HTTP only after functional testing.",
            ],
            "service_observation",
            "medium",
        )

    findings = list(
        (
            await db.execute(
                select(VulnerabilityBaselineFinding).where(
                    VulnerabilityBaselineFinding.lan_asset_id == asset.id,
                    VulnerabilityBaselineFinding.status.in_(ACTIVE_FINDING_STATUSES),
                )
            )
        )
        .scalars()
        .all()
    )
    for finding in findings:
        if finding.remediation_owner and finding.remediation_due_date:
            continue
        add(
            f"baseline_governance_{finding.id}",
            "Assign baseline remediation ownership",
            "high" if finding.severity in {"high", "critical"} else "medium",
            f"Baseline risk indicator '{finding.title}' lacks an owner or due date.",
            "Assign a responsible owner and realistic remediation due date.",
            [
                "Review the advisory evidence with the asset owner.",
                "Assign remediation ownership.",
                "Set a due date and track validation.",
            ],
            "vulnerability_baseline",
            cast(EvidenceConfidence, finding.confidence),
            metadata={"finding_id": str(finding.id)},
        )

    for baseline in (await list_baselines(db)).items:
        for indicator in baseline.indicators:
            if indicator.asset_id != asset.id:
                continue
            title = (
                "Restore expected endpoint service"
                if indicator.indicator_type == "missing_expected_service"
                else "Review unexpected endpoint service"
            )
            add(
                f"service_baseline_{baseline.id}_{indicator.indicator_type}_{indicator.port}",
                title,
                "high" if indicator.severity == "critical" else "medium",
                indicator.detail,
                "Confirm the approved service baseline and remediate the difference manually.",
                [
                    "Validate the expected-service baseline with the owner.",
                    "Confirm the current listening service locally.",
                    "Restore or restrict the service through approved change control.",
                ],
                "expected_service_baseline",
                metadata={"port": indicator.port},
            )
    return specs


async def _sync_recommendations(
    db: AsyncSession, asset: LanAsset, specs: list[RecommendationSpec]
) -> list[EndpointRemediationRecommendation]:
    prefix = f"endpoint-posture:{asset.id}:"
    existing = list(
        (
            await db.execute(
                select(EndpointRemediationRecommendation).where(
                    EndpointRemediationRecommendation.lan_asset_id == asset.id
                )
            )
        )
        .scalars()
        .all()
    )
    by_key = {item.dedupe_key: item for item in existing}
    active_keys: set[str] = set()
    now = datetime.now(UTC)
    for spec in specs:
        key = f"{prefix}{spec.key}"
        active_keys.add(key)
        item = by_key.get(key)
        values = {
            "title": spec.title,
            "severity": spec.severity,
            "reason": spec.reason,
            "recommended_action": spec.action,
            "manual_steps": spec.steps,
            "isolation_recommended": spec.isolation,
            "evidence_source": spec.source,
            "confidence": spec.confidence,
            "event_metadata": _safe_metadata(spec.metadata),
        }
        if item is None:
            item = EndpointRemediationRecommendation(
                lan_asset_id=asset.id, dedupe_key=key, **values
            )
            db.add(item)
            existing.append(item)
        else:
            for field, value in values.items():
                setattr(item, field, value)
            if item.status == "resolved":
                item.status = "open"
                item.resolved_at = None
    for item in existing:
        if (
            item.dedupe_key.startswith(prefix)
            and item.dedupe_key not in active_keys
            and item.status != "resolved"
        ):
            item.status = "resolved"
            item.resolved_at = now
    await db.flush()
    return existing


async def _latest_services(
    db: AsyncSession, asset_id: uuid.UUID
) -> dict[int, LanServiceObservation]:
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
    result: dict[int, LanServiceObservation] = {}
    for row in rows:
        result.setdefault(row.port, row)
    return result


def _score(
    asset: LanAsset,
    telemetry: list[LanAssetTelemetry],
    services: dict[int, LanServiceObservation],
    specs: list[RecommendationSpec],
) -> tuple[int, PostureStatus]:
    if (
        not telemetry
        and not services
        and asset.is_authorized
        and asset.criticality != "critical"
    ):
        return 0, "unknown"
    weights = {"info": 1, "low": 4, "medium": 10, "high": 20, "critical": 35}
    score = max(0, 100 - sum(weights[item.severity] for item in specs))
    if not asset.is_authorized:
        score = min(score, 30 if asset.criticality == "critical" else 60)
    if score >= 85:
        status: PostureStatus = "healthy"
    elif score >= 65:
        status = "needs_review"
    elif score >= 35:
        status = "at_risk"
    else:
        status = "critical"
    return score, status


def _posture_response(
    item: EndpointSecurityPosture, asset: LanAsset
) -> EndpointSecurityPostureResponse:
    return EndpointSecurityPostureResponse(
        id=item.id,
        lan_asset_id=item.lan_asset_id,
        asset_ip=asset.ip_address,
        asset_hostname=asset.hostname,
        asset_authorized=asset.is_authorized,
        asset_criticality=asset.criticality,
        posture_score=item.posture_score,
        posture_status=cast(PostureStatus, item.posture_status),
        firewall_status=item.firewall_status,
        antivirus_status=item.antivirus_status,
        patch_status=item.patch_status,
        pending_reboot=item.pending_reboot,
        os_name=item.os_name,
        os_version=item.os_version,
        disk_health=item.disk_health,
        agent_freshness=item.agent_freshness,
        risky_services_count=item.risky_services_count,
        recommendation_count=item.recommendation_count,
        assessed_at=item.assessed_at,
        metadata=_safe_metadata(item.event_metadata),
    )


def _recommendation_response(
    item: EndpointRemediationRecommendation, asset: LanAsset
) -> EndpointRecommendationResponse:
    return EndpointRecommendationResponse(
        id=item.id,
        lan_asset_id=item.lan_asset_id,
        affected_asset=asset.ip_address,
        asset_hostname=asset.hostname,
        title=item.title,
        severity=cast(RecommendationSeverity, item.severity),
        reason=item.reason,
        recommended_action=item.recommended_action,
        manual_steps=list(item.manual_steps or [])[:12],
        isolation_recommended=item.isolation_recommended,
        evidence_source=item.evidence_source,
        confidence=cast(EvidenceConfidence, item.confidence),
        status=cast(RecommendationStatus, item.status),
        notes=item.notes,
        created_at=item.created_at,
        updated_at=item.updated_at,
        acknowledged_at=item.acknowledged_at,
        resolved_at=item.resolved_at,
        metadata=_safe_metadata(item.event_metadata),
    )


async def _recommendation(
    db: AsyncSession, recommendation_id: uuid.UUID
) -> tuple[EndpointRemediationRecommendation, LanAsset]:
    row = (
        await db.execute(
            select(EndpointRemediationRecommendation, LanAsset)
            .join(
                LanAsset, LanAsset.id == EndpointRemediationRecommendation.lan_asset_id
            )
            .where(EndpointRemediationRecommendation.id == recommendation_id)
        )
    ).one_or_none()
    if row is None:
        raise EndpointRecommendationNotFoundError
    return row[0], row[1]


async def _audit_recommendation(
    db: AsyncSession, user: User, item: EndpointRemediationRecommendation, action: str
) -> None:
    await record_event(
        db,
        action=action,
        actor_id=user.id,
        resource_type="endpoint_remediation_recommendation",
        resource_id=item.id,
        metadata={
            "asset_id": str(item.lan_asset_id),
            "status": item.status,
            "severity": item.severity,
        },
    )


def _agent_freshness(item: LanAssetTelemetry | None) -> str:
    if item is None:
        return "missing"
    cutoff = datetime.now(UTC) - timedelta(minutes=settings.LAN_AGENT_MAX_STALE_MINUTES)
    return "fresh" if item.collected_at >= cutoff else "stale"


def _metadata_status(item: LanAssetTelemetry | None, key: str) -> str | None:
    if item is None or not isinstance(item.event_metadata, dict):
        return None
    value = item.event_metadata.get(key)
    return value if isinstance(value, str) and len(value) <= 24 else None


def _metadata_bool(item: LanAssetTelemetry | None, key: str) -> bool | None:
    if item is None or not isinstance(item.event_metadata, dict):
        return None
    value = item.event_metadata.get(key)
    return value if isinstance(value, bool) else None


def _metadata_ports(item: LanAssetTelemetry | None) -> set[int]:
    if item is None or not isinstance(item.event_metadata, dict):
        return set()
    value = item.event_metadata.get("listening_tcp_ports")
    if not isinstance(value, list):
        return set()
    return {port for port in value if isinstance(port, int) and 1 <= port <= 65535}


def _os_version(item: LanAssetTelemetry | None) -> str | None:
    if item is None:
        return None
    build = _metadata_status(item, "os_build")
    return " ".join(part for part in (item.os_version, build) if part) or None


def _disk_health(item: LanAssetTelemetry | None) -> str | None:
    if item is None or item.disk_percent is None:
        return None
    if item.disk_percent >= 90:
        return "critical"
    if item.disk_percent >= 80:
        return "needs_review"
    return "healthy"


def _risky_service_count(
    services: dict[int, LanServiceObservation], telemetry: LanAssetTelemetry | None
) -> int:
    ports = {port for port, item in services.items() if item.status == "open"}
    ports.update(_metadata_ports(telemetry))
    risky = set(RISKY_PORTS) & ports
    risky.update(
        port
        for port, item in services.items()
        if item.status == "open" and item.non_standard_ssh
    )
    return len(risky)


def _posture_metadata(
    item: LanAssetTelemetry | None, services: dict[int, LanServiceObservation]
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "evidence_mode": "agent_and_stored_observations"
        if item
        else "stored_observations_only",
        "observed_service_count": len(services),
    }
    if item and isinstance(item.event_metadata, dict):
        for key in (
            "os_build",
            "disk_free_gb",
            "latest_patch_date",
            "recent_hotfix_count",
        ):
            value = item.event_metadata.get(key)
            if isinstance(value, (str, int, float, bool)) or value is None:
                result[key] = value
        result["listening_tcp_port_count"] = len(_metadata_ports(item))
    return _safe_metadata(result)


def _safe_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
    if not value:
        return {}
    forbidden = ("password", "secret", "token", "credential", "authorization", "key")
    safe: dict[str, Any] = {}
    for key, item in list(value.items())[:20]:
        if any(term in key.casefold() for term in forbidden):
            continue
        if isinstance(item, (str, int, float, bool)) or item is None:
            safe[key[:80]] = item[:255] if isinstance(item, str) else item
    return safe
