# RavenTech OSINT Final Platform Freeze

## Freeze Identity

- Current version: `5.0.0-rc2`
- Validated code baseline: `97b7561` (`chore: freeze rc2 stability and validation`)
- Branch: `dev`
- Phase 5S scope: portfolio, demo, QA, screenshot, and pre-hosting planning
  documentation only

The Phase 5S packaging commit is the commit containing this document. The
application code baseline remains the Phase 5R commit above.

## Completed Modules

- Login, config-gated registration, session handling, RBAC, membership, and
  administrator user governance
- Dashboard, executive dashboard, Operations Center, investigations, targets,
  passive recon, findings, correlations, IOCs, Evidence Intelligence, and
  Threat Intelligence
- Engagement, authorization, and deterministic scope governance
- Optional AI Analysis with deterministic evidence-backed fallback
- Notes, tasks, bookmarks, playbooks, review board, remediation validation,
  case closure, deliverables, and evidence package manifest
- Analyst-reviewed report templates and HTML, Markdown, PDF, and DOCX exports
- Internal notifications, RBAC-aware Global Search, owner-scoped Saved Views,
  Data Quality Center, audit log, timeline, settings, feature flags, and
  health/readiness/release endpoints

## Tested Local Mode

The frozen, tested mode is local Docker Compose with FastAPI, PostgreSQL, Redis,
Celery, and a separately started Vite frontend. Demo data is synthetic. No
hosted environment, public DNS, Supabase database, or production secret set was
used or validated.

## Validation Status

At the Phase 5S baseline:

- `/health` and `/health/ready`: `status: ok`
- `/api/v1/release`: `5.0.0-rc2`
- Alembic: one current head, `0028_phase5p_quality`, with no schema drift
- pytest: 211 passed
- frontend TypeScript/Vite production build: passed
- Phase 5R ruff, strict mypy, and `pip check`: passed
- Git: clean and synchronized with `origin/dev` at the baseline commit

The full validation gate in `FINAL_QA_CHECKLIST.md` must pass again immediately
before the Phase 5S commit and push.

## Remaining Non-Blocking Warnings

- Upstream `passlib` imports Python's deprecated `crypt` module under Python
  3.12. Review the hashing dependency before Python 3.13; do not hide the
  warning or pin an insecure dependency.
- An empty local `REPORT_LOGO_PATH` produces an expected advisory and report
  exports use text branding.

## Known Limitations

- Passive, defensive OSINT only; no active scanning, exploitation, crawling, or
  autonomous offensive action
- AI is optional and provider failure uses deterministic fallback behavior
- Reports and deliverables require analyst review
- Public registration is disabled by default and must remain governed
- Local Docker Compose is the only validated runtime
- Production/free-tier hosting, DNS, and Supabase production migration are
  deferred
- External paid threat feeds and external search providers are not included

See `KNOWN_LIMITATIONS.md` for the complete list.

## What Is Frozen

- Public API contracts and database migration head
- Authentication, permissions, governance, and defensive-only boundaries
- Investigation, intelligence, reporting, closure, notification, search, and
  quality workflows
- `5.0.0-rc2` release identity
- Local Docker validation commands and the RC2 manual QA flow
- Portfolio narrative, screenshots list, and demo order

## What Must Not Change Before Hosting Review

- Do not add features, modules, providers, migrations, or frontend redesigns.
- Do not weaken RBAC, last-active-admin protection, scope checks, registration
  governance, report review, or audit behavior.
- Do not add active scanning, exploitation, crawling, payloads, or autonomous
  actions.
- Do not deploy, configure DNS, migrate to Supabase, replace backend auth with
  Supabase Auth, or add real credentials.
- Do not change dependencies, migrations, environment contracts, report storage,
  or worker topology without a separate reviewed phase and a full validation run.
- Accept only documented blocker/regression fixes; record and revalidate every
  such change before hosting planning resumes.
