"""Add investigation maturity stage.

Revision ID: 0019_phase4l_workspace
Revises: 0018_phase4i_governance
Create Date: 2026-06-14

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_phase4l_workspace"
down_revision: str | None = "0018_phase4i_governance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "investigations",
        sa.Column(
            "stage",
            sa.String(length=20),
            server_default="intake",
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE investigations
        SET stage = CASE status
            WHEN 'archived' THEN 'archived'
            WHEN 'completed' THEN 'completed'
            WHEN 'validation' THEN 'validation'
            WHEN 'remediation' THEN 'remediation'
            WHEN 'monitoring' THEN 'analysis'
            WHEN 'active' THEN 'analysis'
            ELSE 'intake'
        END
        """
    )
    op.create_check_constraint(
        "ck_investigations_stage",
        "investigations",
        "stage IN ("
        "'intake', 'scoping', 'recon', 'analysis', 'remediation', "
        "'validation', 'reporting', 'completed', 'archived'"
        ")",
    )
    op.create_index(
        "idx_investigations_stage",
        "investigations",
        ["stage"],
    )


def downgrade() -> None:
    op.drop_index("idx_investigations_stage", table_name="investigations")
    op.drop_constraint(
        "ck_investigations_stage",
        "investigations",
        type_="check",
    )
    op.drop_column("investigations", "stage")
