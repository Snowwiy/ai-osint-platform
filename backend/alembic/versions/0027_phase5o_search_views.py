"""Phase 5O global search and saved views.

Revision ID: 0027_phase5o_search
Revises: 0026_phase5n_notify
Create Date: 2026-06-28 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0027_phase5o_search"
down_revision: str | None = "0026_phase5n_notify"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_views",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("view_type", sa.String(length=40), nullable=False),
        sa.Column("route", sa.String(length=500), nullable=False),
        sa.Column(
            "filters",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("sort", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "is_default",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_pinned",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "view_type IN ("
            "'investigation_list', 'findings', 'reports', 'notifications', "
            "'engagements', 'closure', 'search', 'dashboard'"
            ")",
            name="ck_saved_views_type",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_saved_views_user_type",
        "saved_views",
        ["user_id", "view_type"],
    )
    op.create_index(
        "idx_saved_views_user_pinned",
        "saved_views",
        ["user_id", "is_pinned"],
    )
    op.create_index(
        "idx_saved_views_user_type_default",
        "saved_views",
        ["user_id", "view_type", "is_default"],
    )


def downgrade() -> None:
    op.drop_index("idx_saved_views_user_type_default", table_name="saved_views")
    op.drop_index("idx_saved_views_user_pinned", table_name="saved_views")
    op.drop_index("idx_saved_views_user_type", table_name="saved_views")
    op.drop_table("saved_views")
