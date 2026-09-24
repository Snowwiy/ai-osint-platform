"""Stage a pinned PostgreSQL 16 distribution into ignored native build output."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
REQUIRED_EXTENSIONS = ("pgcrypto", "pg_trgm")


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_contrib_resources(
    source_share: Path, source_lib: Path | None, system: str
) -> None:
    """Reject PostgreSQL trees that cannot satisfy RavenTech's initial schema."""
    suffix = ".dll" if system == "windows" else ".so"
    missing: list[str] = []
    for extension in REQUIRED_EXTENSIONS:
        if not (source_share / "extension" / f"{extension}.control").is_file():
            missing.append(f"share/extension/{extension}.control")
        if not any((source_share / "extension").glob(f"{extension}--*.sql")):
            missing.append(f"share/extension/{extension}--*.sql")
        module = source_lib / f"{extension}{suffix}" if source_lib else None
        if module is None or not module.is_file():
            missing.append(f"lib/{extension}{suffix}")
    if missing:
        raise RuntimeError(
            "Required PostgreSQL contrib resources are missing: "
            + ", ".join(missing)
        )


def stage(
    source_bin: Path,
    source_share: Path,
    source_lib: Path | None,
    source_libpq: Path | None = None,
) -> Path:
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
    validate_contrib_resources(source_share, source_lib, system)
    if system == "linux":
        if source_libpq is None and source_lib is not None:
            candidate = source_lib / "libpq.so.5"
            source_libpq = candidate if candidate.is_file() else None
        if source_libpq is None or not source_libpq.is_file():
            raise RuntimeError(
                "The Linux PostgreSQL runtime requires the matching libpq.so.5 library source."
            )
    suffix = ".exe" if system == "windows" else ""
    files: dict[str, dict[str, object]] = {}
    bin_relative = Path("lib/postgresql/16/bin") if system == "linux" else Path("bin")
    share_relative = Path("share/postgresql/16") if system == "linux" else Path("share")
    lib_relative = Path("lib/postgresql/16/lib") if system == "linux" else Path("lib")
    bin_out = target / bin_relative
    share_out = target / share_relative
    lib_out = target / lib_relative
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
        lib_out.mkdir(parents=True, exist_ok=True)
        for source in source_lib.rglob("*.so*"):
            if not source.is_file():
                continue
            destination = lib_out / source.relative_to(source_lib)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    if system == "linux" and source_libpq is not None:
        lib_out.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_libpq, lib_out / "libpq.so.5")
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
        "bin_directory": bin_relative.as_posix(),
        "share_directory": share_relative.as_posix(),
        "library_directory": lib_relative.as_posix(),
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
        child_environment = os.environ.copy()
        child_environment["LD_LIBRARY_PATH"] = str(lib_out.resolve())
        for name in BINARIES:
            result = subprocess.run(
                ["ldd", str(bin_out / name)],
                capture_output=True,
                text=True,
                check=False,
                env=child_environment,
            )
            if result.returncode != 0 or "not found" in result.stdout:
                raise RuntimeError(
                    f"Linux runtime dependencies are unavailable for {name}."
                )
            for line in result.stdout.splitlines():
                if "=>" in line and "/" in line:
                    dependency, location = line.split("=>", 1)
                    resolved = location.strip().split(" ", 1)[0]
                    if not Path(resolved).resolve().is_relative_to(target.resolve()):
                        libraries.add(dependency.strip())
        for module in lib_out.rglob("*.so*"):
            result = subprocess.run(
                ["ldd", str(module)],
                capture_output=True,
                text=True,
                check=False,
                env=child_environment,
            )
            if result.returncode != 0 or "not found" in result.stdout:
                raise RuntimeError(
                    "A PostgreSQL shared module has missing runtime dependencies."
                )
            for line in result.stdout.splitlines():
                if "=>" in line and "/" in line:
                    dependency, location = line.split("=>", 1)
                    resolved = location.strip().split(" ", 1)[0]
                    if not Path(resolved).resolve().is_relative_to(target.resolve()):
                        libraries.add(dependency.strip())
        for path in [
            *(bin_out / name for name in BINARIES),
            *lib_out.rglob("*.so*"),
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
    parser.add_argument("--source-libpq", type=Path)
    args = parser.parse_args()
    try:
        output = stage(
            args.source_bin.resolve(),
            args.source_share.resolve(),
            args.source_lib.resolve() if args.source_lib else None,
            args.source_libpq.resolve() if args.source_libpq else None,
        )
    except RuntimeError as exc:
        print(
            f"PostgreSQL runtime staging failed: {exc}", file=sys.stderr
        )
        return 2
    except (OSError, subprocess.SubprocessError) as exc:
        print(
            f"PostgreSQL runtime staging failed: {type(exc).__name__}", file=sys.stderr
        )
        return 2
    print(f"Staged PostgreSQL 16 runtime: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
