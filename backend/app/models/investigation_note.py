from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InvestigationNote(Base):
    __tablename__ = "investigation_notes"
    __table_args__ = (
        CheckConstraint(
            "note_type IN ("
            "'analyst_note', 'evidence_note', 'remediation_note', "
            "'executive_note', 'timeline_note'"
            ")",
            name="ck_investigation_notes_type",
        ),
        Index("idx_investigation_notes_investigation", "investigation_id"),
        Index("idx_investigation_notes_created_by", "created_by"),
        Index("idx_investigation_notes_pinned", "investigation_id", "pinned"),
        Index("idx_investigation_notes_created", text("created_at DESC")),
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
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    note_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="analyst_note",
        server_default="analyst_note",
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
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

    @property
    def note(self) -> str:
        return self.content

    @note.setter
    def note(self, value: str) -> None:
        self.content = value

    @property
    def author_id(self) -> uuid.UUID | None:
        return self.created_by

    @author_id.setter
    def author_id(self, value: uuid.UUID | None) -> None:
        self.created_by = value
