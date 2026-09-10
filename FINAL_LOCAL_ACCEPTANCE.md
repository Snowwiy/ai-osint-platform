# RavenTech OSINT Final Local Acceptance

Release candidate: `5.0.0-rc3`

Validated mode: local Docker Compose services with a local Vite frontend.

## Automated validation proof

The Phase 5AH gate completed on 2026-09-10:

- Ruff: passed
- Strict mypy: passed across 214 source files
- Pytest: 272 passed; one documented upstream Passlib deprecation warning
- `pip check`: no broken requirements
- Alembic: no new upgrade operations; current/head `0035_phase5ae_agents`
- `/health` and `/health/ready`: HTTP 200 with `status: ok`
- `/api/v1/release`: HTTP 200 with `5.0.0-rc3` and no secret fields
- Frontend TypeScript/Vite production build: passed

## Completed local capabilities

- Authentication, governed registration, admin user management, RBAC, and audit
- Dashboard, Operations Center, investigations, targets, passive recon,
  findings, intelligence, review, remediation, closure, and deliverables
- HTML, Markdown, PDF, and DOCX report generation with analyst review
- Notifications, alert triage, Global Search, Saved Views, Data Quality Center,
  governance settings, health, readiness, and release metadata
- Local monitoring policies, maintenance windows, alert cooldown/dedupe,
  advisory vulnerability baseline, and change timeline
- Authorized private-LAN inventory, manual TCP-connect service checks, service
  history, sanitized SSH hints, endpoint enrollment, asset groups, expected
  services, and coverage summaries

## Local monitoring acceptance boundary

LAN monitoring and service checks are configuration-gated and disabled by
default. Checks are manual, rate limited, limited to configured ports, and
restricted to explicitly authorized private assets/ranges. They perform TCP
connects and a minimal sanitized banner hint only. They never authenticate,
test credentials, brute force, execute commands, exploit, or scan the public
internet.

Docker may not expose host LAN neighbors. This is an informational coverage
limitation, not a platform-health failure. Use approved static/router
observations or a manually run endpoint agent when needed.

## Endpoint agent acceptance boundary

An administrator creates an expiring enrollment credential. Plaintext is shown
once; only its hash is retained, and revoked, expired, exhausted, invalid, or
CIDR-mismatched credentials are rejected. The agent must be started manually.
It collects basic CPU, memory, disk, uptime, OS, and service observation data
only and provides no persistence, remote shell, remote commands, file access,
browser-history access, password access, keystroke access, or credential access.

## Reports and evidence

Reports can be reviewed and exported locally as PDF, DOCX, HTML, and Markdown.
Engagement, authorization, scope, evidence, findings, remediation, closure, and
deliverable context remain visible. Monitoring and baseline content is advisory
and must not be presented as proof of compromise or exploitability.

## Known non-blocking warnings

- Optional passive providers may be unavailable; successful entities are
  preserved and partial enrichment can be retried safely.
- Optional host telemetry and Docker neighbor visibility may be unavailable
  while required platform dependencies remain healthy.
- The password-hashing dependency emits an upstream Python `crypt` deprecation
  warning; review it before Python 3.13.
- Local report branding may use the text fallback when no logo path is set.

## Manual acceptance checklist

1. Start the local platform and apply the current migration head.
2. Verify `/health`, `/health/ready`, and `/api/v1/release` report healthy RC3.
3. Verify registration policy, login, logout, and clean invalid-login handling.
4. Open every main navigation page and confirm no raw errors or crash screen.
5. Run authorized passive target recon with test data.
6. Confirm partial provider failures show valid stored results and safe retry.
7. Review TCP service observations separately from recon URL/service entities.
8. Open every Monitoring Center tab and verify loading, empty, and refresh states.
9. Create and revoke a test enrollment credential; confirm one-time reveal.
10. Review advisory vulnerability-baseline indicators and remediation context.
11. Review alert triage, dedupe, recovery, suppression, and maintenance behavior.
12. Export a reviewed report in PDF, DOCX, HTML, and Markdown.
13. Run a bounded Data Quality scan and review its non-destructive results.
14. Verify audit records for the exercised governed actions contain no secrets.
15. Confirm there are no raw endpoint errors, stack traces, clipped controls,
    horizontal overflow, or React crash screens.

Record completion in `FINAL_QA_CHECKLIST.md`. Any failed required item blocks
the RC3 release commit and tag.

## Deferred after RC3

Desktop packaging (including Electron, Tauri, and installers) and free-tier or
production hosting are deferred. Deployment, DNS, and Supabase migration are
also deferred. RC3 is a completed and validated local web release candidate;
it does not claim a production deployment.
