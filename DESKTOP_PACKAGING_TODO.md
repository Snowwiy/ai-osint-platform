# Desktop Packaging TODO

The Phase 5AL Tauri shell is a source prototype only. Its local status screen,
fixed health bridge, and existing-frontend wrapper are complete; every item
below remains deferred to a separately reviewed packaging phase.

- select final icons, product metadata, and loading treatment
- install and pin an approved Tauri CLI toolchain with a reproducible lockfile
- decide whether a production package should serve a built frontend or retain a
  separately started local frontend
- define explicit Docker Desktop dependency detection and operator support flow
- validate WebView2 availability and supported Windows versions
- produce and test a Windows bundle, installer, upgrade, and clean uninstall
- define local app data paths without moving PostgreSQL or Redis into the shell
- arrange code signing only after release governance approval
- test backup/restore and failure recovery on a clean Windows machine
- assess opt-in, signed update checks in a later security review
- repeat CSP, capability, secret, and dependency audits before packaging

Do not add automatic Docker/PowerShell execution, database reset, `.env`
modification, remote administration, router automation, broad filesystem
access, or a generic command bridge while completing these items.

No installer, executable bundle, auto-update service, hosting, deployment, DNS,
or Supabase migration is included in Phase 5AL.
