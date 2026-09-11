# RavenTech OSINT Desktop 5.0.0-rc4 — Windows Portable Build

This folder is a local-test portable build. A separate Phase 5AO unsigned local
installer workflow exists, but this portable folder has no installer, signing,
updater, backend service, database, Docker runtime, or production deployment.

## Prerequisites

- supported Windows with Microsoft Edge WebView2 Runtime
- Docker Desktop with Docker Compose
- the RavenTech OSINT repository and local `.env` configuration retained
  separately; never copy `.env` into this portable folder
- Node.js/npm for the separately running Vite frontend

## Start the platform first

From the repository root, run these commands yourself:

```powershell
./scripts/local/start_platform.ps1
cd frontend
npm run dev
```

The portable application never starts services automatically. When it can
discover the repository above its executable, it can run only five fixed local
scripts; start, stop, and restart require confirmation. Copy remains available
for every action, and Vite/Docker direct commands remain copy-only.

## Run the portable application

Double-click `RavenTech OSINT Desktop.exe` after the local services are running.
The containing folder is `RavenTech-OSINT-Desktop-5.0.0-rc4`, the window title
is **RavenTech OSINT Desktop — Local Workspace**, and the icon remains a
documented build-only placeholder pending final brand approval.
The shell checks only these local endpoints:

- frontend: `http://localhost:5173`
- backend: `http://localhost:8000`
- health: `http://localhost:8000/health`
- readiness: `http://localhost:8000/health/ready`
- release: `http://localhost:8000/api/v1/release`

When the stack is healthy, the existing web application opens inside the
desktop shell. Browser mode remains available at `http://localhost:5173`.

On first launch, manually enter the repository root in the setup card. The path
is stored only after fixed marker and build-pinned five-script validation. Resolution then
prefers that saved path, followed by matching current-directory ancestry and
development executable ancestry. Missing or invalid paths retain copy-only mode;
there is no broad folder browser or arbitrary command input.

## Troubleshooting

- **Backend unreachable:** confirm Docker Desktop is running, then use
  `./scripts/local/start_platform.ps1` and
  `./scripts/local/check_platform.ps1` from the repository root.
- **Readiness degraded:** inspect `docker compose ps` and backend logs. The
  portable application displays status only and performs no repair.
- **Frontend unreachable:** run `npm run dev` from `frontend/` and retry.
- **Window does not open:** confirm WebView2 Runtime is installed and that local
  endpoint security policy permits the executable.

Do not copy `.env`, credentials, database backups, generated reports, or client
data into this folder. Validate hashes in `portable-manifest.json` after copying
the folder between local test locations.

## Limitations and security boundary

- Windows local testing only; no installer, public release, or support SLA
- unsigned executable with a build-only placeholder icon
- Docker and the Vite frontend remain separate operator-managed dependencies
- no service autostart or automatic command execution
- no arbitrary command input, shell/filesystem plugin, secret collection,
  remote administration, router
  automation, scanning, exploitation, hosting, deployment, DNS, or Supabase
  migration

For the separate unsigned current-user installer workflow, read
`desktop/INSTALLER_BUILD_README.md`. Portable and installer outputs remain
independent, ignored local artifacts; neither is approved for public release.
After both artifacts exist, run `npm run smoke -- --require-artifacts` from
`desktop/` to check their manifests, checksums, names, permissions, and exclusions.
