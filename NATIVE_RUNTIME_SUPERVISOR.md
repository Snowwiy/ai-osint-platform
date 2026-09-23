# Native Tauri runtime supervisor (Phase 5BL)

The Tauri application owns the native runtime lifecycle. On release builds, it resolves only the target platform's bundled `native-runtime/backend` and `native-runtime/worker` directories. Source/development builds may resolve only the repository's fixed `desktop/dist-native/<os>-x86_64` locations. It never searches `PATH`, accepts an executable path from the UI, or accepts user arguments.

## Startup and ownership

The supervisor acquires an application-wide lease (a per-user named mutex on Windows and an OS file lock on Linux) before it can start children. This prevents a second desktop instance from starting another worker. It probes loopback port 8000 and validates the health contract, release metadata, expected version `5.0.0-rc6`, `RUNTIME_PROFILE=desktop`, and native PostgreSQL job engine. A healthy compatible pre-existing backend is marked external. An incompatible or unrelated service is reported as a version mismatch or port conflict; RavenTech does not terminate it or choose another port.

The backend is launched with fixed `--serve` arguments. The supervisor waits for database, migration, and storage checks before starting the worker with fixed `--run` arguments. Worker readiness comes from the existing PostgreSQL heartbeat, not a second worker-state store. For a fresh native desktop installation, PostgreSQL 16 is managed as a local child; configured external databases remain external. Redis and Celery are optional in native mode. Package version and platform are checked before execution. See [MANAGED_POSTGRESQL_RUNTIME.md](MANAGED_POSTGRESQL_RUNTIME.md).

## Monitoring and recovery

The normalized Tauri status command reports runtime profile, OS/architecture, backend/worker state and ownership, PID where owned, release, readiness, PostgreSQL state, optional Redis/Celery state, bounded restart count, last safe error, and a capped recent-message ring. The bilingual Local Runtime panel refreshes independently of the embedded React lifecycle. Reloading the frontend does not spawn or stop services.

An owned component receives at most three delayed restart attempts (2, 5, and 10 seconds). After that, the UI reports a crash loop and requires an explicit retry. Runtime actions are fixed component/action enums. Start is non-destructive; stop/restart requires confirmation and is rejected for external processes. No frontend action can provide a PID, executable path, shell text, or arbitrary arguments.

## Shutdown

On desktop exit, the supervisor asks the owned worker and then backend to stop through a per-component marker in the platform runtime state directory. The worker polls at bounded intervals, finishes safe job boundaries, and marks its PostgreSQL heartbeat as stopping. The backend requests its normal server shutdown. If a child does not exit within its bounded grace period, Tauri terminates only the retained child handle. PostgreSQL and externally managed processes are untouched. Windows uses no visible console window; Linux children are ordinary Tauri-owned processes and are not installed as systemd services.

Sanitized lifecycle events are appended to a size-bounded local `runtime-audit.jsonl`. Child stdout/stderr are not streamed to the UI; backend and worker use the existing platform-native rotating logs. Secrets and full environments are not included in runtime state or audit entries.

## Runtime profiles and packaging

Release desktop defaults to `RUNTIME_PROFILE=desktop`; a debug Tauri run defaults to `development`. Explicit `docker` profile disables automatic native children. Docker Compose, Python development, Redis/Celery compatibility, and external FastAPI workflows remain supported. Windows portable and NSIS packaging include only the Windows x86_64 backend/worker payload. Linux x86_64 uses a target-native Tauri package with sibling `native-runtime` directories. PostgreSQL is never bundled.

The runtime's Windows configuration remains under `%LOCALAPPDATA%\RavenTech OSINT\config`; Linux uses XDG config/data/state directories with standard home-directory fallbacks. The supervisor's stop markers, lock, and bounded audit file live in the runtime state directory. No OS login autostart, service installation, updater, or automatic download is introduced.

## Validation limits and roadmap

This phase targets Windows x86_64 and Linux x86_64. Linux WSL execution is Linux runtime evidence, not clean-machine acceptance. A Linux GUI result must be reported separately from Linux supervisor-core tests. Phase 5BM adds the managed PostgreSQL child; Docker-optional finalization, clean-machine acceptance, and Knowledge ingestion remain future phases. Knowledge imports must later use the fixed PostgreSQL job abstraction, not a direct Celery call.
