# RavenTech OSINT Desktop 5.0.0-rc6 — Local Test Package

This private Windows package contains the RC6 portable desktop executable and
the unsigned NSIS installer. It is for local operator testing only. It is not a
signed or public release. It includes the fixed native backend/worker runtime;
PostgreSQL remains external; project data, reports, credentials, and secrets
remain outside the package.

## PostgreSQL prerequisite

Start or configure a host-reachable PostgreSQL instance and create the
platform-native runtime config. Windows configuration is stored at
`%LOCALAPPDATA%\RavenTech OSINT\config\.env`. Docker remains an optional
compatibility profile.

The desktop includes the built React frontend and expects the backend at
`http://localhost:8000`. `http://localhost:5173` and `npm run dev` are optional
for browser/development testing only. The desktop automatically supervises its
fixed backend and worker children. Existing external processes are observed, not
stopped; runtime stop/restart actions require confirmation and apply only to
children owned by this desktop.

## Portable app

Run `RavenTech OSINT Desktop.exe` directly. No installation is performed. Keep
PostgreSQL available; Vite is not required.

## Unsigned installer

Run `RavenTech-OSINT-Desktop-5.0.0-rc6-unsigned-setup.exe`. Windows SmartScreen
may warn because this local candidate is unsigned. Review the filename and
SHA-256 checksum before choosing to continue. The current-user installer adds
the desktop shell and native backend/worker runtime resources; it does not
install PostgreSQL or add operating-system startup persistence.

To uninstall, use **Settings > Apps > Installed apps > RavenTech OSINT Desktop**
or the uninstall shortcut created by NSIS. Project files and Docker data are
separate and are not removed by uninstalling the shell.

## Verify the package

Compare each file with `SHA256SUMS.txt` and review
`local-release-manifest.json`. The manifest records the source commit, build
time, unsigned/local-only status, and explicit runtime boundaries.

## Limitations and release boundary

- PostgreSQL remains an external local prerequisite. Redis/Celery are not
  required in native desktop mode; Docker compatibility remains available.
- There is no code signing, auto-update, public release, operating-system
  autostart, or bundled database.
- There are no hosting, deployment, DNS, or Supabase migration changes.
- There is no router automation, arbitrary or remote command execution, remote
  administration, scanning addition, or offensive functionality.

See `KNOWN_LIMITATIONS.md` and `LOCAL_STARTUP_INSTRUCTIONS.md` in this package.
The source handoff also provides `OPERATOR_MANUAL.md`,
`DESKTOP_PRIVATE_HANDOFF.md`, and
`DESKTOP_OPERATOR_ACCEPTANCE_CHECKLIST.md`. Keep the completed acceptance record
outside this package because the package has a fixed payload allowlist.
