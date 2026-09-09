# RavenTech OSINT Final QA Checklist

Version: `5.0.0-rc2`

Run from the repository root unless a section says otherwise. Complete this
checklist with synthetic or explicitly authorized data only. A failed required
check blocks the Phase 5S commit and push.

## Automated Validation

- [ ] `docker compose run --rm backend python -m ruff check app workers tests`
- [ ] `docker compose run --rm backend python -m mypy app workers`
- [ ] `docker compose run --rm backend python -m pytest tests/ -q`
- [ ] `docker compose run --rm backend python -m pip check`
- [ ] `docker compose exec backend alembic check`
- [ ] `curl http://localhost:8000/health` returns `status: ok`.
- [ ] `curl http://localhost:8000/health/ready` returns `status: ok`.
- [ ] `curl http://localhost:8000/api/v1/release` returns `5.0.0-rc2` and
      `0028_phase5p_quality` without secrets.
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

## UI And Portfolio Review

- [ ] No normal flow shows raw endpoint dumps, stack traces, `undefined`, or
      `null` text.
- [ ] No long ID, URL, tab row, table, or modal causes horizontal page overflow.
- [ ] No React crash screen appears; retry/empty/degraded states are readable.
- [ ] Screenshot set follows `SCREENSHOTS_CHECKLIST.md` and contains only
      synthetic data.
- [ ] Demo follows the locked 12-step order in `PORTFOLIO_DEMO_FLOW.md`.

## Freeze And Git Gate

- [ ] No hosting, deployment, DNS, Supabase migration, provider, feature, or
      frontend redesign change is present.
- [ ] No production secret or customer data is present.
- [ ] `git diff --check` passes and the diff contains only Phase 5S files.
- [ ] `git status` is reviewed before commit.
- [ ] Commit uses `chore: freeze platform and prep portfolio package`.
- [ ] Push to `origin/dev` succeeds and the working tree is clean/synchronized.
