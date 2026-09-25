# Native Desktop Acceptance — Phase 5BN

Version: `5.0.0-rc6`  
Scope: freeze and verify the Docker-optional Windows/Linux desktop runtime. No
public release, tag, signing claim, version bump, OS service installation, or
autostart behavior is authorized by this record.

## Normal desktop use

Launch RavenTech OSINT Desktop from its installed or portable entry. The Tauri
runtime acquires its per-user lock, resolves the configured managed or external
database mode, starts only the managed PostgreSQL child when selected, verifies
database readiness and schema, starts the native backend, checks health/readiness
and release compatibility, starts the native worker, waits for worker health, and
opens the embedded frontend. Read-only host monitoring is provided by the native
desktop provider. Normal packaged use does not require Docker, Redis, Celery,
Python, Node/npm, Vite, a separately installed PostgreSQL/CLI, repository
ancestry, PowerShell, Bash, or manual terminal steps.

On shutdown the supervisor requests cooperative worker shutdown, then backend
shutdown, closes database activity, and stops only the managed PostgreSQL process
owned by that desktop. External databases and unrelated processes are never
stopped. Startup failures preserve database data and report a safe reason; RavenTech
does not delete or reinitialize unknown data to recover.

The read-only runtime status distinguishes database, backend, worker, embedded
frontend, migrations, native jobs, and host monitoring. Redis and Celery are
optional compatibility components in the desktop profile and do not degrade its
readiness.

## Development / Docker compatibility

Docker Compose remains an alternative development/compatibility profile with
PostgreSQL, backend, Redis, and Celery. Python backend, Vite, Rust/Tauri, build
scripts, approved PowerShell helpers, and repository-relative setup remain
contributor workflows. Their commands are not packaged desktop startup steps.
PostgreSQL remains required in both profiles; desktop defaults to the managed
loopback runtime and Docker retains its service-hostname configuration.

## Dependency reference classification

The source contains references for several profiles. Only the first row is a
packaged desktop runtime requirement; Docker/Redis/Celery references remain for
development and compatibility.

| Category | References | Native desktop interpretation |
|---|---|---|
| A — required native desktop runtime | Tauri shell, fixed bundled backend and worker, managed PostgreSQL 16 runtime; Windows WebView2 or manifest-listed Linux shared libraries | All shipped or OS-provided. PostgreSQL is required; no PATH lookup for backend/worker/PostgreSQL utilities. |
| B — development only | Python, Uvicorn, Node/npm, Vite, Rust/Cargo/Tauri CLI, repository helpers and terminal commands | Contributor/development workflows; not needed by installed or portable launch. |
| C — Docker compatibility | Docker/Docker Compose, Docker-hosted PostgreSQL/backend, Redis, Celery | Preserved compatibility profile; absence is optional in packaged native desktop. |
| D — documentation | Operator troubleshooting and development/Docker examples | Explicitly separated from Normal Desktop Use. |
| E — test/build tooling | Pytest, package builders/validators, PowerShell and Bash syntax checks, Cargo tests | Build/QA only; not invoked as native desktop prerequisites. |
| F — historical/development-only launcher | Repository path binding and fixed approved PowerShell helper launcher | Retained for the source/development compatibility shell. Hidden in native desktop mode and not used by its supervisor startup/shutdown path. |

Bundled `initdb`, `pg_ctl`, `psql`, and readiness utilities are invoked by fixed
validated artifact paths to manage only the owned local cluster; a separate
PostgreSQL installation or CLI from `PATH` is not required.

## Acceptance matrix

Record actual results for each local run. A WSL result is Linux runtime testing,
not clean-machine Linux acceptance. Rendering the status panel is read-only and
does not run destructive checks.

| Area | Result | Evidence / limitation |
|---|---|---|
| Windows packaged zero-Docker desktop | PASS (installed NSIS plus portable API workflows; visual UI inspection NOT RUN) | The current unsigned NSIS installer and portable Tauri app launched from fresh isolated profiles outside the repository. Managed PostgreSQL initialized and bound only to 127.0.0.1:55432; backend health/readiness and release returned 200/200/5.0.0-rc6; the native worker heartbeated and completed PostgreSQL jobs. The installed NSIS app passed first launch, authenticated product API smoke, graceful shutdown, relaunch, uninstall, reinstall, and persistent-cluster reuse. A temporary administrator created through the supported bootstrap utility passed login, profile, refresh rotation, previous-token rejection, logout, and revoked-token rejection. Dashboard, investigation, note/task, analysis, Monitoring Center, LAN/agent/assets, Operations Center, Security Posture, executive, Change Timeline, correlation, vulnerability, maintenance, alert, and notification APIs passed. PDF, DOCX, HTML, and Markdown reports were generated and checked for non-empty output, MIME/signature or document structure, expected RavenTech/report content, and absence of test secrets. The authorized passive recon smoke path returned entities with provider warnings and performed no active scan. Production frontend assets are embedded; no Vite server was used. Direct visual inspection of the desktop UI was NOT RUN because no native Tauri automation surface was available. Test records and the initialized managed cluster remained in the isolated profile; no operator credentials or data were used. |
| Linux/WSL native core | PASS (packaged runtime and API workflows; visual GUI not claimed) | Debian 13 x86_64 WSL ran the current packaged Tauri executable from its bundle with an isolated XDG profile. Managed PostgreSQL 16.15 initialized on loopback, migrations reached the sole head, backend and worker became healthy, and authenticated Monitoring/Operations/Posture/Timeline/Notifications/Reports/Passive Recon APIs passed. A same-profile packaged relaunch reused the existing cluster; its ownership marker, PostgreSQL major version, current schema, and five synthetic users persisted. This process-controlled restart does not verify normal GUI close. This is Linux runtime evidence, not clean-machine acceptance. |
| Linux Tauri GUI | NOT RUN (visual/interactive check) | WSLg was present and the packaged Tauri process launched, but no supported native-window inspection surface was available to verify rendered pages or manually interact with the UI. The embedded production frontend and backend API workflows were independently validated. |
| Windows clean-machine (5BO) | NOT RUN | Requires a separate clean Windows 10/11 x64 machine with WebView2 and no repository checkout. |
| Linux clean-machine (5BP) | NOT RUN | Requires a separate clean Linux x86_64 installation/VM with the package manifest prerequisites. |
| Docker compatibility | PASS (configuration only) | Compose files remain present and a quiet Compose configuration check passed previously; Docker Desktop/service and live containers were stopped during native acceptance, so the live Docker workflow was not exercised here. |
| Frontend production embedding | PASS (build/package; visual inspection NOT RUN) | Production React assets are embedded in the rebuilt Tauri package. Packaged API checks did not use Vite or localhost:5173. No screen-capture automation surface was available for independent visual confirmation. |
| Security boundary | PASS (static/tests) | Desktop safety checks and source review found no new arbitrary command path, remote administration, persistence, or public-release behavior. |

### Phase 5BN follow-up validation — 2026-09-23

- Root cause: the packaged Tauri resource resolver supplied a Windows extended-
  length `\\?\` path. PostgreSQL `initdb` could run, but its sibling lookup did
  not find `postgres.exe` using that spelling even though both executables were
  packaged together. The managed runtime now normalizes only the immutable
  resource root to a normal absolute drive/UNC path before resolving PostgreSQL
  binaries. Path-normalization unit tests and the live isolated PostgreSQL
  bootstrap/restart/persistence test passed with a verbatim-prefixed resource
  root. Existing spaced-path support, data-path ownership checks, and retry
  safeguards remain intact.
- A second stale-status issue was fixed: successful startup already cleared
  PostgreSQL's current error fields, but the summary banner could retain the last
  historical initdb message. Successful managed PostgreSQL startup now records a
  safe loopback-ready message; a regression test proves the old failure is no
  longer the current summary.
- Packaged report rendering exposed a separate Windows resource-path issue:
  the extended-length `\\?\` executable path reached the Jinja template loader,
  which then failed to open the packaged `report.html.j2` resource. The native
  resource resolver now normalizes the Windows drive/UNC prefix before resolving
  bundled resources. Regression coverage exercises drive and UNC paths and loads
  a report template from a path containing spaces and Unicode. The rebuilt
  packaged backend successfully generated all four supported report formats.
- Current packaged Windows portable, unsigned NSIS installer, and local-release
  outputs were rebuilt after the final Rust change and passed strict validators.
  The Linux x86_64 package was rebuilt in Debian/WSL and passed its validator.
- A fresh-profile portable Tauri launch initialized managed PostgreSQL, started
  the backend and worker, and returned healthy `/health` and `/health/ready` plus
  release `5.0.0-rc6`. The PostgreSQL process listened only on 127.0.0.1:55432;
  generated `pg_hba.conf` uses SCRAM-SHA-256 for the loopback host rule. The
  worker heartbeat and completed native PostgreSQL jobs were observed.
- The desktop was closed gracefully and relaunched against the same isolated
  profile. Its ownership-marker hash was unchanged, PostgreSQL remained
  initialized, health/readiness/release passed again, and the isolated test user
  persisted. No `initdb` retry or data-directory replacement occurred.
- No existing operator account was used or copied from Docker/external storage.
  A temporary administrator was provisioned through
  `backend/scripts/create_admin.py`, the supported bootstrap utility, while
  public registration remained disabled. Native-auth API login, authenticated
  profile, refresh rotation, rejection of the previous refresh token, logout,
  and rejection of the revoked token all passed. Authenticated dashboard,
  investigations, Monitoring Center, host metrics, Windows process/service
  inventory, Operations Center, posture/recommendations, Change Timeline, and
  notification workflows passed. A synthetic investigation was archived after
  passive recon smoke. PDF, DOCX, HTML, and Markdown outputs were generated and
  validated for size, content type, signature/structure, RavenTech/report
  content, and secret exclusion. The passive recon smoke preserved returned
  entities and surfaced provider failures as warnings; no active scan ran.
  No credentials or tokens were written to the acceptance record.
- Full backend suite: 370 passed, 0 failed, 5 warnings. On an isolated,
  separately migrated PostgreSQL database, Alembic current and the sole head
  both report `0040_phase5bi_native_jobs`; `alembic check` reports no drift.
  Windows Cargo:
  28 passed, 1 ignored. Debian/WSL Cargo: 26 passed, 1 ignored.
- Desktop source checks passed (48/48). Frontend production build passed;
  localization passed 5/5 and monitoring tests passed 12/12. Windows Cargo:
  28 passed, 1 ignored. Debian/WSL Cargo: 26 passed, 1 ignored. PowerShell and
  Bash syntax checks passed. Current Windows portable, unsigned NSIS installer,
  and local-release packages pass their strict validators; the Linux x86_64
  package passes its strict Debian/WSL validator.
- Ruff 0.15.22, using the CI-equivalent `ruff check app workers tests` scope:
  456 findings against the accepted maximum of 457. Mypy using `mypy app
  workers`: 66 findings against 66. Focused Ruff and mypy checks report no
  findings in the changed Phase 5BN Python module or regression tests.
- Windows packaged zero-Docker acceptance passes for the automated application
  and API workflows above. Visual page inspection is the only UI sub-check
  marked NOT RUN; production embedding and equivalent authenticated API
  workflows passed. Linux clean-machine and Linux Tauri GUI acceptance remain
  NOT RUN. The WSL result is not presented as clean-machine Linux acceptance.

### Debian 13 WSL packaged Linux acceptance — 2026-09-24

- Environment: Debian GNU/Linux 13, x86_64, WSL2; systemd was PID 1 and
  system D-Bus was available. WSLg variables were present. The test ran as the
  regular Linux user, not root. No separate Linux VM or clean installation was
  available, so Linux clean-machine acceptance remains **NOT RUN**.
- Package format: the current unsigned x86_64 directory bundle, containing the
  Tauri desktop, PyInstaller backend and worker, embedded React production
  assets, and PostgreSQL 16.15 runtime. The strict Linux package validator
  passed. No DEB/RPM/AppImage installer or install/uninstall behavior is
  claimed.
- The packaged desktop executable was started from its bundle while the
  current directory was `/`, with isolated XDG config/data/state roots. It
  initialized a fresh marked managed cluster, applied migrations, started the
  packaged backend and native worker, and returned `/health` 200,
  `/health/ready` 200, and release `5.0.0-rc6`. Operations status identified
  the desktop/native PostgreSQL engine and a current worker heartbeat. The
  only database listener was loopback TCP on 55432; the generated host rule
  used SCRAM-SHA-256 and no `trust` or LAN/public rule was present.
- Authentication used only a synthetic account in that isolated database:
  login, profile, refresh rotation, old-token rejection, logout, and revoked
  token rejection passed. Dashboard, investigation listing, Monitoring,
  Operations, systemd inventory, posture, timeline, notification, and
  background-job APIs returned successfully. The read-only systemd inventory
  returned nine units. Native Linux metrics and process inventory providers
  passed their live-provider Rust tests; the backend's fallback metrics are
  explicitly container-scoped and were not represented as host metrics.
- PDF, DOCX, HTML, and Markdown reports were generated and validated for
  non-empty content, correct type/signature or container structure, RavenTech
  report content, and absence of test secrets/private paths. A passive
  authorized recon smoke against the reserved `example.com` test target
  returned entities without active scanning.
- Startup/resource defects found by this run were fixed in the Linux package
  builder/runtime: packaged PostgreSQL required its contrib extensions and
  relocated library layout; Debian startup also needed bundled library-path
  resolution and loopback-only operation without the default system Unix
  socket directory. Regression tests cover the nested resource layout,
  utility library paths, and managed stop path. The current package was rebuilt
  and its validator passed.
- Visual UI/page interaction, Linux process termination, and systemd
  start/stop/restart actions were **NOT RUN**. Process/service protection and
  normalized Linux inventory were exercised by deterministic tests; the live
  read-only systemd inventory/API was exercised without privileged actions.
  The Linux endpoint-agent executable was not present as a Linux product
  package and its live registration was **NOT RUN**. Current WSL neighbor data
  is not treated as evidence of an authorized LAN deployment.
- The packaged app's startup, ready state, authenticated workflows, and
  PostgreSQL-backed jobs were exercised in WSL. After a controlled stop of
  only the isolated test-owned processes, the packaged app relaunched with the
  same XDG profile, reused the existing cluster, and retained five synthetic
  users. A controllable Tauri window was not exposed by the WSLg window tree,
  so visual inspection and normal window-close behavior are **NOT RUN**. The
  Linux GUI and clean-machine statuses remain **NOT RUN**.

### Final Linux validation snapshot — 2026-09-24

- Full backend suite: **371 passed**, five warnings. Alembic on the isolated
  application database reported current and sole head
  `0040_phase5bi_native_jobs`; `alembic check` reported no drift.
- Linux Cargo tests: **30 passed, 1 ignored**. Windows focused Cargo regression:
  **28 passed, 1 ignored**. Desktop checks passed **53/53**; localization
  **5/5**; monitoring tests **12/12**; frontend production build, `pip check`,
  PowerShell and Bash syntax checks passed.
- Ruff 0.15.22 using the CI-equivalent `ruff check app workers tests` scope:
  **456 findings / 457 accepted**. Mypy 2.3.1 using `mypy app workers`:
  **66 findings / 66 accepted**. Focused changed-file checks passed.
- Windows portable, unsigned NSIS, and local-release validators passed. The
  current Linux x86_64 directory bundle passed its strict validator in Debian
  13 WSL. Both Docker Compose configurations parsed with configuration-only
  placeholders; Docker services were not used by the native Linux run.
- SRS PDF structural/traceability and visual checks passed: 56 pages, 154
  unique requirements (118 functional, 36 non-functional), 154 traceability
  rows, SHA-256
  `FE2446C3CFECA3EB1E154036EE24ABB2C3A210C7450DCC5D0C504DB5AD6D6237`.
  The PDF is 186,061 bytes. It records same-profile cluster reuse and data
  persistence while explicitly leaving visual GUI and normal window-close
  checks unverified.

## Safe smoke procedure

1. Use a fresh, isolated per-user data root or disposable test account; confirm
   its canonical location before launch. Do not point tests at operator data.
2. Ensure ports `8000` and `55432` are available. Make Redis and Celery
   unavailable. For the zero-Docker test, do not start Docker Compose services.
3. Launch the packaged desktop normally. Observe managed PostgreSQL, backend,
   worker, embedded UI, migrations, native jobs, and host monitoring reach Ready.
4. Sign in using a test account. Check dashboard, investigations, Monitoring,
   Operations, posture, timeline, notifications, and report/recon flows using
   non-destructive authorized test data.
5. Close the desktop normally. Confirm only its owned worker/backend/database
   stop. Relaunch and verify the isolated test database persists.
6. Record results and sanitized evidence outside the package. Do not collect
   passwords, tokens, full credential-bearing URLs, or database contents.

## Failure checks

Use tests/mocks for failure injection. Verify missing PostgreSQL resources,
unknown database directories, occupied ports, migration errors, missing child
artifacts, startup failures, and permission errors display bounded safe reasons.
Do not corrupt a real database, kill unrelated processes, or auto-delete data.

## Clean-machine preparation

### 5BO — Windows

- Use a disposable Windows 10/11 x64 machine/account with WebView2 and no source
  checkout, Docker, Python, Node, PostgreSQL, Redis, or Celery installed.
- Transfer only the current unsigned installer or portable artifact and verify its
  manifest/checksum before launch.
- Install/launch as the current user; verify first run, login, refresh/logout,
  monitoring, native jobs, reports, shutdown, relaunch, and persistence.
- Confirm no terminal prompt, repository path, Docker Desktop, Redis, Celery, or
  external PostgreSQL is requested. Record OS/build and sanitized outcomes.

### 5BP — Linux

- Use a disposable supported Linux x86_64 VM/install, not WSL. Install only the
  documented shared-library prerequisites and desktop environment.
- Transfer the current Linux package and verify manifest/checksums.
- Verify executable permissions, XDG config/data/state paths, startup, login,
  backend/worker/managed PostgreSQL, monitoring, native jobs, shutdown, relaunch,
  and persistence without Docker/Python/Node/Redis/Celery.
- Record distribution/version and any remaining package dependency gaps.

Clean-machine acceptance is not claimed by this Phase 5BN record unless those
separate machines are actually used. Future Knowledge/Obsidian ingestion is not
implemented here.

## Windows isolated install and SRS delivery — 2026-09-24

### Windows installation and packaged runtime

- Clean Windows Sandbox/VM capability was unavailable on this host. Windows
  clean-machine acceptance remains **NOT RUN**. The strongest available check
  was an isolated Windows install using the current unsigned RC6 NSIS package,
  a fresh temporary per-user data profile, and a working directory outside the
  repository. Docker services, Redis, Celery, Python, Node/Vite, and manual
  backend/worker/PostgreSQL launch were not used by the packaged app.
- The first current NSIS install exposed a real resource-map defect. Tauri's
  recursive wildcard-to-directory mapping flattened nested runtime files in
  the installer. The PostgreSQL tree first lacked the expected `bin` sibling
  layout; after that tree was corrected independently, packaged backend
  validation exposed the flattened `pydantic_core` extension. The installer
  builder now maps every regular file to its exact relative destination for the
  backend, worker, and PostgreSQL trees. It rejects unsafe paths, empty trees,
  symlinks, and unsupported entries. Three deterministic resource-map tests
  cover PostgreSQL `bin/lib/share`, nested backend extension modules, worker
  modules, empty sources, and unsafe destinations.
- The rebuilt installer manifest and strict validator passed. A fresh install
  contained the backend and its ABI-specific `pydantic_core` extension, worker,
  and PostgreSQL `bin`, `lib`, and nested `share` resources. The installed
  backend reported version `5.0.0-rc6` and `--check` passed. The installed Tauri
  app initialized its owned PostgreSQL 16 cluster, reached backend health and
  readiness HTTP 200, reported release `5.0.0-rc6`, and exposed healthy native
  worker state. `/health` reported Redis and Celery as `not_required` and the
  Operations Center engine as `native`.
- A random temporary bootstrap administrator passed login, authenticated
  profile and admin RBAC, refresh rotation, rejection of the old refresh token,
  logout, and rejection of the revoked token. Dashboard and executive surfaces,
  investigations, members, notes, tasks, local analysis/Knowledge search,
  passive recon, reports, Monitoring Center, LAN assets, endpoint agents,
  posture, vulnerabilities, policies/baselines, maintenance windows, alerts,
  notifications, correlations, timelines, and Operations Center API checks
  passed. Recon used only the reserved `example.com` passive smoke path and
  returned partial results with provider warnings. PDF, DOCX, HTML, and Markdown
  downloads were non-empty, had the expected MIME/signature or structure, and
  contained expected RavenTech/report content without test credentials.
- Graceful desktop shutdown stopped its owned worker, backend, and PostgreSQL;
  the managed port stopped listening. Relaunch returned to health/readiness
  HTTP 200 and reused the existing cluster. `PG_VERSION` remained unchanged and
  the isolated acceptance investigation remained present. Normal NSIS
  uninstallation removed the isolated installation directory and executable
  while preserving the per-user database, ownership marker, and credential
  file. Reinstalling the same current installer and launching against that
  profile again returned to Ready and preserved the acceptance record without
  repeating `initdb`. The installed UI was launched, but independent visual
  inspection was **NOT RUN** because native-window automation was unavailable.
- The final NSIS bundle passed the unsigned local installer validator. Portable
  and local-release validators passed, and the Linux x86_64 package passed its
  strict validator in Debian/WSL. The unsigned NSIS installer is 368,681,240
  bytes with SHA-256
  `75f89cb1b262f3f8b5b12aecdb031e309a5ff39ae188dd24c01ee1678cbe5125`.
  The Linux package validator ran on Linux; no Linux clean-machine or Linux
  Tauri GUI claim is made.

### Regression and document delivery

- Full backend suite: **370 passed**, five existing warnings. The initial test
  attempt shared a database with a live native worker, which claimed a test job;
  the suite was rerun against an isolated package-managed PostgreSQL cluster
  with the desktop and worker stopped and then passed. The system PostgreSQL 18
  service remained running and untouched.
- Alembic on the live isolated managed database: current and sole head are
  `0040_phase5bi_native_jobs`; `alembic check` reports no drift. Desktop JS
  checks pass **51/51**. The current NSIS resource-map tests pass **3/3**.
  Frontend localization passes **5/5**, monitoring tests pass **12/12**,
  Windows Cargo tests pass **28/28** with one ignored live-PostgreSQL fixture,
  and Debian/WSL Cargo tests pass **26/26** with the same fixture ignored.
- The Spanish SRS source is
  [`docs/srs/RavenTech_OSINT_SRS_ES.md`](docs/srs/RavenTech_OSINT_SRS_ES.md);
  its delivery PDF is
  [`docs/deliverables/RavenTech_OSINT_SRS_v1.0_ES.pdf`](docs/deliverables/RavenTech_OSINT_SRS_v1.0_ES.pdf).
  The PDF is 56 pages and 185,340 bytes, containing 154 requirements (118
  functional, 36 non-functional) and 154 matching traceability rows. Structural,
  requirement-ID, traceability, version, page-number, secret, private-path, and
  product-history validation passed. Visual QA passed on the cover, contents,
  architecture diagram, functional requirement table, traceability matrix,
  glossary, and final page; no clipping or broken Unicode was observed. SHA-256:
  `c5aa92af515536258f48a4cd363bb7d605ea6ff4f6a0d812552adada3ad84c5b`. The
  README links the professional product specification and contains no internal
  milestone, prompt, or agent-tool chronology.
- Windows clean-machine acceptance remains **NOT RUN**; Linux clean-machine and
  Linux GUI acceptance remain **NOT RUN**.

## Local Knowledge acceptance

Knowledge source support uses an authenticated selected-file snapshot and the
native PostgreSQL worker. The accepted design does not store the original
vault's absolute path or monitor it in the background. Administrators can
review trust and verification metadata, synchronize selected file updates, and
remove the managed copy/index without deleting originals. Search and citation
are local; imported content is not automatically added to reports or uploaded
to external AI services. See [LOCAL_KNOWLEDGE.md](LOCAL_KNOWLEDGE.md) for the
operational behavior and snapshot limitations.

Synthetic fixtures cover Markdown/frontmatter/tags, PDF/DOCX/HTML/TXT/JSON/CSV,
Obsidian links and bounded embeds, hashes, incremental reconciliation, source
removal, path/symlink containment, search filters, trust metadata, explicit
report citations, and Operations Center counters. A live operator vault was
not accessed.
