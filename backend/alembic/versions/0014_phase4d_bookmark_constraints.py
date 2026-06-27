"""Enforce one unique evidence reference per investigation bookmark.

Revision ID: 0014_phase4d_bookmark_rules
Revises: 0013_phase4d_productivity
Create Date: 2026-06-14

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0014_phase4d_bookmark_rules"
down_revision: str | None = "0013_phase4d_productivity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_evidence_bookmarks_link",
        "evidence_bookmarks",
        type_="check",
    )
    op.create_check_constraint(
        "ck_evidence_bookmarks_link",
        "evidence_bookmarks",
        "(CASE WHEN entity_id IS NOT NULL THEN 1 ELSE 0 END + "
        "CASE WHEN finding_id IS NOT NULL THEN 1 ELSE 0 END + "
        "CASE WHEN report_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
    )
    op.create_unique_constraint(
        "uq_evidence_bookmarks_entity",
        "evidence_bookmarks",
        ["investigation_id", "entity_id"],
    )
    op.create_unique_constraint(
        "uq_evidence_bookmarks_finding",
        "evidence_bookmarks",
        ["investigation_id", "finding_id"],
    )
    op.create_unique_constraint(
        "uq_evidence_bookmarks_report",
        "evidence_bookmarks",
        ["investigation_id", "report_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_evidence_bookmarks_report",
        "evidence_bookmarks",
        type_="unique",
    )
    op.drop_constraint(
        "uq_evidence_bookmarks_finding",
        "evidence_bookmarks",
        type_="unique",
    )
    op.drop_constraint(
        "uq_evidence_bookmarks_entity",
        "evidence_bookmarks",
        type_="unique",
    )
    op.drop_constraint(
        "ck_evidence_bookmarks_link",
        "evidence_bookmarks",
        type_="check",
    )
    op.create_check_constraint(
        "ck_evidence_bookmarks_link",
        "evidence_bookmarks",
        "entity_id IS NOT NULL OR finding_id IS NOT NULL OR report_id IS NOT NULL",
    )
