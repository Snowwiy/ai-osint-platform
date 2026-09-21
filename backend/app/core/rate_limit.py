from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    # Auth throttling is PostgreSQL-backed in native mode. SlowAPI has no
    # decorated routes today; keep its optional store off Redis for desktop.
    storage_uri=(
        "memory://" if settings.background_engine == "native" else settings.REDIS_URL
    ),
)
