# RavenTech OSINT Portfolio Demo Flow

This locked RC3 walkthrough is designed for a roughly ten-minute interview,
GitHub, portfolio, or local client-style demonstration. Use only synthetic demo
data and describe the platform as a locally validated release candidate—not a
hosted production service.

## 1. Login

Show the branded login and sign in as the existing demo administrator.

Say: “RavenTech OSINT is a defensive investigation workspace for authorized,
passive evidence collection, analysis, remediation, and reporting.”

Proves: authentication, clear error handling, defensive positioning.

## 2. Dashboard

Show operational posture, prioritized work, recent investigations, and Quick
Access. Briefly open Executive Dashboard or Operations Center if time permits.

Proves: analyst and stakeholder visibility, safe degraded states, navigation.

## 3. Demo Investigation

Open `[DEMO] Authorized External Exposure Review`. Point out its synthetic label,
authorization statement, owner, members, workflow state, and investigation tabs.

Proves: governed case record, ownership, authorization, lifecycle context.

## 4. Engagement And Scope

Open the linked demo engagement. Show authorization status, approved domain/CIDR
scope, evidence references, and a conservative warning for unknown scope.

Say: “Scope matching is deterministic and local; it performs no DNS lookup,
probing, crawling, or scanning.”

Proves: client context, authorization evidence, safe scope governance.

## 5. Recon And Findings

Show authorized synthetic targets, stored passive recon entities, partial-source
handling, and a deterministic evidence-backed finding with severity, confidence,
remediation, and ownership.

Proves: evidence normalization and analyst-reviewed defensive findings.

## 6. Correlations And IOCs

Switch through Correlations Cards, Graph, and Table, then show IOC, Evidence
Intelligence, or Threat Intelligence relationships.

Say: “These views correlate stored internal evidence; they do not perform
internet-wide discovery or unsupported attribution.”

Proves: cross-record reasoning, relationship UX, defensive intelligence scope.

## 7. AI Fallback

Show AI Analysis with the provider unavailable or disabled. Keep the degraded
message and deterministic fallback/citations visible together.

Proves: optional provider integration, graceful failure, evidence grounding.

## 8. Reports

Open a report template/readiness view and an existing executive or technical
report. Show allowed PDF, DOCX, HTML, and Markdown export controls.

Say: “Reports are generated from stored evidence and always require analyst
review; readiness warnings are advisory.”

Proves: stakeholder output, citations, governance-aware export.

## 9. Closure And Deliverables

Show closure checklist, review/approval status, residual risk, deliverable list,
and evidence package manifest. Explain that overrides require an authorized role
and a recorded reason.

Proves: controlled handoff, review trail, manifest consistency.

## 10. Notifications And Search

Open Activity Inbox, mark a synthetic alert read, then use Ctrl+K Global Search
and a pinned Saved View to navigate to an authorized record.

Proves: internal workflow awareness, RBAC-aware search, owner-scoped shortcuts.

## 11. Data Quality

Open Admin > Data Quality. Show the bounded scan summary, one safe issue detail,
and its acknowledge/resolve workflow. Prefer Dry run during a live presentation.

Say: “Quality checks recommend review; they do not automatically delete or
rewrite source records.”

Proves: deterministic maintenance, safe metadata, admin permissions.

## 12. Audit And Governance

Finish with Audit Log, Admin Settings, feature/export controls, and the release
or Operations panel. Confirm `5.0.0-rc4`, current migration, and healthy local
checks without exposing secrets.

Proves: accountability, configuration boundaries, release validation.

## Closing Statement

“This RC3 build is validated locally with Docker Compose and a deterministic
test suite. Hosting, DNS, and production database migration are intentionally
deferred. The platform excludes active scanning, exploitation, payloads,
crawling, and autonomous offensive actions.”

## Presenter Guardrails

- Use only bundled synthetic data and reserved identifiers.
- Keep optional provider keys empty unless a controlled demo explicitly needs
  one; never show keys or environment files.
- Do not enter real targets without written authorization.
- Do not claim production hosting, live compromise, autonomous action, legal
  sign-off, SLA, or compliance certification.
- If a provider is unavailable, demonstrate the fallback rather than changing
  configuration during the walkthrough.
- Follow `SCREENSHOTS_CHECKLIST.md` for portfolio captures and
  `FINAL_LOCAL_ACCEPTANCE.md` before presenting.
