# RavenTech OSINT Desktop Private Handoff

Candidate: `5.0.0-rc6`

After an operator signs in and the backend is ready, RC6 automatically loads the
local Monitoring Center summary and performs a safe read-only refresh every 30
seconds by default. LAN discovery and TCP checks remain off unless their separate
local configuration flags and existing authorization boundaries are enabled. A
disabled optional signal is informational, not a failed platform. Portable and
installed runs use embedded frontend assets and do not need Vite or port 5173.
Distribution: private local Windows testing only
Signature: unsigned

This handoff accompanies RavenTech OSINT Desktop RC6. It does not authorize a
public upload, production deployment, signing claim, or hosted environment.
For a new checkout, complete `FRESH_SETUP_CHECKLIST.md` before this handoff's
artifact and receiving-host steps.
On the receiving Windows machine, use `EXTERNAL_MACHINE_TEST_CHECKLIST.md` for
prerequisites, transfer integrity, project setup, recovery, and uninstall QA.

## Artifact locations

Generated files are local and Git-ignored:

- portable package:
  `desktop/dist-portable/RavenTech-OSINT-Desktop-5.0.0-rc6/`
- unsigned installer:
  `desktop/dist-installer/RavenTech-OSINT-Desktop-5.0.0-rc6/`
- combined private package:
  `desktop/dist-local-release/RavenTech-OSINT-Desktop-5.0.0-rc6/`

The combined package contains exactly:

- `RavenTech OSINT Desktop.exe`
- `RavenTech-OSINT-Desktop-5.0.0-rc6-unsigned-setup.exe`
- `README.md`
- `LOCAL_STARTUP_INSTRUCTIONS.md`
- `KNOWN_LIMITATIONS.md`
- `SHA256SUMS.txt`
- `local-release-manifest.json`

Portable and installer subpackages contain their own manifest and SHA-256
metadata. The combined manifest records the source commit, UTC build time,
unsigned/local-only state, Docker requirement, filenames, and checksums.
Each executable includes the React production assets. Neither portable nor
installed use requires Vite or port 5173; the backend remains external.

## Verify before transfer

From `desktop/`, run:

```powershell
npm run portable:validate
npm run installer:validate -- --require-artifact
npm run local-release:validate -- --require-artifact
npm run smoke -- --require-artifacts
```

Compare each combined-package payload with `SHA256SUMS.txt`, and confirm the
commit in `local-release-manifest.json` is the intended handoff commit. Transfer
only the combined package through an approved private channel. Never add its
binaries to Git.

## Install and launch

1. Confirm Windows WebView2 Runtime and Docker Desktop are installed.
2. Keep the RavenTech repository and its reviewed local `.env` outside the
   distribution package.
3. Verify the installer checksum.
4. Run `RavenTech-OSINT-Desktop-5.0.0-rc6-unsigned-setup.exe` as the current
   user and follow the NSIS prompts.
5. Launch **RavenTech OSINT Desktop** from the Start menu.
6. Bind the repository root in the first-run Project stage.
7. Start Docker/backend services using the approved flow in
   `OPERATOR_MANUAL.md`. Start Vite only for optional browser/development QA.

Windows SmartScreen may warn because the installer is unsigned. Verify the
checksum and follow organizational policy. This package must not be represented
as signed or trusted by Windows.

For portable use, verify the portable manifest and launch
`RavenTech OSINT Desktop.exe` directly from the portable folder. No install or
service registration occurs.

## Smoke test

1. Open the shell and verify the three-stage English/Spanish setup screen.
2. Reject an invalid path, bind the valid repository root, and verify scripts.
3. With services offline, verify clear Docker/backend/frontend guidance and
   copy-only fallback.
4. Start the existing local platform; verify `/health`, `/health/ready`, and
   `/api/v1/release` report a ready RC6 service.
5. Open the embedded UI, sign in, and switch English/Spanish.
   Confirm the status reads **Frontend: Embedded** with Vite stopped.
6. Exercise the approved demo flow, Monitoring Center, endpoint-agent
   instructions, advisory posture, and a benign report export.
7. Confirm start, stop, and restart require confirmation; verify check output is
   bounded and contains no secret.
8. Restart services and confirm recovery, then stop them cleanly.
9. Complete `DESKTOP_OPERATOR_ACCEPTANCE_CHECKLIST.md` and retain the results in
   an approved private QA record, not in the artifact folder.

## Uninstall

Open **Settings > Apps > Installed apps**, select **RavenTech OSINT Desktop**,
and choose **Uninstall**. Confirm its installation directory and Start-menu
shortcut are removed. Uninstalling the shell intentionally leaves the repository,
Docker services/volumes, database, Redis data, reports, saved project-path
preference, and operator-created data outside the installer boundary. Review and
remove any per-user preference only under the tester's local cleanup policy.

## What is not included

The package excludes `.env`, secrets, credentials, tokens, database dumps,
backups, generated reports, logs, source credentials, the backend, PostgreSQL,
Redis, Docker, and project data. It also includes no signing certificate,
auto-updater, service autostart, public release integration, hosting, deployment,
DNS, Supabase migration, router automation, arbitrary/remote command execution,
remote administration, new scanning, or offensive functionality.

Signing, timestamping, public brand approval, clean-machine release-matrix QA,
public distribution, and production support remain deferred.

For Phase 5AZ private LAN acceptance, bind the repository, sign in as an
administrator, and run the Activation bootstrap using `192.168.50.1/24`.
Confirm `192.168.50.0/24`, gateway hint `192.168.50.1`, RC6, and zero discovery
or service-check executions in the verification result. The desktop never edits
`.env`; enrollment and restart commands remain copy-only/manual.
