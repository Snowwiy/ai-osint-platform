from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InvestigationPin(Base):
    __tablename__ = "investigation_pins"
    __table_args__ = (
        UniqueConstraint(
            "investigation_id",
            "user_id",
            name="uq_investigation_pins_investigation_user",
        ),
        Index("idx_investigation_pins_user", "user_id"),
        Index("idx_investigation_pins_investigation", "investigation_id"),
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
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
