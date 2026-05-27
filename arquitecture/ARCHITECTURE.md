# RavenTech OSINT Platform — Architecture

> **Version:** 1.0 — Approved Blueprint
> **Author:** Brayan "Raven" Gutierrez · RavenTech
> **Date:** 2026-05-26
> **Status:** LOCKED FOR IMPLEMENTATION

---

## 1. System Overview

RavenTech OSINT is a **modular monolith threat intelligence platform** for authorized, defensive digital footprint analysis. It collects public data from 10+ OSINT sources, analyzes findings with Claude AI against cybersecurity frameworks (MITRE ATT&CK v19, OWASP 2025, NIST CSF 2.0, ISO/IEC 27001:2022), and produces structured reports with full audit trails.

**Architectural pattern:** Modular Monolith with Plugin Adapters
**Deployment target:** Docker Compose → Cloud VPS (Nginx + TLS)
**Primary users:** Small team (2–10), roles: `admin` / `analyst`

---

## 2. System Architecture Diagram

```mermaid
graph TB
    subgraph External
        U["👤 Analyst / Browser"]
        OSINT["OSINT APIs — v1.0 (5 adapters)\nShodan · VirusTotal · AbuseIPDB\nWHOIS/RDAP · DNS + crt.sh\n(6 more adapters in v1.1)"]
        CLAUDE["☁️ Claude API (Anthropic)\nclaude-3-5-sonnet"]
    end

    subgraph "Docker Network: raventech-net"
        NGINX["🌐 Nginx :443\nTLS Termination · Reverse Proxy\nStatic File Serving"]

        subgraph "Application Layer"
            API["⚙️ FastAPI :8000\nAsync · Pydantic · OpenAPI docs"]
            WORKER["🔧 Celery Worker\nAsync OSINT Jobs · AI Tasks · Report Tasks"]
            FE["💻 React + Vite\nTypeScript · shadcn/ui · Tailwind"]
        end

        subgraph "Data Layer"
            PG[("🐘 PostgreSQL 16\nMain Database\nACID · JSONB · Arrays")]
            REDIS[("🔴 Redis 7\nCelery Broker\nRate Limit Cache\nRefresh Token Blocklist")]
            CHROMA[("🔮 ChromaDB — embedded\nIn-process vector store\nMITRE · OWASP · NIST · ISO\nData persisted to /data/chroma volume")]
        end
    end

    U -->|"HTTPS :443"| NGINX
    NGINX -->|"/api/v1/*"| API
    NGINX -->|"/* (static)"| FE
    API --> PG
    API --> REDIS
    API --> CHROMA
    API -->|"dispatch_task(job_id)"| REDIS
    WORKER -->|"consume jobs"| REDIS
    WORKER --> OSINT
    WORKER --> CLAUDE
    WORKER --> PG
    WORKER --> CHROMA
```

---

## 3. Technology Stack

| Component | Technology | Version | Rationale |
|-----------|-----------|---------|-----------|
| Backend framework | FastAPI | 0.115+ | Async-native, auto OpenAPI docs, excellent Pydantic integration |
| Language | Python | 3.12 | Modern type hints, async/await, strong stdlib |
| ORM | SQLAlchemy | 2.0 (async) | Async sessions, type-safe queries, Alembic support |
| DB migrations | Alembic | latest | Version-controlled schema, autogenerate diffs |
| Database | PostgreSQL | 16 | ACID compliance, JSONB for raw findings, array types, full-text search |
| Task queue | Celery | 5.x | Async OSINT jobs, configurable retries, per-task rate limiting |
| Message broker | Redis | 7.x | Celery broker + result backend + rate limit counters |
| Vector store | ChromaDB | latest | **Embedded mode** — runs in-process inside backend/worker, data persisted to named Docker volume. No separate container. |
| Embeddings | sentence-transformers | latest | `all-MiniLM-L6-v2` — free, local, no API cost, 80MB model |
| AI analysis | Claude 3.5 Sonnet | Anthropic SDK | Best alignment for responsible use, structured JSON output |
| Auth tokens | PyJWT | latest | JWT encode/decode, HS256 + RS256 support |
| Password hashing | passlib[bcrypt] | latest | bcrypt cost factor 12 — industry standard |
| Rate limiting | slowapi | latest | Per-IP and per-user limits backed by Redis |
| HTTP client (backend) | httpx | latest | Async HTTP for all OSINT API calls, connection pooling |
| Input validation | pydantic-settings | latest | Type-safe .env config loading |
| PDF generation | WeasyPrint | latest | HTML→PDF with CSS styling, no commercial license |
| Frontend framework | React | 18 | Stable, large ecosystem, TypeScript-first |
| Frontend build | Vite | 5 | Fast HMR, optimized production builds |
| UI components | shadcn/ui + Tailwind CSS | latest | Production-quality, accessible, composable |
| State management | Zustand | latest | Lightweight, TypeScript-friendly, no boilerplate |
| HTTP client (frontend) | Axios | latest | Interceptors for auto token refresh |
| Reverse proxy | Nginx | 1.25 | TLS termination, static serving, upstream proxy |
| Containerization | Docker + Compose | latest | Reproducible builds, VPS-deployable with one command |

---

## 4. Complete Folder Structure

```
raventech-osint/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                        # App factory, lifespan events, middleware registration
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── router.py              # Include all sub-routers under /api/v1
│   │   │       ├── auth.py                # POST /login, /refresh, /logout, GET /me, PUT /me/password
│   │   │       ├── users.py               # CRUD /users/* [admin only]
│   │   │       ├── investigations.py      # CRUD /investigations/* + member management
│   │   │       ├── targets.py             # CRUD /targets/*
│   │   │       ├── osint.py               # POST /osint/scan, GET /osint/jobs/{id}, GET /osint/adapters, GET /findings/*
│   │   │       ├── ai.py                  # POST /ai/analyze, GET /ai/analyses/*
│   │   │       ├── reports.py             # POST /reports/generate, GET /reports/*, /download
│   │   │       └── admin.py               # /admin/health, /stats [admin only]  ← /api-keys deferred to v1.1
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py                  # Settings class (pydantic-settings) — all env vars
│   │   │   ├── security.py                # JWT create/verify, bcrypt hash/verify
│   │   │   ├── dependencies.py            # get_db(), get_current_user(), require_role()
│   │   │   ├── rate_limit.py              # slowapi Limiter instance + limit decorators
│   │   │   └── middleware.py              # AuditLogMiddleware, CORS config
│   │   ├── models/                        # SQLAlchemy ORM models — 1 file per table
│   │   │   ├── __init__.py
│   │   │   ├── base.py                    # Base + TimestampMixin
│   │   │   ├── user.py
│   │   │   ├── investigation.py
│   │   │   ├── investigation_member.py
│   │   │   ├── target.py
│   │   │   ├── scan_job.py
│   │   │   ├── finding.py
│   │   │   ├── ai_analysis.py
│   │   │   ├── report.py
│   │   │   └── audit_log.py               # (api_key.py deferred to v1.1)
│   │   ├── schemas/                       # Pydantic schemas — mirrors models/, for API I/O
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                    # LoginRequest, TokenResponse, RefreshRequest
│   │   │   ├── user.py                    # UserCreate, UserUpdate, UserResponse
│   │   │   ├── investigation.py
│   │   │   ├── target.py
│   │   │   ├── scan_job.py
│   │   │   ├── finding.py
│   │   │   ├── ai_analysis.py
│   │   │   └── report.py
│   │   ├── services/                      # Business logic — routes call ONLY services
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                    # Token creation, user lookup, password validation
│   │   │   ├── investigation.py           # CRUD + membership + authorization checks
│   │   │   ├── target.py                  # Target validation + CRUD
│   │   │   ├── report.py                  # Report orchestration + PDF generation
│   │   │   ├── audit.py                   # record_event(user, action, resource, details)
│   │   │   ├── osint/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py                # OsintTarget, OsintFinding dataclasses + BaseOsintAdapter ABC
│   │   │   │   ├── registry.py            # AdapterRegistry — auto-discover + register adapters
│   │   │   │   ├── orchestrator.py        # Fan-out to applicable adapters, parallel execution, merge
│   │   │   │   └── adapters/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── whois_rdap.py      # FREE — python-whois + RDAP API
│   │   │   │       ├── dns_crtsh.py       # FREE — dnspython + crt.sh API
│   │   │   │       ├── shodan.py          # PAID — SHODAN_API_KEY
│   │   │   │       ├── virustotal.py      # FREEMIUM — VT_API_KEY
│   │   │   │       └── abuseipdb.py       # FREEMIUM — ABUSEIPDB_API_KEY
│   │   │   │       # v1.1: alienvault · urlscan · securitytrails · censys · hibp · github_osint
│   │   │   └── ai/
│   │   │       ├── __init__.py
│   │   │       ├── client.py              # Anthropic SDK wrapper (async)
│   │   │       ├── rag.py                 # ChromaDB query — embed → search → rerank → return chunks
│   │   │       ├── embeddings.py          # sentence-transformers loader + encode()
│   │   │       ├── analyzer.py            # Main orchestrator: findings → RAG → Claude → store
│   │   │       └── prompts.py             # All prompt templates (system prompt + user template)
│   │   ├── workers/
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py              # Celery app instance + config
│   │   │   ├── osint_tasks.py             # run_scan_job(job_id: str) → void
│   │   │   ├── ai_tasks.py                # run_analysis(target_id: str) → void
│   │   │   └── report_tasks.py            # generate_report(report_id: str) → void
│   │   └── db/
│   │       └── session.py                 # AsyncEngine + AsyncSessionLocal + get_db()
│   ├── alembic/
│   │   ├── env.py                         # Async-compatible Alembic env
│   │   ├── script.py.mako
│   │   └── versions/                      # Migration files (auto-generated)
│   ├── tests/
│   │   ├── conftest.py                    # Fixtures: async test db, test client, auth headers
│   │   ├── unit/
│   │   │   ├── services/
│   │   │   └── adapters/                  # Mock each adapter, test normalize() + score_risk()
│   │   └── integration/
│   │       └── api/                       # HTTP-level tests per route file
│   ├── scripts/
│   │   ├── seed_rag.py                    # Load MITRE/OWASP/NIST/ISO into ChromaDB
│   │   ├── create_admin.py                # Bootstrap first admin user from env vars
│   │   └── health_check.py                # Docker HEALTHCHECK target
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── requirements-dev.txt               # pytest, httpx[test], pytest-asyncio, etc.
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx                        # Router (React Router v6), auth guard
│   │   ├── api/
│   │   │   ├── client.ts                  # Axios instance, base URL, token interceptors
│   │   │   ├── auth.ts
│   │   │   ├── investigations.ts
│   │   │   ├── targets.ts
│   │   │   ├── osint.ts
│   │   │   ├── reports.ts
│   │   │   └── types.ts                   # TypeScript types mirroring Pydantic schemas
│   │   ├── components/
│   │   │   ├── ui/                        # shadcn/ui components (Button, Card, Badge, etc.)
│   │   │   ├── layout/
│   │   │   │   ├── AppLayout.tsx          # Sidebar + topbar wrapper
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   └── Topbar.tsx
│   │   │   ├── investigations/
│   │   │   │   ├── InvestigationCard.tsx
│   │   │   │   └── InvestigationForm.tsx
│   │   │   ├── findings/
│   │   │   │   ├── FindingCard.tsx
│   │   │   │   ├── RiskBadge.tsx          # Color-coded risk level chip
│   │   │   │   └── FrameworkMappings.tsx  # MITRE/OWASP/NIST/ISO badges
│   │   │   └── reports/
│   │   │       └── ReportStatus.tsx
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── Dashboard.tsx              # Summary stats, recent investigations
│   │   │   ├── InvestigationList.tsx
│   │   │   ├── InvestigationDetail.tsx    # Targets + scan jobs + findings
│   │   │   ├── TargetDetail.tsx           # All findings + AI analysis for one target
│   │   │   ├── Reports.tsx
│   │   │   └── Admin.tsx                  # User management, audit logs [admin only]
│   │   ├── hooks/
│   │   │   ├── useAuth.ts                 # Login, logout, token refresh
│   │   │   └── useInvestigation.ts        # Fetch + cache investigation data
│   │   └── store/
│   │       └── authStore.ts               # Zustand: { user, role, isAuthenticated }
│   ├── public/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── Dockerfile
│
├── nginx/
│   ├── nginx.conf                         # Dev: no TLS, proxy API + serve static
│   ├── nginx.prod.conf                    # Prod: TLS (Let's Encrypt), HSTS, security headers
│   └── Dockerfile
│
├── scripts/
│   └── deploy.sh                          # VPS initial setup + docker compose pull + up
│
├── docker-compose.yml                     # Dev (PostgreSQL + Redis, no TLS, local ports exposed for debugging)
├── docker-compose.prod.yml                # Prod (PostgreSQL, TLS, no exposed ports except 443)
├── .env.example                           # All required env vars documented with comments
├── .gitignore
├── ARCHITECTURE.md                        # ← This file
├── MVP_ROADMAP.md
├── DATABASE_SCHEMA.md
├── API_SPEC.md
├── SECURITY_MODEL.md
├── CODEX_HANDOFF.md
└── README.md
```

---

## 5. Module Boundary Rules (Enforced)

| Rule | Description |
|------|-------------|
| **Routes → Services only** | API route functions call service functions. Zero direct DB access in routes. |
| **Services → DB + other services** | Services use `AsyncSession` from `get_db()` and may call other services. |
| **Adapters are stateless** | OSINT adapters receive a target, return a finding. No DB access, no state. |
| **Workers → Services** | Celery tasks call service functions, not routes, not DB directly. |
| **Prompts are isolated** | All Claude prompt strings live only in `services/ai/prompts.py`. |
| **Config via Settings** | No hardcoded values anywhere. All from `core/config.py` Settings. |
| **No secrets in code** | API keys only from environment variables. Never logged or serialized. |

---

## 6. Data Flow: OSINT Scan (Async Job Pattern)

```
POST /api/v1/osint/scan {target_id, adapters}
  │
  ▼ [Route: osint.py]
  Check investigation access → validate target → create scan_job (status: queued)
  │
  ▼ [Celery dispatch]
  osint_tasks.run_scan_job.delay(job_id)  ← returns {job_id} to caller immediately
  │
  ▼ [Worker: osint_tasks.py]
  Load job from DB
  Load applicable adapters from AdapterRegistry
  asyncio.gather(
    WhoisRdapAdapter.collect(target),
    DnsCrtshAdapter.collect(target),
    ShodanAdapter.collect(target),
    VirusTotalAdapter.collect(target),
    ...
  )
  For each result → normalize() + score_risk() → store finding in DB
  Update scan_job status: completed (or partial if some adapters failed)
  Optionally: dispatch ai_tasks.run_analysis.delay(target_id)
```

---

## 7. Data Flow: AI Analysis (RAG + Claude)

```
POST /api/v1/ai/analyze {target_id}
  │
  ▼ [Worker: ai_tasks.py]
  Load findings for target from DB
  Build finding summary text
  │
  ▼ [embeddings.py] → sentence-transformers encode(summary)
  embedding_vector = model.encode(summary)
  │
  ▼ [rag.py] → ChromaDB query (4 collections)
  mitre_chunks   = chroma.mitre_attack.query(embedding, n_results=5)
  owasp_chunks   = chroma.owasp.query(embedding, n_results=5)
  nist_chunks    = chroma.nist_csf.query(embedding, n_results=3)
  iso_chunks     = chroma.iso27001.query(embedding, n_results=3)
  │
  ▼ [prompts.py] → Build structured prompt
  prompt = build_analysis_prompt(findings, mitre_chunks, owasp_chunks, nist_chunks, iso_chunks)
  │
  ▼ [client.py] → Claude API call (claude-3-5-sonnet)
  response = anthropic.messages.create(model, system, user=prompt, max_tokens=4096)
  │
  ▼ Parse structured JSON response
  Store in ai_analyses table (risk_assessment, framework_mappings, recommendations)
```

---

## 8. Environment Variables (.env.example reference)

```bash
# App
APP_SECRET_KEY=          # 64-byte random hex — JWT signing key
APP_ENVIRONMENT=         # development | production
APP_ALLOWED_ORIGINS=     # comma-separated list of allowed CORS origins

# Database
DATABASE_URL=            # postgresql+asyncpg://user:pass@postgres:5432/raventech

# Redis
REDIS_URL=               # redis://redis:6379/0

# ChromaDB (embedded — no Docker service required)
CHROMA_DATA_PATH=        # /data/chroma — path inside backend/worker containers, mapped to named volume chroma_data

# AI
ANTHROPIC_API_KEY=       # sk-ant-...

# OSINT APIs (optional — adapters disabled if key absent)
SHODAN_API_KEY=
VT_API_KEY=
ABUSEIPDB_API_KEY=
OTX_API_KEY=
URLSCAN_API_KEY=
SECURITYTRAILS_API_KEY=
CENSYS_API_ID=
CENSYS_SECRET=
HIBP_API_KEY=
GITHUB_TOKEN=

# First admin (used by scripts/create_admin.py)
ADMIN_EMAIL=
ADMIN_PASSWORD=
ADMIN_USERNAME=
```
