# RavenTech OSINT Final Local Acceptance

Release candidate: `5.0.0-rc4`

Validated mode: local Docker Compose services with a local Vite frontend.

## Completed local capabilities

- English and professional Spanish UI with an explicit language switcher,
  persisted browser preference, and English fallback for missing copy
- Authentication, governed registration, admin user management, RBAC, audit,
  dashboards, operations, investigations, targets, passive recon, findings,
  intelligence, review, remediation, closure, and deliverables
- English or Spanish analyst-reviewed HTML, Markdown, PDF, and DOCX reports
- Notifications, alert triage, Global Search, Saved Views, Data Quality Center,
  governance settings, health, readiness, and release metadata
- Monitoring policies, maintenance windows, cooldown/dedupe, change timeline,
  vulnerability baseline, endpoint posture, and remediation recommendations
- Authorized private-LAN inventory, manual TCP-connect service checks, service
  history, sanitized SSH hints, endpoint enrollment, asset groups, expected
  services, coverage summaries, and advisory posture scoring
- Local launcher scripts and a read-only Operator Console for health,
  readiness, release, Docker service status, local URLs, LAN flags, agent
  coverage, and backup/agent command guidance

## Localization acceptance

English remains the default. A user can choose English or Spanish from both the
sign-in screen and authenticated shell. The choice is retained in local browser
storage and contains no credential or secret. Missing Spanish copy displays its
professional English source rather than a raw translation key.

Reports have an independent English/Spanish selection. Their language is stored
as non-sensitive report metadata and retained for retries and PDF, DOCX, HTML,
and Markdown downloads. Logs and audit event identifiers remain stable English
internal identifiers.

## Monitoring and agent boundary

LAN monitoring and service checks are disabled by default, manual, rate limited,
restricted to configured authorized private assets/ranges, and TCP-connect only.
They never authenticate, test credentials, brute force, execute commands,
exploit, or scan the public internet. Docker neighbor visibility can be limited;
that is an informational coverage limitation, not a platform-health failure.

Endpoint credentials are revealed once and retained only as hashes. Agents are
started manually and collect bounded system/posture signals only. They provide
no persistence, remote shell, remote command, file/password/browser-history/
keystroke collection, or automatic remediation. Posture, service, and baseline
results are advisory risk indicators and never proof of compromise.

## Known non-blocking warnings

- Optional passive providers may fail; valid stored entities remain usable and
  partial enrichment can be retried safely.
- Optional host telemetry and Docker neighbor visibility can be unavailable
  while required platform dependencies remain healthy.
- Passlib emits an upstream Python `crypt` deprecation warning before Python
  3.13; it does not fail the current validation suite.
- Missing local report branding uses the safe text fallback.

## Manual acceptance checklist

1. Start the local platform and apply migration head `0036_phase5ai_posture`.
2. Verify health, readiness, and release endpoints report healthy RC4.
3. Switch English/Spanish at sign-in, refresh, and confirm the choice persists.
4. Login/register and open every main navigation page in both languages.
5. Confirm missing translations fall back to English without raw keys.
6. Run authorized passive recon and review partial-warning copy in both languages.
7. Review service observations separately from recon URL/service entities.
8. Open every Monitoring Center tab and review posture/recommendations.
9. Create/revoke a test enrollment credential and confirm one-time reveal.
10. Generate English and Spanish reports and export PDF/DOCX/HTML/Markdown.
11. Review notifications, triage, search, saved views, data quality, and audit.
12. Confirm no raw errors, secrets, crash screen, clipped controls, or overflow.
13. From **Operations**, refresh the Local Operator Console and verify commands
    are copy-only; run `check_platform.ps1` manually when needed.

## Automated validation proof

The RC4 gate passed Ruff, strict mypy across 217 source files, all 279 backend
tests, three frontend localization contract tests, dependency and schema-drift
checks, live health/readiness/release probes, and the frontend production build.
Database current/head is `0036_phase5ai_posture`; the release endpoint reports
`5.0.0-rc4`. The only warning is the documented upstream Passlib deprecation.

## Deferred after RC4

Desktop packaging, Electron, Tauri, installers, free-tier/production hosting,
deployment, DNS, and Supabase migration remain deferred. RC4 is a completed
local web release candidate and does not claim production deployment.
