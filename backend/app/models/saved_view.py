from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SavedView(Base, TimestampMixin):
    __tablename__ = "saved_views"
    __table_args__ = (
        CheckConstraint(
            "view_type IN ("
            "'investigation_list', 'findings', 'reports', 'notifications', "
            "'engagements', 'closure', 'search', 'dashboard'"
            ")",
            name="ck_saved_views_type",
        ),
        Index("idx_saved_views_user_type", "user_id", "view_type"),
        Index("idx_saved_views_user_pinned", "user_id", "is_pinned"),
        Index(
            "idx_saved_views_user_type_default",
            "user_id",
            "view_type",
            "is_default",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    view_type: Mapped[str] = mapped_column(String(40), nullable=False)
    route: Mapped[str] = mapped_column(String(500), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    sort: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    is_pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
