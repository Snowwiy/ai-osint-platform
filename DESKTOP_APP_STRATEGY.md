# RavenTech Desktop App Strategy

Phase 5AK prepares the validated local web platform for a future desktop shell;
it does not build an installer or desktop application.

## Recommended sequence

1. Keep the browser-based local Docker mode as the reference operator console.
2. Use the local launcher scripts for repeatable start, stop, restart, health,
   and browser-open workflows.
3. Stabilize the in-app Operator Console and document manual support actions.
4. Prototype a desktop shell only after the local workflow is accepted.
5. Package and sign an installer in a separately reviewed phase.

## Shell recommendation

Tauri is the preferred future shell for a small Windows footprint and a native
health-check/open-local-UI bridge. Electron remains a viable alternative when
broader Chromium compatibility or JavaScript-native integrations justify its
larger footprint. The current browser mode remains the simplest and most
transparent option for development and acceptance.

The backend remains FastAPI and the frontend remains React/Vite. PostgreSQL and
Redis remain local Docker services for now. A later shell may check backend
health and open the local frontend URL, but the browser must not execute host
commands, collect credentials, run a remote shell, or change router settings.

Desktop packaging, installer signing, hosting, deployment, DNS, and Supabase
migration are deferred. No automatic router blocking or other automated
remediation is planned in this preparation phase.
