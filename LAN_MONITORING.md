# Authorized LAN Monitoring

## RC3 freeze boundary

The `5.0.0-rc6` validated mode is local Docker Compose. LAN monitoring and TCP
service checks remain disabled by default, explicitly authorized, private-range
limited, manual, rate limited, and bounded by configured ports and timeouts.
They are connectivity observations only—not public scanning, authentication,
credential testing, exploitation, or vulnerability validation.

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
  LAN monitoring and `LAN_SERVICE_CHECK_ENABLED=true` are enabled. They do not
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

Endpoint posture adds normalized, best-effort security status to enrolled agent
telemetry. Agentless assets retain LAN presence, authorization, and stored
service visibility only. Patch state is awareness—not proof of full patch
compliance—and firewall/antivirus state must be confirmed manually when unknown.
Isolation guidance never connects to a router or applies a block automatically.

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

## Phase 5AC asset and service history

Authorized observations now retain a service-history row for every configured
TCP result and create change events only on meaningful transitions: discovered
asset, offline/online, hostname or MAC change, new/closed port, changed service
guess, and newly detected non-standard SSH. Endpoint-agent history records
stale/resumed reporting and CPU, memory, or disk policy-threshold crossings.

The asset detail view summarizes telemetry history, service history, and recent
changes. History never stores raw banners, passwords, tokens, credentials, or
commands. It does not expand scope: public scanning, brute force,
authentication, exploitation, and intrusive vulnerability tests remain
prohibited.

## Phase 5AD triage links

LAN risk notifications now enter the preserved alert triage queue. When a
notification identifies an asset, its triage card carries only the asset ID and
sanitized context. Assignment, mute, resolution, and false-positive decisions
do not initiate discovery or service checks and do not delete notification or
LAN history.

## Phase 5AE groups and coverage

Asset groups provide lightweight labels such as Workstations, Servers,
Network Devices, Critical Assets, and Lab Devices. The coverage dashboard shows
installed agents, stale heartbeats, missing agents, unauthorized assets,
critical telemetry gaps, and per-group coverage/risk counts.

Expected-service baselines apply to one asset or group. Expected ports not
observed open and observed open ports outside the allowed set are risk
indicators only. Existing non-standard SSH, database, Redis, SMB, RDP, and
authorization indicators remain based solely on stored observations; creating
a baseline never opens a socket or runs a scan.

## Phase 5AF activation and target checks

Use **Monitoring → Activation** to inspect effective LAN/service-check flags,
private allowlists, configured ports, disabled reasons, local restart commands,
and endpoint enrollment steps. Enabling remains an explicit local `.env` edit;
the application does not mutate configuration.

Authorized domain and URL targets become service-check eligible only when their
hostname exactly matches an existing authorized, monitored private-LAN asset.
Authorized IP targets require the same exact private asset match. No DNS lookup
is added for eligibility and public targets are never checked. Execution is a
manual, administrator-only reuse of the rate-limited TCP-connect engine.

A URL such as `https://host/path` is a recon service target. An observation
such as `443/tcp open` is separate historical evidence about the matched LAN
asset. The target page labels these separately and shows open, closed, timeout,
service guess, confidence, and possible/non-standard SSH state.

## RC4 localization

LAN, agent, service-observation, SSH, and Docker-limitation UI copy is available
in English and Spanish. Localization does not expand authorization or alter the
disabled-by-default, private-range, TCP-connect-only safety controls.

## Desktop monitoring startup controls

The desktop loads monitoring status automatically but does not automatically
discover neighbors or check ports. These non-secret defaults keep active work
explicit:

```dotenv
LAN_AUTO_DISCOVERY_ON_START=false
LAN_AUTO_SERVICE_CHECK_ON_START=false
LAN_AUTO_DISCOVERY_INTERVAL_SECONDS=300
LAN_AUTO_SERVICE_CHECK_INTERVAL_SECONDS=600
```

Enabling an auto-start flag does not bypass `LAN_MONITORING_ENABLED`,
`LAN_SERVICE_CHECK_ENABLED`, authorized private CIDRs, configured port/host
limits, timeouts, monitoring policies, maintenance windows, cooldowns, or
deduplication. Public ranges, authentication, brute force, credential testing,
and remote commands remain prohibited.

## 192.168.50.0/24 bootstrap profile

Use `192.168.50.1/24` as the wizard input. It normalizes to
`192.168.50.0/24`; `192.168.50.1` remains only a gateway hint. The copy-only
profile enables LAN monitoring, bounded ICMP reachability, and separately gated
TCP checks while leaving both auto-start flags false. Ports are
`22,80,443,445,3389,8080,8443,3000,5000,5432,6379,8000,9000`, timeout is two
seconds, and host/port caps remain 256/32.

Manual router observations accept name, private IP, optional MAC, interface,
connection type, authorization, and notes. They populate inventory without
router access and are validated against the configured private CIDR.

## Endpoint telemetry cadence

Authorized LAN endpoints normally report every 30 seconds; 60 seconds is available
for lower-frequency testing. Discovery remains 300 seconds and service checks 600
seconds when explicitly enabled. Missing agents remain observed LAN assets with
"no host telemetry / endpoint agent recommended" guidance and do not degrade the
platform. Limit inbound backend TCP/8000 to `192.168.50.0/24` when remote LAN agents
must report. No public range, router automation, authentication attempt, or remote
command is introduced.

## Real-LAN verification sequence

For private RC6 acceptance, confirm the runtime card, import or discover an
authorized device, mark authorization/monitoring explicitly, attach an optional
agent, and inspect last-seen and service observations. Service checks remain
ineligible until LAN monitoring and TCP checks are both enabled and the asset is
inside `192.168.50.0/24`. Results distinguish open, closed, filtered, and timeout
states; SSH and non-standard SSH are indicators only. Risk labels recommend manual
review and never assert compromise. Docker neighbor gaps should be handled with
manual router/static evidence or an endpoint agent, never router credentials.
