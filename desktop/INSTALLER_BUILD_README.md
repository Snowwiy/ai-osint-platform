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
- Docker Desktop for PostgreSQL, Redis, and the FastAPI backend

The installer contains only the Tauri desktop shell. It does not contain Docker,
PostgreSQL, Redis, the backend, `.env`, credentials, backups, reports, or logs.

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

## Start the platform before launching

From the repository root, start the required Docker services and local frontend:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local\start_platform.ps1
```

Expected URLs:

- frontend: `http://localhost:5173`
- backend: `http://localhost:8000`
- health: `http://localhost:8000/health`
- readiness: `http://localhost:8000/health/ready`
- release: `http://localhost:8000/api/v1/release`

The desktop shell never starts services automatically. On first launch, enter
the local repository root manually. The shell saves it only after canonical
validation of the compose, backend, frontend, desktop, Python, and five approved
script markers. It never accepts a script name, command argument, or arbitrary
PowerShell command. The five script contents must match this desktop build;
invalid, altered, or missing paths retain copy-only guidance.

## Install, launch, and uninstall

Run the `-unsigned-setup.exe` file and accept the local-test warning only after
verifying its checksum. Launch **RavenTech OSINT Desktop** from the Start menu.
If the services are offline, the shell shows local startup guidance.
The window title is **RavenTech OSINT Desktop — Local Workspace**. The current
icon is the repository-owned RavenTech local-candidate asset; public brand
approval remains deferred.

Uninstall from **Settings > Apps > Installed apps > RavenTech OSINT Desktop**.
The current-user installer does not install backend services or remove Docker data.

## Controlled launcher behavior

Only five fixed repository scripts are eligible: start, stop, restart, check,
and open frontend. Start/stop/restart require confirmation. Output is sanitized
and capped, and every action has a timeout. No shell/filesystem Tauri plugin or
generic command input is enabled.

## Troubleshooting and limitations

- A SmartScreen warning is expected for this unsigned build.
- Install WebView2 Runtime separately if Windows does not already provide it.
- Start Docker Desktop and the platform before opening the local application.
- Ports 5173 and 8000 must be available on loopback.
- The first-run checklist reports port conflicts, Docker detection, release
  mismatch, and migration degradation without modifying the machine.
- There is no signing, auto-update, service autostart, database bundle, hosting,
  deployment, DNS, Supabase migration, or public support channel in this phase.
- Signing and production distribution remain deferred.
- Run `npm run smoke -- --require-artifacts` after building both local artifacts.
