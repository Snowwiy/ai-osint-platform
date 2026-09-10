# Local Health Repair Guide

This guide applies only to the validated local Docker Compose environment. It
does not contain hosting, DNS, or Supabase migration steps.

## First Check

```powershell
./scripts/local/check_platform.ps1
./scripts/local/check_local_health.ps1
docker compose logs backend --tail=100
docker compose logs celery-worker --tail=100
```

In PowerShell, `curl` may resolve to `Invoke-WebRequest`. Use either explicit
PowerShell JSON handling or the executable form:

```powershell
Invoke-RestMethod http://localhost:8000/health
curl.exe -fsS http://localhost:8000/health/ready
```

## Backend Degraded Because Migrations Are Behind

```powershell
docker compose exec -T backend alembic current
docker compose exec -T backend alembic heads
docker compose exec -T backend alembic upgrade head
Invoke-RestMethod http://localhost:8000/health/ready
```

Do not stamp a revision or edit the database manually to bypass a failed
migration.

## Alembic Drift Check Fails

```powershell
docker compose exec -T backend alembic check
git status
git diff -- backend/app/models backend/alembic
```

Drift means models and migrations disagree. Do not autogenerate or apply a new
migration during routine repair. Restore the expected code state or handle the
schema change in a separately reviewed development phase.

## Redis Is Unavailable

```powershell
docker compose ps redis
docker compose logs redis --tail=100
docker compose restart redis
docker compose ps redis
```

Never print `REDIS_PASSWORD`. If authentication fails, compare the variable
names in `.env` and `.env.example` without pasting their values into logs.

## Worker Is Unavailable

```powershell
docker compose ps celery-worker
docker compose logs celery-worker --tail=100
docker compose restart celery-worker
docker compose logs celery-worker --tail=50
```

Confirm Redis and PostgreSQL are healthy before restarting the worker.

## Report Storage Is Unavailable

```powershell
docker compose exec -T backend sh -c "test -d /data/reports && test -w /data/reports"
docker compose exec -T backend df -h /data/reports
docker compose logs backend --tail=100
```

Do not remove or recreate the `reports_data` volume as a repair shortcut. Back
it up with `./scripts/local/backup_db.ps1 -IncludeReports` before any explicit
volume maintenance.

## Frontend API URL Mismatch

For local development, the frontend API base should resolve to:

```text
http://localhost:8000/api/v1
```

Review `frontend/.env` or the shell environment for `VITE_API_BASE_URL`, then
restart Vite because environment variables are read at startup:

```powershell
cd frontend
npm run dev
```

Use the same `localhost` hostname for frontend and backend during local QA to
avoid an origin mismatch.

## Docker Containers Are Unhealthy

```powershell
docker compose ps
docker compose logs postgres --tail=100
docker compose logs redis --tail=100
docker compose logs backend --tail=100
docker compose up -d postgres redis backend celery-worker
./scripts/local/check_local_health.ps1
```

If PostgreSQL will not start, stop and create or locate a verified backup before
considering any volume operation. Never run `docker compose down -v` as a health
repair command because it deletes local data volumes.

## Clean Local Startup

```powershell
./scripts/local/start_platform.ps1
cd frontend
npm run dev
```

Or start the frontend in the background with:

```powershell
./scripts/local/start_platform.ps1 -OpenFrontend
```

To stop or restart without touching data volumes:

```powershell
./scripts/local/stop_platform.ps1
./scripts/local/restart_platform.ps1 -OpenFrontend
```

The Operations → Local Operator Console mirrors these checks and provides
copy-ready commands. It is informational only and does not execute host actions.

No production secrets are required. Local `.env` values are still credentials
and must not be committed or copied into support output.
