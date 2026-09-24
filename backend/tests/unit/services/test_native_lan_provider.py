from __future__ import annotations

import ipaddress

import pytest
from app.core.config import settings
from app.schemas.lan_monitoring import LanDiscoveryObservation, LanServiceInput
from app.services import lan_monitoring
from app.services.native_lan_provider import (
    NativeInterface,
    NativeRoute,
    _interface_names_by_index,
    intersect_networks,
    normalize_mac,
    parse_linux_neighbors,
    parse_linux_routes,
    select_reachable_networks,
)


def _interface(
    name: str, address: str, cidr: str, *, is_up: bool = True
) -> NativeInterface:
    return NativeInterface(
        name=name,
        address=address,
        network=ipaddress.IPv4Network(cidr),
        mac_address="02:11:22:33:44:55",
        is_up=is_up,
    )


def test_authorized_network_is_intersected_with_active_route() -> None:
    result = intersect_networks(
        ipaddress.IPv4Network("192.168.50.0/24"),
        ipaddress.IPv4Network("192.168.50.0/25"),
    )
    assert result == ipaddress.IPv4Network("192.168.50.0/25")

    selected = select_reachable_networks(
        [ipaddress.IPv4Network("192.168.50.0/24")],
        [_interface("Ethernet", "192.168.50.37", "192.168.50.0/24")],
        [NativeRoute("Ethernet", ipaddress.IPv4Network("192.168.50.0/25"))],
    )
    assert [str(item.network) for item in selected] == ["192.168.50.0/25"]


def test_public_unrouted_and_down_interfaces_are_not_selected() -> None:
    authorized = [ipaddress.IPv4Network("192.168.50.0/24")]
    interfaces = [
        _interface("Ethernet", "192.168.50.37", "192.168.50.0/24", is_up=False),
        _interface("Wi-Fi", "10.20.0.4", "10.20.0.0/24"),
    ]
    routes = [
        NativeRoute("Ethernet", ipaddress.IPv4Network("8.8.8.0/24")),
        NativeRoute("Wi-Fi", ipaddress.IPv4Network("10.20.0.0/24")),
    ]
    assert select_reachable_networks(authorized, interfaces, routes) == []


def test_default_route_does_not_authorize_a_different_private_network() -> None:
    selected = select_reachable_networks(
        [ipaddress.IPv4Network("192.168.50.0/24")],
        [_interface("Ethernet", "10.0.0.12", "10.0.0.0/24")],
        [NativeRoute("Ethernet", ipaddress.IPv4Network("0.0.0.0/0"))],
    )
    assert selected == []


def test_linux_route_parser_normalizes_kernel_little_endian_rows() -> None:
    routes = parse_linux_routes(
        "Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\n"
        "eth0 0032A8C0 00000000 0001 0 0 0 00FFFFFF 0 0 0\n"
        "eth0 00000000 010032A8 0000 0 0 0 00000000 0 0 0\n"
    )
    assert len(routes) == 1
    assert routes[0].interface == "eth0"
    assert routes[0].network == ipaddress.IPv4Network("192.168.50.0/24")


def test_linux_neighbor_parser_rejects_invalid_and_public_rows() -> None:
    rows = parse_linux_neighbors(
        "IP address HW type Flags HW address Mask Device\n"
        "192.168.50.11 0x1 0x2 00:11:22:33:44:55 * eth0\n"
        "192.168.50.12 0x1 0x2 00:00:00:00:00:00 * eth0\n"
        "192.168.50.13 0x1 0x2 invalid * eth0\n"
        "8.8.8.8 0x1 0x2 00:11:22:33:44:66 * eth0\n"
    )
    assert len(rows) == 1
    assert rows[0].ip_address == "192.168.50.11"
    assert rows[0].mac_address == "00:11:22:33:44:55"
    assert rows[0].state == "reachable"


def test_mac_normalization_rejects_multicast_zero_and_malformed_addresses() -> None:
    assert normalize_mac("02-11-22-33-44-55") == "02:11:22:33:44:55"
    assert normalize_mac("01:11:22:33:44:55") is None
    assert normalize_mac("00:00:00:00:00:00") is None
    assert normalize_mac("not-a-mac") is None


def test_windows_interface_index_mapping_uses_native_index_name_order() -> None:
    assert _interface_names_by_index(
        [(7, "Ethernet"), (12, "Wi-Fi"), (0, "invalid"), (13, "")]
    ) == {7: "Ethernet", 12: "Wi-Fi"}


def test_bounded_tcp_candidates_skip_local_and_stop_at_host_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LAN_ALLOWED_CIDRS", "192.168.50.0/24")
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_MAX_HOSTS", 3)
    candidates = lan_monitoring._bounded_tcp_candidates(
        [ipaddress.IPv4Network("192.168.50.0/24")], {"192.168.50.1"}
    )
    assert [str(item) for item in candidates] == [
        "192.168.50.2",
        "192.168.50.3",
        "192.168.50.4",
    ]


@pytest.mark.asyncio
async def test_tcp_fallback_is_disabled_without_both_safe_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LAN_DISCOVERY_PING_ENABLED", True)
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_ENABLED", False)

    async def should_not_connect(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("disabled discovery attempted a network connection")

    monkeypatch.setattr(lan_monitoring.asyncio, "open_connection", should_not_connect)
    result = await lan_monitoring._tcp_discovery(
        [ipaddress.IPv4Network("192.168.50.0/24")], set()
    )
    assert result == []


@pytest.mark.asyncio
async def test_service_observation_respects_host_cap_and_configured_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_PORTS", "443,8443")
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_MAX_PORTS", 2)
    monkeypatch.setattr(settings, "LAN_SERVICE_CHECK_MAX_HOSTS", 1)
    monkeypatch.setattr(settings, "LAN_DISCOVERY_CONCURRENCY", 2)
    observed: list[tuple[str, int]] = []

    async def observe(address: str, port: int) -> LanServiceInput:
        observed.append((address, port))
        return LanServiceInput(port=port, status="open")

    monkeypatch.setattr(lan_monitoring, "_tcp_service_observation", observe)
    assets = [
        LanDiscoveryObservation(ip_address="192.168.50.21"),
        LanDiscoveryObservation(ip_address="192.168.50.22"),
    ]
    await lan_monitoring._observe_configured_services(assets)
    assert observed == [("192.168.50.21", 443), ("192.168.50.21", 8443)]
    assert [item.port for item in assets[0].services] == [443, 8443]
    assert assets[1].services == []
