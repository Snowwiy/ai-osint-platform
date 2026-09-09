# RavenTech OSINT Deployment Guide

RavenTech OSINT is a defensive intelligence and investigation workspace. This
guide covers local and production-style Docker Compose operation without cloud
vendor lock-in.

## Prerequisites

- Docker Desktop or Docker Engine with Docker Compose
- Git
- Node.js only when running the frontend development server outside Docker
- A populated `.env` based on `.env.example`

## Environment

Required backend variables:

- `APP_SECRET_KEY` or `SECRET_KEY`
- `DATABASE_URL`
- `REDIS_URL`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `FRONTEND_URL`
- `CORS_ORIGINS`, `BACKEND_CORS_ORIGINS`, or `APP_ALLOWED_ORIGINS`

Optional operational variables:

- `APP_NAME`
- `APP_VERSION`
- `APP_RELEASE_CHANNEL`
- `APP_BUILD_DATE`
- `APP_GIT_COMMIT`
- `ANTHROPIC_API_KEY`
- `REPORT_COMPANY_NAME`
- `REPORT_LOGO_PATH`
- `REPORT_PRIMARY_COLOR`
- `REPORT_SECONDARY_COLOR`
- `CHROMA_DATA_PATH`
- `PUBLIC_REGISTRATION_ENABLED`
- `REGISTRATION_REQUIRES_APPROVAL`
- `REGISTRATION_INVITE_CODE`
- `DEFAULT_REGISTERED_USER_ROLE`

Frontend variable:

- `VITE_API_BASE_URL`

Do not commit real secrets. Use strong values for production-style operation.
For a deployment preflight checklist, Supabase PostgreSQL notes, domain/CORS
guidance, and registration policy details, see
[DEPLOYMENT_PREFLIGHT.md](DEPLOYMENT_PREFLIGHT.md).

## Local Startup

```powershell
docker compose up -d
docker compose logs backend -f
docker compose exec backend alembic upgrade head
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/release
```

Run the frontend development server from the frontend directory:

```powershell
cd frontend
npm install
npm run dev
```

## Production-Style Compose

Use `docker-compose.prod.yml` as the production-style baseline:

```powershell
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
curl http://localhost:8000/health/ready
```

The production compose file keeps PostgreSQL, Redis, Chroma data, and generated
reports on persistent volumes. Review restart policies and environment values
before exposing the platform to an internal network.

## Migration Workflow

1. Back up data before applying migrations.
2. Start PostgreSQL and Redis.
3. Run `alembic upgrade head` from the backend container.
4. Confirm `/health/ready` reports migrations as current.
5. Open the Operations Center and confirm migration current/head match.

## Frontend Build

```powershell
cd frontend
npm install
npm run build
```

Set `VITE_API_BASE_URL` to the backend API base URL before building.

## Health Validation

Use:

- `GET /health`
- `GET /health/live`
- `GET /health/ready`
- `GET /api/v1/operations/status`

The Operations Center shows backend, database, Redis, migrations, AI provider,
local knowledge storage, storage, version, build, and environment status without
displaying secrets.

`GET /api/v1/release` exposes the safe release-candidate metadata used by the
Operations Center: app name, version, release channel, build date, git commit if
available, migration version, and environment.

## Validation Commands

Run these manually before a release:

```powershell
docker compose run --rm backend python -m ruff check app workers tests
docker compose run --rm backend python -m mypy app workers
docker compose run --rm backend python -m pytest tests/ -q
docker compose run --rm backend python -m pip check
docker compose exec backend alembic check
cd frontend
npm run lint
npm run build
```

For GitHub Actions parity, the release candidate CI also runs `pip check`,
Alembic drift detection, frontend lint, and frontend build. Keep tests
deterministic: do not require live AI providers, live internet access, or
external threat feeds.

## Migration Troubleshooting

Check heads:

```powershell
docker compose exec backend alembic heads
```

Check current revision:

```powershell
docker compose exec backend alembic current
```

If `alembic check` reports drift, inspect the model change and generate an
additive migration. Do not patch production databases manually unless you have
a backup and a rollback plan.

## Operational Notes

- Keep report exports on persistent storage.
- Keep database and Redis ports internal unless explicitly required.
- Use the Operations Center diagnostics export for support triage.
- Use backup exports before upgrades or migration work.
- Review audit logs after administrative actions.
- Seed demo data only in non-production environments:
  `docker compose exec backend python scripts/seed_demo_data.py`.
- Clear demo data when a presentation is finished:
  `docker compose exec backend python scripts/seed_demo_data.py --clear`.
