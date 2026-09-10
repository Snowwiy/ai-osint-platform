"""Add safe LAN service observation details.

Revision ID: 0032_phase5ab_ports
Revises: 0031_phase5aa_policy
"""

from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0032_phase5ab_ports"
down_revision: str | None = "0031_phase5aa_policy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_lan_services_status", "lan_service_observations", type_="check"
    )
    op.add_column(
        "lan_service_observations",
        sa.Column("ip_address", sa.String(45), nullable=True),
    )
    op.execute(
        "UPDATE lan_service_observations s SET ip_address = a.ip_address FROM lan_assets a WHERE a.id = s.lan_asset_id"
    )
    op.alter_column("lan_service_observations", "ip_address", nullable=False)
    op.add_column(
        "lan_service_observations",
        sa.Column("service_label", sa.String(160), nullable=True),
    )
    op.add_column(
        "lan_service_observations",
        sa.Column("confidence", sa.Integer(), server_default="40", nullable=False),
    )
    op.add_column(
        "lan_service_observations",
        sa.Column("banner_hint", sa.String(160), nullable=True),
    )
    op.add_column(
        "lan_service_observations",
        sa.Column(
            "non_standard_ssh", sa.Boolean(), server_default="false", nullable=False
        ),
    )
    op.create_check_constraint(
        "ck_lan_services_status",
        "lan_service_observations",
        "status IN ('open', 'closed', 'filtered', 'timeout', 'unknown')",
    )
    op.create_check_constraint(
        "ck_lan_services_confidence",
        "lan_service_observations",
        "confidence BETWEEN 0 AND 100",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_lan_services_confidence", "lan_service_observations", type_="check"
    )
    op.drop_constraint(
        "ck_lan_services_status", "lan_service_observations", type_="check"
    )
    op.execute(
        "UPDATE lan_service_observations SET status = 'unknown' WHERE status IN ('filtered', 'timeout')"
    )
    op.create_check_constraint(
        "ck_lan_services_status",
        "lan_service_observations",
        "status IN ('open', 'closed', 'unknown')",
    )
    op.drop_column("lan_service_observations", "non_standard_ssh")
    op.drop_column("lan_service_observations", "banner_hint")
    op.drop_column("lan_service_observations", "confidence")
    op.drop_column("lan_service_observations", "service_label")
    op.drop_column("lan_service_observations", "ip_address")
