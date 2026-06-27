# RavenTech OSINT V1 Release Checklist

## Backend Readiness

- [ ] `docker compose up -d` starts PostgreSQL, Redis, backend, and worker.
- [ ] `curl http://localhost:8000/health` returns `ok` or understandable
      degraded component status.
- [ ] `curl http://localhost:8000/api/v1/release` returns safe release metadata.
- [ ] `docker compose exec backend alembic upgrade head` completes.
- [ ] `docker compose run --rm backend alembic check` reports no drift.
- [ ] No secrets appear in logs, health responses, reports, or frontend output.

## Frontend Readiness

- [ ] Frontend commands are run from `frontend/`.
- [ ] `npm install` completes.
- [ ] `npm run dev` starts the Vite app.
- [ ] `npm run build` completes.
- [ ] Route-level errors show the friendly fallback instead of a raw crash.
- [ ] Dashboard handles missing or degraded executive payloads.

## Authentication And Access

- [ ] Correct login works.
- [ ] Wrong login shows `Invalid username or password.`
- [ ] Session expiry redirects to login.
- [ ] Viewer role remains read-only.
- [ ] Admin-only pages remain hidden or blocked for non-admin users.

## Investigation Demo Flow

- [ ] Create or open an investigation.
- [ ] Authorization statement and scope are visible.
- [ ] Add domain, IP, or URL target.
- [ ] Run passive recon.
- [ ] Partial recon warnings are compact and clear.
- [ ] Generate deterministic findings.
- [ ] Review MITRE/Sigma/detection guidance.
- [ ] Start remediation task or defensive playbook.
- [ ] Generate executive report.
- [ ] Download PDF, DOCX, HTML, and Markdown.

## Governance And Audit

- [ ] Admin Settings loads.
- [ ] Feature flags load and save.
- [ ] Export controls are enforced.
- [ ] Audit page loads with empty and populated states.
- [ ] Archive and restore flows are understandable.

## Portfolio Presentation

- [ ] Demo Guide 10-minute flow is rehearsed.
- [ ] Screenshots avoid secrets and real customer targets.
- [ ] Demo data is labeled clearly when used.
- [ ] Demo data can be seeded and cleared through admin tooling.
- [ ] Wording stays defensive and evidence-backed.
- [ ] Known limitations are acknowledged.

## Release Candidate CI Gates

- [ ] Backend ruff passes.
- [ ] Backend mypy passes.
- [ ] Backend pytest passes without live external providers.
- [ ] Python `pip check` passes.
- [ ] Alembic upgrade and `alembic check` pass.
- [ ] Frontend lint passes.
- [ ] Frontend build passes.
- [ ] No live Anthropic key is required for tests.
- [ ] No external network dependency is required for regression tests.

## Release Candidate Workflow Checks

- [ ] Archive, restore, and purge governance behave correctly.
- [ ] Case review, report approval, and remediation validation workflows work.
- [ ] Review Board shows pending reviews, approvals, validation, changes
      requested, and closure-ready cases.
- [ ] Evidence Intelligence and Threat Intelligence pages handle partial API
      responses.
- [ ] Correlations Cards/Graph/Table do not crash on empty or malformed data.
- [ ] AI fallback preserves citations and communicates degraded provider status.
- [ ] Report exports remain stable for PDF, DOCX, HTML, and Markdown.
- [ ] Release metadata shows `5.0.0-rc1` or the configured release value.
- [ ] `PORTFOLIO_DEMO_FLOW.md`, `SCREENSHOTS_CHECKLIST.md`, and
      `RELEASE_CANDIDATE_CHECKLIST.md` exist.

## Known Limitations For V1

- [ ] No active scanning.
- [ ] No exploitation or offensive automation.
- [ ] No external SSO.
- [ ] No billing or cloud deployment automation.
- [ ] Optional providers depend on configured API keys and rate limits.
