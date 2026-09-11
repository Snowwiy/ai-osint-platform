# Local startup instructions

RavenTech OSINT Desktop 5.0.0-rc6 wraps the existing local web platform. It
bundles the built React frontend but does not bundle or automatically start
Docker, PostgreSQL, Redis, or the backend.

From the RavenTech OSINT repository root in PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\local\start_platform.ps1
```

Expected endpoints:

- Frontend: embedded in portable/installed builds
- Optional browser/development frontend: `http://localhost:5173/`
- Backend: `http://localhost:8000`
- Health: `http://localhost:8000/health`
- Readiness: `http://localhost:8000/health/ready`
- Release: `http://localhost:8000/api/v1/release`

The first-run screen accepts manual project-path input only. A valid path must
contain the expected Compose file, frontend, backend application, and all five
approved `scripts/local/*.ps1` launchers. Commands entered by the operator are
never executed. Start, stop, and restart require explicit confirmation.

Run `npm run dev` from `frontend/` only for browser/development testing. It is
not a runtime prerequisite for a portable or installed build.
