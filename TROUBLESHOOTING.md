# Troubleshooting

## Backend Shows Unavailable

1. Check service status:

   ```powershell
   docker compose ps
   ```

2. Inspect backend logs:

   ```powershell
   docker compose logs -f backend
   ```

3. Confirm `/health` and `/health/ready` return structured JSON.

Common causes:

- missing or invalid `.env`
- database not ready
- Redis not ready
- unapplied migrations
- stale frontend API base URL

Check release metadata:

```powershell
curl http://localhost:8000/api/v1/release
```

The response should show app name, version, release channel, migration version,
environment, and non-secret build metadata.

## Migrations

Check current revision:

```powershell
docker compose run --rm backend alembic current
```

Apply migrations:

```powershell
docker compose run --rm backend alembic upgrade head
```

Detect drift:

```powershell
docker compose run --rm backend alembic check
```

If an endpoint fails with a missing-column error, inspect the latest migration
and apply `alembic upgrade head` before changing code.

## Login Problems

- Wrong credentials should show `Invalid username or password.`
- Public registration is disabled by default; disabled registration should show
  a clean message instead of a raw endpoint error.
- Pending or disabled accounts cannot access protected areas. Existing admin
  bootstrap accounts should remain active.
- Invite codes are backend-only secrets and should never be displayed in the UI
  or logs.
- Pending accounts can be approved in Admin → Users.
- Disabled or rejected accounts can be reviewed in Admin → Users by a platform
  administrator.
- If an admin cannot disable or demote another admin, confirm at least one other
  active administrator exists.
- Session expiry should redirect to login.
- Backend `401` responses outside login usually mean the access token expired
  or was cleared.
- Do not expose request IDs in the normal login card.

## Deployment Preflight

- Use `DEPLOYMENT_PREFLIGHT.md` before pointing the platform at a hosted
  PostgreSQL database or public domain.
- Supabase is supported as hosted PostgreSQL only. Do not expose `DATABASE_URL`
  to the frontend and do not enable Supabase Auth for this architecture.
- For domain setup, align `FRONTEND_URL`, `BACKEND_CORS_ORIGINS`, and
  `VITE_API_BASE_URL` exactly.

## Report Issues

- Check Admin Settings export controls.
- Confirm the requested format is enabled.
- Review report quality warnings; they are guidance and should not block
  generation.
- If a PDF/DOCX/HTML/Markdown download starts, the UI should not show a false
  backend-unreachable banner.
- If a report references audit data, missing audit rows should degrade to an
  empty audit section rather than a server error.

## Audit Issues

- Admin audit is available only to platform administrators.
- Invalid UUID filters should show a validation error, not a backend crash.
- Empty audit results are valid and should render an empty state.
- Audit metadata should be displayed safely and never include secrets.

## Engagement Or Scope Issues

- Existing investigations do not require an engagement. Link one from the
  investigation edit dialog when client context or report scope metadata is
  needed.
- If a target shows an out-of-scope or pending-review warning, open the linked
  Engagements page and confirm the scope item exists with `in_scope` status.
- CIDR matching is local and deterministic. Confirm the scope item is stored as
  a CIDR value such as `192.0.2.0/24`.
- Authorization statuses such as `not_provided`, `pending_review`, `expired`,
  and `revoked` are intentionally visible in the workspace and reports.
- Scope checks do not perform DNS lookups, active probing, crawling, or external
  enrichment.
- If target creation is blocked, review governance settings for
  `BLOCK_OUT_OF_SCOPE_TARGETS` or approved-authorization enforcement.

## Case Closure Or Deliverable Issues

- If closure cannot be completed, generate or refresh the checklist and review
  required `pending` or `blocked` items. Owners/admins can close with an
  explicit override reason when governance allows it.
- If the package manifest is missing deliverables, create records for executive
  report, technical report, and evidence appendix, then mark them `ready`,
  `approved`, or `delivered`.
- If evidence package readiness shows warnings, link findings to evidence
  records or document accepted residual gaps in the closure summary.
- If a closed case needs more work, reopen it from the Closure tab. Reopening
  preserves history and emits audit/timeline events.
- If closure metadata is missing from a report, regenerate the report after
  closure and deliverable records are created.

## Activity Inbox Issues

- Activity Inbox is internal only. It does not send email, SMS, browser push, or
  chat notifications.
- If unread counts look stale, refresh the inbox or dashboard. Workflow alerts
  are deduplicated, so rebuilding alerts should not create repeated copies.
- If an admin does not see pending user approval alerts, open Admin → Users and
  confirm pending accounts exist, then use the workflow alert rebuild endpoint
  if needed.
- If an action link is unavailable, open the related module manually. The alert
  should still remain readable and dismissible.
- Notification errors should show concise copy with optional technical details,
  not raw endpoint dumps in normal UI.

## Global Search And Saved Views Issues

- Global Search is internal-only. It searches stored application records and
  does not browse the internet, crawl targets, or call external search
  providers.
- If Global Search returns no results, confirm the record exists, is not hidden
  by archive filters, and is accessible to the current user through RBAC or
  investigation membership.
- Non-admin users should not see user-management results. Admin users see only
  safe user metadata, never password hashes or secrets.
- If Ctrl+K does not open search, click the search control in the authenticated
  layout and confirm the browser tab has focus.
- If a saved view does not load expected filters, delete and recreate it after
  clearing the page filters. Saved views store JSON-safe filter values only.
- Saved views are private to the creating user by default. Another analyst not
  seeing your saved view is expected behavior.

## Data Quality Center Issues

- Apply migrations with `docker compose exec backend alembic upgrade head` if
  quality data is unavailable. The Phase 5P head is `0028_phase5p_quality`.
- A scan is bounded and local. If it fails, inspect backend logs and database
  health; investigation and reporting workflows remain usable.
- A recurring resolved issue reopens when the same condition is detected.
  Ignored issues remain ignored unless an administrator resolves them.
- **Archive stale notifications** soft-archives only read or dismissed records
  older than the threshold. It never deletes notification content.
- Diagnostic metadata intentionally omits credentials, invite codes, database
  URLs, provider keys, and tokens.

## Frontend Build Or Layout Problems

- Confirm `frontend/.env` points to the expected API base URL.
- `VITE_API_BASE_URL` should normally be `http://localhost:8000/api/v1` for
  local development.
- Run frontend commands from the `frontend/` directory:

  ```powershell
  cd frontend
  npm install
  npm run dev
  npm run build
  ```

- If `npm run dev` fails at the repository root, change into `frontend/` first.
- Use the browser console for component errors.
- Long IDs, URLs, IOC values, and report identifiers should wrap or provide copy
  controls.
- The sidebar should scroll vertically on short screens.
- If a React route fails, the app should show the friendly page error panel.
  Expand technical details only while debugging.

## Worker Or Background Task Issues

- Inspect worker logs:

  ```powershell
  docker compose logs -f celery_worker
  ```

- Confirm Redis is healthy.
- Retried jobs should be idempotent and should log failure reasons without
  exposing secrets.

## Provider Or AI Unavailable

Optional providers may return degraded or provider-unavailable responses when
keys are missing or rate limited. Deterministic investigation, findings,
knowledge, report, and governance workflows should continue.

Expected AI degraded behavior:

- Missing provider key shows a clear provider-not-configured message.
- Invalid provider response preserves deterministic fallback analysis.
- Retry should re-run the backend request without losing citations already
  displayed.
- Feature-flag disabled AI should return a clean disabled/degraded state, not a
  raw stack trace.

## Demo Data Issues

Seed demo data from the backend container:

```powershell
docker compose exec backend python scripts/seed_demo_data.py
```

Clear demo data:

```powershell
docker compose exec backend python scripts/seed_demo_data.py --clear
```

Admin API equivalents:

- `POST /api/v1/admin/demo/seed`
- `DELETE /api/v1/admin/demo/clear`

If seed fails, check that an active admin user exists, migrations are current,
and demo mode is enabled when using the admin UI action.

## Release Candidate CI Failures

CI runs backend `ruff`, `mypy`, `pytest`, `pip check`, Alembic migration drift
checks, frontend lint, and frontend build.

If backend tests fail:

1. Confirm migrations are linear and the new model is imported by
   `app.models`.
2. Run `docker compose exec backend alembic current` and
   `docker compose exec backend alembic heads`.
3. Re-run only the failing pytest node locally after reviewing the error.

If frontend build fails:

1. Run commands from `frontend/`.
2. Check for unsafe `.length`, `.map`, `.filter`, `.reduce`, or
   `localeCompare` on optional API data.
3. Prefer `safeArray`, `safeString`, `safeNumber`, and friendly empty states.

## Report Export Troubleshooting

- PDF content should start with `%PDF`.
- DOCX content should be a ZIP payload and start with `PK`.
- HTML and Markdown downloads should preserve the generated report content.
- Quality warnings should be template-specific and non-blocking.
- Download handlers should only show an error when the response is not OK or the
  backend returns a JSON error.
