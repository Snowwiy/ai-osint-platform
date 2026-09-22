"""Fixed PyInstaller standalone build for the host OS; never cross-compiles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
COMPONENTS = {
    "backend": ("native_server.py", "RavenTechBackend.exe", "raventech-backend"),
    "worker": ("native_worker.py", "RavenTechWorker.exe", "raventech-worker"),
}
RESOURCE_PATHS = (
    (BACKEND / "alembic", Path("alembic")),
    (BACKEND / "app" / "templates", Path("app/templates")),
    (BACKEND / "data" / "knowledge", Path("data/knowledge")),
)


def target_id() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system not in {"windows", "linux"} or machine not in {"amd64", "x86_64"}:
        raise RuntimeError("Native packaging supports Windows/Linux x86_64 hosts only.")
    return f"{system}-x86_64"


def validate_resource_source(path: Path) -> None:
    if not path.is_dir():
        raise RuntimeError("Required package resource directory is missing.")
    for item in path.rglob("*"):
        if "__pycache__" in item.parts or item.suffix == ".pyc":
            continue
        if item.is_file() and item.suffix not in {".py", ".mako", ".j2", ".md"}:
            raise RuntimeError("Unexpected package resource file type.")


def copy_resources(destination: Path) -> None:
    for source, relative in RESOURCE_PATHS:
        validate_resource_source(source)
        target = destination / "resources" / relative
        target.mkdir(parents=True, exist_ok=True)
        for item in source.rglob("*"):
            if (
                item.is_file()
                and "__pycache__" not in item.parts
                and item.suffix != ".pyc"
            ):
                output = target / item.relative_to(source)
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, output)


def manifest(component: str, binary: Path) -> dict[str, object]:
    from app.core.config import Settings

    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit = "unavailable"
    try:
        worktree_dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, check=True,
            capture_output=True, text=True, timeout=5,
        ).stdout.strip())
    except (OSError, subprocess.SubprocessError):
        worktree_dirty = True
    try:
        version = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            check=True, capture_output=True, text=True, timeout=15,
        ).stdout.splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        version = "unknown"
    return {
        "product": "RavenTech OSINT",
        "component": component,
        "version": Settings().APP_VERSION,
        "git_commit": commit,
        "git_worktree_dirty": worktree_dirty,
        "build_timestamp_utc": datetime.now(UTC).isoformat(),
        "os": platform.system().lower(),
        "architecture": "x86_64",
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "binary_size_bytes": binary.stat().st_size,
        "packaging_engine": f"PyInstaller {version}",
        "runtime_profile": "desktop",
        "required_external_dependencies": ["PostgreSQL", "external configuration"],
    }


def build(component: str) -> Path:
    source, windows_name, linux_name = COMPONENTS[component]
    executable = windows_name if os.name == "nt" else linux_name
    artifact = ROOT / "desktop" / "dist-native" / target_id() / component
    artifact.parent.mkdir(parents=True, exist_ok=True)
    build_area = artifact.parent / f".{component}-build"
    output_root = (ROOT / "desktop" / "dist-native").resolve()
    if not build_area.resolve().is_relative_to(output_root):
        raise RuntimeError("Build path escaped the generated-artifact directory.")
    if not artifact.resolve().is_relative_to(output_root):
        raise RuntimeError("Artifact path escaped the generated-artifact directory.")
    build_area.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND)
    name = Path(executable).stem if os.name == "nt" else executable
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm",
        "--onedir", "--console", "--contents-directory=.",
        f"--name={name}", f"--distpath={build_area}",
        f"--workpath={build_area / 'work'}", f"--specpath={build_area / 'spec'}",
        f"--paths={BACKEND}",
        "--collect-submodules=app", "--collect-submodules=reportlab",
        "--collect-submodules=docx", "--collect-submodules=whois",
        "--collect-submodules=passlib",
        "--collect-submodules=chromadb",
        "--collect-submodules=sentence_transformers",
        "--collect-data=chromadb",
        "--hidden-import=sqlalchemy.dialects.postgresql.asyncpg",
        "--hidden-import=sqlalchemy.dialects.postgresql.psycopg2",
        "--hidden-import=asyncpg", "--hidden-import=psycopg2",
        "--exclude-module=workers", "--exclude-module=celery",
        str(BACKEND / "app" / source),
    ]
    subprocess.run(command, cwd=ROOT, env=env, check=True)
    distribution = build_area / name
    if not distribution.is_dir():
        raise RuntimeError("PyInstaller did not produce a standalone directory.")
    if artifact.exists():
        shutil.rmtree(artifact)
    shutil.move(str(distribution), str(artifact))
    binary = artifact / executable
    if not binary.is_file():
        raise RuntimeError("Native executable was not produced.")
    copy_resources(artifact)
    (artifact / "manifest.json").write_text(
        json.dumps(manifest(component, binary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if os.name != "nt":
        binary.chmod(binary.stat().st_mode | 0o111)
    return binary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("component", choices=tuple(COMPONENTS))
    args = parser.parse_args()
    try:
        binary = build(args.component)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(
            f"Native {args.component} build failed: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 2
    print(f"Built {args.component}: {binary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
