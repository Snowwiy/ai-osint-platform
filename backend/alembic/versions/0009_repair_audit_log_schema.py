"""Repair audit log schema drift.

Revision ID: 0009_repair_audit_log_schema
Revises: 0008_phase3h_audit_hardening
Create Date: 2026-05-30

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_repair_audit_log_schema"
down_revision: Union[str, None] = "0008_phase3h_audit_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not _column_exists("audit_logs", "actor_id"):
        op.add_column(
            "audit_logs",
            sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
    if not _column_exists("audit_logs", "investigation_id"):
        op.add_column(
            "audit_logs",
            sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
    if not _column_exists("audit_logs", "metadata"):
        op.add_column(
            "audit_logs",
            sa.Column(
                "metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'{}'::jsonb"),
                nullable=False,
            ),
        )
    if not _column_exists("audit_logs", "created_at"):
        op.add_column(
            "audit_logs",
            sa.Column(
                "created_at",
                postgresql.TIMESTAMP(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )

    op.execute("UPDATE audit_logs SET actor_id = user_id WHERE actor_id IS NULL")
    op.execute("UPDATE audit_logs SET metadata = details WHERE metadata = '{}'::jsonb")
    op.execute("UPDATE audit_logs SET created_at = timestamp WHERE created_at IS NULL")

    if not _foreign_key_exists("audit_logs", "fk_audit_logs_actor_id_users"):
        op.create_foreign_key(
            "fk_audit_logs_actor_id_users",
            "audit_logs",
            "users",
            ["actor_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if not _foreign_key_exists(
        "audit_logs",
        "fk_audit_logs_investigation_id_investigations",
    ):
        op.create_foreign_key(
            "fk_audit_logs_investigation_id_investigations",
            "audit_logs",
            "investigations",
            ["investigation_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if not _index_exists("audit_logs", "idx_audit_logs_created_at"):
        op.create_index(
            "idx_audit_logs_created_at",
            "audit_logs",
            [sa.text("created_at DESC")],
        )
    if not _index_exists("audit_logs", "idx_audit_logs_actor_id"):
        op.create_index("idx_audit_logs_actor_id", "audit_logs", ["actor_id"])
    if not _index_exists("audit_logs", "idx_audit_logs_investigation_id"):
        op.create_index(
            "idx_audit_logs_investigation_id",
            "audit_logs",
            ["investigation_id"],
        )
    if not _index_exists("audit_logs", "idx_audit_logs_resource_type"):
        op.create_index(
            "idx_audit_logs_resource_type",
            "audit_logs",
            ["resource_type"],
        )


def downgrade() -> None:
    pass


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


def _foreign_key_exists(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return constraint_name in {
        foreign_key["name"] for foreign_key in inspector.get_foreign_keys(table_name)
    }
