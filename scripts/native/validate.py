"""Validate only fixed generated native artifacts for the current host."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = f"{platform.system().lower()}-x86_64"
NAMES = {
    "windows": {"backend": "RavenTechBackend.exe", "worker": "RavenTechWorker.exe"},
    "linux": {"backend": "raventech-backend", "worker": "raventech-worker"},
}
FORBIDDEN_NAMES = {".env", "id_rsa", "id_ed25519"}
FORBIDDEN_SUFFIXES = {".key", ".p12", ".pfx", ".dump"}


def validate(component: str) -> None:
    system = platform.system().lower()
    if system not in NAMES or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise RuntimeError("Unsupported native validation host.")
    artifact = ROOT / "desktop" / "dist-native" / TARGET / component
    binary = artifact / NAMES[system][component]
    metadata = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
    if metadata.get("os") != system or metadata.get("architecture") != "x86_64":
        raise RuntimeError("Artifact target identity is wrong.")
    if metadata.get("binary_sha256") != hashlib.sha256(binary.read_bytes()).hexdigest():
        raise RuntimeError("Artifact checksum does not match manifest.")
    if metadata.get("version") != "5.0.0-rc6":
        raise RuntimeError("Artifact version is wrong.")
    for item in artifact.rglob("*"):
        if item.is_file() and (
            item.name.lower() in FORBIDDEN_NAMES
            or item.suffix.lower() in FORBIDDEN_SUFFIXES
        ):
            raise RuntimeError("Forbidden file found in native artifact.")
        if (
            item.is_file()
            and item.suffix.lower() == ".pem"
            and b"PRIVATE KEY" in item.read_bytes()
        ):
            raise RuntimeError("Private key found in native artifact.")
    env = os.environ.copy()
    env["RAVENTECH_CONFIG_FILE"] = str(ROOT / ".env")
    env["RUNTIME_PROFILE"] = "desktop"
    for flag in ("--version", "--check"):
        outcome = subprocess.run(
            [str(binary), flag], cwd=tempfile.gettempdir(), env=env,
            capture_output=True, text=True, timeout=45,
        )
        if outcome.returncode != 0:
            raise RuntimeError(f"Native {component} {flag} failed.")
        if flag == "--version" and outcome.stdout.strip() != "5.0.0-rc6":
            raise RuntimeError("Native version output is wrong.")


def main() -> int:
    try:
        for component in ("backend", "worker"):
            validate(component)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(
            f"Native artifact validation failed: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 2
    print(f"Native artifacts validated for {TARGET}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
