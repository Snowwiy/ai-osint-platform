# PHASE 0 IMPLEMENTATION PLAN — PART 1F
# Tasks 18–21: Celery Foundation · Dockerfile · Docker Compose · CI/CD · Phase 0 Close

---

## TASK 18 — Celery Foundation

### Files Created
- `app/workers/celery_app.py`
- `app/workers/tasks.py` (placeholder — tasks added in Phase 1)

### app/workers/celery_app.py

**Critical:** `worker_pool` MUST be `"prefork"`. Never `"gevent"` or `"eventlet"` — both break `asyncio.run()` inside tasks.

```python
# app/workers/celery_app.py
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "osint_platform",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_pool="prefork",          # NEVER gevent or eventlet
    worker_concurrency=2,           # Matches docker-compose --concurrency=2
    task_acks_late=True,            # Re-queue on worker crash
    worker_prefetch_multiplier=1,   # One task per worker at a time
    task_track_started=True,
)
```

### app/workers/tasks.py

```python
# app/workers/tasks.py
# Phase 1 will add OSINT scan tasks here.
# Pattern for all tasks:
#
#   @celery_app.task(bind=True, max_retries=3)
#   def run_scan(self, scan_id: str) -> dict:
#       return asyncio.run(_run_scan_async(scan_id))
#
# asyncio.run() is required because prefork workers have no running event loop.
```

**DoD:** `celery -A app.workers.celery_app worker --loglevel=info` starts without import errors; `celery_app.conf.worker_pool == "prefork"`.

---

## TASK 19 — Dockerfile

### File Created
- `Dockerfile`

```dockerfile
# Dockerfile
FROM python:3.12-slim AS base

WORKDIR /app

# System dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download sentence-transformers model into the image layer.
# SENTENCE_TRANSFORMERS_HOME sets the cache path to a fixed location.
# This avoids per-container downloads at runtime (model is ~90 MB).
ENV SENTENCE_TRANSFORMERS_HOME=/app/models
RUN python -c \
    "from sentence_transformers import SentenceTransformer; \
     SentenceTransformer('all-MiniLM-L6-v2')"

# Copy application source
COPY . .

# Non-root user
RUN useradd --system --no-create-home --uid 1001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Secrets are NEVER baked into the image.
# Pass all secrets via --env-file at runtime (see docker-compose.yml).
CMD ["uvicorn", "app.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]
```

**DoD:** `docker build -t osint-platform .` succeeds; `docker run --rm osint-platform python -c "from app.core.config import settings"` imports without error (secrets will be missing but import should not crash — Settings fields are validated on first access, not import).

---

## TASK 20 — Docker Compose (complete file)

### File Created
- `docker-compose.yml`

```yaml
# docker-compose.yml
services:

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: osint
      POSTGRES_PASSWORD: osint_dev
      POSTGRES_DB: osint_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U osint -d osint_db"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  backend:
    build: .
    command: uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload
    env_file: .env
    volumes:
      - .:/app                          # Hot reload in dev
      - reports_data:/data/reports
      - chroma_data:/data/chroma
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  celery-worker:
    build: .
    command: >
      celery -A app.workers.celery_app worker
      --loglevel=info
      --pool=prefork
      --concurrency=2
    env_file: .env
    volumes:
      - .:/app
      - reports_data:/data/reports
      - chroma_data:/data/chroma
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

volumes:
  postgres_data:
  redis_data:
  reports_data:
  chroma_data:
```

### .env.example (commit this; .env is gitignored)

```dotenv
# .env.example — copy to .env and fill in real values
APP_SECRET_KEY=change-me-to-a-long-random-string-at-least-32-chars
APP_ENVIRONMENT=development
DATABASE_URL=postgresql+asyncpg://osint:osint_dev@postgres:5432/osint_db
TEST_DATABASE_URL=postgresql+asyncpg://osint:osint_dev@localhost:5432/osint_test
REDIS_URL=redis://redis:6379/0
CHROMA_DATA_PATH=/data/chroma
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# OSINT adapter keys — leave blank to disable that adapter
SHODAN_API_KEY=
VIRUSTOTAL_API_KEY=
ABUSEIPDB_API_KEY=
URLSCAN_API_KEY=
HUNTER_API_KEY=
```

**.gitignore must include:**
```
.env
*.pyc
__pycache__/
.mypy_cache/
.ruff_cache/
```

---

## TASK 21 — CI Pipeline

### File Created
- `.github/workflows/test.yml`

```yaml
# .github/workflows/test.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: osint
          POSTGRES_PASSWORD: osint_dev
          POSTGRES_DB: osint_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U osint -d osint_test"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 10

    env:
      APP_SECRET_KEY: ci-test-secret-key-not-for-production
      APP_ENVIRONMENT: development
      DATABASE_URL: postgresql+asyncpg://osint:osint_dev@localhost:5432/osint_test
      TEST_DATABASE_URL: postgresql+asyncpg://osint:osint_dev@localhost:5432/osint_test
      REDIS_URL: redis://localhost:6379/0
      CHROMA_DATA_PATH: /tmp/chroma_ci

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Lint (ruff)
        run: ruff check app/ tests/

      - name: Type check (mypy)
        run: mypy app/

      - name: Run migrations
        run: alembic upgrade head

      - name: Run tests
        run: pytest -v --tb=short
```

---

## TASK 22 — Pre-commit + Makefile

### .pre-commit-config.yaml

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies:
          - sqlalchemy[mypy]>=2.0.35
          - pydantic>=2.8.2
        args: [--ignore-missing-imports]
```

**Install:** `pre-commit install` (run once after cloning).

### Makefile (complete)

```makefile
# Makefile
.PHONY: dev dev-bg down test test-unit test-int migrate migration \
        lint format shell create-admin check build logs

dev:
	docker compose up --build

dev-bg:
	docker compose up --build -d

down:
	docker compose down -v

build:
	docker compose build

logs:
	docker compose logs -f backend celery-worker

test:
	docker compose run --rm \
	  -e TEST_DATABASE_URL=postgresql+asyncpg://osint:osint_dev@postgres:5432/osint_db \
	  backend pytest -v --tb=short

test-unit:
	docker compose run --rm backend pytest tests/ -v -m "not integration" --tb=short

test-int:
	docker compose run --rm backend pytest tests/ -v -m "integration" --tb=short

migrate:
	docker compose run --rm backend alembic upgrade head

migration:
	@test -n "$(name)" || (echo "Usage: make migration name=description" && exit 1)
	docker compose run --rm backend alembic revision --autogenerate -m "$(name)"

lint:
	docker compose run --rm backend ruff check app/ tests/
	docker compose run --rm backend mypy app/ --ignore-missing-imports

format:
	docker compose run --rm backend ruff format app/ tests/

shell:
	docker compose run --rm backend python

create-admin:
	@test -n "$(email)" || (echo "Usage: make create-admin email=... password=..." && exit 1)
	@test -n "$(password)" || (echo "Usage: make create-admin email=... password=..." && exit 1)
	docker compose run --rm \
	  -e ADMIN_EMAIL=$(email) \
	  -e ADMIN_PASSWORD=$(password) \
	  backend python scripts/create_admin.py

check: lint test
	@echo "All checks passed."
```

---

## DOCKER VERIFICATION CHECKLIST

Run these commands in order. Each must succeed before the next.

```bash
# 1. Build image — must complete with no errors
docker compose build

# 2. Start services — postgres and redis must show healthy
docker compose up -d postgres redis
docker compose ps   # Expected: postgres (healthy), redis (healthy)

# 3. Run migrations
make migrate
# Expected: "INFO [alembic.runtime.migration] Running upgrade -> xxxx, ..."
# Expected last line: "INFO [alembic.runtime.migration] Running upgrade ..."

# 4. Start full stack
make dev-bg
docker compose ps
# Expected: all 4 services running (backend, celery-worker, postgres, redis)

# 5. Health check
curl http://localhost:8000/api/v1/admin/health
# Expected: {"status":"healthy","database":"ok","redis":"ok","timestamp":"..."}

# 6. Confirm /docs is reachable in dev (disabled in prod)
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs
# Expected: 200

# 7. Confirm Celery worker is alive
docker compose exec celery-worker celery -A app.workers.celery_app inspect ping
# Expected: {"celery@...": {"ok": "pong"}}

# 8. Tear down cleanly
make down
```

---

## MANUAL SMOKE TESTING FLOW

Start stack: `make dev-bg && make migrate`

**Step 1 — Create admin**
```bash
make create-admin email=admin@test.local password=Admin12345!
# Expected: "Admin created: admin@test.local  id=<uuid>"
```

**Step 2 — Login**
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.local","password":"Admin12345!"}' \
  | python -m json.tool | grep access_token | cut -d'"' -f4)
echo "Token: $TOKEN"
```

**Step 3 — Verify /me**
```bash
curl -s http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
# Expected: {"id":"...","email":"admin@test.local","role":"admin","is_active":true}
```

**Step 4 — Create investigation**
```bash
INV=$(curl -s -X POST http://localhost:8000/api/v1/investigations/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Smoke Test Investigation",
    "description": "Phase 0 smoke test",
    "authorization_statement": "This investigation is conducted under explicit written authorization from the asset owner. Scope: internal network only. Duration: 2026-05-27 to 2026-06-27."
  }' | python -m json.tool)
echo "$INV"
# Expected: {"id":"...","title":"Smoke Test Investigation","status":"draft",...}
INV_ID=$(echo "$INV" | python -c "import sys,json; print(json.load(sys.stdin)['id'])")
```

**Step 5 — List members (creator must be owner)**
```bash
curl -s "http://localhost:8000/api/v1/investigations/$INV_ID/members" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
# Expected: [{"investigation_id":"...","user_id":"...","role":"owner"}]
```

**Step 6 — Try short authorization_statement (must fail)**
```bash
curl -s -X POST http://localhost:8000/api/v1/investigations/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Bad","description":"x","authorization_statement":"too short"}' \
  | python -m json.tool
# Expected: 422 Unprocessable Entity
```

**Step 7 — Logout**
```bash
REFRESH=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.local","password":"Admin12345!"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])")

curl -s -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH\"}"
# Expected: 204 No Content

curl -s -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH\"}" | python -m json.tool
# Expected: 401 {"detail":"Token revoked or expired"}
```

---

## PHASE 0 DEFINITION OF DONE

Every item below must be ✅ before Phase 1 begins.

### Infrastructure
- [ ] `docker compose up --build` starts all 4 services without errors
- [ ] `make migrate` applies all Alembic migrations with no errors
- [ ] `GET /api/v1/admin/health` → `{"status":"healthy","database":"ok","redis":"ok"}`
- [ ] Celery worker starts and responds to `inspect ping`
- [ ] `.env` is gitignored; `.env.example` is committed

### Authentication
- [ ] `POST /auth/login` → 200 with access + refresh tokens
- [ ] `POST /auth/refresh` rotates tokens; used refresh token → 401
- [ ] `POST /auth/logout` revokes refresh token; subsequent refresh → 401
- [ ] `GET /auth/me` returns current user without `hashed_password`
- [ ] `POST /auth/me/password` with wrong current password → 400
- [ ] Expired access token → 401 on protected endpoints

### Investigations
- [ ] `POST /investigations/` with `authorization_statement` < 100 chars → 422
- [ ] Creator auto-assigned as `owner` member on creation
- [ ] `GET /investigations/` — analyst sees only their own; admin sees all
- [ ] Non-member `GET /investigations/{id}` → 404 (not 403)
- [ ] `DELETE /members/{user_id}` when only one owner → 409
- [ ] Member `role` must be `"owner"` or `"collaborator"` (not `"analyst"`) → 422

### Tests & Quality
- [ ] `make test` exits 0 with no failures
- [ ] `make lint` exits 0 with no errors
- [ ] `mypy app/` exits 0 with no type errors
- [ ] CI pipeline passes on push to `main`
- [ ] No stack traces appear in any HTTP response body
- [ ] `/docs` accessible in dev; disabled in production (`is_production=True`)

---

## PHASE 0 COMPLETION CHECKLIST

Final file inventory — every file must exist:

```
app/
  core/config.py          settings + is_production
  core/security.py        JWT + bcrypt helpers
  core/dependencies.py    get_db, get_current_user, require_role, get_redis
  core/middleware.py      AuditLogMiddleware
  core/rate_limit.py      slowapi Limiter singleton
  db/session.py           create_async_engine + AsyncSessionLocal
  models/__init__.py      imports all 9 models
  models/user.py
  models/investigation.py
  models/investigation_member.py
  models/target.py
  models/scan_job.py
  models/finding.py
  models/report.py
  models/audit_log.py
  schemas/auth.py
  schemas/user.py
  schemas/common.py       PasswordChangeRequest
  schemas/investigation.py
  schemas/target.py
  services/auth.py
  services/audit.py
  services/investigation.py
  workers/celery_app.py
  workers/tasks.py        placeholder
  api/v1/admin.py         health check
  api/v1/auth.py
  api/v1/investigations.py
  main.py                 create_app factory
alembic/
  env.py                  sync engine pattern
  versions/               at least one migration file
tests/
  conftest.py
  test_security.py        14 unit tests
  test_dependencies.py    5 unit tests
  test_auth.py            7 integration tests
  test_investigations.py  10 integration tests
  test_health.py          3 smoke tests
scripts/
  create_admin.py
Dockerfile
docker-compose.yml
.env.example
.gitignore
.pre-commit-config.yaml
.github/workflows/test.yml
Makefile
requirements.txt
pytest.ini
```

---

## COMMON PHASE 0 DEBUGGING ISSUES

| Symptom | Likely Cause | Fix |
|---|---|---|
| `alembic upgrade head` fails with `ModuleNotFoundError` | `sys.path.insert` missing in `alembic/env.py` | First line of `env.py` must be `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` |
| `alembic upgrade head` fails with `asyncpg not found` | Alembic using async URL | `env.py` must replace `+asyncpg` with `+psycopg2` and use `create_engine()` (sync) |
| `pytest` hangs forever | `asyncio_mode = auto` missing from `pytest.ini` | Add `asyncio_mode = auto` under `[pytest]` |
| `app.dependency_overrides[get_db]` not intercepting in tests | `get_db` imported from wrong module in the route | Routes must import `get_db` from `app.core.dependencies`, not `app.db.session` |
| `KeyError: 'role'` when decoding refresh token | Refresh token was passed to an endpoint expecting access token | Refresh tokens intentionally omit `role`. Always check `payload["type"] == "access"` |
| Celery worker crashes with `Event loop is closed` | Using `gevent` or `eventlet` pool | Must use `--pool=prefork`. Never pass `--pool=gevent` |
| `GET /docs` returns 404 in development | `docs_url=None` set unconditionally | `docs_url=None` only when `settings.is_production` is `True` |
| `{"status":"unhealthy","database":"error"}` on health check | Postgres not yet ready or DATABASE_URL wrong | Check `docker compose ps` — postgres must show `(healthy)`. Verify DATABASE_URL uses `postgres` hostname (Docker service name), not `localhost` |
| `sentence_transformers` model downloads on every container start | Model not pre-downloaded in Dockerfile | Confirm `RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"` is in Dockerfile and `SENTENCE_TRANSFORMERS_HOME=/app/models` is set |
| `422` on login with valid credentials | Email not `EmailStr`-valid in Pydantic | Use a properly formatted email; `EmailStr` requires `@` and valid domain |
| Middleware registers but AuditLog entries missing | Middleware registered after CORSMiddleware | `add_middleware(AuditLogMiddleware)` must come BEFORE `add_middleware(CORSMiddleware)` in `create_app()` |

---

## WHAT MUST BE WORKING BEFORE PHASE 1 STARTS

Phase 1 adds: OSINT adapters, scan jobs, targets, findings, Celery tasks, ChromaDB RAG, AI analysis, and reports. All Phase 1 work builds on this foundation. The following capabilities must be proven stable:

**1. Database layer**
- All 9 ORM models migrate cleanly from zero with `alembic upgrade head`
- `async_sessionmaker` + `get_db` dependency works in tests and production

**2. Auth + RBAC**
- JWTs issued, verified, rotated, and revoked correctly
- `require_role("admin")` blocks analysts; `get_current_user` rejects expired/invalid tokens
- Redis refresh-token store survives worker restarts (Redis has persistence volume)

**3. Investigation scaffold**
- CRUD + membership fully enforced before scan jobs are added in Phase 1
- `authorization_statement` >= 100 chars gate is validated — this is the ethical enforcement layer for all future OSINT operations

**4. Test infrastructure**
- `conftest.py` fixtures produce clean DB state per test
- `make test` takes < 60 seconds — confirms no fixture leaks
- CI green on push — mandatory before any Phase 1 PR merges

**5. Observability baseline**
- `audit_logs` table populated by `AuditLogMiddleware` for all mutating requests
- Health endpoint confirms DB + Redis liveness — Phase 1 will add ChromaDB check

**Handoff statement to Codex:** All files listed in the completion checklist above must exist and all Phase 0 DoD items must be ✅ before any Phase 1 file is created. Phase 1 begins with `workers/tasks.py` (scan job task) and `app/osint/adapters/base.py` (BaseOsintAdapter). Do not create those files until `make test` is green.

---

*PHASE 0 COMPLETE — READY FOR CODEX IMPLEMENTATION*
