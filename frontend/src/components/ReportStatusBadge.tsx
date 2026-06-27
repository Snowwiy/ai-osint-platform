import type { ReportStatus } from "../types";

const tones: Record<ReportStatus, string> = {
  queued: "border-sky-400/30 bg-sky-500/10 text-sky-100",
  generating: "border-amber-400/30 bg-amber-500/10 text-amber-100",
  ready: "border-emerald-400/30 bg-emerald-500/10 text-emerald-100",
  failed: "border-rose-400/30 bg-rose-500/10 text-rose-100",
  archived: "border-raven-border bg-raven-panelSoft text-raven-muted",
};

export function ReportStatusBadge({
  status,
}: {
  status: ReportStatus;
}): JSX.Element {
  return (
    <span
      className={[
        "inline-flex rounded-full border px-2 py-0.5 text-xs font-medium capitalize",
        tones[status],
      ].join(" ")}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
