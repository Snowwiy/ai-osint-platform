# RavenTech OSINT RC2 Manual QA

Release candidate: `5.0.0-rc2`

Run this script against the local Docker Compose environment. Use only synthetic
or explicitly authorized data. Hosting, DNS, Supabase production migration, and
external services are outside this QA pass.

## Locked Demo Walkthrough Order

After the checks below pass, use this exact portfolio sequence: (1) login,
(2) dashboard, (3) demo investigation, (4) engagement/scope, (5) recon/findings,
(6) correlations/IOCs, (7) AI fallback, (8) reports, (9) closure/deliverables,
(10) notifications/Global Search/Saved Views, (11) Data Quality, and (12)
audit/governance. Do not add a hosting step.

## Environment Startup

1. From the repository root, copy `.env.example` to `.env` if local settings do
   not already exist. Use non-production local secrets.
2. Start services and apply the existing migration chain:

   ```powershell
   docker compose up -d
   docker compose exec backend alembic upgrade head
   docker compose ps
   ```

3. Confirm PostgreSQL, Redis, and backend are running; backend and PostgreSQL
   should report healthy.

## Backend Health Checks

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
docker compose exec backend alembic current
docker compose exec backend alembic heads
docker compose exec backend alembic check
```

Pass when `/health` and `/health/ready` return `status: ok`, current and head are
`0030_phase5z_base`, exactly one head exists, and Alembic reports no upgrade
operations. Responses must not expose connection strings, credentials, or raw
exceptions.

## Frontend Startup

```powershell
cd frontend
npm install
npm run build
npm run dev
```

Open the displayed local URL. Pass when the build completes and the app opens
without horizontal page overflow or a React crash screen.

## Login Test

1. Submit an incorrect password; expect `Invalid username or password.`
2. Sign in with the existing active administrator; expect Dashboard.
3. Sign out and sign in again to confirm the session flow remains usable.

## Registration Test

1. Confirm registration visibility matches `PUBLIC_REGISTRATION_ENABLED`.
2. When disabled, submit the endpoint/UI flow and expect a clean governed
   disabled message.
3. In a controlled local test, enable registration and retain approval/invite
   controls. Confirm a public registration never creates an admin.
4. If approval is required, confirm the new account cannot sign in until an
   administrator approves it.

## Admin User Management Test

1. Open Admin > Users and inspect list/search/filter behavior.
2. Approve or reject a synthetic pending account.
3. Disable and reactivate a synthetic non-admin account.
4. Change a synthetic user's safe platform role.
5. Confirm the last active administrator cannot be disabled or demoted.
6. Confirm API/UI output never includes a password hash or invite code.

## Investigation Workflow Test

1. Create an investigation with a clear authorization statement.
2. Confirm Dashboard, Operations Center, Investigations, and the detail page load.
3. Add a member, note, task, and bookmark; verify permission boundaries with a
   second analyst where available.
4. Review Timeline and Audit Log for the recorded actions.

## Engagement And Scope Test

1. Create a synthetic engagement and authorization metadata.
2. Add in-scope domain and CIDR records.
3. Link the investigation and confirm exact domain, subdomain, IP, and CIDR
   checks behave conservatively.
4. Confirm unknown/out-of-scope values warn or block according to governance
   settings and never trigger network activity.

## Findings And Recon Test

1. Add an authorized synthetic target and run passive recon.
2. Confirm partial-provider failures remain readable.
3. Generate findings and exercise severity/status filters.
4. Confirm missing arrays or relations show empty/degraded states, not
   `undefined`, `null`, or a crash.

## Correlations Test

1. Open Correlations Cards, Graph, and Table modes.
2. Test both populated and empty results.
3. Confirm long identifiers wrap and tabs do not clip or cause page overflow.

## AI Fallback Test

1. Leave `ANTHROPIC_API_KEY` empty in the controlled local environment.
2. Open AI Analysis and request analysis for an accessible investigation.
3. Pass when a clear provider-unavailable/degraded state appears and
   deterministic evidence-backed fallback/citations remain available.

## Reports And Export Test

1. Create executive and technical reports from stored synthetic evidence.
2. Review template guidance, readiness warnings, and analyst-review language.
3. Download PDF, DOCX, HTML, and Markdown formats allowed by governance.
4. Confirm PDF begins with `%PDF`, DOCX opens as a valid document, and HTML/MD
   preserve expected report content.

## Closure And Deliverables Test

1. Generate the closure checklist and update its items.
2. Submit, approve, close, and reopen with an authorized owner/admin.
3. Confirm premature closure is blocked unless a permitted override reason is
   recorded.
4. Create executive, technical, and evidence-appendix deliverables and generate
   the evidence package manifest.
5. Confirm included/missing deliverables, warnings, evidence counts, and audit
   events are consistent.

## Notification Test

1. Open Activity Inbox and filter alerts.
2. Mark one alert read, dismiss another, and use Mark all read.
3. Confirm unread counts update and one user cannot change another user's alert.
4. Rebuild workflow alerts as admin and confirm deterministic deduplication.

## Global Search And Saved Views Test

1. Open Global Search with Ctrl+K and search stored synthetic records.
2. Confirm analysts see only RBAC-authorized records and no admin user results.
3. Confirm every result route remains internal.
4. Create, load, pin, set default, unpin, and delete a saved view.
5. Confirm views are owner-scoped and malformed filters/routes fail safely.

## Data Quality Center Test

1. Confirm non-admin access is denied.
2. As admin, run Dry run and verify it changes no source records.
3. Run scan and inspect issue filters and safe metadata.
4. Acknowledge, ignore, or resolve a synthetic issue; verify invalid transitions
   return a clean conflict.
5. Confirm stale-notification maintenance only soft-archives eligible records.

## Audit Log Test

1. Filter audit events by action and resource.
2. Confirm auth, user governance, engagement, closure, deliverable, notification,
   saved-view, quality, report, and export actions appear as exercised.
3. Confirm metadata contains no secrets, password hashes, or raw configuration.

## Release Endpoint Test

```powershell
curl http://localhost:8000/api/v1/release
```

Pass when the response reports `5.0.0-rc2`, release-candidate channel,
environment, migration, and non-secret build metadata.

## Final Pass/Fail Checklist

- [ ] Existing admin login works; registration matches configuration.
- [ ] Admin user management and last-active-admin protection work.
- [ ] Dashboard, Operations Center, investigations, and engagement/scope load.
- [ ] Findings/recon and Correlations Cards/Graph/Table work.
- [ ] IOCs, Evidence Intelligence, and Threat Intelligence load.
- [ ] AI deterministic fallback works without a provider key.
- [ ] Reports export PDF, DOCX, HTML, and Markdown and remain analyst-reviewed.
- [ ] Closure, deliverables, and evidence package manifest work.
- [ ] Notifications, Global Search, and owner-scoped Saved Views work.
- [ ] Data Quality scan/transitions and Audit Log work.
- [ ] Release, health, readiness, and Alembic checks pass.
- [ ] No raw endpoint errors, secret output, `undefined`/`null` UI text, badly
      overflowing IDs, clipped tabs, horizontal page overflow, or React crash.
- [ ] Required backend validation, frontend lint/build, Docker status, and logs
      pass review.
- [ ] No hosting, DNS, deployment, or production database changes were made.
- [ ] GitHub push completes only after every required automated validation and
      applicable manual flow passes.
