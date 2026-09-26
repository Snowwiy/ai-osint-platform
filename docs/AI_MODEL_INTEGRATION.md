# AI Model Integration

RavenTech AI is an optional evidence-aware analysis feature for authorized
administrators and analysts. Its fixed Tool Gateway is read-only and does not
participate in RavenTech backend,
monitoring, investigation, or native-worker readiness. If no provider is
available, core RavenTech workflows continue normally.

## Connections and discovery

RavenTech uses the loopback OpenCode server on `127.0.0.1` for configured
OpenCode providers and discovers models from the server's current provider
inventory. OpenCode Zen is available only when already configured in OpenCode.
RavenTech does not request a Zen or other provider key. OpenCode's executable
version can be detected without launching its interactive TUI; RavenTech does
not install, update, or configure OpenCode.

The adapter can also discover Ollama at `127.0.0.1:11434` and LM Studio at
`127.0.0.1:1234`. Other local providers such as vLLM may be used through an
OpenCode provider configuration when the current inventory reports them. These
optional runtimes are not installed or started by RavenTech. All OpenCode
requests are scoped to an app-owned neutral workspace under RavenTech's native
runtime directory, never the current working directory or RavenTech source tree.

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

- **Free only** (default): local models or remote models currently reported free.
- **Local only**: detected local models; remote choices are rejected by the API.
- **Any configured**: any available configured model, including paid remote
  models, only after the operator explicitly chooses this mode.

There is no silent fallback from a local/free selection to a paid model. If the
selected model disappears or its current inventory no longer meets the selected
mode, RavenTech preserves the session and asks the operator to choose an
available model. A model change applies to a new chat; RavenTech does not assume
provider session state is portable.

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
3. In RavenTech AI, refresh the model catalog and verify provider, availability,
   Local/Remote, and current cost status.
4. Choose the execution mode, review the data destination, and select only the
   context needed for the question.

If OpenCode is installed but its server is stopped, AI integration is reported
unavailable while RavenTech core remains healthy. If OpenCode is absent, local
Ollama/LM Studio discovery and copy-only prompt handoff remain available. Live
model inference requires a configured provider/model; tests use synthetic
provider fixtures and never depend on current model pricing.
