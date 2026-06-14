from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InvestigationTag(Base):
    __tablename__ = "investigation_tags"
    __table_args__ = (
        UniqueConstraint("name", name="uq_investigation_tags_name"),
        Index("idx_investigation_tags_name", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="slate",
        server_default="slate",
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class InvestigationTagLink(Base):
    __tablename__ = "investigation_tag_links"
    __table_args__ = (
        UniqueConstraint(
            "investigation_id",
            "tag_id",
            name="uq_investigation_tag_links_pair",
        ),
        Index("idx_investigation_tag_links_investigation", "investigation_id"),
        Index("idx_investigation_tag_links_tag", "tag_id"),
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
    tag_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("investigation_tags.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
