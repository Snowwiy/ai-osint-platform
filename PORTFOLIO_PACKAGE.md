# RavenTech OSINT Portfolio Package

## Professional Summary

RavenTech OSINT is a local-first defensive intelligence and investigation
workspace for authorized security assessments. It turns passive evidence into
structured findings, analyst-owned remediation, governed case records, and
stakeholder-ready reports while preserving scope, permissions, and audit
context.

Current release candidate: `5.0.0-rc6`.

## Problem Solved

External-exposure reviews often fragment authorization records, evidence,
findings, remediation work, approvals, and reports across unrelated tools. This
project demonstrates a repeatable workflow that keeps those records connected
and reviewable without introducing active scanning or offensive automation.

## Architecture Summary

The React/Vite/TypeScript frontend consumes a FastAPI API. The backend owns
authorization, workflow rules, deterministic analysis, report generation, and
audit logging. PostgreSQL stores authoritative records, Redis supports runtime
coordination, and Celery provides the background-worker foundation. Alembic
maintains a single linear schema history.

## Technology Stack

- React, TypeScript, Vite, Tailwind CSS, TanStack Query
- FastAPI, Pydantic, async SQLAlchemy, Alembic
- PostgreSQL, Redis, Celery
- pytest, ruff, strict mypy, ESLint, TypeScript, GitHub Actions
- Jinja2, ReportLab, and DOCX tooling for analyst-reviewed exports

## Security And Defensive Scope

The platform is intentionally defensive and designed for authorized, passive
work. Backend RBAC and investigation membership are the security boundary.
Registration is configuration-gated, administrators are protected from removing
the last active admin, internal search is permission-aware, saved views are
owner-scoped, and operational metadata is sanitized. No active scanning,
exploitation, crawling, payload generation, or autonomous offensive action is
included.

## Main Features

- Authentication, registration governance, admin users, and audit trail
- Investigations, engagements, authorization/scope, targets, and passive recon
- Evidence-backed findings, correlations, IOCs, and defensive threat workspace
- Optional AI analysis with deterministic fallback and citations
- Tasks, playbooks, remediation validation, review board, closure, deliverables,
  and evidence package manifest
- Executive/technical reporting with HTML, Markdown, PDF, and DOCX export
- Dashboard, Operations Center, notifications, Global Search, Saved Views, and
  Data Quality Center
- Health, readiness, release metadata, feature flags, and governance settings

## Screenshots Needed

Capture the complete set in `SCREENSHOTS_CHECKLIST.md`, using only synthetic
demo data. The strongest portfolio sequence is login, dashboard, investigation,
engagement/scope, recon/findings, correlations/IOCs, AI fallback, reports,
closure/deliverables, notifications/search, Data Quality, and audit/governance.

## Demo Script Summary

Use the 12-step flow in `PORTFOLIO_DEMO_FLOW.md`. Lead with authorization and
the problem solved, show evidence flowing into findings and reports, demonstrate
provider-independent fallback, and close with governance and validation proof.
Keep the walkthrough to approximately ten minutes and avoid live external data.

## Validation Proof

- 272 deterministic backend tests passed in local Docker Compose
- ruff, strict mypy, and `pip check` passed
- frontend TypeScript/Vite production build passed
- `/health` and `/health/ready` returned `ok`
- `/api/v1/release` returned `5.0.0-rc6`
- Alembic reported one current linear head with no model/schema drift
- CI uses local PostgreSQL/Redis and requires no live AI, Supabase, hosting, or
  production credentials

These checks support an RC3 portfolio/demo claim, not a production-hosting
claim. Manual QA remains required before any future hosting work.

## GitHub Presentation Notes

- Pin `README.md`, `PORTFOLIO_PACKAGE.md`, `RELEASE_NOTES_RC3.md`, and the
  screenshot assets near the top of the repository narrative.
- Use concise image captions that state the workflow and defensive control being
  demonstrated.
- Link to `FINAL_PLATFORM_FREEZE.md`, `FINAL_LOCAL_ACCEPTANCE.md`, and
  `FINAL_QA_CHECKLIST.md` as validation evidence.
- Describe the code as a release candidate validated locally; do not claim SLA,
  production deployment, customer operation, or legal/compliance certification.
- Call out synthetic demo data and analyst review wherever reports or threat
  context are shown.
- Keep future hosting architecture in `FREE_TIER_HOSTING_OPTIONS.md` clearly
  labeled as research and deferred planning.
