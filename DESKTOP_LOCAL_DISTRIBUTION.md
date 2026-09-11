# RavenTech OSINT Desktop — Local Distribution

Phase 5AP defines the local Windows test bundle for RavenTech OSINT Desktop
`5.0.0-rc4`. It is an unpublished, unsigned QA workflow—not a public release.

## Local artifacts

- Portable folder: `desktop/dist-portable/RavenTech-OSINT-Desktop-5.0.0-rc4/`
- Installer folder: `desktop/dist-installer/RavenTech-OSINT-Desktop-5.0.0-rc4/`
- Portable checksums: `portable-manifest.json` inside the portable folder
- Installer checksums: `installer-manifest.json` inside the installer folder

Both folders are Git-ignored. Never commit or publish their binaries from this
phase. The build-only icon is a placeholder; final icon and brand approval are
deferred and do not block local QA.

## Prerequisites

- Windows 10 or 11 with Microsoft Edge WebView2 Runtime already installed
- Docker Desktop with Docker Compose
- RavenTech OSINT repository and local configuration kept outside artifacts
- Node.js/npm dependencies for the separately running Vite frontend
- Rust/Cargo and pinned Tauri/NSIS build tools already available locally

No backend, PostgreSQL, Redis, Docker runtime, database, or credentials are
bundled. There is no service autostart or automatic command execution.

## Build

From `desktop/` with dependencies already cached:

```powershell
npm ci --offline
npm run portable:build
npm run installer:build
npm run smoke -- --require-artifacts
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
`RavenTech-OSINT-Desktop-5.0.0-rc4-unsigned-setup.exe` and launch the Start-menu
entry **RavenTech OSINT Desktop**.

The unsigned installer may trigger Windows SmartScreen. This warning is expected
and must not be described as a trusted signature. Do not bypass organizational
security policy merely to run the test.

## Smoke test

1. Confirm the local status screen opens and identifies frontend/backend state.
2. With services stopped, confirm readable English/Spanish startup guidance.
3. Start Docker services and Vite manually; confirm health and readiness become ready.
4. Open the embedded frontend and switch the desktop/web UI between English and Spanish.
5. Export one benign report and confirm existing browser behavior is unchanged.
6. Run `npm run portable:validate`, `npm run installer:validate -- --require-artifact`,
   and `npm run smoke -- --require-artifacts`.

## Uninstall

Open **Settings > Apps > Installed apps**, select **RavenTech OSINT Desktop**,
and choose **Uninstall**. This removes only the desktop shell. It does not remove
Docker services, PostgreSQL data, Redis data, the repository, or local reports.

## Deferred work

Code signing, timestamping, final icon approval, auto-update, public release,
hosting, deployment, DNS, Supabase migration, and production support remain deferred.
