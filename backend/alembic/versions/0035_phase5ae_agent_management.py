"""Add endpoint enrollment, asset groups, and service baselines.

Revision ID: 0035_phase5ae_agents
Revises: 0034_phase5ad_triage
"""

from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0035_phase5ae_agents"
down_revision: str | None = "0034_phase5ad_triage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_enrollment_tokens",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("token_hint", sa.String(16), nullable=False),
        sa.Column("allowed_cidr", sa.String(43)),
        sa.Column("max_enrollments", sa.Integer()),
        sa.Column("enrollment_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID()),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_agent_enrollment_token_hash"),
    )
    op.create_index(
        "idx_agent_enrollment_token_expires", "agent_enrollment_tokens", ["expires_at"]
    )
    op.create_table(
        "asset_groups",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_by", sa.UUID()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_asset_groups_name"),
    )
    op.add_column("lan_assets", sa.Column("enrolled_at", sa.TIMESTAMP(timezone=True)))
    op.add_column("lan_assets", sa.Column("enrollment_token_id", sa.UUID()))
    op.add_column(
        "lan_assets",
        sa.Column(
            "capabilities",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_lan_assets_enrollment_token",
        "lan_assets",
        "agent_enrollment_tokens",
        ["enrollment_token_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "asset_group_memberships",
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["lan_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["asset_groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("asset_id", "group_id"),
    )
    op.create_table(
        "expected_service_baselines",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("asset_id", sa.UUID()),
        sa.Column("group_id", sa.UUID()),
        sa.Column(
            "expected_ports",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "allowed_ports",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(asset_id IS NULL) <> (group_id IS NULL)", name="ck_service_baseline_scope"
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["lan_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["asset_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_service_baseline_asset", "expected_service_baselines", ["asset_id"]
    )
    op.create_index(
        "idx_service_baseline_group", "expected_service_baselines", ["group_id"]
    )


def downgrade() -> None:
    op.drop_table("expected_service_baselines")
    op.drop_table("asset_group_memberships")
    op.drop_constraint(
        "fk_lan_assets_enrollment_token", "lan_assets", type_="foreignkey"
    )
    op.drop_column("lan_assets", "capabilities")
    op.drop_column("lan_assets", "enrollment_token_id")
    op.drop_column("lan_assets", "enrolled_at")
    op.drop_table("asset_groups")
    op.drop_table("agent_enrollment_tokens")
