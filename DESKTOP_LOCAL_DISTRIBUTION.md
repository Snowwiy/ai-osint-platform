# RavenTech OSINT Desktop — Local Distribution

The current local Windows test bundle is RavenTech OSINT Desktop `5.0.0-rc6`.

On authenticated startup the embedded client loads a read-only monitoring
summary from the local backend and refreshes it on the configured safe interval.
This is dashboard polling, not service autostart or network discovery. LAN
discovery-on-start and service-check-on-start are disabled by default and remain
subject to the existing private-CIDR, target, port, timeout, policy, maintenance,
cooldown, and deduplication controls.
It is an unpublished, unsigned QA workflow—not a public release.

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

The corrected RC6 artifact build embeds the existing React production assets.
Portable and installed runs do not require Vite or port 5173; that URL is only
for browser/development testing. Backend/Docker services remain required.

## Local artifacts

- Portable folder: `desktop/dist-portable/RavenTech-OSINT-Desktop-5.0.0-rc6/`
- Installer folder: `desktop/dist-installer/RavenTech-OSINT-Desktop-5.0.0-rc6/`
- Aggregate folder: `desktop/dist-local-release/RavenTech-OSINT-Desktop-5.0.0-rc6/`
- Portable checksums: `portable-manifest.json` inside the portable folder
- Installer checksums: `installer-manifest.json` inside the installer folder

All three folders are Git-ignored. Never commit or publish their binaries from
this phase. The local candidate uses the repository-owned RavenTech icon;
code-signing and public brand/release approval remain deferred.

## Prerequisites

- Windows 10 or 11 with Microsoft Edge WebView2 Runtime already installed
- Docker Desktop with Docker Compose
- RavenTech OSINT repository and local configuration kept outside artifacts
- Node.js/npm only for rebuilding or browser/development mode
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
An installed build outside that tree uses the manually entered, canonicalized
project root only after every fixed marker and pinned script-content check
passes. An unvalidated path cannot select or execute a script; the UI explains
that launchers are unavailable and leaves the copy button active.

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
```

The installed/portable frontend is embedded. Optional Vite browser/development
mode uses `http://localhost:5173`; the required backend is
`http://localhost:8000`. Health, readiness, and release checks
use `/health`, `/health/ready`, and `/api/v1/release`.

## Install or run

For portable testing, launch `RavenTech OSINT Desktop.exe` from the portable
folder. For installer testing, verify the installer-manifest checksum, then run
`RavenTech-OSINT-Desktop-5.0.0-rc6-unsigned-setup.exe` and launch the Start-menu
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
4. Start Docker/backend services through the approved workflow; confirm health
   and readiness become ready. In a release build confirm **Frontend: Embedded**.
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

The complete local operating guide is `OPERATOR_MANUAL.md`. It preserves the
browser/Docker recovery path and keeps backup/restore outside the desktop
launcher's five-script boundary.
