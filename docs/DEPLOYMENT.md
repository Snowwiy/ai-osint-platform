# Deployment

RavenTech OSINT Platform is deployed as a modular monolith with FastAPI,
PostgreSQL, Redis, Celery, and the Vite frontend.

## Environments

Supported profiles:

- `development`: verbose logs, local docs enabled, relaxed operational defaults.
- `staging`: production-like checks with warning-level logging.
- `production`: strict startup validation, secure cookies, hardened headers, and
  docs disabled.

## Required Production Variables

Set these before starting production services:

- `APP_SECRET_KEY` or `SECRET_KEY`
- `DATABASE_URL`
- `REDIS_URL`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `FRONTEND_URL`
- `CORS_ORIGINS` or `APP_ALLOWED_ORIGINS`
- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`

Optional:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `REPORT_LOGO_PATH`
- `REPORT_COMPANY_NAME`

## Local Production Compose

```bash
cp .env.example .env
docker compose -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
docker compose -f docker-compose.prod.yml exec backend python scripts/create_admin.py
```

Check readiness:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

## Startup Order

1. PostgreSQL becomes healthy.
2. Redis becomes healthy.
3. Backend starts, validates configuration, connects to Redis, and exposes
   `/health/live`.
4. Celery worker starts with prefork, late acknowledgements, retry backoff, and
   worker restart safeguards.
5. Run migrations before accepting traffic.

## Common Deployment Checks

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f celery-worker
docker compose -f docker-compose.prod.yml exec backend alembic check
```
