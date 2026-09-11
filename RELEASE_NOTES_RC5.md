# RavenTech OSINT 5.0.0-rc5

## Desktop-local candidate

RC5 freezes the existing RavenTech local web platform and its Tauri desktop
wrapper after portable, unsigned-installer, first-run binding, controlled
launcher, localization, and local Docker regression QA. It adds no product
module, database migration, hosted service, or offensive capability.

## Included local workflows

- unchanged FastAPI, React/Vite, PostgreSQL, Redis, Celery, and Docker Compose
  architecture with browser mode retained
- RavenTech OSINT Desktop portable local-test build
- unsigned, current-user NSIS installer for local testing
- manual first-run repository binding with canonical marker and build-pinned
  five-script validation
- controlled start, stop, restart, check, and open-frontend actions with
  confirmation, timeout, sanitization, and copy-only fallback
- English and Spanish desktop status, setup, prerequisite, and recovery copy
- SHA-256 manifests and strict four-file portable/installer package allowlists

## RC5 identity

- application and desktop version: `5.0.0-rc5`
- tag after the complete acceptance gate: `v5.0.0-rc5`
- migration head remains `0036_phase5ai_posture`; RC5 adds no migration

## Distribution boundary

RC5 is a local distribution candidate, not a public release. The installer and
portable executable are unsigned, Git-ignored, and not published. Docker,
PostgreSQL, Redis, FastAPI, Celery, Vite, WebView2, the repository, and local
configuration remain separate prerequisites. No backend, database, Docker
runtime, secret, backup, report, or log is bundled.

There is no signing certificate, auto-update, hosting, deployment, DNS change,
Supabase migration, router automation, arbitrary or remote command execution,
scanning expansion, exploitation, or offensive functionality in RC5.

## QA note

Deterministic source, backend, frontend, localization, Rust, PowerShell,
portable, installer, manifest, checksum, and process-lifecycle checks form the
release gate. Graphical Computer Use automation may be recorded as unavailable
when its trusted local RPC service is not configured; that limitation must not
be represented as a completed visual click-through.
