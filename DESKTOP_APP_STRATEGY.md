# RavenTech Desktop App Strategy

Phase 5AK established desktop readiness and the local operator workflow. Phase
5AL now provides a minimal Tauri v2 shell prototype; it does not provide an
installer or production packaging.

## Current approach

1. Keep browser-based local Docker mode as the reference and supported workflow.
2. Keep FastAPI, React/Vite, PostgreSQL, Redis, Celery, and Docker unchanged.
3. Isolate the prototype in `desktop/` rather than adding Tauri to `frontend/`.
4. Let the shell check only fixed localhost endpoints and embed the running Vite
   frontend after health succeeds.
5. Keep all host operations manual through copyable commands and the existing
   local launcher scripts.
6. Review packaging, signing, and clean-machine behavior in a separate phase.

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

Desktop packaging, installer signing, auto-update, hosting, deployment, DNS,
and Supabase migration remain deferred. See `DESKTOP_TAURI_PROTOTYPE.md` for
prototype operation and `DESKTOP_PACKAGING_TODO.md` for future gates.
