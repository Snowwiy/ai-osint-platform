import clsx from "clsx";

import type { InvestigationStatus } from "../types";

const statusStyles: Record<InvestigationStatus, string> = {
  intake: "border-slate-400/30 bg-slate-400/10 text-slate-200",
  active: "border-emerald-400/30 bg-emerald-500/10 text-emerald-100",
  monitoring: "border-cyan-400/30 bg-cyan-500/10 text-cyan-100",
  remediation: "border-violet-400/30 bg-violet-500/10 text-violet-100",
  validation: "border-teal-400/30 bg-teal-500/10 text-teal-100",
  completed: "border-emerald-400/30 bg-emerald-500/10 text-emerald-100",
  archived: "border-amber-400/30 bg-amber-500/10 text-amber-100",
};

export function StatusBadge({
  status,
}: {
  status: InvestigationStatus;
}): JSX.Element {
  const label = typeof status === "string" && status.trim()
    ? status.replace(/_/g, " ")
    : "unknown";
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded border px-2 py-1 text-xs font-medium",
        "capitalize",
        statusStyles[status] ?? "border-raven-border bg-raven-panelSoft text-raven-muted",
      )}
    >
      {label}
    </span>
  );
}
