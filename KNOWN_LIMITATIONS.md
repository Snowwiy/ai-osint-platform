# RavenTech OSINT Known Limitations

The completed validated mode for `5.0.0-rc3` is the local web application using
Docker Compose services and a local Vite frontend. Desktop packaging, installers,
hosting, deployment, DNS, and Supabase migration are deferred.

## Product Boundaries

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
variables, PostgreSQL, Redis, and frontend development commands run from the
`frontend/` directory.

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
