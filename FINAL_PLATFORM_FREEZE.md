# RavenTech OSINT Final Platform Freeze

## Freeze identity

- Version: `5.0.0-rc3`
- Validated parent baseline: `df0b1b5` (`fix: complete local monitoring and target workflow polish`)
- Branch: `dev`
- Release tag: `v5.0.0-rc3`, created only after the RC3 validation gate passes
- Validated mode: local Docker Compose backend services with a local Vite frontend
- Database migration head: `0035_phase5ae_agents`

Phase 5AH freezes the completed local web application. It adds no product
module, migration, provider, desktop wrapper, installer, hosted environment,
DNS configuration, or Supabase integration. Only release metadata,
acceptance documentation, and validation-blocking regression fixes are allowed.

## Frozen product surface

- Authentication, config-gated registration, RBAC, investigation membership,
  and administrator user governance
- Dashboard, Operations Center, investigations, targets, passive recon,
  findings, correlations, IOCs, intelligence, notes, tasks, and bookmarks
- Engagement authorization and deterministic scope governance
- Review, remediation, closure, deliverables, and audit workflows
- Analyst-reviewed HTML, Markdown, PDF, and DOCX report exports
- Internal notifications, alert triage, Global Search, Saved Views, Data Quality
  Center, settings, feature flags, health, readiness, and release metadata
- Local Monitoring Center with policies, maintenance windows, change history,
  advisory baseline indicators, authorized LAN inventory, endpoint enrollment,
  asset groups, coverage, and bounded TCP service observations

## Security and monitoring boundary

Monitoring is local and authorized. LAN discovery and service checks are
disabled by default, private-range constrained, manually initiated, rate
limited, and TCP-connect only. SSH recognition uses a minimal sanitized banner
hint and never authenticates, tests credentials, executes commands, brute
forces, sends exploit payloads, or validates vulnerabilities.

Endpoint agents enroll with administrator-managed hashed credentials whose
plaintext is revealed once. Agents collect limited system telemetry and have
no persistence, autostart, remote shell, command channel, file collection,
browser-history collection, keystroke collection, or credential collection.

Risk and vulnerability-baseline entries are advisory indicators derived from
stored observations. They are not CVE claims, proof of compromise, or exploit
validation and require analyst review.

## Acceptance gate

The authoritative automated and manual gate is `FINAL_QA_CHECKLIST.md`. The
resulting proof belongs in `FINAL_LOCAL_ACCEPTANCE.md` and
`RELEASE_NOTES_RC3.md`. A failing required check blocks commit, push, and tag
creation.

The Phase 5AH automated gate completed on 2026-09-10: ruff passed; strict mypy
passed across 214 source files; 272 pytest tests passed; `pip check` and Alembic
schema checks passed; health, readiness, and release returned HTTP 200; and the
frontend TypeScript/Vite production build passed. The only test-suite warning is
the documented upstream Passlib/Python `crypt` deprecation.

Expected release responses after the local backend is recreated:

- `/health`: `status: ok`
- `/health/ready`: `status: ok`
- `/api/v1/release`: version `5.0.0-rc3`, channel `release-candidate`, migration
  `0035_phase5ae_agents`, and no secrets

## Known non-blocking limitations

- Docker Desktop may not expose host neighbor tables; approved static/router
  observations or a manually run endpoint agent provide additional coverage.
- Passive providers can time out, reject requests, or return malformed data;
  stored valid entities remain usable and provider warnings are retriable.
- Optional host telemetry absence does not degrade healthy required services.
- The upstream password-hashing dependency emits a Python `crypt` deprecation
  warning that must be reviewed before a future Python 3.13 upgrade.
- React Router 6 remains frozen; any major dependency upgrade requires a
  separately authorized and fully validated phase.
- Missing local report branding falls back to text branding.

## Deferred work

- Desktop packaging, Electron, Tauri, native installers, and autostart
- Free-tier or production hosting and deployment
- Public DNS and ingress configuration
- Supabase database or authentication migration
- Public or internet-wide scanning and any offensive capability

This freeze is a completed local release candidate, not a production deployment
claim. Future work must begin in a separately scoped phase and rerun the full
acceptance gate.
