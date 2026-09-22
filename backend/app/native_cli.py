"""Small fixed CLI shared by the packaged backend and worker."""

from __future__ import annotations

import ipaddress
import os
import socket
from pathlib import Path

from app.native_runtime import native_paths, resource_path


def validate_bind(host: str, port: int) -> None:
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("Bind host must be a literal private or loopback IP.") from exc
    if not isinstance(address, ipaddress.IPv4Address) or not (
        address.is_loopback or address.is_private
    ) or address.is_unspecified or address.is_link_local:
        raise ValueError("Public, wildcard, and link-local binds are not supported.")
    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535.")


def reserve_socket(host: str, port: int) -> socket.socket:
    validate_bind(host, port)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind((host, port))
        listener.listen(128)
        return listener
    except OSError as exc:
        listener.close()
        raise OSError("Configured backend port is unavailable.") from exc


def check_native_runtime() -> list[str]:
    """Read-only checks. Return fixed safe codes, never config values."""
    from app.core.config import settings

    errors: list[str] = []
    config = Path(os.environ["RAVENTECH_CONFIG_FILE"])
    if not config.is_file() and not os.getenv("DATABASE_URL"):
        errors.append("external_config_missing")
    if settings.RUNTIME_PROFILE != "desktop":
        errors.append("desktop_profile_required")
    if not settings.DATABASE_URL.startswith(("postgresql+asyncpg://", "postgresql://")):
        errors.append("postgresql_configuration_required")
    if settings.startup_errors():
        errors.append("invalid_configuration")
    migration_dir = resource_path("alembic", "versions")
    if not migration_dir.is_dir() or not any(migration_dir.glob("*.py")):
        errors.append("migrations_missing")
    if not resource_path("app", "templates", "reports", "report.html.j2").is_file():
        errors.append("report_template_missing")
    if not resource_path("data", "knowledge").is_dir():
        errors.append("knowledge_resources_missing")
    paths = native_paths()
    if not all(path.is_absolute() for path in (paths.config, paths.data, paths.state)):
        errors.append("runtime_paths_invalid")
    try:
        from app.main import create_app

        if not callable(create_app):
            errors.append("application_import_failed")
    except ModuleNotFoundError as exc:
        missing = (
            exc.name
            if exc.name and exc.name.replace("_", "").replace(".", "").isalnum()
            else "module"
        )
        errors.append(f"application_import_missing:{missing}")
    except Exception as exc:
        errors.append(f"application_import_failed:{type(exc).__name__}")
    return errors
