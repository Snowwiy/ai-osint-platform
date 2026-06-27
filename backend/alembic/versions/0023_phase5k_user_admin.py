"""Phase 5K user account governance.

Revision ID: 0023_phase5k_user_admin
Revises: 0022_phase5e_case_review
Create Date: 2026-06-27 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023_phase5k_user_admin"
down_revision: str | None = "0022_phase5e_case_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(length=120), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "account_status",
            sa.String(length=20),
            server_default="active",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "registration_source",
            sa.String(length=50),
            server_default="admin",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "approved_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        """
        UPDATE users
        SET account_status = CASE
            WHEN is_active THEN 'active'
            ELSE 'pending'
        END
        """
    )
    op.execute(
        """
        UPDATE users
        SET approved_at = COALESCE(approved_at, created_at)
        WHERE account_status = 'active'
        """
    )
    op.create_check_constraint(
        "ck_users_account_status",
        "users",
        "account_status IN ('active', 'pending', 'disabled', 'rejected')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_account_status", "users", type_="check")
    op.drop_column("users", "approved_by")
    op.drop_column("users", "approved_at")
    op.drop_column("users", "registration_source")
    op.drop_column("users", "account_status")
    op.drop_column("users", "full_name")
