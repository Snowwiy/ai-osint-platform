# Desktop Packaging TODO

The Phase 5AL Tauri shell, with Phase 5AM local runtime polish, is a source
prototype only. Its local status screen, fixed health bridge, constrained
existing-frontend wrapper, and safety checks are complete; every item below
remains deferred to a separately reviewed packaging phase.

Phase 5AN proves an unsigned Windows portable local-test build can be produced
without enabling Tauri bundling. The allowlisted folder contains only the
executable, operator README, license, and checksum manifest. This does not
complete installer, signing, distribution, or support readiness.

Phase 5AO prepares and locally exercises an unsigned NSIS current-user installer
using an isolated Tauri override. Its collected output is also allowlisted and
ignored. It is not signed, trusted, published, self-contained, or approved for
production distribution.

- select final icons, product metadata, and loading treatment
- review and update the pinned Tauri CLI only through a separately approved
  dependency-change process
- decide whether a future production package should serve a built frontend or
  retain the Phase 5AN separately started local frontend
- define explicit Docker Desktop dependency detection and operator support flow
- validate WebView2 availability and supported Windows versions
- complete a clean-machine install, launch, upgrade, and uninstall test matrix
- define local app data paths without moving PostgreSQL or Redis into the shell
- arrange code signing only after release governance approval
- test backup/restore and failure recovery on a clean Windows machine
- assess opt-in, signed update checks in a later security review
- repeat CSP, capability, secret, and dependency audits before packaging
- perform signed installer validation only after this source prototype passes
  operator QA on a clean Windows test machine
- decide future artifact retention, provenance, SBOM, and release-attestation
  policy before any public distribution

Do not add automatic Docker/PowerShell execution, database reset, `.env`
modification, remote administration, router automation, broad filesystem
access, or a generic command bridge while completing these items.

No signed installer, public release, auto-update service, hosting, deployment,
DNS, or Supabase migration is included in Phase 5AO.
