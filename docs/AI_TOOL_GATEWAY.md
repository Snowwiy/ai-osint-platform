# AI Tool Gateway

RavenTech's optional AI Console can use a fixed set of read-only application
tools to assemble current evidence for analyst review. The gateway is the only
operational interface exposed to the selected model. It calls RavenTech service
functions directly; it does not call RavenTech's own HTTP endpoints or accept
arbitrary endpoint names.

## Tool contract

The registry contains 18 explicit tools covering host summary and metrics,
processes, services, listening ports, authorized LAN inventory, endpoint
coverage, deterministic posture, alerts, timeline, Knowledge search,
investigations, findings, and operational health. Each definition declares its
input schema, result envelope, required role, risk, timeout, output bound, and
audit policy. Analysts and administrators see only their registered tools;
process/service inventory, LAN inventory, endpoint details, posture, and
operations details require an administrator.

The executor validates arguments with strict Pydantic schemas, applies
role/scope checks, per-user/session/tool rate limits, a ten-call per-turn limit,
a 200-row turn budget, a 20-second turn deadline, and per-tool timeouts. Calls
are deduplicated within a turn. Reads reuse existing RavenTech service layers.
Knowledge results are bounded excerpts, not vault exports. LAN tools read stored
authorized inventory only and do not trigger discovery or service checks.

## Authoritative service map

| Evidence category | Existing RavenTech source | Gateway behavior |
| --- | --- | --- |
| Host metrics and listeners | `local_monitoring.get_system_metrics` | Reads the current bounded host snapshot; no new collector is started. |
| Processes and services | Tauri `get_local_host_inventory` payload | Accepts only the fixed inventory schema, admin-only, and labels it client-reported and unattested. Missing inventory yields no inferred rows. |
| LAN and asset detail | `lan_monitoring.list_lan_assets` and `get_lan_asset`; stored `LanAssetTelemetry` and `LanServiceObservation` records | Reads stored authorized inventory; never starts discovery or service checks. |
| Endpoint coverage | Stored LAN asset and endpoint telemetry models | Summarizes existing heartbeats and posture; exposes no enrollment token or agent command. |
| Security posture | `endpoint_posture.get_posture_overview` and `get_asset_posture` | Reads deterministic stored posture; does not trigger recomputation. |
| Alerts | User-scoped `Notification` records | Lists only existing notifications; does not acknowledge, dismiss, or mutate them. |
| Timeline | `timeline.get_investigation_timeline` and stored `MonitoringChangeEvent` records | Reads the authorized investigation or scoped alert/asset timeline. |
| Knowledge | `knowledge_service.search_knowledge` | Uses bounded keyword retrieval and the existing trust/verification filters; returns excerpts and citations only. |
| Investigations and findings | `investigation.list_investigations`, `get_investigation`, `InvestigationEvidence`, and `Finding` | Applies the existing membership checks before returning bounded summaries. |
| Operations health | `health.health_snapshot` | Returns component states with paths and raw diagnostics removed. |
| Vulnerability baseline, reports, executive intelligence | Existing human-facing APIs and services | No AI tool is registered for baseline edits, report generation, or executive-data export. These remain outside the operational AI boundary. |

This keeps the gateway as a narrow adapter over established read services. It
does not duplicate discovery, posture, investigation, or Knowledge logic and it
does not call RavenTech's own public HTTP API from inside the backend.

## Evidence and model boundary

Each result is a bounded envelope containing the tool ID, success state,
generation time, scope, data, warnings, truncation state, and evidence
references. Evidence identifies its source type and stable record ID, timestamp,
freshness, confidence, and scope where available. AI messages retain only
bounded tool activity summaries and provenance references (source type,
timestamp, freshness, confidence, and safe scope); audit events retain safe
metadata, outcome, duration, and counts, not raw tool payloads. Known evidence
types link only to fixed RavenTech pages.

Tool data, Knowledge excerpts, and user text are untrusted input. The analyst
prompt requires separate labels for RavenTech facts, model interpretation,
hypotheses, and recommendations, and permits citations only from supplied
evidence IDs. Sanitization removes credential-like values, bearer tokens,
credential-bearing URLs, local paths, command-line fields, raw banners, and
secret-bearing keys before model transfer or persistence.

OpenCode's native tools remain denied. A tool-capable model may return exactly
one `<raventech_tool_request>` JSON envelope; RavenTech validates and executes
only the fixed registry, then sends bounded evidence for one final response.
Malformed requests, unknown IDs, extra fields, repeated rounds, excess calls,
timeouts, cancellation, and unauthorized scopes fail safely. This protocol does
not grant shell, SQL, filesystem, arbitrary HTTP, Python, process, service,
firewall, router, endpoint, or remote administration access.

## Remote evidence consent

The selected destination is labeled Local or Remote. A remote provider receives
no operational tool results unless the operator approves evidence sharing for
that turn. The preview identifies the categories that may be sent. Without
approval, the request follows ordinary prepared-context chat and no RavenTech
operational tool is executed for the model. Consent is not saved as a standing
preference. Local providers use the same read-only tools without transmitting
evidence to a remote service.

The desktop process inventory, service inventory, and host summary supplied by
Tauri are marked client-reported and unattested by the backend. They contain no
command lines, environment variables, open-file data, or process credentials.
This source label is preserved in warnings and provenance.

## Workflows and operations

The AI Console provides bounded workflows for server/resource use, services,
ports, LAN, selected assets, posture, alerts, and investigations. A workflow
selects fixed tool bundles; it cannot choose a Python function or endpoint. The
Operations Center reports registry size, read-only/write counts, recent
activity, successful activity, and safe failure categories. Write-tool count is
always zero.

AI availability remains independent of RavenTech health and readiness. Model
inference is not live-validated unless an already-configured local or currently
provider-reported free model is available; synthetic adapter tests exercise the
request and response contracts without model credentials or paid requests.
