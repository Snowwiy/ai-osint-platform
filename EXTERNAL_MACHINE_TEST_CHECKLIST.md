# RavenTech OSINT RC6 External Machine Test Checklist

Candidate: `5.0.0-rc6`

Use this checklist to transfer and test RavenTech OSINT Desktop on a second,
authorized Windows x64 machine. The candidate is private, local-only, and
unsigned. It is not a public release or a self-contained server application.

Record the receiving machine's Windows version, tester, test date, source
commit, manifest identity, and SHA-256 results in an approved private QA record.
Never record `.env` values, passwords, invite codes, enrollment tokens, provider
credentials, database contents, or report contents.

## 1. Understand the two transfer inputs

The receiving machine needs two separate inputs:

1. A RavenTech OSINT repository checkout for Docker services, migrations, the
   Vite frontend, configuration, and the five approved launcher scripts.
2. The ignored private distribution folder for the portable executable and
   unsigned installer.

Prefer cloning the repository through approved Git access. Transfer the complete
aggregate folder without renaming or adding files:

`desktop/dist-local-release/RavenTech-OSINT-Desktop-5.0.0-rc6/`

It contains exactly:

- `RavenTech OSINT Desktop.exe`
- `RavenTech-OSINT-Desktop-5.0.0-rc6-unsigned-setup.exe`
- `README.md`
- `LOCAL_STARTUP_INSTRUCTIONS.md`
- `KNOWN_LIMITATIONS.md`
- `SHA256SUMS.txt`
- `local-release-manifest.json`

The separate portable and installer folders may be retained by the builder for
QA, but the aggregate folder is the preferred private transfer unit. Do not copy
an installed application directory as a substitute for the installer.

## 2. Do not transfer local or sensitive data

Do not add any of the following to the artifact folder or repository transfer:

- `.env` or any environment-specific configuration
- passwords, secrets, API/provider keys, invite codes, credentials, or tokens
- database dumps, PostgreSQL/Redis volumes, or other database files
- backups or restore-test data
- generated reports, evidence exports, screenshots, or case data
- application, Docker, build, or operator logs
- saved project-path preferences or other local user data
- `node_modules/`, Rust `target/`, frontend `dist/`, or unrelated build caches

Create `.env` independently on the receiving machine from the tracked template.
If test data must be shared, use a separately approved data-handling procedure;
never put it in the desktop distribution.

## 3. Receiving-machine prerequisites

Required to run the local platform and desktop shell:

- Windows 10 or 11 x64 with Microsoft Edge WebView2 Runtime
- Docker Desktop with Docker Compose, installed and started manually
- Git for the preferred clone and revision-verification workflow
- Node.js and npm only for browser/development mode or rebuilding artifacts
- access to the RavenTech repository and permission to create a local `.env`
- loopback port `8000` available; port `5173` only for optional Vite mode

Required only when rebuilding desktop artifacts from source:

- Rust/Cargo compatible with the pinned `rust-version`
- locked desktop npm dependencies, including the pinned Tauri CLI
- cached Tauri/NSIS build tools for the unsigned installer workflow

Rust, Cargo, Tauri CLI, and NSIS are not required to run the already-built
portable executable or unsigned installer. Docker, the repository, and backend
remain required. The React frontend is embedded in both portable and installed
builds; Vite is not a release runtime prerequisite.

## 4. Verify the transferred package before execution

- [ ] Confirm the folder has exactly the seven files listed above.
- [ ] Open `local-release-manifest.json` as text and confirm the app/version,
      intended source commit, `signed: false`, `localOnly: true`, and
      `dockerRequired: true` fields.
- [ ] Independently calculate each payload SHA-256 and compare it with
      `SHA256SUMS.txt`.
- [ ] Stop if any file is missing, extra, renamed, or has a checksum mismatch.

From inside the aggregate folder:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath '.\RavenTech OSINT Desktop.exe'
Get-FileHash -Algorithm SHA256 -LiteralPath '.\RavenTech-OSINT-Desktop-5.0.0-rc6-unsigned-setup.exe'
Get-FileHash -Algorithm SHA256 -LiteralPath '.\README.md'
Get-FileHash -Algorithm SHA256 -LiteralPath '.\LOCAL_STARTUP_INSTRUCTIONS.md'
Get-FileHash -Algorithm SHA256 -LiteralPath '.\KNOWN_LIMITATIONS.md'
```

Do not continue merely because Windows allows execution; this package has no
code signature and Windows trust is not asserted.

## 5. Clone and configure the repository

Replace the placeholder with the organization's approved repository URL:

```powershell
git clone APPROVED_REPOSITORY_URL RavenTech-OSINT
Set-Location RavenTech-OSINT
git switch dev
git status --branch --short
git rev-parse HEAD
git rev-parse v5.0.0-rc6
```

Use the assigned `dev` revision for the latest private handoff documentation, or
check out the immutable RC6 tag when the test assignment explicitly requires
the original freeze source. Never recreate or move the existing tag.

Create local configuration once and replace development placeholders with
locally approved values:

```powershell
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

Do not overwrite an existing `.env`, commit it, print it, or copy it back to the
sending machine.

## 6. Start the local platform and apply migrations

- [ ] Start Docker Desktop manually and wait until its engine is ready.
- [ ] Build local images if this is a new checkout.
- [ ] Run the approved platform launcher from the repository root.
- [ ] Confirm the migration current/head state without resetting data.

```powershell
docker version
docker compose version
docker compose build
.\scripts\local\start_platform.ps1
docker compose exec -T backend alembic upgrade head
docker compose exec -T backend alembic heads
docker compose exec -T backend alembic current
```

The start script already runs the safe migration upgrade. The explicit Alembic
commands provide receiving-machine evidence. Never use
`docker compose down -v` as setup or recovery.

## 7. Create a local login and start the frontend

With reviewed local administrator values in `.env`, create or confirm the
administrator. The following frontend commands are optional and apply only to
browser/development testing:

```powershell
docker compose exec -T backend python scripts/create_admin.py
Set-Location frontend
npm ci
npm run dev
```

If testing browser mode, keep Vite running and open a second PowerShell window
at the repository root. A portable/installed test should also run with Vite
stopped and report **Frontend: Embedded**.
Public registration is disabled by default. If explicitly enabled for the test,
registration creates only a non-admin account and may require invite/approval.
Do not transmit or record credentials.

## 8. Verify health and release identity

```powershell
curl.exe -fsS http://localhost:8000/health
curl.exe -fsS http://localhost:8000/health/ready
curl.exe -fsS http://localhost:8000/api/v1/release
```

- [ ] Health and readiness report `status: ok`.
- [ ] Release reports exactly `5.0.0-rc6`.
- [ ] Migration current/head is `0036_phase5ai_posture`.
- [ ] `http://localhost:5173` opens the normal browser application.

## 9. Run portable mode

1. Launch `RavenTech OSINT Desktop.exe` from the verified aggregate folder.
2. In the first-run Project stage, enter the absolute receiving-machine
   repository root—not `desktop/`, `frontend/`, or the artifact folder.
3. Select **Validate and save** / **Validar y guardar**.
4. Confirm Docker, ports, backend, frontend, release, migrations, and all five
   approved scripts show the expected state.
5. Open the embedded local UI, sign in, and switch English/Spanish.
6. Confirm an invalid path or missing/altered script forces copy-only guidance.

Start, stop, and restart must require explicit confirmation. The desktop may
execute only `start_platform.ps1`, `stop_platform.ps1`,
`restart_platform.ps1`, `check_platform.ps1`, and `open_platform.ps1` from the
validated repository. It accepts no command text, arguments, or alternate
script names.

## 10. Run only synthetic demo data

After explicitly enabling demo mode in the receiving machine's untracked
`.env`, restart the backend and seed the fixed synthetic workspace:

```powershell
docker compose exec -T backend python -m scripts.seed_demo_data
```

If reset behavior is assigned, first read `LOCAL_BACKUP_RESTORE.md`, then use
only the guarded wrapper:

```powershell
.\scripts\local\reset_demo.ps1 -Confirmation RESET-DEMO
```

The reset creates a local backup by default. Keep it and all report exports out
of the artifact folder. Perform no real scanning or unauthorized LAN checks.

## 11. Test install and uninstall

1. Verify the installer checksum again.
2. Run `RavenTech-OSINT-Desktop-5.0.0-rc6-unsigned-setup.exe` as the current
   user and record the expected unsigned/SmartScreen warning.
3. Follow organizational policy; do not describe or treat the warning bypass as
   proof of trust.
4. Launch **RavenTech OSINT Desktop** from the Start menu and repeat project-path,
   offline/ready, localization, and copy-only checks outside repository ancestry.
5. Open **Settings > Apps > Installed apps**, select **RavenTech OSINT Desktop**,
   and choose **Uninstall**.
6. Confirm the application directory and Start-menu shortcut are removed and no
   service, scheduled task, updater, or public-network listener was installed.
7. Confirm the repository, Docker volumes, database, Redis data, reports, and
   other operator-owned data were not removed.

Complete `DESKTOP_OPERATOR_ACCEPTANCE_CHECKLIST.md` and retain the result only
in the approved private QA location.

## 12. Recovery checks

Recovery is manual and non-destructive. The desktop does not install software,
change firewall/system settings, terminate other processes, rewrite `.env`, or
reset data.

### Docker is not installed

Stop the test. Install Docker Desktop through the organization's approved
software process, confirm licensing/system requirements, restart if required,
then rerun `docker version`. The desktop cannot install Docker.

### Docker is installed but not running

Start Docker Desktop manually and wait for `docker version` to report both
client and server. Then run `docker compose ps` and the approved start script.

### Port 8000 or 5173 is busy

Identify the listener without terminating it automatically:

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue
Get-NetTCPConnection -State Listen -LocalPort 5173 -ErrorAction SilentlyContinue
```

Have the owner stop or reconfigure the unrelated process under local policy.
RC6 uses fixed loopback URLs; do not expose either port publicly as a workaround.

### Backend is unreachable

From the repository root, run:

```powershell
docker compose ps
docker compose logs backend --tail=100
.\scripts\local\check_platform.ps1
```

Review bounded local logs without copying secrets. Verify PostgreSQL and Redis
health before retrying the approved start/restart flow.

### Frontend is unreachable

Confirm the command is running from `frontend/`, dependencies were installed,
and Vite reports `http://localhost:5173`:

```powershell
Set-Location frontend
npm ci
npm run dev
```

### Project path is wrong

Enter the absolute repository root containing `docker-compose.yml`,
`frontend/package.json`, `backend/app`, `desktop/`, and `scripts/local/`.
Do not choose the artifact, install, frontend, or desktop directory.

### Approved scripts are missing or altered

Do not weaken validation or execute an unverified replacement. Inspect the
checkout and recover the files through approved Git review:

```powershell
git status --short -- scripts/local
git diff -- scripts/local
```

Revalidate the project path only after the five scripts match trusted source.

### Release mismatch

Compare `/api/v1/release`, `git rev-parse HEAD`, desktop manifest version, and
the assigned revision. Stop mixed-version acceptance, rebuild/restart from the
intended clean source, and verify `5.0.0-rc6`; do not edit version output.

### Migrations are pending

```powershell
docker compose exec -T backend alembic heads
docker compose exec -T backend alembic current
docker compose exec -T backend alembic upgrade head
curl.exe -fsS http://localhost:8000/health/ready
```

Do not reset or replace the database. Escalate migration errors with sanitized
evidence and follow `LOCAL_HEALTH_REPAIR.md`.

### SmartScreen warns about the installer

This is expected because RC6 is unsigned. Verify the filename and SHA-256,
confirm the private source and organizational approval, and follow Windows
security policy. Do not disable SmartScreen or claim the installer is signed.

## Acceptance boundary

Passing this checklist verifies one receiving machine only. It is not public
release approval, signing, production support, or a guarantee for every Windows,
Docker, WebView2, endpoint-security, or policy combination.

No feature, version bump, tag, public release, signing, auto-update, hosting,
deployment, DNS, Supabase migration, router automation, arbitrary shell
execution, remote command execution, or offensive functionality is included.
