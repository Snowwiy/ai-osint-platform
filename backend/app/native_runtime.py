"""Fixed, platform-neutral paths for the separately launched native runtime."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NativePaths:
    config: Path
    data: Path
    state: Path
    logs: Path
    reports: Path
    runtime: Path


def is_native_package() -> bool:
    return os.getenv("RAVENTECH_NATIVE_PACKAGE") == "1"


def _strip_windows_verbatim_prefix(value: str) -> str:
    """Convert Windows extended-length paths for libraries that reject them."""
    if value[:8].casefold() == "\\\\?\\unc\\":
        return "\\\\" + value[8:]
    if value.startswith("\\\\?\\"):
        return value[4:]
    return value


def native_paths() -> NativePaths:
    home = Path.home()
    if sys.platform == "win32":
        base = (
            Path(os.getenv("LOCALAPPDATA") or home / "AppData" / "Local")
            / "RavenTech OSINT"
        )
        config = base / "config"
        data = base
        state = base
    else:
        config = (
            Path(os.getenv("XDG_CONFIG_HOME") or home / ".config")
            / "raventech-osint"
        )
        data = (
            Path(os.getenv("XDG_DATA_HOME") or home / ".local" / "share")
            / "raventech-osint"
        )
        state = (
            Path(os.getenv("XDG_STATE_HOME") or home / ".local" / "state")
            / "raventech-osint"
        )
    return NativePaths(
        config=config,
        data=data,
        state=state,
        logs=state / "logs",
        reports=data / "reports",
        runtime=state / "runtime",
    )


def resource_path(*parts: str) -> Path:
    """Read-only data comes from the artifact, never the current directory."""
    if is_native_package() and Path(sys.argv[0]).suffix.lower() != ".py":
        executable = Path(sys.argv[0]).resolve()
        if sys.platform == "win32":
            executable = Path(_strip_windows_verbatim_prefix(str(executable)))
        return executable.parent / "resources" / Path(*parts)
    return Path(__file__).resolve().parents[1] / Path(*parts)


def configure_native_environment() -> None:
    """Set fixed desktop defaults before importing application settings."""
    paths = native_paths()
    os.environ["RAVENTECH_NATIVE_PACKAGE"] = "1"
    os.environ.setdefault("RUNTIME_PROFILE", "desktop")
    os.environ.setdefault("RAVENTECH_CONFIG_FILE", str(paths.config / ".env"))
    os.environ.setdefault("CHROMA_DATA_PATH", str(paths.data / "chroma"))
    # Existing optional local embedding providers must never fetch model weights
    # when a standalone desktop artifact starts.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"


def prepare_native_directories() -> None:
    paths = native_paths()
    for path in (paths.config, paths.logs, paths.reports, paths.runtime):
        path.mkdir(parents=True, exist_ok=True)
