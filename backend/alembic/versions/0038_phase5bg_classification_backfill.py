"""Backfill classification for LAN assets present before Phase 5BG.

Revision ID: 0038_phase5bg_backfill
Revises: 0037_phase5bg_devices
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0038_phase5bg_backfill"
down_revision: str | None = "0037_phase5bg_devices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE lan_assets SET device_type='router', "
        "classification_source='gateway_hint', classification_confidence='high', "
        "classification_evidence='[\"configured gateway address\"]'::jsonb "
        "WHERE asset_type='gateway' AND classification_source='insufficient_evidence'"
    )
    op.execute(
        "UPDATE lan_assets SET device_type='server', agent_mode='ServerHost', "
        "agent_form_factor='server', classification_source='endpoint_agent', "
        "classification_confidence='high', "
        "classification_evidence='[\"server host agent\"]'::jsonb "
        "WHERE asset_type='server_host' AND source='endpoint_agent' "
        "AND classification_source='insufficient_evidence'"
    )
    op.execute(
        "UPDATE lan_assets AS a SET os_name=t.os_name, os_version=t.os_version, "
        "os_family=CASE WHEN lower(t.os_name) LIKE '%android%' THEN 'android' "
        "WHEN lower(t.os_name) LIKE '%iphone%' OR lower(t.os_name) LIKE '%ipad%' "
        "OR lower(t.os_name) LIKE 'ios%' THEN 'ios' "
        "WHEN lower(t.os_name) LIKE '%windows%' THEN 'windows' "
        "WHEN lower(t.os_name) LIKE '%linux%' OR lower(t.os_name) LIKE '%ubuntu%' "
        "OR lower(t.os_name) LIKE '%debian%' THEN 'linux' "
        "WHEN lower(t.os_name) LIKE '%macos%' OR lower(t.os_name) LIKE '%mac os%' "
        "OR lower(t.os_name) LIKE '%darwin%' THEN 'macos' ELSE 'unknown' END, "
        "agent_mode=COALESCE(a.agent_mode, 'LanEndpoint'), "
        "classification_source='endpoint_agent', classification_confidence='high', "
        "classification_evidence='[\"authenticated agent OS\"]'::jsonb "
        "FROM (SELECT DISTINCT ON (lan_asset_id) lan_asset_id, os_name, os_version "
        "FROM lan_asset_telemetry WHERE os_name IS NOT NULL "
        "ORDER BY lan_asset_id, collected_at DESC) AS t "
        "WHERE a.id=t.lan_asset_id AND a.source='endpoint_agent' "
        "AND a.classification_source='insufficient_evidence'"
    )
    op.execute(
        "UPDATE lan_assets SET vendor_source=source, vendor_confidence='low' "
        "WHERE vendor IS NOT NULL AND vendor_source IS NULL"
    )


def downgrade() -> None:
    # Classification is derived from telemetry and operator input; do not erase it.
    pass
