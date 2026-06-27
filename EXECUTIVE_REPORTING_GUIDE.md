# Executive Reporting Guide

RavenTech OSINT executive reporting turns stored defensive investigation data into
stakeholder-ready summaries. It is designed for authorized internal assessment,
governance review, and remediation coordination.

## Data Sources

Executive reporting uses existing stored platform data only:

- investigations and authorized scope
- findings and severity/status
- remediation tasks and due dates
- reports and report readiness
- internal correlations and repeated evidence
- IOC and defensive intelligence summaries when available
- analyst notes, playbooks, bookmarks, and timeline activity where relevant

No live internet retrieval, active scanning, or unsupported compromise claims are
introduced by executive reporting.

## Stakeholder Audiences

### Executive

Focuses on business risk, posture, key risks, remediation urgency, and decisions
needed. Evidence details are summarized and citations remain available.

### Management

Focuses on ownership, remediation progress, due dates, unresolved risk, and
reporting readiness.

### Analyst

Focuses on evidence, findings, correlations, framework mappings, detection
guidance, and next defensive review actions.

## Deterministic Posture Scoring

The organization posture score is calculated from stored signals:

- unresolved critical findings
- unresolved high findings
- open remediation tasks
- overdue remediation tasks
- recurring internal correlation signals

Categories:

- 0-30: Low
- 31-60: Medium
- 61-80: High
- 81-100: Critical

The score is a prioritization aid, not an automated risk decision. Analysts
should validate business impact with asset owners.

## Risk Trend Logic

Risk trend data is derived from dated stored activity:

- findings created
- remediation tasks completed
- investigations created
- reports generated

If there is no historical activity, the trend view shows an empty state rather
than inventing movement.

## Recommendation Logic

Recommendations are grouped into:

- Immediate
- Short-Term
- Long-Term

Recommendations are evidence-backed and deterministic. Typical triggers include:

- unresolved high or critical findings
- overdue remediation tasks
- investigations with evidence but no stakeholder report
- repeated internal infrastructure or finding patterns

## Evidence Requirements

Executive summaries and recommendations should cite stored evidence such as:

- finding IDs
- task IDs
- investigation IDs
- correlation references
- report references

Missing data creates quality warnings or empty states. It does not block
analyst-approved reporting.

## AI Fallback Behavior

Live AI analysis is optional and never required for executive reporting. If the
AI provider is missing, disabled, timed out, or rejected a request, RavenTech
shows deterministic evidence-backed fallback content.

Provider diagnostics expose only safe metadata:

- provider configured: yes/no
- model name
- feature flag state
- last error category

Secrets and API keys are never shown.

## Limitations

- No autonomous decision-making.
- No offensive actions.
- No active scanning.
- No threat actor attribution unless already supported by stored evidence.
- Historical trend quality depends on available stored activity.
- Business impact text should be reviewed by an analyst before external sharing.
