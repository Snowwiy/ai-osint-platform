# RavenTech OSINT Desktop 5.0.0-rc6 — Windows Portable Build

This folder is a private local-test portable build. Managed PostgreSQL 16 is included.
It contains the Tauri shell, fixed PyInstaller backend/worker runtime folders,
and the PostgreSQL runtime; it
does not contain an installer, signing, updater, user database, credentials,
or public deployment.
This copy-only package has no installer.

## Prerequisites

- supported Windows with Microsoft Edge WebView2 Runtime
- Docker Desktop only when choosing the Docker compatibility profile
- Node.js/npm only when rebuilding or running browser/development mode

Fresh native installs start and supervise managed PostgreSQL, backend, and
worker children. Existing external database configuration remains supported.
Redis/Celery are not required in the native desktop profile. Docker remains
available as a separate compatibility profile.

## Run the portable application

Double-click `RavenTech OSINT Desktop.exe`. First launch safely initializes the
managed PostgreSQL 16 runtime on loopback port 55432, applies forward
migrations, then starts the backend and worker.
The containing folder is `RavenTech-OSINT-Desktop-5.0.0-rc6`, the window title
is **RavenTech OSINT Desktop — Local Workspace**, and the icon remains a
repository-owned local-candidate asset; public brand approval remains deferred.
The release shell loads its packaged frontend and checks these local endpoints:

- frontend: embedded (development fallback: `http://localhost:5173/`)
- backend: `http://localhost:8000`
- health: `http://localhost:8000/health`
- readiness: `http://localhost:8000/health/ready`
- release: `http://localhost:8000/api/v1/release`

The desktop verifies backend identity, health, readiness, migrations, worker
heartbeat, and RC6 release compatibility before opening the embedded React
workspace. No repository path, `.env`, Python, Docker, Redis, Celery, Node/Vite,
PostgreSQL CLI from `PATH`, PowerShell, or terminal is required for normal
packaged use. Browser/Vite development remains optional at
`http://localhost:5173`.

## Troubleshooting

- **PostgreSQL unavailable:** Local Runtime shows a sanitized reason. A port
  conflict is not taken over, and existing data is preserved.
- **Backend port conflict:** review the application using loopback port 8000.
  RavenTech does not stop or reconfigure unrelated processes.
- **Readiness degraded:** use Local Runtime status and the platform-native
  runtime logs. A component can be retried only when this desktop owns it.
- **Frontend unavailable:** a packaged release uses embedded assets. Port 5173
  and `npm run dev` apply only to browser/development mode.
- **Window does not open:** confirm WebView2 Runtime is installed and that local
  endpoint security policy permits the executable.

Do not copy `.env`, credentials, database backups, generated reports, or client
data into this folder. Validate hashes in `portable-manifest.json` after copying
the folder between local test locations.

## Limitations and security boundary

- Windows x86_64 portable local testing; Linux x86_64 packaging is documented
  separately; no public release or support SLA
- unsigned executable with the repository-owned RavenTech local-candidate icon
- Fresh native installs use managed PostgreSQL. Existing external PostgreSQL
  and Docker remain supported compatibility options; Docker is not required.
- no OS startup persistence/autostart; child processes stop with this desktop
- no arbitrary command input, shell/filesystem plugin, secret collection,
  remote administration, router
  automation, scanning, exploitation, hosting, deployment, DNS, or Supabase
  migration

For the separate unsigned current-user installer workflow, read
`desktop/INSTALLER_BUILD_README.md`. Portable and installer outputs remain
independent, ignored local artifacts; neither is approved for public release.
After both artifacts exist, run `npm run smoke -- --require-artifacts` from
`desktop/` to check their manifests, checksums, names, permissions, and exclusions.
