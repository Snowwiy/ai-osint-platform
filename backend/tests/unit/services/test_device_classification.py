from __future__ import annotations

import pytest
from app.models.lan_monitoring import LanAsset
from app.services.device_classification import classify, os_family
from app.services.lan_monitoring import _classify_asset


@pytest.mark.parametrize(
    ("name", "family"),
    [
        ("Windows 11", "windows"),
        ("Ubuntu Linux", "linux"),
        ("Android 15", "android"),
        ("iOS 18", "ios"),
        ("macOS", "macos"),
        (None, "unknown"),
    ],
)
def test_agent_os_family(name: str | None, family: str) -> None:
    assert os_family(name) == family


def test_agent_metadata_has_priority_over_operator_and_gateway() -> None:
    result = classify(
        os_name="Android",
        agent_mode="LanEndpoint",
        agent_form_factor="tablet",
        manual_type="server",
        gateway=True,
    )
    assert (result.os_family, result.device_type, result.source, result.confidence) == (
        "android",
        "tablet",
        "endpoint_agent",
        "high",
    )
    assert "agent form factor" in result.evidence


def test_agent_without_form_factor_does_not_guess_mobile_or_server() -> None:
    for name in ("Android", "iOS", "Windows", "Linux"):
        result = classify(os_name=name, agent_mode="LanEndpoint")
        assert result.device_type == "unknown"
        assert result.confidence == "high"


def test_manual_classification_is_preserved_above_passive_hints() -> None:
    result = classify(manual_type="server", gateway=True, hostname="router-home")
    assert result.device_type == "server"
    assert result.source == "operator"


def test_gateway_router_and_hostname_hints_have_explicit_confidence() -> None:
    gateway = classify(gateway=True)
    phone = classify(hostname="samsung-phone", vendor="Samsung")
    unknown = classify(vendor="Apple")
    assert (gateway.device_type, gateway.confidence) == ("router", "high")
    assert (phone.device_type, phone.confidence) == ("mobile", "medium")
    assert (unknown.device_type, unknown.confidence) == ("unknown", "low")


def test_no_exact_os_version_is_inferred() -> None:
    result = classify(hostname="windows-laptop", vendor="Microsoft")
    assert result.os_family == "unknown"
    assert result.device_type == "unknown"


def test_manual_type_survives_passive_and_agent_priority() -> None:
    asset = LanAsset(
        ip_address="192.168.50.99",
        source="static",
        asset_type="unknown",
        manual_device_type="server",
        hostname="phone",
        vendor="Samsung",
    )
    _classify_asset(asset)
    assert (asset.device_type, asset.classification_source) == ("server", "operator")
    asset.source = "endpoint_agent"
    asset.agent_mode = "LanEndpoint"
    asset.os_name = "Windows"
    _classify_asset(asset)
    assert (asset.os_family, asset.device_type, asset.classification_source) == (
        "windows",
        "server",
        "operator+endpoint_agent",
    )
    assert asset.manual_device_type == "server"


def test_gateway_fills_agent_type_when_form_factor_is_missing() -> None:
    result = classify(os_name="Linux", agent_mode="LanEndpoint", gateway=True)
    assert (result.os_family, result.device_type, result.confidence) == (
        "linux",
        "router",
        "high",
    )
