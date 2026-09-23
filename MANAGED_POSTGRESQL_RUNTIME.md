# Managed PostgreSQL Runtime (Phase 5BM)

RavenTech Desktop can run a pinned PostgreSQL 16 runtime without Docker or a separately installed PostgreSQL server. Tauri owns this local child process and keeps it in the same lifecycle as the packaged backend and worker. Python development and Docker profiles remain supported.

## Modes and compatibility

`DATABASE_RUNTIME=managed` selects RavenTech's loopback-only cluster. `DATABASE_RUNTIME=external` preserves an operator-configured database. Existing native installations with a configured `.env` `DATABASE_URL` remain external; only a fresh native desktop install defaults to managed. Docker continues to use its existing `postgres` service hostname and external profile. Compose configuration and volumes are unchanged.

Managed mode requires PostgreSQL 16 x86_64 runtime resources, PostgreSQL-compatible migrations, and the bundled backend/worker. It does not require Docker, Redis, Celery, Python, PostgreSQL CLI tools installed on `PATH`, or a terminal for normal desktop startup. The runtime is not installed as a Windows service or a systemd service.

## Runtime distribution

The selected major version is PostgreSQL 16, matching the project's PostgreSQL 16 Docker service. The Windows x86_64 runtime is staged from the official EnterpriseDB PostgreSQL 16 binary archive. The Linux x86_64 runtime is built from the official PostgreSQL source distribution in Debian/WSL and staged with its required shared libraries listed in the artifact manifest. PyInstaller remains the backend/worker packaging engine; PostgreSQL is a separate fixed runtime resource. Build-generated resources remain ignored and are checked by per-file SHA-256 manifests.

Only the fixed `postgres`, `initdb`, `psql`, `pg_isready`, and `pg_ctl` programs, their runtime libraries, and PostgreSQL share resources are included. The runtime does not search `PATH` and does not invoke a shell. Linux dynamic-library requirements vary by distribution; the manifest lists required shared libraries and minimum glibc observed at build time. WSL testing is Linux runtime testing, not clean-machine acceptance.

## Data, ownership, and credential

The database is stored outside the installed application:

- Windows: `%LOCALAPPDATA%\RavenTech OSINT\data\postgres\16`, with runtime secret/log state under the matching application state directory.
- Linux: `$XDG_DATA_HOME/raventech-osint/postgres/16` and `$XDG_STATE_HOME/raventech-osint/runtime/postgres`; when unset, standard `~/.local/share` and `~/.local/state` fallbacks are used.

The persistent data directory is never stored beside packaged binaries. An adjacent `ownership.json` marker contains the application identity, runtime format, PostgreSQL major, installation id, creation time, port, and initialization state. It contains no credential. A missing, malformed, incompatible, or mismatched marker does not authorize adoption or deletion. Unknown non-empty directories and unmarked initialized clusters are preserved and refused. RavenTech does not automatically reinitialize, delete, downgrade, reset, or repair the cluster.

A cryptographically random per-installation password is stored in an application-owned secret file. Linux creates it with mode 0600 and private parent directories. Windows stores it below the current-user LocalAppData boundary and relies on that directory's user ACL; this is not Windows Credential Manager protection. The backend connection is injected only into the owned child environment and is never returned to the frontend or written to manifests/logs. The database bootstrap superuser is changed to `NOLOGIN`; the application role is a non-superuser owner of only the RavenTech database.

## Network and authentication policy

The preferred managed port is fixed at `55432`. RavenTech checks it before initialization/start and fails without contacting or stopping an unknown listener if it is occupied. It does not take over port 5432 or select a different port silently. The server listens only on `127.0.0.1`; the generated HBA file allows only loopback TCP and local socket access using SCRAM-SHA-256. There is no LAN or public binding and no `trust` authentication. PostgreSQL remains private to the host; LAN agents communicate with RavenTech's backend.

## Lifecycle and migrations

Startup order is PostgreSQL artifact/ownership validation, safe first-run `initdb` if and only if the owned directory is new and empty, database readiness, fixed Alembic forward upgrade to `head`, backend health/readiness/release checks, and worker startup. On normal shutdown the worker and backend stop first, then the owned PostgreSQL child is asked to stop gracefully through the fixed `pg_ctl` path. External databases are never started, stopped, or restarted by the desktop.

PostgreSQL failure is reported with a sanitized reason. Restart attempts are bounded; after the threshold, manual retry is required. The cluster is preserved, and crash recovery never reruns `initdb` or uses destructive repair. Schema migration is forward-only and does not drop user data. Existing-managed-database migration backup is not yet integrated with a native-safe backup flow; treat migration backup/restore as partially supported and retain an operator-controlled backup for important data.

## Status and actions

Operations Center reports mode, state, version, loopback-only address/port, ownership, migration state, PID, uptime when available, restart count, and a safe last error. Start/stop/restart actions are available only for the owned managed database; stopping it first stops dependent RavenTech children and requires confirmation. External mode is informational and has no lifecycle actions. Passwords, full database URLs, and secret paths are never shown.

## Validation and remaining work

The Phase 5BM live tests exercise isolated bootstrap, application-role restrictions, clean stop/restart, and persistence on Windows and Debian/WSL. Full clean-machine Windows and Linux acceptance is still reserved for later phases. A WSL result is not a clean Linux machine result. Managed PostgreSQL major-version upgrades, automatic OS startup, permanent OS services, Knowledge ingestion, public release, and signing are out of scope.

Finalization snapshot (2026-09-22): Windows Tauri managed-runtime startup, migrations, health/readiness/release, PostgreSQL-backed authentication and refresh rotation, Monitoring/Operations APIs, native worker heartbeat, an allowlisted job, graceful shutdown, and relaunch persistence passed against an isolated marked test directory. Windows portable, local-release, and unsigned NSIS packages were rebuilt and passed their strict validators. The Linux x86_64 package was rebuilt and passed validation in Debian/WSL; Linux managed-PostgreSQL bootstrap/restart/persistence and Cargo tests passed there. Linux Tauri GUI acceptance and clean-machine Windows/Linux installation acceptance were not run.

Future roadmap: 5BN completes Docker-optional desktop finalization; 5BO and 5BP cover clean-machine Windows/Linux acceptance; 5BQ covers Obsidian and verified Knowledge ingestion.
