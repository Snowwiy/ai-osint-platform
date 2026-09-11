# Desktop Distribution Checklist

Phases 5AO–5AT prepare and validate local, unsigned Windows installer, portable,
and private aggregate-package testing only. Public release remains deferred
until signing, clean-machine QA, brand approval, and release approval are complete.

## Phase 5AT local release package

- [ ] Confirm the product, window, portable executable, installer, and RC6
      labels consistently use **RavenTech OSINT Desktop**.
- [ ] Confirm the repository-owned SVG and generated Windows ICO/PNG assets are
      present and both Tauri bundle configurations use `icons/icon.ico`.
- [ ] Run `npm run local-release:package` only after portable and installer
      validation passes.
- [ ] Run `npm run local-release:validate -- --require-artifact` and confirm the
      seven-file allowlist, PE headers, checksums, commit, and build-time metadata.
- [ ] Confirm `desktop/dist-local-release/` is ignored and contains no `.env`,
      secrets, databases, backups, reports, logs, credentials, tokens, backend,
      PostgreSQL, Redis, or Docker runtime.

## Phase 5AU RC6 setup gate

- [ ] Verify the three bilingual wizard stages and next-action guidance for
      valid, invalid, offline, degraded, and ready states.
- [ ] Verify Docker missing/not-running, ports 8000/5173, release mismatch,
      migration, frontend/backend, and Windows firewall guidance.
- [ ] Confirm portable and installed flows use only manual validated path binding.
- [ ] Rebuild and validate RC6 portable, unsigned installer, and aggregate package.

## Portable build

- [ ] Run `npm run portable:build` from `desktop/` on Windows.
- [ ] Run `npm run portable:validate` and confirm the four-file allowlist.
- [ ] Verify SHA-256 values in `portable-manifest.json`.
- [ ] Confirm the portable executable starts without installing services.

## Unsigned installer build

- [ ] Run `npm ci --offline` in `desktop/` with the pinned lockfile available.
- [ ] Run `npm run installer:build` and keep output under ignored `dist-installer/`.
- [ ] Run `npm run installer:validate -- --require-artifact`.
- [ ] Confirm the filename and RC6 metadata describe an unsigned local-test build.
- [ ] Confirm current-user install, Start-menu launch, and Settings-app uninstall.
- [ ] Confirm Windows SmartScreen identifies the installer as unsigned/untrusted.
- [ ] Confirm the installed shell launches to **RavenTech OSINT Desktop — Local Workspace**.

## Content and security gate

- [ ] Confirm the package allowlist contains only setup EXE, README, LICENSE, and manifest.
- [ ] Secret-scan source and collected files; reject `.env`, credentials, keys, tokens,
      certificates, database dumps, backups, reports, and local logs.
- [ ] Independently verify every SHA-256 checksum after transfer.
- [ ] Confirm Tauri grants no shell/filesystem plugin permissions or remote origins.
- [ ] Confirm every launcher action retains a copy-only fallback.
- [ ] Confirm runtime execution is limited to five argument-free launcher actions
      and canonical, build-pinned `scripts/local/` script filenames.
- [ ] Confirm start, stop, and restart require explicit confirmation; cancel
      each dialog once and verify no action runs.
- [ ] Confirm installed builds accept only a manually entered path that passes all
      fixed repository and script-content checks; invalid paths remain copy-only.
- [ ] Confirm launcher output is capped/redacted and timeouts show a clean state.
- [ ] Confirm no service autostart, updater, embedded database, or backend is present.
- [ ] Run `npm run smoke -- --require-artifacts` and retain the console result
      with the local QA record; do not add binaries to Git.

## Local operator QA

- [ ] Start the existing Docker/local workflow before launching the desktop shell.
- [ ] Verify `http://localhost:8000/health` and `/health/ready` are readable.
- [ ] Verify `/api/v1/release` reports `5.0.0-rc6`.
- [ ] Test frontend embed at `http://localhost:5173` and offline help fallback.
- [ ] Export one benign report and confirm existing browser behavior is unchanged.
- [ ] Switch desktop help and web UI between English and Spanish.
- [ ] Confirm the repository-owned local-candidate icon is visible and is not
      represented as signed or approved public-release branding.
- [ ] Test install, upgrade rejection/downgrade protection, and clean uninstall locally.
- [ ] Review any Windows Firewall prompt: the shell needs loopback access only; do not
      approve public-network exposure for backend or frontend ports.

## Before any future public release

- [ ] Obtain and protect an approved code-signing certificate.
- [ ] Sign binaries and installer, timestamp them, and verify signatures independently.
- [ ] Complete malware scanning, clean-machine matrix QA, legal review, and release approval.
- [ ] Design an authenticated update channel separately; auto-update is not present.
- [ ] Keep public upload, release notes, hosting, deployment, and DNS changes deferred.
