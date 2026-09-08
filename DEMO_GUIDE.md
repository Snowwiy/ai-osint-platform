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

## Recommended Demo Flow

1. Sign in as an administrator.
2. Open **Admin > Demo Checklist** and review platform health.
3. Enable **Defensive demo mode** in **Admin > Settings** if required.
4. Prepare and open the synthetic demo investigation.
5. Review its linked engagement, approved scope, authorization metadata,
   passive recon entities, and finding.
6. Show remediation ownership and defensive playbook progress.
7. Open **Closure** and review the checklist, deliverables, and evidence package
   readiness.
8. Open **Activity Inbox** and show internal alerts for pending review, report
   readiness, scope reminders, and governance actions.
9. Use **Global Search** to jump to the demo finding or report, then show a
   pinned saved view in dashboard Quick Access.
10. Generate a report using the template suited to the audience.
11. Download PDF, DOCX, HTML, and Markdown formats allowed by governance.
12. Search the local defensive knowledge library.
13. Show the audit trail and explain that demo records are clearly labeled.

## V1 10-Minute Portfolio Flow

1. **Login:** Sign in and point out clean auth handling.
2. **Dashboard overview:** Show portfolio posture, high-risk work, and health.
3. **Open or create investigation:** Explain authorized scope and ownership.
4. **Add authorized target:** Add a domain, IP, or URL that is in scope.
5. **Run passive recon:** Show stored evidence and partial-source warnings.
6. **Generate findings:** Review deterministic evidence-backed findings.
7. **Review defensive intelligence:** Show MITRE, Sigma, coverage, and guidance.
8. **Create remediation/playbook:** Assign analyst-owned next steps.
9. **Prepare closure:** Show final checklist, deliverables, and package manifest.
10. **Review Activity Inbox:** Show pending workflow alerts and mark one read.
11. **Search and navigate:** Use Ctrl+K Global Search, load a saved view, and
    show dashboard Quick Access.
12. **Generate executive report:** Download PDF/DOCX/HTML/Markdown as allowed.
13. **Governance close:** Show audit log, settings, feature flags, and exports.

## Release Candidate Stability Demo Pass

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
- Confirm `GET /api/v1/release` shows `5.0.0-rc1` or the configured version.

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

See `RELEASE_NOTES_RC1.md` for release-candidate scope, validation commands,
and upgrade notes.
