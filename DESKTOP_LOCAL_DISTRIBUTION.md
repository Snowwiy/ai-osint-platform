# RavenTech OSINT Desktop — Local Distribution

Phase 5BK standalone backend/worker outputs live in ignored `desktop/dist-native/windows-x86_64/` or `desktop/dist-native/linux-x86_64/`. Phase 5BL includes target-matching PyInstaller directories in portable and installer artifacts. Phase 5BM also packages a target-matching PostgreSQL 16 runtime for fresh native installs; configured external databases remain supported. See [NATIVE_BACKEND_PACKAGING.md](NATIVE_BACKEND_PACKAGING.md) and [MANAGED_POSTGRESQL_RUNTIME.md](MANAGED_POSTGRESQL_RUNTIME.md).

The current local Windows test bundle is RavenTech OSINT Desktop `5.0.0-rc6`.

## Current normal desktop use (Phase 5BN)

The packaged Windows/Linux app starts the managed PostgreSQL 16 runtime,
native backend, and native worker, verifies readiness, and opens its embedded
React frontend. It provides native host monitoring and a read-only startup
acceptance card. A fresh install needs no repository path, `.env`, Docker,
Redis, Celery, Python, Node/Vite, external PostgreSQL, PostgreSQL CLI from
`PATH`, PowerShell, Bash, or manual terminal action. PostgreSQL remains
required and runs on loopback; user data remains outside package directories.

The Project-binding, Docker launcher, and Vite instructions in older phase
notes below describe historical compatibility workflows. They are not current
packaged-desktop setup steps. See `NATIVE_DESKTOP_ACCEPTANCE.md` for the frozen
normal workflow and future clean-machine procedures.

On authenticated startup the embedded client loads a read-only monitoring
summary from the local backend and refreshes it on the configured safe interval.
This is dashboard polling, not service autostart or network discovery. LAN
discovery-on-start and service-check-on-start are disabled by default and remain
subject to the existing private-CIDR, target, port, timeout, policy, maintenance,
cooldown, and deduplication controls.
It is an unpublished, unsigned QA workflow—not a public release.

Phase 5BC allows optional runtime orchestration for six fixed repository scripts,
including the bounded LAN configuration profile.
It does not add service autostart or arbitrary shell access.

Phase 5AR adds first-run path binding for installed and portable launches. Enter
the repository root manually and choose **Validate and save**. The path is
accepted only when the compose, backend, frontend, desktop, Python, and all five
approved-script markers exist within the canonical root. No folder browser or
broad filesystem permission is enabled. Script contents must also match the five
copies pinned into the desktop build. Invalid or missing paths remain copy-only.

Phase 5AT adds an original RavenTech OSINT shield/radar icon and a private
aggregate artifact package. The icon SVG is repository-owned and contains no
downloaded artwork, font, or third-party logo. Public brand approval remains a
future release-governance step.

Phase 5AU adds a bilingual three-stage setup wizard for project binding,
prerequisites, and local services. It reports Docker detection, fixed ports,
release/migration state, and the next action without installing software,
editing `.env`, or weakening copy-only fallback.

Phase 5AV adds the final private operator manual, handoff instructions, and
acceptance checklist. These documents do not alter the shell, artifact contents,
or distribution status. Use `DESKTOP_PRIVATE_HANDOFF.md` for private transfer
and `DESKTOP_OPERATOR_ACCEPTANCE_CHECKLIST.md` for the receiving-host record.

Phase 5AW records the complete clean-checkout order in
`FRESH_SETUP_CHECKLIST.md` and dry-runs regeneration of all three ignored RC6
artifact sets. RC6 stays at the existing tag and version; no release is published.

Phase 5AX adds `EXTERNAL_MACHINE_TEST_CHECKLIST.md` for a second authorized
Windows machine. It keeps the repository and aggregate package as separate
inputs, distinguishes runtime from rebuild prerequisites, and documents only
manual, non-destructive recovery.

The RC6 artifact embeds the React production assets and native runtime. Vite at
port 5173 is only for browser/development testing. Docker Compose, Redis, Celery,
Python development, and configured external PostgreSQL remain compatibility
workflows; none is required for a fresh packaged desktop install.

## Local artifacts

- Portable folder: `desktop/dist-portable/RavenTech-OSINT-Desktop-5.0.0-rc6/`
- Installer folder: `desktop/dist-installer/RavenTech-OSINT-Desktop-5.0.0-rc6/`
- Aggregate folder: `desktop/dist-local-release/RavenTech-OSINT-Desktop-5.0.0-rc6/`
- Portable checksums: `portable-manifest.json` inside the portable folder
- Installer checksums: `installer-manifest.json` inside the installer folder

All three folders are Git-ignored. Never commit or publish their binaries from
this phase. The local candidate uses the repository-owned RavenTech icon;
code-signing and public brand/release approval remain deferred.

## Runtime prerequisites

- Windows 10 or 11 with Microsoft Edge WebView2 Runtime already installed
- Supported Linux x86_64 distribution with the shared libraries listed in its
  package manifest
- Loopback ports 8000 and 55432 available for the managed runtime

Build-only requirements are Node/npm, Rust/Cargo, Tauri/NSIS tools, and the
target-native package workflow. These are not runtime requirements. Packages
include the backend, worker, PostgreSQL runtime binaries, and embedded frontend;
they exclude initialized databases, credentials, reports, backups, and user
data. There is no service autostart, arbitrary command input, or remote command
execution.

## Development/Docker compatibility launcher

The desktop can run only `start_platform.ps1`, `stop_platform.ps1`,
`restart_platform.ps1`, `check_platform.ps1`, and `open_platform.ps1` from the
canonical repository `scripts/local/` directory. Start, stop, and restart show a
confirmation dialog. Output is capped, sanitized, and time-bounded.

Portable/dev builds can discover scripts from the repository directory tree.
An installed build outside that tree uses the manually entered, canonicalized
project root only after every fixed marker and pinned script-content check
passes. The legacy launcher is hidden in native desktop mode; this workflow is
for source development and Docker compatibility only.

## Build

From `desktop/` with dependencies already cached:

```powershell
npm ci --offline
npm run portable:build
npm run installer:build
npm run smoke -- --require-artifacts
npm run local-release:package
npm run local-release:validate -- --require-artifact
```

## Start local services in Docker compatibility mode

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local\start_platform.ps1
```

This command is for development/Docker compatibility mode. Native packaged
desktop starts its components without it. Vite at `http://localhost:5173` is
optional; the native embedded frontend uses the local backend on port 8000.

## Install or run

For portable testing, launch `RavenTech OSINT Desktop.exe` from the portable
folder. For installer testing, verify the installer-manifest checksum, then run
`RavenTech-OSINT-Desktop-5.0.0-rc6-unsigned-setup.exe` and launch the Start-menu
entry **RavenTech OSINT Desktop**.

The unsigned installer may trigger Windows SmartScreen. This warning is expected
and must not be described as a trusted signature. Do not bypass organizational
security policy merely to run the test.

## Smoke test

1. Open the packaged desktop and verify the native startup stages in English and Spanish.
2. Verify Database, Backend, Worker, Embedded UI, Monitoring, Migrations, and
   Native Jobs status; no project path or terminal is needed.
3. Start with Docker/Redis/Celery unavailable and confirm the native app becomes
   Ready using the managed database and native worker.
4. Open the embedded frontend and switch the desktop/web UI between English and Spanish.
6. Export one benign report and confirm existing browser behavior is unchanged.
7. Run `npm run portable:validate`, `npm run installer:validate -- --require-artifact`,
   and `npm run smoke -- --require-artifacts`.
8. Run **Check** and verify the last-command result contains no secret or raw stack trace.
9. Confirm start/stop/restart cannot run without accepting the confirmation dialog.

## Uninstall

Open **Settings > Apps > Installed apps**, select **RavenTech OSINT Desktop**,
and choose **Uninstall**. This removes only the desktop shell. It does not remove
Docker services, PostgreSQL data, Redis data, the repository, or local reports.

## Deferred work

Code signing, timestamping, public brand approval, auto-update, public release,
hosting, deployment, DNS, Supabase migration, and production support remain deferred.

The complete local operating guide is `OPERATOR_MANUAL.md`. It preserves the
browser/Docker recovery path and keeps backup/restore outside the desktop
launcher's five-script boundary.

## Phase 5BI desktop runtime

The desktop still uses the Docker backend and PostgreSQL in this phase. It can display `BACKGROUND_JOB_BACKEND=native` and native worker status; Redis/Celery are not required desktop dependencies in that mode. Run `python -m app.worker` separately after applying Alembic 0040. Packaging and supervision of a native backend/PostgreSQL are planned for later phases only. See `NATIVE_BACKGROUND_JOBS.md`.

## Phase 5BJ job dependency

The desktop profile no longer requires Redis or Celery for authentication, monitoring jobs, or readiness. It still requires a separately running FastAPI backend, PostgreSQL, migrations, and native worker; the current distribution commonly runs the backend/database through Docker. Native backend packaging and local PostgreSQL installation are future phases. See `DESKTOP_NATIVE_RUNTIME.md`.

## Phase 5BL — Tauri native runtime supervision

Release desktop runs use the cross-platform Tauri supervisor for the fixed PyInstaller backend and worker. The supervisor verifies the RC6 release and native runtime profile, waits for PostgreSQL/migration/storage prerequisites before starting the worker, and reports owned versus external components. It uses bounded restart attempts and cooperative shutdown markers, and only terminates retained child processes that this desktop launched. A per-user Windows mutex or Linux file lock prevents duplicate desktop sessions from independently starting children. Backend port conflicts and external components are observation-only.

Windows portable/installer packages include Windows x86_64 backend, worker, and managed PostgreSQL resources; Linux x86_64 packaging includes equivalent runtime resources. Fresh native installs use managed PostgreSQL; existing external configurations remain supported. Redis/Celery are not required for native desktop mode, while Docker and development profiles remain supported. No OS autostart, systemd installation, updater, or automatic downloads are added. Linux WSL evidence is not clean-machine Linux acceptance.
