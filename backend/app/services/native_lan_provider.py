"""Read-only, platform-native host network context for authorized LAN monitoring."""

from __future__ import annotations

import ctypes
import ipaddress
import os
import platform
import re
import socket
import struct
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

RFC1918 = tuple(
    ipaddress.IPv4Network(value)
    for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)
_MAC = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
_VIRTUAL_HINTS = (
    "docker",
    "container",
    "veth",
    "virbr",
    "vmware",
    "virtualbox",
    "hyper-v",
    "hyperv",
    "wsl",
    "loopback",
    "tun",
    "tap",
    "vpn",
    "tailscale",
    "zerotier",
)


@dataclass(frozen=True)
class NativeInterface:
    name: str
    address: str
    network: ipaddress.IPv4Network
    mac_address: str | None
    is_up: bool = True
    interface_index: int | None = None


@dataclass(frozen=True)
class NativeRoute:
    interface: str
    network: ipaddress.IPv4Network
    is_up: bool = True


@dataclass(frozen=True)
class NativeNeighbor:
    ip_address: str
    mac_address: str | None
    interface: str | None
    state: str
    family: str = "ipv4"


@dataclass(frozen=True)
class NativeLanSnapshot:
    available: bool
    hostname: str | None
    os_name: str
    os_version: str
    architecture: str
    sampled_at: datetime
    interfaces: tuple[NativeInterface, ...]
    reachable_networks: tuple[NativeRoute, ...]
    neighbors: tuple[NativeNeighbor, ...]
    primary_address: str | None
    primary_mac: str | None
    limitation: str | None


def normalize_mac(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().replace("-", ":").upper()
    if (
        not _MAC.fullmatch(normalized)
        or normalized == "00:00:00:00:00:00"
        or int(normalized[:2], 16) & 1
    ):
        return None
    return normalized


def intersect_networks(
    authorized: ipaddress.IPv4Network, route: ipaddress.IPv4Network
) -> ipaddress.IPv4Network | None:
    """Return the narrower CIDR when an authorized range intersects a route."""
    if not authorized.overlaps(route):
        return None
    return authorized if authorized.subnet_of(route) else route


def select_reachable_networks(
    authorized_networks: Iterable[ipaddress.IPv4Network],
    interfaces: Iterable[NativeInterface],
    routes: Iterable[NativeRoute],
) -> list[NativeRoute]:
    """Select authorized portions carried by an active interface route."""
    authorized_networks = tuple(authorized_networks)
    interface_map = {item.name: item for item in interfaces if item.is_up}
    selected: dict[tuple[str, str], NativeRoute] = {}
    for route in routes:
        interface = interface_map.get(route.interface)
        if interface is None or not route.is_up:
            continue
        for authorized in authorized_networks:
            if (
                route.network.prefixlen == 0
                and ipaddress.IPv4Address(interface.address) not in authorized
            ):
                # A default route is not evidence that a configured private CIDR
                # is locally reachable. Require a specific route or local address.
                continue
            overlap = intersect_networks(authorized, route.network)
            if overlap is None or not any(
                overlap.subnet_of(private) for private in RFC1918
            ):
                continue
            # Virtual adapters are considered only when the authorized range also
            # directly contains an address on that adapter; this avoids treating a
            # container/VPN default route as a LAN observation point.
            if is_virtual_interface(interface.name) and not any(
                ipaddress.IPv4Address(item.address) in authorized_networks
                for item in interfaces
                if item.name == interface.name
            ):
                continue
            selected[(route.interface, str(overlap))] = NativeRoute(
                route.interface, overlap, route.is_up
            )
    return sorted(
        selected.values(),
        key=lambda item: (item.interface, item.network.prefixlen, str(item.network)),
    )


def is_virtual_interface(name: str) -> bool:
    normalized = name.strip().lower()
    return any(hint in normalized for hint in _VIRTUAL_HINTS)


def parse_linux_routes(contents: str) -> list[NativeRoute]:
    """Parse the read-only IPv4 kernel route table from /proc/net/route."""
    rows: list[NativeRoute] = []
    for line in contents.splitlines()[1:1025]:
        fields = line.split()
        if len(fields) < 8:
            continue
        try:
            flags = int(fields[3], 16)
            if not flags & 1:
                continue
            destination = socket.inet_ntoa(struct.pack("<I", int(fields[1], 16)))
            mask = socket.inet_ntoa(struct.pack("<I", int(fields[7], 16)))
            network = ipaddress.IPv4Network((destination, mask), strict=False)
        except (OSError, ValueError, struct.error):
            continue
        rows.append(NativeRoute(interface=fields[0][:100], network=network))
    return rows


def parse_linux_neighbors(contents: str, *, limit: int = 2048) -> list[NativeNeighbor]:
    """Normalize the kernel IPv4 ARP cache; no command-line tools are invoked."""
    rows: list[NativeNeighbor] = []
    for line in contents.splitlines()[1 : limit + 1]:
        fields = line.split()
        if len(fields) < 6:
            continue
        try:
            address = ipaddress.ip_address(fields[0])
            flags = int(fields[2], 16)
        except ValueError:
            continue
        mac = normalize_mac(fields[3])
        if (
            not isinstance(address, ipaddress.IPv4Address)
            or not address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_unspecified
            or mac is None
        ):
            continue
        state = "reachable" if flags & 0x2 else "incomplete"
        rows.append(NativeNeighbor(str(address), mac, fields[5][:100], state))
    return rows


def _clean_name(value: str | None, limit: int = 255) -> str | None:
    if not value:
        return None
    clean = " ".join("".join(ch for ch in value if ch.isprintable()).split())
    return clean[:limit] or None


def _authorized_ipv4(value: str, networks: tuple[ipaddress.IPv4Network, ...]) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return (
        isinstance(address, ipaddress.IPv4Address)
        and address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_unspecified
        and any(address in network for network in networks)
    )


def _network_for(address: str, netmask: str) -> ipaddress.IPv4Network | None:
    try:
        return ipaddress.IPv4Network((address, netmask), strict=False)
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError):
        return None


def _system_interfaces() -> tuple[list[NativeInterface], dict[str, int]]:
    try:
        import psutil
    except ImportError:
        return [], {}
    addresses = psutil.net_if_addrs()
    statuses = psutil.net_if_stats()
    try:
        index_to_name = (
            _windows_adapter_names_by_index()
            if os.name == "nt"
            else _interface_names_by_index(socket.if_nameindex())
        )
        if os.name == "nt" and not index_to_name:
            index_to_name = _interface_names_by_index(socket.if_nameindex())
        indices = {name: index for index, name in index_to_name.items()}
    except (AttributeError, OSError):
        indices = {}
    output: list[NativeInterface] = []
    for name, rows in addresses.items():
        stats = statuses.get(name)
        is_up = bool(stats and stats.isup)
        link_address: str | None = None
        for row in rows:
            if row.family in {
                getattr(psutil, "AF_LINK", object()),
                getattr(socket, "AF_PACKET", object()),
            }:
                link_address = normalize_mac(row.address)
        for row in rows:
            if row.family != socket.AF_INET or not row.netmask:
                continue
            try:
                ipaddress.IPv4Address(row.address)
            except ipaddress.AddressValueError:
                continue
            network = _network_for(row.address, row.netmask)
            if network is None or row.address.startswith("127."):
                continue
            output.append(
                NativeInterface(
                    name=name[:100],
                    address=row.address,
                    network=network,
                    mac_address=link_address,
                    is_up=is_up,
                    interface_index=indices.get(name),
                )
            )
    return output, indices


def _linux_route_rows() -> list[NativeRoute]:
    try:
        with open("/proc/net/route", encoding="ascii") as stream:
            return parse_linux_routes(stream.read())
    except OSError:
        return []


class _SockAddrIn(ctypes.Structure):
    _fields_ = [
        ("family", ctypes.c_ushort),
        ("port", ctypes.c_ushort),
        ("address", ctypes.c_ubyte * 4),
        ("zero", ctypes.c_ubyte * 8),
    ]


class _SockAddrIn6(ctypes.Structure):
    _fields_ = [
        ("family", ctypes.c_ushort),
        ("port", ctypes.c_ushort),
        ("flowinfo", ctypes.c_uint32),
        ("address", ctypes.c_ubyte * 16),
        ("scope_id", ctypes.c_uint32),
    ]


class _SockAddrInet(ctypes.Union):
    _fields_ = [("ipv4", _SockAddrIn), ("ipv6", _SockAddrIn6)]


class _IpAddressPrefix(ctypes.Structure):
    _fields_ = [("prefix", _SockAddrInet), ("prefix_length", ctypes.c_ubyte)]


class _MibIpForwardRow2(ctypes.Structure):
    _fields_ = [
        ("interface_luid", ctypes.c_uint64),
        ("interface_index", ctypes.c_uint32),
        ("destination_prefix", _IpAddressPrefix),
        ("next_hop", _SockAddrInet),
        ("site_prefix_length", ctypes.c_ubyte),
        ("valid_lifetime", ctypes.c_uint32),
        ("preferred_lifetime", ctypes.c_uint32),
        ("metric", ctypes.c_uint32),
        ("protocol", ctypes.c_uint32),
        ("loopback", ctypes.c_ubyte),
        ("autoconfigure_address", ctypes.c_ubyte),
        ("publish", ctypes.c_ubyte),
        ("immortal", ctypes.c_ubyte),
        ("age", ctypes.c_uint32),
        ("origin", ctypes.c_uint32),
    ]


class _MibIpForwardTable2(ctypes.Structure):
    _fields_ = [("num_entries", ctypes.c_uint32), ("table", _MibIpForwardRow2 * 1)]


class _MibIpNetRow2(ctypes.Structure):
    _fields_ = [
        ("address", _SockAddrInet),
        ("interface_luid", ctypes.c_uint64),
        ("interface_index", ctypes.c_uint32),
        ("physical_address", ctypes.c_ubyte * 32),
        ("physical_address_length", ctypes.c_uint32),
        ("state", ctypes.c_int),
        ("flags", ctypes.c_ubyte),
    ]


class _MibIpNetTable2(ctypes.Structure):
    _fields_ = [("num_entries", ctypes.c_uint32), ("table", _MibIpNetRow2 * 1)]


class _IpAdapterAddresses(ctypes.Structure):
    pass


_IpAdapterAddresses._fields_ = [
    ("length", ctypes.c_uint32),
    ("interface_index", ctypes.c_uint32),
    ("next", ctypes.POINTER(_IpAdapterAddresses)),
    ("adapter_name", ctypes.c_char_p),
    ("first_unicast_address", ctypes.c_void_p),
    ("first_anycast_address", ctypes.c_void_p),
    ("first_multicast_address", ctypes.c_void_p),
    ("first_dns_server_address", ctypes.c_void_p),
    ("dns_suffix", ctypes.c_wchar_p),
    ("description", ctypes.c_wchar_p),
    ("friendly_name", ctypes.c_wchar_p),
]


def _interface_names_by_index(
    entries: Iterable[tuple[int, str]],
) -> dict[int, str]:
    return {index: name for index, name in entries if index > 0 and name}


def _windows_adapter_names_by_index() -> dict[int, str]:
    if os.name != "nt":
        return {}
    try:
        from ctypes import wintypes

        iphlpapi = ctypes.WinDLL("iphlpapi.dll")
        get_adapters = iphlpapi.GetAdaptersAddresses
        get_adapters.argtypes = [
            wintypes.ULONG,
            wintypes.ULONG,
            ctypes.c_void_p,
            ctypes.POINTER(_IpAdapterAddresses),
            ctypes.POINTER(wintypes.ULONG),
        ]
        get_adapters.restype = wintypes.ULONG
        buffer_size = wintypes.ULONG(0)
        status = get_adapters(0, 0, None, None, ctypes.byref(buffer_size))
        if status not in (0, 111) or not buffer_size.value:
            return {}
        buffer = ctypes.create_string_buffer(buffer_size.value)
        first = ctypes.cast(buffer, ctypes.POINTER(_IpAdapterAddresses))
        status = get_adapters(0, 0, None, first, ctypes.byref(buffer_size))
        if status != 0:
            return {}
    except (AttributeError, OSError, ValueError):
        return {}

    output: dict[int, str] = {}
    current = first
    seen: set[int] = set()
    while current and len(output) < 512:
        address = ctypes.addressof(current.contents)
        if address in seen:
            break
        seen.add(address)
        adapter = current.contents
        name = _clean_name(adapter.friendly_name, 100)
        if adapter.interface_index > 0 and name:
            output[adapter.interface_index] = name
        current = adapter.next
    return output


def _windows_tables() -> tuple[list[NativeRoute], list[NativeNeighbor]]:
    if os.name != "nt":
        return [], []
    try:
        iphlpapi = ctypes.WinDLL("iphlpapi.dll")
        free_table = iphlpapi.FreeMibTable
        if_name_by_index = _windows_adapter_names_by_index()
        if not if_name_by_index:
            if_name_by_index = _interface_names_by_index(socket.if_nameindex())
    except (AttributeError, OSError):
        return [], []

    routes: list[NativeRoute] = []
    route_table = ctypes.c_void_p()
    get_routes = iphlpapi.GetIpForwardTable2
    get_routes.argtypes = [ctypes.c_ushort, ctypes.POINTER(ctypes.c_void_p)]
    get_routes.restype = ctypes.c_ulong
    try:
        if get_routes(2, ctypes.byref(route_table)) == 0 and route_table.value:
            route_header = ctypes.cast(
                route_table, ctypes.POINTER(_MibIpForwardTable2)
            ).contents
            first = ctypes.addressof(route_header) + _MibIpForwardTable2.table.offset
            route_rows = ctypes.cast(first, ctypes.POINTER(_MibIpForwardRow2))
            for index in range(min(route_header.num_entries, 4096)):
                row = route_rows[index]
                if row.destination_prefix.prefix.ipv4.family != 2:
                    continue
                try:
                    address = socket.inet_ntoa(
                        bytes(row.destination_prefix.prefix.ipv4.address)
                    )
                    network = ipaddress.IPv4Network(
                        (address, row.destination_prefix.prefix_length), strict=False
                    )
                except (OSError, ValueError):
                    continue
                interface = if_name_by_index.get(row.interface_index)
                if interface:
                    routes.append(NativeRoute(interface, network))
    finally:
        if route_table.value:
            free_table(route_table)

    neighbors: list[NativeNeighbor] = []
    neighbor_table = ctypes.c_void_p()
    get_neighbors = iphlpapi.GetIpNetTable2
    get_neighbors.argtypes = [ctypes.c_ushort, ctypes.POINTER(ctypes.c_void_p)]
    get_neighbors.restype = ctypes.c_ulong
    try:
        if get_neighbors(0, ctypes.byref(neighbor_table)) == 0 and neighbor_table.value:
            neighbor_header = ctypes.cast(
                neighbor_table, ctypes.POINTER(_MibIpNetTable2)
            ).contents
            first = ctypes.addressof(neighbor_header) + _MibIpNetTable2.table.offset
            neighbor_rows = ctypes.cast(first, ctypes.POINTER(_MibIpNetRow2))
            states = {
                0: "unreachable",
                1: "incomplete",
                2: "probe",
                3: "delay",
                4: "stale",
                5: "reachable",
                6: "permanent",
            }
            for index in range(min(neighbor_header.num_entries, 4096)):
                row = neighbor_rows[index]
                family = row.address.ipv4.family
                try:
                    if family == 2:
                        address = socket.inet_ntoa(bytes(row.address.ipv4.address))
                        family_name = "ipv4"
                    elif family == 23:
                        address = socket.inet_ntop(
                            socket.AF_INET6, bytes(row.address.ipv6.address)
                        )
                        family_name = "ipv6"
                    else:
                        continue
                except (OSError, ValueError):
                    continue
                length = min(row.physical_address_length, 32)
                mac = (
                    normalize_mac(
                        ":".join(
                            f"{byte:02X}" for byte in row.physical_address[:length]
                        )
                    )
                    if length == 6
                    else None
                )
                neighbors.append(
                    NativeNeighbor(
                        address,
                        mac,
                        if_name_by_index.get(row.interface_index),
                        states.get(row.state, "unknown"),
                        family_name,
                    )
                )
    finally:
        if neighbor_table.value:
            free_table(neighbor_table)
    return routes, neighbors


def _linux_neighbors() -> list[NativeNeighbor]:
    try:
        with open("/proc/net/arp", encoding="ascii") as stream:
            return parse_linux_neighbors(stream.read())
    except OSError:
        return []


def collect_native_snapshot(
    authorized_networks: Iterable[ipaddress.IPv4Network],
) -> NativeLanSnapshot:
    """Collect identity, active routes, interfaces, and neighbor cache read-only."""
    networks = tuple(authorized_networks)
    interfaces, _indices = _system_interfaces()
    routes: list[NativeRoute]
    neighbors: list[NativeNeighbor]
    if os.name == "nt":
        routes, neighbors = _windows_tables()
    elif platform.system().lower() == "linux":
        routes = _linux_route_rows()
        neighbors = _linux_neighbors()
    else:
        routes, neighbors = [], []
    if not routes:
        routes = [
            NativeRoute(item.name, item.network) for item in interfaces if item.is_up
        ]
    reachable = select_reachable_networks(networks, interfaces, routes)
    reachable_cidrs = tuple(item.network for item in reachable)
    filtered_neighbors: dict[tuple[str, str | None], NativeNeighbor] = {}
    for item in neighbors[:4096]:
        if item.family != "ipv4" or not _authorized_ipv4(
            item.ip_address, reachable_cidrs
        ):
            continue
        filtered_neighbors[(item.ip_address, item.mac_address)] = item
    local: list[NativeInterface] = []
    for interface in interfaces:
        if not interface.is_up:
            continue
        if any(
            _authorized_ipv4(interface.address, (network,))
            for network in reachable_cidrs
        ):
            local.append(interface)
    local.sort(
        key=lambda item: (is_virtual_interface(item.name), item.name, item.address)
    )
    primary = local[0] if local else None
    try:
        os_name = platform.system() or "Unknown"
        os_version = platform.release() or "Unknown"
        architecture = platform.machine() or "Unknown"
    except OSError:
        os_name, os_version, architecture = "Unknown", "Unknown", "Unknown"
    limitation = None
    if not reachable:
        limitation = (
            "No active route intersects the configured authorized private networks."
        )
    elif not filtered_neighbors:
        limitation = (
            "Limited LAN visibility: no authorized peers were present in the native "
            "neighbor table. Network segmentation, client isolation, firewall policy, "
            "or inactive devices may limit visibility."
        )
    return NativeLanSnapshot(
        available=bool(interfaces),
        hostname=_clean_name(socket.gethostname()),
        os_name=_clean_name(os_name, 100) or "Unknown",
        os_version=_clean_name(os_version, 100) or "Unknown",
        architecture=_clean_name(architecture, 40) or "Unknown",
        sampled_at=datetime.now(UTC),
        interfaces=tuple(interfaces[:128]),
        reachable_networks=tuple(reachable),
        neighbors=tuple(filtered_neighbors.values()),
        primary_address=primary.address if primary else None,
        primary_mac=primary.mac_address if primary else None,
        limitation=limitation,
    )
