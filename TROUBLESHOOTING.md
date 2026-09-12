# Troubleshooting

For private transfer to a second Windows machine, start with
`EXTERNAL_MACHINE_TEST_CHECKLIST.md`. Its recovery section covers missing or
stopped Docker, fixed-port conflicts, backend/frontend reachability, project
binding, approved scripts, RC6 mismatch, pending migrations, and the expected
unsigned SmartScreen warning without automatic system changes.

## Backend Shows Unavailable

For the consolidated local-only repair flow, see `LOCAL_HEALTH_REPAIR.md`.

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
curl.exe -fsS http://localhost:8000/api/v1/release
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

## Deferred Hosting Planning

Hosting is not part of the RC6 private/local validation scope. The following references are
for a future planning phase after final manual QA:

- Use `DEPLOYMENT_PREFLIGHT.md` before pointing the platform at a hosted
  PostgreSQL database or public domain.
- Supabase is supported as hosted PostgreSQL only. Do not expose `DATABASE_URL`
  to the frontend and do not enable Supabase Auth for this architecture.
- For domain setup, align `FRONTEND_URL`, `BACKEND_CORS_ORIGINS`, and
  `VITE_API_BASE_URL` exactly.

## Suspected Secret Exposure

Do not paste or print a suspected credential while diagnosing it. Stop the
affected local service, rotate or revoke the value at its source, replace the
local `.env` value, and inspect tracked filenames with the non-secret-output
checks in `SECRETS_AUDIT_CHECKLIST.md`. Removing a value from the current file
does not remove it from Git history; any history remediation must be a separate,
coordinated operation after rotation.

If backend logs may have received a secret, preserve only the minimum evidence
needed for review and restrict access to the log files. SQL parameter echo is
disabled and the application formatter redacts common secret forms, but neither
control is a substitute for rotation after confirmed exposure.

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
  quality or LAN monitoring data is unavailable. The current head is
  `0036_phase5ai_posture`.
- A scan is bounded and local. If it fails, inspect backend logs and database
  health; investigation and reporting workflows remain usable.
- A recurring resolved issue reopens when the same condition is detected.
  Ignored issues remain ignored unless an administrator resolves them.
- **Archive stale notifications** soft-archives only read or dismissed records
  older than the threshold. It never deletes notification content.
- Diagnostic metadata intentionally omits credentials, invite codes, database
  URLs, provider keys, and tokens.

## Frontend Build Or Layout Problems

Portable and installed RC6 builds load React from bundled Tauri assets. They do
not require `npm run dev` or port 5173. If the release status screen does not
show **Frontend: Embedded**, rebuild the desktop artifacts and validate their
manifests; do not point release mode at a backend API path on port 5173.

If **Start platform** reports that the repository root cannot be resolved,
rebind the canonical repository root (not `desktop/` or an artifact directory).
The script accepts only the internally validated root and fixed repository
markers; it intentionally falls back to copy-only guidance instead of executing
an arbitrary path.

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
  docker compose logs -f celery-worker
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
docker compose exec backend python -m scripts.seed_demo_data
```

Clear demo data:

```powershell
./scripts/local/reset_demo.ps1 -Confirmation RESET-DEMO
```

Admin API equivalents:

- `POST /api/v1/admin/demo/seed`
- `DELETE /api/v1/admin/demo/clear`

If seed fails, check that an active admin user exists, migrations are current,
and demo mode is enabled when using the admin UI action.

The lower-level clear command requires an explicit phrase:

```powershell
docker compose exec -T backend python -m scripts.seed_demo_data `
  --clear --confirm-clear CLEAR-DEMO-DATA
```

Back up and restore instructions are in `LOCAL_BACKUP_RESTORE.md`. Do not use
`docker compose down -v` for routine repair because it deletes local volumes.

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

The frontend uses route-level lazy loading. A brief `Opening workspace` state is
expected on the first visit to a route. If a route chunk cannot load, use the
friendly retry action; do not treat an optional provider degradation as a total
backend outage.

If an Activity Inbox, Global Search, or Data Quality action opens the wrong
record, confirm the URL begins with `/` and uses the current internal query key.
External and protocol-relative action URLs are intentionally rejected.

## Report Export Troubleshooting

- PDF content should start with `%PDF`.
- DOCX content should be a ZIP payload and start with `PK`.
- HTML and Markdown downloads should preserve the generated report content.
- Quality warnings should be template-specific and non-blocking.
- Download handlers should only show an error when the response is not OK or the
  backend returns a JSON error.

## Monitoring and authorized discovery

- **Monitoring loaded; LAN discovery disabled by configuration** is a healthy,
  informational state. Copy the exact non-secret flags from **Monitoring →
  Activation** only if authorized discovery is desired, then restart the local
  platform. Never enable public CIDRs.
- If automatic refresh is inactive, confirm
  `DESKTOP_AUTO_MONITORING_ENABLED=true`,
  `MONITORING_AUTO_REFRESH_ENABLED=true`, and a refresh interval from 15 to 300
  seconds, then recreate the backend containers. The default is 30 seconds.
- Portable and installed monitoring uses embedded frontend assets. Do not start
  Vite to repair it; verify backend readiness at `http://localhost:8000` instead.
- Optional endpoint telemetry and Docker neighbor visibility may be unavailable
  without making the platform degraded.

- If health and readiness are OK but host metrics are absent, expect **Platform
  healthy** and **Optional host telemetry unavailable**. The displayed metrics
  belong to the backend container until the optional local agent reports.
- If LAN discovery returns no neighbors in Docker, this is a container network
  visibility limitation. Supply approved static/router observations or run the
  optional local endpoint agent; do not enable privileged Docker access.
- **Run TCP service check** stays disabled until LAN monitoring and
  `LAN_SERVICE_CHECK_ENABLED` are enabled and the asset is both authorized and
  monitored. A 409 may also mean the per-asset cooldown is active.
- Recon warnings use `provider_timeout`, `provider_http_error`, and
  `provider_parse_error`. Retry is safe; provider failures do not delete valid
  entities already stored, and raw endpoint errors are not shown.

The RC6 accepted browser workflow remains local Docker Compose plus optional
local Vite. The Tauri portable executable and unsigned NSIS installer embed
the same React frontend and require only the external local backend at runtime.
They exist for private local testing only and bundle no backend,
PostgreSQL, Redis, Docker, `.env`, or operator data. Signing, public release,
auto-update, hosting, deployment, DNS, and Supabase migration remain deferred.
## Phase 5AD alert triage and Activity Inbox

- If the Activity Inbox is empty, clear triage filters and confirm the alert is
  an internal `monitoring_alert` for the signed-in user. Resolved and
  false-positive alerts remain in triage history but leave the unread inbox.
- A muted alert uses manual suppression; maintenance-suppressed alerts retain a
  separate badge. Neither state stops monitoring collection. Analysts cannot
  mute critical alerts; an administrator must explicitly do so.
- If an action returns a conflict, refresh the queue because another action or
  automatic recovery may already have moved the alert. Validation errors mean
  a safe reason or resolution summary is missing or contains secret-like text.
- The Activity Inbox is a fixed portal with its own bounded scroll region. It
  should close with Escape or an outside click and must remain within the
  viewport without competing with sidebar scroll.

Triage adds no network checks or offensive behavior. Hosting, deployment, DNS,
and Supabase remain unchanged.

## Phase 5AE endpoint enrollment

- If registration returns 401, verify the credential is current, unrevoked,
  unexpired, below its enrollment limit, and permits the endpoint's private IP.
- If an agent is stale, confirm the backend is healthy and manually restart the
  helper. Agents are intentionally not installed as services or autostart jobs.
- A rotated token invalidates the prior value. Existing agents must receive the
  new value through the secure prompt before their next manual run.
- Empty group coverage means no members are assigned. Baseline indicators need
  existing authorized service observations; baseline creation does not scan.
- Replace `BACKEND_HOST` with localhost or an approved private IP. Stop either
  helper with `Ctrl+C`; never paste tokens into command arguments or logs.

## Phase 5AF activation and target eligibility

- If discovery is disabled, open **Monitoring → Activation** and confirm
  `LAN_MONITORING_ENABLED`, then recreate the local backend/worker containers.
- If a service-check button is disabled, confirm
  `LAN_SERVICE_CHECK_ENABLED=true`, the target exactly matches an existing
  private LAN asset, and that asset is authorized with monitoring enabled.
- Target eligibility does not resolve public DNS names. Add an approved
  private asset observation or endpoint agent with the matching hostname.
- For Windows endpoint access, scope an inbound TCP 8000 firewall rule to the
  configured RFC1918 CIDR only. For example, from elevated PowerShell use
  `New-NetFirewallRule -DisplayName "RavenTech local agent" -Direction Inbound -Protocol TCP -LocalPort 8000 -RemoteAddress 192.168.0.0/24 -Action Allow`
  after replacing the example CIDR. Do not expose the backend publicly.
- A partial enrichment warning does not invalidate stored entities. Expand the
  compact provider list, retain the successful result, and retry safely later.

## RC4 language preference

- The UI defaults to English and stores only `en` or `es` under
  `raventech.language` in browser local storage.
- Privacy modes can block local storage; select the language again for that
  session or clear only that key to reset the preference.
- Missing Spanish copy intentionally falls back to English, including some
  dynamic provider, evidence, and analyst-authored text. Raw translation keys
  must never be displayed.
- Report language is selected separately during generation and retained as safe
  report metadata for retries and downloads.

## Authorized LAN bootstrap recovery

- If `192.168.50.1/24` does not normalize to `192.168.50.0/24`, verify the slash
  and prefix. Public, malformed, or larger-than-256-address inputs are rejected.
- If configured CIDR needs action, copy the wizard's exact non-secret lines into
  the untracked `.env` and recreate backend/worker containers.
- If no heartbeat arrives, confirm the approved endpoint can reach
  `http://192.168.50.201:8000`; use localhost only on the backend host. Never put
  the token on the command line.
- If Docker shows no neighbors, import a manually observed router/static device;
  do not supply router credentials or scrape the router.
- If a service-check button is disabled, verify its flag, exact private CIDR,
  asset authorization, and per-asset monitoring state. Do not bypass it.

## Host metrics troubleshooting

- **Docker container fallback:** the backend is healthy but lacks full Windows-host
  visibility. Open the installed/portable desktop for native metrics or manually run
  `ServerHost` at a 30-second interval.
- **Native metrics unavailable:** no platform failure occurred. Confirm the desktop
  is the Windows Tauri build; browser-only mode cannot call native APIs.
- **ServerHost stale:** confirm the helper is still open, the backend is reachable at
  localhost, and the manually supplied admin token is current. Restart it manually;
  do not create a service or scheduled task.
- **LAN endpoint stale:** confirm TCP/8000 is reachable only from `192.168.50.0/24`,
  the enrollment token was entered only at the prompt, and the 30/60-second cadence
  is allowed. Never open the backend to a public network.

## Real-LAN acceptance troubleshooting

- **No last discovery/check time:** no audited run exists yet; this is informational.
  Enable the relevant local flags and invoke the bounded action manually if approved.
- **Zero assets with a healthy platform:** Docker may not see Windows host neighbors.
  Import a known router/static observation or run an approved endpoint agent.
- **Agent connected but posture unchanged:** wait for the bounded posture cadence,
  refresh the summary, and confirm the heartbeat is fresh; do not increase polling
  aggressively or install persistence.
- **Service check ineligible:** the displayed reason identifies the disabled flag,
  CIDR mismatch, missing authorization, or per-asset monitoring state. Do not bypass it.
- **Fixed profile apply unavailable:** bind the correct repository and restore the
  exact six scripts from trusted Git. In browser mode, use the copy-only profile.
- **Duplicate monitoring key:** resolve the duplicate active key manually; the script
  stops before backup/write so it cannot silently choose between conflicting values.
- **Restart still required:** use the separately confirmed restart action and wait for
  health/readiness/RC6 verification. Never restart by supplying custom commands.
- **Need to recover `.env`:** stop and review the timestamped ignored backup locally.
  Do not print, attach, or commit it because it may contain existing secrets.
