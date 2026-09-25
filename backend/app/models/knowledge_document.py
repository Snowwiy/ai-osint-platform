from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ("
            "'security_notes', 'frameworks', 'playbooks', 'osint_notes'"
            ")",
            name="ck_knowledge_documents_source_type",
        ),
        Index("idx_knowledge_documents_source_type", "source_type"),
        Index("idx_knowledge_documents_hash", "hash"),
        Index("idx_knowledge_documents_file_path", "file_path", unique=True),
        Index("idx_knowledge_documents_category", "category"),
        Index("idx_knowledge_documents_source", "source_id"),
        Index(
            "idx_knowledge_documents_verification", "trust_level", "verification_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("knowledge_sources.id", ondelete="SET NULL")
    )
    relative_name: Mapped[str | None] = mapped_column(String(1000))
    category: Mapped[str] = mapped_column(
        String(80), nullable=False, server_default="Other"
    )
    content_type: Mapped[str] = mapped_column(
        String(80), nullable=False, server_default="text/markdown"
    )
    language: Mapped[str | None] = mapped_column(String(16))
    trust_level: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="unknown"
    )
    verification_status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="unverified"
    )
    document_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="ready"
    )
    size_bytes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    indexed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    knowledge_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
        server_default=text("'{}'::text[]"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
