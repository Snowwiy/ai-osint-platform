"""Phase 4C defensive playbooks and remediation workflows.

Revision ID: 0012_phase4c_defensive_playbooks
Revises: 0011_phase4b_collaboration_rbac
Create Date: 2026-06-14

"""
from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_phase4c_defensive_playbooks"
down_revision: str | None = "0011_phase4b_collaboration_rbac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PLAYBOOKS = (
    {
        "id": uuid.UUID("10000000-0000-4000-8000-000000000001"),
        "name": "DNS Email Security Review",
        "description": (
            "Validate SPF and DMARC posture, document ownership, and coordinate "
            "defensive email-domain remediation."
        ),
        "category": "dns_email_security",
        "severity": "medium",
        "framework": "NIST CSF",
        "is_active": True,
    },
    {
        "id": uuid.UUID("10000000-0000-4000-8000-000000000002"),
        "name": "Public Exposure Review",
        "description": (
            "Review stored public-service evidence, confirm business need, and "
            "track defensive exposure reduction."
        ),
        "category": "exposure_review",
        "severity": "high",
        "framework": "CIS Controls",
        "is_active": True,
    },
    {
        "id": uuid.UUID("10000000-0000-4000-8000-000000000003"),
        "name": "Technology Disclosure Review",
        "description": (
            "Validate disclosed technology metadata and document secure "
            "configuration or disclosure-reduction actions."
        ),
        "category": "technology_review",
        "severity": "low",
        "framework": "OWASP Top 10",
        "is_active": True,
    },
    {
        "id": uuid.UUID("10000000-0000-4000-8000-000000000004"),
        "name": "Evidence Validation Review",
        "description": (
            "Confirm provenance, confidence, scope, and analyst interpretation "
            "before evidence supports a decision."
        ),
        "category": "report_review",
        "severity": "info",
        "framework": "DFIR",
        "is_active": True,
    },
    {
        "id": uuid.UUID("10000000-0000-4000-8000-000000000005"),
        "name": "Remediation Verification Checklist",
        "description": (
            "Verify remediation evidence, record stakeholder approval, and "
            "complete defensive closure checks."
        ),
        "category": "remediation_tracking",
        "severity": "medium",
        "framework": "NIST CSF",
        "is_active": True,
    },
)

_STEP_DEFINITIONS = (
    (
        1,
        (
            (
                "Review stored DNS evidence",
                "Confirm the stored SPF and DMARC observations are current and "
                "associated with the authorized domain.",
                "Documented DNS evidence assessment.",
                "evidence_validation",
            ),
            (
                "Document email security gap",
                "Record the defensive impact, affected mail domain, and expected "
                "policy posture with the domain owner.",
                "Approved remediation scope.",
                "analyst_review",
            ),
            (
                "Track policy remediation",
                "Create or link a remediation task for the authorized owner. Do "
                "not execute external changes from this platform.",
                "Owned remediation task with due date.",
                "remediation_task",
            ),
            (
                "Verify and close",
                "Review submitted evidence and record whether the expected SPF or "
                "DMARC posture was validated.",
                "Verification note and closure decision.",
                "closure_check",
            ),
        ),
    ),
    (
        2,
        (
            (
                "Validate exposure evidence",
                "Confirm the stored service and infrastructure evidence belongs "
                "to the investigation scope.",
                "Validated asset and service context.",
                "evidence_validation",
            ),
            (
                "Confirm business requirement",
                "Ask the asset owner to document whether the public exposure is "
                "required and which controls protect it.",
                "Business owner decision and control summary.",
                "stakeholder_review",
            ),
            (
                "Plan defensive remediation",
                "Track removal, restriction, hardening, or accepted-risk review "
                "as an analyst-approved task.",
                "Remediation task and accountable owner.",
                "remediation_task",
            ),
            (
                "Verify exposure outcome",
                "Validate submitted defensive evidence and record the final "
                "disposition without initiating scanning.",
                "Verification evidence and disposition.",
                "closure_check",
            ),
        ),
    ),
    (
        3,
        (
            (
                "Validate technology attribution",
                "Confirm that stored headers or metadata support the technology "
                "attribution and note confidence limitations.",
                "Technology evidence assessment.",
                "evidence_validation",
            ),
            (
                "Review disclosure risk",
                "Document whether version or platform disclosure increases "
                "defensive exposure for the authorized asset.",
                "Analyst risk statement.",
                "analyst_review",
            ),
            (
                "Track secure configuration",
                "Create or link a configuration-hardening task for the responsible "
                "team when remediation is approved.",
                "Configuration task or accepted-risk record.",
                "remediation_task",
            ),
            (
                "Update technical record",
                "Record the validated outcome and supporting references for the "
                "next technical report.",
                "Report-ready analyst note.",
                "report_update",
            ),
        ),
    ),
    (
        4,
        (
            (
                "Confirm provenance",
                "Review evidence source, timestamp, target scope, and collection "
                "method using only stored investigation data.",
                "Evidence provenance statement.",
                "evidence_validation",
            ),
            (
                "Assess confidence",
                "Record confidence limitations and whether additional analyst "
                "review is needed.",
                "Confidence and limitation note.",
                "analyst_review",
            ),
            (
                "Record validation decision",
                "Mark the evidence as validated, dismissed, or pending review and "
                "document the reasoning.",
                "Auditable evidence decision.",
                "closure_check",
            ),
        ),
    ),
    (
        5,
        (
            (
                "Review remediation evidence",
                "Confirm submitted remediation evidence maps to the finding and "
                "authorized affected asset.",
                "Evidence-to-finding verification note.",
                "evidence_validation",
            ),
            (
                "Confirm stakeholder approval",
                "Record the accountable owner or reviewer approval for closure or "
                "accepted risk.",
                "Stakeholder approval record.",
                "stakeholder_review",
            ),
            (
                "Update report context",
                "Add the remediation outcome and remaining risk to the stored "
                "technical and executive context.",
                "Report-ready remediation summary.",
                "report_update",
            ),
            (
                "Complete closure check",
                "Verify all required steps are complete and record the final "
                "defensive disposition.",
                "Final closure decision.",
                "closure_check",
            ),
        ),
    ),
)


def upgrade() -> None:
    op.create_table(
        "defensive_playbooks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column(
            "severity",
            sa.String(length=20),
            server_default="info",
            nullable=False,
        ),
        sa.Column("framework", sa.String(length=100), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "category IN ("
            "'exposure_review', 'dns_email_security', 'infrastructure_review', "
            "'technology_review', 'access_control', 'report_review', "
            "'remediation_tracking'"
            ")",
            name="ck_defensive_playbooks_category",
        ),
        sa.CheckConstraint(
            "severity IN ('info', 'low', 'medium', 'high', 'critical')",
            name="ck_defensive_playbooks_severity",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_defensive_playbooks_name"),
    )
    op.create_index(
        "idx_defensive_playbooks_category",
        "defensive_playbooks",
        ["category"],
    )
    op.create_index(
        "idx_defensive_playbooks_active",
        "defensive_playbooks",
        ["is_active"],
    )

    op.create_table(
        "playbook_steps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("playbook_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("expected_output", sa.Text(), nullable=True),
        sa.Column("step_type", sa.String(length=30), nullable=False),
        sa.Column(
            "required",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "step_type IN ("
            "'analyst_review', 'evidence_validation', 'remediation_task', "
            "'report_update', 'stakeholder_review', 'closure_check'"
            ")",
            name="ck_playbook_steps_type",
        ),
        sa.ForeignKeyConstraint(
            ["playbook_id"],
            ["defensive_playbooks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "playbook_id",
            "order_index",
            name="uq_playbook_steps_order",
        ),
    )
    op.create_index(
        "idx_playbook_steps_playbook",
        "playbook_steps",
        ["playbook_id"],
    )

    op.create_table(
        "playbook_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("playbook_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="open",
            nullable=False,
        ),
        sa.Column("started_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("completed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "started_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'blocked', 'completed', 'cancelled')",
            name="ck_playbook_runs_status",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["findings.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["playbook_id"],
            ["defensive_playbooks.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["started_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["completed_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in (
        ("idx_playbook_runs_investigation", ["investigation_id"]),
        ("idx_playbook_runs_finding", ["finding_id"]),
        ("idx_playbook_runs_playbook", ["playbook_id"]),
        ("idx_playbook_runs_status", ["status"]),
    ):
        op.create_index(name, "playbook_runs", columns)

    op.create_table(
        "playbook_run_steps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("playbook_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("playbook_step_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("analyst_note", sa.Text(), nullable=True),
        sa.Column("completed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "completed_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'skipped')",
            name="ck_playbook_run_steps_status",
        ),
        sa.ForeignKeyConstraint(
            ["playbook_run_id"],
            ["playbook_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["playbook_step_id"],
            ["playbook_steps.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["completed_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "playbook_run_id",
            "playbook_step_id",
            name="uq_playbook_run_steps_step",
        ),
    )
    op.create_index(
        "idx_playbook_run_steps_run",
        "playbook_run_steps",
        ["playbook_run_id"],
    )

    op.add_column(
        "findings",
        sa.Column(
            "remediation_status",
            sa.String(length=30),
            server_default="not_started",
            nullable=False,
        ),
    )
    op.add_column(
        "findings",
        sa.Column("remediation_owner", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "findings",
        sa.Column("remediation_due_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "findings",
        sa.Column("verification_notes", sa.Text(), nullable=True),
    )
    op.add_column(
        "findings",
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "findings",
        sa.Column(
            "verified_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_findings_remediation_status",
        "findings",
        "remediation_status IN ("
        "'not_started', 'validating', 'remediation_planned', 'in_progress', "
        "'pending_verification', 'remediated', 'accepted_risk', 'false_positive'"
        ")",
    )
    op.create_foreign_key(
        "fk_findings_remediation_owner_users",
        "findings",
        "users",
        ["remediation_owner"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_findings_verified_by_users",
        "findings",
        "users",
        ["verified_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_findings_remediation_status",
        "findings",
        ["remediation_status"],
    )
    op.create_index(
        "idx_findings_remediation_owner",
        "findings",
        ["remediation_owner"],
    )
    _seed_playbooks()


def downgrade() -> None:
    op.drop_index("idx_findings_remediation_owner", table_name="findings")
    op.drop_index("idx_findings_remediation_status", table_name="findings")
    op.drop_constraint(
        "fk_findings_verified_by_users",
        "findings",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_findings_remediation_owner_users",
        "findings",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_findings_remediation_status",
        "findings",
        type_="check",
    )
    for column in (
        "verified_at",
        "verified_by",
        "verification_notes",
        "remediation_due_date",
        "remediation_owner",
        "remediation_status",
    ):
        op.drop_column("findings", column)
    op.drop_index("idx_playbook_run_steps_run", table_name="playbook_run_steps")
    op.drop_table("playbook_run_steps")
    for name in (
        "idx_playbook_runs_status",
        "idx_playbook_runs_playbook",
        "idx_playbook_runs_finding",
        "idx_playbook_runs_investigation",
    ):
        op.drop_index(name, table_name="playbook_runs")
    op.drop_table("playbook_runs")
    op.drop_index("idx_playbook_steps_playbook", table_name="playbook_steps")
    op.drop_table("playbook_steps")
    op.drop_index("idx_defensive_playbooks_active", table_name="defensive_playbooks")
    op.drop_index(
        "idx_defensive_playbooks_category",
        table_name="defensive_playbooks",
    )
    op.drop_table("defensive_playbooks")


def _seed_playbooks() -> None:
    playbook_table = sa.table(
        "defensive_playbooks",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("category", sa.String()),
        sa.column("severity", sa.String()),
        sa.column("framework", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    step_table = sa.table(
        "playbook_steps",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("playbook_id", postgresql.UUID(as_uuid=True)),
        sa.column("order_index", sa.Integer()),
        sa.column("title", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("expected_output", sa.Text()),
        sa.column("step_type", sa.String()),
        sa.column("required", sa.Boolean()),
    )
    op.bulk_insert(playbook_table, list(_PLAYBOOKS))
    rows: list[dict[str, object]] = []
    for playbook_number, steps in _STEP_DEFINITIONS:
        playbook_id = _PLAYBOOKS[playbook_number - 1]["id"]
        for order_index, step in enumerate(steps, start=1):
            title, description, expected_output, step_type = step
            rows.append(
                {
                    "id": uuid.UUID(
                        f"20000000-0000-4000-8{playbook_number:03d}-"
                        f"{order_index:012d}"
                    ),
                    "playbook_id": playbook_id,
                    "order_index": order_index,
                    "title": title,
                    "description": description,
                    "expected_output": expected_output,
                    "step_type": step_type,
                    "required": True,
                }
            )
    op.bulk_insert(step_table, rows)
