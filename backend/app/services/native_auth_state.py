"""PostgreSQL implementation of the small Redis auth-state interface.

Only hashed login keys and refresh-token JTIs are stored; never token bodies.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.db.session import AsyncSessionLocal
from app.models.background_job import NativeAuthState


class PostgresAuthState:
    async def setex(self, key: str, time: int, value: str) -> None:
        if not key.startswith(("rt:", "auth:failed:")) or len(key) > 180:
            raise ValueError("Unsupported native auth key")
        expires = datetime.now(UTC) + timedelta(seconds=time)
        async with AsyncSessionLocal() as db:
            await db.execute(delete(NativeAuthState).where(
                NativeAuthState.expires_at < datetime.now(UTC)
            ))
            statement = insert(NativeAuthState).values(
                key=key, value=value, expires_at=expires
            )
            await db.execute(
                statement.on_conflict_do_update(
                    index_elements=[NativeAuthState.key],
                    set_={"value": value, "expires_at": expires},
                )
            )
            await db.commit()

    async def get(self, key: str) -> str | None:
        async with AsyncSessionLocal() as db:
            return (
                await db.execute(
                    select(NativeAuthState.value).where(
                        NativeAuthState.key == key,
                        NativeAuthState.expires_at > datetime.now(UTC),
                    )
                )
            ).scalar_one_or_none()

    async def delete(self, key: str) -> int:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(NativeAuthState).where(NativeAuthState.key == key)
            )
            await db.commit()
            return int(cast(Any, result).rowcount or 0)

    async def ping(self) -> bool:
        async with AsyncSessionLocal() as db:
            await db.execute(select(NativeAuthState.key).limit(1))
        return True

    async def aclose(self) -> None:
        return None
