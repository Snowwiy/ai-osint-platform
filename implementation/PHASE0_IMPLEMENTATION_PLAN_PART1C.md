# Phase 0: Foundation — Implementation Plan (Part 1C)

Continues from Part 1B. Covers Tasks 7–10.

---

## Task 7: Audit Service + Rate Limiter

### 7a — `backend/app/services/audit.py`

**Files:**
- Create: `backend/app/services/audit.py`

`record_event()` is the only function in this module. It inserts one row into `audit_logs`. It never commits — the caller owns the session lifecycle. It never raises — audit failures must not break the request.

---

- [ ] **Step 7.1 — Write `backend/app/services/audit.py`**

```python
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def record_event(
    db: AsyncSession,
    *,
    action: str,
    user_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Append one audit log entry to the session.

    IMPORTANT — caller rules:
    • Do NOT call db.commit() here — the session is owned by the caller.
    • In route handlers: get_db() commits automatically on success.
    • In middleware: caller must explicitly await db.commit().
    • This function never raises — exceptions are logged and swallowed
      so a logging failure never breaks the user-facing request.
    """
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
        )
        db.add(entry)
    except Exception:
        logger.exception("audit.record_event failed — entry dropped for action=%s", action)
```

- [ ] **Step 7.2 — Verify import**

```bash
cd backend
python -c "from app.services.audit import record_event; print('ok')"
# Expected: ok
```

- [ ] **Step 7.3 — Commit**

```bash
git add backend/app/services/audit.py
git commit -m "feat: add audit record_event service"
```

**Common mistakes:**
- Calling `await db.commit()` inside `record_event` — do not. The session's commit/rollback belongs to `get_db()` in route context or to the middleware explicitly.
- Letting exceptions propagate — wrap the entire body in `try/except` and log. Audit failures must never return a 500 to the user.

---

### 7b — `backend/app/core/rate_limit.py`

**Files:**
- Create: `backend/app/core/rate_limit.py`

A single module-level `limiter` instance. Routes import and decorate with `@limiter.limit(...)`.

---

- [ ] **Step 7.4 — Write `backend/app/core/rate_limit.py`**

```python
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Rate limit counters are stored in Redis so they survive worker restarts
# and work correctly when multiple Uvicorn workers run in production.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
)
```

- [ ] **Step 7.5 — Verify import**

```bash
python -c "from app.core.rate_limit import limiter; print(limiter)"
# Expected: prints the Limiter object (may warn about Redis connection — ignore for now)
```

- [ ] **Step 7.6 — Commit**

```bash
git add backend/app/core/rate_limit.py
git commit -m "feat: add slowapi rate limiter with Redis storage"
```

**Common mistakes:**
- Using default in-memory storage (`Limiter(key_func=...)` with no `storage_uri`) — fine for single-process dev, but silently allows unlimited requests when multiple workers run. Always configure Redis storage from the start.
- Trying to set `key_func` per-route — `key_func` is set once at Limiter creation. Per-route user-based limits use a different `key_func` override passed to `@limiter.limit(...)`.

---

## Task 8: Middleware (`backend/app/core/middleware.py`)

**Files:**
- Create: `backend/app/core/middleware.py`

Two responsibilities in one file:
1. `AuditLogMiddleware` — records every mutating request after the response is sent
2. `configure_cors()` helper that returns the CORS middleware kwargs (used by `main.py`)

---

- [ ] **Step 8.1 — Write `backend/app/core/middleware.py`**

```python
from __future__ import annotations

import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.security import decode_token
from app.db.session import AsyncSessionLocal
from app.services.audit import record_event

logger = logging.getLogger(__name__)

# Actions recorded by the audit middleware.
# GET requests are NOT audited at the middleware level
# (individual services audit sensitive reads explicitly).
_AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Paths excluded from audit logging (health checks, docs).
_EXCLUDED_PATHS = {"/api/v1/admin/health", "/docs", "/redoc", "/openapi.json"}


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Records an audit log entry for every mutating HTTP request.

    Runs AFTER the route handler has produced a response, so the
    status_code is available. Uses its own DB session — separate from
    the route handler's session managed by get_db().
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        if (
            request.method in _AUDITED_METHODS
            and request.url.path not in _EXCLUDED_PATHS
        ):
            await self._write_audit_log(request, response.status_code)

        return response

    async def _write_audit_log(
        self, request: Request, status_code: int
    ) -> None:
        """Write audit entry in a separate session. Swallows all exceptions."""
        user_id: uuid.UUID | None = None

        # Extract user identity from Bearer token if present.
        # Don't block the response if token parsing fails.
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                payload = decode_token(auth_header[7:])
                user_id = uuid.UUID(payload["sub"])
            except Exception:
                pass  # unauthenticated or expired token — still log, just without user_id

        action = f"{request.method.lower()}{request.url.path.replace('/', '.')}"

        try:
            async with AsyncSessionLocal() as db:
                await record_event(
                    db,
                    action=action,
                    user_id=user_id,
                    resource_type=_infer_resource_type(request.url.path),
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    details={
                        "status_code": status_code,
                        "path": request.url.path,
                        "method": request.method,
                    },
                )
                await db.commit()
        except Exception:
            logger.exception(
                "AuditLogMiddleware._write_audit_log failed for %s %s",
                request.method,
                request.url.path,
            )


def _infer_resource_type(path: str) -> str | None:
    """Derive a resource_type string from the URL path segment."""
    segments = [s for s in path.split("/") if s and not _is_uuid_segment(s)]
    # path like /api/v1/investigations/members → "investigations"
    resource_map = {
        "investigations": "investigation",
        "targets": "target",
        "users": "user",
        "auth": "auth",
        "admin": "admin",
        "findings": "finding",
        "analyses": "ai_analysis",
        "reports": "report",
    }
    for seg in reversed(segments):
        if seg in resource_map:
            return resource_map[seg]
    return None


def _is_uuid_segment(segment: str) -> bool:
    try:
        uuid.UUID(segment)
        return True
    except ValueError:
        return False
```

- [ ] **Step 8.2 — Verify import**

```bash
python -c "from app.core.middleware import AuditLogMiddleware; print('ok')"
# Expected: ok
```

- [ ] **Step 8.3 — Commit**

```bash
git add backend/app/core/middleware.py
git commit -m "feat: add AuditLogMiddleware that records all mutating requests"
```

**Common mistakes:**
- Reading `request.body()` inside middleware — the body stream can only be consumed once. The route handler needs it too. Never read the body in `BaseHTTPMiddleware.dispatch`.
- Using the route handler's DB session — middleware runs outside FastAPI's dependency injection. Always open a new `AsyncSessionLocal()` session.
- Forgetting `await db.commit()` — `record_event()` only adds to the session; middleware must commit explicitly.
- CORS middleware ordering — CORS must be registered in `main.py` **before** `AuditLogMiddleware`. FastAPI executes middleware in reverse registration order (last registered = outermost wrapper). See Task 9.

---

## Task 9: App Factory (`backend/app/main.py`)

**Files:**
- Create: `backend/app/main.py`

---

- [ ] **Step 9.1 — Write `backend/app/main.py`**

```python
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.middleware import AuditLogMiddleware
from app.core.rate_limit import limiter

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage resources that must exist for the lifetime of the process.
    Redis connection is created on startup, closed on shutdown.
    """
    logger.info("Starting up RavenTech OSINT Platform...")
    app.state.redis = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    # Verify Redis is reachable at startup — fail fast rather than fail silently.
    try:
        await app.state.redis.ping()
        logger.info("Redis connection established.")
    except Exception as exc:
        logger.error("Redis connection failed at startup: %s", exc)
        raise

    yield  # application runs here

    logger.info("Shutting down — closing Redis connection.")
    await app.state.redis.aclose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="RavenTech OSINT Platform",
        description="Authorized, defensive digital footprint analysis.",
        version="1.0.0",
        # Disable interactive docs in production — never expose Swagger publicly.
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Rate limiting ─────────────────────────────────────────────────────────
    # app.state.limiter must be set BEFORE adding the exception handler.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── Global exception handler ──────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An internal error occurred.",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )

    # ── Middleware (registration order = reverse execution order) ─────────────
    # Execution order when a request arrives:
    #   CORSMiddleware → AuditLogMiddleware → route handler
    #
    # Register AUDIT first so CORS is outermost (handles OPTIONS preflight
    # before the audit layer even sees the request).
    app.add_middleware(AuditLogMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    # ── Routes ────────────────────────────────────────────────────────────────
    from app.api.v1.router import api_router  # local import avoids circular refs
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
```

- [ ] **Step 9.2 — Verify the app instantiates without errors**

```bash
cd backend
python -c "from app.main import app; print('App created:', app.title)"
# Expected: App created: RavenTech OSINT Platform
```

This will fail if `app.api.v1.router` does not exist yet. Create it in Task 10 Step 10.1, then re-run this verification.

- [ ] **Step 9.3 — Commit (after Step 10.1 is done)**

```bash
git add backend/app/main.py
git commit -m "feat: add FastAPI app factory with Redis lifespan and middleware stack"
```

**Common mistakes:**
- Using `@app.on_event("startup")` / `@app.on_event("shutdown")` — these are deprecated in FastAPI. Always use `lifespan` with `@asynccontextmanager`.
- Registering `AuditLogMiddleware` after `CORSMiddleware` — FastAPI wraps middleware in reverse registration order. The last `add_middleware` call becomes the outermost layer. To ensure CORS is outermost, register AUDIT first, then CORS.
- Exposing `/docs` and `/openapi.json` in production — blocked via `docs_url=None` when `is_production=True`. Never skip this.
- Not calling `await app.state.redis.aclose()` in shutdown — leaked connections accumulate and exhaust the Redis connection pool.
- Importing `api_router` at module top level — creates circular import risks because router modules import from `core/` which is also imported in `main.py`. Use a local import inside `create_app()`.

---

## Task 10: Health Endpoint + First Router

**Files:**
- Create: `backend/app/api/v1/router.py`
- Create: `backend/app/api/v1/admin.py`
- Create: `backend/tests/integration/api/test_admin.py`

---

- [ ] **Step 10.1 — Write `backend/app/api/v1/router.py`**

```python
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import admin

api_router = APIRouter()

# Phase 0 routers — add more as tasks complete:
api_router.include_router(admin.router, tags=["admin"])

# Phase 0 stubs — uncomment as each task is completed:
# from app.api.v1 import auth, users, investigations, targets
# api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
# api_router.include_router(users.router, prefix="/users", tags=["users"])
# api_router.include_router(investigations.router, prefix="/investigations", tags=["investigations"])
# api_router.include_router(targets.router, prefix="/targets", tags=["targets"])
```

- [ ] **Step 10.2 — Write the failing smoke test first**

Create `backend/tests/integration/api/test_admin.py`:

```python
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_health_check_returns_200_and_healthy_status():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/admin/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database"] == "ok"
    assert body["redis"] == "ok"
    assert "timestamp" in body


async def test_health_check_response_shape():
    """Verify the response has exactly the documented keys — no extras, no missing."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/admin/health")

    body = response.json()
    expected_keys = {"status", "database", "redis", "timestamp"}
    assert set(body.keys()) == expected_keys


async def test_health_check_requires_no_auth():
    """Health endpoint is public — no Authorization header needed."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Deliberately send no Authorization header
        response = await client.get("/api/v1/admin/health")

    assert response.status_code == 200
```

- [ ] **Step 10.3 — Run the failing tests**

```bash
cd backend
pytest tests/integration/api/test_admin.py -v
```

Expected: `ImportError` — `app.api.v1.admin` does not exist yet. Confirms the test is correctly wired.

- [ ] **Step 10.4 — Write `backend/app/api/v1/admin.py`**

```python
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/admin/health")
async def health_check(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    System health check — public endpoint, no authentication required.
    Used by Docker HEALTHCHECK and external monitoring.

    Returns {"status": "healthy"} only when both DB and Redis are reachable.
    Returns {"status": "unhealthy"} (still HTTP 200) if any dependency is down,
    so monitoring tools can detect partial failures without confusing 5xx errors
    with app crashes.
    """
    db_status = "ok"
    redis_status = "ok"

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check: database ping failed")
        db_status = "error"

    try:
        await request.app.state.redis.ping()
    except Exception:
        logger.exception("Health check: Redis ping failed")
        redis_status = "error"

    overall = "healthy" if db_status == "ok" and redis_status == "ok" else "unhealthy"

    return {
        "status": overall,
        "database": db_status,
        "redis": redis_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
```

- [ ] **Step 10.5 — Run the tests and confirm they all pass**

```bash
pytest tests/integration/api/test_admin.py -v
```

Expected:
```
tests/integration/api/test_admin.py::test_health_check_returns_200_and_healthy_status PASSED
tests/integration/api/test_admin.py::test_health_check_response_shape PASSED
tests/integration/api/test_admin.py::test_health_check_requires_no_auth PASSED

3 passed in X.Xs
```

If `redis_status` is `"error"` and tests fail: confirm Redis is running (`docker compose up redis -d`) and `REDIS_URL` in `.env` is correct. The app's `lifespan` creates the Redis connection — tests use the same `app` instance so the lifespan context runs.

If `db_status` is `"error"`: confirm `DATABASE_URL` points to the test DB and `alembic upgrade head` has been run on it.

- [ ] **Step 10.6 — Manual smoke test against the running stack**

```bash
# Start the stack
make dev-bg

# Wait for healthy (watch until you see "Application startup complete")
docker compose logs backend -f

# Hit the health endpoint
curl -s http://localhost:8000/api/v1/admin/health | python -m json.tool
```

Expected:
```json
{
    "status": "healthy",
    "database": "ok",
    "redis": "ok",
    "timestamp": "2026-05-27T10:00:00.000000+00:00"
}
```

- [ ] **Step 10.7 — Verify main.py instantiates cleanly now**

```bash
python -c "from app.main import app; print('Routes:', [r.path for r in app.routes])"
# Expected: lists /api/v1/admin/health among the routes
```

- [ ] **Step 10.8 — Commit**

```bash
git add backend/app/api/v1/router.py backend/app/api/v1/admin.py \
        backend/app/main.py backend/tests/integration/api/test_admin.py
git commit -m "feat: add app factory, middleware stack, router, and health endpoint with smoke tests"
```

**Definition of done:** All 3 integration tests pass. `make dev-bg` followed by `curl http://localhost:8000/api/v1/admin/health` returns `{"status":"healthy",...}`.

**Common mistakes:**
- Using `db.execute("SELECT 1")` without `text()` wrapper — SQLAlchemy 2.0 requires `text()` for raw SQL strings. `await db.execute("SELECT 1")` raises `ArgumentError`.
- Accessing `request.app.state.redis` before the lifespan runs — in tests, `ASGITransport` triggers the lifespan automatically. In standalone scripts outside FastAPI, `app.state.redis` won't exist.
- Returning HTTP 503 when unhealthy — returning 200 with `{"status":"unhealthy"}` is intentional. Docker's HEALTHCHECK determines health from the exit code of a curl command, not from the HTTP status. A 503 from the health endpoint causes Docker to immediately restart the container, hiding the real error in logs. Return 200 always; let the status field carry the signal.
- Missing `pytest.ini` with `asyncio_mode = auto` — without this, async test functions silently pass without awaiting. Create `backend/pytest.ini` now if it doesn't exist yet:

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short
```

---

*PART1C COMPLETE — READY FOR PART1D*
