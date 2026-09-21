from __future__ import annotations

import pytest
from app.services import native_auth_state
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.mark.asyncio
async def test_native_auth_state_uses_postgres_without_redis(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert db.bind is not None
    monkeypatch.setattr(
        native_auth_state, "AsyncSessionLocal",
        async_sessionmaker(db.bind, expire_on_commit=False),
    )
    store = native_auth_state.PostgresAuthState()
    await store.setex("rt:safe-jti", 30, "user-id")
    assert await store.get("rt:safe-jti") == "user-id"
    assert await store.ping() is True
    assert await store.delete("rt:safe-jti") == 1
    assert await store.get("rt:safe-jti") is None
    with pytest.raises(ValueError):
        await store.setex("secret:key", 30, "never stored")
