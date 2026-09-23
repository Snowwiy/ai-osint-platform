"""Stage a pinned PostgreSQL 16 distribution into ignored native build output."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "desktop" / "dist-native"
BINARIES = ("postgres", "initdb", "psql", "pg_isready", "pg_ctl")


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def stage(source_bin: Path, source_share: Path, source_lib: Path | None) -> Path:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system not in {"windows", "linux"} or machine not in {"amd64", "x86_64"}:
        raise RuntimeError(
            "PostgreSQL staging supports Windows/Linux x86_64 hosts only."
        )
    target = OUT / f"{system}-x86_64" / "postgresql"
    if not source_bin.is_dir() or not source_share.is_dir():
        raise RuntimeError(
            "The selected PostgreSQL distribution must contain bin "
            "and share directories."
        )
    suffix = ".exe" if system == "windows" else ""
    files: dict[str, dict[str, object]] = {}
    bin_out = target / "bin"
    share_out = target / "share"
    if not target.resolve().is_relative_to(OUT.resolve()):
        raise RuntimeError(
            "PostgreSQL artifact path escaped the generated runtime directory."
        )
    if target.exists():
        shutil.rmtree(target)
    bin_out.mkdir(parents=True)
    shutil.copytree(source_share, share_out)
    for name in BINARIES:
        source = source_bin / f"{name}{suffix}"
        if not source.is_file():
            raise RuntimeError(f"Required PostgreSQL runtime binary is missing: {name}")
        destination = bin_out / source.name
        shutil.copy2(source, destination)
        if system == "linux":
            destination.chmod(destination.stat().st_mode | 0o111)
        files[destination.relative_to(target).as_posix()] = {
            "sha256": digest(destination),
            "size_bytes": destination.stat().st_size,
        }
    if system == "windows":
        # EDB's official binary archive keeps its runtime DLL closure beside bin.
        if source_bin.is_dir():
            for source in source_bin.glob("*.dll"):
                destination = bin_out / source.name
                if not destination.exists():
                    shutil.copy2(source, destination)
                    files[destination.relative_to(target).as_posix()] = {
                        "sha256": digest(destination),
                        "size_bytes": destination.stat().st_size,
                    }
        if source_lib and source_lib.is_dir():
            lib_out = target / "lib"
            lib_out.mkdir(parents=True, exist_ok=True)
            for source in source_lib.glob("*.dll"):
                destination = lib_out / source.name
                if not destination.exists():
                    shutil.copy2(source, destination)
                    files[destination.relative_to(target).as_posix()] = {
                        "sha256": digest(destination),
                        "size_bytes": destination.stat().st_size,
                    }
    elif source_lib and source_lib.is_dir():
        # PostgreSQL's compiled-in PKGLIBDIR is the installation lib directory.
        # Keep modules directly under that directory so its $libdir lookup also
        # works after the installation tree is relocated.
        lib_out = target / "lib"
        for source in source_lib.rglob("*.so*"):
            if not source.is_file():
                continue
            destination = lib_out / source.relative_to(source_lib)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    for source in target.rglob("*"):
        if source.is_file():
            relative = source.relative_to(target).as_posix()
            files[relative] = {
                "sha256": digest(source),
                "size_bytes": source.stat().st_size,
            }
    binary_version = subprocess.run(
        [str(bin_out / f"postgres{suffix}"), "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if "PostgreSQL) 16." not in binary_version:
        raise RuntimeError("The staged PostgreSQL binary is not major version 16.")
    manifest = {
        "component": "postgresql",
        "version": binary_version,
        "major_version": 16,
        "os": system,
        "architecture": "x86_64",
        "source_identifier": "EnterpriseDB official Windows binary archive"
        if system == "windows"
        else "PostgreSQL Global Development Group packages/source for "
        "Debian-compatible Linux",
        "distribution_strategy": (
            "Pinned PostgreSQL 16 runtime; no PATH discovery; required binaries "
            "and share resources staged under desktop native-runtime."
        ),
        "build_timestamp_utc": datetime.now(UTC).isoformat(),
        "files": files,
        "required_libraries": [],
        "compatible_raventech_version": "5.0.0-rc6",
    }
    if system == "linux":
        libraries: set[str] = set()
        minimum_glibc: tuple[int, ...] = (0,)
        for name in BINARIES:
            result = subprocess.run(
                ["ldd", str(bin_out / name)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0 or "not found" in result.stdout:
                raise RuntimeError(
                    f"Linux runtime dependencies are unavailable for {name}."
                )
            for line in result.stdout.splitlines():
                if "=>" in line and "/" in line:
                    libraries.add(line.split("=>", 1)[0].strip())
        for module in (target / "lib").glob("*.so*"):
            result = subprocess.run(
                ["ldd", str(module)], capture_output=True, text=True, check=False
            )
            if result.returncode != 0 or "not found" in result.stdout:
                raise RuntimeError(
                    "A PostgreSQL shared module has missing runtime dependencies."
                )
            for line in result.stdout.splitlines():
                if "=>" in line and "/" in line:
                    libraries.add(line.split("=>", 1)[0].strip())
        for path in [
            *(bin_out / name for name in BINARIES),
            *(target / "lib").glob("*.so*"),
        ]:
            versions = re.findall(
                r"GLIBC_(\d+(?:\.\d+)+)",
                subprocess.run(
                    ["readelf", "--version-info", str(path)],
                    capture_output=True,
                    text=True,
                    check=False,
                ).stdout,
            )
            for version in versions:
                numeric = tuple(int(part) for part in version.split("."))
                if numeric > minimum_glibc:
                    minimum_glibc = numeric
        manifest["required_libraries"] = sorted(libraries)
        manifest["minimum_glibc"] = ".".join(str(part) for part in minimum_glibc)
    (target / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-bin", type=Path, required=True)
    parser.add_argument("--source-share", type=Path, required=True)
    parser.add_argument("--source-lib", type=Path)
    args = parser.parse_args()
    try:
        output = stage(
            args.source_bin.resolve(),
            args.source_share.resolve(),
            args.source_lib.resolve() if args.source_lib else None,
        )
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(
            f"PostgreSQL runtime staging failed: {type(exc).__name__}", file=sys.stderr
        )
        return 2
    print(f"Staged PostgreSQL 16 runtime: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
