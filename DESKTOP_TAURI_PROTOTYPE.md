# RavenTech OSINT Tauri Desktop Prototype

Phase 5AL adds a source-level Tauri v2 shell around the existing local web
platform. It is a prototype, not an installer or a production package. Browser
mode remains supported and is still the reference workflow.

Phase 5AM polishes that prototype for local runtime QA. It separates network
reachability from healthy/readiness state, gives service-specific recovery
guidance, constrains embedded navigation, and adds automated safety checks.

Phase 5AN adds a Windows portable-build workflow for local testing. It compiles
the same shell as a standalone executable and collects it with instructions,
the repository license, and a checksum manifest. It is not an installer or a
public release package.

Phase 5AO adds a separate, pinned Tauri CLI workflow for an unsigned NSIS
current-user installer. The installer is a local-test wrapper for the same
shell; it does not bundle or start the backend, frontend, Docker, PostgreSQL,
or Redis and it is not a public release.

Phase 5AP polishes the local distribution identity and adds an artifact-aware
smoke check. The window title is **RavenTech OSINT Desktop — Local Workspace**;
the product, portable folder, and installer names remain aligned to the current candidate.

Phase 5AQ adds a controlled local launcher for the five existing platform
scripts. Start, stop, and restart require an explicit confirmation. Check and
open-frontend actions run directly. No command text, arguments, or paths are
accepted from the UI.

Phase 5AR adds first-run project binding without expanding Tauri capabilities.
The path is typed manually and accepted only after canonical validation of the
compose file, Python/desktop/frontend markers, `backend/app/`, and every approved
launcher script with its build-pinned contents. Only the canonical path is stored in the per-user app-config
directory; `.env` and repository contents are not copied or read for setup.
Resolution order is saved path, current-directory ancestry, development
executable ancestry, then copy-only fallback. Docker is detected with safe local
signals and is never installed or started by the prerequisite check.
For an approved launch, Rust passes only the already validated canonical root
through `RAVENTECH_VALIDATED_PROJECT_ROOT`. The start script revalidates fixed
repository markers before using it and safely falls back through script/current
locations without applying `Join-Path` to a null root.

Phase 5AT adds an original repository-owned shield/radar icon and an ignored
private aggregate package containing only the validated portable executable,
unsigned installer, operator documents, checksums, and provenance manifest.

The Phase 5AX runtime correction builds the unchanged React application into
`desktop/dist/app/` and packages it as a Tauri asset. Release builds therefore
use the embedded UI; Vite is retained only as a development fallback.

## What it does

- opens the bundled unchanged React frontend in installed/portable mode
- accepts `http://localhost:5173/` HTTP 2xx `text/html` as a development frontend
- checks fixed loopback endpoints for backend health, readiness, and release
- shows a bilingual English/Spanish help screen when services are unavailable
- displays copyable start, stop, restart, check, and frontend commands
- displays copy-only helpers for the browser opener and direct Docker services
- can invoke only five approved scripts when the repository is discoverable;
  otherwise it retains the copy-only fallback
- shows Docker dependency state plus the last launcher action and sanitized result
- returns to the help screen when a later service check fails
- keeps the status screen open when the operator chooses to inspect it

The desktop UI is isolated in `desktop/`; the build reuses (and does not rewrite)
the existing React application. Its embedded production copy calls the same
local backend and retains the web application's English/Spanish localization.

## Prerequisites

- Windows with WebView2 (normally included on supported Windows releases)
- Docker Desktop with Docker Compose
- Node.js/npm to build the embedded frontend or run browser/development mode
- Rust and Cargo for the prototype shell
- local development configuration based on `.env.example`

No Tauri CLI is required for the basic prototype command because the shell runs
directly through Cargo. Crate dependencies must already be available locally or
installed in a separately network-approved setup step.

## Run

From the repository root, start the backend dependencies yourself. Start Vite
only when testing browser/development mode:

```powershell
./scripts/local/start_platform.ps1
cd frontend
npm run dev
```

In a second terminal from the repository root:

```powershell
cd desktop
npm run check
npm run tauri:check
npm run tauri:dev
```

The shell uses these local defaults only:

- embedded frontend: packaged Tauri asset `./app/`
- development frontend: `http://localhost:5173/`
- backend: `http://localhost:8000`
- health: `http://localhost:8000/health`
- readiness: `http://localhost:8000/health/ready`
- release: `http://localhost:8000/api/v1/release`

`npm run build` in `desktop/` type-checks and builds the existing React frontend
with a fixed local backend URL, then copies the status shell and React output to
ignored `desktop/dist/`. It does not create an executable or installer itself.

Release builds report the frontend as **Embedded** and load the packaged UI.
Debug builds use Vite only when `/` or `/index.html` returns HTTP 2xx HTML and
otherwise retain the embedded fallback. If the backend
cannot be reached, it shows Docker startup guidance. If the backend answers but
readiness is degraded, it recommends the non-destructive platform check. If
requires action, it shows backend/Docker guidance. Vite guidance is never shown
as a production prerequisite. A recovered stack
reopens automatically unless the operator deliberately selected **Service
status**; **Open local workspace** then returns to the application manually.

## Security boundary

The Tauri capability file grants no plugin permissions and no remote origins.
There is no shell or filesystem plugin. Rust performs bounded HTTP GET probes to
`127.0.0.1:8000` plus the development-only `127.0.0.1:5173` and exposes five argument-free launcher
actions (aside from Tauri's injected app handle). Each maps internally to one fixed filename, resolves it only under a
canonical `scripts/local/` directory, runs Windows PowerShell without a profile
or stdin, caps and sanitizes output, and applies an action-specific timeout.

The embedded frame permits scripts, forms, downloads, modals, same-origin web
storage, and clipboard writes needed by the existing application. It does not
permit popups or top-level navigation, and CSP restricts frames to
itself and the development-only `http://localhost:5173` frame.

The shell never starts a service automatically. Only an explicit user action can
run an approved local script, and start/stop/restart require confirmation. It
cannot edit `.env`, reset a database, accept arbitrary commands, read secrets or
credentials, collect browser history, contact a router, administer another host,
or execute remote commands. Copy buttons remain available for every action.

## Prototype limitations

- Docker, PostgreSQL, Redis, FastAPI, and Celery remain separate services.
- Vite is optional and used only for browser/development mode; installed and
  portable builds use embedded frontend assets.
- The backend must be running on port 8000 for normal application behavior.
- Installed builds bind a manually entered, validated repository path. Missing,
  moved, incomplete, or altered-script repositories show the copy-only fallback.
- Phase 5AO provides an unsigned local-test installer workflow, not a signed or
  production installer, updater, hosted service, deployment, DNS change, or
  Supabase migration.
- The CSP permits self-packaged assets, localhost backend connections, and only
  the development Vite frame as an external frame.
- Production packaging and clean-machine validation remain future work.

## Safe checks

```powershell
cd desktop
npm run check
npm run build
npm run tauri:check
```

`npm run check` validates the fixed five-script allowlist, rejection of dynamic
command input, confirmation behavior, output sanitization and caps, timeouts,
copy fallback, local URLs, bilingual labels, and minimal capabilities.

Review `src-tauri/capabilities/default.json`, `src-tauri/tauri.conf.json`, and
`src-tauri/src/main.rs` before any future permissions or packaging change.

## Windows portable local-test build

With frontend dependencies already installed and Rust crates already available
locally, run from `desktop/`:

```powershell
npm run portable:build
```

The command validates the desktop source, verifies the existing browser
frontend build, runs a locked/offline Cargo release build, packages only an
executable, README, license, and checksum manifest, then validates the result.
It never runs an installer or contacts a package registry.

Output:

```text
desktop/dist-portable/RavenTech-OSINT-Desktop-5.0.0-rc6/
```

`dist-portable/` is intentionally Git-ignored. For separate steps, use
`npm run portable:package` after Cargo compilation and
`npm run portable:validate` after packaging. See
`desktop/PORTABLE_BUILD_README.md` for runtime prerequisites and recovery.

## Unsigned local installer

With the pinned desktop dependencies and locked Rust crates available locally,
run from `desktop/`:

```powershell
npm ci --offline
npm run installer:build
npm run installer:validate -- --require-artifact
```

The build uses only the NSIS target, passes `--no-sign`, skips WebView2 download
or embedding, and collects a strict four-file package under:

```text
desktop/dist-installer/RavenTech-OSINT-Desktop-5.0.0-rc6/
```

The ignored folder contains the unsigned setup executable, README, license, and
SHA-256 manifest. The current-user installer adds only the desktop shell and its
uninstaller. Docker/backend services must still be started manually; Vite is
not required by the installed application.
Read `desktop/INSTALLER_BUILD_README.md` and complete
`DESKTOP_DISTRIBUTION_CHECKLIST.md` before local testing. SmartScreen warnings
are expected; signing and public distribution remain deferred.

After portable and installer artifacts are present, run:

```powershell
npm run smoke -- --require-artifacts
```

The smoke command performs read-only metadata, manifest, checksum, local-URL,
permission, updater, ignore-rule, and forbidden-filename checks. See
`DESKTOP_LOCAL_DISTRIBUTION.md` for the complete local operator sequence.
