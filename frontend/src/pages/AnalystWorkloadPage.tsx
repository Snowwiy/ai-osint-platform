import { RefreshCw, TrendingDown, TrendingUp, UsersRound } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { getAnalystWorkload } from "../lib/api";

export function AnalystWorkloadPage(): JSX.Element {
  const workload = useQuery({
    queryKey: ["analyst-workload"],
    queryFn: getAnalystWorkload,
  });

  if (workload.isLoading) {
    return <LoadingBlock label="Loading analyst workload" />;
  }
  if (workload.isError) {
    return <ErrorBlock message={workload.error} />;
  }

  return (
    <>
      <PageHeader
        title="Analyst Workload"
        eyebrow="Operational visibility"
        actions={
          <button
            type="button"
            onClick={() => void workload.refetch()}
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </button>
        }
      />
      <p className="-mt-3 mb-5 text-sm text-raven-muted">
        Assignment and completion metrics only. No ranking or gamification.
      </p>
      {(workload.data?.items ?? []).length ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {(workload.data?.items ?? []).map((analyst) => (
            <article
              key={analyst.user_id}
              className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <UsersRound className="h-4 w-4 text-raven-cyan" />
                    <h2 className="font-semibold">{analyst.username}</h2>
                  </div>
                  <p className="mt-1 text-sm text-raven-muted">{analyst.email}</p>
                </div>
                <Trend value={analyst.completion_trend} />
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <Metric
                  label="Active investigations"
                  value={analyst.active_investigations}
                />
                <Metric
                  label="Overdue remediation"
                  value={analyst.overdue_remediation}
                  danger={analyst.overdue_remediation > 0}
                />
                <Metric
                  label="Assigned findings"
                  value={analyst.findings_assigned}
                />
                <Metric label="Notes | 30d" value={analyst.notes_added_30d} />
                <Metric
                  label="Completed | 30d"
                  value={analyst.remediations_completed_30d}
                />
                <Metric
                  label="Previous 30d"
                  value={analyst.previous_30d_completed}
                />
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyBlock
          title="No assigned analyst workload"
          message="Workload appears when accessible investigations, findings, or remediation tasks are assigned."
          nextStep="Assign a member to an authorized case or task."
          permission="Assignment changes require the relevant case role."
        />
      )}
    </>
  );
}

function Metric({
  label,
  value,
  danger,
}: {
  label: string;
  value: number;
  danger?: boolean;
}): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <p className="text-xs text-raven-muted">{label}</p>
      <p className={["mt-1 text-xl font-semibold", danger ? "text-rose-100" : ""].join(" ")}>
        {value}
      </p>
    </div>
  );
}

function Trend({ value }: { value: "up" | "steady" | "down" }): JSX.Element {
  if (value === "up") {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-emerald-200">
        <TrendingUp className="h-4 w-4" aria-hidden="true" />
        More completed
      </span>
    );
  }
  if (value === "down") {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-amber-200">
        <TrendingDown className="h-4 w-4" aria-hidden="true" />
        Fewer completed
      </span>
    );
  }
  return <span className="text-xs text-raven-muted">Steady completion</span>;
}
