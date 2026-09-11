from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.schemas.monitoring import MonitoringStartupStatus
from app.services.agent_management import list_agents
from app.services.endpoint_posture import get_posture_overview
from app.services.lan_monitoring import get_monitoring_activation
from app.services.local_monitoring import get_monitoring_overview
from app.services.monitoring_triage import list_triage
from app.services.vulnerability_baseline import get_baseline_overview


async def get_monitoring_startup_status(
    db: AsyncSession,
    redis: Any,
    user: User,
) -> MonitoringStartupStatus:
    """Load local monitoring summaries without initiating network observations."""
    overview = await get_monitoring_overview(db, redis, user)
    activation = get_monitoring_activation()
    baseline = await get_baseline_overview(db, user)
    triage = await list_triage(
        db,
        user,
        status=None,
        severity=None,
        source=None,
        asset_id=None,
        limit=1,
        offset=0,
    )

    agent_total: int | None = None
    agent_covered: int | None = None
    assessed_posture: int | None = None
    open_recommendations: int | None = None
    if user.role == "admin":
        agents = await list_agents(db)
        posture = await get_posture_overview(db, user)
        agent_total = agents.total
        agent_covered = agents.coverage.monitored_by_agent
        assessed_posture = posture.assessed_assets
        open_recommendations = posture.open_recommendations

    enabled = (
        settings.DESKTOP_AUTO_MONITORING_ENABLED
        and settings.MONITORING_AUTO_REFRESH_ENABLED
    )
    now = datetime.now(UTC)
    lan_enabled = settings.LAN_MONITORING_ENABLED
    service_enabled = lan_enabled and settings.LAN_SERVICE_CHECK_ENABLED
    message = (
        "Monitoring loaded."
        if lan_enabled
        else "Monitoring ready, LAN discovery disabled by configuration."
    )
    return MonitoringStartupStatus(
        generated_at=now,
        next_refresh_at=(
            now + timedelta(seconds=settings.MONITORING_AUTO_REFRESH_SECONDS)
            if enabled
            else None
        ),
        status="loaded" if settings.DESKTOP_AUTO_MONITORING_ENABLED else "disabled",
        message=message,
        platform_status=overview.status,
        release_version=overview.release_version,
        desktop_auto_monitoring_enabled=settings.DESKTOP_AUTO_MONITORING_ENABLED,
        auto_refresh_enabled=enabled,
        auto_refresh_seconds=settings.MONITORING_AUTO_REFRESH_SECONDS,
        lan_monitoring_enabled=lan_enabled,
        service_check_enabled=service_enabled,
        lan_auto_discovery_on_start=(
            lan_enabled and settings.LAN_AUTO_DISCOVERY_ON_START
        ),
        lan_auto_service_check_on_start=(
            service_enabled and settings.LAN_AUTO_SERVICE_CHECK_ON_START
        ),
        lan_auto_discovery_interval_seconds=(
            settings.LAN_AUTO_DISCOVERY_INTERVAL_SECONDS
        ),
        lan_auto_service_check_interval_seconds=(
            settings.LAN_AUTO_SERVICE_CHECK_INTERVAL_SECONDS
        ),
        allowed_cidrs=activation.allowed_cidrs,
        service_ports=activation.service_ports,
        discovery_disabled_reason=activation.discovery_disabled_reason,
        service_check_disabled_reason=activation.service_check_disabled_reason,
        services_total=len(overview.services.items),
        active_alerts=overview.alerts.total,
        alerts_created=overview.alerts.notifications_created,
        triage_total=triage.total,
        agent_total=agent_total,
        agent_covered=agent_covered,
        assessed_posture=assessed_posture,
        open_recommendations=open_recommendations,
        baseline_total=baseline.total,
        baseline_open=baseline.open + baseline.acknowledged + baseline.in_progress,
        docker_limitation=activation.docker_limitation,
        safety_notes=[
            "Automatic refresh reads local summaries only; it does not start discovery or TCP checks.",
            "LAN actions remain restricted to configured RFC1918 CIDRs, bounded ports, limits, timeouts, and intervals.",
            "No authentication, brute force, credential testing, remote command, or public scan is performed.",
        ],
    )
