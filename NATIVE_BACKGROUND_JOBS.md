# Native background jobs (Phase 5BI)

RavenTech now has an **opt-in** PostgreSQL job engine. Set `BACKGROUND_JOB_BACKEND=native` and run `python -m app.worker` from `backend` to process allowlisted jobs. The default remains `celery` for existing Docker installations. PostgreSQL and the FastAPI backend remain required; this phase does **not** remove Docker, Redis, or Celery.

## Current work inventory

| Work | Current path | Native status | Properties |
| --- | --- | --- | --- |
| Endpoint posture and recommendations after LAN telemetry | Synchronous | Migrated with compatibility fallback | Required, retryable, idempotent, bounded |
| Monitoring summary refresh | Request polling | Native handler available | Optional, retryable, idempotent |
| Data quality scan | Synchronous admin request | Deferred | Optional, retryable, idempotent |
| Reports | Synchronous | Deferred | Long running; validate idempotent output first |
| Recon and enrichment | Synchronous | Deferred | Scope and rate limits require review |
| Alert/notification maintenance | Synchronous/admin operations | Deferred | Scheduled candidate; operator policy review needed |
| Threat intelligence | Synchronous | Deferred | External provider limits apply |
| Evidence processing | Synchronous | Deferred | Preserve evidence provenance and transaction boundaries |
| Demo jobs | Synchronous | Deferred | Optional |
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

5BI: Native PostgreSQL worker (this phase). 5BJ: Finish Celery/Redis task migration. 5BK: Package FastAPI as a backend executable. 5BL: Tauri supervisor for native backend. 5BM: Local PostgreSQL bootstrap. 5BN: Docker optional desktop runtime. 5BO: Clean machine native desktop acceptance. These later phases are documentation only and are not implemented here.
