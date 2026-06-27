"""Add per-user investigation pins for the operations dashboard.

Revision ID: 0015_phase4f_operations
Revises: 0014_phase4d_bookmark_rules
Create Date: 2026-06-14

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_phase4f_operations"
down_revision: str | None = "0014_phase4d_bookmark_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "investigation_pins",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "investigation_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "investigation_id",
            "user_id",
            name="uq_investigation_pins_investigation_user",
        ),
    )
    op.create_index(
        "idx_investigation_pins_user",
        "investigation_pins",
        ["user_id"],
    )
    op.create_index(
        "idx_investigation_pins_investigation",
        "investigation_pins",
        ["investigation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_investigation_pins_investigation",
        table_name="investigation_pins",
    )
    op.drop_index(
        "idx_investigation_pins_user",
        table_name="investigation_pins",
    )
    op.drop_table("investigation_pins")
