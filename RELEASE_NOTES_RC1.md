# RavenTech OSINT 5.0.0-rc1 Release Notes

Release name: RavenTech OSINT 5.0.0-rc1

Release channel: release-candidate

## Summary

RavenTech OSINT 5.0.0-rc1 is a portfolio-ready release candidate for a
defensive OSINT and threat investigation workspace. It focuses on authorized
scope, passive evidence collection, deterministic findings, remediation
workflow, governance, reporting, and auditability.

## Major Capabilities

- Authenticated FastAPI backend with PostgreSQL, Redis, Alembic, and worker
  foundation
- React/Vite/TypeScript analyst workspace with RavenTech dark UI
- Investigation lifecycle, membership, ownership, notes, tasks, and review board
- Passive recon evidence model for domains, URLs, IPs, services, technologies,
  certificates, and relationships
- Deterministic findings, remediation workflow, validation workflow, and case
  closure controls
- Evidence intelligence, IOC intelligence, and defensive threat intelligence
  workspace
- Correlations Cards, Graph, and Table views
- Optional AI analysis with deterministic fallback when the provider is missing
  or unavailable
- Executive dashboard, risk posture, report approval, and stakeholder-ready
  report exports
- HTML, Markdown, PDF, and DOCX report downloads
- Governance settings, feature flags, export controls, retention posture, audit
  log, and operations center
- Public registration controls, admin account approval, user status management,
  and last-active-admin safeguards
- Engagement scope governance with client metadata, authorization status,
  approved scope items, authorization evidence references, and advisory
  out-of-scope warnings
- Case closure workflow with deterministic final checklist, final risk rating,
  client deliverable tracking, evidence package manifest, and closure audit trail
- Internal Notification Center and Activity Inbox for workflow alerts, pending
  approvals, assigned work, closure blockers, report readiness, scope warnings,
  and governance reminders
- RBAC-aware internal Global Search, private Saved Views, dashboard Quick Access,
  and pinned analyst navigation shortcuts
- Admin Data Quality Center with bounded local scans, persistent issue workflow,
  safe maintenance dry runs, and non-destructive recommendations
- Release metadata endpoint: `GET /api/v1/release`
- Synthetic demo seed and clear tooling for portfolio demonstrations

## Defensive-Only Scope

This release candidate intentionally excludes active scanning, exploitation,
payload generation, malware handling, autonomous agents, internet-wide
enumeration, billing, SSO, external integrations, and cloud deployment
implementation.

Notifications in this release are internal database-backed workflow alerts only.
Email, SMS, browser push, Slack, Discord, Teams, and third-party notification
delivery are intentionally not included.

Global Search in this release is internal-only and database-backed. It does not
use external search providers, crawl targets, or perform internet-wide
enumeration.

The platform should be presented as a defensive intelligence and investigation
workspace, not as an offensive testing platform.

## Demo Flow

Recommended 10-minute flow:

1. Login
2. Open dashboard and health posture
3. Open `[DEMO] Authorized External Exposure Review`
4. Review the linked demo engagement, approved scope, and passive recon evidence
5. Review deterministic findings
6. Review correlations Cards, Graph, and Table
7. Review IOCs, Evidence Intelligence, and Threat Intelligence
8. Open AI Analysis fallback or live analysis if configured
9. Review remediation tasks and defensive playbooks
10. Open Case Closure and review deliverables/evidence package readiness
11. Open Activity Inbox and mark one demo workflow alert as read
12. Use Ctrl+K Global Search and open a pinned saved view from Quick Access
13. Generate an executive report
14. Download PDF, DOCX, HTML, and Markdown
15. Open audit, governance, demo checklist, and operations center

See `PORTFOLIO_DEMO_FLOW.md` for presenter notes.

## Demo Data

Seed:

```powershell
docker compose exec backend python scripts/seed_demo_data.py
```

Clear:

```powershell
docker compose exec backend python scripts/seed_demo_data.py --clear
```

Admin API:

- `POST /api/v1/admin/demo/seed`
- `DELETE /api/v1/admin/demo/clear`

Demo records are synthetic, idempotent, clearly labeled `[DEMO]`, and use
reserved identifiers. They do not represent a real organization, compromise, or
live network activity.

## Validation Commands

Backend:

```powershell
docker compose run --rm backend python -m ruff check app workers tests
docker compose run --rm backend python -m mypy app workers
docker compose run --rm backend python -m pytest tests/ -q
docker compose run --rm backend python -m pip check
docker compose exec backend alembic check
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
curl http://localhost:8000/api/v1/release
```

Frontend:

```powershell
cd frontend
npm run build
```

Docker:

```powershell
docker compose ps
docker compose logs backend --tail=100
```

## Upgrade And Migration Notes

- Apply migrations before starting the demo:
  `docker compose exec backend alembic upgrade head`
- Confirm the active migration:
  `docker compose exec backend alembic current`
- Confirm migration drift:
  `docker compose exec backend alembic check`
- The Phase 5E migration revision ID must remain under Alembic's 32-character
  storage limit: `0022_phase5e_case_review`.
- Phase 5P advances the head to `0028_phase5p_quality` and adds only the
  non-destructive `data_quality_issues` table and supporting indexes.

## Known Limitations

- Passive recon only
- No active scanning or exploitation
- AI is optional and degrades to deterministic fallback when unavailable
- No cloud deployment implementation is included
- Engagement records are governance metadata only; they are not tenant
  boundaries, billing, hosted client portal access, isolation, or legal document
  storage.
- Case deliverables are tracked as metadata and manifest records; no external
  file storage, hosting, or client delivery portal is included.
- Notifications are internal-only records; no email, SMS, push, or chat
  integrations are included.
- Global Search is internal-only; no external search provider, crawling, or
  internet-wide discovery is included.
- Saved Views are user-specific filter shortcuts and must not be used to store
  credentials, tokens, API keys, invite codes, or secrets.
- Data Quality Center results are deterministic recommendations, not autonomous
  cleanup decisions. No source record is automatically deleted or rewritten.
- No external paid threat feeds are required or bundled
- Demo data is synthetic
- Local setup assumes Docker Compose, PostgreSQL, Redis, and frontend commands
  run from `frontend/`

See `KNOWN_LIMITATIONS.md` for the full list.

## Troubleshooting Notes

- If backend health is degraded, run migrations and inspect backend logs.
- If frontend cannot reach the API, verify `VITE_API_BASE_URL`.
- If AI returns a provider error, confirm `ANTHROPIC_API_KEY`,
  `ANTHROPIC_MODEL`, and the AI feature flag. The deterministic fallback should
  remain usable.
- If report downloads start but the UI shows an error, inspect the report
  download handler and backend response status.
- If demo data is stale, clear and reseed it with the script above.

## Release Candidate Acceptance

Accept RC1 only after the manual QA checklist passes and no raw endpoint errors,
React crash screens, broken report exports, or unexpected migration drift are
present.
