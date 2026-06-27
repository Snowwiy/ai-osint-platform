# RavenTech OSINT Known Limitations

## Product Boundaries

- Passive recon only; no active scanning or Nmap integration.
- No exploitation, attack automation, or offensive workflow.
- No internet-wide enumeration or crawler.
- No autonomous agents or unattended remediation.
- No external SSO, billing, or managed cloud deployment.
- No external paid threat feeds are required or bundled.
- No cloud deployment implementation is included in the release candidate.

## Authentication And User Governance

The platform uses its own backend authentication model. Public registration is
configuration-gated and defaults to disabled. Registered users may require admin
approval before they can sign in, and account approval does not replace
organization-specific identity review.

The current platform role model remains intentionally small: admin and analyst
at the platform level, with viewer-style access handled through investigation
membership. External SSO/OAuth and Supabase Auth migration are intentionally not
included.

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

## Reporting

Report quality depends on stored findings, notes, evidence, remediation data,
and framework mappings. Readiness warnings are advisory and do not guarantee
that a report is complete for a specific regulatory or legal purpose.

PDF and DOCX rendering can vary slightly by viewer. Organization-specific legal
language, classification markings, and branding require administrator review.

## Operations

- Health checks can report optional services as degraded while core workflows
  remain available.
- Worker readiness verifies broker reachability, not full job throughput.
- Retention policies mark archive eligibility; they do not automatically
  destroy records.
- Soft archive is used to preserve investigation history and auditability.
- The frontend production bundle currently produces a non-blocking Vite chunk
  size warning and has not yet been split into route-level bundles.

## Validation Responsibility

Before production use, operators should complete the manual QA checklist,
verify database migrations, configure backups, review secrets and CORS, confirm
export controls, and validate organization-specific RBAC and retention policy.

The documented local deployment assumes Docker Compose, local environment
variables, PostgreSQL, Redis, and frontend development commands run from the
`frontend/` directory.
