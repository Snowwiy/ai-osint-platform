# RavenTech OSINT Desktop 5.0.0-rc6 — Unsigned Local Installer

This workflow creates an **unsigned** NSIS installer for local Windows testing.
It is not a trusted or public release. Windows SmartScreen may warn because no
code-signing certificate is configured.

## Prerequisites

- Windows 10 or 11 with Microsoft Edge WebView2 Runtime already installed
- Node.js and npm dependencies installed in `frontend/` and `desktop/`
- Rust/Cargo with the locked desktop dependencies already available
- Tauri NSIS bundler tools already cached by a separately approved setup step;
  the build intentionally fails instead of downloading missing tools
- a host-reachable PostgreSQL instance and a local runtime configuration file

The installer contains the Tauri shell and validated Windows x86_64 PyInstaller
backend/worker resources. It does not contain PostgreSQL, `.env`, credentials,
backups, reports, logs, Redis, or Celery.

## Build and validate

From `desktop/`:

```powershell
npm run installer:build
npm run installer:validate -- --require-artifact
```

The local output is:

```text
desktop/dist-installer/RavenTech-OSINT-Desktop-5.0.0-rc6/
```

That ignored folder contains the unsigned setup executable, this README, the
license, and `installer-manifest.json` with SHA-256 checksums. Do not publish it.
The exact installer name is
`RavenTech-OSINT-Desktop-5.0.0-rc6-unsigned-setup.exe`.

## PostgreSQL prerequisite

PostgreSQL remains external in Phase 5BL. Configure a host-reachable database
URL in `%LOCALAPPDATA%\RavenTech OSINT\config\.env`. Docker mode remains
supported, but the native desktop profile does not require Redis or Celery.

Expected URLs:

- frontend: embedded in the installed app
- optional browser/development frontend: `http://localhost:5173/`
- backend: `http://localhost:8000`
- health: `http://localhost:8000/health`
- readiness: `http://localhost:8000/health/ready`
- release: `http://localhost:8000/api/v1/release`

On launch the desktop automatically supervises the packaged backend, waits for
PostgreSQL, migrations, and storage readiness, and then starts the packaged worker. It
controls only children started by this desktop session. Existing external
backends/workers are observed but never stopped or restarted. No repository
path is needed for the native runtime.

The installer contains the production React assets, so `npm run dev` and port
5173 are not required to display the installed UI.

## Install, launch, and uninstall

Run the `-unsigned-setup.exe` file and accept the local-test warning only after
verifying its checksum. Launch **RavenTech OSINT Desktop** from the Start menu.
If PostgreSQL is unavailable, Local Runtime shows it as required and waiting.
The window title is **RavenTech OSINT Desktop — Local Workspace**. The current
icon is the repository-owned RavenTech local-candidate asset; public brand
approval remains deferred.

Uninstall from **Settings > Apps > Installed apps > RavenTech OSINT Desktop**.
The current-user installer does not install backend services or remove Docker data.

## Controlled launcher behavior

Only six fixed repository scripts are eligible: start, stop, restart, check,
open frontend, and apply the bounded LAN configuration profile.
Start/stop/restart/configuration require confirmation. Output is sanitized
and capped, and every action has a timeout. No shell/filesystem Tauri plugin or
generic command input is enabled.

## Troubleshooting and limitations

- A SmartScreen warning is expected for this unsigned build.
- Install WebView2 Runtime separately if Windows does not already provide it.
- Start or configure host-reachable PostgreSQL before opening the application.
- Port 8000 must be available on loopback. Port 5173 is needed only for optional
  Vite browser/development mode.
- The first-run checklist reports port conflicts, runtime identity, release
  mismatch, and migration degradation without modifying the machine.
- There is no signing, auto-update, service autostart, database bundle, hosting,
  deployment, DNS, Supabase migration, or public support channel in this phase.
- Signing and production distribution remain deferred.
- Run `npm run smoke -- --require-artifacts` after building both local artifacts.
