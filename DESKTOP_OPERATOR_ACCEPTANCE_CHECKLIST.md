# RavenTech OSINT Desktop Operator Acceptance Checklist

Candidate: `5.0.0-rc6`
Scope: private, unsigned local Windows acceptance only

Record the tester, Windows version, test date, source commit, and artifact
checksums in the approved private QA record. Do not record passwords, invite
codes, tokens, `.env` values, or report contents here.

## Artifact and install

- [ ] Verify the local-release manifest identifies `5.0.0-rc6`, the intended
      source commit, `signed: false`, `localOnly: true`, and Docker required.
- [ ] Verify both SHA-256 checksums before running either binary.
- [ ] Confirm the portable, installer, and aggregate output directories are
      ignored by Git and contain no forbidden files.
- [ ] Install the unsigned current-user app and record the expected SmartScreen
      warning without claiming the package is trusted or signed.
- [ ] Open **RavenTech OSINT Desktop** from the Start menu.

## First run and local services

- [ ] Verify an empty, missing, or incomplete project path is rejected safely.
- [ ] Configure the valid repository root and confirm all expected markers and
      six approved scripts pass validation.
- [ ] Verify Docker availability/running state and ports 8000/5173 are reported.
- [ ] Start services only after accepting the confirmation dialog.
- [ ] Verify backend health and readiness are ready and the frontend is reachable.
- [ ] Verify `/api/v1/release` reports exactly `5.0.0-rc6`.
- [ ] Confirm the embedded UI opens; also confirm browser mode still works.
- [ ] Verify offline/degraded guidance and the copy-only fallback are readable.

## Operator workflow

- [ ] Log in with an authorized account; verify invalid login fails cleanly.
- [ ] If registration is enabled for this test, register a non-admin account and
      complete the configured approval flow. Do not record credentials.
- [ ] Switch the setup screen and web UI between English and Spanish and verify
      the selected web language survives refresh.
- [ ] Run the documented synthetic demo flow only; perform no real scanning.
- [ ] Open Monitoring Center and review local service/system/asset status.
- [ ] Review authorized LAN monitoring state and run a TCP service check only if
      the private asset, feature flags, and authorization gates are approved.
- [ ] Review endpoint-agent instructions and confirm they advertise no
      persistence, remote shell, credential collection, or autostart.
- [ ] Run or review an endpoint posture assessment from stored approved data and
      verify recommendations remain manual/advisory.
- [ ] Generate, review, and export one benign report in an approved format; keep
      the output outside the desktop distribution folders.
- [ ] Stop services only after accepting confirmation, then restart and verify
      the platform returns to ready.
- [ ] Verify only start, stop, restart, check, and open-frontend launchers are
      available and altered/missing scripts force copy-only mode.

## Portable and uninstall

- [ ] Launch the portable executable directly and repeat path binding, offline,
      ready, localization, and copy-only checks.
- [ ] Uninstall the installed shell through Windows Settings.
- [ ] Confirm the application directory and Start-menu shortcut are removed.
- [ ] Confirm uninstall does not delete the repository, Docker data, database,
      Redis data, reports, or other operator-owned local data.
- [ ] Confirm no unexpected service, scheduled task, updater, or public-network
      listener was installed.

## Acceptance decision

- [ ] All required checks passed, or every exception is documented with owner,
      risk, evidence, and follow-up date in the private QA record.
- [ ] The tester acknowledges this is an unsigned private RC6 candidate, not a
      public or production release.
- [ ] No public release, signing, hosting, deployment, DNS, Supabase migration,
      router automation, arbitrary/remote command execution, or offensive
      functionality was introduced or accepted.
