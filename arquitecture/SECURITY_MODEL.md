# RavenTech OSINT Platform — Security Model

> **Version:** 1.0
> **Frameworks:** MITRE ATT&CK v19 · OWASP Top 10 2025 · NIST CSF 2.0 · ISO/IEC 27001:2022

---

## 1. Platform Purpose & Ethical Boundaries

This platform is built exclusively for **authorized, defensive digital footprint analysis**. All use must comply with applicable laws and be preceded by explicit written authorization.

### Permitted Use
- Analyzing your own organization's public-facing infrastructure
- Authorized third-party assessments with written permission
- Academic and CTF research on intentionally vulnerable targets
- Blue team / SOC threat intelligence on known attacker infrastructure

### Prohibited Use (Hard Technical Controls + Policy)
| Prohibited Activity | Control Mechanism |
|--------------------|------------------|
| Doxxing individuals | Private IP/personal email validation; no person-targeting target types |
| Stalking / location tracking | No geolocation APIs; target type `username` limited to org-context use |
| Credential abuse | No password/credential lookup APIs integrated |
| Social engineering support | No social graph or relationship mapping features |
| Malware execution | No file execution, no payload delivery, no C2 integration |
| Unauthorized access | Platform makes READ-ONLY calls to PUBLIC APIs; no active exploitation |
| Invasive personal targeting | No endpoints for personal PII correlation |

---

## 2. Threat Model (STRIDE)

### Threats Against the Platform Itself

| # | Threat | STRIDE | ATT&CK Technique | Mitigations |
|---|--------|--------|-----------------|-------------|
| T1 | Unauthenticated API access | Spoofing | T1078 Valid Accounts | JWT required on all `/api/v1/*`; HTTPS only |
| T2 | Token theft (access token) | Spoofing | T1539 Steal Web Session Cookie | Short TTL (30 min); httpOnly refresh cookie |
| T3 | Privilege escalation (analyst → admin) | Elevation | T1548 Abuse Elevation Control | `require_role()` on every admin route; roles in JWT + DB |
| T4 | Horizontal privilege (access other user's investigations) | Elevation | T1078 | Membership check on every investigation access |
| T5 | SQL injection | Tampering | T1190 | SQLAlchemy ORM; parameterized queries only; no raw SQL |
| T6 | Prompt injection via OSINT data | Tampering | T1059 | Findings sanitized before prompt; structured data, not raw strings |
| T7 | SSRF via target input | Tampering | T1583 | Target validation; private IP blocklist enforced in `services/target.py` |
| T8 | Brute force login | Spoofing | T1110 | 5 failed → 15-min lockout; `slowapi` per-IP rate limit |
| T9 | API key theft / leak | Spoofing | T1552 | **v1.0:** No platform API keys — long-lived JWTs only. **v1.1:** SHA-256 hash stored only; raw key shown once; rotate on suspicion. |
| T10 | Insecure OSINT API keys | Info Disclosure | T1552.001 | Keys in `.env` only; never logged; never in DB; never in responses |
| T11 | Report file access without auth | Info Disclosure | T1083 | Reports in private Docker volume; served only via authenticated endpoint |
| T12 | CORS attack | Spoofing | T1185 | Strict `ALLOWED_ORIGINS` allowlist; no wildcard in production |
| T13 | Dependency supply chain attack | Tampering | T1195 | `pip-audit` + `npm audit` in CI; dependabot alerts enabled |
| T14 | Secret committed to git | Info Disclosure | T1552.001 | `.gitignore` for `.env`; pre-commit hook for secret patterns |
| T15 | Data breach via excessive collection | Info Disclosure | T1530 | Data minimization; scope definition required; 90-day retention default |
| T16 | Celery task manipulation | Tampering | T1059 | Tasks receive only IDs, not data; all data loaded from DB inside task |
| T17 | Log tampering | Tampering | T1070 | `audit_logs` is append-only; no update/delete endpoints; admin-only read |
| T18 | Insecure direct object reference | Elevation | T1083 | All resource lookups verify ownership/membership, not just existence |

---

## 3. Authentication Design

### JWT Token Flow

```
[POST /auth/login]
    │
    ├─ Verify credentials (bcrypt compare, constant-time)
    ├─ Check is_active = TRUE
    ├─ Record auth.login in audit_logs
    │
    ├─ Create access_token: {sub, role, jti, type:"access", exp:+30min}
    ├─ Create refresh_token: {sub, jti, type:"refresh", exp:+7days}
    │
    ├─ Store refresh token jti in Redis (TTL: 7 days)
    │
    └─ Response: {access_token} + Set-Cookie: refresh_token (httpOnly, Secure)

[Every API request]
    │
    ├─ Extract Bearer token from Authorization header
    ├─ Verify signature (HS256 with APP_SECRET_KEY)
    ├─ Check exp (reject if expired)
    ├─ Check type = "access" (reject refresh tokens used as access)
    ├─ Load user from DB (verify still active)
    └─ Attach user to request context

[POST /auth/logout]
    │
    ├─ Extract refresh token from cookie
    ├─ Remove jti from Redis (token revoked)
    └─ Clear cookie
```

### Password Policy
- Minimum 12 characters
- At least 1 uppercase, 1 lowercase, 1 digit, 1 special character
- bcrypt cost factor 12
- No password stored in plaintext anywhere, including logs

### Login Brute Force Protection
```python
# Per IP: 5 attempts in 15-minute window → 429 + Retry-After header
@limiter.limit("5/15minutes", key_func=get_remote_address)
@router.post("/auth/login")
```

---

## 4. Role-Based Access Control (RBAC)

### Role Definitions

| Permission | admin | analyst |
|-----------|-------|---------|
| View own investigations | ✅ | ✅ |
| View shared investigations | ✅ | ✅ |
| View all investigations | ✅ | ❌ |
| Create investigations | ✅ | ✅ |
| Add/remove members (own) | ✅ | ✅ (owner role within investigation — `owner` or `collaborator`) |
| Add targets | ✅ | ✅ |
| Start OSINT scans | ✅ | ✅ |
| View findings | ✅ | ✅ (own investigations only) |
| Request AI analysis | ✅ | ✅ |
| Generate reports | ✅ | ✅ |
| Download reports | ✅ | ✅ (own investigations only) |
| View all users | ✅ | ❌ |
| Create/modify/delete users | ✅ | ❌ |
| Change user roles | ✅ | ❌ |
| View audit logs | ✅ | ❌ |
| Manage API keys | ✅ (v1.1 only) | ❌ |
| View system stats | ✅ | ❌ |

### Implementation Pattern

```python
# core/dependencies.py

def require_role(*roles: UserRole) -> Depends:
    """FastAPI dependency — raises 403 if user role not in allowed roles."""
    async def _check(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return Depends(_check)


async def get_investigation_or_403(
    investigation_id: UUID,
    db: AsyncSession,
    current_user: User,
) -> Investigation:
    """Load investigation, enforce membership. Admins bypass membership check."""
    inv = await db.get(Investigation, investigation_id)
    if not inv:
        raise HTTPException(404, "Investigation not found")

    if current_user.role == UserRole.ADMIN:
        return inv

    stmt = select(InvestigationMember).where(
        InvestigationMember.investigation_id == investigation_id,
        InvestigationMember.user_id == current_user.id,
    )
    member = (await db.execute(stmt)).scalar_one_or_none()
    if not member:
        raise HTTPException(403, "Access denied to this investigation")

    return inv
```

---

## 5. Input Validation & Injection Prevention

### Target Validation Rules

```python
# services/target.py — validate_target_value()

PRIVATE_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

def validate_target_value(target_type: TargetType, value: str) -> str:
    if target_type == TargetType.IP:
        ip = ipaddress.ip_address(value)  # Raises ValueError if invalid
        for private_range in PRIVATE_IP_RANGES:
            if ip in private_range:
                raise ValueError(f"Private IP ranges are not permitted targets")
        return str(ip)

    if target_type == TargetType.DOMAIN:
        # Must be a valid FQDN, no IP addresses, no localhost
        if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$', value):
            raise ValueError("Invalid domain name format")
        return value.lower()

    # ... additional rules per type
```

### Prompt Injection Prevention

OSINT findings contain data from external sources (banners, DNS records, WHOIS text). This data could contain prompt injection attempts. Mitigation:

1. **Structured data format** — findings are passed to Claude as structured JSON fields, not free-form text concatenated into the prompt
2. **Field length limits** — each finding field truncated at 500 chars before inclusion in prompt
3. **Explicit role instruction** — system prompt emphasizes Claude's analytical role and instructs it to treat finding data as untrusted input
4. **Output schema enforcement** — Claude is instructed to respond in a specific JSON schema; off-schema responses are rejected

---

## 6. Secret Management

| Secret | Storage | Access Pattern | Rotation |
|--------|---------|----------------|---------|
| APP_SECRET_KEY | `.env` / VPS secret manager | Config only | On compromise |
| DATABASE_URL | `.env` | Config only | On compromise |
| ANTHROPIC_API_KEY | `.env` | Celery worker only | Monthly recommended |
| OSINT API keys | `.env` | Adapter classes only | Per provider schedule |
| Admin initial password | `.env` (create_admin.py only) | Deleted after first login | N/A |

**Rules:**
- `.env` never committed to git (`.gitignore` entry required)
- No secrets in Docker image layers (use `--env-file` at runtime)
- No secrets in API responses, even partial
- No secrets in log output (middleware strips Authorization headers)

---

## 7. Network Security

### Docker Network Isolation
- All services on internal `raventech-net` bridge network
- Only Nginx exposes external ports (80 → redirect, 443 → HTTPS)
- PostgreSQL, Redis, ChromaDB have NO external port exposure
- Celery workers have NO external ports

### Nginx Security Headers (nginx.prod.conf)
```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';" always;
```

---

## 8. Audit & Compliance

### Audit Log Integrity
- `audit_logs` table is append-only by design: no `UPDATE` or `DELETE` endpoint
- Log entries are written by `AuditLogMiddleware` — fires on every mutating request regardless of route handler
- Admins can read logs but cannot modify them via the platform
- For additional integrity, consider periodic log export to an immutable store (S3, cold storage)

### NIST CSF 2.0 Alignment

| Function | Category | Platform Control |
|----------|---------|-----------------|
| Identify | ID.AM | Asset tracking via targets + investigations |
| Protect | PR.AA | JWT auth + RBAC + bcrypt |
| Protect | PR.DS | Data minimization, retention policy, encrypted transport |
| Detect | DE.AE | Audit logging of all events |
| Respond | RS.AN | Report generation, finding evidence chain |
| Recover | RC.RP | Findings + reports retained for post-incident review |

### ISO/IEC 27001:2022 Controls (Key)

| Control | Description | Implementation |
|---------|-------------|---------------|
| 5.15 | Access control | RBAC + JWT + investigation membership |
| 5.16 | Identity management | User accounts, admin-managed |
| 8.2 | Privileged access rights | Admin role separation, audit trail |
| 8.4 | Access to source code | Git access controls (out of platform scope) |
| 8.8 | Management of technical vulnerabilities | `pip-audit` in CI |
| 5.33 | Protection of records | Audit logs immutable, retained indefinitely |

---

## 9. Safe-Use Policy

Every generated report must include the following disclaimer. The report generation service enforces this.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LEGAL AND ETHICAL DISCLAIMER

This report was generated by RavenTech OSINT Platform.
All information is derived from publicly available sources.

USE RESTRICTION: This report is produced exclusively for authorized,
defensive security purposes. It may only be used:
  • By or on behalf of the asset owner with explicit written authorization
  • In compliance with all applicable laws in the jurisdiction of use
  • For defensive, protective, or compliance purposes only

PROHIBITED USE: This report must not be used for:
  • Unauthorized access to systems or services
  • Harassment, stalking, or doxxing of individuals
  • Social engineering attacks against individuals or organizations
  • Any activity prohibited by computer crime law

The operator of this platform and the report generator accept no
liability for misuse of this information.

Authorization Reference: [investigation.authorization_statement]
Investigation ID: [investigation.id]
Generated by: [user.username] on [timestamp]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 10. Security Checklist (Pre-Production)

- [ ] `APP_SECRET_KEY` is 64 random bytes (not a password, not a phrase)
- [ ] `.env` is not committed to git
- [ ] `DEBUG=false` in production
- [ ] Nginx HTTPS-only with valid TLS certificate (Let's Encrypt)
- [ ] Security headers configured in `nginx.prod.conf`
- [ ] PostgreSQL not exposed on any external interface
- [ ] Redis not exposed on any external interface
- [ ] ChromaDB not exposed on any external interface
- [ ] Admin password changed after first login
- [ ] `pip-audit` passes with no critical vulnerabilities
- [ ] `npm audit` passes with no critical vulnerabilities
- [ ] Rate limiting tested (cannot send >5 failed logins before lockout)
- [ ] CORS tested (requests from unauthorized origins are rejected)
- [ ] Report download tested (unauthenticated request returns 401)
- [ ] Private IP target validation tested (192.168.1.1 rejected)
- [ ] All OSINT API keys are project-specific (not personal accounts)

---

## 11. Implementation Safety Notes

Critical implementation details that, if done incorrectly, produce hard-to-debug failures.

### Alembic with Async SQLAlchemy

The app uses `asyncpg` for async database access. Alembic requires a **synchronous** connection for migrations. Use two separate drivers:

```python
# alembic/env.py — CORRECT pattern

from sqlalchemy import create_engine, pool
from app.core.config import settings

# Convert asyncpg URL → psycopg2 URL for migrations ONLY
sync_database_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")

def run_migrations_online() -> None:
    connectable = create_engine(sync_database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
```

```
# requirements.txt — BOTH drivers required
asyncpg          # FastAPI app (async runtime)
psycopg2-binary  # Alembic migrations only (sync)
```

> **Do NOT** use `asyncio.run()` inside `alembic/env.py`. The "async Alembic" pattern shown in many tutorials is brittle. Use sync engine for migrations; the DB schema is identical either way.

---

### Celery Worker Pool and asyncio.run()

OSINT adapters use `async def collect()`. Celery tasks call them via `asyncio.run()`. This only works safely with the **prefork** pool — not with gevent or eventlet.

```python
# workers/celery_app.py
celery_app = Celery("raventech")
celery_app.conf.update(
    broker_url=settings.REDIS_URL,
    result_backend=settings.REDIS_URL,
    worker_pool="prefork",        # REQUIRED — do NOT use gevent or eventlet
    worker_concurrency=4,         # Tune to VPS CPU count
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
)
```

```python
# workers/osint_tasks.py — wrap async logic in asyncio.run()
@celery_app.task(bind=True, max_retries=3, name="raventech.osint.run_scan_job")
def run_scan_job(self, job_id: str) -> None:
    asyncio.run(_run_scan_job_async(job_id))   # Safe with prefork pool

async def _run_scan_job_async(job_id: str) -> None:
    async with AsyncSessionLocal() as db:
        ...  # actual async logic here
```

---

### Adapter Concurrency — asyncio.Semaphore

Never run all adapters without a semaphore. Shodan and VirusTotal detect multiple parallel requests from the same IP and may rate-limit or block you.

```python
# services/osint/orchestrator.py
MAX_CONCURRENT_ADAPTERS = 5  # Max outbound OSINT connections per scan job

async def _fan_out(adapters: list[BaseOsintAdapter], target: OsintTarget) -> list[OsintFinding]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_ADAPTERS)

    async def _run_with_limit(adapter: BaseOsintAdapter) -> OsintFinding:
        async with semaphore:
            return await adapter.collect(target)

    results = await asyncio.gather(
        *[_run_with_limit(a) for a in adapters],
        return_exceptions=True,  # Never let one failure kill the whole scan
    )
    return [r for r in results if isinstance(r, OsintFinding)]
```

---

### ChromaDB Embedded Initialization

ChromaDB runs in-process (no Docker service). Initialize once at app startup:

```python
# services/ai/rag.py — module-level singleton
import chromadb
from app.core.config import settings

# PersistentClient reads/writes from local disk path (mapped to Docker volume)
_chroma_client: chromadb.PersistentClient | None = None

def get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_DATA_PATH)
    return _chroma_client
```

The same `CHROMA_DATA_PATH` volume must be mounted in BOTH the `backend` and `celery-worker` services in `docker-compose.yml`.

---

### sentence-transformers Model Download

Bake the model into the Docker image. If downloaded at runtime, it adds 30+ seconds to the first analysis and fails entirely if the VPS has no internet access at that moment.

```dockerfile
# backend/Dockerfile — add BEFORE the CMD instruction
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
```

Load the model once at Celery worker startup, cache it as a module-level variable:

```python
# services/ai/embeddings.py
from sentence_transformers import SentenceTransformer

_model: SentenceTransformer | None = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model

def encode(text: str) -> list[float]:
    return get_model().encode(text).tolist()
```
