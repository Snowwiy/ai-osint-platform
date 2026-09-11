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

Phase 5AP added consistent RC4 naming, local distribution instructions, and a
read-only smoke checker for both ignored artifacts. At that phase, the
build-only icon remained a documented placeholder.

Phase 5AQ adds a fixed Rust launcher for five existing local scripts. Phase 5AR
adds a manually entered, canonicalized project-path preference so installed
builds can resolve those same scripts. Invalid or incomplete paths are rejected;
the fallback remains copy-only.

Phase 5AS freezes these local workflows as `5.0.0-rc5` after portable,
unsigned-installer, launcher, binding, localization, Docker, and regression QA.
Generated candidates remain ignored and unpublished.

Phase 5AT replaces the generated placeholder with an original repository-owned
shield/radar icon and adds an ignored private aggregate package with strict
checksums and provenance metadata. This is branding polish for local testing,
not public brand approval, signing, or release publication.

Phase 5AU freezes the same local-only distribution at `5.0.0-rc6` after adding
a bilingual end-user setup wizard and clearer prerequisite/firewall guidance.
The wizard performs detection and guidance only; it does not install software,
modify `.env`, reset data, or expand launcher permissions.

- complete public brand approval and any future loading treatment before a
  signed release
- review and update the pinned Tauri CLI only through a separately approved
  dependency-change process
- decide whether a future production package should serve a built frontend or
  retain the Phase 5AN separately started local frontend
- verify Phase 5AR safe Docker detection against standard and non-standard clean-machine installations
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

Do not add service autostart, configurable PowerShell/script input, database
reset, `.env` modification, remote administration, router automation, broad
filesystem access, or a generic command bridge while completing these items.

No signed installer, public release, auto-update service, hosting, deployment,
DNS, or Supabase migration is included in Phase 5AU.
