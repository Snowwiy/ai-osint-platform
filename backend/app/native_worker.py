"""Fixed native worker launcher with no Celery or dynamic handlers."""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.native_runtime import configure_native_environment


def main(argv: list[str] | None = None) -> int:
    configure_native_environment()
    parser = argparse.ArgumentParser(prog="RavenTechWorker")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--version", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)
    from app.core.config import settings

    if args.version:
        print(settings.APP_VERSION)
        return 0
    from app.native_cli import check_native_runtime

    errors = check_native_runtime()
    if errors:
        print("Native worker check failed: " + ", ".join(errors), file=sys.stderr)
        return 2
    if args.check:
        print("Native worker check passed.")
        return 0
    try:
        from app.native_runtime import prepare_native_directories

        prepare_native_directories()
        from app.core.logging import configure_logging
        from app.worker import run_worker

        configure_logging("worker")
        asyncio.run(run_worker())
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        print("Native worker could not start; see sanitized log.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
