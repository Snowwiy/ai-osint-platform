# Local startup instructions

RavenTech OSINT Desktop 5.0.0-rc5 wraps the existing local web platform. It does
not bundle or automatically start Docker, PostgreSQL, Redis, the backend, or the
Vite frontend.

From the RavenTech OSINT repository root in PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\local\start_platform.ps1
cd frontend
npm run dev
```

Expected endpoints:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- Health: `http://localhost:8000/health`
- Readiness: `http://localhost:8000/health/ready`
- Release: `http://localhost:8000/api/v1/release`

The first-run screen accepts manual project-path input only. A valid path must
contain the expected Compose file, frontend, backend application, and all five
approved `scripts/local/*.ps1` launchers. Commands entered by the operator are
never executed. Start, stop, and restart require explicit confirmation.
