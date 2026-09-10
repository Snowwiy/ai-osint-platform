# Authorized LAN Monitoring

## Alert policies and planned work

LAN indicators for stale agents, offline and unauthorized assets, risky passively observed services, and weak coverage are governed by Monitoring Center policies. Cooldowns, dedupe keys, severity overrides, enablement, and per-rule caps reduce repeat noise. Maintenance windows may target asset IDs, service/category keys, or all local monitoring; matching alerts are marked and audited rather than deleted.

These controls add no active scanning. Collection remains limited to the authorized passive/router/static observations and optional endpoint telemetry described below.

LAN monitoring extends the local Monitoring Center with a deliberately bounded
inventory of private, administrator-authorized networks. It is disabled by
default and is not an internet scanner, vulnerability scanner, remote access
tool, or exploitation framework.

## Safe configuration

Set values only in the untracked local `.env` and restart the backend:

```env
LAN_MONITORING_ENABLED=false
LAN_ALLOWED_CIDRS=192.168.0.0/24
LAN_DISCOVERY_INTERVAL_SECONDS=300
LAN_DISCOVERY_PING_ENABLED=false
LAN_SERVICE_CHECK_ENABLED=false
LAN_SERVICE_CHECK_PORTS=22,80,443,3389
LAN_AGENT_TOKEN=
LAN_AGENT_MAX_STALE_MINUTES=10
```

- Monitoring and discovery are off by default.
- Allowed and selected ranges must be private RFC1918 IPv4 space. A discovery
  request is limited to `/24` or smaller and must be contained by an explicitly
  configured allowed range.
- Admin-triggered discovery is rate limited by
  `LAN_DISCOVERY_INTERVAL_SECONDS`, with a minimum of 60 seconds.
- ARP/neighbor observations are read only when visible inside the container.
- ICMP echo checks run only when `LAN_DISCOVERY_PING_ENABLED=true`.
- Bounded TCP connect checks use only configured ports and run only when both
  ping discovery and `LAN_SERVICE_CHECK_ENABLED=true` are enabled. They do not
  send application payloads, authenticate, enumerate versions, or test flaws.
- Static/router observations can be submitted by an authenticated admin; any
  included service observations require the service-check flag.
- Public, loopback, link-local, multicast, IPv6, and out-of-range addresses are
  rejected. Phase 5Y provides no public-address override.

## Docker limitation

Docker Desktop commonly isolates the backend from the Windows host neighbor
table and ICMP facilities. Missing access produces a clean limitation response
and a deduplicated internal alert; it never makes the platform crash and never
requires privileged mode or a Docker socket mount. Use supplied router/static
observations or the endpoint agent when container discovery is unavailable.

## Endpoint agent

Generate a strong random local shared token, place it only in the backend's
untracked `.env` as `LAN_AGENT_TOKEN`, enable LAN monitoring, and restart the
backend. Never commit or paste the token into documentation, command history,
screenshots, logs, or issue reports.

Run the Windows agent interactively:

```powershell
./scripts/local/local_monitor_agent.ps1 -Mode LanEndpoint -Once
./scripts/local/local_monitor_agent.ps1 -Mode LanEndpoint `
  -BackendUrl http://192.168.0.10:8000 -IntervalSeconds 30
```

The script accepts only localhost or private RFC1918 backend addresses, prompts
securely for the shared token, self-registers its private address, and sends
CPU, memory, disk, uptime, OS, and agent version. It does not collect files,
documents, browser history, passwords, keystrokes, credentials, or command
output. It cannot execute remote commands or open a shell. It installs no
service, scheduled task, persistence, or autostart. Stop it with `Ctrl+C`.

Server-only telemetry remains available with the default `-Mode Server`, using
a current admin access token and the existing `/agent/ingest` endpoint.

## API authorization

LAN inventory routes expose internal addresses and are admin-only:

```text
GET   /api/v1/monitoring/lan/assets
GET   /api/v1/monitoring/lan/assets/{asset_id}
POST  /api/v1/monitoring/lan/discover
PATCH /api/v1/monitoring/lan/assets/{asset_id}
GET   /api/v1/monitoring/lan/assets/{asset_id}/telemetry
GET   /api/v1/monitoring/lan/assets/{asset_id}/services
```

The agent routes use the `X-LAN-Agent-Token` header instead of a user session:

```text
POST /api/v1/monitoring/agent/register
POST /api/v1/monitoring/agent/telemetry
```

When the shared token is empty, agent routes are disabled. Responses never echo
the token. Telemetry metadata is bounded and rejects credential-like field
names.

## Status, alerts, and risk indicators

An endpoint agent is connected when its latest sample is within
`LAN_AGENT_MAX_STALE_MINUTES`. Non-agent assets become stale/offline after at
least two discovery intervals, with a ten-minute minimum. Status is an
observation, not proof that a device is secure or unavailable.

The internal Activity Inbox receives deduplicated alerts for new or
unauthorized assets, offline assets, stale agents, high CPU/memory/disk, risky
observed services, discovery limitations, and weak coverage. Port-based and
agent-version results are labeled **risk indicators**, never confirmed
vulnerabilities. No exploit checks, brute force, password testing, payload
testing, stealth scans, CVE validation, remediation, or external notification
delivery occurs.

The optional [defensive vulnerability baseline](VULNERABILITY_BASELINE.md)
uses stored LAN observations and telemetry to create analyst-reviewed
remediation priorities. Running it does not initiate discovery, probe services,
or convert port observations into confirmed vulnerability claims. Admins and
analysts may assign asset criticality and business context; LAN discovery and
raw inventory controls remain administrator-restricted.

The validated runtime remains local Docker Compose. Hosting, deployment, DNS,
and Supabase migration remain deferred.

## Phase 5AB authorized TCP service checks

Manual service checks are disabled until an administrator sets
`LAN_SERVICE_CHECK_ENABLED=true`. They run TCP connect checks only against
authorized, monitoring-enabled assets inside `LAN_ALLOWED_CIDRS`. Public CIDRs
are rejected by default, the configured host/port limits and two-second timeout
bound each run, and the discovery interval supplies the per-asset cooldown.

Configure `LAN_SERVICE_CHECK_PORTS` with only the ports approved for the local
assessment. Each result records open, closed, filtered, or timeout status plus a
bounded service guess and confidence. When enabled, a minimal banner read can
recognize the `SSH-` protocol marker on port 22 or an approved non-standard
port. Raw banners are not stored, and the check never authenticates, tests
credentials, sends commands, brute forces, exploits, or uses stealth behavior.

Docker may not see the host ARP/neighbor table. This is reported as **Host LAN
discovery limited inside Docker**, not as a platform failure. Use the optional
local endpoint agent or sanitized static/router observations when host network
visibility is required. Collection continues independently of alert
suppression and maintenance windows.
