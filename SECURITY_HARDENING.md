# RavenTech OSINT Security Hardening

RavenTech OSINT is a defensive investigation workspace. This guide focuses on
safe internal operation, governance, and supportability.

## Secret Management

- Never commit `.env`.
- Use strong `APP_SECRET_KEY` or `SECRET_KEY` values.
- Rotate provider keys outside the application repository.
- Keep API keys out of frontend builds.
- Use the Operations Center environment validation to confirm presence without
  displaying values.
- Keep `DATABASE_URL`, `REDIS_URL`, provider keys, invite codes, and admin
  bootstrap credentials backend-only. The frontend may receive only public
  build configuration such as `VITE_API_BASE_URL`.
- Placeholder signing keys generate a local warning and are rejected in
  production mode. CORS wildcard configuration is also rejected in production.

The Phase 5V tracked-file audit found no private keys, provider keys, JWTs,
committed `.env` files, or production credentials. Credential-shaped database
URLs in tracked files are restricted to explicit local/CI examples and
historical documentation placeholders. Repeat the checks in
`SECRETS_AUDIT_CHECKLIST.md` before any future hosting review.

## Environment Separation

Use separate configuration for:

- Development
- Staging
- Production-style operation

Production-style operation should use:

- Strict CORS origins
- Non-development signing keys
- Persistent database and report volumes
- Restricted access to Docker host and volumes

## Dependency Hygiene

- Install Python dependencies from the existing backend manifests and require
  `python -m pip check` to pass. Avoid opportunistic major upgrades during the
  RC2 freeze.
- Install frontend dependencies from `package-lock.json`. Phase 5V refreshed
  safe in-range transitive packages and retained React Router 6 to avoid an
  unreviewed breaking migration.
- `npm audit` currently reports two moderate React Router advisories whose
  automated fix moves to React Router 7. The Vite application does not use SSR
  hydration, and dynamic destinations are normalized to internal routes. Plan
  the major upgrade with dedicated regression testing after the freeze.
- The upstream Passlib `crypt` deprecation warning remains documented; do not
  hide it globally or pin insecure replacements.

## RBAC

Preserve backend enforcement:

- Platform admin: administrative controls
- Investigation owner: governance control for owned cases
- Investigation admin: case management
- Analyst: investigation contribution
- Viewer: read-only

Frontend visibility is convenience only. Backend checks are the security boundary.

## User Administration

- Public registration must remain disabled by default unless an operator has
  intentionally enabled it.
- Public registration never creates platform administrator accounts.
- Pending, disabled, and rejected accounts cannot access protected areas.
- Admins can approve, reject, disable, reactivate, and safely change platform
  roles through Admin → Users.
- The backend prevents disabling or demoting the last active administrator.
- Invite codes are environment-controlled and must never be displayed or logged.

## Governance Controls

Review Admin Settings for:

- Data retention metadata
- Export controls
- Audit policy
- Report branding
- Feature flags

Disabled features should return clean errors and hide UI actions where possible.

## Engagement Scope Governance

- Record engagement metadata before client-facing work where possible.
- Store authorization evidence as metadata or references unless a governed file
  storage workflow has been approved.
- Treat `pending_review`, `expired`, `revoked`, and `not_provided`
  authorization states as requiring analyst or owner review.
- Out-of-scope target warnings are advisory by default unless governance policy
  is configured to block them.
- Scope matching is deterministic and local. It does not perform DNS lookups,
  active probing, crawling, scanning, or external enrichment.
- Do not log contracts, passwords, API keys, tokens, or raw invite codes in
  engagement notes, scope metadata, authorization references, or audit fields.

## Case Closure And Deliverables

- Treat closure as a governance workflow, not as legal approval by itself.
- Require owners or administrators to record an override reason when closing
  with unresolved required checklist items.
- Use deliverable records and package manifests to track client-ready artifacts;
  do not store local filesystem paths or external delivery secrets in
  deliverable metadata.
- Evidence package summaries should reference stored evidence counts, findings,
  reports, and warnings without duplicating sensitive legal documents.
- Closed cases remain viewable and reportable; reopening requires owner/admin
  permission.

## Audit Practices

Review audit logs for:

- Login failures
- Permission denials
- Governance changes
- Feature flag changes
- User registration and approval actions
- User disable/reactivate and role changes
- Engagement, scope, and authorization evidence changes
- Closure, checklist, deliverable, and package manifest actions
- Notification creation, read, dismiss, and workflow alert rebuild actions
- Global search activity metadata and saved-view changes
- Backup exports
- Restore validations
- Report downloads
- Member and ownership changes

Do not log secrets in audit metadata.

## Search And Saved Views

- Global Search must remain internal-only and RBAC-aware. It should never call
  external search providers, crawl targets, or perform internet-wide discovery.
- Admin-only user results must expose safe metadata only. Password hashes,
  tokens, invite codes, API keys, authorization headers, and database URLs must
  never appear in search results or snippets.
- Saved views are private to the creating user by default. Do not store
  credentials, secrets, filesystem paths, bearer tokens, or provider keys in
  saved filters.
- Search audit events should log result metadata and safely truncated query
  context only.

## Data Quality And Maintenance

- Restrict quality scans, issue-state changes, dry runs, and maintenance actions
  to authenticated administrators.
- Treat scan findings as recommendations. Never automate deletion, role changes,
  case closure, authorization changes, or evidence edits from quality results.
- Keep scans bounded and local. No external search, crawling, active scanning,
  enrichment, or AI provider is required.
- Persist only sanitized diagnostic metadata. Passwords, hashes, tokens, invite
  codes, database URLs, Authorization headers, and API keys are prohibited.
- Stale notification maintenance is an explicit soft archive limited to old
  read or dismissed notifications.

## Backup Controls

- Store backup exports in approved internal locations.
- Treat backups as sensitive operational data.
- Validate backups with dry-run restore before upgrades.
- Use PostgreSQL-native backup for authoritative recovery.
- Keep `backups/` and generated report output Git-ignored. A database dump can
  contain user and investigation data even though the scripts do not copy
  `.env` or provider configuration.
- Restore only into a new, explicitly named review database. Never bypass the
  refusal of the live and PostgreSQL system database names.

## Logging

Logs should include:

- Request ID
- Endpoint
- User context where safe
- Failure reason

Logs should not include:

- Passwords
- API keys
- JWTs
- Refresh tokens
- Raw `.env` values

SQLAlchemy parameter echo is disabled in all environments. The JSON formatter
redacts sensitive structured fields, configured secret values, authorization
credentials, credential-bearing PostgreSQL/Redis URLs, and common secret
assignments found inside message or exception strings. This is defense in depth;
application code must still avoid logging raw request bodies or credentials.

## Network Exposure

- Keep PostgreSQL and Redis internal to Docker networking where possible.
- Expose the backend only through approved internal routes.
- Restrict frontend CORS to known origins.
- Do not add generalized active, vulnerability, internet-wide, or offensive
  scanning capabilities. Keep optional LAN checks within the bounded controls
  documented below.
- Keep `LAN_MONITORING_ENABLED=false` unless an administrator has documented the
  private ranges and operator authorization. Phase 5Y rejects public ranges and
  limits each discovery request to `/24` or smaller.
- Keep ping and service checks disabled unless separately approved. Configured
  TCP checks establish connectivity only and must never send payloads, test
  credentials, brute force, fingerprint versions, or validate exploits.
- Store `LAN_AGENT_TOKEN` only in the untracked backend environment. Rotate it
  after suspected exposure; never pass it as a command argument or include it in
  logs, telemetry metadata, screenshots, reports, or frontend variables.
- Do not mount the Docker socket or use privileged containers for discovery.
  Prefer the manual endpoint agent or sanitized router/static observations.

## Internal Notifications

- Notifications are database-backed activity records only.
- Do not store passwords, tokens, invite codes, API keys, or legal document
  contents in notification metadata.
- Workflow alerts should use deterministic dedupe keys to avoid repeated noise.
- Notification visibility must remain user-scoped and investigation-aware.
- This release does not send email, SMS, browser push, or chat messages.

## Operational Review

Before release:

1. Confirm `/health/ready`.
2. Confirm `GET /api/v1/release`.
3. Confirm Admin → Operations.
4. Export diagnostics.
5. Export a backup.
6. Validate backup dry-run.
7. Review audit logs.
8. Confirm report downloads.
9. Confirm feature flags and export controls.
10. Confirm demo mode remains disabled in production-style environments.
