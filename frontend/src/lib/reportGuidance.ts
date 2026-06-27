import type { ReportType } from "../types";

interface ReportGuidance {
  summary: string;
  recommendedWhen: string;
  emphasis: string[];
}

export const reportGuidance: Record<ReportType, ReportGuidance> = {
  executive: {
    summary:
      "Concise business risk, defensive posture, top evidence-backed findings, and remediation priorities.",
    recommendedWhen:
      "briefing leadership or stakeholders who need decisions rather than raw evidence.",
    emphasis: ["Business risk", "Defensive posture", "Remediation posture"],
  },
  technical: {
    summary:
      "Detailed evidence, MITRE mappings, Sigma references, monitoring guidance, and citations.",
    recommendedWhen:
      "analysts or technical owners need enough context to validate and remediate.",
    emphasis: ["Technical evidence", "Detection guidance", "Citations"],
  },
  remediation: {
    summary:
      "Prioritized controls, monitoring gaps, ownership, due dates, verification, and residual risk.",
    recommendedWhen:
      "tracking corrective work through validation and accountable closure.",
    emphasis: ["Prioritized controls", "Monitoring gaps", "Verification"],
  },
  evidence_appendix: {
    summary:
      "Evidence chains, bookmarks, citations, and defensive framework references.",
    recommendedWhen:
      "a reviewer needs an auditable evidence package alongside another report.",
    emphasis: ["Evidence chains", "Bookmarks", "Raw references"],
  },
  compliance_mapping: {
    summary:
      "Framework controls and their mappings to stored findings and recommendations.",
    recommendedWhen:
      "connecting defensive observations to governance or control-assurance work.",
    emphasis: ["Frameworks", "Controls", "Finding mappings"],
  },
  playbook_progress: {
    summary:
      "Defensive playbook runs, step progress, blockers, notes, and completion.",
    recommendedWhen:
      "reviewing repeatable analyst workflow execution and outstanding steps.",
    emphasis: ["Run progress", "Step status", "Blockers"],
  },
  operational_dashboard: {
    summary:
      "Investigation queue, triage posture, workload, activity, and operational metrics.",
    recommendedWhen:
      "coordinating multiple cases or presenting an operations-level status view.",
    emphasis: ["Queue posture", "Workload", "Triage metrics"],
  },
};
