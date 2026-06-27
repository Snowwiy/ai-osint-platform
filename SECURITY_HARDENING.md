# RavenTech OSINT Security Hardening

RavenTech OSINT is a defensive investigation workspace. This guide focuses on
safe internal operation, governance, and supportability.

## Secret Management

- Never commit `.env`.
- Use strong `APP_SECRET_KEY` or `SECRET_KEY` values.
- Rotate provider keys outside the application repository.
- Keep API keys out of frontend builds.
- Use the Operations Center environment validation to confirm presence without
  displaying values.

## Environment Separation

Use separate configuration for:

- Development
- Staging
- Production-style operation

Production-style operation should use:

- Strict CORS origins
- Non-development signing keys
- Persistent database and report volumes
- Restricted access to Docker host and volumes

## RBAC

Preserve backend enforcement:

- Platform admin: administrative controls
- Investigation owner: governance control for owned cases
- Investigation admin: case management
- Analyst: investigation contribution
- Viewer: read-only

Frontend visibility is convenience only. Backend checks are the security boundary.

## Governance Controls

Review Admin Settings for:

- Data retention metadata
- Export controls
- Audit policy
- Report branding
- Feature flags

Disabled features should return clean errors and hide UI actions where possible.

## Audit Practices

Review audit logs for:

- Login failures
- Permission denials
- Governance changes
- Feature flag changes
- Backup exports
- Restore validations
- Report downloads
- Member and ownership changes

Do not log secrets in audit metadata.

## Backup Controls

- Store backup exports in approved internal locations.
- Treat backups as sensitive operational data.
- Validate backups with dry-run restore before upgrades.
- Use PostgreSQL-native backup for authoritative recovery.

## Logging

Logs should include:

- Request ID
- Endpoint
- User context where safe
- Failure reason

Logs should not include:

- Passwords
- API keys
- JWTs
- Refresh tokens
- Raw `.env` values

## Network Exposure

- Keep PostgreSQL and Redis internal to Docker networking where possible.
- Expose the backend only through approved internal routes.
- Restrict frontend CORS to known origins.
- Do not add active scanning or offensive capabilities.

## Operational Review

Before release:

1. Confirm `/health/ready`.
2. Confirm `GET /api/v1/release`.
3. Confirm Admin → Operations.
4. Export diagnostics.
5. Export a backup.
6. Validate backup dry-run.
7. Review audit logs.
8. Confirm report downloads.
9. Confirm feature flags and export controls.
10. Confirm demo mode remains disabled in production-style environments.
