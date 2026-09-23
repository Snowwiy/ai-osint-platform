# Desktop native background runtime (Phases 5BJ–5BL)

Phase 5BK adds Windows and Linux standalone backend/worker builds; Phase 5BL supervises those packaged components; Phase 5BM adds Tauri-managed PostgreSQL 16 for fresh native desktop installs. See [NATIVE_RUNTIME_SUPERVISOR.md](NATIVE_RUNTIME_SUPERVISOR.md), [NATIVE_BACKEND_PACKAGING.md](NATIVE_BACKEND_PACKAGING.md), and [MANAGED_POSTGRESQL_RUNTIME.md](MANAGED_POSTGRESQL_RUNTIME.md).

Tauri starts the fixed native FastAPI backend and worker in release desktop mode. For source development, set `RUNTIME_PROFILE=desktop` and run `python -m app.worker` with the same PostgreSQL connection. The profile selects PostgreSQL-backed jobs and authentication even if an older `.env` says `BACKGROUND_JOB_BACKEND=celery`. PostgreSQL, Alembic migrations, and report storage remain required. Redis and Celery are optional compatibility services. PostgreSQL is not packaged and remains externally operated, commonly through Docker.

`RUNTIME_PROFILE=docker` is the default and retains the existing Celery/Redis behavior. `RUNTIME_PROFILE=development` honors `BACKGROUND_JOB_BACKEND=celery|native`. No existing Docker installation is silently switched.

## Dependency inventory and migration decision

| Dependency or work | Class | Desktop decision |
| --- | --- | --- |
| Celery broker/result settings and empty `workers/tasks.py` module | B, E, F | Retained for Docker compatibility; no registered application Celery tasks exist. |
| Refresh-token JTI and failed-login throttling | A, D | PostgreSQL `native_auth_state` in desktop profile; token bodies are never stored. |
| SlowAPI Redis storage | C | No decorated routes currently use it. Desktop points this optional limiter at local memory; required login throttling remains PostgreSQL-backed. |
| LAN posture and recommendations after telemetry | A, E | Allowlisted native jobs with dedupe and cooldown. |
| Monitoring summary refresh | A, E | Allowlisted native job; native worker schedules one bounded cycle per configured interval. |
| Reports and exports (PDF, DOCX, HTML, Markdown) | A | Existing synchronous, permission-checked request flow retained. The API response/download contract and report transaction boundaries remain intact. |
| Recon and enrichment | A | Existing synchronous, scoped request flow retained to preserve authorization, rate limits, partial results, and provider-error semantics. No new provider or scan type. |
| Evidence, intelligence, correlation, timeline, investigation updates | A | Existing synchronous database transactions retained to preserve provenance and immediate user-visible results. |
| Notifications, alerts, data quality, archive/cleanup | A | Existing PostgreSQL request/maintenance flows retained; no Celery dependency or independent recurring requirement. Operator-controlled maintenance remains explicit. |
| Future Knowledge/Obsidian import and indexing | F | No handler registered. A future phase should use this job abstraction with fixed schemas for `knowledge.import`, `knowledge.index`, and `knowledge.reindex`. |

## Scheduler and resource limits

The native worker holds a PostgreSQL advisory transaction lock while deciding whether a monitoring summary cycle is due. It schedules at most one job after a missed interval, uses a fixed dedupe key and cooldown, and never replays a backlog of missed cycles. Existing LAN discovery, service checks, and maintenance windows retain their own explicit authorization and policy; this scheduler does not start network checks. Queue admission is serialized and capped by `NATIVE_WORKER_MAX_QUEUE_DEPTH` (default 1000). Claims use `FOR UPDATE SKIP LOCKED` and a per-type advisory lock to enforce `NATIVE_WORKER_MAX_RUNNING_PER_TYPE` (default 2) across workers. Priorities are fixed: low 20, normal 50, high 70, critical 90. No public enqueue endpoint accepts a numeric priority.

The worker heartbeats, stops gracefully, recovers stale leases, retries bounded transient failures, and checks cancellation before committing handler changes. Handlers have fixed timeouts: 30 seconds for summary refresh and 90 seconds for posture/recommendation recomputation. Timeout or temporary failure produces a safe code and bounded retry; malformed payloads fail without retry. Timeout cancels the async handler transaction, never an OS process. Active dedupe, a completion cooldown, and bounded admission limit UI polling pressure. Existing posture updates replace current state; the summary job is read-only. New side-effecting handlers must define idempotency before registration.

Operations Center shows worker health, queue depth and age, counts, safe errors, and filters for type, status, priority, worker, investigation, asset, and requester. Admin Retry and Cancel remain state-checked. `/health` and `/health/ready` report the profile, engine, required and optional dependencies. Redis/Celery absence is informational in desktop profile. The desktop status panel labels both as optional or compatibility only.

## Security and compatibility

Only fixed application handlers execute. Payloads have exact schemas and contain no passwords, JWTs, API keys, enrollment tokens, executable paths, commands, or raw banners. The worker does not use dynamic imports, `eval`, `exec`, subprocesses, or shell execution. Cancellation is cooperative. Remote commands, public scanning, brute force, credential testing, exploitation, and autostart are outside this runtime.

Redis, Celery, and Docker Compose remain present and supported. Docker mode still requires its configured dependencies. PostgreSQL remains required in every profile: fresh native desktop installs use the managed runtime, while configured external databases remain supported. Remaining phases are 5BN Docker-optional desktop finalization, 5BO Windows clean-machine acceptance, 5BP Linux clean-machine acceptance, and 5BQ Knowledge/Obsidian ingestion. Those later phases are not implemented here.

## Phase 5BL — Tauri native runtime supervision

Release desktop runs use the cross-platform Tauri supervisor for the fixed PyInstaller backend and worker. The supervisor verifies the RC6 release and native runtime profile, waits for PostgreSQL/migration/storage prerequisites before starting the worker, and reports owned versus external components. It uses bounded restart attempts and cooperative shutdown markers, and only terminates retained child processes that this desktop launched. A per-user Windows mutex or Linux file lock prevents duplicate desktop sessions from independently starting children. Backend port conflicts and external components are observation-only.

Windows portable/installer packages include Windows x86_64 backend, worker, and managed PostgreSQL resources; Linux x86_64 packaging includes equivalent runtime resources. Existing external PostgreSQL remains supported. Redis/Celery are not required for native desktop mode, while Docker and development profiles remain supported. No OS autostart, systemd installation, updater, or automatic downloads are added. Linux WSL evidence is not clean-machine Linux acceptance.
