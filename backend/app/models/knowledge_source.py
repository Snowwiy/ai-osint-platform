from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KnowledgeSource(Base):
    """Operator-authorized local material indexed by RavenTech."""

    __tablename__ = "knowledge_sources"
    __table_args__ = (
        Index("idx_knowledge_sources_status", "status"),
        Index("idx_knowledge_sources_trust", "trust_level", "verification_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    root_path: Mapped[str | None] = mapped_column(Text)
    # Private host-local read-only origin for selected Obsidian vaults.
    # Never serialize this field or add it to audit metadata.
    local_root_path: Mapped[str | None] = mapped_column(Text)
    display_location: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(
        String(80), nullable=False, server_default="Other"
    )
    platform: Mapped[str | None] = mapped_column(String(20))
    availability: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="available"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="pending"
    )
    trust_level: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="unknown"
    )
    verification_status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="unverified"
    )
    language: Mapped[str | None] = mapped_column(String(16))
    publisher: Mapped[str | None] = mapped_column(String(200))
    canonical_url: Mapped[str | None] = mapped_column(String(1000))
    publication_date: Mapped[str | None] = mapped_column(String(40))
    version_label: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    last_indexed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    document_count: Mapped[int] = mapped_column(nullable=False, server_default="0")
    chunk_count: Mapped[int] = mapped_column(nullable=False, server_default="0")
    error_summary: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
