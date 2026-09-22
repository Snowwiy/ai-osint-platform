"""Fixed native backend launcher; the desktop supervisor arrives in 5BL."""

from __future__ import annotations

import argparse
import sys

from app.native_runtime import configure_native_environment


def main(argv: list[str] | None = None) -> int:
    configure_native_environment()
    parser = argparse.ArgumentParser(prog="RavenTechBackend")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--version", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--migration-status", action="store_true")
    mode.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    from app.core.config import settings

    if args.version:
        print(settings.APP_VERSION)
        return 0
    from app.native_cli import check_native_runtime, reserve_socket

    errors = check_native_runtime()
    if errors:
        print("Native runtime check failed: " + ", ".join(errors), file=sys.stderr)
        return 2
    if args.check:
        print("Native runtime check passed.")
        return 0
    if args.migration_status:
        from alembic.script import ScriptDirectory
        from sqlalchemy import create_engine, text

        from app.native_runtime import resource_path

        try:
            head = ScriptDirectory(str(resource_path("alembic"))).get_current_head()
            engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
            try:
                with engine.connect() as connection:
                    current = connection.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).scalar_one_or_none()
            finally:
                engine.dispose()
            print(f"Applied migration: {current or 'none'}; available head: {head}")
            return 0
        except Exception:
            print("Migration status is unavailable.", file=sys.stderr)
            return 2
    from app.native_runtime import prepare_native_directories

    try:
        listener = reserve_socket(args.host, args.port)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        prepare_native_directories()
        from app.core.logging import configure_logging

        configure_logging()
        import uvicorn

        from app.main import create_app

        server = uvicorn.Server(
            uvicorn.Config(
                create_app(), host=args.host, port=args.port, log_config=None
            )
        )
        server.run(sockets=[listener])
        return 0 if server.started else 2
    except Exception:
        print("Native backend could not start; see sanitized log.", file=sys.stderr)
        return 2
    finally:
        listener.close()


if __name__ == "__main__":
    raise SystemExit(main())
