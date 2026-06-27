"""Add enterprise case review workflow metadata.

Revision ID: 0022_phase5e_case_review
Revises: 0021_phase5d_threat_workspace
Create Date: 2026-06-24

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_phase5e_case_review"
down_revision: str | None = "0021_phase5d_threat_workspace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _timestamp(name: str, *, nullable: bool = True) -> sa.Column:
    return sa.Column(name, postgresql.TIMESTAMP(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "case_reviews",
        _uuid_pk(),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "review_status",
            sa.String(length=30),
            server_default="not_submitted",
            nullable=False,
        ),
        sa.Column("submitted_by", postgresql.UUID(as_uuid=True), nullable=True),
        _timestamp("submitted_at"),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        _timestamp("reviewed_at"),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("decision", sa.String(length=40), nullable=True),
        sa.Column("closed_by", postgresql.UUID(as_uuid=True), nullable=True),
        _timestamp("closed_at"),
        sa.Column("closure_reason", sa.Text(), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column(
            "checklist",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "evidence_completeness_score",
            sa.SmallInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "evidence_completeness_label",
            sa.String(length=20),
            server_default="incomplete",
            nullable=False,
        ),
        sa.Column(
            "evidence_completeness_contributors",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "review_status IN ("
            "'not_submitted', 'pending_review', 'changes_requested', "
            "'approved', 'rejected', 'closed'"
            ")",
            name="ck_case_reviews_status",
        ),
        sa.CheckConstraint(
            "evidence_completeness_score BETWEEN 0 AND 100",
            name="ck_case_reviews_completeness_score",
        ),
        sa.CheckConstraint(
            "evidence_completeness_label IN ("
            "'incomplete', 'partial', 'adequate', 'strong', 'complete'"
            ")",
            name="ck_case_reviews_completeness_label",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["closed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_case_reviews_investigation",
        "case_reviews",
        ["investigation_id"],
        unique=True,
    )
    op.create_index("idx_case_reviews_status", "case_reviews", ["review_status"])
    op.create_index(
        "idx_case_reviews_submitted_at",
        "case_reviews",
        [sa.text("submitted_at DESC")],
    )

    op.add_column(
        "reports",
        sa.Column(
            "approval_status",
            sa.String(length=30),
            server_default="draft",
            nullable=False,
        ),
    )
    op.add_column(
        "reports",
        sa.Column(
            "approval_submitted_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column("reports", _timestamp("approval_submitted_at"))
    op.add_column(
        "reports",
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("reports", _timestamp("approved_at"))
    op.add_column("reports", sa.Column("approval_notes", sa.Text(), nullable=True))
    op.add_column("reports", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_reports_approval_status",
        "reports",
        "approval_status IN ("
        "'draft', 'pending_approval', 'approved', 'rejected', 'archived'"
        ")",
    )
    op.create_index("idx_reports_approval_status", "reports", ["approval_status"])
    op.create_foreign_key(
        "fk_reports_approval_submitted_by_users",
        "reports",
        "users",
        ["approval_submitted_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_reports_approved_by_users",
        "reports",
        "users",
        ["approved_by"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "findings",
        sa.Column(
            "validation_status",
            sa.String(length=30),
            server_default="not_validated",
            nullable=False,
        ),
    )
    op.add_column(
        "findings",
        sa.Column("validation_owner", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "findings",
        sa.Column("validation_failure_reason", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_findings_validation_status",
        "findings",
        "validation_status IN ("
        "'not_validated', 'validation_pending', 'validated', "
        "'validation_failed', 'accepted_risk'"
        ")",
    )
    op.create_index(
        "idx_findings_validation_status",
        "findings",
        ["validation_status"],
    )
    op.create_index(
        "idx_findings_validation_owner",
        "findings",
        ["validation_owner"],
    )
    op.create_foreign_key(
        "fk_findings_validation_owner_users",
        "findings",
        "users",
        ["validation_owner"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_findings_validation_owner_users",
        "findings",
        type_="foreignkey",
    )
    op.drop_index("idx_findings_validation_owner", table_name="findings")
    op.drop_index("idx_findings_validation_status", table_name="findings")
    op.drop_constraint("ck_findings_validation_status", "findings", type_="check")
    op.drop_column("findings", "validation_failure_reason")
    op.drop_column("findings", "validation_owner")
    op.drop_column("findings", "validation_status")

    op.drop_constraint("fk_reports_approved_by_users", "reports", type_="foreignkey")
    op.drop_constraint(
        "fk_reports_approval_submitted_by_users",
        "reports",
        type_="foreignkey",
    )
    op.drop_index("idx_reports_approval_status", table_name="reports")
    op.drop_constraint("ck_reports_approval_status", "reports", type_="check")
    op.drop_column("reports", "rejection_reason")
    op.drop_column("reports", "approval_notes")
    op.drop_column("reports", "approved_at")
    op.drop_column("reports", "approved_by")
    op.drop_column("reports", "approval_submitted_at")
    op.drop_column("reports", "approval_submitted_by")
    op.drop_column("reports", "approval_status")

    op.drop_index("idx_case_reviews_submitted_at", table_name="case_reviews")
    op.drop_index("idx_case_reviews_status", table_name="case_reviews")
    op.drop_index("idx_case_reviews_investigation", table_name="case_reviews")
    op.drop_table("case_reviews")
