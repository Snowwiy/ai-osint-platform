# RavenTech OSINT Portfolio Demo Flow

This 10-minute script is designed for interviews, client demos, and GitHub
portfolio walkthroughs. Keep the language defensive: authorized scope,
evidence-backed findings, analyst review, remediation, governance.

## 1. Login And Positioning

Click: login page.

Say: "RavenTech OSINT is a defensive intelligence and investigation workspace.
It turns authorized passive evidence into findings, remediation tasks, reports,
and audit-ready case records."

Proves: authentication, professional UX, defensive positioning.

## 2. Dashboard Health And Posture

Click: Dashboard, Executive, Operations Center if needed.

Say: "The dashboard separates operational posture from executive posture. Health
and degraded states are explicit, so the app remains usable when optional
services like live AI are unavailable."

Proves: health readiness, executive visibility, graceful degradation.

## 3. Investigation Workflow

Click: Investigations, open `[DEMO] Authorized External Exposure Review`.

Say: "Every investigation begins with authorization and scope. The demo case is
synthetic and clearly labeled so it cannot be mistaken for a real incident."

Optional click: Engagements.

Say: "The engagement layer records client context, authorization status,
approved scope items, and evidence references. Scope checks are deterministic
and local; unknown values become pending review rather than silently approved."

Proves: governance, scope management, authorization tracking, demo safety.

## 4. Passive Recon Evidence

Click: Targets and Recon.

Say: "Recon is passive only. The platform normalizes entities like domains, IPs,
services, and technologies, then stores relationships for graph and timeline
views."

Proves: passive recon model, normalized entities, relationship workflow.

## 5. Deterministic Findings

Click: Findings.

Say: "Findings are deterministic and evidence-backed. Severity, confidence,
remediation status, and analyst ownership are visible without relying on an LLM."

Proves: findings engine, review workflow, remediation tracking.

## 6. Correlations And IOC Intelligence

Click: Correlations, IOCs, Evidence Intelligence, Threat Intelligence.

Say: "The intelligence layers correlate stored internal evidence across
investigations. There is no internet-wide enrichment or unsupported attribution."

Proves: cross-investigation analysis, IOC repository, threat workspace maturity.

## 7. AI Fallback And Evidence-Backed Analysis

Click: AI Analysis.

Say: "AI is optional. If a provider key is missing or unavailable, the UI shows a
clear degraded state and deterministic evidence-backed fallback remains usable."

Proves: safe AI integration, no secret exposure, robust UX.

## 8. Remediation And Playbooks

Click: Playbooks, Tasks, Review Board.

Say: "Analysts can move from finding to validation, remediation task, playbook
steps, report approval, and case closure. No action is autonomous."

Proves: SOC-style workflow, analyst accountability, governance lifecycle.

## 9. Executive Report Export

Click: Reports, generate or open sample report, download PDF/DOCX/HTML/MD.

Say: "Reports use stored investigation data, citations, approvals, and branding.
Exports support executive and technical audiences."

Proves: report engine, export management, stakeholder readiness.

## 10. Audit And Governance Controls

Click: Admin Settings, Audit Log, Demo Checklist.

Say: "Admin controls cover feature flags, export settings, retention posture,
audit policy, and demo readiness. Sensitive values are never printed."

Proves: enterprise controls, auditability, release-candidate supportability.

## Defensive Scope Explanation

Use this phrase if asked about offensive capability:

"The platform intentionally avoids active scanning, exploitation, payloads,
malware handling, and autonomous actions. It is designed for authorized
defensive assessment, evidence management, remediation, and reporting."
