# RavenTech OSINT Desktop 5.0.0-rc6 — Windows Portable Build

This folder is a private local-test portable build. It contains the Tauri shell
and fixed PyInstaller backend/worker runtime folders; it does not contain an
installer, signing, updater, database, credentials, or public deployment.
This copy-only package has no installer.

## Prerequisites

- supported Windows with Microsoft Edge WebView2 Runtime
- a host-reachable PostgreSQL instance and a local RavenTech configuration
  file under the platform-native application config directory
- Docker Desktop only when choosing the Docker compatibility profile
- Node.js/npm only when rebuilding or running browser/development mode

The desktop starts and supervises only its fixed native backend and worker
children. PostgreSQL remains external; configure its host-reachable URL in the
native runtime config. Redis/Celery are not required in the native desktop
profile. Docker remains available as a separate compatibility profile.

## Run the portable application

Double-click `RavenTech OSINT Desktop.exe` after PostgreSQL is available.
The containing folder is `RavenTech-OSINT-Desktop-5.0.0-rc6`, the window title
is **RavenTech OSINT Desktop — Local Workspace**, and the icon remains a
repository-owned local-candidate asset; public brand approval remains deferred.
The release shell loads its packaged frontend and checks these local endpoints:

- frontend: embedded (development fallback: `http://localhost:5173/`)
- backend: `http://localhost:8000`
- health: `http://localhost:8000/health`
- readiness: `http://localhost:8000/health/ready`
- release: `http://localhost:8000/api/v1/release`

The desktop verifies the backend identity, readiness, and RC6 release before
starting the worker and opening the embedded React workspace. Browser mode remains optionally available at
`http://localhost:5173` when Vite is started separately.

On first launch, manually enter the repository root in the setup card. The path
is stored only after fixed marker and build-pinned five-script validation. Resolution then
prefers that saved path, followed by matching current-directory ancestry and
development executable ancestry. Missing or invalid paths retain copy-only mode;
there is no broad folder browser or arbitrary command input.

## Troubleshooting

- **PostgreSQL unavailable:** start or configure the external PostgreSQL
  service; automatic PostgreSQL setup is deferred to Phase 5BM.
- **Backend port conflict:** review the application using loopback port 8000.
  RavenTech does not stop or reconfigure unrelated processes.
- **Readiness degraded:** use Local Runtime status and the platform-native
  runtime logs. A component can be retried only when this desktop owns it.
- **Frontend unavailable in development:** run `npm run dev` from `frontend/`.
  In a portable release, **Frontend: Embedded** is expected and port 5173 is
  not required.
- **Window does not open:** confirm WebView2 Runtime is installed and that local
  endpoint security policy permits the executable.

Do not copy `.env`, credentials, database backups, generated reports, or client
data into this folder. Validate hashes in `portable-manifest.json` after copying
the folder between local test locations.

## Limitations and security boundary

- Windows x86_64 portable local testing; Linux x86_64 packaging is documented
  separately; no public release or support SLA
- unsigned executable with the repository-owned RavenTech local-candidate icon
- PostgreSQL remains external; Docker is an alternative compatibility runtime
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
