from __future__ import annotations

import hashlib
import json
import os
import platform
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import psutil

from app.schemas.ai_gateway import AiGpuProfile, AiHardwareProfile

_LINUX_VENDOR_NAMES = {
    "0x10de": "NVIDIA",
    "0x1002": "AMD",
    "0x1022": "AMD",
    "0x8086": "Intel",
}
HardwareReadiness = Literal[
    "cpu_only_capable", "entry_local_ai", "moderate_local_ai", "high_local_ai"
]


def collect_hardware_profile() -> AiHardwareProfile:
    memory = psutil.virtual_memory()
    cpu_model = _cpu_model()
    gpus = _windows_gpus() if os.name == "nt" else _linux_gpus()
    disk_free = _disk_free()
    total_vram = sum(gpu.vram_total_bytes or 0 for gpu in gpus)
    known_vram_devices = sum(gpu.vram_total_bytes is not None for gpu in gpus)
    readiness: HardwareReadiness
    if known_vram_devices and total_vram >= 16 * 1024**3:
        readiness = "high_local_ai"
        reason = "Reported dedicated GPU memory is at least 16 GiB in total."
    elif known_vram_devices and total_vram >= 8 * 1024**3:
        readiness = "moderate_local_ai"
        reason = "Reported dedicated GPU memory is at least 8 GiB in total."
    elif gpus or memory.total >= 16 * 1024**3:
        readiness = "entry_local_ai"
        reason = (
            "A GPU is detected or system memory is at least 16 GiB; model fit "
            "still depends on reported model size."
        )
    else:
        readiness = "cpu_only_capable"
        reason = (
            "No dedicated GPU memory was confirmed. CPU inference may be slow; "
            "RavenTech remains fully usable."
        )

    snapshot: dict[str, Any] = {
        "os_name": platform.system() or "unknown",
        "os_version": platform.version()[:120] or None,
        "architecture": platform.machine()[:80] or "unknown",
        "cpu_model": cpu_model,
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "system_memory_total_bytes": memory.total,
        "system_memory_available_bytes": memory.available,
        "disk_free_bytes": disk_free,
        "gpus": [gpu.model_dump(mode="json", exclude={"gpu_id"}) for gpu in gpus],
        "readiness": readiness,
    }
    fingerprint = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return AiHardwareProfile(
        os_name=snapshot["os_name"],
        os_version=snapshot["os_version"],
        architecture=snapshot["architecture"],
        cpu_model=cpu_model,
        physical_cores=snapshot["physical_cores"],
        logical_cores=snapshot["logical_cores"],
        system_memory_total_bytes=memory.total,
        system_memory_available_bytes=memory.available,
        disk_free_bytes=disk_free,
        gpus=gpus,
        readiness=readiness,
        readiness_reason=reason,
        profile_hash=fingerprint,
        sampled_at=datetime.now(UTC),
    )


def evaluate_model_fit(
    *,
    size_bytes: int | None,
    system_memory_available_bytes: int | None,
    gpu_memory_bytes: int | None,
) -> tuple[str, str, int | None]:
    if size_bytes is None or size_bytes <= 0:
        return (
            "unknown",
            "Runtime did not report model size; no fit claim is made.",
            None,
        )
    # A conservative 1.25x multiplier approximates runtime overhead; context/KV
    # cache can require more and varies by architecture and context length.
    estimated = int(size_bytes * 1.25)
    if gpu_memory_bytes is not None and gpu_memory_bytes > 0:
        if estimated <= gpu_memory_bytes * 0.70:
            return (
                "excellent_fit",
                "Approximate weights-plus-overhead fit leaves at least 30% VRAM "
                "headroom; context cache may need additional memory.",
                estimated,
            )
        if estimated <= gpu_memory_bytes * 0.90:
            return (
                "good_fit",
                "Approximate weights-plus-overhead fit leaves some VRAM "
                "headroom; long context may exceed it.",
                estimated,
            )
        if estimated <= gpu_memory_bytes:
            return (
                "marginal",
                "Approximate fit uses most reported VRAM; context cache may exceed "
                "available memory.",
                estimated,
            )
    if system_memory_available_bytes is not None:
        if estimated <= system_memory_available_bytes * 0.75:
            return (
                "cpu_fallback",
                "Model may fit in currently available system RAM, with CPU "
                "inference likely slower; GPU placement is not confirmed.",
                estimated,
            )
        return (
            "insufficient_memory",
            "Approximate model size exceeds conservative available RAM and VRAM "
            "headroom.",
            estimated,
        )
    return (
        "unknown",
        "Available system memory and GPU memory are not both sufficient to "
        "estimate fit.",
        estimated,
    )


def _cpu_model() -> str | None:
    value = platform.processor().strip()
    if value:
        return value[:180]
    if platform.system() == "Linux":
        try:
            with Path("/proc/cpuinfo").open(
                encoding="utf-8", errors="replace"
            ) as cpuinfo:
                for line in cpuinfo:
                    if line.casefold().startswith(("model name", "hardware")):
                        _, _, model = line.partition(":")
                        return model.strip()[:180] or None
        except OSError:
            pass
    return None


def _disk_free() -> int | None:
    try:
        root = (
            Path(os.environ.get("SystemDrive", "C:\\") + "\\")
            if os.name == "nt"
            else Path("/")
        )
        return int(psutil.disk_usage(str(root)).free)
    except (OSError, ValueError):
        return None


def _linux_gpus() -> list[AiGpuProfile]:
    devices: list[AiGpuProfile] = []
    drm = Path("/sys/class/drm")
    if drm.is_dir():
        for card in sorted(drm.glob("card[0-9]*"))[:16]:
            if not re.fullmatch(r"card\d+", card.name):
                continue
            device_path = card / "device"
            vendor_id = _read_text(device_path / "vendor", 32)
            device_id = _read_text(device_path / "device", 32)
            if not vendor_id:
                continue
            vendor_id = vendor_id.lower()
            vendor = _LINUX_VENDOR_NAMES.get(vendor_id, "Unknown")
            vram_total = _read_int(device_path / "mem_info_vram_total")
            vram_used = _read_int(device_path / "mem_info_vram_used")
            model = _nvidia_model(device_path) if vendor == "NVIDIA" else None
            if not model:
                model = f"{vendor} GPU" + (f" ({device_id})" if device_id else "")
            devices.append(
                AiGpuProfile(
                    gpu_id=card.name,
                    vendor=vendor,
                    model=model[:180],
                    vram_total_bytes=vram_total,
                    vram_available_bytes=(
                        max(0, vram_total - vram_used)
                        if vram_total is not None and vram_used is not None
                        else None
                    ),
                    driver_version=None,
                    compute_backend=None,
                    metadata_source="Linux sysfs",
                )
            )
    return devices


def _windows_gpus() -> list[AiGpuProfile]:
    try:
        import winreg
    except ImportError:
        return []
    path = (
        r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
    )
    devices: list[AiGpuProfile] = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as root:
            for index in range(16):
                try:
                    child_name = winreg.EnumKey(root, index)
                except OSError:
                    break
                if not re.fullmatch(r"\d{4}", child_name):
                    continue
                try:
                    with winreg.OpenKey(root, child_name) as child:
                        model = _registry_string(winreg, child, "DriverDesc")
                        if not model:
                            continue
                        driver = _registry_string(winreg, child, "DriverVersion")
                        memory_value = _registry_value(
                            winreg, child, "HardwareInformation.qwMemorySize"
                        )
                        vram = _registry_memory_bytes(memory_value)
                        lower = model.casefold()
                        vendor = next(
                            (
                                name
                                for key, name in (
                                    ("nvidia", "NVIDIA"),
                                    ("amd", "AMD"),
                                    ("radeon", "AMD"),
                                    ("intel", "Intel"),
                                )
                                if key in lower
                            ),
                            "Unknown",
                        )
                        devices.append(
                            AiGpuProfile(
                                gpu_id=f"display-{len(devices)}",
                                vendor=vendor,
                                model=model[:180],
                                vram_total_bytes=vram,
                                vram_available_bytes=None,
                                driver_version=driver[:80] if driver else None,
                                compute_backend=None,
                                metadata_source="Windows display-driver registry",
                            )
                        )
                except OSError:
                    continue
    except OSError:
        return []
    return devices


def _read_text(path: Path, limit: int) -> str | None:
    try:
        value = path.read_text(encoding="utf-8", errors="replace").strip()
        return value[:limit] if value else None
    except OSError:
        return None


def _read_int(path: Path) -> int | None:
    value = _read_text(path, 32)
    if value is None:
        return None
    try:
        parsed = int(value, 0)
        return parsed if parsed >= 0 else None
    except ValueError:
        return None


def _nvidia_model(device_path: Path) -> str | None:
    information = Path("/proc/driver/nvidia/gpus")
    if not information.is_dir():
        return None
    for card in list(information.glob("*/information"))[:16]:
        content = _read_text(card, 4096)
        if content:
            model = re.search(r"(?m)^Model:\s*(.{1,180})$", content)
            if model:
                return model.group(1).strip()
    return None


def _registry_value(winreg: Any, key: Any, name: str) -> Any:
    try:
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def _registry_string(winreg: Any, key: Any, name: str) -> str | None:
    value = _registry_value(winreg, key, name)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _registry_memory_bytes(value: Any) -> int | None:
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, bytes) and len(value) in {4, 8}:
        number = int.from_bytes(value, byteorder="little", signed=False)
        return number if number > 0 else None
    return None
