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
- Session expiry should redirect to login.
- Backend `401` responses outside login usually mean the access token expired
  or was cleared.
- Do not expose request IDs in the normal login card.

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
