import type { ReactNode } from "react";

export function StatCard({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: string | number;
  detail?: string;
  icon: ReactNode;
}): JSX.Element {
  return (
    <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-4 shadow-glow">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-raven-muted">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-raven-text">{value}</p>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-raven-border bg-raven-panelSoft text-raven-cyan">
          {icon}
        </div>
      </div>
      {detail ? <p className="mt-3 text-sm text-raven-muted">{detail}</p> : null}
    </div>
  );
}

