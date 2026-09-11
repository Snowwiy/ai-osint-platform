# RavenTech OSINT Desktop Operator Manual

Version: `5.0.0-rc6`
Audience: authorized local operators and private desktop testers

RavenTech OSINT Desktop is a local Windows shell for the existing RavenTech
OSINT web platform. It shows setup and service status, embeds the local web UI
when it is ready, and can invoke five fixed repository launchers after the
required confirmation. It is not a hosted service, a remote administration
tool, or a replacement for the browser workflow.

## Local architecture

The desktop executable uses Tauri and Windows WebView2. It loads its own local
setup/status UI and, when available, embeds the Vite frontend at
`http://localhost:5173`. The frontend continues to call the FastAPI backend at
`http://localhost:8000`.

Docker Compose separately runs FastAPI, PostgreSQL, Redis, and the worker. The
repository and local configuration remain outside the desktop package. The
portable app and installer do not contain or install Docker, the backend, the
database, Redis, project data, reports, backups, credentials, or `.env` files.

Browser mode remains available at `http://localhost:5173` and uses the same
backend and data as desktop mode.

## Prerequisites

- Windows 10 or 11 with Microsoft Edge WebView2 Runtime
- the RavenTech OSINT repository at the RC6 source revision
- Docker Desktop with Docker Compose, started by the operator
- a local `.env` created and reviewed from `.env.example`; never copy it into a
  distribution package
- ports `8000` and `5173` available on loopback
- Node.js/npm and installed frontend dependencies when running the Vite
  frontend from source
- an account authorized for the intended RavenTech workflow

Rust, Cargo, Tauri CLI, and NSIS are build prerequisites only. They are not
needed to run an already-built portable executable or installer.

## First-run setup

1. Start RavenTech OSINT Desktop. The Project stage opens before the platform UI.
2. Enter the absolute path to the repository root. The desktop does not use a
   broad filesystem browser.
3. Select **Validate and save** / **Validar y guardar**.
4. Review the Project, Prerequisites, and Local services stages and follow the
   displayed next action.
5. Start Docker Desktop yourself if it is unavailable or stopped. The desktop
   never installs or starts Docker automatically.
6. Start the platform and frontend as described below, then use **Check** to
   refresh status. Open the local app when frontend and backend are ready.

An accepted project path must resolve to a canonical directory containing the
expected Compose file, Python project marker, `backend/app`, `frontend/package.json`,
`desktop/`, and all five approved scripts under `scripts/local/`. The approved
scripts must match the copies pinned into the desktop build. Empty, missing,
incomplete, or altered repositories are rejected and remain copy-only.

The saved path is a local preference in the current user's application-config
directory. It is not added to the repository or distribution package. Path
resolution tries the saved path first, then matching current-directory ancestry,
then development executable ancestry, and finally copy-only guidance.

## Start, check, stop, and restart

The desktop may invoke only these exact, argument-free repository scripts:

- `scripts/local/start_platform.ps1`
- `scripts/local/stop_platform.ps1`
- `scripts/local/restart_platform.ps1`
- `scripts/local/check_platform.ps1`
- `scripts/local/open_platform.ps1`

Start, stop, and restart require an explicit confirmation dialog. Check and
open-frontend remain deliberate button actions. Output is bounded, time-limited,
and sanitized. If project validation or PowerShell execution is unavailable,
use the displayed copy-only command instead.

From the repository root, the equivalent operator workflow is:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\local\start_platform.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\local\check_platform.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\local\restart_platform.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\local\stop_platform.ps1
```

Run the frontend separately:

```powershell
cd frontend
npm run dev
```

The desktop does not accept command text, script names, or arguments from the
operator. It cannot run database reset, backup, restore, remote, router, or
scanning commands.

## Health checks

Use **Check** in the desktop setup/status screen or inspect the fixed local URLs:

- frontend: `http://localhost:5173`
- backend: `http://localhost:8000`
- health: `http://localhost:8000/health`
- readiness: `http://localhost:8000/health/ready`
- release: `http://localhost:8000/api/v1/release`

The RC6 acceptance value is `5.0.0-rc6`. A reachable health endpoint with failed
readiness is a degraded state: inspect the Docker services and migration state
before continuing. A release mismatch means the source/services do not match
this desktop candidate. Do not treat a raw port conflict as platform readiness.

## Login and registration

Open the embedded frontend or browser UI and sign in with an existing local
account. No default password is shipped in the desktop package.

Public registration is disabled by default. When a local administrator has
explicitly enabled it, use **Register** on the login screen, enter the requested
username, email, optional full name, password, and invite code when required.
Registration never creates an administrator. If approval is enabled, an active
administrator must approve the account under **Admin > Users** before it can be
used. Do not place passwords or invite codes in support logs or handoff records.

## Language switch

Use the language selector on the login screen or in the application shell to
choose **English** or **Español**. The web UI stores the choice locally as
`raventech.language`; the desktop setup screen also supports both languages.
Report language is selected separately when a report is generated. English is
the fallback for untranslated dynamic text.

## Monitoring overview

After signing in, open **Monitoring** / **Centro de monitoreo**. Access depends
on role and investigation membership. The center presents local service health,
system signals, watched investigations/assets, alert history, maintenance
windows, authorized LAN observations, endpoint coverage, vulnerability baseline,
and endpoint posture. Monitoring uses stored and explicitly enabled local
signals; it is not an external uptime service.

### LAN monitoring and service checks

LAN monitoring is disabled by default and restricted to administrator-configured
private ranges. Docker may not see host neighbor information, so an empty result
is not necessarily a failure. Static/router observations or the optional manual
endpoint agent are documented fallbacks.

TCP service checks are separately gated. Before running one, verify that the
asset is an existing, authorized, monitored private-LAN asset and that the port
is configured. Checks perform bounded TCP-connect observations only: no login,
banner exploitation, vulnerability scanning, or public-network scanning occurs.
See `LAN_MONITORING.md` before enabling this feature.

### Endpoint agents

The **Endpoint Agents** tab is administrator restricted. Create an enrollment
token only for an approved device, then use the UI's copyable Windows or Linux
instruction and enter the token only at the secure prompt. Agents are manually
started, localhost/private-backend constrained, and have no persistence,
autostart, remote shell, browser-history collection, password collection, or
remote-command channel. Stop a foreground agent with `Ctrl+C`. See
`LOCAL_MONITORING.md` for enrollment, expiry, freshness, and coverage details.

### Posture recommendations

The **Security Posture** tab correlates stored authorized LAN observations with
optional agent telemetry. Select a stored asset and run an advisory assessment,
then review open recommendations. Acknowledge or resolve a recommendation only
after the real manual action is verified. Scores and recommendations are
advisory: the platform does not patch endpoints, change firewall/router/VLAN
settings, isolate devices, or validate exploits.

## Reports and export

Open an investigation's **Reports** tab or the **Reports Center**. Select the
report type and English/Spanish report language, generate from stored case data,
review warnings and content, and approve according to local policy. Supported
exports include PDF, DOCX, HTML, and Markdown. Treat every output as potentially
sensitive. Reports require analyst review and are not evidence of regulatory or
legal completeness. Generated reports are not included in desktop artifacts.

## Backup and restore

Backup and restore are separate, manual repository maintenance procedures; the
desktop launcher cannot invoke them. From the repository root, create an ignored
PostgreSQL backup with:

```powershell
.\scripts\local\backup_db.ps1
```

`-IncludeReports` additionally archives generated report storage and therefore
creates sensitive data that must remain private and outside desktop artifacts.

Restore validation refuses the live database and creates a new database name:

```powershell
.\scripts\local\restore_db.ps1 -BackupPath .\backups\local\raventech-<timestamp>.dump
```

Do not attempt an unreviewed cutover or extract a report archive into the live
volume. Follow `LOCAL_BACKUP_RESTORE.md` for safeguards and verification.

## Troubleshooting

- **Wrong or missing project path:** enter the repository root, not `desktop/`
  or `frontend/`. Restore altered/missing approved scripts from trusted Git
  history; do not weaken validation.
- **Docker unavailable:** install Docker separately under organizational policy,
  start Docker Desktop, and retry. The desktop cannot install it.
- **Backend unreachable:** run the approved start workflow, inspect
  `docker compose ps` and bounded service logs, then check `/health`.
- **Readiness degraded or migrations pending:** run the documented local start
  workflow, which applies intended migrations, then check readiness again. Do
  not reset the database.
- **Frontend unreachable:** from `frontend/`, install already-approved
  dependencies as needed and run `npm run dev`.
- **Port 8000 or 5173 unavailable:** stop the unrelated process or reconfigure it
  outside this workflow. The RC6 desktop candidate uses fixed local defaults.
- **Copy failed:** select the displayed command and copy it manually.
- **SmartScreen warning:** the installer is unsigned. Verify its SHA-256 value
  against the package manifest and follow organizational policy; do not describe
  or treat it as trusted software.
- **Docker/LAN firewall prompt:** only loopback access is required for the
  desktop web flow. Do not approve public-network exposure for ports 8000/5173.
- **Raw application error:** record the friendly status and timestamp, not
  credentials or `.env`; consult `LOCAL_HEALTH_REPAIR.md`.

## Limitations and safety boundary

- RC6 is a private, unsigned local-test candidate, not a public release.
- Docker services and the Vite frontend remain separately managed prerequisites.
- Installed-app and clean-uninstall behavior require real Windows host QA.
- There is no code signing, auto-update, service autostart, production package,
  hosting, deployment, DNS, or Supabase migration.
- There is no bundled backend, PostgreSQL, Redis, database, report set, backup,
  credential, or secret.
- The desktop has no broad shell or filesystem plugin permission and no arbitrary
  or remote command execution.
- There is no router automation, remote administration, new scanning, or
  offensive functionality.

For build provenance and private transfer steps, see
`DESKTOP_PRIVATE_HANDOFF.md`. For acceptance, use
`DESKTOP_OPERATOR_ACCEPTANCE_CHECKLIST.md` and `FINAL_QA_CHECKLIST.md`.
