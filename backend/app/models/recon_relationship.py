from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ReconRelationship(Base):
    __tablename__ = "recon_relationships"
    __table_args__ = (
        CheckConstraint(
            "relationship_type IN ("
            "'RESOLVES_TO', 'BELONGS_TO', 'USES_CERTIFICATE', 'HOSTS', "
            "'RELATED_TO', 'DISCOVERED_FROM'"
            ")",
            name="ck_recon_relationships_type",
        ),
        UniqueConstraint(
            "investigation_id",
            "source_entity_id",
            "target_entity_id",
            "relationship_type",
            name="uq_recon_relationships_unique_edge",
        ),
        Index("idx_recon_relationships_investigation", "investigation_id"),
        Index("idx_recon_relationships_source", "source_entity_id"),
        Index("idx_recon_relationships_target", "target_entity_id"),
        Index("idx_recon_relationships_type", "relationship_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("recon_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("recon_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    properties: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
