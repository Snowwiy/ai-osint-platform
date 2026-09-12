# RavenTech OSINT Known Limitations

The completed validated mode for `5.0.0-rc6` includes the local web application
and private Tauri artifacts. Browser/development mode uses local Vite; portable
and installed builds embed the same React production assets. Portable and unsigned
installer workflows are local-test aids; signed production packaging, hosting,
deployment, DNS, and Supabase migration are deferred.

Phase 5AL includes a Tauri source prototype, not a validated desktop package.
It depends on separately running local Docker/backend services. Port 5173 is a
development fallback only; release artifacts do not require it.
Its help buttons copy commands only and cannot start or repair services.

Phase 5AM improves local runtime feedback but does not turn the shell into a
service supervisor. It can distinguish unreachable, degraded, and ready states
only from its fixed HTTP probes. Operators must still use Docker/Vite terminals
and platform logs for diagnosis, and must run copied commands themselves.

Phase 5AN produces an unsigned Windows portable local-test executable. It is not
an installer, supported deployment, or self-contained application: WebView2,
the repository, local configuration, and Docker/backend services remain
separate prerequisites. The frontend is embedded. The repository-owned local-candidate icon is not public
brand approval or a signed release identity.
The generated `dist-portable/` folder is ignored and must not be published as a
release artifact without a later signing, provenance, and clean-machine review.

Phase 5AO adds an unsigned NSIS current-user installer workflow. It installs only
the shell and is expected to trigger Windows SmartScreen warnings. It requires
WebView2 to be installed separately, does not start services, and remains
dependent on the repository, Docker stack, and configuration, but not Vite.
The ignored `dist-installer/` output is not a trusted or public release. Signing,
timestamping, auto-update, firewall distribution policy, and full clean-machine
compatibility testing remain deferred.

The RC6 setup wizard can report fixed local signals, but it cannot guarantee
that Docker Desktop is healthy when its backend is offline, diagnose third-party
firewall policy, install prerequisites, change ports, or repair migrations. It
provides manual bilingual guidance and copy-only recovery in those cases.

Phase 5AP adds local artifact smoke checks and consistent distribution naming,
but it does not make the package self-contained or production-ready. Phase 5AT
adds an original RavenTech shield/radar asset. Installer launch checks on one development host
do not replace clean-machine, Windows-version, endpoint-security, accessibility,
upgrade, and uninstall matrix testing.

Phase 5BC can orchestrate only six fixed scripts. Phase 5AR can store one
validated per-user project-path preference, but it does not search the whole
computer or provide a folder browser. A moved, deleted, or incomplete repository
must be rebound manually; otherwise the launcher falls back to copied guidance.
Docker detection may say "not detected" for non-standard installations. Port
checks identify RavenTech, another listener, or an available/non-listening port,
but never reconfigure it. A launcher timeout stops waiting and
requests a status check; external Docker work already accepted by Docker may
finish independently. The launcher is not a service supervisor. Its Vite helper
is copy-only and is relevant only to browser/development mode.

Phase 5AV supplies operator and private-handoff documentation only. It does not
turn documentation review into clean-machine certification, provide support or
update infrastructure, or expand the installed shell's removal boundary. The
operator acceptance checklist must be executed on each authorized Windows test
environment; completed records can contain operational context and therefore
remain outside Git and distribution artifacts.

Phase 5AW dry-run checks improve reproducibility evidence but do not guarantee
all clean Windows hosts, Docker Desktop versions, WebView2 policies, endpoint
security products, or organizational controls. Each receiving environment still
requires the private operator acceptance checklist. RC6 remains unsigned and
local-only with a separately managed repository and Docker/backend stack.

Phase 5AX provides receiving-machine transfer and recovery guidance, not remote
support or automated repair. Artifact success on the build host does not prove
compatibility with another host's Windows policy, WebView2 runtime, Docker
configuration, endpoint protection, ports, or user permissions. The receiving
operator must verify checksums and complete the external-machine checklist.

## Product Boundaries

- RC6 provides English and Spanish UI/report labels. Uncommon dynamic provider,
  evidence, or analyst-authored prose can remain in English; missing localized
  copy falls back to English and never exposes raw translation keys.

- Passive, defensive OSINT investigation workflow only; no generalized active
  scanning or Nmap integration. Separately enabled LAN monitoring performs only
  bounded private-network ICMP/TCP connectivity observations.
- No exploitation, attack automation, or offensive workflow.
- No internet-wide enumeration or crawler.
- No autonomous agents, unattended remediation, or autonomous offensive
  actions.
- No external SSO, billing, or managed cloud deployment.
- No external paid threat feeds are required or bundled.
- No cloud deployment implementation is included in the release candidate.
- Production hosting and DNS configuration remain deferred until after final
  platform review.
- Local Docker Compose is the current tested operating mode. Production and
  free-tier hosting have not been validated.
- The production database has not been migrated to Supabase.
- Notifications are internal Activity Inbox records only. Email, SMS, browser
  push, and chat integrations are not included.
- Global Search is internal-only and database-backed. It does not use external
  search providers, crawl the web, or perform internet-wide discovery.
- LAN monitoring is disabled by default, limited to explicitly configured
  private RFC1918 IPv4 ranges, and is not an internet or vulnerability scanner.
- The vulnerability baseline is deterministic and uses stored observations; it
  does not identify service versions, query CVE feeds, scan for flaws, validate
  exploits, or prove compromise. Its risk indicators require analyst review.

## Monitoring history

- The timeline starts collecting after migration `0033_phase5ac_history`; it
  does not reconstruct transitions from older Phase 5AB rows.
- Offline and stale-agent changes are evaluated when monitoring summaries or
  timeline endpoints run. This local release has no always-on external monitor.
- TCP status and service names are observations and bounded guesses, not proof
  of service identity, compromise, CVEs, or exploitability.
- Docker may not expose host neighbor tables. Static/router observations or the
  optional endpoint agent are still required for complete host-LAN visibility.
- Monitoring history remains local. No hosting, deployment, public scanning,
  DNS automation, or Supabase migration is included.
## Authentication And User Governance

The platform uses its own backend authentication model. Public registration is
configuration-gated and defaults to disabled. Registered users may require admin
approval before they can sign in, and account approval does not replace
organization-specific identity review.

The current platform role model remains intentionally small: admin and analyst
at the platform level, with viewer-style access handled through investigation
membership. External SSO/OAuth and Supabase Auth migration are intentionally not
included.

## Engagement And Scope Governance

Engagements are lightweight governance records for client metadata,
authorization status, approved scope items, and authorization evidence
references. They are not billing records, tenant boundaries, a hosted client
portal, or legal document storage.

Scope checks are deterministic and local. They support exact values, conservative
domain/subdomain matching, exact IP matching, and CIDR matching. They do not
perform DNS resolution, active probing, crawling, scanning, or external
enrichment. Unknown values are marked pending review by default.

Out-of-scope handling is warning-first unless an operator explicitly enables a
blocking governance policy.

## Case Closure And Deliverables

Case closure is a review workflow, not a legal sign-off system or client portal.
Deliverables are tracked as application records and package manifests. The
platform does not upload, host, email, or externally deliver final packages.

Evidence package manifests summarize stored evidence, findings, reports,
authorization status, and warnings. They do not duplicate all raw report files
or create external storage. Analysts remain responsible for final client
handoff review.

## Notifications

The Notification Center is designed for internal workflow visibility. It stores
alerts for approvals, assignments, reports, closure, scope, and governance in
the database. It does not deliver messages outside the application, and it is
not a replacement for an enterprise incident-management or ticketing platform.

## Provider Availability

Some enrichment and AI capabilities require separately configured provider
credentials. Missing credentials return an unavailable or degraded status and
must not prevent deterministic investigation workflows.

AI analysis is optional. When the configured provider key is missing, disabled
by feature flag, or returns an error, the application should display a clear
degraded state and preserve deterministic evidence-backed fallback content.

External provider results may be incomplete, rate limited, delayed, or
unavailable. Partial passive recon can still preserve valid evidence.

## Demo Data

Demo mode is intended for local or controlled demonstrations. It is disabled by
default and ignored by environment bootstrapping in production. The bundled
sample data is synthetic, uses reserved identifiers, and must not be presented
as a real incident or compromise.

Demo records are labeled with `[DEMO]`, can be seeded idempotently, and can be
cleared through the admin endpoint or local script. Demo data is synthetic and
should not be mixed into real client evidence unless a reviewer intentionally
uses it in a training environment.

## Knowledge Retrieval

Knowledge Search uses only locally curated and indexed content. It does not
browse the internet. Search quality depends on the available local documents
and their indexing state.

## Global Search And Saved Views

Global Search searches safe fields from accessible internal records only.
Results depend on RBAC, investigation membership, and stored application data.
It is not a replacement for an enterprise search appliance and intentionally
does not index secrets, password hashes, invite codes, raw credentials,
authorization headers, database URLs, or provider keys.

Saved views store user-specific filter preferences and routes. They do not
share filters across users by default and should not be used to store sensitive
notes or credentials.

## Data Quality Checks

The Data Quality Center uses bounded deterministic checks over stored records.
It can flag likely duplicates, stale workflow items, missing evidence, invalid
internal routes, configuration risks, and cross-workflow inconsistencies, but
it does not prove that records are semantically identical or legally complete.

No automatic destructive cleanup is included. Administrators must review and
correct source records through governed workflows. Notification maintenance is
limited to explicit soft archive of old read or dismissed items.

## Reporting

Report quality depends on stored findings, notes, evidence, remediation data,
and framework mappings. Readiness warnings are advisory and do not guarantee
that a report is complete for a specific regulatory or legal purpose.

All reports and exported deliverables require analyst review. Generated content
must not be treated as autonomous approval, legal sign-off, or a verified claim
of compromise.

PDF and DOCX rendering can vary slightly by viewer. Organization-specific legal
language, classification markings, and branding require administrator review.

## Operations

- Local launcher scripts are Windows-friendly wrappers around Docker Compose and
  local HTTP probes. They intentionally do not remove volumes, reset databases,
  or expose environment values. The in-app Operator Console is read-only;
  command buttons copy text for a human operator and do not execute host actions.
- The optional Tauri shell can open the local frontend and check fixed backend
  endpoints. Its portable executable and unsigned installer are validated only
  as local-test candidates; they are not signed or publicly distributed.
  Browser mode remains the recovery path.
- Installed and portable artifacts embed frontend assets. Vite/5173 remains an
  optional development path, not a release runtime dependency.
- The local frontend runs inside a constrained frame. Popups and top-level
  navigation are disabled; workflows that later require either behavior must
  receive a separate security and UX review.

- Platform health is degraded only when required dependencies fail. Missing
  optional host-agent telemetry and Docker neighbor visibility are labeled as
  informational coverage limitations while core workflows remain healthy.
- Monitoring is local, pull-based, and active only while a client polls the
  authenticated endpoints. It is not an external uptime monitor or durable
  observability system.
- Default system metrics describe the backend container and may be estimates.
  Full Windows host metrics require the optional localhost-only PowerShell agent.
- Only the latest accepted host-agent sample is retained in backend memory; it
  is cleared on restart and considered stale after ten minutes.
- Docker status is intentionally limited because the backend does not mount the
  Docker socket. Use `docker compose ps` for authoritative container state.
- Docker Desktop may not expose the Windows neighbor table or ICMP utility to
  the backend. LAN discovery can therefore return no observations; router/static
  observations or the optional manual endpoint agent are the supported fallback.
- LAN online/offline state is observation-based and can be affected by endpoint
  firewalls, sleeping devices, container routing, and the selected interval.
- Service observations are bounded TCP connectivity indicators only. They do
  not identify versions, prove vulnerability, authenticate, or validate CVEs.
- Endpoint enrollment uses administrator-created, hashed, expiring local
  credentials with optional private-CIDR and enrollment-count limits. It is not
  a remote fleet-management service: agents run manually and install no
  persistence, autostart, shell, or command channel.
- Monitoring alerts are deterministic snapshots with daily per-user
  deduplication in the internal Activity Inbox. They do not send email, SMS,
  push messages, webhooks, or run automated remediation.
- Asset criticality and remediation ownership are operator-maintained context;
  the platform does not automatically know business impact or complete fixes.
- Worker readiness verifies broker reachability, not full job throughput.
- Retention policies mark archive eligibility; they do not automatically
  destroy records.
- Soft archive is used to preserve investigation history and auditability.
- Frontend pages are split into route-level bundles. The initial production
  bundle remains a shared application shell rather than a minimal static page,
  but it no longer triggers the configured Vite chunk-size warning.
- The current password hashing dependency emits an upstream Python deprecation
  warning for the standard-library `crypt` module. It does not affect the Python
  3.12 release-candidate runtime, but the hashing dependency must be reviewed
  before a future Python 3.13 upgrade.
- The frontend remains on React Router 6 during the RC3 freeze. `npm audit`
  reports two moderate advisories whose available automated fix requires the
  breaking React Router 7 migration. This client-rendered application does not
  use React Router SSR hydration, and dynamic application routes are constrained
  to safe internal paths, but the major upgrade must be planned and retested in
  a separately authorized post-freeze phase.
- A local environment without `REPORT_LOGO_PATH` emits a configuration advisory
  and uses text branding for report exports.

## Validation Responsibility

Before any future production use, operators should complete the RC3 final QA
checklist, verify database migrations, configure backups, review secrets and
CORS, confirm export controls, and validate organization-specific RBAC and
retention policy. Public registration must remain governed through explicit
enablement, invite/approval policy, and administrator review.

The documented local deployment assumes Docker Compose, local environment
variables, PostgreSQL, and Redis. Frontend commands from `frontend/` are needed
for browser/development mode or rebuilding, not prebuilt desktop runtime.

## Phase 5AG completion boundary

Local Docker Compose is the only validated product mode. LAN discovery and TCP
service checks remain disabled until explicitly enabled in local configuration,
and Docker Desktop may not expose host neighbor data. Target service checks
require an exact match to an existing authorized, monitored private LAN asset;
they do not resolve or scan public targets.

Recon provider warnings can coexist with valid stored entities. They describe
partial enrichment availability, not invalid evidence or a confirmed security
issue. Port observations, SSH hints, and baseline results are advisory risk
indicators only. Desktop packaging, installers, hosting, deployment, DNS work,
and Supabase migration remain outside the validated scope.

## RC3 acceptance boundary

RC3 freezes the local web application without adding a module or migration.
Authorized service observations remain TCP-connect only, and all monitoring and
baseline risk indicators remain advisory rather than exploit validation. The
release makes no desktop-package, hosted-service, or production-deployment claim.

## Endpoint posture limitations

- Patch status is coarse awareness from locally available timestamps/hotfixes;
  it does not prove complete applicability or compliance.
- Firewall and antivirus status depend on safe, non-privileged platform APIs and
  may be unknown or unavailable, especially on Linux.
- Listening port numbers are local observations and do not prove service identity,
  exploitability, exposure beyond the host, or compromise.
- Scores and remediation items are deterministic advisory risk indicators that
  require owner validation and normal change control.
- Block and isolation steps are manual guidance. No router connection,
  credential use, policy change, VLAN action, or automatic block is implemented.

## Automatic monitoring limits

- Monitoring status loads after authentication and refreshes while a client is
  open. It is not a background Windows service and stops when all clients close.
- LAN discovery-on-start and TCP-check-on-start are disabled by default. Enabling
  either still requires the parent flag and all approved private-CIDR, host,
  port, timeout, policy, maintenance, cooldown, and dedupe constraints.
- Missing endpoint telemetry and Docker host-neighbor visibility are optional
coverage limitations, not platform-health failures.

## LAN bootstrap limits

- `192.168.50.1` is a hint only; RavenTech does not verify, connect to,
  administer, scrape, or reconfigure the router.
- Bootstrap verification never proves complete LAN coverage and never starts
  discovery or service checks itself.
- `http://192.168.50.201:8000` is guided private-backend input, not automatic
  host-IP detection. Confirm it and restrict firewall access to the private CIDR.
- Manual observations are operator-supplied evidence requiring owner,
  authorization, and accuracy review.

## Phase 5BA limitations

- Native metrics are Windows desktop-only and show the system drive rather than
  enumerating every volume. Browser mode relies on manual host-agent telemetry.
- `ServerHost` and `LanEndpoint` helpers are foreground/manual processes with no
  persistence, automatic restart, service installation, or autostart.
- The backend's Docker metrics describe only the container and are intentionally
  labeled as fallback. Missing host telemetry remains informational.
- LAN agent reachability may require an operator-created firewall rule restricted
  to `192.168.50.0/24`; RavenTech does not modify firewall or system settings.

## Phase 5BB acceptance limits

- Runtime timestamps reflect stored audited actions, not proof of complete LAN coverage.
- Manual router/static observations depend on operator accuracy and do not establish
  router connectivity or continuous device presence.
- Enrollment agents remain foreground-only; loss of a heartbeat is an advisory
  freshness condition, not automatic evidence of compromise.
- TCP results are point-in-time connect observations on configured ports and cannot
  prove service safety, identity, authentication state, or exploitability.

## Phase 5BC activation limits

- The activation script applies only the fixed `192.168.50.0/24` profile; it is not
  a general settings editor and accepts no keys, values, paths, or commands.
- Timestamped `.env` backups may contain pre-existing secrets and therefore remain
  local and Git-ignored; the desktop displays only their filename.
- Configuration changes require a separately confirmed Compose restart. The script
  does not start discovery, service checks, endpoint agents, or Docker.
- ServerHost/LanEndpoint tests remain manual foreground processes with no persistence,
  service installation, scheduled task, or automatic recovery.
