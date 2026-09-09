"""Phase 5M case closure deliverables workflow.

Revision ID: 0025_phase5m_closure
Revises: 0024_phase5l_engagement
Create Date: 2026-06-28 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025_phase5m_closure"
down_revision: str | None = "0024_phase5l_engagement"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "case_closures",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("closure_summary", sa.Text(), nullable=True),
        sa.Column(
            "final_risk_rating",
            sa.String(length=20),
            server_default="not_assessed",
            nullable=False,
        ),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("closed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("approved_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("closed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
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
            "status IN ('draft', 'in_review', 'approved', 'closed', 'reopened')",
            name="ck_case_closures_status",
        ),
        sa.CheckConstraint(
            "final_risk_rating IN ("
            "'low', 'moderate', 'elevated', 'high', 'critical', 'not_assessed'"
            ")",
            name="ck_case_closures_final_risk_rating",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["closed_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_case_closures_investigation",
        "case_closures",
        ["investigation_id"],
        unique=True,
    )
    op.create_index("idx_case_closures_status", "case_closures", ["status"])
    op.create_index(
        "idx_case_closures_closed_at",
        "case_closures",
        [sa.text("closed_at DESC")],
    )

    op.create_table(
        "case_closure_checklist_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("closure_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("required", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("completed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("completed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
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
            "status IN ('pending', 'completed', 'blocked', 'not_applicable')",
            name="ck_case_closure_checklist_status",
        ),
        sa.ForeignKeyConstraint(
            ["closure_id"],
            ["case_closures.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["completed_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_case_closure_checklist_investigation",
        "case_closure_checklist_items",
        ["investigation_id", "key"],
        unique=True,
    )
    op.create_index(
        "idx_case_closure_checklist_closure",
        "case_closure_checklist_items",
        ["closure_id"],
    )
    op.create_index(
        "idx_case_closure_checklist_status",
        "case_closure_checklist_items",
        ["status"],
    )

    op.create_table(
        "case_deliverables",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("deliverable_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("export_format", sa.String(length=10), nullable=True),
        sa.Column("file_reference", sa.String(length=500), nullable=True),
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
            "deliverable_type IN ("
            "'executive_report', 'technical_report', 'evidence_appendix', "
            "'remediation_plan', 'scope_summary', 'audit_summary', 'final_package'"
            ")",
            name="ck_case_deliverables_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'ready', 'approved', 'delivered', 'archived')",
            name="ck_case_deliverables_status",
        ),
        sa.CheckConstraint(
            "export_format IS NULL OR export_format IN ('pdf', 'docx', 'html', 'md')",
            name="ck_case_deliverables_export_format",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_case_deliverables_investigation",
        "case_deliverables",
        ["investigation_id"],
    )
    op.create_index(
        "idx_case_deliverables_status",
        "case_deliverables",
        ["status"],
    )
    op.create_index(
        "idx_case_deliverables_type",
        "case_deliverables",
        ["deliverable_type"],
    )


def downgrade() -> None:
    op.drop_index("idx_case_deliverables_type", table_name="case_deliverables")
    op.drop_index("idx_case_deliverables_status", table_name="case_deliverables")
    op.drop_index(
        "idx_case_deliverables_investigation",
        table_name="case_deliverables",
    )
    op.drop_table("case_deliverables")
    op.drop_index(
        "idx_case_closure_checklist_status",
        table_name="case_closure_checklist_items",
    )
    op.drop_index(
        "idx_case_closure_checklist_closure",
        table_name="case_closure_checklist_items",
    )
    op.drop_index(
        "idx_case_closure_checklist_investigation",
        table_name="case_closure_checklist_items",
    )
    op.drop_table("case_closure_checklist_items")
    op.drop_index("idx_case_closures_closed_at", table_name="case_closures")
    op.drop_index("idx_case_closures_status", table_name="case_closures")
    op.drop_index("idx_case_closures_investigation", table_name="case_closures")
    op.drop_table("case_closures")
