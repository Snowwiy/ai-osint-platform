import clsx from "clsx";

import type { Severity } from "../types";

const styles: Record<Severity, string> = {
  info: "border-cyan-300/30 bg-cyan-400/10 text-cyan-100",
  low: "border-emerald-300/30 bg-emerald-400/10 text-emerald-100",
  medium: "border-amber-300/30 bg-amber-400/10 text-amber-100",
  high: "border-orange-300/30 bg-orange-400/10 text-orange-100",
  critical: "border-rose-300/30 bg-rose-400/10 text-rose-100",
};

export function SeverityBadge({ severity }: { severity: Severity }): JSX.Element {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium capitalize",
        styles[severity],
      )}
    >
      {severity}
    </span>
  );
}

