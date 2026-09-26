from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ActionDefinition:
    action_id: str
    display_name: str
    description: str
    risk_level: Literal["low", "medium", "high", "blocked"]
    required_role: Literal["analyst", "admin"]
    executor: Literal["backend_fixed", "desktop_native"]
    target_type: str
    expected_effect: str
    possible_impact: str
    rollback_guidance: str


_DEFINITIONS = (
    ActionDefinition(
        "raventech.service.start",
        "Start local service",
        "Start one enumerated service on this RavenTech host.",
        "medium",
        "admin",
        "desktop_native",
        "local_service",
        "The selected local service reaches running state.",
        "Dependent local applications may become available.",
        "Stop the same service through a new approved action if appropriate.",
    ),
    ActionDefinition(
        "raventech.service.stop",
        "Stop local service",
        "Stop one enumerated, unprotected service on this RavenTech host.",
        "high",
        "admin",
        "desktop_native",
        "local_service",
        "The selected local service reaches stopped state.",
        "Applications depending on this service may be disrupted.",
        "Start the same service through a new approved action if appropriate.",
    ),
    ActionDefinition(
        "raventech.service.restart",
        "Restart local service",
        "Restart one enumerated, unprotected service on this RavenTech host.",
        "medium",
        "admin",
        "desktop_native",
        "local_service",
        "The selected local service returns to running state.",
        "A brief interruption may affect dependent local applications.",
        "A new approved start action may restore service if it remains stopped.",
    ),
    ActionDefinition(
        "raventech.process.terminate",
        "Terminate local process",
        "Terminate one selected non-protected local process after identity "
        "revalidation.",
        "high",
        "admin",
        "desktop_native",
        "local_process",
        "The selected process exits.",
        "Unsaved work in the selected process may be lost.",
        "Restart the application manually if needed.",
    ),
    ActionDefinition(
        "raventech.alert.acknowledge",
        "Acknowledge alert",
        "Mark one existing RavenTech monitoring alert as read.",
        "low",
        "analyst",
        "backend_fixed",
        "alert",
        "The selected alert is acknowledged for this user.",
        "The alert remains in history and may still be visible to other users.",
        "Review the alert history; acknowledgement does not change underlying "
        "system state.",
    ),
    ActionDefinition(
        "raventech.lan.asset.authorize",
        "Authorize LAN asset",
        "Authorize one existing discovered asset for configured monitoring.",
        "medium",
        "admin",
        "backend_fixed",
        "lan_asset",
        "The selected asset becomes authorized.",
        "Authorized assets can receive only configured bounded private-LAN "
        "observations.",
        "Set the asset to needs review with a new approved action.",
    ),
    ActionDefinition(
        "raventech.lan.asset.reject",
        "Reject LAN asset",
        "Mark one existing discovered asset unauthorized and disable its monitoring.",
        "medium",
        "admin",
        "backend_fixed",
        "lan_asset",
        "The selected asset is unauthorized and monitoring is disabled.",
        "Existing stored history is retained.",
        "Authorize the asset with a new approved action after review.",
    ),
    ActionDefinition(
        "raventech.lan.asset.needs_review",
        "Return asset to review",
        "Remove authorization from one existing discovered LAN asset.",
        "low",
        "admin",
        "backend_fixed",
        "lan_asset",
        "The selected asset returns to review state.",
        "Monitoring follows the asset configuration and authorization policy.",
        "Authorize it again with a new approved action after review.",
    ),
    ActionDefinition(
        "raventech.lan.discovery.run",
        "Run bounded LAN discovery",
        "Queue existing discovery for configured authorized private CIDRs only.",
        "low",
        "admin",
        "backend_fixed",
        "configured_lan",
        "A registered bounded discovery job is queued.",
        "Only configured private ranges and existing limits are used.",
        "No rollback is needed; review observations and trust decisions.",
    ),
    ActionDefinition(
        "raventech.lan.services.refresh",
        "Refresh asset services",
        "Queue existing bounded TCP observations for one authorized LAN asset.",
        "low",
        "admin",
        "backend_fixed",
        "lan_asset",
        "A registered bounded service-observation job is queued.",
        "Configured ports, timeouts, and authorized private-address rules apply.",
        "No rollback is needed; observations are historical records.",
    ),
    ActionDefinition(
        "raventech.posture.recompute",
        "Recompute asset posture",
        "Queue deterministic posture assessment for one existing LAN asset.",
        "low",
        "admin",
        "backend_fixed",
        "lan_asset",
        "A registered posture job is queued.",
        "Stored posture recommendations may be refreshed.",
        "Recompute again after correcting source telemetry.",
    ),
    ActionDefinition(
        "raventech.job.retry",
        "Retry safe internal job",
        "Retry one failed job whose type is in the fixed native handler registry.",
        "medium",
        "admin",
        "backend_fixed",
        "background_job",
        "The selected allowlisted job is queued for a bounded retry.",
        "The job may repeat an idempotent application operation.",
        "Cancel the queued job before it starts if the current state permits.",
    ),
)

ACTION_REGISTRY = {item.action_id: item for item in _DEFINITIONS}


def validate_action_registry() -> None:
    if len(ACTION_REGISTRY) != len(_DEFINITIONS):
        raise RuntimeError("Action registry contains duplicate identifiers.")
    if any(not item.action_id.startswith("raventech.") for item in _DEFINITIONS):
        raise RuntimeError("Action registry contains an invalid identifier.")
    if any(item.risk_level == "blocked" for item in _DEFINITIONS):
        raise RuntimeError("Blocked actions must not be registered for execution.")


validate_action_registry()
