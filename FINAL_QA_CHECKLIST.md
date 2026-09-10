# RavenTech OSINT Final QA Checklist

## Phase 5AA — monitoring policies

- [ ] Analyst can read policies and maintenance windows; unauthenticated access returns 401.
- [ ] Only administrators can create or update policies and maintenance windows.
- [ ] Resource, stale/offline, risky-service, unauthorized, weak-coverage, finding, and overdue rules have safe defaults.
- [ ] Cooldown, dedupe, per-rule cap, enablement, severity override, and acknowledge behavior validate cleanly.
- [ ] Suppress/unsuppress returns clean 403/404/409/422 outcomes and writes audit events.
- [ ] Active maintenance marks alerts without deletion or collection interruption.
- [ ] Monitoring Center states avoid raw API errors, crash screens, and horizontal overflow.
- [ ] No secrets, active scanning, hosting, deployment, DNS, or Supabase changes exist.

Version: `5.0.0-rc2`

Run from the repository root unless a section says otherwise. Complete this
checklist with synthetic or explicitly authorized data only. A failed required
check blocks the current release-freeze commit and push.

## Automated Validation

- [ ] `docker compose run --rm backend python -m ruff check app workers tests`
- [ ] `docker compose run --rm backend python -m mypy app workers`
- [ ] `docker compose run --rm backend python -m pytest tests/ -q`
- [ ] `docker compose run --rm backend python -m pip check`
- [ ] `docker compose exec backend alembic check`
- [ ] `curl http://localhost:8000/health` returns `status: ok`.
- [ ] `curl http://localhost:8000/health/ready` returns `status: ok`.
- [ ] `curl http://localhost:8000/api/v1/release` returns `5.0.0-rc2` and
      `0030_phase5z_base` without secrets.
- [ ] From `frontend/`, `npm run build` passes.
- [ ] `docker compose ps` shows required local services running; backend and
      PostgreSQL are healthy.
- [ ] `docker compose logs backend --tail=100` has no blocking error or secret.

## Authentication And Admin Users

- [ ] Existing active administrator login works; bad credentials return a clean
      401 message.
- [ ] Registration UI/API matches configuration and never creates an admin.
- [ ] Pending/disabled/rejected users cannot access protected routes.
- [ ] Admin Users list/search/filter and approve/reject/disable/reactivate work.
- [ ] The last active administrator cannot be disabled or demoted.
- [ ] Password hashes, invite codes, tokens, and secret configuration never
      appear in responses or UI.

## Core Investigation Workflow

- [ ] Dashboard and Operations Center load with safe empty/degraded states.
- [ ] Investigations list/detail, membership, ownership, notes, tasks, bookmarks,
      timeline, and archive/restore work.
- [ ] Engagement authorization and scope records can be reviewed and linked.
- [ ] Domain/subdomain/IP/CIDR scope checks remain local and conservative.
- [ ] Targets and passive recon work without active scanning or crawling.
- [ ] Findings load, filter, update, and retain evidence/remediation context.
- [ ] Correlations Cards/Graph/Table, IOCs, Evidence Intelligence, and Threat
      Intelligence tolerate empty or partial data.
- [ ] AI provider failure shows deterministic fallback rather than a crash.

## Reports, Closure, And Deliverables

- [ ] Executive and technical reports generate from stored evidence.
- [ ] PDF, DOCX, HTML, and Markdown downloads work according to export policy.
- [ ] Report warnings are advisory and every report remains analyst-reviewed.
- [ ] Review/approval and remediation validation transitions work.
- [ ] Closure checklist submit/approve/close/reopen works for authorized roles.
- [ ] Premature closure requires a permitted, recorded override reason.
- [ ] Deliverable records and evidence package manifest show consistent included,
      missing, warning, and evidence data.

## Notifications, Search, And Saved Views

- [ ] Notification list/filter/read/dismiss/mark-all-read and unread count work.
- [ ] Users cannot access or mutate another user's notification.
- [ ] Global Search returns only RBAC-authorized internal records and safe routes.
- [ ] Non-admin users cannot retrieve admin user results.
- [ ] Saved Views create/update/load/pin/default/unpin/delete works.
- [ ] Saved Views remain owner-scoped and reject unsafe routes/secret filters.

## Data Quality, Audit, And Governance

- [ ] Data Quality Center denies non-admin access.
- [ ] Dry run changes no source record; scan creates bounded review issues.
- [ ] Issue acknowledge/ignore/resolve and invalid-transition handling work.
- [ ] Stale-notification maintenance only soft-archives eligible records.
- [ ] Audit Log records the exercised security, workflow, report, search, and
      quality actions without secrets.
- [ ] Governance settings, feature flags, export controls, and demo-mode state
      display consistently.

## Local Monitoring

- [ ] Monitoring requires authentication; an analyst sees only accessible
      investigations and an administrator sees the platform-authorized set.
- [ ] Overview, services, system, assets, and alerts endpoints return bounded,
      sanitized responses without secrets or raw exceptions.
- [ ] Service cards reflect backend, database, Redis, worker, migration, report
      storage, and deliberately limited Docker visibility.
- [ ] Poll selection remains between 15 and 300 seconds and manual refresh works.
- [ ] Asset Watch summarizes targets, findings, evidence, reports, closure,
      scope, and authorization without active scanning.
- [ ] Repeated overview polling creates at most one Activity Inbox notification
      per alert/user/day.
- [ ] Optional local agent rejects non-local backend URLs and invalid telemetry;
      ingestion is admin-only and the bearer token is never persisted or logged.
- [ ] Missing/stale agent data falls back cleanly to container metrics and does
      not make the platform unavailable.
- [ ] Normal navigation shows no global demo-mode banner; QA Tools and demo
      seed/reset controls are admin-only, while synthetic records remain labeled.
- [ ] LAN monitoring is disabled by default and LAN inventory routes deny
      non-admin users.
- [ ] Public, non-RFC1918, out-of-range, and discovery ranges larger than `/24`
      are rejected.
- [ ] Discovery is admin-triggered and rate limited; ping and bounded configured
      TCP connects remain disabled unless separately enabled.
- [ ] Docker neighbor-table limitations return a clear empty/limitation state
      without privileged mode or a crash.
- [ ] Agent registration/telemetry rejects missing, invalid, or unset shared
      tokens and never echoes or logs them.
- [ ] Endpoint detail tolerates missing telemetry, services, MAC, hostname,
      latency, and notes without a React crash.
- [ ] LAN alerts deduplicate, and port/resource/version results are labeled risk
      indicators rather than confirmed vulnerabilities.
- [ ] Vulnerability Baseline evaluates stored observations only and does not
      initiate discovery, service probing, credential checks, or exploit tests.
- [ ] Admin and analyst roles can set asset criticality/business context and
      track baseline status, remediation owner, and due date.
- [ ] Risky service, stale agent, unauthorized asset, sustained pressure,
      missing-owner, and overdue-remediation indicators appear without alert
      duplication or secret metadata.

## UI And Portfolio Review

- [ ] No normal flow shows raw endpoint dumps, stack traces, `undefined`, or
      `null` text.
- [ ] No long ID, URL, tab row, table, or modal causes horizontal page overflow.
- [ ] No React crash screen appears; retry/empty/degraded states are readable.
- [ ] Screenshot set follows `SCREENSHOTS_CHECKLIST.md` and contains only
      synthetic data.
- [ ] Demo follows the locked 12-step order in `PORTFOLIO_DEMO_FLOW.md`.
- [ ] `LOCAL_DEMO_BUNDLE.md` and `GITHUB_RELEASE_DRAFT.md` match the frozen
      version, validation evidence, limitations, and defensive-only scope.

## Freeze And Git Gate

- [ ] No hosting, deployment, DNS, Supabase migration, provider, feature, or
      frontend redesign change is present.
- [ ] No production secret or customer data is present.
- [ ] Local backup creates a non-empty custom-format PostgreSQL dump without
      including `.env` or secret configuration.
- [ ] Restore validation refuses the live database and restores only into a new,
      previously absent database.
- [ ] Demo prepare can run repeatedly without duplicates or a 500 response.
- [ ] Guarded demo reset takes a safety backup by default, removes only fixed
      synthetic records, and preserves non-demo investigations.
- [ ] `./scripts/local/check_local_health.ps1` passes.
- [ ] `git diff --check` passes and the diff contains only the current phase.
- [ ] `git status` is reviewed before commit.
- [ ] Commit uses the message required by the current phase.
- [ ] Push to `origin/dev` succeeds and the working tree is clean/synchronized.
- [ ] If `v5.0.0-rc2` already exists, verify its target instead of recreating or
      moving it blindly; otherwise create it only on the validated package commit.
- [ ] Push `v5.0.0-rc2` only after the release-package commit reaches
      `origin/dev`, then verify the local and remote tag targets match.

## Phase 5AB monitoring reliability

- [ ] Healthy required dependencies remain **Platform healthy** when optional
      host telemetry is unavailable; container and host-agent metrics are
      labeled accurately.
- [ ] Recovered overview alerts retire, refresh clears stale banners, and alert
      dedupe/cooldowns/maintenance suppression prevent refresh spam.
- [ ] Recon timeout, HTTP, and JSON parse failures are grouped by provider;
      valid stored entities survive partial failures and retry remains enabled.
- [ ] LAN service checks are disabled by default, admin-operated, TCP-connect
      only, rate-limited, private/allowlisted, and bounded by configured ports,
      host limits, and timeout.
- [ ] Port 22 and approved non-standard SSH banners receive clear service and
      confidence labels without storing raw or sensitive banner content.
- [ ] Monitoring tabs, cards, notification dropdown, empty states, tooltips,
      buttons, and alert actions fit small widths without clipping or raw errors.
- [ ] No public scanning, authentication, brute force, command execution,
      exploitation, intrusive testing, hosting, deployment, DNS, or Supabase
      change is present.

## Phase 5AC history and timeline

- [ ] New asset, offline/online, hostname/MAC, port open/closed, service guess,
      non-standard SSH, stale/resumed agent, threshold, and baseline transitions
      produce bounded change events only when state changes.
- [ ] Service history preserves previous/current TCP status, service guess,
      confidence, source, and observed time without raw banners or secrets.
- [ ] Change APIs enforce authentication, role access, pagination, filters,
      safe 404/422 responses, and audited acknowledgement.
- [ ] Change-derived notifications respect policy cooldowns, dedupe limits,
      suppressions, and maintenance windows.
- [ ] Change Timeline and asset history views render useful loading, empty,
      error, filtering, and acknowledgement states without horizontal overflow.

## Phase 5AD alert triage and overlays

- [ ] Triage is user-scoped and supports status, severity, source, and asset
      filters with bounded pagination.
- [ ] Assignment, investigate, mute/unmute, resolve, and false-positive actions
      return clean errors and write audit events without secrets.
- [ ] Maintenance suppression remains distinct from manual mute; monitoring and
      notification history continue unchanged.
- [ ] Analysts cannot mute critical alerts or assign another user.
- [ ] Activity Inbox overlays page/sidebar content, scrolls independently, and
      closes on outside click or Escape without clipping at small dimensions.
- [ ] Alerts show useful loading, empty, retry, action, and disabled states with
      no raw endpoint errors, crash screen, or horizontal overflow.
