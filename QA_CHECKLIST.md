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

## Governance And Audit

- [ ] Admin Settings loads for administrators only.
- [ ] Feature flags hide disabled UI and backend routes reject mutations.
- [ ] Retention settings show archive eligibility without destructive deletion.
- [ ] Audit filters work and an empty audit result is clear.
- [ ] Important workflow and export actions appear in audit.

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
