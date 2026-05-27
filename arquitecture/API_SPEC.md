# RavenTech OSINT Platform — API Specification

> **Version:** 1.0
> **Base URL:** `https://<your-vps>/api/v1`
> **Auth:** `Authorization: Bearer <access_token>` on all endpoints except `/auth/login` and `/auth/refresh`
> **Content-Type:** `application/json` for all requests
> **Auto-docs:** Available at `/docs` (Swagger UI) and `/redoc` (ReDoc) in development

---

## Authentication

### POST /auth/login

Authenticate with username + password. Returns access token and sets refresh token cookie.

**Auth:** None required

**Request:**
```json
{
  "username": "raven",
  "password": "SecurePass123!"
}
```

**Response 200:**
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "uuid",
    "username": "raven",
    "email": "raven@raventech.mx",
    "role": "admin"
  }
}
```

**Sets cookie:** `refresh_token=<token>; HttpOnly; Secure; SameSite=Strict; Max-Age=604800`

**Errors:** `401` wrong credentials | `429` rate limited (5 attempts / 15 min per IP)

---

### POST /auth/refresh

Issue a new access token using the refresh token cookie.

**Auth:** Refresh token cookie (automatic)

**Response 200:**
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Errors:** `401` invalid/expired refresh token

---

### POST /auth/logout

Revoke the refresh token (adds to Redis blocklist).

**Auth:** Bearer token

**Response 204:** No content

---

### GET /auth/me

Get the current authenticated user's profile.

**Auth:** Bearer token

**Response 200:**
```json
{
  "id": "uuid",
  "username": "raven",
  "email": "raven@raventech.mx",
  "role": "analyst",
  "is_active": true,
  "created_at": "2026-05-26T00:00:00Z",
  "last_login": "2026-05-26T10:00:00Z"
}
```

---

### PUT /auth/me/password

Change current user's password.

**Auth:** Bearer token

**Request:**
```json
{
  "current_password": "OldPass123!",
  "new_password": "NewPass456!"
}
```

**Response 204:** No content
**Errors:** `400` wrong current password | `422` password too weak

---

## Users [Admin Only]

### GET /users/

List all users (paginated).

**Auth:** Bearer token + `admin` role
**Query params:** `?skip=0&limit=50&role=analyst&is_active=true`

**Response 200:**
```json
{
  "total": 5,
  "items": [
    {
      "id": "uuid",
      "username": "analyst1",
      "email": "analyst1@raventech.mx",
      "role": "analyst",
      "is_active": true,
      "created_at": "2026-05-26T00:00:00Z",
      "last_login": null
    }
  ]
}
```

---

### POST /users/

Create a new user account.

**Auth:** Bearer token + `admin` role

**Request:**
```json
{
  "username": "analyst2",
  "email": "analyst2@raventech.mx",
  "password": "TempPass789!",
  "role": "analyst"
}
```

**Response 201:**
```json
{ "id": "uuid", "username": "analyst2", "role": "analyst" }
```

---

### GET /users/{id}

Get user details.
**Auth:** Bearer + `admin` | **Response 200:** user object | **Errors:** `404`

---

### PUT /users/{id}

Update user (role, is_active, email).
**Auth:** Bearer + `admin` | **Response 200:** updated user | **Errors:** `404`, `422`

---

### DELETE /users/{id}

Deactivate user (soft delete — sets `is_active=false`). Cannot delete self.
**Auth:** Bearer + `admin` | **Response 204** | **Errors:** `400` (self-delete), `404`

---

## Investigations

### GET /investigations/

List investigations accessible to the current user.

**Auth:** Bearer token
**Query:** `?status=active&skip=0&limit=20`

**Response 200:**
```json
{
  "total": 3,
  "items": [
    {
      "id": "uuid",
      "title": "Acme Corp External Footprint",
      "description": "Q2 2026 authorized assessment",
      "status": "active",
      "owner": { "id": "uuid", "username": "raven" },
      "target_count": 5,
      "created_at": "2026-05-26T00:00:00Z",
      "updated_at": "2026-05-26T00:00:00Z"
    }
  ]
}
```

---

### POST /investigations/

Create a new investigation. `authorization_statement` is required.

**Auth:** Bearer token

**Request:**
```json
{
  "title": "Acme Corp External Footprint",
  "description": "Authorized external footprint assessment for Q2 2026",
  "authorization_statement": "Written authorization received from Acme Corp CISO on 2026-05-20. Reference: AUTH-2026-042.",
  "scope_definition": "In scope: acme.com domain and all subdomains, IPs in ASN AS12345. Out of scope: acmepayments.com."
}
```

**Response 201:** investigation object
**Errors:** `422` (authorization_statement missing or too short)

---

### GET /investigations/{id}

Get full investigation details including members and target count.
**Auth:** Bearer + membership | **Response 200:** full investigation object | **Errors:** `403`, `404`

---

### PUT /investigations/{id}

Update title, description, status, or scope.
**Auth:** Bearer + membership (analyst or above) | **Response 200** | **Errors:** `403`, `404`

---

### DELETE /investigations/{id}

Archive the investigation (status → archived). Permanent delete requires `admin`.
**Auth:** Bearer + owner or admin | **Response 204** | **Errors:** `403`, `404`

---

### GET /investigations/{id}/members

List team members on this investigation.
**Auth:** Bearer + membership | **Response 200:** `{ "items": [ { "user": {...}, "role": "collaborator", "added_at": "..." } ] }`

---

### POST /investigations/{id}/members

Add a user to this investigation.

**Auth:** Bearer + `owner` role within investigation or `admin`

**Request:**
```json
{ "user_id": "uuid", "role": "collaborator" }
```

**Response 201:** member object | **Errors:** `404` user not found, `409` already member

---

### DELETE /investigations/{id}/members/{user_id}

Remove a member. Cannot remove the owner.
**Auth:** Bearer + owner or admin | **Response 204** | **Errors:** `400` (remove owner), `403`, `404`

---

## Targets

### GET /targets/

List targets for an investigation.

**Auth:** Bearer + investigation membership
**Query:** `?investigation_id=<uuid>&target_type=domain`

**Response 200:**
```json
{
  "total": 4,
  "items": [
    {
      "id": "uuid",
      "investigation_id": "uuid",
      "target_type": "domain",
      "target_value": "acme.com",
      "label": "Main corporate domain",
      "created_at": "2026-05-26T00:00:00Z"
    }
  ]
}
```

---

### POST /targets/

Add a target to an investigation.

**Auth:** Bearer + investigation membership

**Request:**
```json
{
  "investigation_id": "uuid",
  "target_type": "domain",
  "target_value": "acme.com",
  "label": "Main corporate domain",
  "notes": "Primary domain for all services"
}
```

**Response 201:** target object
**Errors:** `400` invalid target_type or target_value format | `409` duplicate target in investigation

**Validation rules:**
- `domain` → valid domain name (not an IP, not a private range)
- `ip` → valid IPv4/IPv6, NOT RFC1918 private ranges
- `email` → valid email format
- `username` → alphanumeric + common chars, 2–50 chars
- `org` → 2–200 chars non-empty string
- `url` → valid URL, http/https only

---

### GET /targets/{id}

Get target with latest scan job summary and finding count.
**Auth:** Bearer + investigation membership | **Response 200:** target object | **Errors:** `403`, `404`

---

### DELETE /targets/{id}

Remove a target (cascades to findings and scan_jobs).
**Auth:** Bearer + investigation owner or admin | **Response 204** | **Errors:** `403`, `404`

---

## OSINT Collection

### GET /osint/adapters

List all registered OSINT adapters, their availability (API key configured), and supported target types.

**Auth:** Bearer token

**Response 200:**
```json
{
  "adapters": [
    {
      "name": "whois_rdap",
      "display_name": "WHOIS / RDAP",
      "available": true,
      "requires_api_key": false,
      "supported_targets": ["domain", "org"]
    },
    {
      "name": "dns_crtsh",
      "display_name": "DNS + Certificate Transparency (crt.sh)",
      "available": true,
      "requires_api_key": false,
      "supported_targets": ["domain"]
    },
    {
      "name": "shodan",
      "display_name": "Shodan",
      "available": true,
      "requires_api_key": true,
      "supported_targets": ["ip", "domain"]
    },
    {
      "name": "virustotal",
      "display_name": "VirusTotal",
      "available": true,
      "requires_api_key": true,
      "supported_targets": ["domain", "ip", "url"]
    },
    {
      "name": "abuseipdb",
      "display_name": "AbuseIPDB",
      "available": false,
      "requires_api_key": true,
      "supported_targets": ["ip"],
      "unavailable_reason": "ABUSEIPDB_API_KEY not configured"
    }
  ],
  "total": 5,
  "available": 4,
  "unavailable": 1
}
```

> This endpoint lets the frontend show users exactly which sources are active before they scan. Adapters with missing API keys are listed as `available: false` with a reason — never raises an error.

---

### POST /osint/scan

Start an async OSINT scan for a target. Returns immediately with job ID.

**Auth:** Bearer token + investigation membership
**Rate limit:** 10 scans / minute per user

**Request:**
```json
{
  "target_id": "uuid",
  "adapters": ["whois_rdap", "dns_crtsh", "shodan", "virustotal"]
}
```
> Omit `adapters` to run ALL available adapters that support the target type.

**Response 202:**
```json
{
  "job_id": "uuid",
  "status": "queued",
  "target_id": "uuid",
  "adapters_requested": ["whois_rdap", "dns_crtsh", "shodan", "virustotal"],
  "message": "Scan queued. Poll /osint/jobs/{job_id} for status."
}
```

---

### GET /osint/jobs/{job_id}

Poll scan job status.

**Auth:** Bearer token + investigation membership

**Response 200:**
```json
{
  "job_id": "uuid",
  "status": "completed",
  "adapters_requested": ["shodan", "virustotal"],
  "adapters_completed": ["virustotal"],
  "adapters_failed": { "shodan": "API rate limit exceeded" },
  "finding_count": 3,
  "started_at": "2026-05-26T10:00:00Z",
  "completed_at": "2026-05-26T10:00:45Z"
}
```

**Possible statuses:** `queued` | `running` | `completed` | `partial` | `failed`

---

### GET /osint/findings/

List findings for a target (most recent first).

**Auth:** Bearer + investigation membership
**Query:** `?target_id=<uuid>&source=shodan&min_risk=50&skip=0&limit=50`

**Response 200:**
```json
{
  "total": 8,
  "items": [
    {
      "id": "uuid",
      "target_id": "uuid",
      "source": "shodan",
      "risk_score": 75,
      "confidence": "high",
      "normalized_data": {
        "open_ports": [22, 80, 443, 8080],
        "vulnerabilities": [{"cve": "CVE-2021-44228", "cvss": 10.0}]
      },
      "evidence_urls": ["https://www.shodan.io/host/1.2.3.4"],
      "collected_at": "2026-05-26T10:00:45Z"
    }
  ]
}
```

---

### GET /osint/findings/{id}

Get single finding including full raw_data.
**Auth:** Bearer + investigation membership | **Response 200:** finding with raw_data included | **Errors:** `403`, `404`

---

## AI Analysis

### POST /ai/analyze

Trigger Claude analysis for a target (uses all existing findings). Runs async.

**Auth:** Bearer token + investigation membership
**Rate limit:** 5 analysis requests / minute per user

**Request:**
```json
{
  "target_id": "uuid",
  "finding_ids": ["uuid1", "uuid2"]
}
```
> Omit `finding_ids` to analyze ALL findings for the target.

**Response 202:**
```json
{
  "analysis_id": "uuid",
  "status": "queued",
  "message": "Analysis queued. Poll /ai/analyses/{analysis_id} for result."
}
```

---

### GET /ai/analyses/

List AI analyses for a target.

**Auth:** Bearer + investigation membership
**Query:** `?target_id=<uuid>&skip=0&limit=10`

**Response 200:**
```json
{
  "total": 2,
  "items": [
    {
      "id": "uuid",
      "target_id": "uuid",
      "risk_assessment": "high",
      "analysis_text": "The target exhibits multiple indicators of security misconfiguration...",
      "framework_mappings": {
        "mitre": [{"id": "T1190", "name": "Exploit Public-Facing Application", "relevance": "Open port 8080 running vulnerable Tomcat version"}],
        "owasp": [{"id": "A05:2025", "name": "Security Misconfiguration", "relevance": "Default credentials and outdated software detected"}],
        "nist": [{"function": "ID.AM", "description": "Asset inventory gaps identified"}],
        "iso": [{"control": "8.8", "description": "Management of technical vulnerabilities required"}]
      },
      "recommendations": [
        {"priority": "critical", "action": "Immediately patch CVE-2021-44228 on port 8080 service", "framework_ref": "T1190"},
        {"priority": "high", "action": "Disable port 8080 if not required for business operations", "framework_ref": "A05:2025"}
      ],
      "model_used": "claude-3-5-sonnet-20241022",
      "created_at": "2026-05-26T10:01:00Z"
    }
  ]
}
```

---

### GET /ai/analyses/{id}

Get full analysis including rag_sources and token usage.
**Auth:** Bearer + investigation membership | **Response 200:** full analysis object | **Errors:** `403`, `404`

---

## Reports

### POST /reports/generate

Generate an HTML report for an investigation. Runs async.
**v1.0 note:** Only `"html"` format is supported. PDF generation (WeasyPrint) is deferred to v1.1. Report configuration options (`config`) are also deferred to v1.1 — the full report is always generated in v1.0.

**Auth:** Bearer + investigation membership

**Request:**
```json
{
  "investigation_id": "uuid",
  "title": "Acme Corp External Footprint Report — Q2 2026",
  "format": "html"
}
```

**Response 202:**
```json
{
  "report_id": "uuid",
  "status": "pending",
  "message": "Report generation queued. Poll /reports/{report_id} for status."
}
```

---

### GET /reports/

List reports for an investigation.

**Auth:** Bearer + investigation membership
**Query:** `?investigation_id=<uuid>&status=ready&skip=0&limit=20`

**Response 200:** paginated list of report objects

---

### GET /reports/{id}

Get report metadata and status.

**Auth:** Bearer + investigation membership

**Response 200:**
```json
{
  "id": "uuid",
  "investigation_id": "uuid",
  "title": "Acme Corp External Footprint Report — Q2 2026",
  "format": "html",
  "status": "ready",
  "file_size_bytes": 245000,
  "created_at": "2026-05-26T10:05:00Z",
  "generated_by": { "id": "uuid", "username": "raven" }
}
```

---

### GET /reports/{id}/download

Stream report file download. Only available when status = `ready`.

**Auth:** Bearer + investigation membership
**Response 200:** Binary file stream
**Headers:** `Content-Type: text/html`, `Content-Disposition: attachment; filename="report.html"`
**Errors:** `409` (report not ready yet), `403`, `404`

---

## Audit Logs [Admin Only]

### GET /audit/logs

Query audit logs with filters.

**Auth:** Bearer + `admin` role
**Query:** `?user_id=<uuid>&action=auth.login&resource_type=investigation&from=2026-05-01&to=2026-05-26&skip=0&limit=100`

**Response 200:**
```json
{
  "total": 1250,
  "items": [
    {
      "id": 42,
      "user": { "id": "uuid", "username": "raven" },
      "action": "osint.scan_started",
      "resource_type": "scan_job",
      "resource_id": "uuid",
      "ip_address": "1.2.3.4",
      "details": { "target_id": "uuid", "adapters": ["shodan"] },
      "timestamp": "2026-05-26T10:00:00Z"
    }
  ]
}
```

---

## Admin

### GET /admin/health

System health check (public endpoint for Docker HEALTHCHECK).

**Auth:** None

**Response 200:**
```json
{
  "status": "healthy",
  "database": "ok",
  "redis": "ok",
  "chroma": "ok",
  "timestamp": "2026-05-26T10:00:00Z"
}
```

---

### GET /admin/stats

Platform usage statistics.

**Auth:** Bearer + `admin` role

**Response 200:**
```json
{
  "users": { "total": 5, "active": 4 },
  "investigations": { "total": 12, "active": 3 },
  "targets": { "total": 47 },
  "findings": { "total": 1850 },
  "scans": { "total": 95, "last_24h": 8 },
  "ai_analyses": { "total": 42, "tokens_used": 85000 },
  "reports": { "total": 15, "ready": 14 }
}
```

---

<!-- API key management (POST/GET/DELETE /admin/api-keys) is DEFERRED TO v1.1.
     In v1.0, long-lived JWTs serve as programmatic access tokens.
     The full API key table and endpoints will be added in v1.1. -->

---

## Error Response Schema

All errors follow this format:

```json
{
  "detail": "Human-readable error message",
  "code": "MACHINE_READABLE_CODE",
  "timestamp": "2026-05-26T10:00:00Z"
}
```

| HTTP Status | When used |
|-------------|-----------|
| `400` | Invalid request (bad input, business rule violation) |
| `401` | Missing or invalid auth token |
| `403` | Valid token but insufficient permissions |
| `404` | Resource not found |
| `409` | Conflict (duplicate, wrong state) |
| `422` | Validation error (Pydantic) |
| `429` | Rate limit exceeded |
| `500` | Unexpected server error (never exposes internal details in prod) |

---

## Rate Limits

| Endpoint group | Limit | Window |
|---------------|-------|--------|
| POST /auth/login | 5 requests | per IP, 15 minutes |
| POST /osint/scan | 10 requests | per user, 1 minute |
| POST /ai/analyze | 5 requests | per user, 1 minute |
| POST /reports/generate | 3 requests | per user, 5 minutes |
| All other endpoints | 120 requests | per user, 1 minute |

Rate limit headers returned on every response:
```
X-RateLimit-Limit: 120
X-RateLimit-Remaining: 118
X-RateLimit-Reset: 1748260800
```
