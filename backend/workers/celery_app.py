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
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        "visibility_timeout": 3600,
        "socket_keepalive": True,
    },
    enable_utc=True,
    result_serializer="json",
    task_acks_late=True,
    task_default_retry_delay=30,
    task_annotations={
        "*": {
            "max_retries": settings.CELERY_TASK_MAX_RETRIES,
            "retry_backoff": True,
            "retry_backoff_max": settings.CELERY_TASK_RETRY_BACKOFF_MAX_SECONDS,
            "retry_jitter": True,
        }
    },
    task_reject_on_worker_lost=True,
    task_serializer="json",
    task_time_limit=900,
    task_soft_time_limit=840,
    task_track_started=True,
    timezone="UTC",
    worker_cancel_long_running_tasks_on_connection_loss=True,
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
    worker_max_tasks_per_child=100,
    worker_pool="prefork",
    worker_prefetch_multiplier=1,
)
