from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.endpoint_posture import EndpointSecurityPosture
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.lan_monitoring import LanAsset, LanAssetTelemetry, LanServiceObservation
from app.models.monitoring_history import (
    MonitoringChangeEvent,
    ServiceObservationHistory,
)
from app.models.monitoring_triage import MonitoringAlertTriage
from app.models.notification import Notification
from app.models.operational_analysis import OperationalAnalysis
from app.models.recon_entity import ReconEntity
from app.models.user import User
from app.schemas.ai_analysis import EvidenceAnalysisRequest, ResourceKind
from app.services.ai_analysis.engine import (
    MAX_BUNDLE_BYTES,
    MetricSample,
    TimeWindow,
    bundle_hash,
    classify_confidence,
    compare_port_sets,
    correlate_changes,
    metric_hypotheses,
    metric_trend,
    normalize_time_window,
)
from app.services.investigation import get_investigation
from app.services.knowledge.retriever import retrieve_context

_SECRET_PATTERN = re.compile(
    r"(?is)(-----BEGIN (?:ENCRYPTED |RSA |EC |OPENSSH |PGP )?PRIVATE KEY"
    r"(?: BLOCK)?-----.*?-----END "
    r"(?:ENCRYPTED |RSA |EC |OPENSSH |PGP )?PRIVATE KEY(?: BLOCK)?-----|"
    r"bearer\s+\S+|(?:password|api[_-]?key|token|secret|authorization)"
    r"\s*[:=]\s*\S+|postgres(?:ql)?://[^\s]+|"
    r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}|"
    r"(?:sk|ghp|gho|xox[baprs])-?[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16})"
)
_MAX_ASSETS = 200
_MAX_CHANGES = 150
_MAX_EVIDENCE = 100
_MAX_KNOWLEDGE = 3


class AnalysisNotFoundError(Exception):
    pass


class AnalysisAccessError(Exception):
    pass


async def create_analysis(
    db: AsyncSession,
    user: User,
    request: EvidenceAnalysisRequest,
    *,
    force_new: bool = False,
) -> tuple[OperationalAnalysis, bool]:
    now = datetime.now(UTC)
    window = normalize_time_window(
        request.window, now=now, start_at=request.start_at, end_at=request.end_at
    )
    scope_type, scope_id = _scope(request.workflow, request.scope_id)
    if request.desktop_inventory is not None and user.role != "admin":
        raise AnalysisAccessError(
            "Local desktop inventory requires administrator access."
        )
    bundle = await build_bundle(db, user, request, window, now)
    digest = bundle_hash(bundle)
    dedupe_key = bundle_hash(
        {
            "user": str(user.id),
            "workflow": request.workflow,
            "scope_type": scope_type,
            "scope_id": str(scope_id) if scope_id else None,
            "window": window.label,
            "evidence": _evidence_fingerprint(bundle),
            "rerun_nonce": str(uuid.uuid4()) if force_new else None,
        }
    )
    existing = (
        await db.execute(
            select(OperationalAnalysis).where(
                OperationalAnalysis.dedupe_key == dedupe_key
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, True

    result = _analysis_result(request.workflow, bundle, request.resource)
    encoded_result = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    if len(encoded_result.encode("utf-8")) > MAX_BUNDLE_BYTES:
        _trim_result(result)
        encoded_result = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    if len(encoded_result.encode("utf-8")) > MAX_BUNDLE_BYTES:
        raise ValueError("Evidence result exceeded the configured safe size limit.")
    row = OperationalAnalysis(
        requested_by_user_id=user.id,
        workflow=request.workflow,
        scope_type=scope_type,
        scope_id=str(scope_id) if scope_id else None,
        status="completed_with_warnings" if bundle["data_gaps"] else "completed",
        summary=_clean(result["summary"], 500),
        confidence=bundle["confidence"],
        evidence_count=len(bundle["facts"]) + len(bundle["changes"]),
        window=bundle["time_window"],
        evidence_ids=[item["id"] for item in bundle["facts"] + bundle["changes"]][:200],
        result=result,
        model_metadata={"mode": "deterministic", "provider": None, "model": None},
        bundle_sha256=digest,
        dedupe_key=dedupe_key,
    )
    db.add(row)
    await db.flush()
    return row, False


async def build_bundle(
    db: AsyncSession,
    user: User,
    request: EvidenceAnalysisRequest,
    window: TimeWindow,
    now: datetime,
) -> dict[str, Any]:
    workflow = request.workflow
    scope_type, scope_id = _scope(workflow, request.scope_id)
    assets: list[LanAsset] = []
    notification: Notification | None = None
    investigation: Investigation | None = None
    if workflow in {"asset_current", "asset_changes", "posture_context"} and scope_id:
        asset = await db.get(LanAsset, scope_id)
        if asset is None:
            raise AnalysisNotFoundError("Asset was not found.")
        assets = [asset]
    elif workflow == "alert_context" and scope_id:
        notification = await db.get(Notification, scope_id)
        if notification is None:
            raise AnalysisNotFoundError("Alert was not found.")
        if notification.entity_type == "lan_asset" and notification.entity_id:
            asset = await db.get(LanAsset, notification.entity_id)
            if asset:
                assets = [asset]
        event_at = _aware(notification.created_at)
        start = event_at - timedelta(minutes=30)
        end = min(now, event_at + timedelta(minutes=15))
        window = normalize_time_window("1h", now=now, start_at=start, end_at=end)
    elif workflow == "investigation_context" and scope_id:
        investigation = await get_investigation(db, user, scope_id)
    elif workflow.startswith("host_"):
        host = (
            await db.execute(
                select(LanAsset)
                .where(LanAsset.asset_type == "server_host")
                .order_by(LanAsset.last_seen.desc().nullslast())
                .limit(1)
            )
        ).scalar_one_or_none()
        assets = [host] if host else []
    elif workflow in {"asset_current", "asset_changes"}:
        raise AnalysisNotFoundError("Asset scope is required.")
    else:
        assets = list(
            (
                await db.execute(
                    select(LanAsset)
                    .order_by(LanAsset.last_seen.desc().nullslast())
                    .limit(_MAX_ASSETS)
                )
            )
            .scalars()
            .all()
        )

    asset_ids = [item.id for item in assets]
    telemetry: list[LanAssetTelemetry] = []
    if asset_ids:
        telemetry = list(
            (
                await db.execute(
                    select(LanAssetTelemetry)
                    .where(
                        LanAssetTelemetry.lan_asset_id.in_(asset_ids),
                        LanAssetTelemetry.collected_at >= window.baseline_start_at,
                        LanAssetTelemetry.collected_at <= window.end_at,
                    )
                    .order_by(LanAssetTelemetry.collected_at.desc())
                    .limit(1000)
                )
            )
            .scalars()
            .all()
        )

    changes = await _load_changes(db, workflow, asset_ids, window)
    service_history = await _load_service_history(db, asset_ids, window)
    alerts = await _load_alerts(db, workflow, scope_id, window, notification)
    posture = await _load_posture(db, asset_ids)
    services = await _load_services(db, asset_ids)
    sources: set[str] = set()
    gaps: list[str] = []
    facts: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}
    process_items: list[dict[str, Any]] = []
    local_services: list[dict[str, Any]] = []
    ports: list[dict[str, Any]] = []
    asset_items = [_asset_item(asset_item, now) for asset_item in assets]
    alert_items = [_notification_item(alert_item) for alert_item in alerts]
    posture_items = [_posture_item(posture_item) for posture_item in posture]

    telemetry_by_asset: dict[uuid.UUID, list[LanAssetTelemetry]] = {}
    for row in telemetry:
        telemetry_by_asset.setdefault(row.lan_asset_id, []).append(row)
    selected_asset = assets[0] if len(assets) == 1 else None
    if selected_asset is not None:
        rows = sorted(
            telemetry_by_asset.get(selected_asset.id, []),
            key=lambda item: _aware(item.collected_at),
        )
        if not rows:
            gaps.append("No persisted metric samples exist in the selected time range.")
        else:
            sources.add("lan_asset_telemetry")
            metric_specs: tuple[tuple[ResourceKind, str], ...] = (
                ("cpu", "cpu_percent"),
                ("memory", "memory_percent"),
                ("disk", "disk_percent"),
            )
            for name, attr in metric_specs:
                samples = [
                    MetricSample(observed_at=row.collected_at, value=value)
                    for row in rows
                    if (value := getattr(row, attr)) is not None
                ]
                recent = [
                    item
                    for item in samples
                    if window.start_at <= _aware(item.observed_at) <= window.end_at
                ]
                baseline = [
                    item
                    for item in samples
                    if window.baseline_start_at
                    <= _aware(item.observed_at)
                    < window.baseline_end_at
                ]
                metric = metric_trend(name, recent, baseline)
                metrics[name] = metric.model_dump(mode="json")
                if metric.current is not None and metric.current_observed_at:
                    facts.append(
                        _evidence(
                            f"metric:{selected_asset.id}:{name}:{metric.current_observed_at.isoformat()}",
                            "metric_sample",
                            f"Current {name.upper()} utilization",
                            f"{metric.current:.1f}% observed at "
                            f"{metric.current_observed_at.isoformat()}.",
                            metric.current_observed_at,
                            "lan_asset_telemetry",
                            _freshness(metric.current_observed_at, now),
                        )
                    )
                if metric.baseline_status == "insufficient_data":
                    gaps.append(f"Insufficient {name} history for a reliable baseline.")
            if rows[-1].collected_at < now - timedelta(
                minutes=settings.LAN_AGENT_MAX_STALE_MINUTES
            ):
                gaps.append("Server or asset metric telemetry is stale.")
    elif workflow.startswith("host_"):
        gaps.append(
            "No primary ServerHost asset is registered; server history is unavailable."
        )

    if telemetry:
        sources.add("lan_asset_telemetry")
    for event in changes:
        facts.append(_change_evidence(event))
        sources.add("monitoring_change_events")
    for service_event in service_history:
        changes.append(_service_history_item(service_event))
        sources.add("service_observation_history")
    for service_observation in services:
        local_services.append(
            {
                "evidence_id": f"lan-service:{service_observation.id}",
                "asset_id": str(service_observation.lan_asset_id),
                "ip_address": service_observation.ip_address,
                "port": service_observation.port,
                "protocol": service_observation.protocol,
                "service": _clean(
                    service_observation.service_label
                    or service_observation.service_name
                    or "Unknown TCP service",
                    100,
                ),
                "state": service_observation.status,
                "confidence": service_observation.confidence,
                "observed_at": _aware(service_observation.observed_at).isoformat(),
                "source": _clean(service_observation.source, 80),
            }
        )
    if services:
        sources.add("lan_service_observations")

    if request.desktop_inventory and request.desktop_inventory.available:
        sources.add("native_desktop_inventory")
        for process in request.desktop_inventory.processes[:100]:
            process_items.append(
                {
                    "evidence_id": f"process:{process.pid}:{process.started_at_unix}",
                    "pid": process.pid,
                    "name": _clean(process.name, 160),
                    "cpu_percent": round(process.cpu_percent, 2),
                    "memory_bytes": process.memory_bytes,
                    "started_at": datetime.fromtimestamp(
                        process.started_at_unix, UTC
                    ).isoformat(),
                    "runtime_seconds": process.runtime_seconds,
                    "source": "client_supplied_native_inventory",
                }
            )
        process_items.sort(
            key=lambda item: (
                item["memory_bytes"]
                if request.resource == "memory"
                else item["cpu_percent"]
                if request.resource == "cpu"
                else max(item["memory_bytes"], item["cpu_percent"])
            ),
            reverse=True,
        )
        for process_item in process_items[:20]:
            started = datetime.fromisoformat(process_item["started_at"])
            facts.append(
                _evidence(
                    process_item["evidence_id"],
                    "process",
                    f"Process {process_item['name']}",
                    f"PID {process_item['pid']}; "
                    f"CPU {process_item['cpu_percent']:.1f}%; "
                    f"memory {process_item['memory_bytes'] / (1024**2):.1f} MiB; "
                    f"started {process_item['started_at']}.",
                    started,
                    "client_supplied_native_inventory",
                    "current",
                )
            )
        for local_service in request.desktop_inventory.services[:100]:
            local_services.append(
                {
                    "evidence_id": f"local-service:{_clean(local_service.name, 128)}",
                    "name": _clean(local_service.name, 128),
                    "display_name": _clean(local_service.display_name, 160),
                    "state": _clean(local_service.state, 40),
                    "start_type": _clean(local_service.start_type or "unknown", 40),
                    "source": "client_supplied_native_inventory",
                }
            )
        gaps.append(
            "Local process and service inventory is current client-supplied "
            "data, not historical telemetry."
        )
    elif workflow.startswith("host_"):
        gaps.append(
            "Local process and service inventory was not supplied for this analysis."
        )

    # ServerHost reports bounded listening-port observations with its telemetry.
    host_rows = sorted(
        telemetry, key=lambda item: _aware(item.collected_at), reverse=True
    )
    if host_rows and workflow in {
        "host_current",
        "host_changes",
        "host_ports",
        "host_resource",
    }:
        latest_ports = _ports(host_rows[0].event_metadata)
        previous_ports = (
            _ports(host_rows[1].event_metadata) if len(host_rows) > 1 else None
        )
        for port in sorted(latest_ports)[:64]:
            ports.append(
                {
                    "port": port,
                    "state": "open",
                    "observed_at": _aware(host_rows[0].collected_at).isoformat(),
                    "source": "server_host_telemetry",
                }
            )
        for port_change in compare_port_sets(latest_ports, previous_ports):
            transitioned_port = port_change["port"]
            opened = port_change["kind"] == "port_opened"
            changes.append(
                {
                    "id": (
                        f"host-port:{transitioned_port}:"
                        f"{_aware(host_rows[0].collected_at).isoformat()}"
                    ),
                    "kind": port_change["kind"],
                    "title": (
                        f"TCP port {transitioned_port} "
                        f"{'appeared' if opened else 'was absent'} in the latest sample"
                    ),
                    "summary": (
                        "ServerHost telemetry observation; an open port is "
                        "not a vulnerability by itself."
                    ),
                    "observed_at": _aware(host_rows[0].collected_at).isoformat(),
                    "scope_id": str(host_rows[0].lan_asset_id),
                    "severity": "info",
                    "source": "server_host_telemetry",
                }
            )

    for asset in assets:
        first_seen = _aware(asset.first_seen)
        if window.start_at <= first_seen <= window.end_at:
            changes.append(
                {
                    "id": f"asset-first-seen:{asset.id}:{first_seen.isoformat()}",
                    "kind": "asset_first_seen",
                    "title": (
                        "Asset first observed: "
                        f"{_clean(asset.hostname or asset.ip_address, 160)}"
                    ),
                    "summary": (
                        "Newly observed in RavenTech inventory; this is not "
                        "evidence of malicious activity."
                    ),
                    "observed_at": first_seen.isoformat(),
                    "scope_id": str(asset.id),
                    "severity": "info",
                    "source": "lan_assets",
                }
            )
    if workflow == "alert_context" and notification is not None:
        triage = (
            await db.execute(
                select(MonitoringAlertTriage)
                .where(MonitoringAlertTriage.alert_id == notification.id)
                .limit(1)
            )
        ).scalar_one_or_none()
        if triage:
            alert_items[0]["triage_status"] = triage.status
            alert_items[0]["first_seen"] = _aware(triage.first_seen).isoformat()
            alert_items[0]["last_seen"] = _aware(triage.last_seen).isoformat()

    if investigation is not None:
        finding_count = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(Finding)
                    .where(Finding.investigation_id == investigation.id)
                )
            ).scalar_one()
        )
        entity_count = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(ReconEntity)
                    .where(ReconEntity.investigation_id == investigation.id)
                )
            ).scalar_one()
        )
        findings = list(
            (
                await db.execute(
                    select(Finding)
                    .where(Finding.investigation_id == investigation.id)
                    .order_by(Finding.risk_score.desc(), Finding.created_at.desc())
                    .limit(20)
                )
            )
            .scalars()
            .all()
        )
        facts.append(
            _evidence(
                f"investigation:{investigation.id}",
                "investigation",
                _clean(investigation.title, 180),
                f"Status {investigation.status}; scope review "
                f"{investigation.scope_review_status}; {finding_count} findings "
                f"and {entity_count} stored recon entities.",
                investigation.updated_at,
                "investigations",
                "current",
                target_url=f"/investigations/{investigation.id}",
            )
        )
        for finding in findings:
            facts.append(
                _evidence(
                    f"finding:{finding.id}",
                    "finding",
                    _clean(finding.title, 180),
                    f"Severity {finding.severity}; status {finding.status}; "
                    f"risk score {finding.risk_score}.",
                    finding.updated_at,
                    "findings",
                    "current",
                    target_url=f"/investigations/{investigation.id}",
                )
            )
        sources.add("investigations")

    for service_item in local_services[:100]:
        facts.append(_service_evidence(service_item))
    for alert_item in alert_items[:30]:
        facts.append(_notification_evidence(alert_item))
    for posture_item in posture_items[:100]:
        facts.append(_posture_evidence(posture_item))
    knowledge = _knowledge(_knowledge_query(workflow, request.resource, facts, changes))
    if knowledge:
        sources.add("local_knowledge_retriever")
    else:
        gaps.append("No relevant local Knowledge references were found.")

    changes = _dedupe(changes)[:_MAX_CHANGES]
    correlations = correlate_changes(changes)
    hypotheses: list[dict[str, Any]] = []
    metric_key = request.resource or "memory"
    if metric_key in metrics:
        from app.services.ai_analysis.engine import MetricTrend

        hypotheses = metric_hypotheses(
            metric=MetricTrend.model_validate(metrics[metric_key]),
            processes=process_items[:30],
            evidence=facts,
        )
    if workflow.startswith("host_") and not telemetry:
        gaps.append("No primary host metric history exists for comparison.")
    if workflow.startswith("host_") and not (
        request.desktop_inventory and request.desktop_inventory.available
    ):
        gaps.append(
            "Per-process history is not persisted; process attribution is unavailable."
        )

    facts = _dedupe_evidence(facts)[:_MAX_EVIDENCE]
    gaps = list(dict.fromkeys(gaps))[:30]
    bundle = {
        "bundle_id": str(uuid.uuid4()),
        "scope_type": scope_type,
        "scope_id": str(scope_id) if scope_id else None,
        "generated_at": now.isoformat(),
        "time_window": window.model_dump(mode="json"),
        "baseline_window": {
            "start_at": window.baseline_start_at.isoformat(),
            "end_at": window.baseline_end_at.isoformat(),
            "policy": "bounded preceding matched window, capped at seven days",
        },
        "facts": facts,
        "changes": changes,
        "alerts": alert_items[:30],
        "posture": posture_items[:100],
        "metrics": metrics,
        "processes": process_items[:30],
        "services": local_services[:100],
        "ports": ports[:64],
        "assets": asset_items[:_MAX_ASSETS],
        "agents": [_agent_item(asset, now) for asset in assets],
        "timeline": changes[:100],
        "correlations": correlations,
        "hypotheses": hypotheses,
        "knowledge": knowledge,
        "data_gaps": gaps,
        "confidence": classify_confidence(
            evidence_count=len(facts) + len(changes),
            source_count=len(sources),
            gaps=gaps,
            stale=any("stale" in gap.casefold() for gap in gaps),
        ),
        "truncated": len(telemetry) >= 1000 or len(assets) >= _MAX_ASSETS,
        "provenance": sorted(sources),
    }
    _trim_bundle(bundle)
    return bundle


async def _load_changes(
    db: AsyncSession, workflow: str, asset_ids: list[uuid.UUID], window: Any
) -> list[dict[str, Any]]:
    stmt = select(MonitoringChangeEvent).where(
        MonitoringChangeEvent.detected_at >= window.start_at,
        MonitoringChangeEvent.detected_at <= window.end_at,
    )
    if workflow.startswith("host_"):
        stmt = stmt.where(
            MonitoringChangeEvent.asset_id == asset_ids[0]
            if asset_ids
            else MonitoringChangeEvent.asset_id.is_(None)
        )
    elif workflow in {"asset_current", "asset_changes", "alert_context"} and asset_ids:
        stmt = stmt.where(MonitoringChangeEvent.asset_id == asset_ids[0])
    elif workflow == "lan_changes":
        stmt = stmt.where(MonitoringChangeEvent.asset_id.is_not(None))
    rows = list(
        (
            await db.execute(
                stmt.order_by(MonitoringChangeEvent.detected_at.desc()).limit(
                    _MAX_CHANGES
                )
            )
        )
        .scalars()
        .all()
    )
    return [_change_item(row) for row in rows]


async def _load_service_history(
    db: AsyncSession, asset_ids: list[uuid.UUID], window: Any
) -> list[ServiceObservationHistory]:
    if not asset_ids:
        return []
    return list(
        (
            await db.execute(
                select(ServiceObservationHistory)
                .where(
                    ServiceObservationHistory.asset_id.in_(asset_ids),
                    ServiceObservationHistory.observed_at >= window.start_at,
                    ServiceObservationHistory.observed_at <= window.end_at,
                )
                .order_by(ServiceObservationHistory.observed_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )


async def _load_alerts(
    db: AsyncSession,
    workflow: str,
    scope_id: uuid.UUID | None,
    window: Any,
    selected: Notification | None,
) -> list[Notification]:
    stmt = select(Notification).where(
        Notification.created_at >= window.start_at,
        Notification.created_at <= window.end_at,
        Notification.severity.in_(("warning", "critical")),
    )
    if workflow == "alert_context" and selected:
        stmt = select(Notification).where(Notification.id == selected.id)
    elif workflow in {"asset_current", "asset_changes"} and scope_id:
        stmt = stmt.where(Notification.entity_id == scope_id)
    return list(
        (await db.execute(stmt.order_by(Notification.created_at.desc()).limit(50)))
        .scalars()
        .all()
    )


async def _load_posture(
    db: AsyncSession, asset_ids: list[uuid.UUID]
) -> list[EndpointSecurityPosture]:
    if not asset_ids:
        return []
    return list(
        (
            await db.execute(
                select(EndpointSecurityPosture)
                .where(EndpointSecurityPosture.lan_asset_id.in_(asset_ids))
                .order_by(EndpointSecurityPosture.assessed_at.desc())
                .limit(_MAX_ASSETS)
            )
        )
        .scalars()
        .all()
    )


async def _load_services(
    db: AsyncSession, asset_ids: list[uuid.UUID]
) -> list[LanServiceObservation]:
    if not asset_ids:
        return []
    rows = list(
        (
            await db.execute(
                select(LanServiceObservation)
                .where(LanServiceObservation.lan_asset_id.in_(asset_ids))
                .order_by(LanServiceObservation.observed_at.desc())
                .limit(500)
            )
        )
        .scalars()
        .all()
    )
    latest: dict[tuple[uuid.UUID, str, int], LanServiceObservation] = {}
    for item in rows:
        latest.setdefault((item.lan_asset_id, item.protocol, item.port), item)
    return list(latest.values())


async def list_analyses(
    db: AsyncSession, user: User, *, limit: int = 25, offset: int = 0
) -> list[OperationalAnalysis]:
    return list(
        (
            await db.execute(
                select(OperationalAnalysis)
                .where(OperationalAnalysis.requested_by_user_id == user.id)
                .order_by(OperationalAnalysis.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def get_analysis(
    db: AsyncSession, user: User, analysis_id: uuid.UUID
) -> OperationalAnalysis:
    row = await db.get(OperationalAnalysis, analysis_id)
    if row is None or (user.role != "admin" and row.requested_by_user_id != user.id):
        raise AnalysisNotFoundError("Analysis was not found.")
    return row


def compare_analysis_rows(
    first: OperationalAnalysis, second: OperationalAnalysis
) -> dict[str, Any]:
    differences: list[str] = []
    if first.bundle_sha256 == second.bundle_sha256:
        summary = "Both analyses used the same normalized evidence bundle."
    else:
        summary = (
            "The analyses used different evidence bundles; differences are "
            "based on recorded evidence."
        )
        first_result = first.result if isinstance(first.result, dict) else {}
        second_result = second.result if isinstance(second.result, dict) else {}
        first_metrics = first_result.get("metrics", {})
        second_metrics = second_result.get("metrics", {})
        if isinstance(first_metrics, dict) and isinstance(second_metrics, dict):
            for metric_name in sorted(set(first_metrics) | set(second_metrics)):
                before = first_metrics.get(metric_name)
                after = second_metrics.get(metric_name)
                if not isinstance(before, dict) or not isinstance(after, dict):
                    if before != after:
                        differences.append(
                            f"{metric_name} metric evidence was added or removed."
                        )
                    continue
                for field in ("current", "average", "trend", "baseline_status"):
                    old_value, new_value = before.get(field), after.get(field)
                    if old_value != new_value:
                        differences.append(
                            f"{metric_name} {field} changed from "
                            f"{_safe_compare_value(old_value)} to "
                            f"{_safe_compare_value(new_value)}."
                        )
        first_bundle = first_result.get("bundle", {})
        second_bundle = second_result.get("bundle", {})
        if isinstance(first_bundle, dict) and isinstance(second_bundle, dict):
            _append_record_changes(
                differences,
                first_bundle.get("changes", []),
                second_bundle.get("changes", []),
                label="timeline change",
            )
            _append_record_changes(
                differences,
                first_bundle.get("facts", []),
                second_bundle.get("facts", []),
                label="evidence fact",
            )
            first_gaps = set(first_bundle.get("data_gaps", []))
            second_gaps = set(second_bundle.get("data_gaps", []))
            for gap in sorted(second_gaps - first_gaps)[:10]:
                differences.append(f"Evidence gap added: {_clean(str(gap), 240)}")
            for gap in sorted(first_gaps - second_gaps)[:10]:
                differences.append(f"Evidence gap resolved: {_clean(str(gap), 240)}")
        if first.confidence != second.confidence:
            differences.append(
                f"Confidence changed from {first.confidence} to {second.confidence}."
            )
        if first.evidence_count != second.evidence_count:
            differences.append(
                f"Evidence count changed from {first.evidence_count} "
                f"to {second.evidence_count}."
            )
        if first.summary != second.summary:
            differences.append("The deterministic summary changed.")
    return {
        "first_analysis_id": first.id,
        "second_analysis_id": second.id,
        "same_bundle": first.bundle_sha256 == second.bundle_sha256,
        "summary": summary,
        "differences": differences[:30],
    }


def _safe_compare_value(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, (str, int, float, bool)):
        return _clean(str(value), 80)
    return "recorded value"


def _append_record_changes(
    output: list[str], before_rows: Any, after_rows: Any, *, label: str
) -> None:
    if not isinstance(before_rows, list) or not isinstance(after_rows, list):
        return
    before = {
        str(item.get("id")): item
        for item in before_rows
        if isinstance(item, dict) and item.get("id") is not None
    }
    after = {
        str(item.get("id")): item
        for item in after_rows
        if isinstance(item, dict) and item.get("id") is not None
    }
    for identity in sorted(after.keys() - before.keys())[:10]:
        item = after[identity]
        title = _clean(str(item.get("title") or item.get("kind") or label), 120)
        output.append(f"New {label}: {title}.")
    for identity in sorted(before.keys() - after.keys())[:10]:
        item = before[identity]
        title = _clean(str(item.get("title") or item.get("kind") or label), 120)
        output.append(f"No longer present {label}: {title}.")


def _analysis_result(
    workflow: str, bundle: dict[str, Any], resource: str | None
) -> dict[str, Any]:
    changes = bundle["changes"]
    summary = (
        "No significant RavenTech-observed change was recorded in the selected window."
        if not changes
        else f"RavenTech recorded {len(changes)} relevant change(s) "
        "in the selected window."
    )
    metric = bundle["metrics"].get(resource or "memory")
    if workflow == "host_resource" and metric and metric.get("current") is not None:
        name = resource or "memory"
        summary = f"Current {name} utilization is {metric['current']:.1f}%."
        if metric.get("baseline_status") != "available":
            summary += " There is not enough history for a reliable baseline."
        elif metric.get("delta_from_baseline") is not None:
            summary += (
                " The change from its observed baseline is "
                f"{metric['delta_from_baseline']:+.1f} percentage points."
            )
    if bundle["data_gaps"]:
        summary += " Some evidence is missing or stale; see Data gaps."
    recommendations = []
    if bundle["data_gaps"]:
        recommendations.append(
            {
                "priority": "informational",
                "text": (
                    "Refresh the relevant RavenTech telemetry and rerun the "
                    "analysis to improve historical comparison."
                ),
                "basis": "The result identifies missing or stale evidence.",
            }
        )
    if changes:
        recommendations.append(
            {
                "priority": "informational",
                "text": (
                    "Review the related Monitoring Center or LAN observations "
                    "and verify whether the changes were expected."
                ),
                "basis": "Manual diagnostic guidance only; no action is performed.",
            }
        )
    return {
        "analysis_type": workflow,
        "resource": resource,
        "scope": {"type": bundle["scope_type"], "id": bundle["scope_id"]},
        "generated_at": bundle["generated_at"],
        "window": bundle["time_window"],
        "baseline_window": bundle["baseline_window"],
        "summary": summary,
        "confidence": bundle["confidence"],
        "quality": _quality(bundle),
        "facts": bundle["facts"],
        "changes": changes,
        "correlations": bundle["correlations"],
        "hypotheses": bundle["hypotheses"],
        "recommendations": recommendations,
        "uncertainties": bundle["data_gaps"],
        "data_gaps": bundle["data_gaps"],
        "evidence": bundle["facts"],
        "knowledge": bundle["knowledge"],
        "metrics": bundle["metrics"],
        "processes": bundle["processes"],
        "services": bundle["services"],
        "ports": bundle["ports"],
        "assets": bundle["assets"],
        "alerts": bundle["alerts"],
        "posture": bundle["posture"],
        "timeline": bundle["timeline"],
        "bundle": bundle,
        "model_metadata": {"mode": "deterministic", "provider": None, "model": None},
    }


def _scope(workflow: str, scope_id: uuid.UUID | None) -> tuple[str, uuid.UUID | None]:
    if workflow.startswith("host_"):
        return "host", None
    if workflow.startswith("lan_") or workflow == "global_attention":
        return "lan", None
    mapping = {
        "asset_current": "asset",
        "asset_changes": "asset",
        "alert_context": "alert",
        "posture_context": "posture",
        "investigation_context": "investigation",
    }
    return mapping.get(workflow, "global"), scope_id


def _asset_item(asset: LanAsset, now: datetime) -> dict[str, Any]:
    last_seen = _aware(asset.last_seen) if asset.last_seen else None
    cutoff = timedelta(seconds=max(settings.LAN_DISCOVERY_INTERVAL_SECONDS * 2, 600))
    return {
        "id": str(asset.id),
        "hostname": _clean(asset.hostname or "", 160) or None,
        "ip_address": asset.ip_address,
        "os_family": asset.os_family,
        "os_name": _clean(asset.os_name or "", 100) or None,
        "device_type": asset.manual_device_type or asset.device_type,
        "classification_source": asset.classification_source,
        "classification_confidence": asset.classification_confidence,
        "authorized": asset.is_authorized,
        "status": "online"
        if last_seen and now - last_seen <= cutoff
        else "stale_or_unknown",
        "first_seen": _aware(asset.first_seen).isoformat(),
        "last_seen": last_seen.isoformat() if last_seen else None,
        "observed_at": (last_seen or _aware(asset.first_seen)).isoformat(),
    }


def _agent_item(asset: LanAsset, now: datetime) -> dict[str, Any]:
    last_seen = _aware(asset.last_seen) if asset.last_seen else None
    threshold = timedelta(minutes=settings.LAN_AGENT_MAX_STALE_MINUTES)
    state = (
        "unknown"
        if last_seen is None
        else "fresh"
        if now - last_seen <= threshold
        else "stale"
    )
    return {
        "asset_id": str(asset.id),
        "mode": _clean(asset.agent_mode or "unknown", 40),
        "status": state,
        "last_seen": last_seen.isoformat() if last_seen else None,
        "observed_at": last_seen.isoformat() if last_seen else None,
    }


def _change_item(item: MonitoringChangeEvent) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "kind": item.event_type,
        "title": _clean(item.title, 180),
        "summary": _clean(item.description, 240),
        "old_value": _clean(item.old_value or "", 100) or None,
        "new_value": _clean(item.new_value or "", 100) or None,
        "observed_at": _aware(item.detected_at).isoformat(),
        "scope_id": str(item.asset_id) if item.asset_id else None,
        "severity": item.severity,
        "source": _clean(item.source, 80),
        "target_url": "/monitoring"
        if item.asset_id is None
        else f"/lan/assets/{item.asset_id}",
    }


def _service_history_item(item: ServiceObservationHistory) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "kind": "service_state_changed",
        "title": f"Port {item.port} service state observed",
        "summary": (
            f"{_clean(item.service_name or 'Unknown TCP service', 100)}: "
            f"{_clean(item.previous_status or 'unknown', 30)} -> "
            f"{_clean(item.current_status, 30)}."
        ),
        "observed_at": _aware(item.observed_at).isoformat(),
        "scope_id": str(item.asset_id),
        "severity": "info",
        "source": _clean(item.source, 80),
        "port": item.port,
    }


def _notification_item(item: Notification) -> dict[str, Any]:
    url = item.action_url
    safe_url = _safe_target_url(url)
    return {
        "id": str(item.id),
        "entity_type": item.entity_type,
        "entity_id": str(item.entity_id) if item.entity_id else None,
        "severity": item.severity,
        "title": _clean(item.title, 180),
        "summary": _clean(item.message, 240),
        "status": item.status,
        "observed_at": _aware(item.created_at).isoformat(),
        "source": _clean(item.notification_type, 80),
        "target_url": safe_url,
    }


def _posture_item(item: EndpointSecurityPosture) -> dict[str, Any]:
    observed = _aware(item.assessed_at)
    return {
        "id": str(item.id),
        "asset_id": str(item.lan_asset_id),
        "score": item.posture_score,
        "status": _clean(item.posture_status, 40),
        "firewall": _clean(item.firewall_status, 40),
        "antivirus": _clean(item.antivirus_status, 40),
        "patch": _clean(item.patch_status, 40),
        "risky_services": item.risky_services_count,
        "assessed_at": observed.isoformat(),
        "observed_at": observed.isoformat(),
        "source": "endpoint_security_postures",
    }


def _evidence(
    evidence_id: str,
    kind: str,
    title: str,
    summary: str,
    observed_at: datetime | None,
    source: str,
    freshness: str,
    *,
    target_url: str | None = None,
) -> dict[str, Any]:
    safe_target = _safe_target_url(target_url)
    return {
        "id": _clean(evidence_id, 180),
        "kind": _clean(kind, 40),
        "title": _clean(title, 180),
        "summary": _clean(summary, 500),
        "observed_at": _aware(observed_at).isoformat() if observed_at else None,
        "freshness": freshness,
        "source": _clean(source, 80),
        "target_url": safe_target,
    }


def _change_evidence(item: dict[str, Any]) -> dict[str, Any]:
    return _evidence(
        item["id"],
        item.get("kind", "change"),
        item.get("title", "Change"),
        item.get("summary", ""),
        _parse_timestamp(item.get("observed_at")),
        item.get("source", "monitoring_timeline"),
        "historical",
        target_url=item.get("target_url"),
    )


def _service_evidence(item: dict[str, Any]) -> dict[str, Any]:
    name = item.get("service", item.get("display_name", item.get("name", "Service")))
    port = item.get("port", "local")
    return _evidence(
        item["evidence_id"],
        "service",
        f"{name} on {port}",
        f"Observed state: {item.get('state', 'unknown')}.",
        _parse_timestamp(item.get("observed_at")),
        item.get("source", "service_inventory"),
        "current",
    )


def _notification_evidence(item: dict[str, Any]) -> dict[str, Any]:
    return _evidence(
        f"alert:{item['id']}",
        "alert",
        item["title"],
        item["summary"],
        _parse_timestamp(item["observed_at"]),
        item["source"],
        "recent",
        target_url=item.get("target_url"),
    )


def _posture_evidence(item: dict[str, Any]) -> dict[str, Any]:
    return _evidence(
        f"posture:{item['id']}",
        "posture",
        f"Security posture: {item['status']}",
        f"Official posture score {item['score']}; risky service count "
        f"{item['risky_services']}.",
        _parse_timestamp(item["observed_at"]),
        item["source"],
        "current",
        target_url=f"/lan/assets/{item['asset_id']}",
    )


def _knowledge(query: str) -> list[dict[str, Any]]:
    try:
        result = retrieve_context(query, top_k=_MAX_KNOWLEDGE)
    except Exception:
        return []
    return [
        {
            "id": citation.id,
            "title": _clean(chunk.title, 180),
            "source": _clean(chunk.source, 100),
            "framework": _clean(chunk.framework, 80),
            "category": _clean(chunk.category, 100),
            "confidence": round(chunk.confidence, 2),
            "summary": _clean(chunk.content, 700),
            "trust_level": _clean(citation.trust_level, 40),
            "verification_status": _clean(citation.verification_status, 40),
            "observed_at": None,
            "target_url": None,
        }
        for chunk, citation in zip(
            result.matched_chunks, result.citations, strict=False
        )
    ]


def _knowledge_query(
    workflow: str,
    resource: str | None,
    facts: list[dict[str, Any]],
    changes: list[dict[str, Any]],
) -> str:
    topics = " ".join(item.get("title", "") for item in facts[:6])
    event_types = " ".join(item.get("kind", "") for item in changes[:5])
    return _clean(
        f"defensive operational analysis {workflow} {resource or ''} "
        f"{topics} {event_types}",
        500,
    )


def _quality(bundle: dict[str, Any]) -> str:
    count, source_count = (
        len(bundle["facts"]) + len(bundle["changes"]),
        len(bundle["provenance"]),
    )
    if count >= 8 and source_count >= 3 and not bundle["data_gaps"]:
        return "high"
    if count >= 3 and source_count >= 2:
        return "medium"
    return "low"


def _trim_bundle(bundle: dict[str, Any]) -> None:
    lists = (
        "facts",
        "changes",
        "timeline",
        "services",
        "assets",
        "alerts",
        "posture",
        "processes",
        "ports",
        "knowledge",
        "correlations",
        "hypotheses",
    )
    while (
        len(
            json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        > MAX_BUNDLE_BYTES
    ):
        key = max(lists, key=lambda item: len(bundle.get(item, [])))
        if not bundle.get(key):
            break
        bundle[key].pop()
        bundle["truncated"] = True
    if bundle["truncated"]:
        gap = "Evidence bundle was truncated to the configured response-size budget."
        if gap not in bundle["data_gaps"]:
            bundle["data_gaps"].append(gap)


def _trim_result(result: dict[str, Any]) -> None:
    for key in (
        "facts",
        "evidence",
        "changes",
        "timeline",
        "services",
        "assets",
        "alerts",
        "posture",
        "processes",
        "ports",
        "knowledge",
        "correlations",
        "hypotheses",
    ):
        if isinstance(result.get(key), list):
            result[key] = result[key][:20]
    bundle = result.get("bundle")
    if isinstance(bundle, dict):
        _trim_bundle(bundle)
        bundle["truncated"] = True
    result["truncated"] = True


def _evidence_fingerprint(bundle: dict[str, Any]) -> str:
    view = dict(bundle)
    for key in ("bundle_id", "generated_at", "time_window", "baseline_window"):
        view.pop(key, None)
    return bundle_hash(view)


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output, seen = [], set()
    for item in sorted(
        items, key=lambda row: str(row.get("observed_at", "")), reverse=True
    ):
        key = str(item.get("id") or bundle_hash(item))
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output


def _dedupe_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output, seen = [], set()
    for item in items:
        if item["id"] not in seen:
            seen.add(item["id"])
            output.append(item)
    return output


def _ports(metadata: dict[str, Any]) -> set[int]:
    values = (
        metadata.get("listening_tcp_ports", []) if isinstance(metadata, dict) else []
    )
    if not isinstance(values, list):
        return set()
    return {item for item in values if isinstance(item, int) and 1 <= item <= 65535}


def _freshness(timestamp: datetime, now: datetime) -> str:
    age = now - _aware(timestamp)
    return (
        "current"
        if age <= timedelta(minutes=5)
        else "recent"
        if age <= timedelta(hours=1)
        else "stale"
    )


def _clean(value: str | None, limit: int) -> str:
    if value is None:
        return ""
    cleaned = _SECRET_PATTERN.sub("[redacted]", value.replace("\x00", ""))
    return " ".join(cleaned.split())[:limit]


def _safe_target_url(value: str | None) -> str | None:
    if value in {"/monitoring", "/lan", "/notifications"}:
        return value
    if value and re.fullmatch(
        r"/(?:lan/assets|notifications|investigations)/"
        r"[0-9a-fA-F-]{36}(?:/(?:findings|timeline))?",
        value,
    ):
        return value
    return None


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return _aware(value)
    if isinstance(value, str):
        try:
            return _aware(datetime.fromisoformat(value))
        except ValueError:
            return None
    return None


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
