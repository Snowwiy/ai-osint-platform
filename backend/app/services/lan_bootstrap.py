from __future__ import annotations

from datetime import UTC, datetime
import ipaddress
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent_management import AgentEnrollmentToken
from app.models.lan_monitoring import LanAsset
from app.models.user import User
from app.schemas.lan_monitoring import LanBootstrapRequest, LanBootstrapStatus
from app.services.agent_management import list_agents
from app.services.endpoint_posture import get_posture_overview
from app.services.health import _migration_head
from app.services.lan_monitoring import (
    configured_networks,
    configured_service_ports,
    normalize_private_cidr,
)
from app.services.monitoring_runtime import get_monitoring_startup_status
from app.services.release import get_release_metadata


async def verify_lan_bootstrap(
    db: AsyncSession,
    redis: Any,
    user: User,
    body: LanBootstrapRequest,
) -> LanBootstrapStatus:
    """Verify local LAN readiness without starting discovery or service checks."""
    network, gateway = normalize_private_cidr(body.cidr, body.gateway_hint)
    configured = configured_networks()
    activation_matches = any(network == allowed for allowed in configured)
    startup = await get_monitoring_startup_status(db, redis, user)
    agents = await list_agents(db)
    posture = await get_posture_overview(db, user)
    now = datetime.now(UTC)
    active_tokens = int(
        (
            await db.execute(
                select(func.count(AgentEnrollmentToken.id)).where(
                    AgentEnrollmentToken.revoked_at.is_(None),
                    AgentEnrollmentToken.expires_at > now,
                )
            )
        ).scalar_one()
    )
    assets_total, static_router = (
        await db.execute(
            select(
                func.count(LanAsset.id),
                func.count(LanAsset.id).filter(LanAsset.source.in_(("static", "router"))),
            )
        )
    ).one()
    fresh_agents = sum(item.telemetry_fresh for item in agents.items)
    release = await get_release_metadata(db)
    agent_backend = _safe_agent_backend_url(settings.LOCAL_BACKEND_URL)
    env_lines = _bootstrap_env_lines(str(network), str(gateway))
    next_action = _next_action(
        activation_matches=activation_matches,
        lan_enabled=settings.LAN_MONITORING_ENABLED,
        service_enabled=settings.LAN_SERVICE_CHECK_ENABLED,
        observation_available=bool(static_router or agents.total),
        token_available=active_tokens > 0,
    )
    return LanBootstrapStatus(
        verified_at=now,
        input_cidr=body.cidr,
        normalized_cidr=str(network),
        gateway_hint=str(gateway),
        private_cidr_valid=True,
        configured_cidr_matches=activation_matches,
        backend_reachable=True,
        migrations_ready=release.migration_version == _migration_head(),
        release_version=release.version,
        lan_monitoring_enabled=settings.LAN_MONITORING_ENABLED,
        service_check_enabled=(settings.LAN_MONITORING_ENABLED and settings.LAN_SERVICE_CHECK_ENABLED),
        ping_enabled=settings.LAN_DISCOVERY_PING_ENABLED,
        configured_ports=configured_service_ports(),
        active_enrollment_tokens=active_tokens,
        enrollment_capability_ready=settings.LAN_MONITORING_ENABLED,
        assets_total=int(assets_total or 0),
        static_router_observations=int(static_router or 0),
        agents_total=agents.total,
        fresh_agents=fresh_agents,
        assessed_posture=posture.assessed_assets,
        open_recommendations=posture.open_recommendations,
        observation_path_available=bool(static_router or agents.total),
        env_lines=env_lines,
        windows_agent_command=(
            f".\\scripts\\local\\local_monitor_agent.ps1 -Mode LanEndpoint "
            f"-BackendUrl {agent_backend} -IntervalSeconds 30 "
            "# paste <ENROLLMENT_TOKEN> only at the secure prompt"
        ),
        linux_agent_command=(
            "python scripts/local/local_monitor_agent.py --backend-url "
            f"{agent_backend} --interval-seconds 30 "
            "# paste <ENROLLMENT_TOKEN> only at the secure prompt"
        ),
        steps=[
            "Validate the bound repository path in desktop setup.",
            "Confirm Docker/backend readiness and release 5.0.0-rc6.",
            f"Review the normalized authorized CIDR {network} and gateway hint {gateway}.",
            "Copy the non-secret .env guidance, then restart the local platform manually.",
            "Create a short-lived CIDR-limited enrollment token and copy its one-time value.",
            "Run an endpoint helper manually and verify its first heartbeat.",
            "Import an approved router/static observation if Docker cannot see neighbors.",
            "Run service checks only for an authorized monitored asset when configuration allows.",
            "Review advisory posture, recommendations, and alerts.",
        ],
        next_action=next_action,
        safety_notes=[
            "Verification refreshed stored monitoring summaries only; discovery and service checks were not run.",
            "Only private RFC1918 CIDRs within the configured host limit are accepted.",
            "No router connection, authentication, credential testing, brute force, exploit payload, or remote command is used.",
            startup.message,
        ],
    )


def _bootstrap_env_lines(cidr: str, gateway: str) -> list[str]:
    return [
        "DESKTOP_AUTO_MONITORING_ENABLED=true",
        "MONITORING_AUTO_REFRESH_ENABLED=true",
        "MONITORING_AUTO_REFRESH_SECONDS=30",
        "SERVER_HOST_METRICS_ENABLED=true",
        "SERVER_HOST_METRICS_INTERVAL_SECONDS=30",
        "LAN_ENDPOINT_AGENT_INTERVAL_SECONDS=30",
        "POSTURE_RECOMPUTE_INTERVAL_SECONDS=300",
        "LAN_MONITORING_ENABLED=true",
        f"LAN_ALLOWED_CIDRS={cidr}",
        f"LAN_GATEWAY_HINT={gateway}",
        "LAN_DISCOVERY_PING_ENABLED=true",
        "LAN_SERVICE_CHECK_ENABLED=true",
        "LAN_AUTO_DISCOVERY_ON_START=false",
        "LAN_AUTO_SERVICE_CHECK_ON_START=false",
        "LAN_AUTO_DISCOVERY_INTERVAL_SECONDS=300",
        "LAN_AUTO_SERVICE_CHECK_INTERVAL_SECONDS=600",
        "LAN_SERVICE_CHECK_PORTS=22,80,443,445,3389,8080,8443,3000,5000,5432,6379,8000,9000",
        "LAN_SERVICE_CHECK_TIMEOUT_SECONDS=2",
        "LAN_SERVICE_CHECK_MAX_HOSTS=256",
        "LAN_SERVICE_CHECK_MAX_PORTS=32",
        "LAN_REJECT_PUBLIC_CIDRS=true",
        "LAN_SSH_BANNER_DETECTION_ENABLED=true",
    ]


def _safe_agent_backend_url(value: str) -> str:
    """Use a configured private/local backend URL, otherwise retain localhost."""
    fallback = "http://localhost:8000"
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if parsed.scheme != "http" or not host or parsed.username or parsed.password:
            return fallback
        local_host = host.lower() == "localhost"
        private_ip = ipaddress.ip_address(host).is_private if not local_host else True
        if not private_ip:
            return fallback
        port = parsed.port or 8000
    except (ValueError, UnicodeError):
        return fallback
    formatted_host = f"[{host}]" if ":" in host else host
    return f"http://{formatted_host}:{port}"


def _next_action(
    *,
    activation_matches: bool,
    lan_enabled: bool,
    service_enabled: bool,
    observation_available: bool,
    token_available: bool,
) -> str:
    if not activation_matches or not lan_enabled:
        return "Copy the reviewed .env lines and restart the local Docker services manually."
    if not token_available:
        return "Create a short-lived enrollment token for 192.168.50.0/24."
    if not observation_available:
        return "Run an approved endpoint agent or import one manual router/static observation."
    if not service_enabled:
        return "Enable bounded TCP service checks only if locally authorized."
    return "Review agent freshness, service observations, posture recommendations, and alerts."
