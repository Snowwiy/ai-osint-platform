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

## What it does

- opens the unchanged frontend from `http://localhost:5173` inside the shell
- checks fixed loopback endpoints for backend health, readiness, and release
- shows a bilingual English/Spanish help screen when services are unavailable
- displays copyable start, stop, restart, check, and frontend commands
- displays copy-only helpers for the browser opener and direct Docker services
- returns to the help screen when a later service check fails
- keeps the status screen open when the operator chooses to inspect it

The desktop UI is isolated in `desktop/`; it does not rewrite or bundle a second
copy of the React application. The iframe retains the web application's normal
API behavior, authentication origin, and English/Spanish localization.

## Prerequisites

- Windows with WebView2 (normally included on supported Windows releases)
- Docker Desktop with Docker Compose
- Node.js/npm for the existing frontend
- Rust and Cargo for the prototype shell
- local development configuration based on `.env.example`

No Tauri CLI is required for the basic prototype command because the shell runs
directly through Cargo. Crate dependencies must already be available locally or
installed in a separately network-approved setup step.

## Run

From the repository root, start the backend dependencies and frontend yourself:

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

- frontend: `http://localhost:5173`
- backend: `http://localhost:8000`
- health: `http://localhost:8000/health`
- readiness: `http://localhost:8000/health/ready`
- release: `http://localhost:8000/api/v1/release`

`npm run build` in `desktop/` only validates and copies the small shell UI to an
ignored local `desktop/dist/` directory. It does not create an executable,
bundle, installer, updater, or signed artifact.

On its first healthy check, the shell embeds the local frontend. If the backend
cannot be reached, it shows Docker startup guidance. If the backend answers but
readiness is degraded, it recommends the non-destructive platform check. If
only the frontend is unavailable, it shows the Vite command. A recovered stack
reopens automatically unless the operator deliberately selected **Service
status**; **Open local workspace** then returns to the application manually.

## Security boundary

The Tauri capability file grants no plugin permissions and no remote origins.
There is no shell or filesystem plugin. The only invoked Rust command accepts no user input and
performs bounded HTTP GET probes to `127.0.0.1:8000` and
`127.0.0.1:5173`. Responses are size-limited and shown as simple status values;
raw stack traces and response bodies are not exposed.

The embedded frame permits scripts, forms, downloads, modals, same-origin web
storage, and clipboard writes needed by the existing application. It does not
permit popups or top-level navigation, and CSP restricts frames to
`http://localhost:5173`.

The shell never starts Docker, runs PowerShell, modifies `.env`, resets a
database, reads secrets or credentials, collects browser history, contacts a
router, administers another host, or executes remote commands. Copy buttons use
the web clipboard API and always require the operator to paste and run the text.

## Prototype limitations

- Docker, PostgreSQL, Redis, FastAPI, Celery, and Vite remain separate services.
- The frontend must be running on port 5173 before it can be embedded.
- The backend must be running on port 8000 for normal application behavior.
- Phase 5AO provides an unsigned local-test installer workflow, not a signed or
  production installer, updater, hosted service, deployment, DNS change, or
  Supabase migration.
- The CSP intentionally allows framing only `http://localhost:5173`.
- Production packaging and clean-machine validation remain future work.

## Safe checks

```powershell
cd desktop
npm run check
npm run build
npm run tauri:check
```

`npm run check` validates the config, all seven copy-only commands, fixed local
URLs, bilingual help labels, secret-field absence, disabled bundling, and the
lack of shell/filesystem or remote-navigation capability.

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
desktop/dist-portable/RavenTech-OSINT-Desktop-5.0.0-rc4/
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
desktop/dist-installer/RavenTech-OSINT-Desktop-5.0.0-rc4/
```

The ignored folder contains the unsigned setup executable, README, license, and
SHA-256 manifest. The current-user installer adds only the desktop shell and its
uninstaller. Docker/local services and Vite must still be started manually.
Read `desktop/INSTALLER_BUILD_README.md` and complete
`DESKTOP_DISTRIBUTION_CHECKLIST.md` before local testing. SmartScreen warnings
are expected; signing and public distribution remain deferred.
