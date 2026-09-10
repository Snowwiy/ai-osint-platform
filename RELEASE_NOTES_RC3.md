# RavenTech OSINT 5.0.0-rc3

## Summary

RC3 freezes RavenTech OSINT as a completed local web release candidate. It
incorporates the monitoring, authorized LAN, endpoint-agent, target/recon,
alert, reporting, and local QA work completed since RC2 without adding a new
feature module or changing the deployment boundary.

## Changes since RC2

- Added safe monitoring policies, alert cooldown/dedupe controls, explicit
  suppressions, and auditable maintenance windows.
- Corrected platform health so optional host telemetry and Docker LAN visibility
  do not masquerade as required-service failures; recovered alerts retire.
- Added authorized, disabled-by-default, bounded TCP service observations with
  service history and standard/non-standard SSH hints.
- Added monitoring change history, acknowledgements, alert triage, and preserved
  notification/audit history.
- Added hashed one-time-reveal endpoint enrollment credentials, agent inventory,
  asset groups, expected-service baselines, and coverage summaries.
- Added a read-only monitoring activation guide and safe manual agent command
  builders.
- Polished target eligibility, service-observation separation, partial recon
  warnings, valid-entity preservation, safe retry, and last-successful-result UX.
- Completed local regression and visual QA across authentication, core
  workflows, monitoring, reports, notifications, search, data quality, and audit.

## Security posture

Monitoring is authorized and local. Service checks are manual, rate limited,
private/scope constrained, configurable, and TCP-connect only. SSH detection
uses a minimal sanitized hint. The platform performs no public scanning,
credential testing, brute force, remote commands, exploit payloads, or exploit
validation. Baseline results are advisory risk indicators, not confirmed
vulnerabilities.

Enrollment plaintext is returned only at create/rotate time and is not listed,
logged, or persisted in plaintext. Agents collect limited system telemetry and
provide no remote shell, persistence, file collection, password collection,
browser-history collection, or keystroke collection.

## Validation proof

The RC3 release gate completed on 2026-09-10: ruff passed; strict mypy passed
across 214 source files; all 272 pytest tests passed with one documented upstream
Passlib deprecation warning; `pip check` found no broken requirements; Alembic
reported no new upgrade operations; health, readiness, and release returned HTTP
200; and the frontend TypeScript/Vite production build passed. Diff review and
clean Git synchronization are release-handling gates.

Expected metadata:

- Version: `5.0.0-rc3`
- Channel: `release-candidate`
- Migration head: `0035_phase5ae_agents`
- Validated runtime: local Docker Compose plus local Vite frontend

## Limitations and deployment status

Docker LAN visibility can be incomplete, passive providers can fail partially,
and optional host telemetry requires a manually run enrolled agent. Valid stored
recon entities survive provider warnings. Reports and advisory indicators require
analyst review.

RC3 includes no desktop packaging, Electron, Tauri, installer, hosting,
deployment, DNS, or Supabase migration. It makes no production-deployment claim.
