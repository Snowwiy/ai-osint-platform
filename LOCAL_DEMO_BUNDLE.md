# RavenTech OSINT Local Demo Bundle

Release candidate: `5.0.0-rc2`

Supported mode: local Docker Compose with a local Vite frontend

This bundle is a documentation entry point for a reproducible, synthetic,
defensive-only demonstration. It does not deploy the application, configure
DNS, use Supabase, or require production secrets.

## Prerequisites

- Docker Desktop with Docker Compose
- PowerShell 7 or Windows PowerShell
- Node.js and npm for the frontend
- A local `.env` created from `.env.example`
- One active local administrator account

Do not overwrite an existing `.env`. For a first-time local setup only:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose build
Set-Location frontend
npm ci
Set-Location ..
```

Use development-only local values. Do not place `.env`, database dumps,
generated reports, provider keys, or production credentials in the bundle or
source control.

## Start Locally

From the repository root:

```powershell
./scripts/local/start_local.ps1 -StartFrontend
```

The script starts PostgreSQL, Redis, the backend, and the Celery worker; applies
`alembic upgrade head`; waits for readiness; runs the local health check; and
optionally starts Vite. The expected local URLs are:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- API documentation: `http://localhost:8000/docs`

## Optional: Seed Synthetic Demo Data

Set `ENABLE_DEMO_MODE=true` only in the local `.env`, restart the backend, and
prepare the idempotent workspace:

```powershell
docker compose exec -T backend python -m scripts.seed_demo_data
```

The command requires an active administrator, reuses the fixed synthetic
workspace, and does not make live recon requests. Re-running it must not create
duplicate demo records.

Normal platform navigation has no demo-mode banner. The optional seed/reset
controls are available only to administrators under **QA Tools**, and synthetic
records remain labeled so they cannot be mistaken for operational data.
Keep `ENABLE_DEMO_MODE=false` and disable the corresponding Admin Settings flag
when QA data is not needed; this hides/prevents preparation controls without
deleting the guarded seed/reset implementation.

## Reset Synthetic Demo Data

Use the guarded reset wrapper:

```powershell
./scripts/local/reset_demo.ps1 -Confirmation RESET-DEMO
```

It creates a PostgreSQL safety backup by default, clears only the fixed demo
records, and reseeds them. It does not target ordinary investigations. Read
`LOCAL_BACKUP_RESTORE.md` before using the lower-level clear command or skipping
the safety backup.

## Run Health Checks

```powershell
./scripts/local/check_local_health.ps1
curl.exe http://localhost:8000/health
curl.exe http://localhost:8000/health/ready
curl.exe http://localhost:8000/api/v1/release
```

The expected release is `5.0.0-rc2`, with migration head
`0030_phase5z_base` and `status: ok` for health and readiness.

## Generate Demo Reports

1. Sign in with the configured local administrator account.
2. Open the clearly labeled synthetic investigation.
3. Open **Reports**, choose an existing template and report type, and generate
   the report from stored synthetic evidence.
4. Review readiness warnings and analyst-review language.
5. Download each format allowed by governance: PDF, DOCX, HTML, and Markdown.
6. Keep generated exports local and verify they contain no credentials or real
   customer data.

Follow `PORTFOLIO_DEMO_FLOW.md` for the complete 12-step walkthrough.

## Run Final Validation

From the repository root:

```powershell
docker compose run --rm backend python -m ruff check app workers tests
docker compose run --rm backend python -m mypy app workers
docker compose run --rm backend python -m pytest tests/ -q
docker compose run --rm backend python -m pip check
docker compose exec backend alembic check
curl.exe http://localhost:8000/health
curl.exe http://localhost:8000/health/ready
curl.exe http://localhost:8000/api/v1/release

Set-Location frontend
npm run build
Set-Location ..
git status
```

Use `FINAL_QA_CHECKLIST.md` for the full acceptance gate and
`SECRETS_AUDIT_CHECKLIST.md` before sharing any repository snapshot.

## Screenshot And Artifact Checklist

- [ ] Capture only the views listed in
  [SCREENSHOTS_CHECKLIST.md](SCREENSHOTS_CHECKLIST.md).
- [ ] Use only the clearly labeled synthetic demo workspace.
- [ ] Check screenshots for usernames, local paths, tokens, or environment data.
- [ ] Confirm `README.md`, `DEMO_GUIDE.md`, `PORTFOLIO_DEMO_FLOW.md`, and
  `GITHUB_RELEASE_DRAFT.md` agree on version and scope.
- [ ] Confirm health, readiness, release, Alembic, backend checks, and frontend
  build pass.
- [ ] Confirm `.env`, `backups/`, `reports_output/`, `frontend/dist/`, caches,
  and `frontend/node_modules/` are absent from Git.
- [ ] Confirm the working tree is clean and synchronized with `origin/dev`.
- [ ] Confirm `v5.0.0-rc2` points to the validated release-package commit.

## Known Local Limitations

- Local Docker Compose is the only validated runtime; hosting is deferred.
- Supabase has not been configured or migrated, and Supabase Auth is not used.
- Public registration is disabled by default and must remain governed.
- AI providers are optional; deterministic fallback remains available.
- Demo data is synthetic and reports require analyst review.
- The platform performs passive, defensive OSINT investigation only. Optional
  LAN reachability checks are bounded and disabled by default; no vulnerability
  scanning, exploitation, crawling, or autonomous offensive actions are included.
- See `KNOWN_LIMITATIONS.md` for dependency and operational advisories.
