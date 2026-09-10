# Local Monitoring Center

## Phase 5AA policy tuning

The Monitoring Center exposes administrator-managed policies for CPU, memory, disk, stale agents, offline or unauthorized assets, risky observed services, weak coverage, high/critical findings, and overdue remediation. Safe defaults start resource alerts at 90%, apply multi-hour cooldowns and dedupe keys, and cap daily notifications. Analysts may read policy state; only administrators may change it.

Acknowledging a notification does not stop its rule. Suppression is explicit, reversible, and audited; it never deletes the alert or stops collection. Critical alerts remain visible unless an administrator explicitly suppresses them or configures a matching maintenance window. Active maintenance retains matching alerts with `suppressed_due_to_maintenance` while polling and telemetry continue.

The Monitoring Center provides local operational visibility for RavenTech
OSINT `5.0.0-rc4`. It polls authenticated backend summaries and does not scan
targets, contact external services, expose Docker control, or perform automated
remediation.

RC3 is the completed validated local web mode. Optional host telemetry and host
LAN visibility can improve coverage but are not required platform dependencies;
their absence must not change a healthy platform into a degraded one. Desktop
packaging, hosting, deployment, DNS, and Supabase migration remain deferred.

## Start and open

```powershell
docker compose up -d
docker compose exec backend alembic upgrade head
./scripts/local/check_local_health.ps1

cd frontend
npm run dev
```

Sign in as an active admin or analyst and open **Monitoring**. The default poll
interval is 30 seconds; the UI offers bounded intervals from 15 to 300 seconds.
Polling occurs only while the page is open.

## What is monitored

- Backend, PostgreSQL, Redis, Celery worker, migration alignment, and report
  storage use the existing local readiness checks.
- Docker is reported as unavailable unless status is supplied by an authorized
  operator. The backend does not mount the Docker socket.
- CPU, memory, disk, process count, and uptime use best-effort backend-container
  measurements by default.
- Asset Watch summarizes only investigations visible to the signed-in user. It
  includes targets, unresolved high/critical findings, evidence, reports,
  closure, scope, and engagement authorization state.
- A target is considered stale after 30 days when it has no completed/partial
  passive collection job or linked finding.
- Recent backend errors contain sanitized audit metadata only—never request
  bodies, credentials, headers, URLs with secrets, or stack traces.

## API and authorization

All UI/read routes require user authentication. Investigation monitoring follows
normal membership rules; server-agent ingestion requires an administrator.
LAN inventory routes are admin-only, while endpoint-agent routes use the
separately configured local shared-token header described in `LAN_MONITORING.md`.

```text
GET  /api/v1/monitoring/overview
GET  /api/v1/monitoring/services
GET  /api/v1/monitoring/system
GET  /api/v1/monitoring/assets
GET  /api/v1/monitoring/alerts
POST /api/v1/monitoring/agent/ingest
```

The overview is designed for the UI and returns release metadata, service
status, system telemetry, RBAC-scoped assets, alerts, and sanitized recent
errors. It does not return environment variables, database/Redis URLs, API
keys, access tokens, authorization headers, passwords, or password hashes.

## Optional Windows host agent

Phase 5AI adds best-effort endpoint posture fields to the manually run agent:
OS build, disk free space, normalized firewall and Defender/antivirus state,
recent hotfix awareness, pending reboot, and local listening TCP port numbers.
Unavailable fields remain unknown. No raw command output, file contents,
credentials, browser history, keystrokes, persistence, or remote-command channel
is collected or installed. See `ENDPOINT_SECURITY_POSTURE.md`.

Container metrics do not represent the full Windows host. An administrator may
run the optional local agent from the repository root:

```powershell
./scripts/local/local_monitor_agent.ps1 -Once
./scripts/local/local_monitor_agent.ps1 -IntervalSeconds 30
```

In server mode the script accepts localhost or private RFC1918 backend URLs and
prompts securely for a current admin bearer token. The token remains in process memory, is sent only in
the Authorization header, and is not placed in telemetry, command arguments,
files, or logs. The payload is limited to agent ID, platform, timestamp, CPU,
memory, disk, process count, and uptime. Stop continuous collection with
`Ctrl+C`.

The backend keeps only the latest accepted agent sample in memory. Restarting
the backend clears it, and samples older than ten minutes fall back to container
metrics. This is intentional local telemetry, not durable monitoring.

## Alerts and deduplication

Alerts are derived from current local state for service degradation, migration
drift, high system utilization, unresolved high/critical findings, stale
targets, authorization risk, repeated report failures, and repeated AI fallback
events. Alerts do not run active checks or modify investigations.

Opening the overview or alerts endpoint may create an internal
`monitoring_alert` Activity Inbox record for the current user. A stable daily
deduplication key prevents polling from creating duplicates for the same alert.
No email, SMS, browser push, webhook, or third-party notification is sent.

## Troubleshooting

- Run `./scripts/local/check_local_health.ps1` and follow
  `LOCAL_HEALTH_REPAIR.md` when a required service is degraded.
- Run `docker compose exec backend alembic upgrade head` for an unapplied
  migration, then repeat `docker compose exec backend alembic check`.
- Start the optional agent only when host-level metrics are useful. Monitoring
  remains functional without it.
- Treat unavailable Docker status as informational; no Docker socket or remote
  daemon access is required.

The validated mode remains local Docker Compose. Hosting, deployment, DNS, and
Supabase migration are deferred.

## Phase 5AB status and alert recovery

Platform health now reflects required dependency checks from `/health` and
`/health/ready`. Missing optional host-agent telemetry leaves the platform
healthy and labels the displayed system values as backend container metrics.
When the local agent is absent, unavailable host uptime is informational.

Overview-managed notifications are dismissed when their condition recovers;
active alerts continue to use policy dedupe keys, maximum counts, cooldowns,
explicit suppression, and maintenance-window suppression. Provider warnings
identify the provider and a sanitized timeout, HTTP, or parse failure code.
Valid recon entities remain available as the last successful result when a
later retry has warnings.

Authorized LAN service observations are shown separately from required service
health. They are risk indicators, not proof of exploitation or confirmed
vulnerabilities. See [LAN_MONITORING.md](LAN_MONITORING.md).

## Phase 5AC change timeline

The **Change Timeline** records state transitions for LAN assets, ports,
services, endpoint agents, policy-threshold telemetry, and vulnerability
baseline indicators. Entries retain bounded old/new values, source, severity,
time, acknowledgement state, and sanitized metadata. Filters cover asset,
event type, severity, acknowledgement, and date range.

Acknowledgement is an audited analyst workflow action; it does not delete
history or stop collection. Change-derived alerts continue through monitoring
policy cooldowns, dedupe limits, explicit suppressions, and maintenance windows.

## Optional authorized LAN monitoring

The **LAN Assets** and **Endpoint Agents** tabs are admin-only because they show
internal addresses and host telemetry. LAN monitoring is disabled by default,
uses explicitly configured private ranges, and does not weaken the server
monitoring path. See [LAN_MONITORING.md](LAN_MONITORING.md) for safe enablement,
agent-token handling, Docker limitations, polling, discovery rate limits, and
non-intrusive risk indicators.

## Defensive vulnerability baseline

The **Vulnerability Baseline** tab evaluates already stored LAN observations,
endpoint telemetry, authorization state, and analyst-reviewed high/critical
findings. It supports remediation ownership, due dates, and status transitions
without performing network discovery or exploit validation. See
[VULNERABILITY_BASELINE.md](VULNERABILITY_BASELINE.md).

## Phase 5AD alert triage

The Monitoring Center **Alerts** tab is a user-scoped incident queue backed by
the existing internal monitoring notifications. Operators can filter by
status, severity, or source; self-assign; record safe notes; investigate; mute
or unmute; resolve; or mark an item false positive. These actions preserve the
source notification and dedupe history rather than deleting evidence.

Mute uses the existing alert-suppression lifecycle. Maintenance suppression is
shown separately and collection continues during every suppression. Critical
alerts can be muted only by an administrator. Recovered conditions are retired
automatically. Notes must never contain credentials, tokens, keys, or secrets.

## Phase 5AE endpoint enrollment and coverage

Admins create short-lived enrollment credentials in **Monitoring → Endpoint
Agents**. The full credential is revealed once; only its SHA-256 digest and a
non-sensitive hint are stored. Optional private CIDR and enrollment-count
limits narrow use. Expired, revoked, exhausted, invalid, or out-of-range
credentials are rejected. Rotation revokes the previous credential.

Windows agents run manually with
`./scripts/local/local_monitor_agent.ps1 -Mode LanEndpoint -BackendUrl http://BACKEND_HOST:8000 -IntervalSeconds 30`.
Linux hosts may run
`python scripts/local/local_monitor_agent.py --backend-url http://BACKEND_HOST:8000 --interval-seconds 30`.
Both prompt securely for the token and stop with `Ctrl+C`; neither installs
autostart or collects files, passwords, browser history, or remote commands.

## Phase 5AF local activation

The Monitoring Center **Activation** tab reads the effective local settings and
shows the exact non-secret `.env` lines needed to enable LAN monitoring and TCP
service checks. Review `LAN_ALLOWED_CIDRS` and `LAN_SERVICE_CHECK_PORTS`, save
the local file, then run `docker compose up -d --force-recreate backend worker`
and `docker compose ps`. The UI never writes `.env` or reveals an enrollment
token after its create/rotate response.

When an approved endpoint must reach the backend from Windows, allow inbound
TCP port 8000 only from the configured private CIDR in Windows Defender
Firewall. Never create a public or any-source firewall rule. The command
builder uses a backend URL and interval with an `<ENROLLMENT_TOKEN>` prompt
placeholder; agents remain manual, non-persistent, and telemetry-only.

From an elevated PowerShell prompt, substitute the actual configured private
CIDR and use a scoped rule such as:

```powershell
New-NetFirewallRule -DisplayName "RavenTech local agent" -Direction Inbound -Protocol TCP -LocalPort 8000 -RemoteAddress 192.168.0.0/24 -Action Allow
```

Remove or disable that rule when LAN-agent access is no longer required.

## RC4 localization

Monitoring Center labels, statuses, empty/error states, activation guidance,
and advisory posture terminology are available in English and Spanish. English
is the safe fallback for uncommon provider- or evidence-generated prose.
