import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { SeverityBadge } from "../components/SeverityBadge";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { listFindings } from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import type { Severity } from "../types";

const severities: Array<Severity | "all"> = [
  "all",
  "critical",
  "high",
  "medium",
  "low",
  "info",
];

export function FindingsPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const findings = useQuery({
    queryKey: ["findings", investigationId],
    queryFn: () => listFindings(investigationId),
  });

  const filtered = useMemo(() => {
    const items = findings.data ?? [];
    return severity === "all"
      ? items
      : items.filter((item) => item.severity === severity);
  }, [findings.data, severity]);

  if (findings.isLoading) {
    return <LoadingBlock label="Loading findings" />;
  }
  if (findings.isError) {
    return <ErrorBlock message={findings.error.message} />;
  }

  return (
    <>
      <PageHeader
        title="Findings"
        eyebrow="Correlation output"
        actions={
          <select
            value={severity}
            onChange={(event) => setSeverity(event.target.value as Severity | "all")}
            className="rounded-md border border-raven-border bg-raven-panel px-3 py-2 text-sm text-raven-text"
          >
            {severities.map((item) => (
              <option key={item} value={item}>
                {item === "all" ? "All severities" : item}
              </option>
            ))}
          </select>
        }
      />

      {filtered.length ? (
        <div className="space-y-4">
          {filtered.map((finding) => (
            <article
              key={finding.id}
              className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <h2 className="font-semibold">{finding.title}</h2>
                  <p className="mt-2 text-sm leading-6 text-raven-muted">
                    {finding.description}
                  </p>
                </div>
                <SeverityBadge severity={finding.severity} />
              </div>
              <div className="mt-4 grid gap-3 text-sm text-raven-muted md:grid-cols-4">
                <Metric label="Risk" value={finding.risk_score} />
                <Metric label="Confidence" value={finding.confidence_score} />
                <Metric label="Source" value={finding.source} />
                <Metric label="Status" value={finding.status} />
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyBlock message="No findings match the current filter." />
      )}
    </>
  );
}

function Metric({ label, value }: { label: string; value: string | number }): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2">
      <p className="text-xs uppercase tracking-wide">{label}</p>
      <p className="mt-1 text-raven-text">{value}</p>
    </div>
  );
}
