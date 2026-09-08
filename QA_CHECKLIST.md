# RavenTech OSINT Manual QA Checklist

## Authentication

- [ ] Wrong credentials display `Invalid username or password.`
- [ ] Correct credentials open the dashboard.
- [ ] A 401 after session expiry redirects to login.
- [ ] Normal UI errors do not expose raw endpoint or request identifiers.

## Platform Readiness

- [ ] `/health` returns structured component status.
- [ ] Admin Demo Checklist shows current and head migrations.
- [ ] Database, Redis, storage, and worker readiness are understandable.
- [ ] Optional AI unavailability is shown as degraded, not total failure.
- [ ] No secrets or provider keys appear in readiness responses.
- [ ] Dashboard, report, IOC, and admin pages do not refetch repeatedly while
      idle.
- [ ] Dashboard handles missing executive fields with a degraded or empty panel.
- [ ] Route-level page errors show the friendly fallback, not a raw React crash.

## Investigation Workflow

- [ ] Create an investigation with an authorization statement.
- [ ] Add an authorized domain, IP address, or URL target.
- [ ] Run passive recon and review partial-source warnings.
- [ ] Generate deterministic evidence-backed findings.
- [ ] Add a member and confirm role restrictions.
- [ ] Add a note, task, bookmark, and remediation update.
- [ ] Archive and restore the investigation.

## Reports

- [ ] Template descriptions, section previews, and recommended use differ.
- [ ] Quality warnings match the selected report type.
- [ ] Generate executive and technical reports.
- [ ] Download PDF, DOCX, HTML, and Markdown without false error banners.
- [ ] Export controls hide or reject disabled formats.
- [ ] Custom templates can be deactivated and restored.
- [ ] Report errors show a concise message with optional technical details.

## Case Closure And Deliverables

- [ ] Closure tab loads for an existing investigation.
- [ ] Closure checklist can be generated and refreshed.
- [ ] Checklist item status can be updated without raw endpoint errors.
- [ ] Closure can be submitted for review, approved, closed, and reopened by an
      allowed owner/admin.
- [ ] Closure without required checklist completion requires an explicit
      override reason.
- [ ] Deliverable records can be created, marked ready, approved, and archived.
- [ ] Package manifest generation returns included deliverables, missing
      deliverables, warnings, and evidence package readiness.
- [ ] Closure metadata appears in executive, technical, and evidence appendix
      reports.
- [ ] Closure and deliverable actions appear in audit and timeline views.

## Notifications And Activity Inbox

- [ ] Notification bell appears only after login.
- [ ] Unread count updates after marking an alert read.
- [ ] Activity Inbox loads with clear loading, empty, and error states.
- [ ] Filters by status, severity, and alert type work.
- [ ] Dismiss action works without raw endpoint errors.
- [ ] Mark all read updates unread count.
- [ ] Admin pending user approval alert links to Admin → Users.
- [ ] Closure review, report ready, deliverable ready, scope warning, and
      governance demo alerts appear after demo seed.
- [ ] Notification audit events appear for create, read, dismiss, and mark all
      read actions.
- [ ] No email, SMS, browser push, or chat delivery is implied in the UI.

## Governance And Audit

- [ ] Admin Settings loads for administrators only.
- [ ] Feature flags hide disabled UI and backend routes reject mutations.
- [ ] Retention settings show archive eligibility without destructive deletion.
- [ ] Audit filters work and an empty audit result is clear.
- [ ] Important workflow and export actions appear in audit.

## Data Quality And Maintenance

- [ ] Admin Data Quality Center loads; non-admin access is denied cleanly.
- [ ] Dry run reports recommendations and no destructive changes.
- [ ] Run scan persists bounded issues without changing source records.
- [ ] Severity, status, issue-type, and entity filters work.
- [ ] Issue detail wraps long values and exposes only safe metadata.
- [ ] Issues can be acknowledged, ignored, and resolved when allowed.
- [ ] Invalid issue transitions return a clean conflict response.
- [ ] Operations shows counts or a clean degraded quality panel.
- [ ] Stale notification maintenance requires confirmation and only soft-archives
      old read or dismissed notifications.
- [ ] Audit records scan, issue workflow, dry-run, and maintenance actions.
- [ ] Demo seed is idempotent and demo clear removes synthetic quality issues.

## Demo Mode

- [ ] Demo mode is off by default.
- [ ] Demo data is labeled `[DEMO]` or `Synthetic demo`.
- [ ] Demo targets use `.invalid` and TEST-NET identifiers.
- [ ] Demo setup is idempotent.
- [ ] Demo clear removes synthetic records and can be rerun safely.
- [ ] Disabling demo mode removes it from active work without deleting data.
- [ ] Production configuration does not bootstrap demo data.

## Knowledge And Navigation

- [ ] Knowledge Search states that it uses only local defensive content.
- [ ] Example searches work and references can be copied.
- [ ] Global Search opens with Ctrl+K and from the authenticated layout.
- [ ] Global Search returns only authorized investigations, findings, reports,
      engagements, notifications, IOCs, and threat intelligence objects.
- [ ] Non-admin users do not see admin user-management search results.
- [ ] Search result navigation opens the expected in-app route.
- [ ] Saved views can be created, loaded, pinned, unpinned, set as default, and
      deleted on investigations, findings, reports, notifications, and
      engagements.
- [ ] Dashboard Quick Access shows pinned saved views, recent investigations,
      and unread notification count.
- [ ] Search and saved-view actions appear in audit logs without secrets.
- [ ] Empty states explain the section and the next action.
- [ ] Sidebar remains scrollable at reduced viewport height.
- [ ] Long identifiers and report content remain readable.
- [ ] Threat Intelligence, IOC correlations, and dashboard widgets stay readable
      with long domains, URLs, and UUIDs.

## Production Readiness

- [ ] Manual backend validation commands pass.
- [ ] Manual frontend lint and build commands pass.
- [ ] `alembic check` reports no drift.
- [ ] Admin export controls and feature flags save without stale errors.
- [ ] Archive and restore flows do not expose destructive actions incorrectly.
- [ ] Frontend development starts only after running `cd frontend`.

## Release Candidate Regression Pack

- [ ] Case review can be submitted, approved, rejected, and closed.
- [ ] Case closure checklist, deliverables, and package manifest workflows work.
- [ ] Closure before approval requires an explicit owner/admin override reason.
- [ ] Report approval can be submitted, approved, and rejected.
- [ ] Remediation validation can be submitted, validated, failed, or accepted
      as risk without active checking.
- [ ] Review Board filters by status, priority, risk, reviewer, and due date.
- [ ] Archived investigations cannot be purged until they are archived.
- [ ] Active investigations return a clean conflict response on purge attempts.
- [ ] Member add by username and email works.
- [ ] Duplicate and missing member errors are clean and non-technical.
- [ ] `GET /api/v1/release` returns app name, version, channel, environment,
      migration, and build metadata without secrets.
- [ ] Demo seed and clear use only synthetic `[DEMO]` data.
- [ ] Correlations Cards, Graph, and Table modes tolerate empty or partial data.
- [ ] Threat Intelligence and Evidence Intelligence pages tolerate missing
      nested arrays.

## Manual Validation Commands

Backend:

```powershell
docker compose run --rm backend python -m ruff check app workers tests
docker compose run --rm backend python -m mypy app workers
docker compose run --rm backend python -m pytest tests/ -q
docker compose run --rm backend python -m pip check
docker compose exec backend alembic check
```

Frontend:

```powershell
cd frontend
npm run lint
npm run build
```

Health:

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
curl http://localhost:8000/api/v1/release
```
