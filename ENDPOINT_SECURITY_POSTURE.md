# Endpoint Security Posture

Endpoint Security Posture is a deterministic, local, advisory assessment of
stored authorized LAN observations and optional endpoint-agent telemetry. It
does not scan the public internet, validate exploitation, authenticate to a
service, execute a remote command, or remediate an endpoint automatically.

## Visibility with and without an agent

Without an agent, posture uses only stored LAN presence, IP, MAC and hostname
when available, online/offline state, authorization, observed TCP ports, bounded
service guesses, criticality, and unmanaged/unknown-asset status.

With an enrolled agent, posture can additionally use CPU, memory, disk usage and
free space, uptime, OS caption/version/build, agent freshness, normalized
firewall and antivirus/Defender state, recent patch/hotfix summary, pending
reboot state, and local listening TCP port numbers. Collection is best effort;
an unavailable field remains `unknown` or `unavailable` and is never invented.

The helper collects no files, private documents, passwords, credentials,
browser history, keystrokes, or file contents. Linux OS identification reads
only `/etc/os-release`; listening ports are derived from local kernel socket
tables. No privilege escalation, persistence, autostart, shell channel, or
remote command channel is installed.

## Posture scoring

Each stored assessment has a bounded 0–100 score and one status:

- `healthy`
- `needs_review`
- `at_risk`
- `critical`
- `unknown`

Scores are deterministic deductions for current recommendations. An authorized
asset with no agent or service evidence can remain `unknown`; an unauthorized
asset is never scored as healthy. The score is prioritization guidance, not a
claim of compromise or a substitute for endpoint-management evidence.

## Patch, firewall, and antivirus awareness

Windows collection uses read-only local operating-system interfaces when
available. Firewall profile and Defender state are normalized to enabled,
disabled, unknown, or unavailable. Recent installed hotfix dates provide patch
awareness; they do not prove that every applicable security update is installed.

Linux collection never refreshes package repositories or installs packages.
When a local package-update timestamp is safely available, it provides a coarse
current/stale signal; otherwise patch state remains unknown. Firewall and
antivirus state remain unknown/unavailable unless a non-privileged, reliable
local signal exists. Operators should confirm results in approved management
tools.

## Deterministic recommendations

Recommendations cover unauthorized assets, critical assets without agents,
stale agents, disabled or unknown protection, stale/unknown patch posture,
pending reboot, high resource usage, risky stored service observations,
non-standard SSH, HTTP without observed HTTPS, baseline ownership/due-date gaps,
and expected-service differences.

Every recommendation contains an affected asset, reason, severity, manual
action, checklist, isolation guidance, evidence source, confidence, and
lifecycle status. Recommendations are deduplicated per asset and condition.
Operators may acknowledge or resolve them; reassessment reopens a condition if
the evidence still supports it.

## Manual block and isolation guidance

For an unauthorized or sufficiently risky asset, RavenTech can recommend:

1. Confirm IP, hostname, and MAC with the asset owner.
2. Compare the observation with the approved asset register and change record.
3. If unapproved, use an authorized router rule or quarantine VLAN manually.
4. Record the decision and monitor for recurrence.

RavenTech does not connect to a router, scrape an administration panel, request
router credentials, change firewall/router configuration, block an address, or
isolate a VLAN automatically.

## API and RBAC

Endpoint posture contains LAN identifiers and is administrator-restricted:

```text
GET   /api/v1/monitoring/posture/overview
GET   /api/v1/monitoring/lan/assets/{asset_id}/posture
POST  /api/v1/monitoring/lan/assets/{asset_id}/posture/assess
GET   /api/v1/monitoring/recommendations
PATCH /api/v1/monitoring/recommendations/{id}
POST  /api/v1/monitoring/recommendations/{id}/acknowledge
POST  /api/v1/monitoring/recommendations/{id}/resolve
```

Assessment is explicit and evaluates stored data only. Recommendation filters
support status, severity, asset, bounded limit, and offset. Audit and monitoring
notifications store sanitized identifiers and state only.

## Alerts and reports

High and critical active recommendations enter the existing Monitoring Center
alert path. Existing policy enablement, cooldowns, per-rule caps, dedupe,
suppression, maintenance windows, and triage apply.

Reports include posture only when an investigation target exactly matches an
assessed LAN asset IP or hostname. They summarize posture counts, top advisory
risks, unauthorized assets, and manual actions, with a no-exploit-validation
disclaimer. Unrelated LAN assets are not added to an investigation report.

## Deployment boundary

The Security Posture UI and its manual recommendation terminology support
English and Spanish with English fallback. Stored evidence and stable audit
identifiers are not rewritten when display language changes.

This feature is validated only in the local web application. It adds no desktop
packaging, Electron, Tauri, installer, hosting, deployment, DNS, Supabase
migration, public scanning, router automation, or offensive capability.

## Automatic summary refresh

The authenticated desktop startup summary refreshes stored posture,
recommendation, baseline, coverage, and alert counts. This read-only refresh does
not contact endpoints, require agent telemetry, authenticate to a device, execute
commands, or initiate LAN discovery/service checks. Missing agent telemetry is
an informational coverage limitation rather than a platform failure.

## Bootstrap verification

After an approved observation or endpoint heartbeat exists, assess posture and
review recommendations. Expected advisory indicators include unauthorized or
unknown-device review, critical assets missing agents, stale agents, risky
RDP/SMB/Redis/PostgreSQL exposure, non-standard SSH, missing expected services,
and manual block/isolate guidance. These are risk indicators, not claims of
exploitation or compromise; every action requires manual owner review.

## Telemetry-driven updates

Each accepted `LanEndpoint` heartbeat updates asset freshness, agent coverage,
posture evidence, stale-agent state, critical gaps, and advisory recommendations
through the existing defensive pipeline. The primary server may use native desktop
metrics or manual `ServerHost` mode; Docker-only data remains explicitly scoped to
the container. Cadence defaults are 30 seconds for agents and 300 seconds for
posture recomputation. Missing optional telemetry is informational, not a platform
failure.
