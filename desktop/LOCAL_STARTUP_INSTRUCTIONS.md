# Local startup instructions

RavenTech OSINT Desktop 5.0.0-rc6 bundles the React frontend and fixed native
backend/worker artifacts. It automatically starts and supervises only the
children it owns. PostgreSQL remains external; Redis and Celery are not required
in native desktop mode.

Expected endpoints:

- Frontend: embedded in portable/installed builds
- Optional browser/development frontend: `http://localhost:5173/`
- Backend: `http://localhost:8000`
- Health: `http://localhost:8000/health`
- Readiness: `http://localhost:8000/health/ready`
- Release: `http://localhost:8000/api/v1/release`

Windows configuration is `%LOCALAPPDATA%\RavenTech OSINT\config\.env`;
Linux configuration is `$XDG_CONFIG_HOME/raventech-osint/.env` or its standard
home-directory fallback. Set `DATABASE_URL` to a PostgreSQL endpoint reachable
from the host OS. The Docker-only hostname `postgres` is not a host endpoint.
PostgreSQL bootstrap is deferred to Phase 5BM.

The Local Runtime panel distinguishes processes owned by this desktop from
external processes. Stop/restart requires confirmation and is unavailable for
external services. An unrelated service on port 8000 is never killed.

Run `npm run dev` from `frontend/` only for browser/development testing. It is
not a runtime prerequisite for a portable or installed build.
