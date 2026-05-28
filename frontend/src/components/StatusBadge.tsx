import clsx from "clsx";

import type { InvestigationStatus } from "../types";

const statusStyles: Record<InvestigationStatus, string> = {
  draft: "border-slate-400/30 bg-slate-400/10 text-slate-200",
  active: "border-emerald-400/30 bg-emerald-500/10 text-emerald-100",
  completed: "border-cyan-400/30 bg-cyan-500/10 text-cyan-100",
  archived: "border-amber-400/30 bg-amber-500/10 text-amber-100",
};

export function StatusBadge({
  status,
}: {
  status: InvestigationStatus;
}): JSX.Element {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded border px-2 py-1 text-xs font-medium",
        "capitalize",
        statusStyles[status],
      )}
    >
      {status}
    </span>
  );
}
