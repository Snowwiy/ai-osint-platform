"""Persist human approved fixed local actions.

Revision ID: 0045_phase6d_action_gateway
Revises: 0044_phase6c_op_analysis
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0045_phase6d_action_gateway"
down_revision: str | None = "0044_phase6c_op_analysis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "action_gateway_policy",
        sa.Column("id", sa.Integer(), server_default="1", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_action_gateway_policy_singleton"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "action_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("action_id", sa.String(100), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("origin", sa.String(32), nullable=False),
        sa.Column("scope_type", sa.String(32), server_default="local", nullable=False),
        sa.Column("scope_id", sa.String(80), nullable=True),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(100), nullable=True),
        sa.Column("target_display_name", sa.String(180), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("supporting_evidence_ids", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("expected_effect", sa.String(300), nullable=False),
        sa.Column("possible_impact", sa.String(500), nullable=False),
        sa.Column("rollback_guidance", sa.String(500), nullable=False),
        sa.Column("preconditions", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("target_snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("proposal_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="awaiting_approval", nullable=False),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("result_summary", sa.String(500), nullable=True),
        sa.Column("safe_error_code", sa.String(60), nullable=True),
        sa.Column("completed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('awaiting_approval','approved','rejected','expired','executing','completed','completed_with_warnings','failed','cancelled','verification_failed')", name="ck_action_proposals_status"),
        sa.CheckConstraint("risk_level IN ('low','medium','high','blocked')", name="ck_action_proposals_risk"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_action_proposals_status_created", "action_proposals", ["status", sa.text("created_at DESC")])
    op.create_index("idx_action_proposals_requester_created", "action_proposals", ["requested_by_user_id", sa.text("created_at DESC")])
    op.create_index("idx_action_proposals_target", "action_proposals", ["target_type", "target_id"])
    op.create_table(
        "action_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("approval_method", sa.String(24), server_default="human_ui", nullable=False),
        sa.Column("confirmation_text", sa.String(220), nullable=True),
        sa.Column("proposal_hash", sa.String(64), nullable=False),
        sa.Column("target_snapshot_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("consumed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["proposal_id"], ["action_proposals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("proposal_id", name="uq_action_approvals_proposal"),
    )
    op.create_index("idx_action_approvals_expiry", "action_approvals", ["expires_at"])
    op.create_table(
        "action_target_locks",
        sa.Column("target_key", sa.String(240), nullable=False),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lease_expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["proposal_id"], ["action_proposals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("target_key"),
        sa.UniqueConstraint("proposal_id", name="uq_action_target_locks_proposal"),
    )
    op.create_index("idx_action_target_locks_expiry", "action_target_locks", ["lease_expires_at"])


def downgrade() -> None:
    op.drop_index("idx_action_target_locks_expiry", table_name="action_target_locks")
    op.drop_table("action_target_locks")
    op.drop_index("idx_action_approvals_expiry", table_name="action_approvals")
    op.drop_table("action_approvals")
    op.drop_index("idx_action_proposals_target", table_name="action_proposals")
    op.drop_index("idx_action_proposals_requester_created", table_name="action_proposals")
    op.drop_index("idx_action_proposals_status_created", table_name="action_proposals")
    op.drop_table("action_proposals")
    op.drop_table("action_gateway_policy")
