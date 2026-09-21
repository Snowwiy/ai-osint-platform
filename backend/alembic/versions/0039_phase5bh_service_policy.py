"""Add explicit critical LAN exposure policy to service baselines.

Revision ID: 0039_phase5bh_service_policy
Revises: 0038_phase5bg_backfill
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0039_phase5bh_service_policy"
down_revision: str | None = "0038_phase5bg_backfill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("expected_service_baselines", sa.Column("critical_ports", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))


def downgrade() -> None:
    op.drop_column("expected_service_baselines", "critical_ports")
