"""Conservative, explainable LAN identity classification."""

from __future__ import annotations

from dataclasses import dataclass

FAMILIES = {"windows", "linux", "macos", "android", "ios", "other", "unknown"}
TYPES = {
    "desktop",
    "laptop",
    "server",
    "mobile",
    "tablet",
    "router",
    "network_device",
    "iot",
    "virtual_machine",
    "unknown",
}


@dataclass(frozen=True)
class Classification:
    os_family: str = "unknown"
    device_type: str = "unknown"
    source: str = "insufficient_evidence"
    confidence: str = "low"
    evidence: tuple[str, ...] = ()


def os_family(name: str | None, explicit: str | None = None) -> str:
    if explicit and explicit.lower() in FAMILIES:
        return explicit.lower()
    value = (name or "").lower()
    if "android" in value:
        return "android"
    if "iphone" in value or "ipad" in value or value.startswith("ios"):
        return "ios"
    if "macos" in value or "mac os" in value or "darwin" in value:
        return "macos"
    if "windows" in value:
        return "windows"
    if "linux" in value or "ubuntu" in value or "debian" in value or "fedora" in value:
        return "linux"
    return "unknown"


def classify(
    *,
    os_name: str | None = None,
    agent_family: str | None = None,
    agent_form_factor: str | None = None,
    agent_mode: str | None = None,
    manual_type: str | None = None,
    gateway: bool = False,
    hostname: str | None = None,
    vendor: str | None = None,
) -> Classification:
    family = os_family(os_name, agent_family)
    form = (agent_form_factor or "").lower()
    if agent_mode:
        if form in TYPES - {"unknown"}:
            return Classification(
                family,
                form,
                "endpoint_agent",
                "high",
                (
                    ("authenticated agent OS", "agent form factor")
                    if family != "unknown"
                    else ("agent form factor",)
                ),
            )
        if manual_type in TYPES - {"unknown"}:
            return Classification(
                family,
                manual_type,
                "operator+endpoint_agent",
                "high",
                (
                    ("authenticated agent OS", "operator classification")
                    if family != "unknown"
                    else ("operator classification",)
                ),
            )
        if gateway:
            return Classification(
                family,
                "router",
                "gateway_hint+endpoint_agent",
                "high",
                (
                    ("authenticated agent OS", "configured gateway address")
                    if family != "unknown"
                    else ("configured gateway address",)
                ),
            )
    if agent_mode and family != "unknown":
        if family in {"android", "ios"}:
            return Classification(
                family,
                "unknown",
                "endpoint_agent",
                "high",
                ("authenticated agent OS", "form factor unreported"),
            )
        return Classification(
            family,
            "unknown",
            "endpoint_agent",
            "high",
            ("authenticated agent OS", "device type unreported"),
        )
    if manual_type in TYPES - {"unknown"}:
        return Classification(
            family, manual_type, "operator", "high", ("operator classification",)
        )
    if gateway:
        return Classification(
            family, "router", "gateway_hint", "high", ("configured gateway address",)
        )
    name = (hostname or "").lower()
    if any(term in name for term in ("router", "gateway", "switch", "ap-")):
        kind = "router" if "router" in name or "gateway" in name else "network_device"
        return Classification(
            family, kind, "hostname_heuristic", "medium", ("hostname pattern",)
        )
    if any(term in name for term in ("iphone", "ipad", "phone", "tablet")):
        kind = "tablet" if "ipad" in name or "tablet" in name else "mobile"
        return Classification(
            family, kind, "hostname_heuristic", "medium", ("hostname pattern",)
        )
    if (
        vendor
        and name
        and any(
            term in vendor.lower() for term in ("samsung", "apple", "xiaomi", "huawei")
        )
    ):
        return Classification(
            family,
            "unknown",
            "vendor_hostname_hint",
            "low",
            ("vendor", "hostname; device type unconfirmed"),
        )
    return Classification(family, "unknown", "insufficient_evidence", "low", ())
