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
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AiModelPreference(Base):
    __tablename__ = "ai_model_preferences"
    __table_args__ = (
        CheckConstraint(
            "execution_mode IN ('free_only', 'local_only', 'any_configured')",
            name="ck_ai_model_preferences_execution_mode",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    selected_model_id: Mapped[str | None] = mapped_column(String(300))
    preferred_local_model_id: Mapped[str | None] = mapped_column(String(300))
    preferred_free_model_id: Mapped[str | None] = mapped_column(String(300))
    execution_mode: Mapped[str] = mapped_column(
        String(24), nullable=False, default="free_only", server_default="free_only"
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AiSession(Base):
    __tablename__ = "ai_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ready', 'running', 'failed', 'cancelled')",
            name="ck_ai_sessions_status",
        ),
        Index("idx_ai_sessions_owner_updated", "owner_id", text("updated_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(120), nullable=False, server_default="New AI chat"
    )
    provider_id: Mapped[str] = mapped_column(String(120), nullable=False)
    model_id: Mapped[str] = mapped_column(String(240), nullable=False)
    execution_type: Mapped[str] = mapped_column(String(12), nullable=False)
    context_policy: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="verified_only"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="ready"
    )
    external_session_id: Mapped[str | None] = mapped_column(String(200))
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AiMessage(Base):
    __tablename__ = "ai_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_ai_messages_role"),
        UniqueConstraint(
            "session_id", "sequence", name="uq_ai_messages_session_sequence"
        ),
        Index("idx_ai_messages_session_created", "session_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(12), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="completed"
    )
    provider_id: Mapped[str | None] = mapped_column(String(120))
    model_id: Mapped[str | None] = mapped_column(String(240))
    execution_type: Mapped[str | None] = mapped_column(String(12))
    context_sources: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    supplied_citations: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
