# Deployment Preflight

RavenTech OSINT is a defensive investigation workspace that uses its own backend
authentication system and database user model. Supabase can be used as the
hosted PostgreSQL provider, but Supabase Auth is not part of this deployment
path.

## Readiness Checklist

- Confirm the target environment is `staging` or `production`.
- Generate a strong `SECRET_KEY` and store it only in the backend environment.
- Configure `DATABASE_URL` for PostgreSQL and run Alembic migrations.
- Configure `REDIS_URL` for API rate limits, refresh-token state, and workers.
- Set `FRONTEND_URL` and `BACKEND_CORS_ORIGINS` to the final HTTPS origins.
- Decide whether public registration is disabled, invite-only, or approval-only.
- Confirm report branding, export settings, and governance settings.
- Verify `/health` and `/health/ready` before opening access to users.
- Keep demo mode disabled for production unless explicitly presenting demo data.

## Required Environment Variables

Backend:

```env
SECRET_KEY=<backend-only-secret>
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:5432/<database>?ssl=require
REDIS_URL=redis://:<password>@<host>:6379/0
ACCESS_TOKEN_EXPIRE_MINUTES=30
FRONTEND_URL=https://your-domain.example
BACKEND_CORS_ORIGINS=https://your-domain.example
PUBLIC_REGISTRATION_ENABLED=false
REGISTRATION_REQUIRES_APPROVAL=true
REGISTRATION_INVITE_CODE=
DEFAULT_REGISTERED_USER_ROLE=viewer
REPORT_COMPANY_NAME=RavenTech
REPORT_LOGO_PATH=
REPORT_PRIMARY_COLOR=#7C3AED
REPORT_SECONDARY_COLOR=#111827
APP_VERSION=5.0.0-rc1
RELEASE_CHANNEL=release-candidate
```

Optional backend variables:

```env
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-6
CHROMA_DATA_PATH=/data/chroma
```

Frontend:

```env
VITE_API_BASE_URL=https://api.your-domain.example/api/v1
```

Never expose `DATABASE_URL`, `SECRET_KEY`, Redis credentials, or provider API
keys to the frontend.

## Registration Controls

Public registration is disabled by default.

- `PUBLIC_REGISTRATION_ENABLED=false` keeps `/api/v1/auth/register` closed.
- `REGISTRATION_REQUIRES_APPROVAL=true` creates pending users when registration
  is enabled.
- `REGISTRATION_INVITE_CODE` enables invite-code registration when non-empty.
- `DEFAULT_REGISTERED_USER_ROLE=viewer` is the governance intent. The current
  platform user table supports admin and analyst roles; public registration maps
  to the lowest non-admin platform role and investigation membership controls
  viewer-level access.

Public registration never creates admin users. Continue using
`backend/scripts/create_admin.py` or the existing bootstrap workflow for admin
accounts.

## Supabase PostgreSQL Notes

Use Supabase as hosted PostgreSQL only for this deployment path.

- Do not enable or migrate to Supabase Auth unless a later phase explicitly
  changes the authentication architecture.
- Put the Supabase PostgreSQL connection string in backend `DATABASE_URL` only.
- Use SSL if required by the Supabase connection string, commonly
  `?ssl=require`.
- Run Alembic migrations against the Supabase database before production use.
- Consider connection pooling for production traffic and background workers.
- Use a least-privilege database user when your hosting model supports it.
- Back up the database before migrations and before demo-data imports.

Migration command:

```powershell
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current
docker compose exec backend alembic check
```

## Domain, DNS, and CORS

Example production shape:

```env
FRONTEND_URL=https://your-domain.example
API_BASE_URL=https://api.your-domain.example
BACKEND_CORS_ORIGINS=https://your-domain.example
VITE_API_BASE_URL=https://api.your-domain.example/api/v1
```

Checklist:

- Point the frontend domain at the static frontend host.
- Point the API domain at the backend host or reverse proxy.
- Use HTTPS for both frontend and API.
- Set CORS to the exact frontend origin, not `*`.
- If Cloudflare is used, confirm proxy mode, SSL mode, and DNS records.
- If cookies are introduced later, review secure, same-site, and domain
  settings. Current JWT behavior is header-based.

## Hosting Requirements

Backend:

- Python application runtime.
- PostgreSQL database reachable from backend and worker containers.
- Redis reachable from backend and workers.
- Persistent storage for generated reports if the deployment separates runtime
  containers from storage.
- Environment variables injected securely.

Frontend:

- Static host or Node/Vite-compatible preview host.
- `VITE_API_BASE_URL` set at build time for the deployed API.

Workers:

- Same backend image and environment as the API.
- Access to PostgreSQL, Redis, and report storage.
- Restart policy and logs enabled.

Reports:

- Keep generated report paths on persistent storage.
- Do not store report exports in ephemeral container layers for production.
- Confirm PDF and DOCX dependencies are available in the runtime image.

## Secrets Checklist

- `SECRET_KEY` is unique and at least 32 characters.
- Database and Redis credentials are not committed.
- Anthropic or other provider keys are backend-only.
- Invite codes are backend-only and are not printed in logs or UI.
- `.env` files are excluded from source control.

## Health Checks

Use these after startup:

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
curl http://localhost:8000/api/v1/release
```

Expected readiness checks include database, Redis, migrations, workers,
knowledge storage, AI provider configuration, and report export availability.

## Rollback Checklist

- Stop inbound traffic or place the app in maintenance mode.
- Restore the most recent PostgreSQL backup if a migration or import caused
  data issues.
- Revert the backend and frontend images to the previous release candidate.
- Re-run `alembic current` and `/health/ready`.
- Verify login, dashboard, investigations, reports, audit, and governance.
- Document the rollback reason in the audit or release notes.

## Common Preflight Failures

- Backend degraded: run `docker compose logs backend --tail=100`.
- Migration drift: run `docker compose exec backend alembic check`.
- Frontend cannot reach API: verify `VITE_API_BASE_URL` and CORS origins.
- Registration unavailable: verify `PUBLIC_REGISTRATION_ENABLED`.
- New accounts cannot log in: verify `REGISTRATION_REQUIRES_APPROVAL`.
- AI unavailable: verify `ANTHROPIC_API_KEY`; deterministic fallback should
  still work without it.
