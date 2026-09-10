from __future__ import annotations

import os
import shutil
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.case_closure import CaseClosure
from app.models.engagement import Engagement
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.investigation_evidence import InvestigationEvidence
from app.models.investigation_member import InvestigationMember
from app.models.report import Report
from app.models.notification import Notification
from app.models.monitoring_policy import (
    AlertSuppression,
    MaintenanceWindow,
    MonitoringPolicy,
)
from app.models.lan_monitoring import VulnerabilityBaselineFinding
from app.models.scan_job import ScanJob
from app.models.target import Target
from app.models.user import User
from app.schemas.monitoring import (
    AgentTelemetryIngest,
    AgentTelemetryIngestResponse,
    MonitoringAlert,
    MonitoringAlertsResponse,
    MonitoringAssetItem,
    MonitoringAssetsResponse,
    MonitoringOverviewResponse,
    MonitoringRecentError,
    MonitoringSeverity,
    MonitoringServicesResponse,
    MonitoringServiceStatus,
    MonitoringStatus,
    MonitoringSystemResponse,
)
from app.services.health import health_snapshot
from app.services.notification import create_notification
from app.services.monitoring_policy import ensure_default_policies
from app.services.audit import record_event

POLLING_INTERVAL_OPTIONS = [15, 30, 60, 120, 300]
RECOMMENDED_POLLING_INTERVAL = 30
STALE_TARGET_DAYS = 30
AGENT_STALE_SECONDS = 600
UNRESOLVED_FINDING_STATUSES = {"new", "open", "under_review", "validated"}

_latest_agent_sample: tuple[AgentTelemetryIngest, datetime] | None = None


async def get_monitoring_overview(
    db: AsyncSession,
    redis: Any,
    user: User,
) -> MonitoringOverviewResponse:
    services = await get_service_status(redis)
    system = get_system_metrics()
    assets = await get_asset_watch(db, user)
    alerts = await get_monitoring_alerts(
        db,
        user,
        services=services,
        system=system,
        assets=assets,
    )
    recent_errors = await get_recent_errors(db, user)
    return MonitoringOverviewResponse(
        generated_at=datetime.now(UTC),
        status=_overall_monitoring_status(services, alerts),
        release_version=settings.APP_VERSION,
        polling_interval_options=POLLING_INTERVAL_OPTIONS,
        recommended_polling_interval=RECOMMENDED_POLLING_INTERVAL,
        services=services,
        system=system,
        assets=assets,
        alerts=alerts,
        recent_errors=recent_errors,
    )


async def get_service_status(redis: Any) -> MonitoringServicesResponse:
    generated_at = datetime.now(UTC)
    snapshot = await health_snapshot(redis, include_ready=True)
    checks = snapshot.get("checks") if isinstance(snapshot.get("checks"), dict) else {}
    checks = cast(dict[str, Any], checks)
    storage = _safe_mapping(checks.get("storage"))
    paths = _safe_mapping(storage.get("paths"))
    migrations = _safe_mapping(checks.get("migrations"))
    items = [
        MonitoringServiceStatus(
            key="backend",
            label="Backend API",
            status=_monitoring_status(snapshot.get("status")),
            detail="Authenticated API and required local dependencies.",
        ),
        MonitoringServiceStatus(
            key="readiness",
            label="Readiness",
            status=_monitoring_status(snapshot.get("status")),
            detail="Required local dependencies and storage readiness.",
        ),
        MonitoringServiceStatus(
            key="release",
            label="Release metadata",
            status="healthy",
            detail=f"Local release endpoint reports {settings.APP_VERSION}.",
            metadata={"version": settings.APP_VERSION},
        ),
        _health_service("database", "PostgreSQL", checks),
        _health_service("redis", "Redis", checks),
        _health_service("worker", "Celery worker", checks),
        MonitoringServiceStatus(
            key="migrations",
            label="Database migrations",
            status=_monitoring_status(migrations.get("status")),
            detail=(
                "Migration head matches the local database."
                if migrations.get("status") == "ok"
                else "Migration state needs operator review."
            ),
            metadata={
                "current": _safe_short_text(migrations.get("current")),
                "head": _safe_short_text(migrations.get("head")),
            },
        ),
        MonitoringServiceStatus(
            key="report_storage",
            label="Report storage",
            status=("healthy" if paths.get("reports") == "writable" else "unavailable"),
            detail=(
                "Local report storage is writable."
                if paths.get("reports") == "writable"
                else "Local report storage is unavailable."
            ),
        ),
        _docker_service_status(),
    ]
    required = [item for item in items if item.key != "docker"]
    status: MonitoringStatus = "healthy"
    if any(item.status == "unavailable" for item in required):
        status = "unavailable"
    elif any(item.status == "degraded" for item in required):
        status = "degraded"
    return MonitoringServicesResponse(
        generated_at=generated_at,
        status=status,
        items=items,
    )


def get_system_metrics() -> MonitoringSystemResponse:
    now = datetime.now(UTC)
    if _latest_agent_sample is not None:
        sample, received_at = _latest_agent_sample
        age = max(0.0, (now - received_at).total_seconds())
        if age <= AGENT_STALE_SECONDS:
            return MonitoringSystemResponse(
                generated_at=now,
                source="local_agent",
                metric_scope="authorized local host",
                available=True,
                stale=False,
                agent_id=sample.agent_id,
                platform=sample.platform,
                collected_at=sample.collected_at,
                received_at=received_at,
                cpu_percent=sample.cpu_percent,
                memory_percent=sample.memory_percent,
                disk_percent=sample.disk_percent,
                process_count=sample.process_count,
                uptime_seconds=sample.uptime_seconds,
                detail="Latest optional local-agent sample; no secrets are collected.",
            )

    cpu_percent = _container_cpu_percent()
    memory_percent = _container_memory_percent()
    disk_percent = _disk_percent(Path("/data"))
    process_count = _process_count()
    available = any(
        value is not None
        for value in (cpu_percent, memory_percent, disk_percent, process_count)
    )
    return MonitoringSystemResponse(
        generated_at=now,
        source="container",
        metric_scope="backend container",
        available=available,
        stale=False,
        platform="linux-container" if Path("/proc").exists() else os.name,
        collected_at=now,
        cpu_percent=cpu_percent,
        memory_percent=memory_percent,
        disk_percent=disk_percent,
        process_count=process_count,
        detail=(
            "Container-scoped fallback metrics; run the optional local agent for "
            "Windows host metrics."
            if available
            else "System metrics are unavailable; platform health remains usable."
        ),
    )


async def ingest_agent_telemetry(
    db: AsyncSession,
    user: User,
    payload: AgentTelemetryIngest,
) -> AgentTelemetryIngestResponse:
    global _latest_agent_sample
    received_at = datetime.now(UTC)
    _latest_agent_sample = (payload, received_at)
    from app.services.audit import record_event

    await record_event(
        db,
        action="monitoring.agent_telemetry_ingested",
        actor_id=user.id,
        resource_type="monitoring",
        metadata={
            "agent_id": payload.agent_id,
            "platform": payload.platform,
            "metric_count": sum(
                value is not None
                for value in (
                    payload.cpu_percent,
                    payload.memory_percent,
                    payload.disk_percent,
                    payload.process_count,
                    payload.uptime_seconds,
                )
            ),
        },
    )
    return AgentTelemetryIngestResponse(
        accepted=True,
        received_at=received_at,
        message="Local telemetry sample accepted.",
    )


async def get_asset_watch(db: AsyncSession, user: User) -> MonitoringAssetsResponse:
    investigations = await _accessible_investigations(db, user)
    investigation_ids = [item.id for item in investigations]
    if not investigation_ids:
        return _empty_assets()

    targets = await _models(
        db, select(Target).where(Target.investigation_id.in_(investigation_ids))
    )
    target_ids = [item.id for item in targets]
    findings = await _models(
        db, select(Finding).where(Finding.investigation_id.in_(investigation_ids))
    )
    evidence = await _models(
        db,
        select(InvestigationEvidence).where(
            InvestigationEvidence.investigation_id.in_(investigation_ids)
        ),
    )
    reports = await _models(
        db, select(Report).where(Report.investigation_id.in_(investigation_ids))
    )
    closures = await _models(
        db,
        select(CaseClosure).where(CaseClosure.investigation_id.in_(investigation_ids)),
    )
    scan_jobs = (
        await _models(db, select(ScanJob).where(ScanJob.target_id.in_(target_ids)))
        if target_ids
        else []
    )
    engagement_ids = {
        item.engagement_id for item in investigations if item.engagement_id
    }
    engagements = (
        await _models(
            db,
            select(Engagement).where(Engagement.id.in_(engagement_ids)),
        )
        if engagement_ids
        else []
    )

    targets_by_investigation = _group_by_investigation(targets)
    findings_by_investigation = _group_by_investigation(findings)
    evidence_by_investigation = _group_by_investigation(evidence)
    reports_by_investigation = _group_by_investigation(reports)
    closures_by_investigation = {item.investigation_id: item for item in closures}
    engagements_by_id = {item.id: item for item in engagements}
    evidence_target_ids = {
        item.target_id for item in findings if item.target_id is not None
    } | {
        item.target_id for item in scan_jobs if item.status in {"completed", "partial"}
    }
    stale_cutoff = datetime.now(UTC) - timedelta(days=STALE_TARGET_DAYS)
    items: list[MonitoringAssetItem] = []
    for investigation in investigations:
        inv_targets = targets_by_investigation.get(investigation.id, [])
        inv_findings = findings_by_investigation.get(investigation.id, [])
        inv_evidence = evidence_by_investigation.get(investigation.id, [])
        inv_reports = reports_by_investigation.get(investigation.id, [])
        engagement = (
            engagements_by_id.get(investigation.engagement_id)
            if investigation.engagement_id
            else None
        )
        authorization_status = (
            engagement.authorization_status if engagement else "not_linked"
        )
        stale_targets = sum(
            target.created_at < stale_cutoff and target.id not in evidence_target_ids
            for target in inv_targets
        )
        unresolved_high = sum(
            item.severity == "high" and _finding_unresolved(item)
            for item in inv_findings
        )
        unresolved_critical = sum(
            item.severity == "critical" and _finding_unresolved(item)
            for item in inv_findings
        )
        report_status = _report_status(inv_reports)
        closure = closures_by_investigation.get(investigation.id)
        status = _asset_status(
            investigation,
            authorization_status=authorization_status,
            stale_targets=stale_targets,
            unresolved_high=unresolved_high,
            unresolved_critical=unresolved_critical,
            evidence_count=len(inv_evidence),
        )
        items.append(
            MonitoringAssetItem(
                investigation_id=investigation.id,
                title=investigation.title,
                status=status,
                investigation_status=investigation.status,
                scope_status=investigation.scope_review_status,
                authorization_status=authorization_status,
                targets=len(inv_targets),
                stale_targets=stale_targets,
                unresolved_high=unresolved_high,
                unresolved_critical=unresolved_critical,
                evidence_records=len(inv_evidence),
                report_status=report_status,
                closure_status=closure.status if closure else "not_started",
                action_url=f"/investigations/{investigation.id}",
            )
        )

    recent_cutoff = datetime.now(UTC) - timedelta(hours=24)
    repeated_report_failures = sum(
        report.status == "failed" and report.created_at >= recent_cutoff
        for report in reports
    )
    repeated_ai_degraded = await _recent_ai_degraded_count(
        db, user, investigation_ids, recent_cutoff
    )
    authorization_risks = sum(
        item.authorization_status in {"expired", "revoked"} for item in engagements
    )
    return MonitoringAssetsResponse(
        generated_at=datetime.now(UTC),
        stale_after_days=STALE_TARGET_DAYS,
        investigations=len(investigations),
        targets=len(targets),
        healthy_assets=sum(item.status == "healthy" for item in items),
        assets_needing_review=sum(item.status == "degraded" for item in items),
        stale_assets=sum(item.stale_targets > 0 for item in items),
        high_risk_assets=sum(
            item.unresolved_high + item.unresolved_critical > 0 for item in items
        ),
        out_of_scope_assets=sum(item.scope_status == "out_of_scope" for item in items),
        unresolved_high=sum(item.unresolved_high for item in items),
        unresolved_critical=sum(item.unresolved_critical for item in items),
        findings_by_severity={
            severity: sum(item.severity == severity for item in findings)
            for severity in ("critical", "high", "medium", "low", "info")
        },
        authorization_risks=authorization_risks,
        repeated_report_failures=repeated_report_failures,
        repeated_ai_degraded=repeated_ai_degraded,
        items=sorted(
            items,
            key=lambda item: (
                0
                if item.status == "unavailable"
                else 1
                if item.status == "degraded"
                else 2,
                item.title.lower(),
            ),
        )[:50],
    )


async def get_monitoring_alerts(
    db: AsyncSession,
    user: User,
    *,
    services: MonitoringServicesResponse | None = None,
    system: MonitoringSystemResponse | None = None,
    assets: MonitoringAssetsResponse | None = None,
) -> MonitoringAlertsResponse:
    service_data = services or await get_service_status(None)
    system_data = system or get_system_metrics()
    asset_data = assets or await get_asset_watch(db, user)
    await ensure_default_policies(db)
    policies = {
        item.rule_key: item
        for item in (await db.execute(select(MonitoringPolicy))).scalars().all()
    }
    alerts = _build_alerts(service_data, system_data, asset_data, policies)
    if user.role == "admin":
        from app.services.lan_monitoring import get_lan_alerts

        alerts.extend(await get_lan_alerts(db))
    alerts.extend(await _overdue_remediation_alerts(db, user))
    alerts.extend(await _recon_provider_alerts(db, user))
    tuned_alerts = [_apply_policy(alert, policies) for alert in alerts]
    alerts = [alert for alert in tuned_alerts if alert is not None]
    await _retire_recovered_alerts(db, user, {alert.key for alert in alerts})
    created = existing = 0
    now = datetime.now(UTC)
    active_windows = list(
        (
            await db.execute(
                select(MaintenanceWindow).where(
                    MaintenanceWindow.suppress_alerts.is_(True),
                    MaintenanceWindow.start_time <= now,
                    MaintenanceWindow.end_time > now,
                )
            )
        )
        .scalars()
        .all()
    )
    for alert in alerts:
        policy = policies.get(_policy_key_for_alert(alert))
        cooldown = policy.cooldown_minutes if policy else 1440
        maximum = policy.max_alerts_per_rule if policy else 1
        rule = policy.rule_key if policy else alert.key
        since = now - timedelta(hours=24)
        recent_count = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(Notification)
                    .where(
                        Notification.user_id == user.id,
                        Notification.notification_type == "monitoring_alert",
                        Notification.created_at >= since,
                        Notification.event_metadata["policy_rule"].astext == rule,
                    )
                )
            ).scalar_one()
        )
        bucket = int(now.timestamp() // (cooldown * 60))
        dedupe = policy.dedupe_key if policy else alert.key
        if recent_count >= maximum:
            existing += 1
            notification = (
                (
                    await db.execute(
                        select(Notification)
                        .where(
                            Notification.user_id == user.id,
                            Notification.notification_type == "monitoring_alert",
                            Notification.event_metadata["policy_rule"].astext == rule,
                        )
                        .order_by(Notification.created_at.desc())
                    )
                )
                .scalars()
                .first()
            )
            if notification is None:
                continue
        else:
            result = await create_notification(
                db,
                user_id=user.id,
                actor_user_id=user.id,
                investigation_id=alert.investigation_id,
                notification_type="monitoring_alert",
                severity=alert.severity,
                title=alert.title,
                message=alert.message,
                entity_type="monitoring",
                action_url=alert.action_url,
                metadata={
                    "rule": alert.key,
                    "policy_rule": rule,
                    "category": alert.category,
                    "count": alert.count,
                    "cooldown_minutes": cooldown,
                    "managed_by_overview": True,
                },
                dedupe_key=f"monitoring:{dedupe}:{bucket}:{user.id}",
            )
            notification = result.notification
            created += int(result.created)
            existing += int(not result.created)
        alert.id = notification.id
        active = (
            (
                await db.execute(
                    select(AlertSuppression)
                    .where(
                        AlertSuppression.alert_id == notification.id,
                        AlertSuppression.active.is_(True),
                        or_(
                            AlertSuppression.ends_at.is_(None),
                            AlertSuppression.ends_at > now,
                        ),
                    )
                    .order_by(AlertSuppression.created_at.desc())
                )
            )
            .scalars()
            .first()
        )
        window = next(
            (item for item in active_windows if _window_matches(item, alert)), None
        )
        if window and active is None:
            active = AlertSuppression(
                alert_id=notification.id,
                source="maintenance",
                reason=window.reason,
                starts_at=now,
                ends_at=window.end_time,
                created_by=window.created_by,
                event_metadata={"maintenance_window_id": str(window.id)},
            )
            db.add(active)
            notification.event_metadata = {
                **notification.event_metadata,
                "suppressed": True,
                "suppressed_due_to_maintenance": True,
                "maintenance_window_id": str(window.id),
            }
            await db.flush()
            await record_event(
                db,
                action="monitoring.alert_suppressed",
                actor_id=window.created_by,
                resource_type="notification",
                resource_id=notification.id,
                metadata={
                    "source": "maintenance",
                    "maintenance_window_id": str(window.id),
                },
            )
        if active:
            alert.suppressed = True
            alert.suppressed_due_to_maintenance = active.source == "maintenance"
            alert.suppression_reason = active.reason
    return MonitoringAlertsResponse(
        generated_at=datetime.now(UTC),
        total=len(alerts),
        notifications_created=created,
        notifications_existing=existing,
        items=alerts,
    )


async def get_recent_errors(
    db: AsyncSession,
    user: User,
) -> list[MonitoringRecentError]:
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    accessible = await _accessible_investigations(db, user)
    ids = [item.id for item in accessible]
    filters = [
        AuditLog.created_at >= cutoff,
        AuditLog.action.in_(("report.failed", "ai_analysis.executed")),
    ]
    if user.role != "admin":
        filters.append(
            or_(AuditLog.investigation_id.in_(ids), AuditLog.actor_id == user.id)
        )
    rows = await _models(
        db,
        select(AuditLog).where(*filters).order_by(AuditLog.created_at.desc()).limit(50),
    )
    errors: list[MonitoringRecentError] = []
    for row in rows:
        metadata = row.event_metadata if isinstance(row.event_metadata, dict) else {}
        status = str(metadata.get("status", ""))
        if row.action == "ai_analysis.executed" and status == "completed":
            continue
        if row.action == "ai_analysis.executed" and status not in {
            "provider_unavailable",
            "provider_timeout",
            "provider_failed",
            "malformed_response",
        }:
            continue
        errors.append(
            MonitoringRecentError(
                category="AI degraded"
                if row.action == "ai_analysis.executed"
                else "Report failure",
                action=row.action,
                occurred_at=row.created_at,
                investigation_id=row.investigation_id,
            )
        )
    return errors[:10]


def _build_alerts(
    services: MonitoringServicesResponse,
    system: MonitoringSystemResponse,
    assets: MonitoringAssetsResponse,
    policies: dict[str, MonitoringPolicy] | None = None,
) -> list[MonitoringAlert]:
    alerts: list[MonitoringAlert] = []
    for item in services.items:
        if item.key == "docker" or item.status == "healthy":
            continue
        severity: MonitoringSeverity = (
            "critical" if item.status == "unavailable" else "warning"
        )
        alerts.append(
            MonitoringAlert(
                key=f"service:{item.key}:{item.status}",
                severity=severity,
                title=f"{item.label} needs attention",
                message=item.detail,
                category="service",
                action_url="/monitoring",
            )
        )
    for key, label, value, policy_key in (
        ("cpu", "CPU", system.cpu_percent, "cpu_threshold"),
        ("memory", "Memory", system.memory_percent, "memory_threshold"),
        ("disk", "Disk", system.disk_percent, "disk_threshold"),
    ):
        threshold = float(
            getattr((policies or {}).get(policy_key), "threshold_value", 90) or 90
        )
        if value is not None and value >= threshold:
            alerts.append(
                MonitoringAlert(
                    key=f"system:{key}:high",
                    severity="critical" if value >= 95 else "warning",
                    title=f"High {label} utilization",
                    message=f"{label} utilization is {value:.1f}% on the monitored {system.metric_scope}.",
                    category="system",
                    action_url="/monitoring",
                )
            )
    if assets.unresolved_high or assets.unresolved_critical:
        alerts.append(
            MonitoringAlert(
                key="assets:unresolved-high-risk",
                severity="critical" if assets.unresolved_critical else "warning",
                title="Unresolved high-risk findings",
                message=(
                    f"{assets.unresolved_critical} critical and "
                    f"{assets.unresolved_high} high findings need review."
                ),
                category="risk",
                action_url="/monitoring",
                count=max(1, assets.unresolved_high + assets.unresolved_critical),
            )
        )
    if assets.stale_assets:
        alerts.append(
            MonitoringAlert(
                key="assets:stale-targets",
                severity="warning",
                title="Stale targets need evidence",
                message=f"{assets.stale_assets} accessible investigations contain stale targets without collected evidence.",
                category="asset",
                action_url="/monitoring",
                count=assets.stale_assets,
            )
        )
    if assets.out_of_scope_assets:
        alerts.append(
            MonitoringAlert(
                key="assets:out-of-scope",
                severity="critical",
                title="Out-of-scope assets need review",
                message=f"{assets.out_of_scope_assets} accessible investigations are marked out of scope.",
                category="governance",
                action_url="/monitoring",
                count=assets.out_of_scope_assets,
            )
        )
    if assets.authorization_risks:
        alerts.append(
            MonitoringAlert(
                key="assets:authorization-risk",
                severity="critical",
                title="Authorization is expired or revoked",
                message=f"{assets.authorization_risks} engagement authorizations need immediate review.",
                category="governance",
                action_url="/engagements",
                count=assets.authorization_risks,
            )
        )
    if assets.repeated_report_failures >= 2:
        alerts.append(
            MonitoringAlert(
                key="reports:repeated-failures",
                severity="warning",
                title="Repeated report failures",
                message=f"{assets.repeated_report_failures} report generations failed in the last 24 hours.",
                category="report",
                action_url="/reports",
                count=assets.repeated_report_failures,
            )
        )
    if assets.repeated_ai_degraded >= 2:
        alerts.append(
            MonitoringAlert(
                key="ai:repeated-degraded",
                severity="warning",
                title="Repeated AI degraded responses",
                message=f"{assets.repeated_ai_degraded} AI requests used a degraded provider state in the last 24 hours.",
                category="ai",
                action_url="/monitoring",
                count=assets.repeated_ai_degraded,
            )
        )
    return alerts


def _policy_key_for_alert(alert: MonitoringAlert) -> str:
    key = alert.key
    if key.startswith("system:cpu:"):
        return "cpu_threshold"
    if key.startswith("system:memory:"):
        return "memory_threshold"
    if key.startswith("system:disk:"):
        return "disk_threshold"
    if "agent_stale" in key:
        return "stale_agent"
    if ":offline" in key:
        return "offline_asset"
    if "risky_service" in key or "ssh_nonstandard" in key:
        return "risky_service"
    if ":unauthorized" in key:
        return "unauthorized_asset"
    if ":coverage" in key or ":unmanaged" in key:
        return "weak_coverage"
    if key == "assets:unresolved-high-risk":
        return "high_critical_finding"
    if key == "remediation:overdue":
        return "overdue_remediation"
    if key == "recon:provider-repeated-failure":
        return "recon_provider_failure"
    return key


def _apply_policy(
    alert: MonitoringAlert, policies: dict[str, MonitoringPolicy]
) -> MonitoringAlert | None:
    policy = policies.get(_policy_key_for_alert(alert))
    if policy is None:
        return alert
    if not policy.enabled:
        return alert if alert.severity == "critical" else None
    if policy.severity_override and alert.severity != "critical":
        # Critical alerts stay visible and critical until explicitly suppressed.
        alert.severity = cast(MonitoringSeverity, policy.severity_override)
    return alert


def _window_matches(window: MaintenanceWindow, alert: MonitoringAlert) -> bool:
    assets = set(window.affected_assets or [])
    services = set(window.affected_services or [])
    asset_match = (
        not assets
        or "*" in assets
        or (
            alert.investigation_id is not None and str(alert.investigation_id) in assets
        )
    )
    service_match = (
        not services
        or "*" in services
        or alert.category in services
        or any(value in alert.key for value in services)
    )
    return asset_match and service_match


async def _overdue_remediation_alerts(
    db: AsyncSession, user: User
) -> list[MonitoringAlert]:
    today = datetime.now(UTC).date()
    statement = (
        select(func.count())
        .select_from(VulnerabilityBaselineFinding)
        .where(
            VulnerabilityBaselineFinding.remediation_due_date < today,
            VulnerabilityBaselineFinding.status.in_(
                ("open", "acknowledged", "in_progress")
            ),
        )
    )
    if user.role != "admin":
        accessible = await _accessible_investigations(db, user)
        statement = statement.where(
            VulnerabilityBaselineFinding.investigation_id.in_(
                [item.id for item in accessible]
            )
        )
    count = int((await db.execute(statement)).scalar_one())
    if not count:
        return []
    return [
        MonitoringAlert(
            key="remediation:overdue",
            severity="critical",
            title="Overdue remediation",
            message=f"{count} baseline remediation items are overdue.",
            category="remediation",
            action_url="/monitoring",
            count=count,
        )
    ]


async def _recon_provider_alerts(db: AsyncSession, user: User) -> list[MonitoringAlert]:
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    filters = [AuditLog.action == "recon.executed", AuditLog.created_at >= cutoff]
    if user.role != "admin":
        accessible = await _accessible_investigations(db, user)
        filters.append(AuditLog.investigation_id.in_([item.id for item in accessible]))
    rows = list((await db.execute(select(AuditLog).where(*filters))).scalars().all())
    failures: list[tuple[str, str]] = []
    for row in rows:
        metadata = row.event_metadata if isinstance(row.event_metadata, dict) else {}
        for item in metadata.get("provider_failures", []):
            if isinstance(item, dict) and item.get("code") in {
                "provider_timeout",
                "provider_http_error",
                "provider_parse_error",
            }:
                failures.append(
                    (str(item.get("source", "provider")), str(item["code"]))
                )
    if len(failures) < 2:
        return []
    providers = ", ".join(sorted({source for source, _ in failures}))
    return [
        MonitoringAlert(
            key="recon:provider-repeated-failure",
            severity="warning",
            title="Repeated passive recon provider failures",
            message=f"{len(failures)} sanitized provider failures were recorded in 24 hours ({providers}). Valid stored entities were preserved.",
            category="recon",
            source="recon",
            action_url="/investigations",
        )
    ]


def _health_service(
    key: str,
    label: str,
    checks: dict[str, Any],
) -> MonitoringServiceStatus:
    check = _safe_mapping(checks.get(key))
    status = _monitoring_status(check.get("status"))
    detail = str(check.get("detail") or f"{label} status is {status}.")
    return MonitoringServiceStatus(key=key, label=label, status=status, detail=detail)


def _docker_service_status() -> MonitoringServiceStatus:
    socket = Path("/var/run/docker.sock")
    if socket.exists():
        return MonitoringServiceStatus(
            key="docker",
            label="Docker services",
            status="degraded",
            detail="Docker socket is present, but direct host inspection is intentionally disabled.",
            metadata={"accessible": False},
        )
    return MonitoringServiceStatus(
        key="docker",
        label="Docker services",
        status="degraded",
        detail="Docker host metrics are not mounted; use docker compose ps locally.",
        metadata={"accessible": False},
    )


def _monitoring_status(value: object) -> MonitoringStatus:
    if value in {"ok", "healthy"}:
        return "healthy"
    if value == "degraded":
        return "degraded"
    return "unavailable"


def _safe_mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_short_text(value: object) -> str | None:
    return str(value)[:80] if value else None


def _container_cpu_percent() -> float | None:
    try:
        load = os.getloadavg()[0]
        cpus = max(1, os.cpu_count() or 1)
        return round(min(100.0, max(0.0, load / cpus * 100)), 1)
    except (AttributeError, OSError):
        return None


def _container_memory_percent() -> float | None:
    try:
        current_path = Path("/sys/fs/cgroup/memory.current")
        maximum_path = Path("/sys/fs/cgroup/memory.max")
        if current_path.exists() and maximum_path.exists():
            current = int(current_path.read_text(encoding="utf-8").strip())
            maximum_text = maximum_path.read_text(encoding="utf-8").strip()
            if maximum_text != "max":
                maximum = int(maximum_text)
                if maximum > 0:
                    return round(min(100.0, current / maximum * 100), 1)
        values: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            name, raw = line.split(":", 1)
            values[name] = int(raw.strip().split()[0])
        total = values.get("MemTotal", 0)
        available = values.get("MemAvailable", 0)
        if total > 0:
            return round(min(100.0, max(0.0, (total - available) / total * 100)), 1)
    except (OSError, ValueError):
        return None
    return None


def _disk_percent(path: Path) -> float | None:
    try:
        usage = shutil.disk_usage(path if path.exists() else Path("/"))
        return round(usage.used / usage.total * 100, 1) if usage.total else None
    except OSError:
        return None


def _process_count() -> int | None:
    try:
        return sum(item.name.isdigit() for item in Path("/proc").iterdir())
    except OSError:
        return None


async def _accessible_investigations(
    db: AsyncSession,
    user: User,
) -> list[Investigation]:
    statement = select(Investigation)
    if user.role != "admin":
        statement = statement.join(
            InvestigationMember,
            InvestigationMember.investigation_id == Investigation.id,
        ).where(InvestigationMember.user_id == user.id)
    result = await db.execute(statement.order_by(Investigation.updated_at.desc()))
    return list(result.scalars().unique().all())


async def _models[T](db: AsyncSession, statement: Select[tuple[T]]) -> list[T]:
    result = await db.execute(statement)
    return list(result.scalars().all())


def _group_by_investigation(items: list[Any]) -> dict[uuid.UUID, list[Any]]:
    grouped: dict[uuid.UUID, list[Any]] = defaultdict(list)
    for item in items:
        grouped[item.investigation_id].append(item)
    return dict(grouped)


def _finding_unresolved(finding: Finding) -> bool:
    return finding.status in UNRESOLVED_FINDING_STATUSES


def _report_status(reports: list[Report]) -> str:
    if any(item.status == "failed" for item in reports):
        return "failed"
    if any(item.status == "ready" for item in reports):
        return "ready"
    if reports:
        return reports[-1].status
    return "not_generated"


def _asset_status(
    investigation: Investigation,
    *,
    authorization_status: str,
    stale_targets: int,
    unresolved_high: int,
    unresolved_critical: int,
    evidence_count: int,
) -> MonitoringStatus:
    if (
        investigation.scope_review_status == "out_of_scope"
        or authorization_status in {"expired", "revoked"}
        or unresolved_critical > 0
    ):
        return "unavailable"
    if (
        investigation.scope_review_status in {"not_reviewed", "pending_review"}
        or stale_targets > 0
        or unresolved_high > 0
        or evidence_count == 0
    ):
        return "degraded"
    return "healthy"


async def _recent_ai_degraded_count(
    db: AsyncSession,
    user: User,
    investigation_ids: list[uuid.UUID],
    cutoff: datetime,
) -> int:
    filters = [
        AuditLog.action == "ai_analysis.executed",
        AuditLog.created_at >= cutoff,
    ]
    if user.role != "admin":
        filters.append(
            or_(
                AuditLog.investigation_id.in_(investigation_ids),
                AuditLog.actor_id == user.id,
            )
        )
    rows = await _models(db, select(AuditLog).where(*filters))
    return sum(
        isinstance(item.event_metadata, dict)
        and item.event_metadata.get("status")
        in {
            "provider_unavailable",
            "provider_timeout",
            "provider_failed",
            "malformed_response",
        }
        for item in rows
    )


def _empty_assets() -> MonitoringAssetsResponse:
    return MonitoringAssetsResponse(
        generated_at=datetime.now(UTC),
        stale_after_days=STALE_TARGET_DAYS,
        investigations=0,
        targets=0,
        healthy_assets=0,
        assets_needing_review=0,
        stale_assets=0,
        high_risk_assets=0,
        out_of_scope_assets=0,
        unresolved_high=0,
        unresolved_critical=0,
        findings_by_severity={
            severity: 0 for severity in ("critical", "high", "medium", "low", "info")
        },
        authorization_risks=0,
        repeated_report_failures=0,
        repeated_ai_degraded=0,
        items=[],
    )


def _overall_monitoring_status(
    services: MonitoringServicesResponse,
    alerts: MonitoringAlertsResponse,
) -> MonitoringStatus:
    del alerts
    if services.status == "unavailable":
        return "unavailable"
    if services.status == "degraded":
        return "degraded"
    return "healthy"


async def _retire_recovered_alerts(
    db: AsyncSession, user: User, active_keys: set[str]
) -> None:
    now = datetime.now(UTC)
    rows = list(
        (
            await db.execute(
                select(Notification).where(
                    Notification.user_id == user.id,
                    Notification.notification_type == "monitoring_alert",
                    Notification.status == "unread",
                    Notification.event_metadata["managed_by_overview"].astext == "true",
                )
            )
        )
        .scalars()
        .all()
    )
    for notification in rows:
        metadata = (
            notification.event_metadata
            if isinstance(notification.event_metadata, dict)
            else {}
        )
        if metadata.get("rule") in active_keys:
            continue
        notification.status = "dismissed"
        notification.dismissed_at = now
        notification.event_metadata = {**metadata, "recovered_at": now.isoformat()}


def _reset_agent_telemetry_for_tests() -> None:
    global _latest_agent_sample
    _latest_agent_sample = None
