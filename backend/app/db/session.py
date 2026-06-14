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
    echo=settings.debug_enabled,
    connect_args={
        "server_settings": {
            "statement_timeout": str(settings.DATABASE_STATEMENT_TIMEOUT_MS),
        },
    },
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=10,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
