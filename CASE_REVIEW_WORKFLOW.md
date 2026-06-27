# Case Review Workflow

RavenTech OSINT case review workflows help analysts move an authorized
investigation from evidence collection to formal review, remediation validation,
report approval, and governed closure.

The workflow is defensive and analyst-driven. It does not perform active
checking, exploitation, autonomous decisions, or external ticketing actions.

## Review Lifecycle

Investigation review statuses:

- `not_submitted`
- `pending_review`
- `changes_requested`
- `approved`
- `rejected`
- `closed`

Analysts can submit cases for review. Reviewers, investigation owners, and
platform admins can approve, reject, or request changes. Closed cases become
read-only for non-owner analysts and viewers.

## Review Checklist

The case review checklist is deterministic and based on stored records:

- Authorization statement exists.
- Targets exist.
- Passive recon was executed.
- Findings were generated.
- Evidence is linked.
- Remediation was reviewed.
- Reports were generated.
- Audit trail exists.
- No unresolved critical or high blockers unless accepted risk is documented.
- Executive summary exists.

Each checklist item is classified as:

- `passed`
- `warning`
- `failed`
- `not_applicable`

## Evidence Completeness Scoring

Evidence completeness is scored from 0 to 100.

Inputs:

- Target count
- Recon entity count
- Finding count
- Citation count
- Evidence chains
- Bookmarks
- Notes
- Reports
- Remediation tasks

Labels:

- `incomplete`
- `partial`
- `adequate`
- `strong`
- `complete`

The score is only a readiness indicator. It does not claim that risk has been
eliminated.

## Report Approval

Report approval statuses:

- `draft`
- `pending_approval`
- `approved`
- `rejected`
- `archived`

Analysts can submit reports for approval. Reviewers, owners, and admins can
approve or reject reports. Rejected reports preserve the rejection reason.
Archived reports preserve approval metadata.

## Remediation Validation

Remediation validation statuses:

- `not_validated`
- `validation_pending`
- `validated`
- `validation_failed`
- `accepted_risk`

Validation is documentation and analyst review only. It does not perform active
testing or vulnerability verification.

## Closure Workflow

Before closure, analysts should review:

- Unresolved critical or high findings
- Pending remediation
- Unapproved reports
- Missing executive summary
- Incomplete evidence

Closure is allowed when the case review is approved. Owners and platform admins
can override closure with a documented reason.

## RBAC Rules

Viewer:

- Read-only.

Analyst:

- Submit case review.
- Submit reports for approval.
- Submit remediation validation.

Reviewer, owner, admin:

- Approve, reject, or request changes.
- Validate remediation.
- Close cases.

Platform admin:

- Override closure with a reason.

## Audit And Timeline

Workflow actions create audit events and timeline entries:

- `case.review_submitted`
- `case.review_approved`
- `case.review_rejected`
- `case.changes_requested`
- `case.closed`
- `case.closure_overridden`
- `report.approval_submitted`
- `report.approved`
- `report.rejected`
- `remediation.validation_submitted`
- `remediation.validated`
- `remediation.validation_failed`
- `remediation.accepted_risk`

## Limitations

- No autonomous decisions.
- No active validation.
- No external ticketing integration.
- No offensive workflows.
- Evidence completeness is a readiness signal, not a guarantee.

