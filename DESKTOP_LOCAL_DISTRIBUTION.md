# RavenTech OSINT Desktop — Local Distribution

Phase 5AP defines the local Windows test bundle for RavenTech OSINT Desktop
`5.0.0-rc5`. It is an unpublished, unsigned QA workflow—not a public release.

Phase 5AQ adds optional runtime orchestration for five fixed repository scripts.
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

## Local artifacts

- Portable folder: `desktop/dist-portable/RavenTech-OSINT-Desktop-5.0.0-rc5/`
- Installer folder: `desktop/dist-installer/RavenTech-OSINT-Desktop-5.0.0-rc5/`
- Aggregate folder: `desktop/dist-local-release/RavenTech-OSINT-Desktop-5.0.0-rc5/`
- Portable checksums: `portable-manifest.json` inside the portable folder
- Installer checksums: `installer-manifest.json` inside the installer folder

All three folders are Git-ignored. Never commit or publish their binaries from
this phase. The local candidate uses the repository-owned RavenTech icon;
code-signing and public brand/release approval remain deferred.

## Prerequisites

- Windows 10 or 11 with Microsoft Edge WebView2 Runtime already installed
- Docker Desktop with Docker Compose
- RavenTech OSINT repository and local configuration kept outside artifacts
- Node.js/npm dependencies for the separately running Vite frontend
- Rust/Cargo and pinned Tauri/NSIS build tools already available locally

No backend, PostgreSQL, Redis, Docker runtime, database, or credentials are
bundled. There is no service autostart, arbitrary command input, or remote
command execution.

## Controlled launcher

The desktop can run only `start_platform.ps1`, `stop_platform.ps1`,
`restart_platform.ps1`, `check_platform.ps1`, and `open_platform.ps1` from the
canonical repository `scripts/local/` directory. Start, stop, and restart show a
confirmation dialog. Output is capped, sanitized, and time-bounded.

Portable/dev builds can discover scripts from the repository directory tree.
An installed build outside that tree cannot be given an arbitrary path: it
explains that scripts are unavailable and leaves the copy button active.

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

## Start local services

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local\start_platform.ps1
cd frontend
npm run dev
```

Expected local URLs are `http://localhost:5173` for the frontend and
`http://localhost:8000` for the backend. Health, readiness, and release checks
use `/health`, `/health/ready`, and `/api/v1/release`.

## Install or run

For portable testing, launch `RavenTech OSINT Desktop.exe` from the portable
folder. For installer testing, verify the installer-manifest checksum, then run
`RavenTech-OSINT-Desktop-5.0.0-rc5-unsigned-setup.exe` and launch the Start-menu
entry **RavenTech OSINT Desktop**.

The unsigned installer may trigger Windows SmartScreen. This warning is expected
and must not be described as a trusted signature. Do not bypass organizational
security policy merely to run the test.

## Smoke test

1. Confirm the local status screen opens and identifies frontend/backend state.
2. Reject a non-repository path, then bind the valid project root and confirm all
   fixed markers and approved scripts report available.
3. With services stopped, confirm readable English/Spanish Docker, port, release,
   migration, backend, frontend, and script guidance.
4. Start Docker services and Vite through the approved workflow; confirm health and readiness become ready.
5. Open the embedded frontend and switch the desktop/web UI between English and Spanish.
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
