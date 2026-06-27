"""Phase 3I workflow hardening and case ownership.

Revision ID: 0010_phase3i_workflow_hardening
Revises: 0009_repair_audit_log_schema
Create Date: 2026-05-30

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_phase3i_workflow_hardening"
down_revision: Union[str, None] = "0009_repair_audit_log_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    _harden_investigations()
    _harden_findings()
    _harden_tasks()
    _harden_evidence()


def downgrade() -> None:
    pass


def _harden_investigations() -> None:
    _drop_constraint("investigations", "ck_investigations_status", "check")
    if not _column_exists("investigations", "reviewer_id"):
        op.add_column(
            "investigations",
            sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
    if not _foreign_key_exists("investigations", "fk_investigations_reviewer_id_users"):
        op.create_foreign_key(
            "fk_investigations_reviewer_id_users",
            "investigations",
            "users",
            ["reviewer_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if not _index_exists("investigations", "idx_investigations_reviewer"):
        op.create_index(
            "idx_investigations_reviewer",
            "investigations",
            ["reviewer_id"],
        )
    op.execute("UPDATE investigations SET status = 'triage' WHERE status = 'review'")
    op.execute(
        "UPDATE investigations SET status = 'remediation' "
        "WHERE status = 'remediated'"
    )
    op.create_check_constraint(
        "ck_investigations_status",
        "investigations",
        "status IN ("
        "'draft', 'active', 'triage', 'monitoring', 'remediation', "
        "'validated', 'archived', 'review', 'remediated'"
        ")",
    )


def _harden_findings() -> None:
    _drop_constraint("findings", "ck_findings_status", "check")
    for column_name, column in (
        (
            "assigned_to",
            sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True),
        ),
        (
            "reviewed_by",
            sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        ),
        ("review_notes", sa.Column("review_notes", sa.Text(), nullable=True)),
        (
            "remediation_notes",
            sa.Column("remediation_notes", sa.Text(), nullable=True),
        ),
        ("validation_notes", sa.Column("validation_notes", sa.Text(), nullable=True)),
        (
            "confidence_reasoning",
            sa.Column("confidence_reasoning", sa.Text(), nullable=True),
        ),
        ("evidence_summary", sa.Column("evidence_summary", sa.Text(), nullable=True)),
        (
            "review_history",
            sa.Column(
                "review_history",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'[]'::jsonb"),
                nullable=False,
            ),
        ),
    ):
        if not _column_exists("findings", column_name):
            op.add_column("findings", column)
    if not _foreign_key_exists("findings", "fk_findings_assigned_to_users"):
        op.create_foreign_key(
            "fk_findings_assigned_to_users",
            "findings",
            "users",
            ["assigned_to"],
            ["id"],
            ondelete="SET NULL",
        )
    if not _foreign_key_exists("findings", "fk_findings_reviewed_by_users"):
        op.create_foreign_key(
            "fk_findings_reviewed_by_users",
            "findings",
            "users",
            ["reviewed_by"],
            ["id"],
            ondelete="SET NULL",
        )
    if not _index_exists("findings", "idx_findings_assigned_to"):
        op.create_index("idx_findings_assigned_to", "findings", ["assigned_to"])
    if not _index_exists("findings", "idx_findings_reviewed_by"):
        op.create_index("idx_findings_reviewed_by", "findings", ["reviewed_by"])
    op.execute("UPDATE findings SET status = 'new' WHERE status = 'open'")
    op.execute("UPDATE findings SET status = 'mitigated' WHERE status = 'resolved'")
    op.execute(
        "UPDATE findings SET review_history = '[]'::jsonb "
        "WHERE review_history IS NULL"
    )
    op.create_check_constraint(
        "ck_findings_status",
        "findings",
        "status IN ("
        "'new', 'under_review', 'validated', 'accepted_risk', "
        "'mitigated', 'false_positive', 'archived', 'open', 'resolved'"
        ")",
    )


def _harden_tasks() -> None:
    _drop_constraint(
        "investigation_tasks",
        "ck_investigation_tasks_status",
        "check",
    )
    _drop_constraint(
        "investigation_tasks",
        "ck_investigation_tasks_priority",
        "check",
    )
    for column_name, column in (
        (
            "finding_id",
            sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=True),
        ),
        ("remediation_link", sa.Column("remediation_link", sa.Text(), nullable=True)),
        (
            "evidence_reference_ids",
            sa.Column(
                "evidence_reference_ids",
                postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
                server_default=sa.text("'{}'::uuid[]"),
                nullable=False,
            ),
        ),
        (
            "updated_at",
            sa.Column(
                "updated_at",
                postgresql.TIMESTAMP(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        ),
    ):
        if not _column_exists("investigation_tasks", column_name):
            op.add_column("investigation_tasks", column)
    if not _foreign_key_exists("investigation_tasks", "fk_tasks_finding_id_findings"):
        op.create_foreign_key(
            "fk_tasks_finding_id_findings",
            "investigation_tasks",
            "findings",
            ["finding_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if not _index_exists("investigation_tasks", "idx_investigation_tasks_finding"):
        op.create_index(
            "idx_investigation_tasks_finding",
            "investigation_tasks",
            ["finding_id"],
        )
    op.execute("UPDATE investigation_tasks SET status = 'open' WHERE status = 'todo'")
    op.execute(
        "UPDATE investigation_tasks SET priority = 'critical' "
        "WHERE priority = 'urgent'"
    )
    op.execute(
        "UPDATE investigation_tasks SET evidence_reference_ids = '{}'::uuid[] "
        "WHERE evidence_reference_ids IS NULL"
    )
    op.execute(
        "UPDATE investigation_tasks SET updated_at = created_at "
        "WHERE updated_at IS NULL"
    )
    op.create_check_constraint(
        "ck_investigation_tasks_status",
        "investigation_tasks",
        "status IN ("
        "'open', 'in_progress', 'blocked', 'completed', 'cancelled', 'todo'"
        ")",
    )
    op.create_check_constraint(
        "ck_investigation_tasks_priority",
        "investigation_tasks",
        "priority IN ('critical', 'high', 'medium', 'low', 'urgent')",
    )


def _harden_evidence() -> None:
    for column_name, column in (
        (
            "review_status",
            sa.Column(
                "review_status",
                sa.String(length=20),
                server_default="collected",
                nullable=False,
            ),
        ),
        (
            "reviewed_by",
            sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        ),
        (
            "reviewed_at",
            sa.Column("reviewed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        ),
        ("analyst_note", sa.Column("analyst_note", sa.Text(), nullable=True)),
        (
            "confidence_score",
            sa.Column(
                "confidence_score",
                sa.SmallInteger(),
                server_default="50",
                nullable=False,
            ),
        ),
        (
            "archived_at",
            sa.Column("archived_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        ),
    ):
        if not _column_exists("investigation_evidence", column_name):
            op.add_column("investigation_evidence", column)
    if not _foreign_key_exists(
        "investigation_evidence",
        "fk_investigation_evidence_reviewed_by_users",
    ):
        op.create_foreign_key(
            "fk_investigation_evidence_reviewed_by_users",
            "investigation_evidence",
            "users",
            ["reviewed_by"],
            ["id"],
            ondelete="SET NULL",
        )
    if not _constraint_exists(
        "investigation_evidence",
        "ck_investigation_evidence_confidence_score",
    ):
        op.create_check_constraint(
            "ck_investigation_evidence_confidence_score",
            "investigation_evidence",
            "confidence_score BETWEEN 0 AND 100",
        )
    if not _constraint_exists(
        "investigation_evidence",
        "ck_investigation_evidence_review_status",
    ):
        op.create_check_constraint(
            "ck_investigation_evidence_review_status",
            "investigation_evidence",
            "review_status IN ('collected', 'reviewed', 'validated', 'dismissed')",
        )
    op.execute(
        "UPDATE investigation_evidence SET confidence_score = confidence "
        "WHERE confidence_score IS NULL"
    )


def _drop_constraint(table_name: str, constraint_name: str, constraint_type: str) -> None:
    if _constraint_exists(table_name, constraint_name):
        op.drop_constraint(constraint_name, table_name, type_=constraint_type)


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {
        column["name"] for column in inspector.get_columns(table_name)
    }


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return index_name in {
        index["name"] for index in inspector.get_indexes(table_name)
    }


def _constraint_exists(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return constraint_name in {
        constraint["name"] for constraint in inspector.get_check_constraints(table_name)
    }


def _foreign_key_exists(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return constraint_name in {
        foreign_key["name"] for foreign_key in inspector.get_foreign_keys(table_name)
    }
