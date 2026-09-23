# RavenTech OSINT Desktop Private Handoff

Phase 5BN freezes the Docker-optional native desktop flow for private Windows/Linux testing. The packaged application supervises its managed PostgreSQL, native backend, and native worker and opens the embedded React UI. No artifact is published. See [NATIVE_DESKTOP_ACCEPTANCE.md](NATIVE_DESKTOP_ACCEPTANCE.md), [NATIVE_RUNTIME_SUPERVISOR.md](NATIVE_RUNTIME_SUPERVISOR.md), and [MANAGED_POSTGRESQL_RUNTIME.md](MANAGED_POSTGRESQL_RUNTIME.md).

Candidate: `5.0.0-rc6`

After an operator signs in and the backend is ready, RC6 automatically loads the
local Monitoring Center summary and performs a safe read-only refresh every 30
seconds by default. LAN discovery and TCP checks remain off unless their separate
local configuration flags and existing authorization boundaries are enabled. A
disabled optional signal is informational, not a failed platform. Portable and
installed runs use embedded frontend assets and do not need Vite or port 5173.
Distribution: private local Windows/Linux testing only
Signature: unsigned

This handoff accompanies RavenTech OSINT Desktop RC6. It does not authorize a
public upload, production deployment, signing claim, or hosted environment.
Packaged native use does not require the repository, Docker, Redis, Celery,
Python, Node/Vite, external PostgreSQL, PostgreSQL CLI tools from `PATH`,
PowerShell, Bash, or manual terminal commands. PostgreSQL remains required and
is managed locally by default. Use the separate development/Docker workflow
only when that compatibility profile is intentionally selected.

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
unsigned/local-only state, Docker optionality, managed PostgreSQL inclusion,
filenames, and checksums. Each executable includes the React production assets
and native backend, worker, and PostgreSQL runtime. No initialized database is
packaged.

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

1. Confirm Windows WebView2 Runtime, or the Linux shared-library prerequisites
   listed in the matching package manifest.
2. Verify the installer or package checksum.
3. Run `RavenTech-OSINT-Desktop-5.0.0-rc6-unsigned-setup.exe` as the current
   user and follow the NSIS prompts.
4. Launch **RavenTech OSINT Desktop** from the Start menu or open the Linux
   desktop binary from the package.
5. Wait for native runtime status to reach Ready, then open RavenTech and sign
   in. No repository path binding or manual service startup is needed.

Windows SmartScreen may warn because the installer is unsigned. Verify the
checksum and follow organizational policy. This package must not be represented
as signed or trusted by Windows.

For portable use, verify the portable manifest and launch
`RavenTech OSINT Desktop.exe` directly from the portable folder. No install or
service registration occurs.

## Smoke test

1. Launch the packaged app with Docker, Redis, and Celery unavailable; verify
   the native status stages and optional compatibility labels.
2. Confirm managed PostgreSQL, backend, worker, embedded UI, host monitoring,
   migrations, and native jobs reach Ready without repository setup.
3. Open the embedded UI, sign in, and switch English/Spanish with Vite stopped.
4. Exercise the approved demo flow, Monitoring Center, endpoint-agent
   instructions, advisory posture, and a benign report export.
5. Confirm start, stop, and restart require confirmation; verify check output is
   bounded and contains no secret.
6. Close and relaunch the desktop; confirm recovery and database persistence.
7. Complete `DESKTOP_OPERATOR_ACCEPTANCE_CHECKLIST.md` and retain the results in
   an approved private QA record, not in the artifact folder.

## Uninstall

Open **Settings > Apps > Installed apps**, select **RavenTech OSINT Desktop**,
and choose **Uninstall**. Confirm its installation directory and Start-menu
shortcut are removed. Uninstalling the shell intentionally preserves managed
PostgreSQL data and other per-user data outside the installer boundary. It also
does not modify repository files, Docker services/volumes, Redis data, reports,
or operator-created data. Review and remove retained data only under the tester's
local cleanup policy.

## What is not included

The package excludes `.env`, secrets, credentials, tokens, database dumps,
backups, generated reports, logs, initialized PostgreSQL data, Redis, Docker,
and project data. It includes the native backend, worker, and PostgreSQL runtime
resources. It also includes no signing certificate,
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

## Phase 5BA host visibility handoff

The desktop binary contains a fixed read-only native Windows metric command and no
new capability permissions. Verify that the Server tab says **Host native metrics**
when available. If unavailable, run the documented `ServerHost` helper manually;
otherwise expect **Docker container fallback**, explicitly not full host visibility.
No agent is installed, persisted, or started automatically. RC6 and all private,
unsigned distribution constraints remain unchanged.

## Phase 5BB private acceptance

On the authorized test LAN, verify the embedded Monitoring Center reports RC6,
`192.168.50.0/24`, gateway hint `192.168.50.1`, host-metric precedence, stored LAN
activity times, asset/agent coverage, and posture status. Enrollment tokens are
revealed once and entered only at the manual helper prompt. The portable/installer
artifacts do not include agents, persistence, backend services, databases, secrets,
or router integration.

## Historical Phase 5BJ source-run note (superseded)

This source-run instruction was superseded by Phases 5BK–5BM. Packaged desktop runs now contain the native backend, worker, and managed PostgreSQL runtime. PostgreSQL remains required as a supervised local runtime; Redis/Celery are compatibility-only in desktop mode. No public release or signing is implied. See `DESKTOP_NATIVE_RUNTIME.md`.

## Phase 5BL — Tauri native runtime supervision

Release desktop runs use the cross-platform Tauri supervisor for the fixed PyInstaller backend and worker. The supervisor verifies the RC6 release and native runtime profile, waits for PostgreSQL/migration/storage prerequisites before starting the worker, and reports owned versus external components. It uses bounded restart attempts and cooperative shutdown markers, and only terminates retained child processes that this desktop launched. A per-user Windows mutex or Linux file lock prevents duplicate desktop sessions from independently starting children. Backend port conflicts and external components are observation-only.

Windows portable/installer packages include Windows x86_64 backend, worker, and managed PostgreSQL resources; Linux x86_64 packaging includes equivalent runtime resources. Fresh native installs use managed PostgreSQL; existing external configurations remain supported. Redis/Celery are not required for native desktop mode, while Docker and development profiles remain supported. No OS autostart, systemd installation, updater, or automatic downloads are added. Linux WSL evidence is not clean-machine Linux acceptance.
