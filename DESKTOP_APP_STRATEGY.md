# RavenTech Desktop App Strategy

Phase 5AK established desktop readiness and the local operator workflow. Phase
5AL now provides a minimal Tauri v2 shell prototype; it does not provide an
installer or production packaging.

Phase 5AM makes the prototype suitable for local operator QA through readable
degraded states, explicit recovery guidance, safe workspace/status transitions,
and regression checks. It does not change the underlying architecture.

Phase 5AN adds a reproducible Windows portable local-test build. The output is
an unsigned executable plus documentation, license, and checksums. It remains
dependent on the operator-managed repository, Docker stack, and Vite frontend;
it does not convert those components into embedded desktop services.

Phase 5AO adds a separate unsigned NSIS installer profile for local Windows
testing. It installs only the same shell for the current user, preserves the
portable workflow, and leaves signing, updater design, and public distribution
behind later release gates.

## Current approach

1. Keep browser-based local Docker mode as the reference and supported workflow.
2. Keep FastAPI, React/Vite, PostgreSQL, Redis, Celery, and Docker unchanged.
3. Isolate the prototype in `desktop/` rather than adding Tauri to `frontend/`.
4. Let the shell check only fixed localhost endpoints and embed the running Vite
   frontend after health succeeds.
5. Keep all host operations manual through copyable commands and the existing
   local launcher scripts.
6. Test the unsigned installer locally; review signing and production
   distribution in a separate approved phase.

The default and portable configuration keeps Tauri bundling disabled. Phase 5AO
uses a separate `tauri.installer.conf.json` override that enables only an
unsigned NSIS current-user target. Generated folders under ignored
`desktop/dist-portable/` and `desktop/dist-installer/` are local artifacts, not
release assets. The installer embeds no services, sidecars, resources, secrets,
or WebView2 bootstrapper.

## Why Tauri

Tauri provides a small native shell while allowing RavenTech OSINT to preserve
the existing web application. The prototype uses a Rust loopback health bridge
instead of granting browser CORS exceptions or a generic HTTP capability. It
does not use Electron, embed databases, replace Docker, or change the backend.

The browser workflow remains the simplest development and recovery path. If the
shell is unavailable, operators can continue using `npm run dev` from
`frontend/` and open `http://localhost:5173` normally.

## Security posture

The prototype grants no Tauri plugin permissions and includes no shell or
filesystem plugin. Its only command has no parameters and probes four fixed
local routes. It does not collect credentials or history, access secrets,
administer routers, start services, or execute local or remote commands.

The embedded frontend is limited by CSP to `http://localhost:5173`. Its sandbox
does not grant popup or top-level navigation, while preserving the scripts,
forms, downloads, local application storage, and copy behavior needed by the
existing web workflow.

Installer signing, auto-update, public release, hosting, deployment, DNS, and
Supabase migration remain deferred. See `DESKTOP_TAURI_PROTOTYPE.md` for local
operation, `DESKTOP_DISTRIBUTION_CHECKLIST.md` for QA, and
`DESKTOP_PACKAGING_TODO.md` for future gates.
