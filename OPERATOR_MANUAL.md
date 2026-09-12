# RavenTech OSINT Desktop Operator Manual

Version: `5.0.0-rc6`
Audience: authorized local operators and private desktop testers

RavenTech OSINT Desktop is a local Windows shell for the existing RavenTech
OSINT web platform. It shows setup and service status, embeds the local web UI
when it is ready, and can invoke six fixed repository launchers after the
required confirmation. It is not a hosted service, a remote administration
tool, or a replacement for the browser workflow.

## Local architecture

The desktop executable uses Tauri and Windows WebView2. Installed and portable
builds load the existing React production build from bundled Tauri assets. That
frontend continues to call the FastAPI backend at `http://localhost:8000`.
Vite at `http://localhost:5173/` is an optional browser/development endpoint.

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
- port `8000` available on loopback; port `5173` only for optional Vite mode
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
6. Start the platform as described below, then use **Check** to refresh status.
   A release build reports **Frontend: Embedded**; open it when the backend is ready.

An accepted project path must resolve to a canonical directory containing the
expected Compose file, Python project marker, `backend/app`, `frontend/package.json`,
`desktop/`, and all six approved scripts under `scripts/local/`. The approved
scripts must match the copies pinned into the desktop build. Empty, missing,
incomplete, or altered repositories are rejected and remain copy-only.

The saved path is a local preference in the current user's application-config
directory. It is not added to the repository or distribution package. Path
resolution tries the saved path first, then matching current-directory ancestry,
then development executable ancestry, and finally copy-only guidance.
The launcher supplies that validated canonical root to the fixed script through
an internal environment value. `start_platform.ps1` validates it again, then
tries its own script location and current directory; failure produces clean
copy-only guidance rather than a null-path PowerShell stack trace.

## Start, check, stop, and restart

The desktop may invoke only these exact, argument-free repository scripts:

- `scripts/local/start_platform.ps1`
- `scripts/local/stop_platform.ps1`
- `scripts/local/restart_platform.ps1`
- `scripts/local/check_platform.ps1`
- `scripts/local/open_platform.ps1`
- `scripts/local/apply_lan_monitoring_config.ps1`

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

For optional browser or desktop-development testing, run Vite separately:

```powershell
cd frontend
npm run dev
```

Installed and portable builds do not require this Vite command. The desktop
does not accept command text, script names, or arguments from the
operator. It cannot run database reset, backup, restore, remote, router, or
scanning commands.

## Health checks

Use **Check** in the desktop setup/status screen or inspect the fixed local URLs:

- frontend: embedded in installed/portable mode
- development frontend: `http://localhost:5173/` (HTTP 2xx `text/html`)
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
- **Frontend unavailable:** a release build should report **Embedded** without
  Vite. In development only, run `npm run dev` from `frontend/`.
- **Port 8000 unavailable:** stop the unrelated process or reconfigure it outside
  this workflow. Port 5173 matters only for optional Vite mode.
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
- Docker/backend services remain separately managed prerequisites; Vite is not
  required for installed/portable UI rendering.
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
Operators starting from a clean checkout should complete
`FRESH_SETUP_CHECKLIST.md` first.
Operators receiving artifacts on another Windows machine should also complete
`EXTERNAL_MACHINE_TEST_CHECKLIST.md` before acceptance.

## Automatic desktop monitoring

After sign-in and backend readiness, the desktop automatically loads the local
Monitoring Center summary and refreshes it every 30 seconds by default. The UI
shows the last and next refresh times, health, alerts and triage, agent coverage,
posture, recommendations, and vulnerability baseline. This is authenticated,
read-only polling; it does not start Docker, discover LAN hosts, or check ports.

A disabled LAN or TCP-check setting is informational: **Monitoring ready, LAN
discovery disabled by configuration** means the core platform is healthy. Enable
active discovery or checks only through the exact local `.env` flags shown in
**Monitoring → Activation**, then restart the existing Docker services. Installed
and portable builds use the embedded frontend; `npm run dev` and port 5173 are
not required.

## Authorized LAN bootstrap for 192.168.50.0/24

As an administrator, open **Monitoring → Activation → Authorized LAN
Bootstrap**. Keep the input `192.168.50.1/24` and gateway hint `192.168.50.1`,
then select **Verify LAN setup**. The `/24` mask clears the last octet and
produces `192.168.50.0/24`; the original host remains a non-operative gateway
hint. Copy the displayed `.env` lines, edit the untracked file manually, and
restart Docker with the displayed command.

Create a short-lived enrollment token limited to `192.168.50.0/24`; its secret
is shown once and is pasted only at the helper's secure prompt. Use
`http://192.168.50.201:8000` when that private host address is confirmed, or
localhost for same-host use, at a 30-second interval. Confirm the heartbeat and
posture in Endpoint Agents. If Docker cannot see neighbors, manually enter a
device already shown by an authorized router UI. RavenTech never logs in to,
scrapes, configures, or blocks through the router. TCP checks remain limited to
authorized monitored private assets and configured ports, without credentials,
brute force, or exploit payloads.

## Native host metrics and endpoint cadence

In the installed or portable desktop, the Server tab chooses metrics in this
order: native desktop host, fresh `ServerHost` endpoint agent, fresh backend-host
agent, Docker container fallback, unavailable. Native collection uses read-only
Windows APIs for CPU, memory, system-drive utilization, uptime, OS/build, hostname,
and timestamp. It does not enumerate documents, command lines, browser history,
credentials, tokens, or environment contents.

Run the server helper manually from the repository root:

```powershell
.\scripts\local\local_monitor_agent.ps1 -Mode ServerHost -BackendUrl http://localhost:8000 -IntervalSeconds 30
```

On another approved `192.168.50.0/24` Windows endpoint, use the confirmed server
address and `LanEndpoint` mode. The UI supplies only an `<ENROLLMENT_TOKEN>`
placeholder and the secret is entered at the secure prompt. Recommended cadences
are 30 seconds for server/endpoint samples and UI refresh, 300 seconds for LAN
discovery/posture recompute, and 600 seconds for bounded service checks. Stop an
agent with Ctrl+C; no service, scheduled task, persistence, or autostart is created.
If LAN endpoints need port 8000, create a manual Windows firewall rule limited to
remote subnet `192.168.50.0/24`, never Public profile or unrestricted sources.

## Real LAN operator acceptance

Open **Monitoring Center** and verify the runtime card shows CIDR
`192.168.50.0/24`, gateway hint `192.168.50.1`, the most recent discovery and
service-check times, asset and agent totals, the chosen host-metric source, and
posture/recommendation status. Create a short-lived enrollment token, copy it
once, then enter it only at a `LanEndpoint` agent's secure prompt. `ServerHost`
instead prompts for a current local admin access token. Run `ServerHost` on the
main machine and `LanEndpoint` on approved LAN PCs, verify a fresh heartbeat,
then confirm posture refresh. Import router-observed devices manually if Docker
neighbor visibility is incomplete. All service results are advisory TCP-connect
observations; authorize the asset and enable both LAN/service flags first.

## Controlled LAN activation

In **Monitoring → Activation**, review the displayed fixed profile and select
**Apply fixed LAN profile**. The desktop requires confirmation, validates the
bound repository and exact script bytes, and creates `.env.backup-<UTC timestamp>`
before changing `.env`. Only the documented monitoring keys are replaced or
appended; passwords, tokens, connection strings, and unknown settings are neither
read into the UI nor changed. Browser mode copies the profile instead of writing.

After a successful apply, select **Restart and verify** and confirm separately.
The existing restart launcher recreates changed Compose services, applies existing
migrations safely, then checks `/health`, `/health/ready`, and `/api/v1/release`.
Confirm RC6 and that LAN/service flags are enabled. Automatic discovery and service
checks on startup remain false. Run `ServerHost` manually with localhost and a
current local admin access token entered only at its secure prompt. Run
`LanEndpoint` manually with a short-lived enrollment token and the confirmed private
backend URL; restrict Windows Firewall TCP/8000 to `192.168.50.0/24`.

### Automatic LAN asset registration

`ServerHost` and `LanEndpoint` now register their own authorized private endpoint
in LAN inventory when the backend accepts their authenticated telemetry. No manual
asset record is required first. Existing operator names and authorization decisions
are preserved. The manually run `ServerHost` also reads a maximum of 256 entries
from the Windows neighbor table, limited to its local private `/24`, and sends only
IP, normalized MAC, interface, state, timestamp, and source. The backend applies the
configured `LAN_ALLOWED_CIDRS` boundary again, rejects public/out-of-range entries,
deduplicates by IP/MAC, and marks newly observed neighbors for review. The configured
`192.168.50.1` gateway is labeled as a likely gateway; RavenTech never connects to,
authenticates to, scrapes, or configures it.
