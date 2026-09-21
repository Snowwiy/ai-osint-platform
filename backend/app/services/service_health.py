"""Explainable, advisory service classifications. No network or process actions live here."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_management import AssetGroupMembership, ExpectedServiceBaseline

Severity = Literal["healthy", "warning", "critical", "neutral"]
Expectation = Literal["expected", "allowed", "unexpected", "unclassified"]


@dataclass(frozen=True)
class ServiceAssessment:
    severity: Severity
    expectation: Expectation
    reason: str


@dataclass(frozen=True)
class LanServiceBaseline:
    expected_ports: frozenset[int] = frozenset()
    allowed_ports: frozenset[int] = frozenset()
    critical_ports: frozenset[int] = frozenset()
    configured: bool = False


async def lan_baseline(db: AsyncSession, asset_id: uuid.UUID) -> LanServiceBaseline:
    groups = select(AssetGroupMembership.group_id).where(AssetGroupMembership.asset_id == asset_id)
    rows = list((await db.execute(select(ExpectedServiceBaseline).where(
        (ExpectedServiceBaseline.asset_id == asset_id) |
        (ExpectedServiceBaseline.group_id.in_(groups))
    ))).scalars().all())
    return LanServiceBaseline(
        frozenset(port for row in rows for port in row.expected_ports),
        frozenset(port for row in rows for port in row.allowed_ports),
        frozenset(port for row in rows for port in row.critical_ports),
        bool(rows),
    )


def assess_lan_service(
    *,
    port: int,
    status: str,
    device_type: str,
    os_family: str,
    trust_state: str,
    service_name: str | None,
    non_standard_ssh: bool,
    expected_ports: set[int],
    allowed_ports: set[int],
    has_baseline: bool,
    critical_ports: set[int] | None = None,
) -> ServiceAssessment:
    """An open port is evidence of reachability, never proof of a vulnerability."""
    expectation: Expectation = (
        "expected" if port in expected_ports else
        "allowed" if port in allowed_ports else
        "unexpected" if has_baseline else "unclassified"
    )
    if status != "open":
        if expectation == "expected" and status == "closed":
            return ServiceAssessment("warning", expectation, f"Expected TCP/{port} is currently closed; confirm the service locally.")
        return ServiceAssessment("neutral", expectation, f"TCP/{port} was observed {status}; no reachable service was confirmed.")
    if expectation in {"expected", "allowed"}:
        return ServiceAssessment("healthy", expectation, f"TCP/{port} is reachable and matches the configured {expectation}-service baseline.")
    if port in (critical_ports or set()):
        return ServiceAssessment("critical", expectation, f"TCP/{port} is reachable from the authorized LAN and policy explicitly marks this exposure critical; review access manually.")
    if expectation == "unexpected":
        return ServiceAssessment("warning", expectation, f"TCP/{port} is reachable from the authorized LAN but is not in this asset's expected or allowed service baseline.")
    if device_type in {"mobile", "tablet"}:
        return ServiceAssessment("warning", expectation, f"TCP/{port} is reachable on a {device_type}; confirm whether a listening service is intended. Mobile visibility is limited.")
    if non_standard_ssh or (service_name == "ssh" and port != 22):
        return ServiceAssessment("warning", expectation, f"Possible SSH is reachable on non-standard TCP/{port}; verify the intended service and access manually.")
    if port in {5432, 6379}:
        return ServiceAssessment("warning", expectation, f"Database service TCP/{port} is reachable from the authorized LAN; confirm its access policy and intended clients.")
    if port == 3389:
        return ServiceAssessment("warning", expectation, "RDP is reachable from the authorized LAN; confirm that remote desktop access is intended.")
    if port == 445 and os_family == "windows":
        return ServiceAssessment("neutral", expectation, "SMB is reachable on a Windows device; review sharing policy if this is unexpected.")
    if device_type in {"router", "network_device"} and port in {53, 80, 443, 8080, 8443}:
        return ServiceAssessment("neutral", expectation, "A common network-device service is reachable; confirm its management exposure manually.")
    if trust_state in {"unauthorized", "needs_review"} and port in {22, 23, 445, 5900}:
        return ServiceAssessment("warning", expectation, f"TCP/{port} is reachable on a device needing trust review; verify ownership and intended access.")
    if device_type == "unknown":
        return ServiceAssessment("neutral", expectation, f"TCP/{port} is reachable; device type and service intent need review before assigning risk.")
    return ServiceAssessment("neutral", expectation, f"TCP/{port} is reachable; no configured baseline or deterministic risk rule assigns severity.")


def assess_local_service(
    state: str, *, expected_state: str | None = None,
    required: bool = False, criticality: str = "medium", stale: bool = False,
) -> ServiceAssessment:
    if stale:
        return ServiceAssessment("warning", "unclassified", "Service inventory has not refreshed within the expected interval.")
    if state in {"starting", "stopping", "paused"}:
        return ServiceAssessment("warning", "unclassified", f"Service is {state}; wait for a stable state or review it locally.")
    if expected_state is None:
        return ServiceAssessment("neutral", "unclassified", "No expected state is configured for this service.")
    if state == expected_state:
        return ServiceAssessment("healthy" if state == "running" else "neutral", "expected", "Service state matches the configured baseline.")
    if expected_state == "running" and state == "stopped" and (required or criticality == "critical"):
        return ServiceAssessment("critical", "expected", "Required or critical expected service is not running.")
    return ServiceAssessment("warning", "expected", "Service state differs from the configured baseline.")


def assess_core_service(status: str, *, required: bool, stale: bool = False) -> ServiceAssessment:
    if stale:
        return ServiceAssessment("warning", "expected", "Telemetry has not been refreshed within the expected interval.")
    if status in {"healthy", "running", "connected"}:
        return ServiceAssessment("healthy", "expected", "Required component is reporting healthy." if required else "Component is reporting healthy.")
    if status in {"unavailable", "down", "stopped", "offline"}:
        return ServiceAssessment("critical" if required else "warning", "expected", "Required component is unavailable." if required else "Optional component is unavailable.")
    return ServiceAssessment("warning" if required else "neutral", "unclassified", "Component health is unknown; confirm its status manually.")
