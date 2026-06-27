# Production Hardening

Phase 4A hardens the platform for defensive internal enterprise use.

## Security Headers

API responses include:

- `Content-Security-Policy`
- `Strict-Transport-Security` in production
- `X-Frame-Options`
- `X-Content-Type-Options`
- `Referrer-Policy`
- `X-Request-ID`

## API Error Shape

Errors include the legacy `detail` field plus a structured envelope:

```json
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Resource not found.",
    "detail": "Investigation not found",
    "request_id": "..."
  }
}
```

## Authentication Protection

Login attempts are rate-limited with Redis-backed failure counters. Repeated
failures produce `429` responses and audit events without exposing secrets.

## Configuration Validation

Startup validates required operational settings. Production rejects placeholder
secrets and wildcard CORS origins.

## Logging

Backend logs are JSON formatted and include request correlation IDs. Sensitive
fields such as tokens, secrets, passwords, cookies, and API keys are redacted.

## Database Safety

The async database engine uses:

- `pool_pre_ping`
- statement timeout
- pool recycling
- transaction rollback on exceptions

Readiness checks compare the current Alembic revision to the migration head.

## Worker Reliability

Celery runs with prefork, late acknowledgements, prefetch `1`, retry backoff,
task time limits, worker loss rejection, and task recycling.
