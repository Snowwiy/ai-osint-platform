# RavenTech OSINT Platform — MVP Roadmap

> **Version:** 1.1 (post-review update)
> **Target:** v1.0 production-ready MVP
> **Timeline:** ~12 weeks (solo developer, transitioning to small team)
> **Philosophy:** Build the impressive part first. The demo that lands clients is working by Week 4.

---

## Architectural Decisions Applied (from Senior Review)

| Change | Reason |
|--------|--------|
| AI/RAG moved to Phase 1 (not Phase 3) | The RAG + Claude pipeline is the most impressive feature — validate and build it early |
| Only 5 adapters in v1.0 | Plugin architecture makes adding more trivial; quality > quantity |
| ChromaDB embedded (no Docker service) | Simpler ops, faster dev, no network overhead, same capability at MVP scale |
| Celery Beat removed from MVP | No scheduled tasks defined yet — premature infrastructure |
| `api_keys` table deferred to v1.1 | Full scoped key system costs 2 days; long-lived JWTs serve the small team |
| WeasyPrint PDF deferred to v1.1 | Heavy system deps, Dockerfile bloat, ARM issues — HTML reports work fine |
| `reports.config` JSONB removed | Generate full report always; add configuration in v1.1 |
| `investigation_members` simplified to 2 roles | `owner` + `collaborator` — `viewer` deferred to v2.0 |
| `authorization_statement` min length 100 chars | Enforce real authorization text, not "authorized" |

---

## Phase Overview

```
Phase 0: Foundation          ████░░░░░░░░  Weeks  1– 2  → Auth + DB + Docker + CI
Phase 1: AI Walking Skeleton ████░░░░░░░░  Weeks  3– 4  → 2 free adapters + RAG + Claude (END-TO-END DEMO)
Phase 2: OSINT Expansion     ████████░░░░  Weeks  5– 6  → Shodan + VirusTotal + AbuseIPDB + risk scoring
Phase 3: Frontend            ████████████  Weeks  7– 9  → React dashboard, job polling, findings display
Phase 4: Reports + Deploy    ████████████  Weeks 10–12  → HTML reports + Nginx TLS + v1.0 tag
```

---

## Phase 0: Foundation (Weeks 1–2)
**Goal:** Platform running in Docker. Admin can log in. DB schema exists. CI is configured.

**End state:** `docker compose up` → `GET /admin/health` returns healthy → login works → tests pass.

### Tasks

**Repository & CI (Do these FIRST)**
- [ ] Initialize Git repo, create `backend/`, `frontend/`, `nginx/`, root config files
- [ ] `.github/workflows/test.yml` — pytest + ruff + mypy on every push/PR to main
- [ ] `.pre-commit-config.yaml` — ruff, mypy, detect-secrets
- [ ] `Makefile` — `make dev`, `make test`, `make migrate`, `make seed-rag`, `make lint`
- [ ] `.gitignore` — `.env`, `*.pyc`, `__pycache__`, `node_modules`, `chroma_data/`, `reports_output/`
- [ ] `.env.example` — all required env vars documented with inline comments

**Backend Core**
- [ ] `backend/app/core/config.py` — pydantic-settings Settings class (all env vars, CHROMA_DATA_PATH instead of CHROMA_HOST/PORT)
- [ ] `backend/app/db/session.py` — AsyncEngine + AsyncSessionLocal (asyncpg)
- [ ] `backend/app/models/*.py` — all ORM models **except** `api_key.py` (deferred)
- [ ] `backend/alembic/env.py` — **sync psycopg2 engine** for migrations (see CODEX_HANDOFF.md Pattern 1)
- [ ] `backend/requirements.txt` — includes **both** `asyncpg` and `psycopg2-binary`
- [ ] Run: `alembic revision --autogenerate -m "initial"` → `alembic upgrade head`
- [ ] `backend/app/core/security.py` — `create_access_token()`, `create_refresh_token()`, `verify_token()`, `hash_password()`, `verify_password()`
- [ ] `backend/app/core/dependencies.py` — `get_db()`, `get_current_user()`, `require_role()`
- [ ] `backend/app/core/rate_limit.py` — slowapi Limiter
- [ ] `backend/app/core/middleware.py` — AuditLogMiddleware, CORS
- [ ] `backend/app/services/audit.py` — `record_event(user, action, resource_type, resource_id, details)`
- [ ] `backend/app/api/v1/auth.py` — POST /login, /refresh, /logout, GET /me, PUT /me/password
- [ ] `backend/app/api/v1/users.py` — CRUD [admin only]
- [ ] `backend/app/api/v1/investigations.py` — CRUD + member management (owner/collaborator roles)
- [ ] `backend/app/api/v1/targets.py` — CRUD + `validate_target_value()` (private IP blocklist, domain format)
- [ ] `backend/app/api/v1/admin.py` — GET /admin/health, GET /admin/stats
- [ ] `backend/scripts/create_admin.py` — bootstrap first admin from env vars
- [ ] `backend/Dockerfile` — Python 3.12 slim, multi-stage build (builder + runtime)
- [ ] `docker-compose.yml` — services: `nginx`, `backend`, `celery-worker`, `frontend`, `postgres`, `redis` (**no chroma service**)
- [ ] **No Celery Beat service** — not needed in v1.0

**Tests**
- [ ] `backend/tests/conftest.py` — async test DB, test client, auth header fixtures
- [ ] `backend/tests/integration/api/test_auth.py`
- [ ] `backend/tests/integration/api/test_investigations.py`
- [ ] `backend/tests/integration/api/test_targets.py`

### Phase 0 Exit Criteria
- [ ] `docker compose up` — all services healthy, no startup errors
- [ ] `GET /admin/health` returns `{"status": "healthy", "database": "ok", "redis": "ok"}`
- [ ] Login → JWT → access protected route → 200
- [ ] Auth tests pass: `pytest tests/integration/api/test_auth.py`
- [ ] CI workflow passes on GitHub
- [ ] `make lint` runs clean (ruff + mypy)

---

## Phase 1: AI Walking Skeleton (Weeks 3–4)
**Goal:** End-to-end pipeline working. Scan a domain → WHOIS + DNS data → Claude analysis → MITRE/OWASP/NIST/ISO framework mapping. This is the portfolio demo.

**End state:** Analyst can scan `acme.com`, trigger AI analysis, and see T-codes + recommendations in the API response.

### Tasks

**OSINT Core (2 free adapters)**
- [ ] `workers/celery_app.py` — Celery app with **prefork pool** (see CODEX_HANDOFF.md Pattern 2)
- [ ] `workers/osint_tasks.py` — `run_scan_job(job_id)` wrapping `asyncio.run(_async_impl)`
- [ ] `services/osint/base.py` — `OsintTarget`, `OsintFinding` dataclasses + `BaseOsintAdapter` ABC (with `display_name`, `api_key_env_var`, `is_available()`)
- [ ] `services/osint/registry.py` — `AdapterRegistry` with auto-discover
- [ ] `services/osint/orchestrator.py` — `fan_out()` with `asyncio.Semaphore(5)` (see CODEX_HANDOFF.md Pattern 3)
- [ ] `services/osint/adapters/whois_rdap.py` — FREE, supports: domain, org
- [ ] `services/osint/adapters/dns_crtsh.py` — FREE, supports: domain
- [ ] `api/v1/osint.py` — POST /osint/scan, GET /osint/jobs/{id}, **GET /osint/adapters**, GET /findings/, GET /findings/{id}
- [ ] Tests: `tests/unit/adapters/test_whois_rdap.py`, `test_dns_crtsh.py`

**RAG + AI Pipeline**
- [ ] `scripts/seed_rag.py` — reads Obsidian wiki markdown from `OBSIDIAN_WIKI_PATH`, chunks documents (~500 tokens, 50 overlap), inserts into 4 ChromaDB collections
- [ ] **Before coding:** validate RAG in `notebooks/validate_rag.ipynb` — embed a test finding → query all 4 collections → verify relevant chunks returned → call Claude → verify structured JSON output
- [ ] `services/ai/embeddings.py` — `get_model()` singleton + `encode(text)` → `list[float]` (see CODEX_HANDOFF.md Pattern 5)
- [ ] `services/ai/rag.py` — `get_chroma_client()` embedded singleton (Pattern 4) + `query_collections(embedding)` → top chunks per framework
- [ ] `services/ai/client.py` — async Anthropic SDK wrapper, retry on 429, token usage tracking
- [ ] `services/ai/prompts.py` — `SYSTEM_PROMPT` + `build_analysis_prompt(findings, rag_chunks)` → `str`
- [ ] `services/ai/analyzer.py` — full pipeline: load findings → embed → RAG → prompt → Claude → parse Pydantic model → store `AiAnalysis`
- [ ] `workers/ai_tasks.py` — `run_analysis(target_id)` Celery task
- [ ] `api/v1/ai.py` — POST /ai/analyze, GET /ai/analyses/, GET /ai/analyses/{id}
- [ ] `backend/Dockerfile` — add sentence-transformers model download RUN instruction (Pattern 5)
- [ ] Add `OBSIDIAN_WIKI_PATH` and `CHROMA_DATA_PATH` to `.env.example`
- [ ] Tests: `tests/unit/services/test_analyzer.py` (mock Claude + ChromaDB), `tests/unit/services/test_rag.py`

### Phase 1 Exit Criteria
- [ ] `make seed-rag` populates 4 ChromaDB collections without error
- [ ] Query "open port 8080 vulnerable Tomcat" retrieves T1190 from mitre_attack collection
- [ ] `POST /osint/scan` for `acme.com` → job completes → WHOIS + DNS findings stored
- [ ] `POST /ai/analyze` → Claude returns structured JSON with MITRE/OWASP/NIST/ISO mappings
- [ ] `GET /osint/adapters` returns list of 2 adapters, both `available: true`
- [ ] End-to-end demo: scan → analyze → read framework mappings from API

**🎯 Demo checkpoint:** At end of Phase 1, the core value proposition is demonstrable via API (no frontend yet). Record a demo video of the API calls for portfolio use.

---

## Phase 2: OSINT Expansion (Weeks 5–6)
**Goal:** 3 more adapters (including the two most impressive paid ones). Risk scoring is meaningful.

### Tasks
- [ ] `adapters/shodan.py` — PAID (SHODAN_API_KEY), supports: IP, domain; open ports, services, CVEs
- [ ] `adapters/virustotal.py` — FREEMIUM (VT_API_KEY), supports: domain, IP, URL; reputation, malicious flags
- [ ] `adapters/abuseipdb.py` — FREEMIUM (ABUSEIPDB_API_KEY), supports: IP; abuse score, report count
- [ ] Risk scoring calibration per adapter — documented scoring rubric in each adapter file
- [ ] Composite target risk: `max(finding.risk_score)` across all findings for a target — add `risk_score` field to Target response schema
- [ ] Graceful degradation: adapters with missing API keys report as `available: false` in `/osint/adapters`, not skipped silently
- [ ] Rate limit enforcement: httpx retry-after handling for 429 responses from OSINT APIs
- [ ] Tests: `tests/unit/adapters/test_shodan.py`, `test_virustotal.py`, `test_abuseipdb.py` (all with recorded httpx mock responses)
- [ ] `GET /admin/stats` endpoint — total findings, scans, token usage, estimated API cost

### Phase 2 Exit Criteria
- [ ] Full scan on a domain target: WHOIS + DNS + Shodan + VirusTotal findings stored
- [ ] Scan on an IP target: Shodan + AbuseIPDB findings stored
- [ ] Risk scores 0–100 per finding, meaningful by source type
- [ ] `GET /osint/adapters` correctly shows `available: false` when API key absent
- [ ] All 5 adapter unit tests pass

---

## Phase 3: Frontend Dashboard (Weeks 7–9)
**Goal:** Full workflow usable in the browser. No curl commands needed.

### Tasks
- [ ] Vite + React 18 + TypeScript init, Tailwind CSS + shadcn/ui setup
- [ ] `api/client.ts` — Axios instance + request interceptor (attach Bearer token) + response interceptor (refresh on 401 → retry)
- [ ] `api/types.ts` — TypeScript types mirroring all Pydantic schemas (snake_case, matching exactly)
- [ ] `api/auth.ts`, `api/investigations.ts`, `api/targets.ts`, `api/osint.ts`, `api/reports.ts`
- [ ] `store/authStore.ts` — Zustand: `{ user, role, accessToken, isAuthenticated }`
- [ ] `hooks/useAuth.ts` — `login()`, `logout()`, `refreshToken()`
- [ ] `pages/Login.tsx` — login form, error messages, redirect on success
- [ ] `pages/Dashboard.tsx` — stats cards: total investigations, findings, risk distribution, recent activity
- [ ] `pages/InvestigationList.tsx` — table + status badges + create button
- [ ] `pages/InvestigationDetail.tsx` — target list, member management, scan trigger, real-time job status polling (3-second interval until completed/failed)
- [ ] `pages/TargetDetail.tsx` — findings grouped by source, per-finding risk score + confidence badge, AI analysis section (framework mappings expandable)
- [ ] `pages/Reports.tsx` — generate button, download when status=ready
- [ ] `pages/Admin.tsx` — user management table, audit log viewer with filters [admin role only]
- [ ] `components/findings/RiskBadge.tsx` — color-coded: grey (0–10) / green (11–30) / yellow (31–50) / orange (51–75) / red (76–100)
- [ ] `components/findings/FrameworkMappings.tsx` — expandable chips: MITRE Txxxx / OWASP Axx:2025 / NIST CSF / ISO 27001
- [ ] React Router v6 routes + auth guard (redirect to `/login` if not authenticated, preserve intended URL)
- [ ] `frontend/Dockerfile` — `npm run build` → Nginx static serving
- [ ] `@tanstack/react-query` for all API calls (no manual loading/error useState)

### Phase 3 Exit Criteria
- [ ] Full workflow completable in browser: login → create investigation → add target → scan → poll → view findings → analyze → view framework mappings
- [ ] Job status updates without page refresh (polling visible in UI)
- [ ] Risk badges color-coded correctly at all risk levels
- [ ] Admin page visible only to admin role; 403 if analyst tries to access
- [ ] Build passes `npm run build` without errors

---

## Phase 4: Reports + Deploy + v1.0 Tag (Weeks 10–12)
**Goal:** Platform running on VPS with HTTPS, HTML reports downloadable, hardened, documented, tagged v1.0.

### Tasks

**HTML Reports (NOT WeasyPrint PDF — see v1.1 backlog)**
- [ ] `workers/report_tasks.py` — `generate_report(report_id)` Celery task
- [ ] `services/report.py` — Jinja2 HTML template rendering, file saved to reports volume
- [ ] Report template (`templates/report.html`) — includes legal disclaimer from SECURITY_MODEL.md §9, findings by target, AI analyses, framework mapping table, risk summary
- [ ] `api/v1/reports.py` — POST /generate (async), GET /, GET /{id}, GET /{id}/download (streams HTML file)
- [ ] Frontend: report status polling + download button in `pages/Reports.tsx`

**Production Deployment**
- [ ] `nginx/nginx.prod.conf` — HTTPS, HTTP→HTTPS redirect, security headers (HSTS, CSP, X-Frame-Options, etc.)
- [ ] `docker-compose.prod.yml` — production overrides (no debug, named volumes, resource limits, no exposed DB ports)
- [ ] `scripts/deploy.sh` — VPS init: install Docker, clone repo, configure `.env`, `docker compose -f docker-compose.prod.yml up -d`
- [ ] Let's Encrypt TLS — via Certbot or Nginx ACME challenge
- [ ] `chroma_data` named volume mounted in both `backend` and `celery-worker` services

**Hardening + v1.0**
- [ ] `pip-audit` — zero critical/high vulnerabilities → fix or document exceptions
- [ ] `npm audit` — zero critical/high vulnerabilities
- [ ] All items in `SECURITY_MODEL.md` §10 checklist completed
- [ ] `README.md` — installation guide, `.env` setup, `make dev` / `make seed-rag`, first-run instructions
- [ ] Update `docs/superpowers/specs/2026-05-26-osint-platform-design.md` with v1.0 changes
- [ ] Git tag: `v1.0.0`
- [ ] GitHub Release with changelog

### Phase 4 Exit Criteria (v1.0 Definition of Done)
- [ ] Platform running on VPS at `https://osint.raventech.mx` (or similar)
- [ ] HTTPS with valid Let's Encrypt certificate
- [ ] All 5 OSINT adapters produce real findings end-to-end
- [ ] AI analysis produces MITRE-mapped output for a real target
- [ ] HTML report generates and downloads correctly with legal disclaimer
- [ ] All audit events logged correctly
- [ ] `pip-audit` and `npm audit` pass
- [ ] Security checklist 100% complete
- [ ] v1.0.0 tag pushed to GitHub

---

## GitHub Milestone Structure

### M0: Foundation (Phase 0 — 10 issues)
1. Initialize repo, CI workflow, pre-commit, Makefile
2. Database models + Alembic migration (sync engine pattern)
3. JWT authentication endpoints (login, refresh, logout, me)
4. User management CRUD (admin only)
5. Investigation CRUD + member management (owner/collaborator)
6. Target management + validation (private IP blocklist)
7. Audit log middleware
8. Rate limiting (slowapi)
9. Docker Compose skeleton (6 services, no chroma service)
10. Integration tests: auth + investigations

### M1: AI Walking Skeleton (Phase 1 — 12 issues)
11. BaseOsintAdapter ABC + AdapterRegistry + Orchestrator (with Semaphore)
12. WHOIS/RDAP adapter
13. DNS + crt.sh adapter
14. Celery tasks: run_scan_job (prefork + asyncio.run pattern)
15. OSINT scan API endpoints (including GET /osint/adapters)
16. RAG validation notebook (notebooks/validate_rag.ipynb)
17. seed_rag.py — Obsidian wiki → ChromaDB (embedded)
18. sentence-transformers embeddings service (baked into Dockerfile)
19. RAG query pipeline (4 collections)
20. Claude API client + prompts
21. AI analysis pipeline + Celery task
22. AI analysis API endpoints

### M2: OSINT Expansion (Phase 2 — 8 issues)
23. Shodan adapter (IP + domain)
24. VirusTotal adapter (domain + IP + URL)
25. AbuseIPDB adapter (IP)
26. Risk scoring calibration (scoring rubric per adapter)
27. Composite target risk score (max of findings)
28. Graceful degradation (missing keys → available: false)
29. Rate limit + retry handling for OSINT APIs
30. GET /admin/stats (token usage, scan counts, finding counts)

### M3: Frontend (Phase 3 — 12 issues)
31. Vite + React + TypeScript + Tailwind + shadcn/ui setup
32. Axios client with interceptors + token refresh
33. Zustand auth store + login page
34. Dashboard page (stats cards)
35. Investigation list + create flow
36. Investigation detail + target management + scan trigger
37. Job status polling (3s interval)
38. Target detail: findings + RiskBadge + FrameworkMappings
39. Reports page + download
40. Admin page: user management + audit log viewer
41. Frontend Dockerfile + Nginx static
42. React Query setup for all API calls

### M4: Reports + Deploy + v1.0 (Phase 4 — 14 issues)
43. HTML report template (Jinja2) with legal disclaimer
44. Report generation Celery task
45. Report API endpoints + streaming download
46. Frontend: report polling + download button
47. Nginx production config (TLS, security headers)
48. docker-compose.prod.yml
49. deploy.sh VPS setup script
50. Let's Encrypt TLS
51. pip-audit pass (zero critical)
52. npm audit pass (zero critical)
53. Security checklist (SECURITY_MODEL.md §10) — 100% complete
54. README.md installation guide
55. v1.0.0 Git tag + GitHub Release
56. Demo video: end-to-end scan + AI analysis + report download

---

## v1.1 Backlog (after v1.0 ships)

| Feature | Description |
|---------|-------------|
| PDF reports | WeasyPrint or headless Chrome; HTML reports work fine for v1.0 |
| API key management | Full `api_keys` table with scopes, hashing, rotation |
| 6 additional adapters | AlienVault OTX, URLScan.io, SecurityTrails, Censys, HIBP, GitHub OSINT |
| Celery Beat + scheduled retention | 90-day finding cleanup, audit log archiving |
| Report configuration | Section selection, date range filters |
| Viewer role in investigations | Read-only investigation membership |

## v2.0 Backlog

| Feature | Description |
|---------|-------------|
| WebSocket real-time updates | Replace polling with push notifications |
| SSO / OAuth | For teams >10 users |
| ML-based risk scoring | Replace rule-based adapter scores |
| Threat actor correlation | Link findings to known APT TTPs |
| Scheduled recurring scans | Auto re-scan targets on interval |
| Public API | External programmatic access with rate limits |
