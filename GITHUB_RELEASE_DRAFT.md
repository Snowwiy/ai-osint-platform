# RavenTech OSINT 5.0.0-rc3

## Release Summary

RavenTech OSINT `5.0.0-rc3` is a local-first release candidate for a defensive
investigation and intelligence workspace. This package freezes the tested local
Docker workflow and provides portfolio, demonstration, backup/restore, QA, and
security-review documentation. It should not be described as production-hosted
or production-certified.

## Key Capabilities

- Authentication, governed registration, RBAC, investigation membership, and
  last-active-administrator protection
- Dashboard, Operations Center, investigation lifecycle, engagement and scope
  governance, targets, passive recon, findings, and remediation workflow
- Correlation Cards/Graph/Table, IOCs, Evidence Intelligence, and Threat
  Intelligence
- Optional AI analysis with deterministic evidence-backed fallback
- Analyst-reviewed HTML, Markdown, PDF, and DOCX reports
- Review board, closure checklist, deliverables, and evidence package manifests
- Internal notifications, RBAC-aware Global Search, private Saved Views, Data
  Quality Center, audit log, governance settings, and release/health endpoints
- Local monitoring policies, maintenance windows, authorized LAN observations,
  endpoint enrollment, coverage, change history, alert triage, and advisory
  vulnerability baseline
- Guarded local backup, non-overwriting restore, synthetic demo seed/reset, and
  local health-repair tooling

## Validation Proof

- Ruff: passed
- mypy: passed across 214 backend source files
- pytest: 272 passed
- `pip check`: passed
- Alembic: one linear head, `0035_phase5ae_agents`, with no schema drift
- `/health` and `/health/ready`: `status: ok`
- `/api/v1/release`: `5.0.0-rc3`
- Frontend TypeScript/Vite production build: passed
- Local Docker services: healthy/running
- Phase 5V tracked-file secrets audit: no production secrets found

## Local Setup

Use [LOCAL_DEMO_BUNDLE.md](LOCAL_DEMO_BUNDLE.md) for the reproducible setup,
synthetic demo seed/reset, health checks, report walkthrough, validation
commands, and artifact checklist. Use
[FINAL_LOCAL_ACCEPTANCE.md](FINAL_LOCAL_ACCEPTANCE.md) and
[FINAL_QA_CHECKLIST.md](FINAL_QA_CHECKLIST.md) for detailed acceptance.

## Known Limitations

- Local Docker Compose is the only validated runtime.
- Hosting, deployment, DNS, and Supabase migration are not included.
- Public registration is disabled by default and requires explicit governance.
- AI configuration is optional; provider failure uses deterministic fallback.
- Demo data is synthetic, and every generated report requires analyst review.
- An upstream Passlib/Python `crypt` deprecation warning remains documented.
- Two moderate React Router advisories require a separately tested breaking v7
  migration; dynamic routes are constrained and this Vite SPA does not use SSR
  hydration.

See `KNOWN_LIMITATIONS.md` for the complete operational and product boundaries.

## Defensive-Only Disclaimer

RavenTech OSINT is intended for authorized passive collection, defensive
analysis, evidence management, governance, and reporting. It does not include
active scanning, exploitation, payload generation, web crawling, internet-wide
enumeration, or autonomous offensive actions.

## Release Handling

This file is release copy for review. Creating it does not create or publish a
GitHub release. The `v5.0.0-rc3` Git tag identifies the validated local release
candidate commit; any future GitHub release publication requires separate,
explicit authorization.
