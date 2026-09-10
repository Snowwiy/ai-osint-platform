#!/usr/bin/env python3
"""Manual Linux endpoint telemetry helper; no persistence or remote execution."""

from __future__ import annotations

import argparse
import getpass
import ipaddress
import json
import os
import platform
import shutil
import socket
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

AGENT_VERSION = "1.1.0"


def private_ip(backend_host: str, explicit: str | None) -> str:
    if explicit:
        address = ipaddress.ip_address(explicit)
    else:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.connect((backend_host, 80))
            address = ipaddress.ip_address(client.getsockname()[0])
    if not isinstance(address, ipaddress.IPv4Address) or not address.is_private or address.is_loopback:
        raise ValueError("asset IP must be a private non-loopback IPv4 address")
    return str(address)


def memory_percent() -> float | None:
    try:
        values: dict[str, int] = {}
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                key, value, *_ = line.split()
                values[key.rstrip(":")] = int(value)
        return round((1 - values["MemAvailable"] / values["MemTotal"]) * 100, 1)
    except (OSError, KeyError, ValueError, ZeroDivisionError):
        return None


def telemetry() -> dict[str, object | None]:
    cores = os.cpu_count() or 1
    load = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0
    disk = shutil.disk_usage("/")
    try:
        with open("/proc/uptime", encoding="utf-8") as handle:
            uptime = int(float(handle.read().split()[0]))
    except (OSError, ValueError, IndexError):
        uptime = None
    os_release: dict[str, str] = {}
    try:
        with open("/etc/os-release", encoding="utf-8") as handle:
            for line in handle:
                if "=" not in line:
                    continue
                key, value = line.rstrip().split("=", 1)
                if key in {"PRETTY_NAME", "VERSION_ID"}:
                    os_release[key] = value.strip('"')[:100]
    except OSError:
        pass
    listening_ports: set[int] = set()
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(path, encoding="ascii") as handle:
                for line in list(handle)[1:]:
                    fields = line.split()
                    if len(fields) > 3 and fields[3] == "0A":
                        listening_ports.add(int(fields[1].split(":")[1], 16))
        except (OSError, ValueError, IndexError):
            continue
    patch_date: str | None = None
    patch_status = "unknown"
    patch_stamp = "/var/lib/apt/periodic/update-success-stamp"
    try:
        modified = datetime.fromtimestamp(os.path.getmtime(patch_stamp), UTC)
        patch_date = modified.date().isoformat()
        patch_status = "stale" if datetime.now(UTC) - modified > timedelta(days=45) else "current"
    except OSError:
        pass
    return {
        "collected_at": datetime.now(UTC).isoformat(),
        "cpu_percent": round(min(100, load / cores * 100), 1),
        "memory_percent": memory_percent(),
        "disk_percent": round((disk.used / disk.total) * 100, 1) if disk.total else None,
        "uptime_seconds": uptime,
        "os_name": os_release.get("PRETTY_NAME", platform.system()),
        "os_version": os_release.get("VERSION_ID", platform.release()),
        "os_build": platform.release(),
        "agent_version": AGENT_VERSION,
        "disk_free_gb": round(disk.free / (1024**3), 2),
        "firewall_status": "unknown",
        "antivirus_status": "unavailable",
        "patch_status": patch_status,
        "latest_patch_date": patch_date,
        "recent_hotfix_count": None,
        "pending_reboot": os.path.exists("/var/run/reboot-required"),
        "listening_tcp_ports": sorted(listening_ports)[:64],
        "metadata": {"collection_mode": "manual"},
    }


def post(url: str, token: str, payload: dict[str, object | None]) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-LAN-Agent-Token": token},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - validated local/private URL
        return json.loads(response.read(16_384))


def main() -> int:
    parser = argparse.ArgumentParser(description="Send basic Linux telemetry to an authorized local RavenTech backend.")
    parser.add_argument("--backend-url", default="http://localhost:8000")
    parser.add_argument("--asset-ip")
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    parsed = urlparse(args.backend_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SystemExit("backend URL must use HTTP(S)")
    try:
        host = ipaddress.ip_address(parsed.hostname)
        if not (host.is_private or host.is_loopback):
            raise SystemExit("backend host must be localhost or private")
    except ValueError:
        if parsed.hostname != "localhost":
            raise SystemExit("backend host must be localhost or a private IP") from None
    if not 10 <= args.interval_seconds <= 3600:
        raise SystemExit("interval must be between 10 and 3600 seconds")
    address = private_ip(parsed.hostname, args.asset_ip)
    token = getpass.getpass("Paste the one-time endpoint enrollment token: ")
    base = args.backend_url.rstrip("/")
    try:
        registered = post(f"{base}/api/v1/monitoring/agent/register", token, {
            "ip_address": address, "hostname": socket.gethostname(), "asset_type": "endpoint",
            "os_name": platform.system(), "os_version": platform.release(),
            "agent_version": AGENT_VERSION,
            "capabilities": ["basic_telemetry", "os_basics", "security_posture", "patch_awareness", "listening_ports"],
        })
        asset_id = str(registered["asset_id"])
        print("Agent enrolled. Sending basic telemetry; press Ctrl+C to stop.")
        while True:
            sample = telemetry()
            sample["asset_id"] = asset_id
            try:
                post(f"{base}/api/v1/monitoring/agent/telemetry", token, sample)
                print(f"Telemetry accepted at {sample['collected_at']}.")
            except (urllib.error.URLError, ValueError, KeyError):
                print("Telemetry was not accepted; check backend health and token status.")
            if args.once:
                break
            time.sleep(args.interval_seconds)
    except KeyboardInterrupt:
        pass
    finally:
        token = ""
        print("Agent stopped. No persistence or autostart was configured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
