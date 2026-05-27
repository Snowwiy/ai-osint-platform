from __future__ import annotations

from typing import Any

import app.models  # noqa: F401
import pytest
from app.core.config import settings
from app.core.dependencies import get_db, get_redis
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.base import Base
from app.models.investigation import Investigation
from app.models.investigation_member import InvestigationMember
from app.models.user import User
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_PASSWORD = "TestPassword123!"
VALID_AUTH_STATEMENT = (
    "Written authorization received from Acme Corp CISO on 2026-05-20. "
    "Reference: AUTH-2026-042. This assessment covers all public-facing "
    "infrastructure of acme.com and its subdomains as described in scope."
)

_ASYNC_TEST_URL = settings.async_test_database_url
_SYNC_TEST_URL = settings.sync_test_database_url
_test_engine = create_async_engine(_ASYNC_TEST_URL, echo=False, poolclass=NullPool)
_TestSession = async_sessionmaker(
    _test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
_db_prepared = False


class FakeRedis:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def ping(self) -> bool:
        return True

    async def setex(self, key: str, _ttl: int, value: str) -> None:
        self._data[key] = value

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def delete(self, key: str) -> int:
        existed = key in self._data
        self._data.pop(key, None)
        return int(existed)

    async def aclose(self) -> None:
        self._data.clear()


def _prepare_database() -> None:
    global _db_prepared
    if _db_prepared:
        return
    _ensure_database_exists(_SYNC_TEST_URL)
    sync_engine = create_engine(_SYNC_TEST_URL)
    with sync_engine.begin() as connection:
        connection.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
        connection.execute(text('CREATE EXTENSION IF NOT EXISTS "pg_trgm"'))
        Base.metadata.create_all(connection)
    sync_engine.dispose()
    _db_prepared = True


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if not _db_prepared:
        return
    sync_engine = create_engine(_SYNC_TEST_URL)
    Base.metadata.drop_all(sync_engine)
    sync_engine.dispose()


def _ensure_database_exists(sync_url: str) -> None:
    url = make_url(sync_url)
    database = url.database
    if not database:
        return
    maintenance_url = url.set(database="postgres")
    engine = create_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    escaped_database = database.replace('"', '""')
    try:
        with engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": database},
            ).scalar_one_or_none()
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{escaped_database}"'))
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
async def clean_db() -> None:
    yield
    if not _db_prepared:
        return
    async with _test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest.fixture
async def fake_redis() -> FakeRedis:
    redis = FakeRedis()
    app.state.redis = redis
    return redis


@pytest.fixture
async def client(fake_redis: FakeRedis) -> AsyncClient:
    _prepare_database()

    async def _test_get_db() -> Any:
        async with _TestSession() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def _test_get_redis() -> FakeRedis:
        return fake_redis

    app.dependency_overrides[get_db] = _test_get_db
    app.dependency_overrides[get_redis] = _test_get_redis

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def db() -> AsyncSession:
    _prepare_database()
    async with _TestSession() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def analyst_user(db: AsyncSession) -> User:
    user = User(
        username="analyst_test",
        email="analyst@test.raventech.mx",
        hashed_password=hash_password(TEST_PASSWORD),
        role="analyst",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def admin_user(db: AsyncSession) -> User:
    user = User(
        username="admin_test",
        email="admin@test.raventech.mx",
        hashed_password=hash_password(TEST_PASSWORD),
        role="admin",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def inactive_user(db: AsyncSession) -> User:
    user = User(
        username="inactive_test",
        email="inactive@test.raventech.mx",
        hashed_password=hash_password(TEST_PASSWORD),
        role="analyst",
        is_active=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def analyst_headers(analyst_user: User) -> dict[str, str]:
    token = create_access_token(user_id=str(analyst_user.id), role=analyst_user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_headers(admin_user: User) -> dict[str, str]:
    token = create_access_token(user_id=str(admin_user.id), role=admin_user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def test_investigation(
    db: AsyncSession,
    analyst_user: User,
) -> Investigation:
    investigation = Investigation(
        title="Test Investigation",
        owner_id=analyst_user.id,
        authorization_statement=VALID_AUTH_STATEMENT,
        status="active",
    )
    db.add(investigation)
    await db.flush()
    db.add(
        InvestigationMember(
            investigation_id=investigation.id,
            user_id=analyst_user.id,
            role="owner",
        )
    )
    await db.commit()
    await db.refresh(investigation)
    return investigation


@pytest.fixture
async def other_user(db: AsyncSession) -> User:
    user = User(
        username="other_test",
        email="other@test.raventech.mx",
        hashed_password=hash_password(TEST_PASSWORD),
        role="analyst",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
