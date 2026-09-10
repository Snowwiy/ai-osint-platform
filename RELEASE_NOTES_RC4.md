# RavenTech OSINT 5.0.0-rc4

## Summary

RC4 freezes the completed local web platform with professional English/Spanish
localization. The release remains local Docker validated and preserves the RC3
and Phase 5AI security boundaries.

## Changes since RC3

- Added endpoint posture and deterministic manual remediation recommendations
- Added an English/Spanish language switcher on sign-in and authenticated UI
- Persisted language locally with English default and missing-copy fallback
- Localized major navigation, workflows, statuses, severities, loading/empty/
  error states, monitoring/recon terminology, and common actions
- Added independent English/Spanish report language selection
- Preserved PDF, DOCX, HTML, and Markdown report exports
- Corrected visible empty-state copy regressions discovered during freeze QA
- Bumped release metadata to `5.0.0-rc4`

## Security posture

Localization contains no secrets and changes no authorization decision. Logs
and audit action identifiers remain stable. Reports store only the `en`/`es`
language code. Monitoring stays authorized/local and TCP-connect only; posture
and baseline output remains advisory with no exploit validation.

## Validation proof

- Ruff: passed
- Strict mypy: passed across 217 backend source files
- Pytest: 279 passed
- Frontend localization contract tests: 3 passed
- Frontend TypeScript/Vite production build: passed
- `pip check`: passed
- Alembic: current/head `0036_phase5ai_posture`, no schema drift
- `/health` and `/health/ready`: healthy
- `/api/v1/release`: `5.0.0-rc4`

The only test warning is the documented upstream Passlib/Python `crypt`
deprecation. No Phase 5AJ schema migration was introduced.

## Known limitations

- Some uncommon or evidence/provider-generated prose may use the English
  fallback; raw translation keys are never shown.
- Docker may not expose host LAN neighbors and optional agent telemetry may be
  absent without degrading healthy required services.
- Optional recon providers can fail while valid stored entities remain usable.
- The upstream Passlib/Python `crypt` deprecation warning remains non-blocking.

## Deferred status

Desktop packaging, Electron, Tauri, installers, hosting, deployment, DNS, and
Supabase migration remain deferred. RC4 is not a hosted production release.
