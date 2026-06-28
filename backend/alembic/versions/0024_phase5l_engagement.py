"""Phase 5L engagement scope governance.

Revision ID: 0024_phase5l_engagement
Revises: 0023_phase5k_user_admin
Create Date: 2026-06-27 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024_phase5l_engagement"
down_revision: str | None = "0023_phase5k_user_admin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "engagements",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("client_name", sa.String(length=255), nullable=False),
        sa.Column("client_contact", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column(
            "authorization_status",
            sa.String(length=30),
            server_default="not_provided",
            nullable=False,
        ),
        sa.Column("start_date", postgresql.DATE(), nullable=True),
        sa.Column("end_date", postgresql.DATE(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
            "status IN ('draft', 'active', 'completed', 'archived')",
            name="ck_engagements_status",
        ),
        sa.CheckConstraint(
            "authorization_status IN ("
            "'not_provided', 'pending_review', 'approved', 'expired', 'revoked'"
            ")",
            name="ck_engagements_authorization_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_engagements_status", "engagements", ["status"])
    op.create_index(
        "idx_engagements_authorization_status",
        "engagements",
        ["authorization_status"],
    )
    op.create_index("idx_engagements_created_by", "engagements", ["created_by"])

    op.create_table(
        "engagement_scope_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_type", sa.String(length=30), nullable=False),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="pending_review",
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
            "scope_type IN ("
            "'domain', 'subdomain', 'ip', 'cidr', 'email', 'username', "
            "'organization', 'other'"
            ")",
            name="ck_engagement_scope_items_type",
        ),
        sa.CheckConstraint(
            "status IN ('in_scope', 'out_of_scope', 'pending_review')",
            name="ck_engagement_scope_items_status",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["engagement_id"],
            ["engagements.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "engagement_id",
            "scope_type",
            "value",
            name="uq_engagement_scope_item_value",
        ),
    )
    op.create_index(
        "idx_engagement_scope_items_engagement",
        "engagement_scope_items",
        ["engagement_id"],
    )
    op.create_index(
        "idx_engagement_scope_items_status",
        "engagement_scope_items",
        ["status"],
    )
    op.create_index(
        "idx_engagement_scope_items_value",
        "engagement_scope_items",
        ["value"],
    )

    op.create_table(
        "authorization_evidence",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("evidence_type", sa.String(length=50), nullable=False),
        sa.Column("reference", sa.String(length=500), nullable=True),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="pending_review",
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
            "evidence_type IN ("
            "'contract', 'email_approval', 'statement_of_work', "
            "'internal_authorization', 'other'"
            ")",
            name="ck_authorization_evidence_type",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'not_provided', 'pending_review', 'approved', 'expired', 'revoked'"
            ")",
            name="ck_authorization_evidence_status",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["engagement_id"],
            ["engagements.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_authorization_evidence_engagement",
        "authorization_evidence",
        ["engagement_id"],
    )
    op.create_index(
        "idx_authorization_evidence_status",
        "authorization_evidence",
        ["status"],
    )

    op.add_column(
        "investigations",
        sa.Column("engagement_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "investigations",
        sa.Column(
            "scope_review_status",
            sa.String(length=30),
            server_default="not_reviewed",
            nullable=False,
        ),
    )
    op.add_column(
        "investigations",
        sa.Column("scope_notes", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_investigations_engagement_id",
        "investigations",
        "engagements",
        ["engagement_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_investigations_scope_review_status",
        "investigations",
        "scope_review_status IN ("
        "'not_reviewed', 'in_scope', 'out_of_scope', 'pending_review'"
        ")",
    )
    op.create_index(
        "idx_investigations_engagement",
        "investigations",
        ["engagement_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_investigations_engagement", table_name="investigations")
    op.drop_constraint(
        "ck_investigations_scope_review_status",
        "investigations",
        type_="check",
    )
    op.drop_constraint(
        "fk_investigations_engagement_id",
        "investigations",
        type_="foreignkey",
    )
    op.drop_column("investigations", "scope_notes")
    op.drop_column("investigations", "scope_review_status")
    op.drop_column("investigations", "engagement_id")
    op.drop_index(
        "idx_authorization_evidence_status",
        table_name="authorization_evidence",
    )
    op.drop_index(
        "idx_authorization_evidence_engagement",
        table_name="authorization_evidence",
    )
    op.drop_table("authorization_evidence")
    op.drop_index(
        "idx_engagement_scope_items_value",
        table_name="engagement_scope_items",
    )
    op.drop_index(
        "idx_engagement_scope_items_status",
        table_name="engagement_scope_items",
    )
    op.drop_index(
        "idx_engagement_scope_items_engagement",
        table_name="engagement_scope_items",
    )
    op.drop_table("engagement_scope_items")
    op.drop_index("idx_engagements_created_by", table_name="engagements")
    op.drop_index(
        "idx_engagements_authorization_status",
        table_name="engagements",
    )
    op.drop_index("idx_engagements_status", table_name="engagements")
    op.drop_table("engagements")
