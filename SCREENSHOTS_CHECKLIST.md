# RavenTech OSINT Portfolio Screenshots Checklist

Use only synthetic `[DEMO]` records and reserved identifiers. Hide browser
password managers, tokens, environment values, real customer data, local file
paths, and personal notifications. Capture a consistent desktop viewport and,
where useful, one narrow responsive view.

## Required Screenshots

- [ ] **Login and registration:** branded login plus the registration state that
      matches configuration (disabled, invite-gated, or pending approval).
- [ ] **Dashboard:** posture cards, prioritized work, recent investigations, and
      Quick Access without clipped content.
- [ ] **Operations Center:** health/readiness, release, migration, storage, and
      safe diagnostics panels.
- [ ] **Investigations:** list and `[DEMO]` detail overview with authorization,
      ownership, status, and tabs.
- [ ] **Engagement and scope:** synthetic client context, authorization status,
      approved domain/CIDR scope, and conservative scope warning.
- [ ] **Targets and recon:** authorized synthetic target plus passive recon
      entities and graceful partial-source state.
- [ ] **Findings:** severity, confidence, evidence, remediation, and analyst
      ownership on a deterministic finding.
- [ ] **Correlations:** Cards, Graph, and Table modes; use a three-image composite
      or three separate captures.
- [ ] **IOCs and intelligence:** IOC relationships plus Evidence Intelligence or
      Threat Intelligence context without unsupported attribution.
- [ ] **AI Analysis fallback:** provider-unavailable/degraded message with
      deterministic fallback and citations still visible.
- [ ] **Reports and export:** template/readiness view and PDF, DOCX, HTML, and
      Markdown export controls.
- [ ] **Closure and deliverables:** checklist, approval state, deliverable list,
      and evidence package manifest/readiness.
- [ ] **Notifications:** Activity Inbox with synthetic workflow alerts, filters,
      and unread state.
- [ ] **Global Search:** Ctrl+K search results showing internal, RBAC-aware
      navigation.
- [ ] **Saved Views:** pinned/default view plus Dashboard Quick Access.
- [ ] **Data Quality Center:** scan summary, safe issue detail, and
      acknowledge/resolve workflow.
- [ ] **Admin users:** pending/active account controls and role/status filters;
      never show password hashes or invite codes.
- [ ] **Audit and governance:** audit event metadata plus settings/feature flags
      demonstrating defensive controls.
- [ ] **Health and release endpoints:** `/health`, `/health/ready`, and
      `/api/v1/release` showing `5.0.0-rc3` and `0036_phase5ai_posture` without
      secrets.

## Quality Gate For Every Capture

- [ ] Defensive wording and synthetic labels are visible where relevant.
- [ ] No `undefined`, `null`, raw endpoint error, stack trace, or secret appears.
- [ ] Long IDs/URLs wrap or truncate cleanly and tabs remain usable.
- [ ] No horizontal page overflow, clipped modal, or React crash screen appears.
- [ ] Browser chrome and cursor placement do not obscure the subject.
- [ ] Caption states what the screen proves; it does not claim production
      hosting, live compromise, or autonomous action.

No hosting or deployment screenshot belongs in the RC3 portfolio package.
