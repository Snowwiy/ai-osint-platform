# RavenTech OSINT RC6 Fresh Setup Checklist

Candidate: `5.0.0-rc6`

This checklist is for an authorized operator starting from a clean repository
checkout on Windows. It prepares the validated local Docker/Vite workflow and
the private, unsigned desktop candidate. It does not create a public release,
install system prerequisites automatically, or configure hosting.

Never paste passwords, invite codes, tokens, provider credentials, or `.env`
values into a QA record. Keep generated reports, backups, and desktop artifacts
in their documented ignored locations.

## 1. Clone and verify the repository

- [ ] Clone the repository through the organization's approved Git access and
      change into its root directory.
- [ ] Check out `dev` or the immutable `v5.0.0-rc6` tag according to the test
      assignment. Do not create or move the tag.
- [ ] Run `git status --branch --short` and confirm the checkout is clean.
- [ ] Run `git describe --tags --always` and record the non-secret revision in
      the private QA record.

Example, replacing the placeholder with the approved repository URL:

```powershell
git clone APPROVED_REPOSITORY_URL RavenTech-OSINT
Set-Location RavenTech-OSINT
git status --branch --short
```

## 2. Create the local configuration

- [ ] Confirm `.env` does not already exist before copying the template.
- [ ] Copy `.env.example` once and review every development-only placeholder.
- [ ] Set a strong local administrator password and any explicitly approved
      local feature flags. Do not commit `.env`.

```powershell
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

The RC6 desktop package does not read, copy, or bundle `.env`. Production
secrets, hosted services, DNS, and Supabase are not required for local setup.

## 3. Prepare and start Docker services

- [ ] Install and start Docker Desktop separately under organizational policy.
- [ ] Confirm `docker version` and `docker compose version` succeed.
- [ ] Build the local images and start the fixed services.
- [ ] Apply the existing Alembic migration chain without resetting data.

```powershell
docker compose build
.\scripts\local\start_platform.ps1
docker compose exec -T backend alembic upgrade head
docker compose exec -T backend alembic current
```

The approved start script runs PostgreSQL, Redis, FastAPI, and the Celery worker
and already applies `alembic upgrade head`; the explicit migration commands
above make the clean-setup verification visible. Never use
`docker compose down -v` for routine setup or repair.

## 4. Create an administrator and start the frontend

This section starts browser/development mode. A prebuilt portable or installed
desktop already includes the frontend and can skip the Vite steps.

- [ ] With reviewed `ADMIN_USERNAME`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD` local
      values, create or confirm the local administrator.
- [ ] Install locked frontend dependencies and start Vite from `frontend/`.

```powershell
docker compose exec -T backend python scripts/create_admin.py
Set-Location frontend
npm ci
npm run dev
```

Keep Vite running only while testing browser/development mode and use another PowerShell window for subsequent
commands. Return to the repository root before running root-relative scripts:

```powershell
Set-Location ..
```

## 5. Verify health, readiness, and RC6

- [ ] Confirm health and readiness return structured status `ok`.
- [ ] Confirm release metadata reports exactly `5.0.0-rc6`.
- [ ] Confirm migration current/head is `0036_phase5ai_posture`.

```powershell
curl.exe -fsS http://localhost:8000/health
curl.exe -fsS http://localhost:8000/health/ready
curl.exe -fsS http://localhost:8000/api/v1/release
docker compose exec -T backend alembic heads
docker compose exec -T backend alembic current
```

Expected local URLs are `http://localhost:5173` and
`http://localhost:8000`. Use `LOCAL_HEALTH_REPAIR.md` and `TROUBLESHOOTING.md`
if a check fails; do not reset the database as a generic repair.

## 6. Login or registration

- [ ] Open `http://localhost:5173` and sign in with the configured administrator.
- [ ] Confirm an invalid login shows a friendly error without exposing details.
- [ ] If and only if public registration is intentionally enabled locally,
      register a non-admin account, supply an invite code only when required,
      and complete administrator approval under **Admin > Users**.
- [ ] Switch between English and Spanish and confirm the choice survives refresh.

Public registration is disabled by default and never creates administrators.

## 7. Seed and reset the synthetic demo

- [ ] Enable demo mode only in the untracked local `.env`, restart the backend,
      and seed the fixed synthetic workspace.
- [ ] Verify the demo performs no live recon requests.
- [ ] When reset behavior is part of the assigned test, use only the guarded
      exact confirmation. It creates a safety backup by default.

```powershell
docker compose exec -T backend python -m scripts.seed_demo_data
.\scripts\local\reset_demo.ps1 -Confirmation RESET-DEMO
```

Read `LOCAL_DEMO_BUNDLE.md` and `LOCAL_BACKUP_RESTORE.md` before reset. Never
copy its backup or generated reports into a desktop distribution folder.

## 8. Open the desktop shell and bind the project

- [ ] Install already-approved desktop dependencies from `desktop/`. The locked,
      offline form below is the validated RC6 build path.
- [ ] Run source validation and the Tauri development shell.
- [ ] Enter the absolute repository root in the first-run Project stage and
      select **Validate and save**.
- [ ] Confirm Docker, ports, backend, frontend, release, migrations, and all five
      approved scripts report their expected state.
- [ ] For installed/portable testing, confirm **Frontend: Embedded** even when
      no Vite process is running.

```powershell
Set-Location desktop
npm ci --offline
npm run check
npm run tauri:check
npm run tauri:dev
```

The shell may execute only start, stop, restart, check, and open-frontend via
the five build-pinned PowerShell scripts. Start/stop/restart require explicit
confirmation; invalid paths retain copy-only mode.

## 9. Regenerate private artifacts

- [ ] Build and validate the portable RC6 folder.
- [ ] Build and validate the unsigned current-user NSIS installer.
- [ ] Assemble and validate the private local-release package.
- [ ] Run artifact-aware smoke checks and confirm all output remains ignored.

```powershell
npm run portable:build
npm run portable:validate
npm run installer:build
npm run installer:validate -- --require-artifact
npm run local-release:package
npm run local-release:validate -- --require-artifact
npm run smoke -- --require-artifacts
Set-Location ..
git status --branch --short
```

The aggregate package must contain only the two binaries, README, startup
instructions, known limitations, checksums, and manifest. It must contain no
`.env`, secret, token, credential, database dump, backup, generated report, log,
local user data, backend, PostgreSQL, Redis, or Docker runtime.

## 10. Complete private acceptance

- [ ] Follow `OPERATOR_MANUAL.md` for normal operation.
- [ ] Verify transfer and provenance with `DESKTOP_PRIVATE_HANDOFF.md`.
- [ ] Complete `DESKTOP_OPERATOR_ACCEPTANCE_CHECKLIST.md` for portable and
      installed modes on the authorized Windows host.
- [ ] Confirm uninstall removes the shell and Start-menu shortcut without
      deleting operator-owned repository, Docker, database, or report data.
- [ ] Retain the signed-off checklist privately; do not add it or generated
      binaries to Git.

When the artifacts move to a second Windows host, use
`EXTERNAL_MACHINE_TEST_CHECKLIST.md` for transfer integrity, receiving-machine
prerequisites, project rebinding, recovery, and uninstall evidence.

RC6 remains locked: no feature, version bump, new tag, public release, signing,
auto-update, hosting, deployment, DNS, Supabase migration, router automation,
arbitrary shell execution, remote command execution, or offensive functionality
is part of this checklist.

## Optional authorized LAN acceptance

- [ ] Open Monitoring → Activation as an administrator.
- [ ] Verify `192.168.50.1/24` normalizes to `192.168.50.0/24`, retaining
  `192.168.50.1` as the gateway hint.
- [ ] Review and manually copy the `.env` profile; keep both LAN auto-start
  flags false, then restart Docker manually.
- [ ] Create one short-lived CIDR-limited token and securely capture its one-time
  value; confirm lists and logs expose only its hint.
- [ ] Run one approved endpoint agent or import one router/static observation.
- [ ] Verify heartbeat, service-check eligibility, posture, recommendations, and
  alerts. Run TCP checks only with explicit authorization and enabled config.
- [ ] Confirm the Server tab metric source: native host, ServerHost agent, or
  explicitly scoped Docker container fallback.
- [ ] If native metrics are unavailable, manually run `.\scripts\local\local_monitor_agent.ps1 -Mode ServerHost -BackendUrl http://localhost:8000 -IntervalSeconds 30`.
- [ ] For another approved LAN PC, use `LanEndpoint`, a one-time enrollment token,
  and the confirmed private backend address; never place the token on the command line.
- [ ] If required, manually limit Windows Firewall inbound TCP/8000 to
  `192.168.50.0/24`. Do not enable Public-profile or unrestricted access.
- [ ] Confirm the Monitoring Center runtime card shows last discovery/check times,
  next refresh, asset/import counts, connected-agent coverage, host-metric source,
  and posture/recommendation status without treating disabled options as degraded.
- [ ] Confirm open/closed/filtered/timeout service results and SSH indicators are
  advisory, private-CIDR-only, configured-port-only TCP observations.
