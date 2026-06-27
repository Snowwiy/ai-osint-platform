# Release Candidate Checklist

Use this before demos, portfolio recording, or local deployment review.

## Backend

- `docker compose up -d`
- `docker compose exec backend alembic upgrade head`
- `docker compose run --rm backend python -m ruff check app workers tests`
- `docker compose run --rm backend python -m mypy app workers`
- `docker compose run --rm backend python -m pytest tests/ -q`
- `docker compose run --rm backend python -m pip check`
- `docker compose exec backend alembic check`
- `curl http://localhost:8000/health`
- `curl http://localhost:8000/health/ready`
- `curl http://localhost:8000/api/v1/release`

## Frontend

- `cd frontend`
- `npm install`
- `npm run build`
- Confirm no React crash screen appears during manual navigation
- Confirm stale errors clear after successful refresh/generation/download

## Manual Product Flow

- Login with valid credentials
- Confirm wrong credentials show a clean invalid-login message
- Open dashboard and Operations Center
- Create or open a demo investigation
- Add authorized target
- Run passive recon or inspect synthetic passive recon evidence
- Generate or review findings
- Check Correlations Cards, Graph, and Table
- Open Evidence Intelligence and Threat Intelligence
- Open AI Analysis and verify fallback/degraded state if no provider key exists
- Generate/download PDF, DOCX, HTML, and Markdown reports
- Submit case review, report approval, and remediation validation where relevant
- Open Review Board
- Open Admin Settings, Audit Log, and Demo Checklist

## Demo Data

- Enable demo mode only in a non-production environment
- Seed demo data:
  `docker compose exec backend python scripts/seed_demo_data.py`
- Clear demo data:
  `docker compose exec backend python scripts/seed_demo_data.py --clear`
- Confirm all demo records are labeled `[DEMO]`
- Confirm no demo screen makes a real compromise claim

## Release Packaging

- README is current and portfolio-ready
- `RELEASE_NOTES_RC1.md` exists and matches version `5.0.0-rc1`
- `PORTFOLIO_DEMO_FLOW.md` exists
- `SCREENSHOTS_CHECKLIST.md` exists
- `KNOWN_LIMITATIONS.md` is current
- Troubleshooting includes frontend run path and migration recovery
- No secrets are present in docs, screenshots, diagnostics, or exports

## Acceptance Criteria

- Backend health is ok or only expected degraded optional checks are present
- Migrations are current
- Frontend build passes
- Reports export successfully
- Audit events appear for major actions
- Governance and feature flags load
- No raw endpoint dumps or stack traces appear in normal UI
