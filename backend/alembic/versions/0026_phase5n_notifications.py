"""Phase 5N notification center and activity inbox.

Revision ID: 0026_phase5n_notify
Revises: 0025_phase5m_closure
Create Date: 2026-06-28 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026_phase5n_notify"
down_revision: str | None = "0025_phase5m_closure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notification_type", sa.String(length=80), nullable=False),
        sa.Column(
            "severity",
            sa.String(length=20),
            server_default="info",
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("action_url", sa.String(length=500), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="unread",
            nullable=False,
        ),
        sa.Column("read_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("dismissed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
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
            "severity IN ('info', 'success', 'warning', 'critical')",
            name="ck_notifications_severity",
        ),
        sa.CheckConstraint(
            "status IN ('unread', 'read', 'dismissed', 'archived')",
            name="ck_notifications_status",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["engagement_id"],
            ["engagements.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_notifications_user_status_created",
        "notifications",
        ["user_id", "status", "created_at"],
    )
    op.create_index(
        "idx_notifications_type_created",
        "notifications",
        ["notification_type", "created_at"],
    )
    op.create_index(
        "idx_notifications_investigation",
        "notifications",
        ["investigation_id"],
    )
    op.create_index(
        "idx_notifications_engagement",
        "notifications",
        ["engagement_id"],
    )
    op.create_index(
        "idx_notifications_dedupe_key",
        "notifications",
        ["dedupe_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_notifications_dedupe_key", table_name="notifications")
    op.drop_index("idx_notifications_engagement", table_name="notifications")
    op.drop_index("idx_notifications_investigation", table_name="notifications")
    op.drop_index("idx_notifications_type_created", table_name="notifications")
    op.drop_index("idx_notifications_user_status_created", table_name="notifications")
    op.drop_table("notifications")
