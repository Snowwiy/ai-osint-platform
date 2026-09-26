# AI Model Integration

RavenTech AI is an optional evidence-aware analysis feature for authorized
administrators and analysts. Its fixed Tool Gateway is read-only and does not
participate in RavenTech backend,
monitoring, investigation, or native-worker readiness. If no provider is
available, core RavenTech workflows continue normally.

## Connections and discovery

RavenTech can call installed local runtimes directly: Ollama at
`127.0.0.1:11434`, LM Studio at `127.0.0.1:1234`, and llama.cpp, vLLM, or another
OpenAI-compatible local server at an explicitly configured loopback endpoint.
OpenCode remains an optional orchestration/provider layer for remote providers.
RavenTech does not request provider credentials or copy them into its database.
These runtimes are not installed, started, reconfigured, or exposed to LAN by
RavenTech.

Discovery checks only known Ollama/LM Studio loopback defaults and explicitly
configured endpoints; it does not scan ports. Endpoint validation rejects
non-loopback IPs and DNS names, blocks credentials/query strings and redirects,
and pins `localhost` to its resolved loopback address before requests. An
explicit network-addressed endpoint is labeled as network and blocked from
local inference. Keep runtime authentication and credential configuration in
the runtime that owns it; RavenTech does not scrape credentials.

Direct local inference uses the runtime's installed model inventory and its
native Ollama or OpenAI-compatible API. Model weights are never downloaded by
discovery, test, or benchmark actions. Setup requires the operator to install
and start a supported runtime and model separately. All OpenCode requests remain
scoped to an app-owned neutral workspace under RavenTech's native runtime
directory, never the current working directory or RavenTech source tree.

OpenCode documents its server as a programmatic HTTP interface, with a loopback
default and endpoints for health, providers, sessions, messages, asynchronous
prompts, cancellation, and server events. RavenTech uses those supported APIs
for chat; it does not use the shell endpoint, command API, TUI control API,
filesystem endpoints, or provider-auth endpoints. See the
[OpenCode server documentation](https://dev.opencode.ai/docs/server/).

## Model selection and cost policy

The catalog is dynamic; RavenTech does not hardcode a required model. It displays
provider, model, availability, capabilities when reported, execution location,
and the current price classification. `Free · provider reported` means the
provider currently reports zero input and output cost. It is not a promise that
pricing will remain free.

Execution modes are:

- **Local first** (new-user default): prefer an explicitly selected or preferred
  installed local model, then a compatible installed local model. A remote
  fallback is eligible only when the provider currently reports zero cost.
- **Free only**: local models or remote models currently reported free, retained
  from the existing Phase 6A policy.
- **Local only**: detected local models; remote choices are rejected by the API.
- **Any configured**: any available configured model, including paid remote
  models, only after the operator explicitly chooses this mode.
- **Offline AI**: a separate per-user switch that takes precedence over the
  execution mode. It skips remote provider discovery and blocks remote model
  inference. If a local model is missing or fails, RavenTech reports that local
  AI is unavailable and keeps deterministic RavenTech workflows available.

Routing honors an explicitly selected model first, then a preferred installed
local model that passes conservative hardware fit, then another compatible
installed local model. A provider-reported free remote model is considered only
when the selected privacy mode permits remote inference. Paid remote models are
never selected silently. If the selected model disappears or its inventory no
longer meets the mode, RavenTech preserves the session and asks the operator to
choose an available model. A model change applies to a new chat.

The separate routing selector offers Manual, Recommended, and Automatic local
only. Operators can assign installed local models to fast triage, general
analysis, deep analysis, Knowledge/RAG, tool calling, structured reports,
bilingual work, and offline tasks. Automatic local routing uses hardware fit
and matching-hardware benchmark scores when available; it never searches remote
providers. Each message records its requested model, actual model, and a
non-sensitive routing reason. If no eligible local model is available, the
request fails closed with a clear message; normal deterministic RavenTech
analysis remains available.

## Hardware and model fit

The AI Models page reads local OS, CPU, memory, disk, and available GPU metadata
through platform APIs and Linux `/proc`/`sysfs` where available. It does not
collect hardware serials. GPU entries support multiple devices; VRAM, driver,
and compute backend remain unknown when the platform cannot report them safely.
Hardware details stay local and are not added to prompts or sent to remote
providers.

Model inventory fields such as size, parameter count, quantization, context,
and capabilities are shown only when the runtime reports them. Capability
states distinguish supported, unsupported, and unknown. Compatibility uses
reported model size and currently available RAM/VRAM with a conservative weight
overhead estimate; it is approximate and may not account for model-specific
placement, quantization behavior, or context/KV-cache requirements. Unknown
metadata is not inferred from model names or treated as a fit guarantee.

## Local tests and benchmarks

An administrator can run a minimal `READY` model test against an already
installed local model. It adds no RavenTech operational context. Synthetic
streaming and fixed JSON checks run only after the operator starts the local
model test; tool support remains unknown until a safe, supported method can be
verified, and the test never executes a tool. Synthetic
benchmarks are separately started and limited to one run per host, ten fixed
synthetic cases, five seconds per case, and a sixty-second overall limit. They
measure latency, time to first token, an approximate whitespace token rate,
memory delta, and deterministic output scores for structured output, evidence,
citations, tool formatting, action safety, language, Knowledge, and injection
handling. The tool-format case never executes a tool.

History retains model/runtime identifiers, hardware snapshot hash, score and
timing metrics, and safe warnings. It does not retain benchmark prompts or model
outputs. Throughput is an estimate when the runtime does not provide token
counts. A missing local runtime or model is shown as unavailable; no model is
downloaded to complete a benchmark.

## Data destination and Knowledge context

Before a request, the console labels the selected model **Local** or **Remote**.
For a remote model, the selected provider receives the submitted message and
only the context explicitly selected by the operator. Local retrieval occurs in
RavenTech. The operator can preview Knowledge excerpts using `Verified only`,
`Trusted+`, or `All allowed sources`; the default is `Verified only`. The maximum
is five excerpts, with bounded excerpts and stable Knowledge citation IDs. A
vault, investigation database, host inventory, or full RavenTech log is never
sent automatically.

Selected excerpts are serialized as untrusted data so embedded instructions
cannot override the analysis policy. Responses show provenance and validate
model-generated Knowledge references against IDs actually supplied to that
request. Unknown citations are marked unverified; model statements are never
treated as verified RavenTech telemetry.

RavenTech applies deterministic redaction for common authorization headers,
JWTs, API keys, password/token fields, credential-bearing database URLs, and
private-key blocks before persistence or context transfer. This is defense in
depth, not a complete data-loss-prevention guarantee. Review selected context
and the destination before sending. Do not put secrets into chat.

## Sessions, access, and retention

The backend requires the AI feature flag and an authenticated admin or analyst
role. Each model preference and session belongs to the signed-in user. The
database stores the provider/model IDs, execution type, context policy, and
sanitized user-visible user/assistant messages. It does not store provider keys,
OpenCode credentials, hidden reasoning, full raw request payloads, or raw
provider configuration. Session creation is bounded to 100 sessions per user by
default (configurable with `AI_SESSION_MAX_SESSIONS`, clamped to 1–500). Message
history is bounded by `AI_SESSION_MAX_MESSAGES` (20–200 effective range).
Sessions can be renamed, archived, or deleted; an active response must be
cancelled or completed before archive/delete.

Streaming cancellation is cooperative. The UI progressively shows visible text;
RavenTech saves only the sanitized completed response and visible transcript.
Audit records identify actions and safe metadata/digests, not prompt bodies,
provider credentials, or full responses. Operations Center provider/model
diagnostics are administrator-only and do not return secrets.

## Read-only tool boundary

The OpenCode request uses a RavenTech system policy and explicitly denies all
OpenCode-native tools, including shell/bash, read/write/edit/apply-patch,
external directories, task/process execution, web search/fetch, skills, and MCP.
When a tool-capable model requests current RavenTech evidence, it can use only
the fixed read-only Tool Gateway registry. The gateway applies RBAC, strict
schemas, scoped access, rate limits, timeouts, result limits, sanitization,
provenance, and metadata-only audit. Read-only tool results are sent to a remote
model only after turn-specific operator consent. See
[AI_TOOL_GATEWAY.md](AI_TOOL_GATEWAY.md) for the registry and evidence contract.

The neutral app-owned workspace prevents normal RavenTech AI sessions from
inheriting the operator's current project or repository. In addition to fixed
read-only evidence tools, a separate proposal-only tool may be offered when the
current user explicitly asks for one specific registered action. It can create
one pending proposal, but cannot approve or execute it. Local service/process
proposals must match the supplied current desktop inventory; RavenTech rechecks
the target before approval and execution. The authenticated operator reviews
and approves any action in the Action Gateway. Arbitrary file/configuration
changes, firewall changes, scans, and remote commands remain unavailable. See
[ACTION_GATEWAY.md](../ACTION_GATEWAY.md).

The console can generate and copy a defensive OpenCode prompt and a correctly
quoted `opencode run --model ...` command. Copying does not launch a terminal or
run the command. Handoff text is generated from bounded, sanitized facts and
stable citation IDs and is audited by digest only.

## Setup and diagnosis

1. Configure the provider using OpenCode's own supported setup and credential
   ownership, or start an optional local model service separately.
2. Keep OpenCode bound to loopback. RavenTech does not widen its bind address or
   CORS policy.
3. In AI Models, refresh local runtimes and review runtime status, installed
   models, reported metadata, hardware fit, and any network endpoint warning.
4. In the AI Console, choose a model and privacy mode. Enable Offline AI when
   remote provider discovery and inference must be blocked.
5. Review the data destination and select only the context needed for the
   question. Run local model tests or synthetic benchmarks only when needed.

If a local runtime is stopped, RavenTech reports its safe status/reason and the
core remains usable. An unavailable local model never falls back to a remote
provider while Offline AI is enabled. In Local only mode, remote model execution
is rejected. Tests use provider-independent fixtures when no local runtime or
model is installed; live inference is not run automatically.
