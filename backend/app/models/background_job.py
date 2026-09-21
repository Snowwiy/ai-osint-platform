from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BackgroundJob(Base):
    __tablename__ = "background_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','scheduled','running','completed','failed',"
            "'retry_wait','cancel_requested','cancelled')",
            name="ck_background_jobs_status",
        ),
        CheckConstraint(
            "priority BETWEEN 0 AND 100", name="ck_background_jobs_priority"
        ),
        CheckConstraint(
            "progress BETWEEN 0 AND 100", name="ck_background_jobs_progress"
        ),
        CheckConstraint(
            "attempt_count >= 0 AND max_attempts BETWEEN 1 AND 11",
            name="ck_background_jobs_attempts",
        ),
        Index("idx_background_jobs_claim", "status", "priority", "scheduled_at"),
        Index("idx_background_jobs_requested", "requested_by_user_id", "created_at"),
        Index(
            "uq_background_jobs_active_dedupe",
            "dedupe_key",
            unique=True,
            postgresql_where=text(
                "dedupe_key IS NOT NULL AND status IN "
                "('queued','scheduled','running','retry_wait','cancel_requested')"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    job_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="queued"
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="50")
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    result_summary: Mapped[str | None] = mapped_column(String(255))
    progress: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="4"
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(40))
    last_error_summary: Mapped[str | None] = mapped_column(String(255))
    dedupe_key: Mapped[str | None] = mapped_column(String(160))
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    investigation_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("investigations.id", ondelete="SET NULL")
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("lan_assets.id", ondelete="SET NULL")
    )
    worker_id: Mapped[str | None] = mapped_column(String(100))
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class BackgroundJobEvent(Base):
    __tablename__ = "background_job_events"
    __table_args__ = (
        Index("idx_background_job_events_job_time", "job_id", "occurred_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("background_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    worker_id: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[str] = mapped_column(String(255), nullable=False)


class NativeWorkerHeartbeat(Base):
    __tablename__ = "native_worker_heartbeats"
    worker_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    heartbeat_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    stopping: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )


class NativeAuthState(Base):
    __tablename__ = "native_auth_state"
    __table_args__ = (Index("idx_native_auth_state_expires", "expires_at"),)
    key: Mapped[str] = mapped_column(String(180), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
