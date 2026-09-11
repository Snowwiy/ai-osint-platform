# RavenTech OSINT Desktop 5.0.0-rc6 — Local Test Package

This private Windows package contains the RC6 portable desktop executable and
the unsigned NSIS installer. It is for local operator testing only. It is not a
signed or public release, and it does not contain the RavenTech backend,
PostgreSQL, Redis, Docker, project data, reports, credentials, or secrets.

## Start the local platform first

Install and start Docker Desktop, clone or open the RavenTech OSINT repository,
and run these commands from the repository root in PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\local\start_platform.ps1
cd frontend
npm run dev
```

The desktop expects the frontend at `http://localhost:5173` and the backend at
`http://localhost:8000`. Use the first-run screen to bind the repository root.
Start, stop, and restart actions require confirmation and can invoke only the
five fixed local launcher scripts. If the repository cannot be validated, the
desktop keeps copy-only guidance.

## Portable app

Run `RavenTech OSINT Desktop.exe` directly. No installation is performed. Keep
the local Docker services and Vite frontend running while testing.

## Unsigned installer

Run `RavenTech-OSINT-Desktop-5.0.0-rc6-unsigned-setup.exe`. Windows SmartScreen
may warn because this local candidate is unsigned. Review the filename and
SHA-256 checksum before choosing to continue. The current-user installer adds
only the desktop shell; it does not start services automatically.

To uninstall, use **Settings > Apps > Installed apps > RavenTech OSINT Desktop**
or the uninstall shortcut created by NSIS. Project files and Docker data are
separate and are not removed by uninstalling the shell.

## Verify the package

Compare each file with `SHA256SUMS.txt` and review
`local-release-manifest.json`. The manifest records the source commit, build
time, unsigned/local-only status, and explicit runtime boundaries.

## Limitations and release boundary

- Docker Desktop, PostgreSQL, Redis, the backend, and the Vite frontend remain
  separately managed local prerequisites.
- There is no code signing, auto-update, public release, service autostart, or
  bundled database/backend runtime.
- There are no hosting, deployment, DNS, or Supabase migration changes.
- There is no router automation, arbitrary or remote command execution, remote
  administration, scanning addition, or offensive functionality.

See `KNOWN_LIMITATIONS.md` and `LOCAL_STARTUP_INSTRUCTIONS.md` in this package.
