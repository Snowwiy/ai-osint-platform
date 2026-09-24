"""Add conservative LAN connection-medium evidence fields.

Revision ID: 0041_phase5bq_lan_discovery
Revises: 0040_phase5bi_native_jobs
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0041_phase5bq_lan_discovery"
down_revision: str | None = "0040_phase5bi_native_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lan_assets",
        sa.Column(
            "connection_medium",
            sa.String(20),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column(
        "lan_assets",
        sa.Column("connection_medium_source", sa.String(40), nullable=True),
    )
    op.add_column(
        "lan_assets",
        sa.Column(
            "connection_medium_confidence",
            sa.String(10),
            nullable=False,
            server_default="low",
        ),
    )


def downgrade() -> None:
    op.drop_column("lan_assets", "connection_medium_confidence")
    op.drop_column("lan_assets", "connection_medium_source")
    op.drop_column("lan_assets", "connection_medium")
