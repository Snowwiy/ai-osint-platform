"""Add endpoint security posture and remediation recommendations.

Revision ID: 0036_phase5ai_posture
Revises: 0035_phase5ae_agents
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0036_phase5ai_posture"
down_revision: str | None = "0035_phase5ae_agents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "endpoint_security_postures",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("lan_asset_id", sa.UUID(), nullable=False),
        sa.Column("posture_score", sa.Integer(), nullable=False),
        sa.Column("posture_status", sa.String(24), nullable=False),
        sa.Column("firewall_status", sa.String(24)),
        sa.Column("antivirus_status", sa.String(24)),
        sa.Column("patch_status", sa.String(24)),
        sa.Column("pending_reboot", sa.Boolean()),
        sa.Column("os_name", sa.String(100)),
        sa.Column("os_version", sa.String(100)),
        sa.Column("disk_health", sa.String(24)),
        sa.Column("agent_freshness", sa.String(24)),
        sa.Column(
            "risky_services_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "recommendation_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "assessed_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "posture_score BETWEEN 0 AND 100", name="ck_endpoint_posture_score"
        ),
        sa.CheckConstraint(
            "posture_status IN ('healthy', 'needs_review', 'at_risk', 'critical', 'unknown')",
            name="ck_endpoint_posture_status",
        ),
        sa.ForeignKeyConstraint(
            ["lan_asset_id"], ["lan_assets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lan_asset_id", name="uq_endpoint_posture_asset"),
    )
    op.create_index(
        "idx_endpoint_posture_status", "endpoint_security_postures", ["posture_status"]
    )
    op.create_index(
        "idx_endpoint_posture_assessed", "endpoint_security_postures", ["assessed_at"]
    )
    op.create_table(
        "endpoint_remediation_recommendations",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("lan_asset_id", sa.UUID(), nullable=False),
        sa.Column("dedupe_key", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column(
            "manual_steps",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "isolation_recommended",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("evidence_source", sa.String(100), nullable=False),
        sa.Column("confidence", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="open", nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("acknowledged_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'low', 'medium', 'high', 'critical')",
            name="ck_endpoint_recommendation_severity",
        ),
        sa.CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="ck_endpoint_recommendation_confidence",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved')",
            name="ck_endpoint_recommendation_status",
        ),
        sa.ForeignKeyConstraint(
            ["lan_asset_id"], ["lan_assets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_endpoint_recommendation_dedupe"),
    )
    op.create_index(
        "idx_endpoint_recommendation_asset",
        "endpoint_remediation_recommendations",
        ["lan_asset_id"],
    )
    op.create_index(
        "idx_endpoint_recommendation_status",
        "endpoint_remediation_recommendations",
        ["status"],
    )
    op.create_index(
        "idx_endpoint_recommendation_severity",
        "endpoint_remediation_recommendations",
        ["severity"],
    )


def downgrade() -> None:
    op.drop_table("endpoint_remediation_recommendations")
    op.drop_table("endpoint_security_postures")
