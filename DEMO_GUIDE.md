# RavenTech OSINT Demo Guide

## Purpose

RavenTech OSINT is a defensive investigation workspace for authorized passive
recon, evidence-backed findings, remediation workflows, reporting, governance,
and analyst coordination.

The platform does not perform active scanning, exploitation, attack automation,
or internet-wide enumeration.

## Demo Mode

Demo mode is disabled by default.

Set the following only in a local or controlled demonstration environment:

```env
ENABLE_DEMO_MODE=true
```

Demo mode is ignored by the environment bootstrap when
`APP_ENVIRONMENT=production`. An administrator can also enable or disable it in
Admin Settings. Enabling the feature creates an idempotent synthetic workspace
containing:

- one clearly labeled demo investigation
- one clearly labeled demo engagement with approved synthetic scope
- reserved `.invalid` and TEST-NET target identifiers
- passive recon entities
- one evidence-backed defensive finding
- one remediation task
- one defensive playbook run
- one sample report
- closure checklist and client deliverables package metadata
- sample internal Activity Inbox notifications for review, scope, report, and
  governance workflows
- sample pinned saved views for high-risk findings, reports ready, scope
  warnings, and open investigations
- one local knowledge reference
- sample IOC and threat intelligence records
- analyst notes, bookmarks, and evidence-chain metadata

The dataset makes no live network requests and no compromise claims.

Prepare the idempotent workspace from PowerShell:

```powershell
docker compose exec -T backend python -m scripts.seed_demo_data
```

For a clean local reset, use the guarded wrapper. It takes a database safety
backup by default, clears only fixed synthetic records, and reseeds them:

```powershell
./scripts/local/reset_demo.ps1 -Confirmation RESET-DEMO
```

See `LOCAL_BACKUP_RESTORE.md` before clearing demo data. Do not use demo reset
against a hosted or production environment.

## Locked RC3 Demo Flow

Use this order for portfolio and local client-style demonstrations:

1. **Login:** Sign in as the existing demo administrator and state the
   defensive-only purpose.
2. **Dashboard:** Show posture, prioritized work, recent cases, and Quick Access.
3. **Demo investigation:** Open the clearly labeled synthetic investigation and
   show authorization, ownership, lifecycle, and navigation.
4. **Engagement and scope:** Review the linked engagement, approved scope,
   authorization metadata, and conservative scope handling.
5. **Recon and findings:** Show authorized synthetic targets, passive evidence,
   partial-source behavior, and deterministic findings.
6. **Correlations and IOCs:** Switch through Cards, Graph, and Table, then show
   IOC/Evidence/Threat Intelligence relationships.
7. **AI fallback:** Show a clear unavailable/degraded provider state alongside
   deterministic fallback analysis and citations.
8. **Reports:** Review template/readiness guidance and PDF, DOCX, HTML, and
   Markdown export controls.
9. **Closure and deliverables:** Show the checklist, approval, residual risk,
   deliverables, and evidence package manifest.
10. **Notifications and search:** Mark a synthetic Activity Inbox item read, use
    Ctrl+K Global Search, and open a pinned Saved View.
11. **Data Quality:** Show Dry run or scan results and a safe issue transition.
12. **Audit and governance:** Close with audit events, settings, feature/export
    controls, then open **Monitoring** to show local service health, container
    telemetry, RBAC-scoped Asset Watch, and `5.0.0-rc4` release metadata.

Detailed presenter language is in `PORTFOLIO_DEMO_FLOW.md`.

## RC3 Stability Demo Pass

Before presenting, walk through these quick checks:

- Login with a known bad password and confirm the message is simple.
- Open Dashboard, Threat Intelligence, Reports, Admin Audit, and Settings.
- Confirm loading and empty states are clear and do not show raw endpoints.
- Generate a report and download PDF, DOCX, HTML, and Markdown.
- Open a long IOC, URL, report ID, or audit metadata value and confirm it wraps
  or can be copied.
- Confirm optional provider failures are shown as degraded, not total platform
  failure.
- Use the investigation tabs at laptop and narrow widths and confirm the active
  section scrolls into view without moving the full page horizontally.
- Open an Activity Inbox action, a Global Search result, and a Data Quality
  issue link and confirm each stays inside the authenticated workspace.
- Confirm `GET /api/v1/release` shows `5.0.0-rc4` or the explicitly configured
  version.
- Open Monitoring and confirm service cards, system metrics, alerts, and the
  synthetic investigation load without raw errors. Docker may show unavailable
  because the application intentionally has no Docker socket access.

## Safer Demo Defaults

- Use only the bundled synthetic investigation for public demonstrations.
- Do not enter customer targets without written authorization.
- Use Engagements to show client context, authorization status, approved scope,
  and conservative out-of-scope warnings.
- Keep provider API keys empty unless the demonstration explicitly requires a
  configured provider.
- Do not enable demo mode in production.
- Review report export and redaction controls before downloading files.
- Use Activity Inbox for internal workflow visibility only. No email, SMS, push,
  or external chat delivery is part of the demo.
- Use Global Search for internal records only. It does not browse the internet,
  crawl targets, or call an external search provider.

## Data Quality Demo

Open **Admin > Data Quality** and run **Dry run** first. Explain that RavenTech
checks consistency locally and recommends analyst actions without modifying
investigations, findings, reports, evidence, users, or authorization records.
Run **Run scan** to persist the report, open an issue, and demonstrate its
acknowledge or resolve audit trail.

The synthetic workspace includes clearly labeled educational quality records.
They are idempotent and removed by demo clear.

## Common Local Issues

- **Backend shows degraded:** Open the health panel. Optional AI availability
  does not prevent deterministic case, recon, finding, or report workflows.
- **Migration warning:** Run `docker compose run --rm backend alembic upgrade head`.
- **Demo workspace not ready:** Enable demo mode, then use **Prepare demo
  workspace** on the Demo Checklist page.
- **Export unavailable:** Review Admin Settings export controls and report
  storage health.
- **Raw endpoint visible:** Open the expanded technical details only when
  debugging; normal user-facing copy should stay concise.

See `FINAL_LOCAL_ACCEPTANCE.md` for the locked QA flow and `RELEASE_NOTES_RC3.md` for
release-candidate scope, validation status, and known limitations.

The currently validated demo runtime is local Docker Compose. Hosting, DNS, and
Supabase migration are deferred, and no production secrets are required for the
local synthetic walkthrough.
