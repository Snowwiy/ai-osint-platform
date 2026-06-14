"""Phase 4B collaboration RBAC.

Revision ID: 0011_phase4b_collaboration_rbac
Revises: 0010_phase3i_workflow_hardening
Create Date: 2026-05-31

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_phase4b_collaboration_rbac"
down_revision: Union[str, None] = "0010_phase3i_workflow_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    _harden_membership()


def downgrade() -> None:
    pass


def _harden_membership() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    _drop_constraint("investigation_members", "ck_investigation_members_role", "check")

    if not _column_exists("investigation_members", "id"):
        op.add_column(
            "investigation_members",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=True,
            ),
        )
        op.execute(
            "UPDATE investigation_members "
            "SET id = gen_random_uuid() WHERE id IS NULL"
        )
        op.alter_column("investigation_members", "id", nullable=False)

    if not _column_exists("investigation_members", "invited_by"):
        op.add_column(
            "investigation_members",
            sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=True),
        )

    if not _column_exists("investigation_members", "created_at"):
        op.add_column(
            "investigation_members",
            sa.Column(
                "created_at",
                postgresql.TIMESTAMP(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
        )
        if _column_exists("investigation_members", "added_at"):
            op.execute(
                "UPDATE investigation_members "
                "SET created_at = added_at WHERE created_at IS NULL"
            )
        op.execute(
            "UPDATE investigation_members "
            "SET created_at = now() WHERE created_at IS NULL"
        )
        op.alter_column("investigation_members", "created_at", nullable=False)

    if not _column_exists("investigation_members", "updated_at"):
        op.add_column(
            "investigation_members",
            sa.Column(
                "updated_at",
                postgresql.TIMESTAMP(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
        )
        op.execute(
            "UPDATE investigation_members "
            "SET updated_at = created_at WHERE updated_at IS NULL"
        )
        op.alter_column("investigation_members", "updated_at", nullable=False)

    op.execute(
        "UPDATE investigation_members SET role = 'analyst' "
        "WHERE role = 'collaborator'"
    )
    _create_foreign_key(
        "fk_investigation_members_invited_by_users",
        "investigation_members",
        "users",
        ["invited_by"],
        ["id"],
        ondelete="SET NULL",
    )
    _create_unique_constraint(
        "uq_investigation_members_id",
        "investigation_members",
        ["id"],
    )
    _create_unique_constraint(
        "uq_investigation_members_investigation_user",
        "investigation_members",
        ["investigation_id", "user_id"],
    )
    _create_index("investigation_members", "idx_investigation_members_id", ["id"])
    _create_index("investigation_members", "idx_investigation_members_user", ["user_id"])
    op.create_check_constraint(
        "ck_investigation_members_role",
        "investigation_members",
        "role IN ('owner', 'admin', 'analyst', 'viewer')",
    )


def _drop_constraint(table_name: str, constraint_name: str, constraint_type: str) -> None:
    if _constraint_exists(table_name, constraint_name):
        op.drop_constraint(constraint_name, table_name, type_=constraint_type)


def _create_foreign_key(
    name: str,
    source_table: str,
    referent_table: str,
    local_cols: list[str],
    remote_cols: list[str],
    *,
    ondelete: str,
) -> None:
    if not _foreign_key_exists(source_table, name):
        op.create_foreign_key(
            name,
            source_table,
            referent_table,
            local_cols,
            remote_cols,
            ondelete=ondelete,
        )


def _create_unique_constraint(
    name: str,
    table_name: str,
    columns: list[str],
) -> None:
    if not _unique_constraint_exists(table_name, name):
        op.create_unique_constraint(name, table_name, columns)


def _create_index(table_name: str, index_name: str, columns: list[str]) -> None:
    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {
        column["name"] for column in inspector.get_columns(table_name)
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


def _unique_constraint_exists(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return constraint_name in {
        constraint["name"] for constraint in inspector.get_unique_constraints(table_name)
    }


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return index_name in {
        index["name"] for index in inspector.get_indexes(table_name)
    }
