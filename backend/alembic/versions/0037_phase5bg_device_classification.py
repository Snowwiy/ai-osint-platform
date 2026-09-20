"""Store evidence-backed LAN device classification.

Revision ID: 0037_phase5bg_devices
Revises: 0036_phase5ai_posture
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0037_phase5bg_devices"
down_revision: str | None = "0036_phase5ai_posture"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_columns = (
    ("vendor_source", sa.String(40), None),
    ("vendor_confidence", sa.String(10), "low"),
    ("os_family", sa.String(20), "unknown"),
    ("os_name", sa.String(100), None),
    ("os_version", sa.String(100), None),
    ("architecture", sa.String(40), None),
    ("agent_mode", sa.String(40), None),
    ("agent_form_factor", sa.String(30), None),
    ("device_type", sa.String(30), "unknown"),
    ("manual_device_type", sa.String(30), None),
    ("classification_source", sa.String(40), "insufficient_evidence"),
    ("classification_confidence", sa.String(10), "low"),
)


def upgrade() -> None:
    for name, type_, default in _columns:
        op.add_column(
            "lan_assets",
            sa.Column(name, type_, nullable=default is None, server_default=default),
        )
    op.add_column(
        "lan_assets",
        sa.Column(
            "classification_evidence",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("lan_assets", "classification_evidence")
    for name, _, _ in reversed(_columns):
        op.drop_column("lan_assets", name)
