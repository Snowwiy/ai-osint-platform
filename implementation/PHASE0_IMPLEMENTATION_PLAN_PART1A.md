# Phase 0: Foundation — Implementation Plan (Part 1A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use `- [ ]` checkbox syntax for tracking.

**Goal:** Stand up a fully working FastAPI + PostgreSQL + Redis + Celery foundation with JWT auth, RBAC, investigation/target CRUD, audit logging, and a passing CI pipeline — the stable base Phase 1 builds on.

**Architecture:** Modular monolith. Routes → Services → DB. No business logic in routes. No direct DB access in routes. All config from pydantic-settings. No hardcoded secrets anywhere.

**Tech Stack:** Python 3.12, FastAPI 0.115+, SQLAlchemy 2.0 async (asyncpg), Alembic (psycopg2 sync), PostgreSQL 16, Redis 7, Celery 5 (prefork), PyJWT, passlib[bcrypt], slowapi, httpx, pytest-asyncio

---

## Deliverable 1 — Phase 0 File Tree

Every file that must exist at the end of Phase 0. Nothing more.

```
raventech-osint/
├── .github/
│   └── workflows/
│       └── test.yml                        # CI: ruff + mypy + pytest on push/PR
├── .gitignore
├── .pre-commit-config.yaml
├── .env.example                            # All env vars documented with inline comments
├── Makefile
├── docker-compose.yml                      # 4 services: postgres, redis, backend, celery-worker
│                                           # nginx + frontend added in Phase 3/4
├── ARCHITECTURE.md                         # (already exists — do not modify)
├── MVP_ROADMAP.md
├── DATABASE_SCHEMA.md
├── API_SPEC.md
├── SECURITY_MODEL.md
├── CODEX_HANDOFF.md
└── backend/
    ├── app/
    │   ├── __init__.py
    │   ├── main.py                         # App factory, lifespan, middleware registration
    │   ├── api/
    │   │   ├── __init__.py
    │   │   └── v1/
    │   │       ├── __init__.py
    │   │       ├── router.py               # Includes all Phase 0 sub-routers
    │   │       ├── auth.py                 # POST /login /refresh /logout, GET /me, PUT /me/password
    │   │       ├── users.py                # GET/POST/PUT/DELETE /users/* [admin only]
    │   │       ├── investigations.py       # CRUD /investigations/* + member management
    │   │       ├── targets.py              # CRUD /targets/*
    │   │       └── admin.py               # GET /admin/health, GET /admin/stats
    │   ├── core/
    │   │   ├── __init__.py
    │   │   ├── config.py                   # Settings (pydantic-settings) — single source of truth
    │   │   ├── security.py                 # create_access_token, create_refresh_token, hash_password, verify_password
    │   │   ├── dependencies.py             # get_db(), get_current_user(), require_role(), get_redis()
    │   │   ├── rate_limit.py               # slowapi Limiter instance
    │   │   └── middleware.py               # AuditLogMiddleware, CORS setup
    │   ├── models/
    │   │   ├── __init__.py                 # Import all models so Alembic sees them
    │   │   ├── base.py                     # DeclarativeBase + TimestampMixin
    │   │   ├── user.py
    │   │   ├── investigation.py
    │   │   ├── investigation_member.py
    │   │   ├── target.py
    │   │   ├── scan_job.py
    │   │   ├── finding.py
    │   │   ├── ai_analysis.py
    │   │   ├── report.py
    │   │   └── audit_log.py
    │   ├── schemas/
    │   │   ├── __init__.py
    │   │   ├── common.py                   # PaginatedResponse, ErrorResponse
    │   │   ├── auth.py                     # LoginRequest, TokenResponse, PasswordChangeRequest
    │   │   ├── user.py                     # UserCreate, UserUpdate, UserResponse
    │   │   ├── investigation.py            # InvestigationCreate, InvestigationResponse, MemberAdd
    │   │   └── target.py                   # TargetCreate, TargetResponse
    │   ├── services/
    │   │   ├── __init__.py
    │   │   ├── auth.py                     # login(), refresh_tokens(), get_user_by_username()
    │   │   ├── user.py                     # CRUD helpers for users
    │   │   ├── investigation.py            # CRUD + membership + ownership checks
    │   │   ├── target.py                   # validate_target_value() + CRUD
    │   │   └── audit.py                    # record_event()
    │   └── db/
    │       └── session.py                  # AsyncEngine + AsyncSessionLocal + get_db()
    ├── workers/
    │   ├── __init__.py
    │   └── celery_app.py                   # Celery app instance, prefork config
    ├── alembic/
    │   ├── env.py                          # Sync psycopg2 engine — CRITICAL pattern
    │   ├── script.py.mako
    │   └── versions/
    │       └── 0001_initial.py             # Auto-generated initial migration
    ├── tests/
    │   ├── conftest.py                     # Fixtures: engine, db session, HTTP client, users, auth headers
    │   ├── unit/
    │   │   └── test_security.py            # hash_password, verify_password, create/decode tokens
    │   └── integration/
    │       └── api/
    │           ├── test_admin.py           # GET /admin/health
    │           ├── test_auth.py            # login, refresh, logout, me, password change
    │           ├── test_users.py           # admin user CRUD
    │           ├── test_investigations.py  # CRUD + member management + auth_statement validation
    │           └── test_targets.py         # CRUD + private IP rejection + domain validation
    ├── scripts/
    │   └── create_admin.py
    ├── alembic.ini
    ├── pytest.ini
    ├── requirements.txt
    ├── requirements-dev.txt
    └── Dockerfile
```

---

## Deliverable 2 — Ordered Implementation Sequence

Strict order. Each task depends on all previous tasks. Do not reorder.

| # | Task | Produces |
|---|------|---------|
| 1 | Repo scaffold | .gitignore, .env.example, Makefile, pre-commit, CI workflow, directory skeleton |
| 2 | `core/config.py` | Settings class — all tasks depend on this |
| 3 | `db/session.py` | AsyncEngine + AsyncSessionLocal |
| 4 | `models/` | All 9 ORM models + base |
| 5 | Alembic setup | `alembic.ini`, `alembic/env.py`, initial migration run |
| 6 | `core/security.py` | JWT encode/decode, bcrypt hash/verify |
| 7 | `core/rate_limit.py` | slowapi Limiter instance |
| 8 | `services/audit.py` | `record_event()` |
| 9 | `core/middleware.py` | AuditLogMiddleware, CORS |
| 10 | `main.py` | App factory + lifespan (Redis connect/disconnect) |
| 11 | `api/v1/admin.py` + router | GET /admin/health — first working endpoint |
| 12 | `tests/conftest.py` | All test fixtures — required before writing any test |
| 13 | `schemas/` | All Pydantic I/O schemas |
| 14 | `core/dependencies.py` | get_db, get_current_user, require_role, get_redis |
| 15 | `services/auth.py` + `api/v1/auth.py` | Auth endpoints — login/refresh/logout/me/password |
| 16 | `services/user.py` + `api/v1/users.py` | Admin user CRUD |
| 17 | `services/investigation.py` + `api/v1/investigations.py` | Investigation CRUD + members |
| 18 | `services/target.py` + `api/v1/targets.py` | Target CRUD + validation |
| 19 | `workers/celery_app.py` | Celery foundation (prefork) |
| 20 | `Dockerfile` + `docker-compose.yml` | Full Docker stack |
| 21 | `scripts/create_admin.py` | Admin bootstrap |
| 22 | Phase 0 final verification | All exit criteria pass |

---

## Deliverable 3 — GitHub Milestone M0 Issues

Create these as GitHub Issues under milestone **M0: Foundation**.

1. `[scaffold]` Initialize repo, CI, pre-commit, Makefile
2. `[db]` ORM models + Alembic initial migration (sync engine)
3. `[auth]` JWT auth endpoints: login, refresh, logout, me, password
4. `[admin]` User management CRUD (admin role only)
5. `[investigations]` Investigation CRUD + owner/collaborator membership
6. `[targets]` Target CRUD + validation (private IP blocklist, domain format)
7. `[audit]` AuditLogMiddleware — record every mutating request
8. `[infra]` Rate limiting (slowapi per-IP + per-user)
9. `[docker]` Docker Compose stack: postgres, redis, backend, celery-worker
10. `[tests]` Integration tests: auth + investigations + targets

---

## Deliverable 4 — Exact Dependencies

**`backend/requirements.txt`** — production runtime
```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
sqlalchemy[asyncio]>=2.0.35
asyncpg>=0.29.0
psycopg2-binary>=2.9.9
alembic>=1.13.2
pydantic>=2.8.2
pydantic-settings>=2.4.0
PyJWT>=2.9.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.9
slowapi>=0.1.9
redis>=5.0.8
celery>=5.4.0
httpx>=0.27.2
```

**`backend/requirements-dev.txt`** — test and tooling
```
-r requirements.txt
pytest>=8.3.0
pytest-asyncio>=0.23.8
pytest-cov>=5.0.0
httpx>=0.27.2
ruff>=0.6.0
mypy>=1.11.0
pre-commit>=3.8.0
detect-secrets>=1.5.0
types-passlib>=1.7.7.post4
```

> `asyncpg` is the async runtime driver. `psycopg2-binary` is **only** for Alembic migrations. Both must be present. This is not a mistake.

---

## Deliverable 5 — Docker Compose Specification

**`docker-compose.yml`** — Phase 0 (4 services; nginx + frontend added in Phase 3/4)

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: raventech
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: raventech
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"          # exposed for dev tooling (TablePlus, psql)
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U raventech"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"          # exposed for dev tooling (redis-cli)
    healthcheck:
      test: ["CMD", "redis-cli", "--no-auth-warning", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      target: development
    env_file: .env
    volumes:
      - ./backend:/app        # hot reload in dev
      - reports_data:/data/reports
      - chroma_data:/data/chroma  # placeholder volume; ChromaDB used in Phase 1
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  celery-worker:
    build:
      context: ./backend
      target: development
    env_file: .env
    volumes:
      - ./backend:/app
      - reports_data:/data/reports
      - chroma_data:/data/chroma
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A workers.celery_app worker --loglevel=info --pool=prefork --concurrency=2

volumes:
  postgres_data:
  redis_data:
  reports_data:
  chroma_data:
```

---

## Deliverable 6 — Environment Variables

**`.env.example`** — copy to `.env` and fill in values before running

```bash
# ─── App ──────────────────────────────────────────────────────
APP_SECRET_KEY=          # Required. 64 random hex bytes. Generate: python -c "import secrets; print(secrets.token_hex(64))"
APP_ENVIRONMENT=development  # development | production
APP_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:8000

# ─── Database ─────────────────────────────────────────────────
POSTGRES_PASSWORD=       # Required. Set a strong password.
DATABASE_URL=postgresql+asyncpg://raventech:${POSTGRES_PASSWORD}@postgres:5432/raventech
# For Alembic (migrations only — do not use in app code):
# DATABASE_URL_SYNC=postgresql+psycopg2://raventech:${POSTGRES_PASSWORD}@postgres:5432/raventech

# ─── Redis ────────────────────────────────────────────────────
REDIS_PASSWORD=          # Required. Set a strong password.
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0

# ─── ChromaDB (Phase 1 — leave defaults for Phase 0) ──────────
CHROMA_DATA_PATH=/data/chroma

# ─── AI (Phase 1 — leave empty for Phase 0) ───────────────────
ANTHROPIC_API_KEY=
OBSIDIAN_WIKI_PATH=

# ─── OSINT APIs (Phase 1/2 — leave empty for Phase 0) ─────────
SHODAN_API_KEY=
VT_API_KEY=
ABUSEIPDB_API_KEY=
OTX_API_KEY=
URLSCAN_API_KEY=
SECURITYTRAILS_API_KEY=
CENSYS_API_ID=
CENSYS_SECRET=
HIBP_API_KEY=
GITHUB_TOKEN=

# ─── Admin Bootstrap ─────────────────────────────────────────
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@raventech.mx
ADMIN_PASSWORD=          # Required. Min 12 chars, uppercase, lowercase, digit, special.

# ─── Test DB (used by pytest — separate from dev DB) ──────────
TEST_DATABASE_URL=postgresql+asyncpg://raventech:${POSTGRES_PASSWORD}@localhost:5432/raventech_test
```

---

## Deliverable 7 — Database Migration Order

Run these commands in order. Never skip step 2 before step 3.

```bash
# 1. Confirm Alembic can connect (sync engine via psycopg2)
make shell          # opens a shell inside the backend container
alembic check       # should say "No new upgrade operations detected" or list pending

# 2. Generate initial migration (run AFTER all models are written)
alembic revision --autogenerate -m "initial"
# Review the generated file in alembic/versions/ before running step 3

# 3. Apply migration
alembic upgrade head

# 4. Verify tables exist
psql postgresql://raventech:PASSWORD@localhost:5432/raventech -c "\dt"
# Expected: 10 tables (users, investigations, investigation_members, targets,
#           scan_jobs, findings, ai_analyses, reports, audit_logs + alembic_version)

# 5. Create test DB (once, before first pytest run)
psql postgresql://raventech:PASSWORD@localhost:5432/postgres -c "CREATE DATABASE raventech_test;"
# pytest conftest.py creates tables in raventech_test automatically
```

---

## Deliverable 8 — Test Strategy

**Unit tests** (`tests/unit/`) — no DB, no HTTP, no external services:
- Mock all dependencies with `unittest.mock`
- Test pure functions: `hash_password`, `verify_password`, `create_access_token`, `decode_token`, `validate_target_value`
- Run in milliseconds

**Integration tests** (`tests/integration/`) — real PostgreSQL (raventech_test DB), real Redis:
- `AsyncClient` with `ASGITransport(app=app)` — no network overhead
- Each test function gets a clean DB via `autouse` table-truncation fixture
- Fixtures create test users, auth tokens, and base data
- Test the full request → service → DB → response cycle

**pytest configuration** (`backend/pytest.ini`):
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short
```

---

## Deliverable 9 — Definition of Done

| Task | Done When |
|------|-----------|
| Task 1 (Scaffold) | `git log` shows initial commit; `pre-commit run --all-files` passes clean |
| Task 2 (Config) | `python -c "from app.core.config import settings; print(settings.APP_ENVIRONMENT)"` prints without error |
| Task 3 (DB Session) | `python -c "from app.db.session import AsyncSessionLocal; print('ok')"` prints without error |
| Task 4 (Models) | `python -c "from app.models import *; print('ok')"` prints without error |
| Task 5 (Alembic) | `alembic upgrade head` runs clean; all 10 tables exist in psql |
| Task 6 (Security) | All unit tests in `test_security.py` pass |
| Tasks 7–10 (Core) | App starts: `uvicorn app.main:app` shows no import errors |
| Task 11 (Health) | `GET /api/v1/admin/health` returns `{"status":"healthy","database":"ok","redis":"ok"}` |
| Task 12 (Conftest) | `pytest tests/ --collect-only` lists all tests without errors |
| Tasks 13–14 (Schemas+Deps) | `pytest tests/unit/` passes |
| Task 15 (Auth) | `pytest tests/integration/api/test_auth.py` — all 8 tests pass |
| Task 16 (Users) | `pytest tests/integration/api/test_users.py` — all 6 tests pass |
| Task 17 (Investigations) | `pytest tests/integration/api/test_investigations.py` — all 10 tests pass |
| Task 18 (Targets) | `pytest tests/integration/api/test_targets.py` — all 8 tests pass |
| Task 19 (Celery) | `celery -A workers.celery_app inspect ping` returns `pong` from worker |
| Task 20 (Docker) | `docker compose up --build` → all 4 services healthy; `GET /api/v1/admin/health` → 200 |
| Task 21 (Admin script) | `python scripts/create_admin.py` creates admin user; login with those credentials works |
| Task 22 (Final) | `make test` passes 100%; `make lint` passes; `make check` = green |

---

## Deliverable 10 — Common Implementation Mistakes

Read this before writing a single line of code.

1. **Alembic with async URL** — If `DATABASE_URL` contains `+asyncpg`, Alembic will crash. `alembic/env.py` must call `.replace("+asyncpg", "+psycopg2")` and use `create_engine()` (sync), not `create_async_engine()`. See Task 5.

2. **Celery with gevent/eventlet** — OSINT adapters use `async def`. Celery tasks call them via `asyncio.run()`. This only works with `prefork` pool. Setting `worker_pool="gevent"` or `"eventlet"` breaks `asyncio.run()` silently. Always set `worker_pool="prefork"`.

3. **SQLAlchemy 1.x query style** — `db.query(User).filter(...)` is SQLAlchemy 1.x style and does not work with async sessions. Use `select(User).where(...)` then `await db.execute(stmt)`.

4. **Missing `asyncio_mode = auto`** — Without this in `pytest.ini`, async test functions silently become sync and never actually `await` anything. Tests pass trivially and catch nothing.

5. **Confusing platform role with investigation role** — `users.role` is `admin | analyst`. `investigation_members.role` is `owner | collaborator`. Never mix these. The `require_role()` dependency checks `users.role`. Investigation ownership is a separate check against `investigation_members`.

6. **Not checking `is_active` in `get_current_user`** — A deactivated user's JWT is still cryptographically valid. `get_current_user` must load the user from DB on every request and verify `user.is_active == True`.

7. **Refresh token stored in Redis wrong** — The Redis key must be `rt:{jti}` (not the token itself). On logout, delete by JTI. On refresh, verify the JTI exists in Redis before issuing a new access token.

8. **`python-multipart` missing** — FastAPI requires `python-multipart` for form data parsing (used by OAuth2PasswordRequestForm if you use it). Even if you use JSON login, add it to avoid confusing startup errors.

9. **Missing `from __future__ import annotations`** — SQLAlchemy 2.0 `Mapped[...]` type hints require PEP 563 deferred evaluation. Without this at the top of every model file, Python 3.10- raises `NameError`.

10. **Models not imported in `alembic/env.py`** — Alembic generates diffs by comparing `Base.metadata` to the live DB. If model files aren't imported, their tables are invisible to Alembic and migration will be empty. Always `import app.models` in `alembic/env.py`.

11. **`audit_logs.id` is `BIGSERIAL`, not UUID** — Do not use `gen_random_uuid()` or `uuid.uuid4()` as default for this column. Use `BigInteger` with `autoincrement=True`.

12. **`investigation_members` has composite PK** — No single `id` column. Primary key is `(investigation_id, user_id)`. Map it correctly in SQLAlchemy with two `primary_key=True` columns.

---

## Deliverable 11 — Codex-Ready Implementation Checklist

Copy this into a GitHub issue or project board. Check off as you go.

```
PHASE 0 — FOUNDATION CHECKLIST

REPO SCAFFOLD
[ ] git init, initial commit with blueprint .md files
[ ] .gitignore — excludes .env, __pycache__, *.pyc, node_modules, chroma_data/, reports_output/
[ ] .env.example — all vars with inline comments
[ ] .pre-commit-config.yaml — ruff, mypy, detect-secrets hooks
[ ] .github/workflows/test.yml — pytest + ruff + mypy on push/PR to main
[ ] Makefile — dev, test, migrate, migration, lint, format, shell, create-admin targets
[ ] Backend directory skeleton created (empty __init__.py files in place)

CONFIG & DB FOUNDATION
[ ] backend/app/core/config.py — Settings class, settings singleton, all env vars typed
[ ] backend/app/db/session.py — AsyncEngine, AsyncSessionLocal, get_db() generator
[ ] backend/app/models/base.py — DeclarativeBase, TimestampMixin
[ ] backend/app/models/user.py
[ ] backend/app/models/investigation.py
[ ] backend/app/models/investigation_member.py (composite PK)
[ ] backend/app/models/target.py
[ ] backend/app/models/scan_job.py
[ ] backend/app/models/finding.py
[ ] backend/app/models/ai_analysis.py
[ ] backend/app/models/report.py
[ ] backend/app/models/audit_log.py (BIGSERIAL PK)
[ ] backend/app/models/__init__.py — imports ALL models
[ ] backend/alembic.ini
[ ] backend/alembic/env.py — sync psycopg2 engine, imports all models
[ ] alembic revision --autogenerate -m "initial" — review generated file
[ ] alembic upgrade head — verify 10 tables created

SECURITY & CORE
[ ] backend/app/core/security.py — hash_password, verify_password, create_access_token, create_refresh_token, decode_token
[ ] unit tests pass: tests/unit/test_security.py
[ ] backend/app/core/rate_limit.py — limiter instance
[ ] backend/app/services/audit.py — record_event()
[ ] backend/app/core/middleware.py — AuditLogMiddleware, CORS
[ ] backend/app/main.py — app factory, lifespan (Redis connect), middleware

HEALTH ENDPOINT (first smoke test)
[ ] backend/app/api/v1/admin.py — GET /admin/health (no auth), GET /admin/stats
[ ] backend/app/api/v1/router.py — includes admin router
[ ] Manual: GET http://localhost:8000/api/v1/admin/health → 200 {"status":"healthy",...}

TEST INFRASTRUCTURE
[ ] backend/pytest.ini — asyncio_mode=auto, testpaths=tests
[ ] backend/tests/conftest.py — test engine, db fixture, client fixture, user fixtures, auth header fixtures
[ ] CREATE DATABASE raventech_test; (run once)

SCHEMAS & DEPENDENCIES
[ ] backend/app/schemas/common.py
[ ] backend/app/schemas/auth.py
[ ] backend/app/schemas/user.py
[ ] backend/app/schemas/investigation.py
[ ] backend/app/schemas/target.py
[ ] backend/app/core/dependencies.py — get_db, get_current_user (checks is_active), require_role, get_redis

AUTH ENDPOINTS
[ ] backend/app/services/auth.py — login, refresh_tokens, revoke_token
[ ] backend/app/api/v1/auth.py — 5 endpoints
[ ] pytest tests/integration/api/test_auth.py — all pass

USER MANAGEMENT
[ ] backend/app/services/user.py — get, list, create, update, deactivate
[ ] backend/app/api/v1/users.py — 5 endpoints (admin only)
[ ] pytest tests/integration/api/test_users.py — all pass

INVESTIGATIONS
[ ] backend/app/services/investigation.py — CRUD + membership + ownership checks
[ ] backend/app/api/v1/investigations.py — 8 endpoints
[ ] pytest tests/integration/api/test_investigations.py — all pass

TARGETS
[ ] backend/app/services/target.py — validate_target_value() + CRUD
[ ] backend/app/api/v1/targets.py — 4 endpoints
[ ] pytest tests/integration/api/test_targets.py — all pass

CELERY & DOCKER
[ ] backend/workers/__init__.py
[ ] backend/workers/celery_app.py — Celery app, prefork pool
[ ] backend/Dockerfile — multi-stage (builder + runtime)
[ ] docker-compose.yml — 4 services with healthchecks
[ ] docker compose up --build → all services healthy

ADMIN BOOTSTRAP & FINAL
[ ] backend/scripts/create_admin.py — reads env vars, creates admin user idempotently
[ ] make create-admin → admin user exists in DB
[ ] make test → 100% pass
[ ] make lint → ruff + mypy clean
[ ] git tag phase-0-complete
```

---

## Task 1: Repository Scaffold

**Files:**
- Create: `.gitignore`
- Create: `.env.example` (see Deliverable 6)
- Create: `.pre-commit-config.yaml`
- Create: `.github/workflows/test.yml`
- Create: `Makefile`
- Create: all empty `__init__.py` files to establish the module structure

---

- [ ] **Step 1.1 — Create .gitignore**

```
# Python
__pycache__/
*.py[cod]
*.so
.Python
.venv/
venv/
dist/
*.egg-info/

# Environment
.env
.env.*
!.env.example

# Testing
.pytest_cache/
.coverage
htmlcov/

# Data volumes
chroma_data/
reports_output/

# Node
node_modules/
dist/
.next/

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 1.2 — Create .pre-commit-config.yaml**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.0
    hooks:
      - id: mypy
        additional_dependencies:
          - pydantic>=2.8.0
          - types-passlib>=1.7.7

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: [--baseline, .secrets.baseline]
```

- [ ] **Step 1.3 — Create .github/workflows/test.yml**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: raventech
          POSTGRES_PASSWORD: testpass
          POSTGRES_DB: raventech_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: backend/requirements-dev.txt

      - name: Install dependencies
        run: pip install -r backend/requirements-dev.txt

      - name: Run ruff
        run: ruff check backend/app backend/tests
        working-directory: .

      - name: Run mypy
        run: mypy backend/app
        working-directory: .

      - name: Run tests
        env:
          APP_SECRET_KEY: "00000000000000000000000000000000000000000000000000000000000000000000"
          APP_ENVIRONMENT: development
          APP_ALLOWED_ORIGINS: "http://localhost:5173"
          DATABASE_URL: "postgresql+asyncpg://raventech:testpass@localhost:5432/raventech_test"
          REDIS_URL: "redis://localhost:6379/1"
          CHROMA_DATA_PATH: "/tmp/chroma_test"
          TEST_DATABASE_URL: "postgresql+asyncpg://raventech:testpass@localhost:5432/raventech_test"
        run: |
          cd backend
          alembic upgrade head
          pytest tests/ -v --tb=short --cov=app --cov-report=term-missing
```

- [ ] **Step 1.4 — Create Makefile**

```makefile
.PHONY: dev dev-bg down test test-unit test-int migrate migration lint format shell create-admin check

# ─── Docker ──────────────────────────────────────────────────────────────────
dev:
	docker compose up --build

dev-bg:
	docker compose up --build -d

down:
	docker compose down

shell:
	docker compose exec backend bash

# ─── Testing ─────────────────────────────────────────────────────────────────
test:
	docker compose exec backend pytest tests/ -v --tb=short --cov=app --cov-report=term-missing

test-unit:
	docker compose exec backend pytest tests/unit/ -v

test-int:
	docker compose exec backend pytest tests/integration/ -v

# ─── Database ────────────────────────────────────────────────────────────────
migrate:
	docker compose exec backend alembic upgrade head

migration:
	@test -n "$(msg)" || (echo "Usage: make migration msg='describe your change'" && exit 1)
	docker compose exec backend alembic revision --autogenerate -m "$(msg)"

# ─── Code Quality ────────────────────────────────────────────────────────────
lint:
	docker compose exec backend ruff check app/ tests/ workers/
	docker compose exec backend mypy app/

format:
	docker compose exec backend ruff format app/ tests/ workers/

check: lint test

# ─── Bootstrap ───────────────────────────────────────────────────────────────
create-admin:
	docker compose exec backend python scripts/create_admin.py
```

- [ ] **Step 1.5 — Create empty module skeleton**

Run these from the repo root to create all `__init__.py` files:

```bash
mkdir -p backend/app/{api/v1,core,models,schemas,services,db}
mkdir -p backend/{workers,alembic/versions,tests/unit,tests/integration/api,scripts}

touch backend/app/__init__.py
touch backend/app/api/__init__.py
touch backend/app/api/v1/__init__.py
touch backend/app/core/__init__.py
touch backend/app/models/__init__.py
touch backend/app/schemas/__init__.py
touch backend/app/services/__init__.py
touch backend/workers/__init__.py
touch backend/tests/__init__.py
touch backend/tests/unit/__init__.py
touch backend/tests/integration/__init__.py
touch backend/tests/integration/api/__init__.py
```

- [ ] **Step 1.6 — Create .env from .env.example and fill in required values**

```bash
cp .env.example .env
# Now open .env and set:
# APP_SECRET_KEY  — python -c "import secrets; print(secrets.token_hex(64))"
# POSTGRES_PASSWORD — any strong password
# REDIS_PASSWORD  — any strong password
# ADMIN_PASSWORD  — min 12 chars, uppercase + lowercase + digit + special
```

- [ ] **Step 1.7 — Initial git commit**

```bash
git init
git add .gitignore .env.example .pre-commit-config.yaml .github/ Makefile backend/
git commit -m "chore: initialize repo scaffold with CI, pre-commit, and directory structure"
```

**Definition of done:** `git log --oneline` shows one commit; `ls backend/app/` shows directories.

---

## Task 2: Core Configuration (`backend/app/core/config.py`)

**Files:**
- Create: `backend/app/core/config.py`
- Test: no unit test needed — import verification is the test

The Settings class is the single source of truth for all configuration. Every other module imports `settings` from here. Never use `os.environ.get()` outside this file.

---

- [ ] **Step 2.1 — Write `backend/app/core/config.py`**

```python
from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────────────────────
    APP_SECRET_KEY: str
    APP_ENVIRONMENT: Literal["development", "production"] = "development"
    APP_ALLOWED_ORIGINS: str = "http://localhost:5173"

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str              # postgresql+asyncpg://...
    TEST_DATABASE_URL: str = ""    # used by pytest conftest only

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str                 # redis://:password@redis:6379/0

    # ── ChromaDB (Phase 1) ────────────────────────────────────────────────────
    CHROMA_DATA_PATH: str = "/data/chroma"

    # ── AI (Phase 1) ─────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    OBSIDIAN_WIKI_PATH: str = ""

    # ── OSINT APIs (Phase 1/2) ────────────────────────────────────────────────
    SHODAN_API_KEY: str = ""
    VT_API_KEY: str = ""
    ABUSEIPDB_API_KEY: str = ""
    OTX_API_KEY: str = ""
    URLSCAN_API_KEY: str = ""
    SECURITYTRAILS_API_KEY: str = ""
    CENSYS_API_ID: str = ""
    CENSYS_SECRET: str = ""
    HIBP_API_KEY: str = ""
    GITHUB_TOKEN: str = ""

    # ── Admin bootstrap ───────────────────────────────────────────────────────
    ADMIN_USERNAME: str = ""
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.APP_ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENVIRONMENT == "production"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",           # ignore unknown env vars — don't crash
    )


settings = Settings()
```

- [ ] **Step 2.2 — Verify import works**

```bash
cd backend
python -c "from app.core.config import settings; print(settings.APP_ENVIRONMENT)"
# Expected output: development
```

- [ ] **Step 2.3 — Commit**

```bash
git add backend/app/core/config.py
git commit -m "feat: add Settings class with pydantic-settings"
```

**Definition of done:** Step 2.2 prints `development` without errors.

---

## Task 3: Database Session (`backend/app/db/session.py`)

**Files:**
- Create: `backend/app/db/session.py`

This module creates the async SQLAlchemy engine and session factory. Every DB operation in the app flows through `AsyncSessionLocal`. Routes never touch this directly — they use `get_db()` from `core/dependencies.py` (Task 14).

---

- [ ] **Step 3.1 — Write `backend/app/db/session.py`**

```python
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENVIRONMENT == "development",  # log SQL in dev only
    pool_pre_ping=True,    # verify connection health before using from pool
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,   # objects remain accessible after commit
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields an async DB session.
    Commits on success, rolls back on any exception.
    Add to route signature: db: AsyncSession = Depends(get_db)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

- [ ] **Step 3.2 — Verify import works**

```bash
cd backend
python -c "from app.db.session import AsyncSessionLocal; print('AsyncSessionLocal:', AsyncSessionLocal)"
# Expected: prints the sessionmaker object without errors
```

- [ ] **Step 3.3 — Commit**

```bash
git add backend/app/db/session.py
git commit -m "feat: add async SQLAlchemy engine and session factory"
```

**Definition of done:** Step 3.2 prints without errors. Note: no DB connection is made yet — the engine is created lazily. The first actual connection happens when Alembic runs in Task 5.

---

*PART1A COMPLETE — READY FOR PART1B*
