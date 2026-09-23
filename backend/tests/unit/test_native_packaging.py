from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest
from app.native_cli import reserve_socket, validate_bind
from app.native_runtime import (
    _strip_windows_verbatim_prefix,
    native_paths,
    resource_path,
)
from app.native_server import main as server_main
from app.native_worker import main as worker_main
from jinja2 import Environment, FileSystemLoader


def test_fixed_native_version(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in (
        "RAVENTECH_NATIVE_PACKAGE",
        "RUNTIME_PROFILE",
        "RAVENTECH_CONFIG_FILE",
        "CHROMA_DATA_PATH",
    ):
        monkeypatch.delenv(name, raising=False)
    assert server_main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "5.0.0-rc6"
    assert worker_main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "5.0.0-rc6"


def test_bind_is_loopback_by_default_and_rejects_public() -> None:
    validate_bind("127.0.0.1", 8000)
    validate_bind("192.168.50.10", 8000)
    for host in ("0.0.0.0", "8.8.8.8", "example.com", "169.254.1.1"):
        with pytest.raises(ValueError):
            validate_bind(host, 8000)
    with pytest.raises(ValueError):
        validate_bind("127.0.0.1", 0)


def test_occupied_port_fails_without_killing_owner() -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    try:
        with pytest.raises(OSError, match="unavailable"):
            reserve_socket("127.0.0.1", port)
    finally:
        listener.close()


def test_native_windows_and_xdg_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    windows = native_paths()
    assert windows.config == tmp_path / "Local" / "RavenTech OSINT" / "config"
    assert windows.reports == tmp_path / "Local" / "RavenTech OSINT" / "reports"
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    linux = native_paths()
    assert linux.config == tmp_path / "config" / "raventech-osint"
    assert linux.logs == tmp_path / "state" / "raventech-osint" / "logs"


def test_resources_resolve_without_repository_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("RAVENTECH_NATIVE_PACKAGE", raising=False)
    monkeypatch.chdir(tmp_path)
    assert resource_path("alembic", "versions").is_dir()
    assert resource_path("app", "templates", "reports", "report.html.j2").is_file()


def test_windows_verbatim_resource_prefix_normalization() -> None:
    assert (
        _strip_windows_verbatim_prefix(
            r"\\?\C:\Users\Long Name\RavenTech OSINT\backend.exe"
        )
        == r"C:\Users\Long Name\RavenTech OSINT\backend.exe"
    )
    assert (
        _strip_windows_verbatim_prefix(
            r"\\?\UNC\host\share\RavenTech OSINT\backend.exe"
        )
        == r"\\host\share\RavenTech OSINT\backend.exe"
    )
    assert _strip_windows_verbatim_prefix(r"C:\RavenTech\backend.exe") == (
        r"C:\RavenTech\backend.exe"
    )


@pytest.mark.skipif(sys.platform != "win32", reason="Windows packaged path behavior")
def test_packaged_jinja_template_loads_from_tauri_verbatim_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executable_directory = tmp_path / "RavenTech OSINT Café" / "backend"
    template_directory = (
        executable_directory / "resources" / "app" / "templates" / "reports"
    )
    template_directory.mkdir(parents=True)
    (executable_directory / "RavenTechBackend.exe").touch()
    (template_directory / "report.html.j2").write_text(
        "{{ product }} packaged report", encoding="utf-8"
    )
    monkeypatch.setenv("RAVENTECH_NATIVE_PACKAGE", "1")
    monkeypatch.setattr(
        sys,
        "argv",
        ["\\\\?\\" + str(executable_directory / "RavenTechBackend.exe")],
    )

    template_path = resource_path("app", "templates", "reports", "report.html.j2")
    environment = Environment(loader=FileSystemLoader(template_path.parent))

    assert environment.get_template(template_path.name).render(product="RavenTech") == (
        "RavenTech packaged report"
    )


def test_native_check_is_read_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app import native_cli

    monkeypatch.setenv("RAVENTECH_CONFIG_FILE", str(tmp_path / ".env"))
    monkeypatch.setenv("RUNTIME_PROFILE", "desktop")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://local@127.0.0.1/db")
    monkeypatch.setattr(
        native_cli, "resource_path", lambda *parts: tmp_path / Path(*parts)
    )
    errors = native_cli.check_native_runtime()
    assert "migrations_missing" in errors
    assert "report_template_missing" in errors
    assert not tmp_path.joinpath(".env").exists()


def test_build_manifest_has_only_safe_metadata(tmp_path: Path) -> None:
    import importlib.util

    source = Path(__file__).resolve().parents[3] / "scripts" / "native" / "build.py"
    spec = importlib.util.spec_from_file_location("native_build", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    binary = tmp_path / "binary"
    binary.write_bytes(b"fixed test bytes")
    metadata = module.manifest("backend", binary)
    assert metadata["binary_sha256"]
    assert metadata["version"] == "5.0.0-rc6"
    assert not any("password" in key or "token" in key for key in metadata)
    assert "username" not in metadata
    assert "home" not in metadata
