# Local Monitoring Center

The Monitoring Center provides local operational visibility for RavenTech
OSINT `5.0.0-rc2`. It polls authenticated backend summaries and does not scan
targets, contact external services, expose Docker control, or perform automated
remediation.

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

## Optional authorized LAN monitoring

The **LAN Assets** and **Endpoint Agents** tabs are admin-only because they show
internal addresses and host telemetry. LAN monitoring is disabled by default,
uses explicitly configured private ranges, and does not weaken the server
monitoring path. See [LAN_MONITORING.md](LAN_MONITORING.md) for safe enablement,
agent-token handling, Docker limitations, polling, discovery rate limits, and
non-intrusive risk indicators.
