from __future__ import annotations

from importlib import import_module
from typing import Any

from app.core.config import settings

Celery: Any = import_module("celery").Celery

celery_app = Celery(
    "raventech",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["workers.tasks"],
)

celery_app.conf.update(
    accept_content=["json"],
    enable_utc=True,
    result_serializer="json",
    task_acks_late=True,
    task_serializer="json",
    task_track_started=True,
    timezone="UTC",
    worker_concurrency=2,
    worker_pool="prefork",
    worker_prefetch_multiplier=1,
)
