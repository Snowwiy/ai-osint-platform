# Native background jobs (Phases 5BI–5BL)

Phase 5BK packages the fixed PostgreSQL worker as a standalone Windows or Linux component; Phase 5BL makes Tauri start and supervise the packaged worker with its backend in release desktop mode. PostgreSQL remains external. See [NATIVE_RUNTIME_SUPERVISOR.md](NATIVE_RUNTIME_SUPERVISOR.md) and [NATIVE_BACKEND_PACKAGING.md](NATIVE_BACKEND_PACKAGING.md).

RavenTech has a PostgreSQL job engine. In desktop runtime, Tauri starts the fixed native backend and worker, which process allowlisted jobs without Redis or Celery. For source development, set `RUNTIME_PROFILE=desktop` and run `python -m app.worker` from `backend`. Docker installations retain their `celery` default; development may set `BACKGROUND_JOB_BACKEND=native` directly. PostgreSQL and the FastAPI backend remain required; Redis, Celery, and Docker support are retained.

## Current work inventory

| Work | Current path | Native status | Properties |
| --- | --- | --- | --- |
| Endpoint posture and recommendations after LAN telemetry | Synchronous | Migrated with compatibility fallback | Required, retryable, idempotent, bounded |
| Monitoring summary refresh | Request polling | Native handler available | Optional, retryable, idempotent |
| Data quality scan | Synchronous admin request | Retained synchronous | Admin-initiated; no Celery dependency |
| Reports | Synchronous | Retained synchronous | Keep authorization and download contract |
| Recon and enrichment | Synchronous | Retained synchronous | Keep scope, rate limits, partial results |
| Alert/notification maintenance | Synchronous/admin operations | Retained synchronous | Keep explicit operator policy and transaction boundaries |
| Threat intelligence | Synchronous | Retained synchronous | Keep provider limits and immediate results |
| Evidence processing | Synchronous | Retained synchronous | Preserve evidence provenance and transactions |
| Demo jobs | Synchronous | Retained synchronous | Optional; no Celery task |
| Knowledge ingestion | No background implementation | Reserved for future phase only | No handler or executable payload accepted |
| Celery task module | Registered module has no task definitions | Compatibility retained | Redis broker/result settings remain |

## Queue and worker

`background_jobs` persists status, priority, safe payload, progress, timestamps, attempts, retry time, dedupe key, owner, asset/investigation references, worker identity, and cancellation state. `background_job_events` records coarse transitions. A partial unique index protects active dedupe keys. Claiming uses `FOR UPDATE SKIP LOCKED`, ordered by priority and schedule. The worker heartbeats itself and running jobs, recovers stale leases, retries transient failures with bounded exponential backoff, and stops gracefully. Selected handlers are idempotent; a crash after an external side effect can require manual review, so new handlers must define an idempotency strategy.

Only registered job types and exact payload schemas are accepted. Current handlers are `posture.recompute`, `recommendations.recompute`, and `monitoring.refresh`. There is no generic import, Python execution, shell execution, URL fetch, or command field. Payloads exclude credentials, tokens, command lines, and raw banners. Error summaries and audit metadata are sanitized. Cancellation is cooperative: queued jobs stop immediately; running jobs finish their current safe boundary before cancellation takes effect. It never terminates an OS process.

Future Knowledge ingestion should dispatch through this background-job abstraction after a dedicated allowlisted, idempotent handler and payload schema are designed. No Knowledge ingestion handler is implemented in Phase 5BI.

## Configuration and operations

| Setting | Default | Purpose |
| --- | --- | --- |
| `BACKGROUND_JOB_BACKEND` | `celery` | `celery` compatibility or `native` PostgreSQL mode |
| `NATIVE_WORKER_ENABLED` | `true` | Require a native worker heartbeat in native readiness |
| `NATIVE_WORKER_POLL_SECONDS` | `2` | Queue poll interval |
| `NATIVE_WORKER_CONCURRENCY` | `2` | Maximum simultaneous jobs per process |
| `NATIVE_WORKER_HEARTBEAT_SECONDS` | `15` | Lease refresh interval |
| `NATIVE_WORKER_STALE_SECONDS` | `90` | Abandoned lease threshold |
| `NATIVE_WORKER_MAX_RETRIES` | `3` | Automatic retries beyond first attempt |

Apply Alembic revision `0040_phase5bi_native_jobs` before enabling native mode. Run one or more `python -m app.worker` processes with the same PostgreSQL URL as the backend. Operations Center shows queue counts, status, progress, attempts, worker, related asset, safe error, retry time, and admin-only Cancel/Retry actions. Health responses identify the selected backend. In native mode, Redis/Celery are optional for desktop readiness; refresh-token revocation and failed-login state use the `native_auth_state` PostgreSQL table. In Celery mode, existing Redis and synchronous paths remain.

If a worker stops, restart it and inspect its heartbeat and failed jobs in Operations Center. A stale running job is recovered within the configured interval. Repeated failures stop at the attempt limit. Do not put secrets in job payloads or use a job as a command transport.

## Docker decoupling roadmap

5BI: Native PostgreSQL worker (complete). 5BJ: Desktop Redis/Celery independence (complete). 5BK: Separate Windows/Linux backend and worker packaging (complete). 5BL: Tauri supervisor for native backend and worker (complete). 5BM: Local PostgreSQL bootstrap. 5BN: Docker optional desktop runtime. 5BO: Windows clean-machine acceptance. 5BP: Linux clean-machine acceptance. 5BQ: Knowledge/Obsidian ingestion. Future phases remain documentation only here.

## Phase 5BJ desktop profile

`RUNTIME_PROFILE=desktop` selects the native PostgreSQL engine and authentication state; Redis/Celery are compatibility-only. The native worker now schedules bounded monitoring summary cycles and enforces queue depth, per-type concurrency, fixed priorities, and handler timeouts. Reports, recon, evidence, notifications, data quality, and other request flows remain synchronous because they have no registered Celery task and need their current authorization and transaction semantics. See `DESKTOP_NATIVE_RUNTIME.md` for the full dependency inventory and revised roadmap.

## Phase 5BL — Tauri native runtime supervision

Release desktop runs use the cross-platform Tauri supervisor for the fixed PyInstaller backend and worker. The supervisor verifies the RC6 release and native runtime profile, waits for PostgreSQL/migration/storage prerequisites before starting the worker, and reports owned versus external components. It uses bounded restart attempts and cooperative shutdown markers, and only terminates retained child processes that this desktop launched. A per-user Windows mutex or Linux file lock prevents duplicate desktop sessions from independently starting children. Backend port conflicts and external components are observation-only.

Windows portable/installer packages include Windows x86_64 backend and worker resources; Linux x86_64 packaging includes Linux runtime directories. PostgreSQL remains external and required. Redis/Celery are not required for native desktop mode, while Docker and development profiles remain supported. No OS autostart, systemd installation, updater, or automatic downloads are added. See `NATIVE_RUNTIME_SUPERVISOR.md` for ownership and shutdown details. Linux WSL evidence is not clean-machine Linux acceptance.
