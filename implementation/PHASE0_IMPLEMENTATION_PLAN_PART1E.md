# PHASE 0 IMPLEMENTATION PLAN — PART 1E
# Tasks 14–17: Auth Endpoints · Admin Bootstrap · Investigations CRUD · Membership Logic

---

## TASK 14 — Auth Service + Auth Endpoints

### Files Created
- `app/services/auth.py`
- `app/schemas/auth.py` (complete)
- `app/api/v1/auth.py`

### 14.1 — app/services/auth.py

**Rule:** Business logic only — no HTTP concepts. All functions receive `db` and `redis` as explicit args. Never call `await db.commit()` inside a service; `get_db` commits on yield exit.

```python
# app/services/auth.py
from __future__ import annotations
import uuid
from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.security import (
    create_access_token, create_refresh_token,
    decode_token, verify_password, hash_password,
)
from app.models.user import User

_REFRESH_TTL = int(timedelta(days=7).total_seconds())


class AuthError(Exception):
    """Base for all auth service errors."""


class InvalidCredentialsError(AuthError):
    pass


class InactiveUserError(AuthError):
    pass


class TokenError(AuthError):
    pass


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Invalid credentials")
    if not user.is_active:
        raise InactiveUserError("Account disabled")
    return user


async def login(db: AsyncSession, redis, email: str, password: str) -> dict[str, str]:
    user = await authenticate_user(db, email, password)
    access_token = create_access_token(str(user.id), user.role)
    refresh_token, jti = create_refresh_token(str(user.id))
    # Store JTI in Redis — key: rt:{jti}, TTL: 7 days
    await redis.setex(f"rt:{jti}", _REFRESH_TTL, str(user.id))
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


async def refresh_access_token(
    db: AsyncSession, redis, refresh_token: str
) -> dict[str, str]:
    try:
        payload = decode_token(refresh_token)
    except Exception:
        raise TokenError("Invalid token")
    if payload.get("type") != "refresh":
        raise TokenError("Not a refresh token")
    jti = payload["jti"]
    user_id = payload["sub"]
    stored = await redis.get(f"rt:{jti}")
    if not stored:
        raise TokenError("Token revoked or expired")
    user = await db.get(User, uuid.UUID(user_id))
    if not user or not user.is_active:
        raise TokenError("User unavailable")
    # Rotate — delete old JTI, issue new pair
    await redis.delete(f"rt:{jti}")
    new_access = create_access_token(str(user.id), user.role)
    new_refresh, new_jti = create_refresh_token(str(user.id))
    await redis.setex(f"rt:{new_jti}", _REFRESH_TTL, str(user.id))
    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


async def logout(redis, refresh_token: str) -> None:
    """Always succeeds — silently ignores invalid or already-expired tokens."""
    try:
        payload = decode_token(refresh_token)
        jti = payload.get("jti")
        if jti:
            await redis.delete(f"rt:{jti}")
    except Exception:
        pass  # Token invalid or already expired — treat as logged out


async def change_password(
    db: AsyncSession, user: User, current_password: str, new_password: str
) -> None:
    if not verify_password(current_password, user.hashed_password):
        raise InvalidCredentialsError("Current password is incorrect")
    user.hashed_password = hash_password(new_password)
    db.add(user)
    # Caller's get_db commits
```

### 14.2 — app/schemas/auth.py (complete)

```python
# app/schemas/auth.py
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LogoutRequest(BaseModel):
    refresh_token: str
```

### 14.3 — app/api/v1/auth.py

```python
# app/api/v1/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_current_user, get_db, get_redis
from app.models.user import User
from app.schemas.auth import (
    LoginRequest, LoginResponse, LogoutRequest,
    RefreshRequest, TokenResponse,
)
from app.schemas.common import PasswordChangeRequest
from app.schemas.user import UserResponse
from app.services.auth import (
    InvalidCredentialsError, InactiveUserError, TokenError,
    change_password, login, logout, refresh_access_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse, status_code=200)
async def login_endpoint(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    try:
        return await login(db, redis, body.email, body.password)
    except InactiveUserError:
        raise HTTPException(status_code=403, detail="Account disabled")
    except InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/refresh", response_model=TokenResponse, status_code=200)
async def refresh_endpoint(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    try:
        return await refresh_access_token(db, redis, body.refresh_token)
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.post("/logout", status_code=204)
async def logout_endpoint(
    body: LogoutRequest,
    redis=Depends(get_redis),
):
    await logout(redis, body.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me_endpoint(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/me/password", status_code=204)
async def change_password_endpoint(
    body: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await change_password(db, current_user, body.current_password, body.new_password)
    except InvalidCredentialsError:
        raise HTTPException(status_code=400, detail="Current password is incorrect")
```

### 14.4 — Register Router

Inside `create_app()` in `main.py`, add alongside other router registrations:

```python
from app.api.v1.auth import router as auth_router
api_router.include_router(auth_router)
```

---

## TASK 15 — Admin Bootstrap Script

### File Created
- `scripts/create_admin.py`

```python
# scripts/create_admin.py
"""
Bootstrap the first admin user.

Usage (non-interactive):
  ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=Secure123! python scripts/create_admin.py

Usage (interactive — prompts if env vars absent):
  python scripts/create_admin.py
"""
from __future__ import annotations
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User


async def main() -> None:
    email = os.environ.get("ADMIN_EMAIL") or input("Admin email: ").strip()
    password = os.environ.get("ADMIN_PASSWORD") or input("Admin password: ").strip()

    if len(password) < 12:
        print("ERROR: Password must be at least 12 characters.", file=sys.stderr)
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()

        if existing:
            if existing.role == "admin":
                print(f"Admin already exists: {email}")
            else:
                existing.role = "admin"
                await db.commit()
                print(f"Promoted existing user to admin: {email}")
            return

        user = User(
            email=email,
            hashed_password=hash_password(password),
            role="admin",
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        print(f"Admin created: {email}  id={user.id}")


if __name__ == "__main__":
    asyncio.run(main())
```

**DoD:** Running the script twice with the same email prints "already exists" on the second run. Running with `password` < 12 chars exits 1.

---

## TASK 16 — Investigation Service + CRUD Endpoints

### Files Created
- `app/services/investigation.py`
- `app/api/v1/investigations.py`

### 16.1 — app/services/investigation.py (CRUD portion)

```python
# app/services/investigation.py
from __future__ import annotations
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.investigation import Investigation, InvestigationStatus
from app.models.investigation_member import InvestigationMember, MemberRole
from app.models.user import User
from app.schemas.investigation import InvestigationCreate, InvestigationUpdate


class InvestigationNotFoundError(Exception):
    pass


class ForbiddenError(Exception):
    pass


class MemberAlreadyExistsError(Exception):
    pass


class LastOwnerError(Exception):
    pass


async def _get_membership(
    db: AsyncSession, investigation_id: uuid.UUID, user_id: uuid.UUID
) -> InvestigationMember | None:
    """Return the InvestigationMember row or None. Does not raise."""
    result = await db.execute(
        select(InvestigationMember).where(
            InvestigationMember.investigation_id == investigation_id,
            InvestigationMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def create_investigation(
    db: AsyncSession, user: User, data: InvestigationCreate
) -> Investigation:
    investigation = Investigation(
        title=data.title,
        description=data.description,
        authorization_statement=data.authorization_statement,
        status=InvestigationStatus.draft,
        created_by=user.id,
    )
    db.add(investigation)
    # flush() assigns the server-default UUID without committing
    await db.flush()
    member = InvestigationMember(
        investigation_id=investigation.id,
        user_id=user.id,
        role=MemberRole.owner,
    )
    db.add(member)
    return investigation


async def list_investigations(
    db: AsyncSession, user: User, skip: int = 0, limit: int = 20
) -> list[Investigation]:
    if user.role == "admin":
        q = select(Investigation).offset(skip).limit(limit)
    else:
        q = (
            select(Investigation)
            .join(
                InvestigationMember,
                Investigation.id == InvestigationMember.investigation_id,
            )
            .where(InvestigationMember.user_id == user.id)
            .offset(skip)
            .limit(limit)
        )
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_investigation(
    db: AsyncSession, user: User, investigation_id: uuid.UUID
) -> Investigation:
    investigation = await db.get(Investigation, investigation_id)
    if not investigation:
        raise InvestigationNotFoundError
    if user.role != "admin":
        membership = await _get_membership(db, investigation_id, user.id)
        if not membership:
            # Return NotFound — never reveal the investigation exists to non-members
            raise InvestigationNotFoundError
    return investigation


async def update_investigation(
    db: AsyncSession, user: User, investigation_id: uuid.UUID, data: InvestigationUpdate
) -> Investigation:
    investigation = await get_investigation(db, user, investigation_id)
    if user.role != "admin":
        membership = await _get_membership(db, investigation_id, user.id)
        if not membership or membership.role != MemberRole.owner:
            raise ForbiddenError("Only owners can update investigations")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(investigation, field, value)
    db.add(investigation)
    return investigation


async def delete_investigation(
    db: AsyncSession, user: User, investigation_id: uuid.UUID
) -> None:
    investigation = await get_investigation(db, user, investigation_id)
    if user.role != "admin":
        membership = await _get_membership(db, investigation_id, user.id)
        if not membership or membership.role != MemberRole.owner:
            raise ForbiddenError("Only owners can delete investigations")
    await db.delete(investigation)
```

### 16.2 — app/api/v1/investigations.py (CRUD portion)

```python
# app/api/v1/investigations.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.investigation import (
    InvestigationCreate, InvestigationListResponse,
    InvestigationResponse, InvestigationUpdate,
)
from app.services.investigation import (
    ForbiddenError, InvestigationNotFoundError,
    create_investigation, delete_investigation,
    get_investigation, list_investigations, update_investigation,
)

router = APIRouter(prefix="/investigations", tags=["investigations"])


@router.post("/", response_model=InvestigationResponse, status_code=201)
async def create(
    body: InvestigationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await create_investigation(db, current_user, body)


@router.get("/", response_model=InvestigationListResponse)
async def list_all(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items = await list_investigations(db, current_user, skip=skip, limit=limit)
    return {"items": items, "total": len(items)}


@router.get("/{investigation_id}", response_model=InvestigationResponse)
async def get_one(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_investigation(db, current_user, investigation_id)
    except InvestigationNotFoundError:
        raise HTTPException(status_code=404, detail="Investigation not found")


@router.put("/{investigation_id}", response_model=InvestigationResponse)
async def update(
    investigation_id: uuid.UUID,
    body: InvestigationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await update_investigation(db, current_user, investigation_id, body)
    except InvestigationNotFoundError:
        raise HTTPException(status_code=404, detail="Investigation not found")
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.delete("/{investigation_id}", status_code=204)
async def delete(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await delete_investigation(db, current_user, investigation_id)
    except InvestigationNotFoundError:
        raise HTTPException(status_code=404, detail="Investigation not found")
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
```

### 16.3 — Required Schema Additions (schemas/investigation.py)

```python
class InvestigationUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None

class InvestigationListResponse(BaseModel):
    items: list[InvestigationResponse]
    total: int
```

### 16.4 — Register Router

Inside `create_app()` in `main.py`:

```python
from app.api.v1.investigations import router as investigations_router
api_router.include_router(investigations_router)
```

---

## TASK 17 — Investigation Membership Logic

### 17.1 — Addition to app/services/investigation.py

Append after the CRUD functions above:

```python
async def list_members(
    db: AsyncSession, user: User, investigation_id: uuid.UUID
) -> list[InvestigationMember]:
    await get_investigation(db, user, investigation_id)  # Enforces access check
    result = await db.execute(
        select(InvestigationMember).where(
            InvestigationMember.investigation_id == investigation_id
        )
    )
    return list(result.scalars().all())


async def add_member(
    db: AsyncSession,
    requesting_user: User,
    investigation_id: uuid.UUID,
    target_user_id: uuid.UUID,
    role: str,
) -> InvestigationMember:
    await get_investigation(db, requesting_user, investigation_id)
    if requesting_user.role != "admin":
        membership = await _get_membership(db, investigation_id, requesting_user.id)
        if not membership or membership.role != MemberRole.owner:
            raise ForbiddenError("Only owners can add members")
    existing = await _get_membership(db, investigation_id, target_user_id)
    if existing:
        raise MemberAlreadyExistsError("User is already a member")
    new_member = InvestigationMember(
        investigation_id=investigation_id,
        user_id=target_user_id,
        role=MemberRole(role),
    )
    db.add(new_member)
    return new_member


async def update_member_role(
    db: AsyncSession,
    requesting_user: User,
    investigation_id: uuid.UUID,
    target_user_id: uuid.UUID,
    role: str,
) -> InvestigationMember:
    await get_investigation(db, requesting_user, investigation_id)
    if requesting_user.role != "admin":
        membership = await _get_membership(db, investigation_id, requesting_user.id)
        if not membership or membership.role != MemberRole.owner:
            raise ForbiddenError("Only owners can change member roles")
    member = await _get_membership(db, investigation_id, target_user_id)
    if not member:
        raise InvestigationNotFoundError("Member not found")
    # Prevent demoting the last owner
    if member.role == MemberRole.owner and MemberRole(role) != MemberRole.owner:
        count_result = await db.execute(
            select(InvestigationMember).where(
                InvestigationMember.investigation_id == investigation_id,
                InvestigationMember.role == MemberRole.owner,
            )
        )
        if len(count_result.scalars().all()) <= 1:
            raise LastOwnerError("Cannot demote the last owner")
    member.role = MemberRole(role)
    db.add(member)
    return member


async def remove_member(
    db: AsyncSession,
    requesting_user: User,
    investigation_id: uuid.UUID,
    target_user_id: uuid.UUID,
) -> None:
    await get_investigation(db, requesting_user, investigation_id)
    if requesting_user.role != "admin":
        membership = await _get_membership(db, investigation_id, requesting_user.id)
        if not membership or membership.role != MemberRole.owner:
            raise ForbiddenError("Only owners can remove members")
    member = await _get_membership(db, investigation_id, target_user_id)
    if not member:
        raise InvestigationNotFoundError("Member not found")
    if member.role == MemberRole.owner:
        count_result = await db.execute(
            select(InvestigationMember).where(
                InvestigationMember.investigation_id == investigation_id,
                InvestigationMember.role == MemberRole.owner,
            )
        )
        if len(count_result.scalars().all()) <= 1:
            raise LastOwnerError("Cannot remove the last owner")
    await db.delete(member)
```

### 17.2 — Membership Endpoints (append to app/api/v1/investigations.py)

Add these imports at the top of `investigations.py`:

```python
from app.schemas.investigation import MemberAddRequest, MemberResponse, MemberUpdateRequest
from app.services.investigation import (
    LastOwnerError, MemberAlreadyExistsError,
    add_member, list_members, remove_member, update_member_role,
)
```

Then append routes:

```python
@router.get("/{investigation_id}/members", response_model=list[MemberResponse])
async def get_members(
    investigation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await list_members(db, current_user, investigation_id)
    except InvestigationNotFoundError:
        raise HTTPException(status_code=404, detail="Investigation not found")


@router.post("/{investigation_id}/members", response_model=MemberResponse, status_code=201)
async def add_member_endpoint(
    investigation_id: uuid.UUID,
    body: MemberAddRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await add_member(db, current_user, investigation_id, body.user_id, body.role)
    except InvestigationNotFoundError:
        raise HTTPException(status_code=404, detail="Investigation not found")
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except MemberAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.put("/{investigation_id}/members/{user_id}", response_model=MemberResponse)
async def update_member_endpoint(
    investigation_id: uuid.UUID,
    user_id: uuid.UUID,
    body: MemberUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await update_member_role(db, current_user, investigation_id, user_id, body.role)
    except InvestigationNotFoundError:
        raise HTTPException(status_code=404, detail="Not found")
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except LastOwnerError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.delete("/{investigation_id}/members/{user_id}", status_code=204)
async def remove_member_endpoint(
    investigation_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await remove_member(db, current_user, investigation_id, user_id)
    except InvestigationNotFoundError:
        raise HTTPException(status_code=404, detail="Not found")
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except LastOwnerError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
```

### 17.3 — Required Schema Additions (schemas/investigation.py)

```python
import uuid
from pydantic import field_validator

class MemberAddRequest(BaseModel):
    user_id: uuid.UUID
    role: str

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v: str) -> str:
        if v not in ("owner", "collaborator"):
            raise ValueError("role must be 'owner' or 'collaborator'")
        return v

class MemberUpdateRequest(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v: str) -> str:
        if v not in ("owner", "collaborator"):
            raise ValueError("role must be 'owner' or 'collaborator'")
        return v

class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    investigation_id: uuid.UUID
    user_id: uuid.UUID
    role: str
```

---

## REQUIRED TESTS — Tasks 14–17

### tests/test_auth.py

```python
# tests/test_auth.py
import pytest
from httpx import AsyncClient

_PASSWORD = "TestPassword123!"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, analyst_user):
    resp = await client.post("/api/v1/auth/login", json={
        "email": analyst_user.email, "password": _PASSWORD,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, analyst_user):
    resp = await client.post("/api/v1/auth/login", json={
        "email": analyst_user.email, "password": "WrongPassword999!",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient, inactive_user):
    resp = await client.post("/api/v1/auth/login", json={
        "email": inactive_user.email, "password": _PASSWORD,
    })
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_refresh_rotates_token(client: AsyncClient, analyst_user):
    login = await client.post("/api/v1/auth/login", json={
        "email": analyst_user.email, "password": _PASSWORD,
    })
    old_refresh = login.json()["refresh_token"]
    # First refresh succeeds
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 200
    # Old token is now revoked
    resp2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client: AsyncClient, analyst_user):
    login = await client.post("/api/v1/auth/login", json={
        "email": analyst_user.email, "password": _PASSWORD,
    })
    refresh_token = login.json()["refresh_token"]
    await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(client: AsyncClient, analyst_headers, analyst_user):
    resp = await client.get("/api/v1/auth/me", headers=analyst_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == analyst_user.email
    assert "hashed_password" not in resp.json()


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 403  # HTTPBearer raises 403 when no credentials
```

### tests/test_investigations.py

```python
# tests/test_investigations.py
import pytest
from httpx import AsyncClient

_VALID_AUTH = "A" * 100  # Exactly 100 chars — meets minimum


@pytest.mark.asyncio
async def test_create_investigation_success(client: AsyncClient, analyst_headers):
    resp = await client.post("/api/v1/investigations/", json={
        "title": "Test Investigation",
        "description": "For testing",
        "authorization_statement": _VALID_AUTH,
    }, headers=analyst_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test Investigation"
    assert data["status"] == "draft"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_rejects_short_auth_statement(client: AsyncClient, analyst_headers):
    resp = await client.post("/api/v1/investigations/", json={
        "title": "Test",
        "description": "Test",
        "authorization_statement": "too short",
    }, headers=analyst_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_creator_is_automatically_owner(client: AsyncClient, analyst_headers):
    inv = await client.post("/api/v1/investigations/", json={
        "title": "Ownership Test",
        "description": "Test",
        "authorization_statement": _VALID_AUTH,
    }, headers=analyst_headers)
    inv_id = inv.json()["id"]
    members = await client.get(
        f"/api/v1/investigations/{inv_id}/members", headers=analyst_headers
    )
    assert members.status_code == 200
    assert any(m["role"] == "owner" for m in members.json())


@pytest.mark.asyncio
async def test_analyst_cannot_see_others_investigations(
    client: AsyncClient, analyst_headers, admin_headers
):
    # Admin creates investigation; analyst is not a member
    await client.post("/api/v1/investigations/", json={
        "title": "Admin Only Investigation",
        "description": "Not for analyst",
        "authorization_statement": _VALID_AUTH,
    }, headers=admin_headers)
    resp = await client.get("/api/v1/investigations/", headers=analyst_headers)
    titles = [i["title"] for i in resp.json()["items"]]
    assert "Admin Only Investigation" not in titles


@pytest.mark.asyncio
async def test_admin_sees_all_investigations(
    client: AsyncClient, analyst_headers, admin_headers
):
    await client.post("/api/v1/investigations/", json={
        "title": "Analyst Investigation",
        "description": "Analyst owns this",
        "authorization_statement": _VALID_AUTH,
    }, headers=analyst_headers)
    resp = await client.get("/api/v1/investigations/", headers=admin_headers)
    titles = [i["title"] for i in resp.json()["items"]]
    assert "Analyst Investigation" in titles


@pytest.mark.asyncio
async def test_get_investigation_returns_404_for_non_member(
    client: AsyncClient, analyst_headers, admin_headers
):
    inv = await client.post("/api/v1/investigations/", json={
        "title": "Private",
        "description": "Admin only",
        "authorization_statement": _VALID_AUTH,
    }, headers=admin_headers)
    inv_id = inv.json()["id"]
    resp = await client.get(f"/api/v1/investigations/{inv_id}", headers=analyst_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_member_as_owner(client: AsyncClient, analyst_headers, admin_user):
    inv = await client.post("/api/v1/investigations/", json={
        "title": "Membership Test",
        "description": "Test",
        "authorization_statement": _VALID_AUTH,
    }, headers=analyst_headers)
    inv_id = inv.json()["id"]
    resp = await client.post(
        f"/api/v1/investigations/{inv_id}/members",
        json={"user_id": str(admin_user.id), "role": "collaborator"},
        headers=analyst_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "collaborator"


@pytest.mark.asyncio
async def test_add_duplicate_member_returns_409(
    client: AsyncClient, analyst_headers, admin_user
):
    inv = await client.post("/api/v1/investigations/", json={
        "title": "Dupe Member Test",
        "description": "Test",
        "authorization_statement": _VALID_AUTH,
    }, headers=analyst_headers)
    inv_id = inv.json()["id"]
    payload = {"user_id": str(admin_user.id), "role": "collaborator"}
    await client.post(f"/api/v1/investigations/{inv_id}/members", json=payload, headers=analyst_headers)
    resp = await client.post(f"/api/v1/investigations/{inv_id}/members", json=payload, headers=analyst_headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_cannot_remove_last_owner(client: AsyncClient, analyst_headers, analyst_user):
    inv = await client.post("/api/v1/investigations/", json={
        "title": "Last Owner Test",
        "description": "Test",
        "authorization_statement": _VALID_AUTH,
    }, headers=analyst_headers)
    inv_id = inv.json()["id"]
    resp = await client.delete(
        f"/api/v1/investigations/{inv_id}/members/{analyst_user.id}",
        headers=analyst_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_invalid_member_role_returns_422(client: AsyncClient, analyst_headers, admin_user):
    inv = await client.post("/api/v1/investigations/", json={
        "title": "Invalid Role Test",
        "description": "Test",
        "authorization_statement": _VALID_AUTH,
    }, headers=analyst_headers)
    inv_id = inv.json()["id"]
    resp = await client.post(
        f"/api/v1/investigations/{inv_id}/members",
        json={"user_id": str(admin_user.id), "role": "analyst"},  # invalid — must be owner|collaborator
        headers=analyst_headers,
    )
    assert resp.status_code == 422
```

---

## VERIFICATION STEPS

Run in order after all Task 14–17 files are in place:

```bash
# 1. Confirm migrations are applied (tables must exist)
make migrate

# 2. Lint + type-check
make lint

# 3. Bootstrap admin and confirm idempotent
ADMIN_EMAIL=admin@test.com ADMIN_PASSWORD=Admin12345! python scripts/create_admin.py
ADMIN_EMAIL=admin@test.com ADMIN_PASSWORD=Admin12345! python scripts/create_admin.py  # must print "already exists"

# 4. Run targeted test suites
pytest tests/test_auth.py tests/test_investigations.py -v

# 5. Full suite must pass green
make test

# 6. Optional manual smoke (requires: make dev running)
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"Admin12345!"}' | python -m json.tool
```

**DoD Checklist:**
- [ ] `POST /auth/login` → 200 with `access_token` + `refresh_token`
- [ ] `POST /auth/refresh` rotates tokens; same old refresh token → 401 on second use
- [ ] `POST /auth/logout` + old refresh token → 401 on next refresh attempt
- [ ] `GET /auth/me` returns user object without `hashed_password` field
- [ ] `POST /investigations/` with `authorization_statement` < 100 chars → 422
- [ ] Creator automatically appears in `/members` list with `role = "owner"`
- [ ] Analyst cannot see or GET investigations they are not members of → 404
- [ ] `DELETE /members/{user_id}` when only one owner remains → 409
- [ ] `POST /members` with `role = "analyst"` (invalid) → 422
- [ ] `make test` exits 0 with no failures

---

## COMMON MISTAKES

| Mistake | Fix |
|---|---|
| Calling `await db.commit()` inside a service function | Never — `get_db` commits on yield exit. Services only call `db.add()`, `db.flush()`, `db.delete()`. |
| Forgetting `await db.flush()` before using `investigation.id` in `create_investigation` | `flush()` triggers `RETURNING id` from PostgreSQL server default; id is populated after it. |
| Using access token as refresh token input to `/refresh` | `refresh_access_token()` checks `payload["type"] == "refresh"`; access tokens are rejected with 401. |
| `logout()` raising on invalid token | Must silently `pass` — client may send a bad or already-expired token; always return 204. |
| Returning 403 when a non-member accesses an investigation | Always return 404 — never confirm the investigation exists to unauthorized callers. |
| Confusing platform role (`user.role`) with investigation role (`member.role`) | `user.role` ∈ `("admin", "analyst")`. `member.role` ∈ `("owner", "collaborator")`. Platform role controls visibility; investigation role controls write/delete. |
| Not checking `_get_membership` before checking `membership.role` | `_get_membership` returns `None` if not a member. Always guard: `if not membership or membership.role != MemberRole.owner`. |
| Registering a new router but forgetting `api_router.include_router(...)` in `main.py` | Every new `APIRouter` must be registered inside `create_app()`. Confirm with `GET /openapi.json`. |
| Schema validator using Pydantic v1 `@validator` instead of v2 `@field_validator` | Must use `@field_validator("field_name")` + `@classmethod` in Pydantic v2. |

---

*PART1E COMPLETE — READY FOR PART1F*
