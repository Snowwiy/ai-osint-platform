# Managed PostgreSQL Runtime (Phase 5BM)

RavenTech Desktop can run a pinned PostgreSQL 16 runtime without Docker or a separately installed PostgreSQL server. Tauri owns this local child process and keeps it in the same lifecycle as the packaged backend and worker. Python development and Docker profiles remain supported.

## Modes and compatibility

`DATABASE_RUNTIME=managed` selects RavenTech's loopback-only cluster. `DATABASE_RUNTIME=external` preserves an operator-configured database. Existing native installations with a configured `.env` `DATABASE_URL` remain external; only a fresh native desktop install defaults to managed. Docker continues to use its existing `postgres` service hostname and external profile. Compose configuration and volumes are unchanged.

Managed mode requires PostgreSQL 16 x86_64 runtime resources, PostgreSQL-compatible migrations, and the bundled backend/worker. It does not require Docker, Redis, Celery, Python, PostgreSQL CLI tools installed on `PATH`, or a terminal for normal desktop startup. The runtime is not installed as a Windows service or a systemd service.

## Runtime distribution

The selected major version is PostgreSQL 16, matching the project's PostgreSQL 16 Docker service. The Windows x86_64 runtime is staged from the official EnterpriseDB PostgreSQL 16 binary archive. The Linux x86_64 runtime is assembled from the Debian-compatible PostgreSQL 16.15 distribution and staged with its required shared libraries listed in the artifact manifest. Its bundle keeps Debian's relocated `lib/postgresql/16/{bin,lib}` and `share/postgresql/16` layout, including the `pgcrypto` and `pg_trgm` extension modules required by the application schema. PyInstaller remains the backend/worker packaging engine; PostgreSQL is a separate fixed runtime resource. Build-generated resources remain ignored and are checked by per-file SHA-256 manifests.

Only the fixed `postgres`, `initdb`, `psql`, `pg_isready`, and `pg_ctl` programs, their runtime libraries, and PostgreSQL share resources are included. The runtime does not search `PATH` and does not invoke a shell. On Linux, these fixed child processes receive a runtime-specific `LD_LIBRARY_PATH` assembled from the validated packaged directories; the server uses loopback TCP without requiring a system Unix-socket directory. Linux dynamic-library requirements vary by distribution; the manifest lists required shared libraries and minimum glibc observed at build time. Debian 13 WSL runtime validation is Linux runtime evidence, not clean-machine acceptance.

## Data, ownership, and credential

The database is stored outside the installed application:

- Windows: `%LOCALAPPDATA%\RavenTech OSINT\data\postgres\16`, with runtime secret/log state under the matching application state directory.
- Linux: `$XDG_DATA_HOME/raventech-osint/postgres/16` and `$XDG_STATE_HOME/raventech-osint/runtime/postgres`; when unset, standard `~/.local/share` and `~/.local/state` fallbacks are used.

The persistent data directory is never stored beside packaged binaries. An adjacent `ownership.json` marker contains the application identity, runtime format, PostgreSQL major, installation id, creation time, port, and initialization state. It contains no credential. A missing, malformed, incompatible, or mismatched marker does not authorize adoption or deletion. Unknown non-empty directories and unmarked initialized clusters are preserved and refused. RavenTech does not automatically reinitialize, delete, downgrade, reset, or repair the cluster.

A cryptographically random per-installation password is stored in an application-owned secret file. Linux creates it with mode 0600 and private parent directories. Windows stores it below the current-user LocalAppData boundary and relies on that directory's user ACL; this is not Windows Credential Manager protection. The backend connection is injected only into the owned child environment and is never returned to the frontend or written to manifests/logs. The database bootstrap superuser is changed to `NOLOGIN`; the application role is a non-superuser owner of only the RavenTech database.

## Network and authentication policy

The preferred managed port is fixed at `55432`. RavenTech checks it before initialization/start and fails without contacting or stopping an unknown listener if it is occupied. It does not take over port 5432 or select a different port silently. The server listens only on `127.0.0.1`; the generated HBA file allows only loopback TCP and local socket access using SCRAM-SHA-256. There is no LAN or public binding and no `trust` authentication. PostgreSQL remains private to the host; LAN agents communicate with RavenTech's backend.

## Lifecycle and migrations

Startup order is PostgreSQL artifact/ownership validation, safe first-run `initdb`, database readiness, fixed Alembic forward upgrade to `head`, backend health/readiness/release checks, and worker startup. A retry of interrupted initialization is allowed only when the RavenTech ownership marker is valid, says initialization did not complete, and the expected data directory still exists and is empty. Nonempty or unmarked data, symlinks, and initialized clusters remain fail-closed and are preserved. On normal shutdown the worker and backend stop first, then the owned PostgreSQL child is asked to stop gracefully through the fixed `pg_ctl` path. External databases are never started, stopped, or restarted by the desktop.

PostgreSQL failures are reported with a sanitized reason. `initdb` output is classified internally into a bounded failure category and exit code; raw output is not retained or shown. An initialization/configuration failure is not counted as a PostgreSQL process crash loop. A valid, empty, RavenTech-owned incomplete initialization can be retried; any data-bearing incomplete directory remains protected. Process-start/readiness restart attempts are bounded; after the threshold, explicit retry is required. The cluster is preserved and no destructive repair is attempted. Schema migration is forward-only and does not drop user data. Existing-managed-database migration backup is not yet integrated with a native-safe backup flow; treat migration backup/restore as partially supported and retain an operator-controlled backup for important data.

## Status and actions

Operations Center reports mode, state, version, loopback-only address/port, ownership, migration state, PID, uptime when available, restart count, and a safe last error. Start/stop/restart actions are available only for the owned managed database; stopping it first stops dependent RavenTech children and requires confirmation. External mode is informational and has no lifecycle actions. Passwords, full database URLs, and secret paths are never shown.

## Packaged Windows resource paths

The PostgreSQL runtime package keeps `initdb.exe` and `postgres.exe` together
under the immutable packaged `postgresql/bin` directory. Tauri may resolve the
Windows resource root with an extended-length `\\?\` prefix; PostgreSQL's
`initdb` sibling-executable lookup did not accept that spelling in the packaged
startup path. The native supervisor now normalizes only that immutable resource
root to a normal absolute drive or UNC path before resolving executables and the
PostgreSQL `share` directory. Managed data and state paths remain separate
platform-native mutable locations. This does not relax ownership validation,
unknown-data protection, SCRAM authentication, loopback binding, or safe retry
conditions.

An initdb failure is reported separately from a PostgreSQL process crash loop.
Retry is allowed only for a valid RavenTech ownership marker for the same
installation, `initialized=false`, an empty expected data directory, and no
running PostgreSQL process using it. Unknown, non-empty, symlinked, or already
initialized data remains protected.

## Validation and remaining work

The Phase 5BM live tests exercise isolated bootstrap, application-role restrictions, clean stop/restart, and persistence on Windows and Debian/WSL. Full clean-machine Windows and Linux acceptance is still reserved for later phases. A WSL result is not a clean Linux machine result. Managed PostgreSQL major-version upgrades, automatic OS startup, permanent OS services, Knowledge ingestion, public release, and signing are out of scope.

Finalization snapshot (2026-09-22): Windows Tauri managed-runtime startup, migrations, health/readiness/release, PostgreSQL-backed authentication and refresh rotation, Monitoring/Operations APIs, native worker heartbeat, an allowlisted job, graceful shutdown, and relaunch persistence passed against an isolated marked test directory. Windows portable, local-release, and unsigned NSIS packages were rebuilt and passed their strict validators. The Linux x86_64 package was rebuilt and passed validation in Debian/WSL; Linux managed-PostgreSQL bootstrap/restart/persistence and Cargo tests passed there. Linux Tauri GUI acceptance and clean-machine Windows/Linux installation acceptance were not run.

Phase 5BN finalizes the packaged runtime as Docker-optional; this does not change PostgreSQL's required status or managed/external database behavior. Future phases are 5BO Windows clean-machine acceptance, 5BP Linux clean-machine acceptance, and 5BQ Obsidian plus verified Knowledge ingestion.

Follow-up packaged validation on 2026-09-23 reproduced the Windows failure with an extended-length Tauri resource path and identified why `initdb` could not find sibling `postgres.exe`. The immutable resource root is now normalized before resolving PostgreSQL binaries. A current packaged Tauri launch and same-profile relaunch passed managed initialization/reuse, health/readiness/release, worker heartbeat, and isolated data persistence. The full interactive zero-Docker gate remains incomplete; see [NATIVE_DESKTOP_ACCEPTANCE.md](NATIVE_DESKTOP_ACCEPTANCE.md).

Debian 13 WSL package validation on 2026-09-24 launched the current Tauri
bundle with isolated XDG roots. The bundled PostgreSQL 16.15 runtime initialized
with the required contrib extensions, applied migrations, bound only to
loopback, and supported backend/worker health plus authenticated application
API workflows. The packaged child processes use the bundled library layout;
Linux clean-machine installation and visual GUI acceptance remain **NOT RUN**.
