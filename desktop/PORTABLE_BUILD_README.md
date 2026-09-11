# RavenTech OSINT Desktop 5.0.0-rc6 — Windows Portable Build

This folder is a local-test portable build. A separate Phase 5AO unsigned local
installer workflow exists, but this portable folder has no installer, signing,
updater, backend service, database, Docker runtime, or production deployment.

## Prerequisites

- supported Windows with Microsoft Edge WebView2 Runtime
- Docker Desktop with Docker Compose
- the RavenTech OSINT repository and local `.env` configuration retained
  separately; never copy `.env` into this portable folder
- Node.js/npm only when rebuilding or running browser/development mode

## Start the platform first

From the repository root, start the Docker/backend services yourself:

```powershell
./scripts/local/start_platform.ps1
```

The portable executable contains the built React frontend. For optional browser
or desktop-development testing only, run `npm run dev` from `frontend/`.

The portable application never starts services automatically. When it can
discover the repository above its executable, it can run only five fixed local
scripts; start, stop, and restart require confirmation. Copy remains available
for every action, and Vite/Docker direct commands remain copy-only.

## Run the portable application

Double-click `RavenTech OSINT Desktop.exe` after the local services are running.
The containing folder is `RavenTech-OSINT-Desktop-5.0.0-rc6`, the window title
is **RavenTech OSINT Desktop — Local Workspace**, and the icon remains a
repository-owned local-candidate asset; public brand approval remains deferred.
The release shell loads its packaged frontend and checks these local endpoints:

- frontend: embedded (development fallback: `http://localhost:5173/`)
- backend: `http://localhost:8000`
- health: `http://localhost:8000/health`
- readiness: `http://localhost:8000/health/ready`
- release: `http://localhost:8000/api/v1/release`

When the backend is ready, the existing web application opens from bundled
assets inside the desktop shell. Browser mode remains optionally available at
`http://localhost:5173` when Vite is started separately.

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
- **Frontend unavailable in development:** run `npm run dev` from `frontend/`.
  In a portable release, **Frontend: Embedded** is expected and port 5173 is
  not required.
- **Window does not open:** confirm WebView2 Runtime is installed and that local
  endpoint security policy permits the executable.

Do not copy `.env`, credentials, database backups, generated reports, or client
data into this folder. Validate hashes in `portable-manifest.json` after copying
the folder between local test locations.

## Limitations and security boundary

- Windows local testing only; no installer, public release, or support SLA
- unsigned executable with the repository-owned RavenTech local-candidate icon
- Docker and the backend remain separate operator-managed dependencies; Vite
  is optional for browser/development testing
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
