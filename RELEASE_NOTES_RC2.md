# RavenTech OSINT 5.0.0-rc2 Release Notes

Release name: RavenTech OSINT RC2 Stability Freeze

Version candidate: `5.0.0-rc2`

Release channel: release-candidate

## Summary

RC2 freezes the existing defensive investigation platform for final manual QA,
GitHub review, portfolio walkthroughs, local client-style demonstrations, and
pre-hosting review. It adds no major product area and does not claim production
hosting or production maturity.

## Major Capabilities Already Present

- Authentication, governed registration, RBAC, membership, and last-active-admin
  protection
- Dashboard, Operations Center, investigations, engagement/scope governance,
  passive recon, findings, Correlations Cards/Graph/Table, IOCs, Evidence
  Intelligence, and Threat Intelligence
- Optional AI analysis with deterministic evidence-backed fallback
- Executive dashboard, review board, remediation, closure, deliverables, and
  evidence package manifest
- Analyst-reviewed HTML, Markdown, PDF, and DOCX reports
- Internal notifications, RBAC-aware Global Search, owner-scoped Saved Views,
  Data Quality Center, audit log, timeline, governance settings, and feature flags
- Health, readiness, and non-secret release metadata endpoints

## Stability And UX Improvements

- Release metadata defaults now identify `5.0.0-rc2` consistently.
- Health failures return stable operational messages instead of raw dependency
  exception text.
- Investigation lifecycle rendering tolerates an unknown status from a partial
  or malformed API response without triggering a React crash.
- Existing safe defaults continue to protect major pages from missing arrays,
  invalid dates/numbers, malformed metadata, and unsafe internal routes.

## Test And CI Validation Status

- Targeted coverage now locks the RC2 release endpoint, readiness contract,
  sanitized health failures, and Alembic single-head/linear/storage-safe chain.
- Existing deterministic coverage continues to exercise auth/registration,
  admin safety, engagement scope, closure, deliverables, notifications, search,
  saved-view ownership, Data Quality transitions, report exports, and AI fallback.
- GitHub Actions uses local PostgreSQL and Redis services and does not require
  Anthropic, Supabase, hosting, external search, or production secrets.
- RC2 validation completed with ruff, strict mypy, 211 pytest tests, `pip check`,
  Alembic drift/head/current checks, frontend lint/build, live health/readiness,
  release metadata, Docker status, and backend log review passing.

## Known Non-Blocking Warning

`passlib` imports Python's deprecated standard-library `crypt` module. This is
an upstream warning under Python 3.12, does not block the RC2 test suite, and is
documented for review before Python 3.13. It is not hidden globally, and no
insecure dependency pin was introduced.

Local startup also reports an expected configuration advisory when
`REPORT_LOGO_PATH` is empty; exports use text branding. This is non-blocking and
does not expose a secret.

## Known Limitations

- Passive, defensive OSINT workflow only; no active scanning, exploitation, or
  autonomous offensive action
- No external paid threat feeds or external search providers
- AI provider configuration is optional; deterministic fallback remains
  available when it is missing or unavailable
- Local Docker Compose is the current tested mode
- Production/free-tier hosting, DNS, and Supabase production database migration
  are deferred
- Demo data is synthetic and makes no compromise claim
- Reports and deliverables require analyst review
- Public registration must be explicitly governed through configuration,
  invite/approval policy, and administrator review

See `KNOWN_LIMITATIONS.md` for full operational boundaries.

## Intentionally Not Included

RC2 does not include production deployment, hosting, VPS or Cloudflare setup,
DNS changes, Supabase Auth/database migration, new providers, crawling, active
scanning, exploitation, autonomous agents, billing, SSO/OAuth, or a frontend
redesign.

## Next Step After RC2

Complete `MANUAL_QA_RC2.md`, review the frozen diff on GitHub, and conduct the
portfolio/local demo walkthrough. Future free-tier deployment planning begins
only after RC2 acceptance; it is not part of this release.
