# Troubleshooting

> Legacy implementation reference. Use `TROUBLESHOOTING.md` and
> `LOCAL_HEALTH_REPAIR.md` at the repository root for the current RC2 local
> runbooks. This file is retained as historical context.

## Backend Will Not Start

Check configuration:

```bash
docker compose logs backend
docker compose exec backend python -c "from app.core.config import settings; print(settings.startup_errors())"
```

Common causes:

- placeholder production `SECRET_KEY`
- missing `FRONTEND_URL`
- missing or wildcard production `CORS_ORIGINS`
- PostgreSQL or Redis not healthy

## Migration Problems

```bash
docker compose exec backend alembic current
docker compose exec backend alembic heads
docker compose exec backend alembic check
docker compose exec backend alembic upgrade head
```

If `/health/ready` reports migration drift, run `alembic upgrade head`.

## Audit Page Errors

Check:

- current migration head
- `audit_logs` columns: `actor_id`, `metadata`, `created_at`
- backend logs for the request ID shown in the UI

Audit rows with malformed metadata are normalized to `{}` in API responses.

## Report Issues

Validate:

```bash
docker compose exec backend python -m pytest tests/integration/api/test_reports.py -q
```

If exports fail, check report content, `/data/reports` permissions, and optional
`REPORT_LOGO_PATH`.

## Worker Failures

```bash
docker compose logs -f celery-worker
docker compose restart celery-worker
```

Workers require Redis and PostgreSQL. Tasks use retry backoff and late
acknowledgements, so interrupted work can retry safely.

## Frontend Shows Backend Errors

The UI surfaces endpoint, status code, backend detail, and request ID when
available. Use the request ID to find the matching backend log entry.
