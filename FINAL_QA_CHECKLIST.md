# RavenTech OSINT Final QA Checklist

## Phase 5AA — monitoring policies

- [ ] Analyst can read policies and maintenance windows; unauthenticated access returns 401.
- [ ] Only administrators can create or update policies and maintenance windows.
- [ ] Resource, stale/offline, risky-service, unauthorized, weak-coverage, finding, and overdue rules have safe defaults.
- [ ] Cooldown, dedupe, per-rule cap, enablement, severity override, and acknowledge behavior validate cleanly.
- [ ] Suppress/unsuppress returns clean 403/404/409/422 outcomes and writes audit events.
- [ ] Active maintenance marks alerts without deletion or collection interruption.
- [ ] Monitoring Center states avoid raw API errors, crash screens, and horizontal overflow.
- [ ] No secrets, active scanning, hosting, deployment, DNS, or Supabase changes exist.

Version: `5.0.0-rc4`

## Phase 5AR — first-run setup and project-path reliability

- [ ] Manual path input accepts the RavenTech root only when compose, Python,
      desktop, frontend, backend, and all five approved script markers validate.
- [ ] Altered content under an approved script filename is rejected using the
      scripts pinned into the desktop build.
- [ ] Invalid, missing, moved, and incomplete paths are rejected or produce a
      copy-only fallback without raw filesystem errors.
- [ ] Resolution order is saved path, current-directory ancestry,
      development-executable ancestry, then copy-only fallback.
- [ ] Status shows repository, scripts, Docker, backend, frontend, ports
      8000/5173, RC4 release match, migrations, local URLs, and next action.
- [ ] Setup guidance works in English and Spanish without horizontal overflow,
      raw stack traces, `.env` values, or secret output.
- [ ] No shell/filesystem plugin, arbitrary script/arguments, folder browser,
      remote command, auto-install, system-setting change, or service autostart exists.
- [ ] Portable, installer, artifact smoke, Rust, frontend, and backend gates pass.

## Phase 5AQ — controlled local service launcher

- [ ] Rust exposes only argument-free check/start/stop/restart/open-frontend
      actions mapped to the five approved `scripts/local/` filenames; the injected
      app handle is not user input.
- [ ] Script resolution uses the validated saved path and canonical local ancestry;
      no UI command, argument, or script filename is accepted. The separate setup
      path is data-only and must pass the fixed repository validator.
- [ ] Start, stop, and restart require an explicit confirmation; cancel runs nothing.
- [ ] Check and open-frontend are explicit user actions, never startup actions.
- [ ] Missing repository scripts or PowerShell produce a readable copy-only fallback.
- [ ] Captured output is bounded, control characters and repository paths are
      sanitized, sensitive-marker lines are removed, and timeouts return cleanly.
- [ ] Desktop status shows backend, readiness, release, frontend, Docker
      dependency state, last command, and sanitized command result in English/Spanish.
- [ ] Local scripts pass PowerShell parsing and retain non-destructive stop,
      safe start-time migrations, concise errors, and no secret output.
- [ ] No shell/filesystem Tauri plugin or remote origin is granted.
- [ ] Portable and installer builds/validators plus desktop smoke checks pass.
- [ ] No public release, signing, service autostart, hosting, deployment, DNS,
      Supabase migration, router automation, remote/arbitrary command execution,
      or offensive functionality is added.

## Phase 5AP — installer QA, branding, and local distribution

- [ ] Product name, identifier, RC4 version, portable folder, installer name,
      README names, and **Local Workspace** window title are consistent.
- [ ] English and Spanish installer labels remain configured; the build-only
      placeholder icon is documented and not treated as final branding.
- [ ] Installer and portable builds pass their strict four-file allowlists and
      SHA-256 manifest validation while their output folders remain Git-ignored.
- [ ] `npm run smoke -- --require-artifacts` passes metadata, local URL,
      permission, updater, manifest, checksum, and forbidden-file checks.
- [ ] The unsigned installer launches the shell to its local status screen on
      the authorized QA host; no raw stack traces or secrets are displayed.
- [ ] Offline backend/frontend states show startup guidance; healthy services
      are detected and the unchanged frontend embeds successfully.
- [ ] Docker, FastAPI, Vite, PostgreSQL, and Redis remain separate and manually
      started; no service autostart or database/backend bundle is present.
- [ ] The uninstall path is documented and removes only the desktop shell.
- [ ] SmartScreen and unsigned status are stated clearly; no trusted signature
      or public-release claim is made.
- [ ] No signed installer, public release, auto-update, hosting, deployment,
      DNS, Supabase migration, router automation, remote command execution,
      scanning, or offensive functionality is added.

## Phase 5AO — unsigned Windows installer preparation

- [ ] Default/portable `bundle.active` remains false; the isolated installer
      override enables only NSIS and creates no updater artifacts.
- [ ] App metadata remains `RavenTech OSINT Desktop`, `5.0.0-rc4`, identifier
      `com.raventech.osint`, and an explicitly unsigned local-test publisher.
- [ ] Installer mode is current-user, downgrades are blocked, and English and
      Spanish installer languages are configured.
- [ ] WebView2 install mode is `skip`; the operator installs the runtime
      separately and the build performs no runtime download or embedding.
- [ ] `npm run installer:build` invokes the pinned Tauri CLI with `--no-sign`
      and collects output only under ignored `desktop/dist-installer/`.
- [ ] `npm run installer:validate -- --require-artifact` verifies the PE file,
      RC4 metadata, strict file allowlist, disabled boundaries, and SHA-256 hashes.
- [ ] Installer output contains only unsigned setup EXE, README, LICENSE, and
      manifest—no `.env`, credentials, certificates, databases, backups,
      reports, logs, backend, Docker runtime, or sidecars.
- [ ] Portable build still validates; browser/local Docker workflows and
      backend/frontend architecture remain unchanged.
- [ ] Install, local launch, frontend embed, language switch, benign report
      export, and uninstall checks pass on an authorized Windows test machine.
- [ ] SmartScreen warning and loopback-only Windows Firewall guidance are clear.
- [ ] No signed installer, public release, updater, hosting, deployment, DNS,
      Supabase migration, router automation, remote command execution, scanning,
      or offensive functionality is added.

## Phase 5AN — Windows portable desktop build preparation

- [ ] Desktop metadata reports `RavenTech OSINT Desktop` and `5.0.0-rc4` with
      the local prototype window title and build-only placeholder icon.
- [ ] `npm run portable:build` validates desktop source and the existing
      frontend, then runs Cargo with `--release --locked --offline`.
- [ ] Output exists only under ignored
      `desktop/dist-portable/RavenTech-OSINT-Desktop-5.0.0-rc4/`.
- [ ] The portable folder contains only `RavenTech OSINT Desktop.exe`,
      `README.md`, `LICENSE`, and `portable-manifest.json`.
- [ ] `npm run portable:validate` confirms PE signature, RC4 metadata, file
      allowlist, disabled boundaries, and SHA-256 checksums.
- [ ] No `.env`, credential, certificate, database, backup, report, client data,
      backend service, PostgreSQL, Redis, or Docker runtime is packaged.
- [ ] The copied executable starts and responds on Windows while retaining the
      fixed local health/status, controlled launcher, and copy-fallback behavior.
- [ ] Tauri default `bundle.active` remains false; the portable workflow invokes
      no MSI, NSIS, signing, updater, release publishing, or service autostart.
- [ ] Browser/local Docker mode, backend validation, frontend localization,
      RC4 release metadata, and migration head remain unchanged.
- [ ] No hosting, deployment, DNS, Supabase migration, router automation,
      remote command execution, scanning, or offensive functionality is added.

## Phase 5AM — desktop runtime QA and local build preparation

- [ ] Backend, readiness, release, and frontend cards distinguish reachable,
      unreachable, ready, and degraded states without raw response bodies.
- [ ] Backend-unreachable, dependency-degraded, and frontend-unreachable states
      show distinct English/Spanish operator guidance.
- [ ] A healthy first check opens the existing local frontend; service failure
      returns to status; manual status inspection is not overridden by polling.
- [ ] The shell provides copy-only start, stop, restart, health check, browser
      open, frontend dev, and Docker service commands.
- [ ] `npm run check` passes fixed-URL, bilingual-label, copy-command, secret,
      capability, navigation, and disabled-bundling checks.
- [ ] The embedded frame has no popup or top-navigation permission and CSP
      allows only `http://localhost:5173` as a frame source.
- [ ] Cargo check and the static desktop UI build pass without producing an
      installer, release package, or published artifact.
- [ ] Browser mode, frontend build, backend tests, RC4 release metadata, and
      migration head `0036_phase5ai_posture` remain unchanged.
- [ ] No hosting, deployment, DNS, Supabase, router automation, remote command
      execution, shell/filesystem plugin, scanning, or offensive work is added.

## Phase 5AL — Tauri desktop shell prototype

- [ ] `desktop/` remains isolated from the existing React/Vite frontend.
- [ ] The shell shows backend health, readiness, release, and frontend status.
- [ ] With the Vite frontend available, the unchanged bilingual web app opens
      inside the desktop window; normal browser mode still works.
- [ ] With a service unavailable, the bilingual help screen shows local URLs
      and copyable start/stop/restart/check/frontend commands without raw errors.
- [ ] `cd desktop; npm run check` passes the static security/document checks.
- [ ] `cd desktop; npm run build` validates the static shell assets only and
      creates no installer or production bundle.
- [ ] `cd desktop; npm run tauri:check` passes when Rust dependencies are
      available locally.
- [ ] `src-tauri/capabilities/default.json` grants no plugin permissions.
- [ ] No shell/filesystem plugin, generic URL command, secret access, automatic
      command execution, installer, hosting, deployment, DNS, Supabase, router
      automation, remote administration, or offensive feature is present.

## Phase 5AK — desktop readiness and local operator workflow

- [ ] `scripts/local/start_platform.ps1 -OpenFrontend` starts services, applies
      migrations, and checks health/readiness/release without printing secrets.
- [ ] `scripts/local/check_platform.ps1` reports healthy local status and
      `scripts/local/stop_platform.ps1` stops services without removing volumes.
- [ ] Restart and browser-open helpers work; the legacy `start_local.ps1` helper
      remains available.
- [ ] Operations → Local Operator Console shows read-only backend health,
      readiness, RC4 release, database/Redis/worker status, local URLs, LAN
      flags, configured ranges/ports, and agent coverage.
- [ ] Operator command buttons show copy confirmation and never execute host
      commands; no secrets appear in the payload or UI.
- [ ] English/Spanish localization remains available on the Operator Console.
- [ ] Desktop shell, installer, hosting, deployment, DNS, Supabase, router
      automation, and offensive functionality remain deferred/out of scope.

Run from the repository root unless a section says otherwise. Complete this
checklist with synthetic or explicitly authorized data only. A failed required
check blocks the current release-freeze commit and push.

## Automated Validation

- [ ] `docker compose run --rm backend python -m ruff check app workers tests`
- [ ] `docker compose run --rm backend python -m mypy app workers`
- [ ] `docker compose run --rm backend python -m pytest tests/ -q`
- [ ] `docker compose run --rm backend python -m pip check`
- [ ] `docker compose exec backend alembic check`
- [ ] `curl http://localhost:8000/health` returns `status: ok`.
- [ ] `curl http://localhost:8000/health/ready` returns `status: ok`.
- [ ] `curl http://localhost:8000/api/v1/release` returns `5.0.0-rc4` and
      `0036_phase5ai_posture` without secrets.
- [ ] From `frontend/`, `npm run build` passes.
- [ ] `docker compose ps` shows required local services running; backend and
      PostgreSQL are healthy.
- [ ] `docker compose logs backend --tail=100` has no blocking error or secret.

## Authentication And Admin Users

- [ ] Existing active administrator login works; bad credentials return a clean
      401 message.
- [ ] Registration UI/API matches configuration and never creates an admin.
- [ ] Pending/disabled/rejected users cannot access protected routes.
- [ ] Admin Users list/search/filter and approve/reject/disable/reactivate work.
- [ ] The last active administrator cannot be disabled or demoted.
- [ ] Password hashes, invite codes, tokens, and secret configuration never
      appear in responses or UI.

## Core Investigation Workflow

- [ ] Dashboard and Operations Center load with safe empty/degraded states.
- [ ] Investigations list/detail, membership, ownership, notes, tasks, bookmarks,
      timeline, and archive/restore work.
- [ ] Engagement authorization and scope records can be reviewed and linked.
- [ ] Domain/subdomain/IP/CIDR scope checks remain local and conservative.
- [ ] Targets and passive recon work without active scanning or crawling.
- [ ] Findings load, filter, update, and retain evidence/remediation context.
- [ ] Correlations Cards/Graph/Table, IOCs, Evidence Intelligence, and Threat
      Intelligence tolerate empty or partial data.
- [ ] AI provider failure shows deterministic fallback rather than a crash.

## Reports, Closure, And Deliverables

- [ ] Executive and technical reports generate from stored evidence.
- [ ] PDF, DOCX, HTML, and Markdown downloads work according to export policy.
- [ ] Report warnings are advisory and every report remains analyst-reviewed.
- [ ] Review/approval and remediation validation transitions work.
- [ ] Closure checklist submit/approve/close/reopen works for authorized roles.
- [ ] Premature closure requires a permitted, recorded override reason.
- [ ] Deliverable records and evidence package manifest show consistent included,
      missing, warning, and evidence data.

## Notifications, Search, And Saved Views

- [ ] Notification list/filter/read/dismiss/mark-all-read and unread count work.
- [ ] Users cannot access or mutate another user's notification.
- [ ] Global Search returns only RBAC-authorized internal records and safe routes.
- [ ] Non-admin users cannot retrieve admin user results.
- [ ] Saved Views create/update/load/pin/default/unpin/delete works.
- [ ] Saved Views remain owner-scoped and reject unsafe routes/secret filters.

## Data Quality, Audit, And Governance

- [ ] Data Quality Center denies non-admin access.
- [ ] Dry run changes no source record; scan creates bounded review issues.
- [ ] Issue acknowledge/ignore/resolve and invalid-transition handling work.
- [ ] Stale-notification maintenance only soft-archives eligible records.
- [ ] Audit Log records the exercised security, workflow, report, search, and
      quality actions without secrets.
- [ ] Governance settings, feature flags, export controls, and demo-mode state
      display consistently.

## Local Monitoring

- [ ] Monitoring requires authentication; an analyst sees only accessible
      investigations and an administrator sees the platform-authorized set.
- [ ] Overview, services, system, assets, and alerts endpoints return bounded,
      sanitized responses without secrets or raw exceptions.
- [ ] Service cards reflect backend, database, Redis, worker, migration, report
      storage, and deliberately limited Docker visibility.
- [ ] Poll selection remains between 15 and 300 seconds and manual refresh works.
- [ ] Asset Watch summarizes targets, findings, evidence, reports, closure,
      scope, and authorization without active scanning.
- [ ] Repeated overview polling creates at most one Activity Inbox notification
      per alert/user/day.
- [ ] Optional local agent rejects non-local backend URLs and invalid telemetry;
      ingestion is admin-only and the bearer token is never persisted or logged.
- [ ] Missing/stale agent data falls back cleanly to container metrics and does
      not make the platform unavailable.
- [ ] Normal navigation shows no global demo-mode banner; QA Tools and demo
      seed/reset controls are admin-only, while synthetic records remain labeled.
- [ ] LAN monitoring is disabled by default and LAN inventory routes deny
      non-admin users.
- [ ] Public, non-RFC1918, out-of-range, and discovery ranges larger than `/24`
      are rejected.
- [ ] Discovery is admin-triggered and rate limited; ping and bounded configured
      TCP connects remain disabled unless separately enabled.
- [ ] Docker neighbor-table limitations return a clear empty/limitation state
      without privileged mode or a crash.
- [ ] Agent registration/telemetry rejects missing, invalid, or unset shared
      tokens and never echoes or logs them.
- [ ] Endpoint detail tolerates missing telemetry, services, MAC, hostname,
      latency, and notes without a React crash.
- [ ] LAN alerts deduplicate, and port/resource/version results are labeled risk
      indicators rather than confirmed vulnerabilities.
- [ ] Vulnerability Baseline evaluates stored observations only and does not
      initiate discovery, service probing, credential checks, or exploit tests.
- [ ] Admin and analyst roles can set asset criticality/business context and
      track baseline status, remediation owner, and due date.
- [ ] Risky service, stale agent, unauthorized asset, sustained pressure,
      missing-owner, and overdue-remediation indicators appear without alert
      duplication or secret metadata.

## UI And Portfolio Review

- [ ] No normal flow shows raw endpoint dumps, stack traces, `undefined`, or
      `null` text.
- [ ] No long ID, URL, tab row, table, or modal causes horizontal page overflow.
- [ ] No React crash screen appears; retry/empty/degraded states are readable.
- [ ] Screenshot set follows `SCREENSHOTS_CHECKLIST.md` and contains only
      synthetic data.
- [ ] Demo follows the locked 12-step order in `PORTFOLIO_DEMO_FLOW.md`.
- [ ] `LOCAL_DEMO_BUNDLE.md` and `GITHUB_RELEASE_DRAFT.md` match the frozen
      version, validation evidence, limitations, and defensive-only scope.

## Freeze And Git Gate

- [ ] No hosting, deployment, DNS, Supabase migration, provider, feature, or
      frontend redesign change is present.
- [ ] No production secret or customer data is present.
- [ ] Local backup creates a non-empty custom-format PostgreSQL dump without
      including `.env` or secret configuration.
- [ ] Restore validation refuses the live database and restores only into a new,
      previously absent database.
- [ ] Demo prepare can run repeatedly without duplicates or a 500 response.
- [ ] Guarded demo reset takes a safety backup by default, removes only fixed
      synthetic records, and preserves non-demo investigations.
- [ ] `./scripts/local/check_local_health.ps1` passes.
- [ ] `git diff --check` passes and the diff contains only the current phase.
- [ ] `git status` is reviewed before commit.
- [ ] Commit uses the message required by the current phase.
- [ ] Push to `origin/dev` succeeds and the working tree is clean/synchronized.
- [ ] If `v5.0.0-rc4` already exists, verify its target instead of recreating or
      moving it blindly; otherwise create it only on the validated package commit.
- [ ] Push `v5.0.0-rc4` only after the release-package commit reaches
      `origin/dev`, then verify the local and remote tag targets match.

## Phase 5AB monitoring reliability

- [ ] Healthy required dependencies remain **Platform healthy** when optional
      host telemetry is unavailable; container and host-agent metrics are
      labeled accurately.
- [ ] Recovered overview alerts retire, refresh clears stale banners, and alert
      dedupe/cooldowns/maintenance suppression prevent refresh spam.
- [ ] Recon timeout, HTTP, and JSON parse failures are grouped by provider;
      valid stored entities survive partial failures and retry remains enabled.
- [ ] LAN service checks are disabled by default, admin-operated, TCP-connect
      only, rate-limited, private/allowlisted, and bounded by configured ports,
      host limits, and timeout.
- [ ] Port 22 and approved non-standard SSH banners receive clear service and
      confidence labels without storing raw or sensitive banner content.
- [ ] Monitoring tabs, cards, notification dropdown, empty states, tooltips,
      buttons, and alert actions fit small widths without clipping or raw errors.
- [ ] No public scanning, authentication, brute force, command execution,
      exploitation, intrusive testing, hosting, deployment, DNS, or Supabase
      change is present.

## Phase 5AC history and timeline

- [ ] New asset, offline/online, hostname/MAC, port open/closed, service guess,
      non-standard SSH, stale/resumed agent, threshold, and baseline transitions
      produce bounded change events only when state changes.
- [ ] Service history preserves previous/current TCP status, service guess,
      confidence, source, and observed time without raw banners or secrets.
- [ ] Change APIs enforce authentication, role access, pagination, filters,
      safe 404/422 responses, and audited acknowledgement.
- [ ] Change-derived notifications respect policy cooldowns, dedupe limits,
      suppressions, and maintenance windows.
- [ ] Change Timeline and asset history views render useful loading, empty,
      error, filtering, and acknowledgement states without horizontal overflow.

## Phase 5AD alert triage and overlays

- [ ] Triage is user-scoped and supports status, severity, source, and asset
      filters with bounded pagination.
- [ ] Assignment, investigate, mute/unmute, resolve, and false-positive actions
      return clean errors and write audit events without secrets.
- [ ] Maintenance suppression remains distinct from manual mute; monitoring and
      notification history continue unchanged.
- [ ] Analysts cannot mute critical alerts or assign another user.
- [ ] Activity Inbox overlays page/sidebar content, scrolls independently, and
      closes on outside click or Escape without clipping at small dimensions.
- [ ] Alerts show useful loading, empty, retry, action, and disabled states with
      no raw endpoint errors, crash screen, or horizontal overflow.

## Phase 5AE enrollment, groups, and coverage

- [ ] Enrollment plaintext appears only in the create/rotate response and is
      absent from lists, database plaintext, logs, telemetry, and commands.
- [ ] Invalid, expired, revoked, exhausted, and CIDR-mismatched credentials are
      rejected; token management is admin-only.
- [ ] Agent registration and heartbeats retain OS/version/freshness,
      enrollment label, capabilities, authorization, monitoring, and context.
- [ ] Group CRUD, membership, filtering, coverage, and risk summaries work with
      clean RBAC and empty/error states.
- [ ] Asset/group service baselines identify missing expected and unexpected
      open ports from stored observations without initiating a connection.
- [ ] Windows and Linux helpers collect basic CPU/RAM/disk/uptime/OS data only,
      prompt securely, stop with Ctrl+C, and configure no persistence.
- [ ] Overlay, tabs, health, LAN inventory, triage dedupe, and narrow layouts
      retain prior regression coverage.

## Phase 5AF activation and recon UX

- [ ] Activation status shows effective LAN/service flags, allowed private
      CIDRs, ports, disabled reasons, safe `.env` lines, and restart guidance.
- [ ] Activation and command-builder output contains no token or secret; the UI
      never edits `.env` and firewall guidance scopes TCP 8000 privately.
- [ ] Target eligibility requires an exact existing authorized private-LAN
      asset match; analysts may read status and only admins may execute checks.
- [ ] URL recon services remain visually separate from TCP port observations,
      including status, service guess, confidence, and SSH badges.
- [ ] Partial enrichment warnings say stored results are valid and retry is
      safe; provider codes include timeout, HTTP, parse, and connectivity.
- [ ] Monitoring tabs, cards, tables, modals, and buttons remain unclipped and
      avoid raw endpoint errors or React crash screens at narrow widths.

## RC4 final local acceptance flow

1. [ ] Start the local platform and apply the current migration head.
2. [ ] Verify `/health`, `/health/ready`, and `/api/v1/release` report healthy RC4.
3. [ ] Verify registration policy, login, logout, and invalid-login handling.
4. [ ] Open every main navigation page without raw errors or a crash screen.
5. [ ] Run authorized passive target recon using synthetic test data.
6. [ ] Review `completed_with_warnings`: stored results are valid and retry is safe.
7. [ ] Review TCP service observations separately from recon service entities.
8. [ ] Open every Monitoring Center tab and verify refresh and empty states.
9. [ ] Create and revoke an enrollment credential; verify one-time reveal.
10. [ ] Review advisory vulnerability-baseline indicators and remediation data.
11. [ ] Review alert triage, dedupe, recovery, suppression, and maintenance state.
12. [ ] Export a reviewed report as PDF, DOCX, HTML, and Markdown.
13. [ ] Run a bounded Data Quality scan and review its non-destructive results.
14. [ ] Verify audit records for exercised actions contain no secrets.
15. [ ] Confirm no raw errors, stack traces, React crash screen, overflow, or
        clipped tabs/buttons appear.

## Prior RC3 feature-freeze gate

- [ ] The prior RC3 metadata, acceptance documentation, regression tests, and
      validation-blocking fixes are present; no new module or migration exists.
- [ ] Local Docker Compose remains the only validated product mode.
- [ ] Monitoring remains authorized/local, service checks remain TCP-connect
      only, and baseline results remain advisory rather than exploit validation.
- [ ] Desktop packaging, Electron, Tauri, installers, hosting, deployment, DNS,
      and Supabase migration remain deferred.

## Phase 5AI endpoint security posture

- [ ] Posture assessment persists a bounded score/status from stored authorized
      LAN and agent evidence without initiating a scan or remote command.
- [ ] Agentless assets show only LAN/service/authorization visibility; missing
      firewall, antivirus, and patch data remains unknown rather than invented.
- [ ] Windows/Linux helpers collect only safe normalized posture fields and
      listening port numbers with no files, credentials, history, or keystrokes.
- [ ] Unauthorized asset, stale agent, disabled protection, patch awareness,
      pending reboot, resource pressure, risky service, baseline governance, and
      expected-service recommendations deduplicate correctly.
- [ ] Acknowledge/resolve transitions enforce RBAC and clean 404/409/422 errors.
- [ ] Manual isolation guidance never contacts a router or changes a network,
      host firewall, VLAN, or endpoint configuration.
- [ ] High/critical alerts respect policies, cooldowns, suppressions,
      maintenance windows, dedupe, and existing triage.
- [ ] Reports include only exactly matched assessed target assets, advisory
      wording, top manual actions, and no-exploit-validation language.
- [ ] Migration current/head is `0036_phase5ai_posture`; exports and frontend
      build remain stable.

## Phase 5AJ bilingual localization and RC4 freeze

- [ ] English is the default and Spanish can be selected on login and in the
      authenticated shell without changing authorization or backend logs.
- [ ] The `raventech.language` preference survives refresh; unavailable storage
      falls back safely to English and missing Spanish copy shows English text.
- [ ] Navigation, login/register, shared status/severity badges, loading, empty,
      error, actions, monitoring, recon, reports, search, administration, data
      quality, audit, and QA headings render professional Spanish copy.
- [ ] No `namespace.translation_key`, secret, token, password, raw endpoint
      error, or React crash screen is visible in tested localized workflows.
- [ ] Recon partial-enrichment, provider-error, Docker/LAN, optional telemetry,
      non-standard SSH, risk, and manual isolation copy works in both languages.
- [ ] English and Spanish reports retain the selected language on retry and
      export successfully as PDF, DOCX, HTML, and Markdown.
- [ ] `/api/v1/release` reports `5.0.0-rc4`; migration current/head remains
      `0036_phase5ai_posture` and no Phase 5AJ migration exists.
- [ ] `npm run test:i18n` and `npm run build` pass before commit/tag.
- [ ] Desktop packaging, hosting, deployment, DNS, Supabase, router automation,
      public scanning, and offensive behavior remain absent.
