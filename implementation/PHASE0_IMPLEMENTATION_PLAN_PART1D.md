# Phase 0: Foundation — Implementation Plan (Part 1D)

Continues from Part 1C. Covers Tasks 11–13.

---

## Task 11: Test Infrastructure (`backend/tests/conftest.py`)

**Files:**
- Create: `backend/pytest.ini`
- Create: `backend/tests/conftest.py`

The conftest provides all shared fixtures. Every integration test depends on it. Write it before writing any route test — a broken conftest produces misleading errors in unrelated test files.

---

- [ ] **Step 11.1 — Write `backend/pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short
```

> **Critical:** Without `asyncio_mode = auto`, async test functions silently become sync. They appear to pass while actually skipping every `await`. Set this before writing a single test.

- [ ] **Step 11.2 — Create the test database**

Run once. Never needs to be repeated unless the container is wiped.

```bash
docker compose exec postgres psql -U raventech -d postgres \
  -c "CREATE DATABASE raventech_test;"

# Apply the same schema to the test DB
docker compose exec backend bash -c \
  "TEST_DATABASE_URL=postgresql+asyncpg://raventech:\$POSTGRES_PASSWORD@postgres:5432/raventech_test \
   alembic upgrade head"
```

- [ ] **Step 11.3 — Write `backend/tests/conftest.py`**

```python
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401 — registers all models with Base.metadata
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.base import Base
from app.models.investigation import Investigation
from app.models.investigation_member import InvestigationMember
from app.models.user import User

# ── Test database URLs ────────────────────────────────────────────────────────
_ASYNC_TEST_URL = settings.TEST_DATABASE_URL
_SYNC_TEST_URL = settings.TEST_DATABASE_URL.replace("+asyncpg", "+psycopg2")

# Module-level async engine — created once, shared by all tests in the session.
_test_engine = create_async_engine(_ASYNC_TEST_URL, echo=False, pool_pre_ping=True)
_TestSession = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)


# ── Session-scoped: create tables once before any test runs ───────────────────
# Using a synchronous engine here avoids pytest-asyncio event-loop-scope
# complexity for session-scoped fixtures.
def pytest_sessionstart(session: pytest.Session) -> None:
    """Create all tables in the test DB before the test session begins."""
    sync_engine = create_engine(_SYNC_TEST_URL)
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Drop all tables after the test session ends."""
    sync_engine = create_engine(_SYNC_TEST_URL)
    Base.metadata.drop_all(sync_engine)
    sync_engine.dispose()


# ── Function-scoped: truncate all rows between every test ─────────────────────
@pytest.fixture(autouse=True)
async def clean_db() -> None:
    """
    Runs after every test function. Deletes all rows from all tables.
    Preserves schema — faster than drop/create.
    Reversed order respects FK constraints.
    """
    yield
    async with _test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


# ── HTTP client — routes use test DB via get_db override ─────────────────────
@pytest.fixture
async def client() -> AsyncClient:
    """
    AsyncClient connected to the FastAPI app.
    Overrides get_db so every route handler uses the test database.
    Clears dependency overrides after each test.
    """

    async def _test_get_db() -> AsyncSession:
        async with _TestSession() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _test_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Direct DB session — for test setup and assertions ────────────────────────
@pytest.fixture
async def db() -> AsyncSession:
    """
    Yields a committed AsyncSession for creating test data directly.
    Use this fixture in test setup; route handlers use their own sessions
    via the get_db override inside the `client` fixture.
    """
    async with _TestSession() as session:
        yield session
        await session.rollback()


# ── User factories ─────────────────────────────────────────────────────────────
@pytest.fixture
async def analyst_user(db: AsyncSession) -> User:
    """Create and persist a regular analyst user."""
    user = User(
        username="analyst_test",
        email="analyst@test.raventech.mx",
        hashed_password=hash_password("AnalystPass123!"),
        role="analyst",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def admin_user(db: AsyncSession) -> User:
    """Create and persist an admin user."""
    user = User(
        username="admin_test",
        email="admin@test.raventech.mx",
        hashed_password=hash_password("AdminPass123!"),
        role="admin",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def inactive_user(db: AsyncSession) -> User:
    """Create and persist a deactivated user — for auth rejection tests."""
    user = User(
        username="inactive_test",
        email="inactive@test.raventech.mx",
        hashed_password=hash_password("InactivePass123!"),
        role="analyst",
        is_active=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ── Auth header factories ──────────────────────────────────────────────────────
@pytest.fixture
def analyst_headers(analyst_user: User) -> dict[str, str]:
    """Bearer token headers for the analyst_user."""
    token = create_access_token(user_id=str(analyst_user.id), role="analyst")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(admin_user: User) -> dict[str, str]:
    """Bearer token headers for the admin_user."""
    token = create_access_token(user_id=str(admin_user.id), role="admin")
    return {"Authorization": f"Bearer {token}"}


# ── Investigation factory ──────────────────────────────────────────────────────
_VALID_AUTH_STATEMENT = (
    "Written authorization received from Acme Corp CISO on 2026-05-20. "
    "Reference: AUTH-2026-042. This assessment covers all public-facing "
    "infrastructure of acme.com and its subdomains as described in scope."
)  # 212 chars — well above the 100-char minimum


@pytest.fixture
async def test_investigation(db: AsyncSession, analyst_user: User) -> Investigation:
    """
    Create an investigation owned by analyst_user.
    Also creates the InvestigationMember row (owner role).
    """
    inv = Investigation(
        title="Test Investigation",
        owner_id=analyst_user.id,
        authorization_statement=_VALID_AUTH_STATEMENT,
        status="active",
    )
    db.add(inv)
    await db.flush()  # assigns inv.id without committing

    member = InvestigationMember(
        investigation_id=inv.id,
        user_id=analyst_user.id,
        role="owner",
    )
    db.add(member)
    await db.commit()
    await db.refresh(inv)
    return inv
```

- [ ] **Step 11.4 — Run a quick sanity check on the conftest**

```bash
cd backend
pytest tests/integration/api/test_admin.py -v
```

Expected: all 3 health-check tests still pass. If they fail now, the conftest has an import error. Read the traceback carefully — it points to the exact line.

- [ ] **Step 11.5 — Commit**

```bash
git add backend/pytest.ini backend/tests/conftest.py
git commit -m "test: add full test infrastructure (conftest, test DB, fixtures)"
```

**Common mistakes:**

- Using `scope="session"` for async fixtures without configuring `asyncio_default_fixture_loop_scope = "session"` in `pytest.ini` — session-scoped async fixtures and function-scoped async fixtures cannot share an event loop with default settings. Avoid by using `pytest_sessionstart` (sync) for table creation, as shown above.
- Not clearing `app.dependency_overrides` after each test — overrides leak between tests. Always call `app.dependency_overrides.clear()` in the fixture teardown (after `yield`).
- The `db` fixture and the `client` fixture use **separate** sessions by design. Do not pass `db` into `client` — routes need their own committed session to work correctly.
- Missing `import app.models` at the top — if models aren't imported, `Base.metadata.sorted_tables` is empty and `pytest_sessionstart` creates no tables.

---

## Task 12: Pydantic Schemas (`backend/app/schemas/`)

**Files:**
- Create: `backend/app/schemas/common.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/schemas/investigation.py`
- Create: `backend/app/schemas/target.py`

All schemas use Pydantic v2 syntax. `model_config = ConfigDict(from_attributes=True)` on response schemas enables construction from ORM objects.

---

- [ ] **Step 12.1 — Write `backend/app/schemas/common.py`**

```python
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    total: int
    items: list[T]


class ErrorResponse(BaseModel):
    detail: str
    code: str
    timestamp: str
```

- [ ] **Step 12.2 — Write `backend/app/schemas/auth.py`**

```python
from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class LoginRequest(BaseModel):
    username: str
    password: str


class UserBrief(BaseModel):
    """Minimal user info embedded in TokenResponse."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 1800  # seconds
    user: UserBrief


class AccessTokenResponse(BaseModel):
    """Returned by /auth/refresh — no user field."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 1800


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        errors = []
        if len(v) < 12:
            errors.append("at least 12 characters")
        if not any(c.isupper() for c in v):
            errors.append("one uppercase letter")
        if not any(c.islower() for c in v):
            errors.append("one lowercase letter")
        if not any(c.isdigit() for c in v):
            errors.append("one digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in v):
            errors.append("one special character")
        if errors:
            raise ValueError("Password requires: " + ", ".join(errors))
        return v
```

- [ ] **Step 12.3 — Write `backend/app/schemas/user.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "analyst"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("admin", "analyst"):
            raise ValueError("role must be 'admin' or 'analyst'")
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not (2 <= len(v) <= 50):
            raise ValueError("username must be 2–50 characters")
        return v.lower()


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    role: str | None = None
    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        if v is not None and v not in ("admin", "analyst"):
            raise ValueError("role must be 'admin' or 'analyst'")
        return v


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: datetime | None
```

- [ ] **Step 12.4 — Write `backend/app/schemas/investigation.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.user import UserResponse


class InvestigationCreate(BaseModel):
    title: str
    description: str | None = None
    authorization_statement: str
    scope_definition: str | None = None

    @field_validator("authorization_statement")
    @classmethod
    def validate_auth_statement(cls, v: str) -> str:
        if len(v.strip()) < 100:
            raise ValueError(
                "authorization_statement must be at least 100 characters. "
                "Document the legal basis for this investigation properly."
            )
        return v

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title cannot be blank")
        return v.strip()


class InvestigationUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    scope_definition: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        allowed = ("draft", "active", "completed", "archived")
        if v is not None and v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v


class MemberAdd(BaseModel):
    user_id: uuid.UUID
    role: str = "collaborator"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("owner", "collaborator"):
            raise ValueError("Investigation member role must be 'owner' or 'collaborator'")
        return v


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    role: str
    added_at: datetime


class InvestigationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    status: str
    owner_id: uuid.UUID
    authorization_statement: str
    scope_definition: str | None
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 12.5 — Write `backend/app/schemas/target.py`**

```python
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

_VALID_TARGET_TYPES = ("domain", "ip", "email", "username", "org", "url")


class TargetCreate(BaseModel):
    investigation_id: uuid.UUID
    target_type: str
    target_value: str
    label: str | None = None
    notes: str | None = None

    @field_validator("target_type")
    @classmethod
    def validate_target_type(cls, v: str) -> str:
        if v not in _VALID_TARGET_TYPES:
            raise ValueError(f"target_type must be one of {_VALID_TARGET_TYPES}")
        return v

    @field_validator("target_value")
    @classmethod
    def validate_target_value_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("target_value cannot be blank")
        return v.strip()


class TargetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    target_type: str
    target_value: str
    label: str | None
    notes: str | None
    created_by: uuid.UUID | None
    created_at: datetime
```

- [ ] **Step 12.6 — Verify all schemas import cleanly**

```bash
cd backend
python -c "
from app.schemas.common import PaginatedResponse, ErrorResponse
from app.schemas.auth import LoginRequest, TokenResponse, PasswordChangeRequest
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.schemas.investigation import InvestigationCreate, InvestigationResponse, MemberAdd
from app.schemas.target import TargetCreate, TargetResponse
print('All schemas import OK')
"
# Expected: All schemas import OK
```

- [ ] **Step 12.7 — Commit**

```bash
git add backend/app/schemas/
git commit -m "feat: add all Pydantic v2 I/O schemas"
```

**Common mistakes:**

- Using Pydantic v1 syntax (`class Config: orm_mode = True`) — Pydantic v2 uses `model_config = ConfigDict(from_attributes=True)`. `orm_mode` is gone.
- Putting `authorization_statement` length validation only in the Pydantic schema — it must also exist as a DB-level `CheckConstraint`. Both layers enforce the rule. Schema gives a clean 422 error; DB constraint is the last line of defense.
- Confusing `InvestigationMember.role` (`owner`|`collaborator`) with `User.role` (`admin`|`analyst`). The `MemberAdd.role` validator enforces `owner`|`collaborator`. Never put `analyst` or `admin` there.

---

## Task 13: Core Dependencies (`backend/app/core/dependencies.py`)

**Files:**
- Create: `backend/app/core/dependencies.py`

`get_current_user` checks the JWT **and** loads the user from DB on every request. This is intentional — a deactivated user's token is cryptographically valid but must be rejected at the DB check.

---

- [ ] **Step 13.1 — Write `backend/app/core/dependencies.py`**

```python
from __future__ import annotations

import uuid

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db as get_db  # explicit re-export — routes import from here
from app.models.user import User

# HTTPBearer extracts the token from "Authorization: Bearer <token>" header.
# auto_error=True means it raises 403 automatically if the header is missing.
_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decode and validate the Bearer JWT. Load the user from DB. Check is_active.

    Raises HTTP 401 for any failure:
    - Missing/malformed Authorization header
    - Expired token
    - Invalid signature
    - Token type is not 'access'
    - User not found in DB
    - User is deactivated

    Routes that require authentication use: current_user: User = Depends(get_current_user)
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise credentials_exception

    # Reject refresh tokens used as access tokens
    if payload.get("type") != "access":
        raise credentials_exception

    sub = payload.get("sub")
    if not sub:
        raise credentials_exception

    # Load from DB — not just from JWT — so deactivated users are caught immediately.
    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise credentials_exception

    user = await db.get(User, user_id)

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated. Contact an administrator.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_role(*roles: str):
    """
    Dependency factory. Returns a FastAPI dependency that raises 403
    if the authenticated user's platform role is not in `roles`.

    Usage in route:
        @router.get("/admin/stats")
        async def stats(user: User = Depends(require_role("admin"))):
            ...

    The returned function itself takes `current_user` as a Depends,
    so it also performs full authentication (token + DB check).
    """

    async def _check(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of these roles: {list(roles)}",
            )
        return current_user

    return _check


async def get_redis(request: Request):
    """
    FastAPI dependency — returns the Redis client from app.state.
    Created during application lifespan (see main.py).

    Usage in route:
        @router.post("/auth/logout")
        async def logout(redis=Depends(get_redis)):
            await redis.delete(f"rt:{jti}")
    """
    return request.app.state.redis
```

- [ ] **Step 13.2 — Write tests for `get_current_user`**

Create `backend/tests/unit/test_dependencies.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.models.user import User


def _make_user(*, role: str = "analyst", is_active: bool = True) -> User:
    """Build an unsaved User ORM object for use in mock returns."""
    user = User.__new__(User)
    user.id = uuid.uuid4()
    user.username = "testuser"
    user.email = "test@example.com"
    user.role = role
    user.is_active = is_active
    return user


async def _invoke_get_current_user(token: str, db_user: User | None):
    """Helper: call get_current_user with a mocked DB session."""
    from fastapi.security import HTTPAuthorizationCredentials
    from app.core.dependencies import get_current_user

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=db_user)

    return await get_current_user(credentials=credentials, db=mock_db)


async def test_get_current_user_returns_user_for_valid_token():
    user = _make_user()
    token = create_access_token(user_id=str(user.id), role="analyst")
    result = await _invoke_get_current_user(token, db_user=user)
    assert result is user


async def test_get_current_user_raises_401_for_expired_token():
    from fastapi import HTTPException

    expired = pyjwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
        },
        settings.APP_SECRET_KEY,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc_info:
        await _invoke_get_current_user(expired, db_user=_make_user())
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


async def test_get_current_user_raises_401_for_refresh_token():
    from fastapi import HTTPException

    token, _ = create_refresh_token(user_id=str(uuid.uuid4()))
    with pytest.raises(HTTPException) as exc_info:
        await _invoke_get_current_user(token, db_user=_make_user())
    assert exc_info.value.status_code == 401


async def test_get_current_user_raises_401_when_user_not_in_db():
    from fastapi import HTTPException

    token = create_access_token(user_id=str(uuid.uuid4()), role="analyst")
    with pytest.raises(HTTPException) as exc_info:
        await _invoke_get_current_user(token, db_user=None)
    assert exc_info.value.status_code == 401


async def test_get_current_user_raises_401_for_inactive_user():
    from fastapi import HTTPException

    user = _make_user(is_active=False)
    token = create_access_token(user_id=str(user.id), role="analyst")
    with pytest.raises(HTTPException) as exc_info:
        await _invoke_get_current_user(token, db_user=user)
    assert exc_info.value.status_code == 401
    assert "deactivated" in exc_info.value.detail.lower()
```

- [ ] **Step 13.3 — Run the unit tests**

```bash
pytest tests/unit/test_dependencies.py -v
```

Expected:
```
tests/unit/test_dependencies.py::test_get_current_user_returns_user_for_valid_token PASSED
tests/unit/test_dependencies.py::test_get_current_user_raises_401_for_expired_token PASSED
tests/unit/test_dependencies.py::test_get_current_user_raises_401_for_refresh_token PASSED
tests/unit/test_dependencies.py::test_get_current_user_raises_401_when_user_not_in_db PASSED
tests/unit/test_dependencies.py::test_get_current_user_raises_401_for_inactive_user PASSED

5 passed in X.Xs
```

- [ ] **Step 13.4 — Run the full unit test suite**

```bash
pytest tests/unit/ -v
```

All unit tests (security + dependencies) must pass before moving to auth routes.

- [ ] **Step 13.5 — Commit**

```bash
git add backend/app/core/dependencies.py backend/tests/unit/test_dependencies.py
git commit -m "feat: add get_current_user, require_role, get_redis dependencies with unit tests"
```

**Common mistakes:**

- Trusting JWT claims without the DB check — the JWT carries `role` and `sub`, but if a user is deactivated after login, their token is still cryptographically valid for up to 30 minutes. The `await db.get(User, user_id)` call catches this. Never skip it.
- Using `require_role("admin")` in a route signature directly without `Depends()` — `require_role("admin")` returns a coroutine **function**, not a coroutine. Routes must wrap it: `Depends(require_role("admin"))`.
- Accessing `request.app.state.redis` in `get_redis` before lifespan runs — in production this is always safe because lifespan raises on Redis failure. In standalone scripts or test environments that bypass lifespan, `app.state.redis` won't exist. The `client` fixture triggers lifespan automatically via `ASGITransport`.
- Importing `get_db` directly from `app.db.session` in route files — import it from `app.core.dependencies` instead. The dependency override in the test conftest patches `app.db.session.get_db`, and routes that import it as `from app.db.session import get_db` will NOT get the override. Always import through `app.core.dependencies`.

> **Note on the last mistake:** The `get_db` re-export in `dependencies.py` (`from app.db.session import get_db as get_db`) means the object identity is the same — FastAPI's dependency injection matches by object identity, not by name. Routes importing `get_db` from `app.core.dependencies` will use the same object that the test conftest overrides via `app.dependency_overrides[get_db] = ...`.

---

*PART1D COMPLETE — READY FOR PART1E*
