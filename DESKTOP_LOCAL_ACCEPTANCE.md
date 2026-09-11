# RavenTech OSINT Desktop RC6 Local Acceptance

Candidate: `5.0.0-rc6`

This acceptance applies only to the local Windows portable and unsigned NSIS
installer workflows. It is not approval for public distribution or production
deployment.

Phase 5AV adds the final private handoff set: `OPERATOR_MANUAL.md`,
`DESKTOP_PRIVATE_HANDOFF.md`, and
`DESKTOP_OPERATOR_ACCEPTANCE_CHECKLIST.md`. Complete the operator checklist on
an authorized Windows host and retain the result in a private QA record.

Phase 5AT adds the ignored aggregate package at
`desktop/dist-local-release/RavenTech-OSINT-Desktop-5.0.0-rc6/`. It combines
only the validated portable executable, unsigned installer, local instructions,
known limitations, checksums, and provenance manifest. The package must pass
`npm run local-release:validate -- --require-artifact`.

## Prerequisites

- Windows with WebView2 Runtime
- Docker Desktop, Docker Compose, and the existing RavenTech repository
- local Docker services and Vite frontend when testing the embedded application
- ports 8000 and 5173 available for the RavenTech services

## RC6 setup-wizard acceptance

1. Confirm the bilingual Project, Prerequisites, and Local services stages show
   complete or needs-action states without exposing raw errors.
2. Reject an empty, missing, or incomplete project path and retain copy-only mode.
3. Confirm Docker unavailable/not-running guidance never installs or starts it
   automatically and the next recommended action remains explicit.
4. Confirm ports 8000/5173, release mismatch, migrations, backend/frontend, and
   Windows firewall guidance remain readable in English and Spanish.
5. Confirm portable and installed wording explains that the same validated path
   is used and that installed mode normally requires one-time binding.

## Portable acceptance

1. Build with `npm run portable:build` from `desktop/`.
2. Confirm the ignored output is
   `desktop/dist-portable/RavenTech-OSINT-Desktop-5.0.0-rc6/`.
3. Validate the four-file allowlist and SHA-256 manifest.
4. Launch from the portable folder, confirm the local status screen, bind the
   repository path, and verify healthy/offline guidance and embedded frontend.
5. Confirm English/Spanish switching and copy-only fallback behavior.

## Installer acceptance

1. Build with `npm run installer:build`; signing remains disabled.
2. Confirm the ignored output is
   `desktop/dist-installer/RavenTech-OSINT-Desktop-5.0.0-rc6/`.
3. Verify the manifest, then install for the current user on the authorized QA host.
4. Launch outside repository ancestry, bind the repository, and confirm the
   same status, localization, launcher, and fallback behavior as portable mode.
5. Uninstall through the generated uninstaller and confirm the install directory
   and RavenTech Start Menu shortcut are removed.

## Launcher and workflow acceptance

- only `start_platform.ps1`, `stop_platform.ps1`, `restart_platform.ps1`,
  `check_platform.ps1`, and `open_platform.ps1` can execute
- altered or missing approved scripts force copy-only fallback
- start, stop, and restart require explicit confirmation
- output is bounded and sanitized; `.env` values and secrets are never returned
- no reset, destructive operation, dynamic command, argument, or script path exists
- monitoring, recon, and report regressions are covered by the existing backend
  and frontend suites; no real scan is run for RC6 acceptance

## Required evidence

- Ruff, mypy, pytest, pip check, and Alembic check
- `/health`, `/health/ready`, and `/api/v1/release` with RC6 identity
- frontend build and localization tests
- desktop validation, Cargo tests/check, PowerShell syntax checks
- portable and installer builds/validators plus artifact-aware desktop smoke
- real portable and installed process launch and clean uninstall
- branded icon source and generated Windows icon assets
- strict local-release file allowlist, SHA-256 list, build time, and Git commit
- completed private operator acceptance checklist with no credentials, secrets,
  tokens, `.env` values, or report contents

If any required gate fails, do not commit, push, or tag. Generated artifacts
remain Git-ignored and local. No signing, public release, updater, hosting,
deployment, DNS, Supabase migration, router automation, remote/arbitrary shell,
or offensive functionality is accepted by this document.
