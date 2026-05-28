"""Phase 2D report generation fields.

Revision ID: 0006_phase2d_reports
Revises: 0005_phase2a_knowledge
Create Date: 2026-05-28

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_phase2d_reports"
down_revision: Union[str, None] = "0005_phase2a_knowledge"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reports",
        sa.Column(
            "report_type",
            sa.String(length=20),
            server_default="technical",
            nullable=False,
        ),
    )
    op.add_column("reports", sa.Column("html_content", sa.Text(), nullable=True))
    op.add_column("reports", sa.Column("markdown_content", sa.Text(), nullable=True))
    op.add_column(
        "reports",
        sa.Column(
            "report_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_reports_type",
        "reports",
        "report_type IN ('executive', 'technical')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_reports_type", "reports", type_="check")
    op.drop_column("reports", "report_metadata")
    op.drop_column("reports", "markdown_content")
    op.drop_column("reports", "html_content")
    op.drop_column("reports", "report_type")
