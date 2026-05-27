# RavenTech OSINT Platform — Codex Handoff

> **Purpose:** This file provides everything an AI coding assistant (Codex, Claude, Copilot) needs to build this platform correctly without prior context. Read this file and all blueprint files before writing any code.
>
> **Blueprint files to read first:**
> 1. `ARCHITECTURE.md` — system design, folder structure, data flows, module boundaries
> 2. `DATABASE_SCHEMA.md` — full SQL schema and table relationships
> 3. `API_SPEC.md` — all API endpoints with request/response schemas
> 4. `SECURITY_MODEL.md` — threat model, RBAC, auth design, safe-use policy
> 5. `MVP_ROADMAP.md` — phase-by-phase feature list and GitHub milestones

---

## Project Identity

- **Name:** RavenTech OSINT Platform
- **Owner:** Brayan "Raven" Gutierrez · RavenTech (Mexico)
- **Purpose:** Authorized, defensive digital footprint analysis platform
- **Stack:** FastAPI (Python 3.12) + React/Vite (TypeScript) + PostgreSQL + ChromaDB + Redis + Docker
- **AI layer:** Claude 3.5 Sonnet (Anthropic SDK) + sentence-transformers (local embeddings)
- **Phase:** Blueprint approved. Starting Phase 0 (Foundation).

---

## Architecture Summary (Read ARCHITECTURE.md for full details)

```
nginx → fastapi backend → postgresql + redis + chromadb
                        → celery worker → osint_apis + claude_api
react frontend (served by nginx)
```

**Pattern:** Modular Monolith. Routes call services. Services call DB. Adapters are stateless plugins.
**NO:** direct DB access in routes, business logic in routes, hardcoded config values, secrets in code.

---

## Absolute Rules for All Code Written

### Python Backend

1. **All async.** Use `async def` for all route handlers, service functions, and adapter methods. Use `await` for all DB operations, HTTP calls, and async operations.

2. **Type hints everywhere.** Every function parameter and return type must be annotated. Use `from __future__ import annotations` at top of every file. Use `uuid.UUID` not `str` for IDs in function signatures (Pydantic handles conversion from route params).

3. **Pydantic for all I/O.** Request bodies use Pydantic `BaseModel`. Response bodies use Pydantic `BaseModel`. No raw dicts returned from routes. No raw dicts in function signatures where a schema exists.

4. **SQLAlchemy 2.0 style only.** Use `async with AsyncSession` pattern. Use `select()` not `.query()`. No `.filter()` — use `.where()`. Always use `await db.execute(stmt)` then `.scalar_one_or_none()` or `.scalars().all()`.

5. **Config from Settings only.** Import `from app.core.config import settings`. Never use `os.environ.get()` outside of `config.py`.

6. **Errors are HTTPExceptions.** Services raise `HTTPException(status_code, detail)`. Routes do NOT catch generic exceptions — let FastAPI handle them. Add a global exception handler in `main.py` for unexpected errors (returns generic 500, no internal details).

7. **Tests for every service and adapter.** Unit tests mock external calls (httpx, Anthropic SDK, ChromaDB). Integration tests use a test database (separate from dev DB). Never test against production services.

8. **No print() statements.** Use `import logging; logger = logging.getLogger(__name__)`. Log at appropriate levels: DEBUG for adapter responses, INFO for job status changes, WARNING for retried errors, ERROR for failures.

### TypeScript Frontend

1. **TypeScript strict mode.** `"strict": true` in `tsconfig.json`. No `any` types. No `// @ts-ignore`.

2. **API types mirror backend.** All types in `api/types.ts`. Use the same field names as the Pydantic schemas (snake_case). Axios response types are always `ApiResponse<T>`.

3. **No inline fetch.** All API calls go through the typed functions in `api/*.ts`. No `fetch()` calls in components.

4. **Zustand for global state.** Auth state in `store/authStore.ts`. No prop drilling for auth. No Redux.

5. **React Query for server state.** Use `@tanstack/react-query` for all API calls in components. No manual loading/error state management with `useState`.

---

## File Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Python modules | `snake_case.py` | `osint_tasks.py` |
| Python classes | `PascalCase` | `ShodanAdapter` |
| Python functions | `snake_case` | `run_scan_job()` |
| TypeScript components | `PascalCase.tsx` | `InvestigationCard.tsx` |
| TypeScript hooks | `camelCase starting with 'use'` | `useAuth.ts` |
| TypeScript API functions | `camelCase` | `getInvestigations()` |
| TypeScript types | `PascalCase` | `Investigation`, `ScanJob` |
| SQL tables | `snake_case` | `scan_jobs`, `audit_logs` |
| Env variables | `SCREAMING_SNAKE_CASE` | `ANTHROPIC_API_KEY` |

---

## Key Interfaces (Do Not Change)

These interfaces are the contracts between modules. Implement them exactly.

### BaseOsintAdapter (services/osint/base.py)

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class TargetType(str, Enum):
    DOMAIN   = "domain"
    IP       = "ip"
    EMAIL    = "email"
    USERNAME = "username"
    ORG      = "org"
    URL      = "url"

@dataclass
class OsintTarget:
    type:             TargetType
    value:            str
    investigation_id: str
    target_db_id:     str          # UUID string of the targets.id row

@dataclass
class OsintFinding:
    source:          str            # "shodan" | "virustotal" | etc.
    target:          OsintTarget
    raw_data:        dict[str, Any] # Exactly what the API returned — never modify
    normalized_data: dict[str, Any] # Standard schema (see ARCHITECTURE.md §5)
    risk_score:      int            # 0–100
    confidence:      str            # "low" | "medium" | "high"
    evidence_urls:   list[str]  = field(default_factory=list)
    error:           str | None = None   # Set if collection partially failed


class BaseOsintAdapter(ABC):
    """All OSINT adapters MUST subclass this and implement all abstract methods."""

    source_name:       str            # Unique ID, e.g. "shodan"
    display_name:      str            # Human-readable, e.g. "WHOIS / RDAP"
    supported_targets: list[TargetType]
    requires_api_key:  bool = True
    api_key_env_var:   str  = ""     # e.g. "SHODAN_API_KEY" — used by is_available() + adapters endpoint

    @abstractmethod
    async def collect(self, target: OsintTarget) -> OsintFinding:
        """Fetch raw data from the source. Never raise — catch exceptions and set finding.error."""
        ...

    @abstractmethod
    def normalize(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Convert source-specific format to the standard normalized_data schema."""
        ...

    @abstractmethod
    def score_risk(self, normalized: dict[str, Any]) -> int:
        """Return integer 0–100. 0=clean, 25=low, 50=medium, 75=high, 100=critical."""
        ...

    def supports(self, target: OsintTarget) -> bool:
        return target.type in self.supported_targets

    def is_available(self, settings) -> bool:
        """Return False if required API key is absent — adapter will be skipped and shown as unavailable."""
        if not self.requires_api_key:
            return True
        return bool(getattr(settings, self.api_key_env_var.lower(), None))
```

### Normalized Finding Schema

Every adapter's `normalize()` must return a dict that is a subset of this schema. Include only fields the adapter actually populates. Do NOT invent new top-level keys.

```python
{
    # Network / Infrastructure (Shodan, Censys)
    "open_ports":    [80, 443, 8080],
    "services":      [{"port": 80, "protocol": "tcp", "banner": "nginx/1.18", "product": "nginx"}],
    "vulnerabilities": [{"cve": "CVE-2021-44228", "cvss": 10.0, "description": "Log4Shell"}],
    "hostnames":     ["mail.example.com"],
    "asn":           {"number": 12345, "name": "Example ISP", "country": "MX"},
    "os":            "Linux",

    # Reputation (VirusTotal, AbuseIPDB, AlienVault)
    "reputation":    {"malicious": False, "suspicious": True, "score": 15, "sources": 3},
    "abuse_reports": {"count": 0, "confidence": 0},
    "threat_intel":  [{"type": "malware", "name": "Mirai", "source": "OTX"}],

    # Domain / DNS (WHOIS, DNS/crt.sh, SecurityTrails)
    "registrar":     "GoDaddy, LLC",
    "registered":    "2020-01-15",
    "expires":       "2027-01-15",
    "nameservers":   ["ns1.example.com"],
    "dns_records":   {"A": ["1.2.3.4"], "MX": ["mail.example.com"], "TXT": [...]},
    "subdomains":    ["www.example.com", "mail.example.com", "dev.example.com"],

    # Certificates
    "certificates":  [{"subject": "example.com", "issuer": "Let's Encrypt", "expires": "2026-09-01", "san": [...]}],

    # Email / Breach (HIBP)
    "breach_data":   {"breached": False, "breach_count": 0, "breaches": []},

    # URL / Web (URLScan)
    "technologies":  ["Nginx", "React", "Cloudflare"],
    "redirects":     ["http://example.com → https://example.com"],
    "links":         [],

    # Code Exposure (GitHub)
    "github_exposure": {"repos": 3, "exposed_secrets_patterns": 0, "public_emails": []}
}
```

### AdapterRegistry (services/osint/registry.py)

```python
class AdapterRegistry:
    """Discovers and manages all OSINT adapters."""

    def register(self, adapter: BaseOsintAdapter) -> None: ...
    def get_all(self) -> list[BaseOsintAdapter]: ...
    def get_for_target(self, target: OsintTarget, settings) -> list[BaseOsintAdapter]:
        """Return adapters that support(target) AND is_available(settings)."""
        ...
    def get_by_name(self, name: str) -> BaseOsintAdapter | None: ...
```

### Celery Task Signature (workers/osint_tasks.py)

```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="raventech.osint.run_scan_job",
)
async def run_scan_job(self, job_id: str) -> None:
    """
    Runs all requested adapters for a scan job.
    - Loads job + target from DB
    - Gets applicable adapters from registry
    - Runs adapters in parallel with asyncio.gather
    - Stores findings to DB
    - Updates job status
    - On error: updates job status to 'failed', does NOT raise
    """
    ...
```

---

## Database Access Pattern

```python
# CORRECT — use async session from dependency injection
from app.db.session import AsyncSessionLocal

# In Celery tasks (no FastAPI DI):
async def _run():
    async with AsyncSessionLocal() as db:
        job = await db.get(ScanJob, uuid.UUID(job_id))
        ...

# In route handlers (via FastAPI DI):
@router.get("/investigations/{id}")
async def get_investigation(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ...

# CORRECT — SQLAlchemy 2.0 style
from sqlalchemy import select
stmt = select(Finding).where(Finding.target_id == target_id).order_by(Finding.collected_at.desc())
result = await db.execute(stmt)
findings = result.scalars().all()

# WRONG — do not use
findings = db.query(Finding).filter(Finding.target_id == target_id).all()  # NO
```

---

## AI Pipeline Contract (services/ai/analyzer.py)

```python
async def analyze_target(
    target_id: uuid.UUID,
    finding_ids: list[uuid.UUID] | None,
    db: AsyncSession,
) -> AiAnalysis:
    """
    Full pipeline:
    1. Load findings from DB
    2. Build finding summary text
    3. Embed with sentence-transformers
    4. Query 4 ChromaDB collections
    5. Build prompt (see prompts.py)
    6. Call Claude via client.py
    7. Parse structured JSON response
    8. Store AiAnalysis in DB
    9. Return AiAnalysis ORM object
    """
```

**Claude must be called with a structured output requirement.** The system prompt in `prompts.py` must include the exact JSON schema the model should return. Parse the response with Pydantic. If parsing fails, log the raw response and store `risk_assessment = "none"` with an error note.

---

## ChromaDB Collection Schema

```python
# Each document inserted into ChromaDB:
{
    "id":        "mitre-T1190",           # Unique ID within collection
    "document":  "Full text of the chunk...",
    "metadata": {
        "framework":  "mitre_attack",      # "mitre_attack" | "owasp" | "nist_csf" | "iso27001"
        "id":         "T1190",             # Technique/control ID
        "name":       "Exploit Public-Facing Application",
        "category":   "Initial Access",   # Tactic / Top 10 category / CSF function / ISO domain
        "type":       "technique",        # "technique" | "subtechnique" | "category" | "control"
    }
}
```

---

## Seed RAG Script (scripts/seed_rag.py)

```python
# Reads from the Obsidian wiki at the path in settings.OBSIDIAN_WIKI_PATH
# Parses markdown files from:
#   wiki/frameworks/mitre-attack.md        → mitre_attack collection
#   wiki/frameworks/owasp-*.md             → owasp collection
#   wiki/frameworks/nist-*.md              → nist_csf collection
# Splits documents into chunks of ~500 tokens with 50-token overlap
# Embeds each chunk with embeddings.py
# Upserts into ChromaDB (idempotent — safe to re-run)
```

Add `OBSIDIAN_WIKI_PATH=C:\Users\Ravenslg\Documents\Obsidian\Raven's Memory\wiki\frameworks` to `.env.example`.

---

## Error Handling Rules

| Layer | Rule |
|-------|------|
| OSINT Adapters | Catch ALL exceptions inside `collect()`. Set `finding.error = str(e)`. Never raise. Return the finding object with `error` set and `raw_data = {}`, `normalized_data = {}`, `risk_score = 0`. |
| Celery Tasks | Catch job-level errors. Update `scan_job.status = 'failed'`. Do not let task crash without updating DB. |
| Services | Raise `HTTPException` for business rule violations. Let unexpected exceptions bubble up to FastAPI's global handler. |
| Routes | Zero try/except blocks. Let exceptions propagate to FastAPI handlers. |
| Claude API | Retry on 429 (exponential backoff, max 3 retries). On repeated failure, store `risk_assessment = "none"` with error note in `analysis_text`. |

---

## Starting Point: Phase 0 Tasks (First Things to Build)

Build in this exact order to avoid dependency problems:

1. `backend/app/core/config.py` — Settings class. Everything depends on this.
2. `backend/app/db/session.py` — AsyncEngine + AsyncSessionLocal. Everything DB depends on this.
3. `backend/app/models/*.py` — All ORM models **except** `api_key.py` (deferred to v1.1). Alembic depends on these.
4. `backend/alembic/` — Set up with **sync psycopg2 engine** (see Alembic section below). Run `alembic revision --autogenerate -m "initial"` + `alembic upgrade head`.
5. `backend/app/core/security.py` — JWT + bcrypt. Auth routes depend on this.
6. `backend/app/core/dependencies.py` — `get_db()`, `get_current_user()`, `require_role()`. All routes depend on these.
7. `backend/app/api/v1/auth.py` — Login/logout/refresh. Test this manually first.
8. `backend/app/core/middleware.py` — AuditLogMiddleware. Add to main.py.
9. `backend/app/api/v1/users.py` + `investigations.py` + `targets.py`
10. `backend/scripts/create_admin.py` — Bootstrap. Run this after step 4 to create first admin.
11. `backend/tests/conftest.py` + `test_auth.py` — Tests should pass before moving to Phase 1.
12. `docker-compose.yml` — Get everything running with `docker compose up`. Services: `nginx`, `backend`, `celery-worker`, `frontend`, `postgres`, `redis`. No `chroma` service (embedded).

---

## Important: Things That Must NOT Be Changed Without Updating All Blueprint Files

- Database table names or column names (Alembic migration must be created)
- API endpoint paths or HTTP methods (update API_SPEC.md)
- Platform role names (`admin`, `analyst`) or role permission table (update SECURITY_MODEL.md)
- Investigation member roles (`owner`, `collaborator`) — update DB schema + service layer + frontend
- `BaseOsintAdapter` method signatures (all 5 v1.0 adapters must be updated)
- Normalized finding schema top-level keys (all adapters + AI prompts + frontend must be updated)
- JWT payload structure (update SECURITY_MODEL.md + ARCHITECTURE.md)
- `CHROMA_DATA_PATH` — must match in both `backend` and `celery-worker` service volume mounts

---

## Critical Implementation Patterns

These patterns MUST be followed exactly. Deviating from them produces failures that are hard to debug.

### Pattern 1 — Alembic: Use Sync Engine for Migrations

The app uses `asyncpg` for async DB access. Alembic requires synchronous connections. Install both drivers and use a sync URL for Alembic only.

```
# requirements.txt — BOTH required
asyncpg          # FastAPI + SQLAlchemy async runtime
psycopg2-binary  # Alembic env.py (sync migrations only)
```

```python
# alembic/env.py — complete correct implementation
from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from alembic import context
from app.core.config import settings
from app.models.base import Base  # import all models so metadata is populated
import app.models  # noqa: F401 — side effect: registers all models with Base.metadata

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata

# KEY: convert asyncpg URL → psycopg2 URL for sync migrations
sync_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")

def run_migrations_offline() -> None:
    context.configure(url=sync_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = create_engine(sync_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

---

### Pattern 2 — Celery: prefork pool + asyncio.run()

Celery tasks call async OSINT adapters. This works with prefork pool. Never use gevent or eventlet — they break `asyncio.run()`.

```python
# workers/celery_app.py
from celery import Celery
from app.core.config import settings

celery_app = Celery("raventech")
celery_app.conf.update(
    broker_url=settings.REDIS_URL,
    result_backend=settings.REDIS_URL,
    worker_pool="prefork",         # CRITICAL — never change to gevent/eventlet
    worker_concurrency=4,          # Tune to VPS vCPU count
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,           # Ack only after task completes (safer for retries)
)
```

```python
# workers/osint_tasks.py — correct async wrapping
import asyncio
from workers.celery_app import celery_app
from app.db.session import AsyncSessionLocal

@celery_app.task(bind=True, max_retries=3, default_retry_delay=30,
                 name="raventech.osint.run_scan_job")
def run_scan_job(self, job_id: str) -> None:
    """Sync wrapper → calls async implementation via asyncio.run()."""
    asyncio.run(_run_scan_job_async(job_id))

async def _run_scan_job_async(job_id: str) -> None:
    async with AsyncSessionLocal() as db:
        ...  # all async logic here
```

---

### Pattern 3 — Adapter Fan-out: asyncio.Semaphore

Limit concurrent outbound OSINT connections per scan job. Parallel requests from the same IP trigger rate limits on Shodan and VirusTotal.

```python
# services/osint/orchestrator.py
import asyncio
from services.osint.base import BaseOsintAdapter, OsintTarget, OsintFinding

MAX_CONCURRENT_ADAPTERS = 5

async def fan_out(
    adapters: list[BaseOsintAdapter],
    target: OsintTarget,
) -> list[OsintFinding]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_ADAPTERS)

    async def _guarded(adapter: BaseOsintAdapter) -> OsintFinding:
        async with semaphore:
            return await adapter.collect(target)  # never raises — errors → finding.error

    results = await asyncio.gather(
        *[_guarded(a) for a in adapters],
        return_exceptions=True,
    )
    # Filter out any unexpected exceptions (should not happen; adapters catch internally)
    return [r for r in results if isinstance(r, OsintFinding)]
```

---

### Pattern 4 — ChromaDB: Embedded Singleton

ChromaDB runs in-process. No Docker service. Initialize once per process (both backend and worker share the same volume path but run in separate processes with their own in-memory state).

```python
# services/ai/rag.py
import chromadb
from chromadb import PersistentClient, Collection
from app.core.config import settings

_client: PersistentClient | None = None

def get_chroma_client() -> PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.CHROMA_DATA_PATH)
    return _client

def get_collection(name: str) -> Collection:
    """Get or create a ChromaDB collection. Safe to call repeatedly."""
    return get_chroma_client().get_or_create_collection(name=name)
```

Volume mount in `docker-compose.yml` (BOTH services must mount the same volume):
```yaml
services:
  backend:
    volumes:
      - chroma_data:/data/chroma
  celery-worker:
    volumes:
      - chroma_data:/data/chroma  # same volume — same persisted data

volumes:
  chroma_data:
```

> **Note:** Because backend and celery-worker are separate processes writing to the same ChromaDB path, ChromaDB's SQLite lock may cause issues if both write simultaneously. In v1.0, only the Celery worker writes to ChromaDB (via `seed_rag.py` + analysis tasks) and the backend only reads (via `/ai/analyses` endpoints). Keep this write/read split clean.

---

### Pattern 5 — sentence-transformers: Bake into Docker Image

```dockerfile
# backend/Dockerfile — place AFTER pip install, BEFORE CMD
RUN python -c "\
    from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); \
    print('Model downloaded successfully')"
```

```python
# services/ai/embeddings.py — module-level singleton, loaded once per process
from __future__ import annotations
from sentence_transformers import SentenceTransformer

_model: SentenceTransformer | None = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        # Loads from local cache (baked into image) — no network call in production
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model

def encode(text: str) -> list[float]:
    """Encode text to embedding vector. Loads model on first call."""
    return get_model().encode(text, convert_to_numpy=True).tolist()
```

---

### Pattern 6 — GET /osint/adapters: Self-Documenting Registry

```python
# api/v1/osint.py
from services.osint.registry import adapter_registry

@router.get("/adapters")
async def list_adapters(current_user: User = Depends(get_current_user)) -> dict:
    """Return all registered adapters and their availability status."""
    adapters_info = []
    available_count = 0

    for adapter in adapter_registry.get_all():
        is_available = adapter.is_available(settings)
        if is_available:
            available_count += 1
        entry = {
            "name": adapter.source_name,
            "display_name": adapter.display_name,  # Add this attribute to BaseOsintAdapter
            "available": is_available,
            "requires_api_key": adapter.requires_api_key,
            "supported_targets": [t.value for t in adapter.supported_targets],
        }
        if not is_available:
            entry["unavailable_reason"] = f"{adapter.api_key_env_var} not configured"
        adapters_info.append(entry)

    return {
        "adapters": adapters_info,
        "total": len(adapters_info),
        "available": available_count,
        "unavailable": len(adapters_info) - available_count,
    }
```

Add to `BaseOsintAdapter`:
```python
class BaseOsintAdapter(ABC):
    source_name: str
    display_name: str          # Human-readable, e.g. "WHOIS / RDAP"
    supported_targets: list[TargetType]
    requires_api_key: bool = True
    api_key_env_var: str = ""  # e.g. "SHODAN_API_KEY" — used for unavailable_reason message

    def is_available(self, settings) -> bool:
        if not self.requires_api_key:
            return True
        return bool(getattr(settings, self.api_key_env_var.lower(), None))
```

---

## Environment: Development vs Production

| Setting | Development | Production |
|---------|------------|-----------|
| `APP_ENVIRONMENT` | `development` | `production` |
| Debug mode | ON (FastAPI reload) | OFF |
| CORS | `http://localhost:5173` | Actual VPS domain |
| Database | Local PostgreSQL via Docker | Same (in prod compose) |
| TLS | No | Yes (Nginx + Let's Encrypt) |
| Logs | Console (colored) | JSON (structured, to stdout) |
| ChromaDB | embedded — `CHROMA_DATA_PATH` volume (no Docker service) | Same |

In production:
- FastAPI must NOT expose `/docs` or `/redoc` (set `docs_url=None, redoc_url=None` in prod)
- Error responses must NOT include stack traces
- All HTTP headers from SECURITY_MODEL.md §7 must be set
