# RavenTech OSINT Final Platform Freeze

## RC4 freeze identity

- Version: `5.0.0-rc4`
- Parent baseline: Phase 5AI commit `5012a9e`
- Branch: `dev`
- Intended release tag: `v5.0.0-rc4`, only after every RC4 gate passes
- Validated mode: local Docker Compose backend with local Vite frontend
- Database migration head: `0036_phase5ai_posture` (no Phase 5AJ migration)

Phase 5AJ freezes the bilingual completed local web application. Its only
product-surface change is English/Spanish localization and report-language
selection. It adds no unrelated module, provider, desktop wrapper, installer,
hosted environment, DNS configuration, or Supabase integration.

## Frozen product surface

The freeze includes governed authentication/RBAC; dashboards and operations;
investigation, scope, recon, findings, intelligence, remediation, review and
closure; reports and evidence exports; notifications, search, saved views,
data quality and audit; and the complete local Monitoring Center with LAN,
agents, policies, maintenance, triage, history, vulnerability baseline,
security posture, and manual recommendations.

English is the default UI/report language. Spanish can be selected explicitly,
persists locally, and falls back to English copy when a Spanish phrase is not
available. Internal logs and audit action identifiers are not translated.

## Security boundary

Monitoring remains authorized/local. Service checks are manual, bounded,
private-range constrained by default, and TCP-connect only. Agents and checks
never authenticate, collect credentials, execute remote commands, brute force,
send exploit payloads, or perform exploit validation. SSH/banner hints are
sanitized. Risk, vulnerability, posture, and remediation results are advisory.
Router/VLAN isolation guidance is manual; no router automation exists.

## Acceptance gate

`FINAL_QA_CHECKLIST.md` is authoritative. Validation must include backend lint,
typing, full tests, dependency and Alembic checks, live health/ready/release,
frontend localization tests and production build, and clean Git status. The
final evidence is recorded in `RELEASE_NOTES_RC4.md`.

## Deferred work

- Desktop packaging, Electron, Tauri, installers, and autostart
- Hosting, deployment, public DNS, and ingress
- Supabase database or authentication migration
- Public scanning, router automation, and offensive functionality

RC4 is a local release candidate, not a production deployment claim.
