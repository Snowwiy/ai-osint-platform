from __future__ import annotations

import importlib.util
import io
from pathlib import Path
from typing import Any

import pytest


def _agent() -> Any:
    source = (
        Path(__file__).resolve().parents[3]
        / "scripts" / "local" / "local_monitor_agent.py"
    )
    spec = importlib.util.spec_from_file_location("linux_agent", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_linux_neighbors_are_passive_private_and_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = _agent()
    arp = (
        "IP address HW type Flags HW address Mask Device\n"
        "192.168.50.1 0x1 0x2 aa:bb:cc:dd:ee:ff * eth0\n"
        "192.168.50.20 0x1 0x2 11:22:33:44:55:66 * eth0\n"
        "192.168.51.8 0x1 0x2 00:11:22:33:44:55 * eth0\n"
        "8.8.8.8 0x1 0x2 00:11:22:33:44:55 * eth0\n"
    )
    original_open = open

    def fake_open(path: str, *args: Any, **kwargs: Any) -> Any:
        if path == "/proc/net/arp":
            return io.StringIO(arp)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", fake_open)
    rows = agent.host_neighbor_observations("192.168.50.20")
    assert [row["ip_address"] for row in rows] == ["192.168.50.1"]
    assert rows[0]["source"] == "host_neighbor_table"
    assert rows[0]["mac_address"] == "AA:BB:CC:DD:EE:FF"
