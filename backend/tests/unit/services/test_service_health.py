from __future__ import annotations

import pytest

from app.services.service_health import (
    assess_core_service,
    assess_lan_service,
    assess_local_service,
)


def lan(**changes: object):
    values = dict(
        port=443, status="open", device_type="server", os_family="linux",
        trust_state="authorized", service_name="https", non_standard_ssh=False,
        expected_ports=set(), allowed_ports=set(), has_baseline=False,
        critical_ports=set(),
    )
    values.update(changes)
    return assess_lan_service(**values)


@pytest.mark.parametrize(
    ("changes", "severity", "expectation"),
    [
        ({"expected_ports": {443}, "has_baseline": True}, "healthy", "expected"),
        ({"allowed_ports": {443}, "has_baseline": True}, "healthy", "allowed"),
        ({"has_baseline": True}, "warning", "unexpected"),
        ({"critical_ports": {443}}, "critical", "unclassified"),
        ({"port": 5432, "service_name": "postgresql"}, "warning", "unclassified"),
        ({"port": 6379, "service_name": "redis"}, "warning", "unclassified"),
        ({"port": 3389, "os_family": "windows"}, "warning", "unclassified"),
        ({"port": 2222, "service_name": "ssh", "non_standard_ssh": True}, "warning", "unclassified"),
        ({"device_type": "mobile"}, "warning", "unclassified"),
        ({"device_type": "tablet"}, "warning", "unclassified"),
        ({"device_type": "router", "port": 80}, "neutral", "unclassified"),
        ({"device_type": "unknown"}, "neutral", "unclassified"),
        ({"status": "closed"}, "neutral", "unclassified"),
        ({"status": "closed", "expected_ports": {443}, "has_baseline": True}, "warning", "expected"),
    ],
)
def test_lan_exposure_is_contextual(changes: dict[str, object], severity: str, expectation: str) -> None:
    result = lan(**changes)
    assert (result.severity, result.expectation) == (severity, expectation)
    assert result.reason
    assert "vulnerable" not in result.reason.lower()


def test_expected_service_takes_priority_over_port_sensitivity() -> None:
    assert lan(port=6379, expected_ports={6379}, has_baseline=True).severity == "healthy"


def test_local_service_baseline_and_transitions() -> None:
    assert assess_local_service("running", expected_state="running").severity == "healthy"
    assert assess_local_service("stopped", expected_state="stopped").severity == "neutral"
    assert assess_local_service("stopped", expected_state="running", required=True).severity == "critical"
    assert assess_local_service("stopped", expected_state="running").severity == "warning"
    assert assess_local_service("paused", expected_state="running").severity == "warning"
    assert assess_local_service("running").severity == "neutral"
    assert assess_local_service("running", expected_state="running", stale=True).severity == "warning"


@pytest.mark.parametrize("name", ["Backend", "PostgreSQL", "Redis", "Celery Worker"])
def test_required_core_service_down_is_critical(name: str) -> None:
    assert assess_core_service("down", required=True).severity == "critical", name
    assert assess_core_service("healthy", required=True).severity == "healthy"


def test_optional_core_service_and_unknown_health() -> None:
    assert assess_core_service("unavailable", required=False).severity == "warning"
    assert assess_core_service("unknown", required=False).severity == "neutral"
