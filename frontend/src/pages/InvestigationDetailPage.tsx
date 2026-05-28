import { BrainCircuit, FileText, GitGraph, Network, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { StatCard } from "../components/StatCard";
import { ErrorBlock, LoadingBlock } from "../components/StateBlock";
import {
  getCorrelations,
  getInvestigation,
  getInvestigationGraph,
  getTimeline,
  listFindings,
  listReports,
} from "../lib/api";
import { useInvestigationId } from "../lib/hooks";

export function InvestigationDetailPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const investigation = useQuery({
    queryKey: ["investigation", investigationId],
    queryFn: () => getInvestigation(investigationId),
  });
  const graph = useQuery({
    queryKey: ["graph", investigationId],
    queryFn: () => getInvestigationGraph(investigationId),
  });
  const findings = useQuery({
    queryKey: ["findings", investigationId],
    queryFn: () => listFindings(investigationId),
  });
  const timeline = useQuery({
    queryKey: ["timeline", investigationId],
    queryFn: () => getTimeline(investigationId),
  });
  const correlations = useQuery({
    queryKey: ["correlations", investigationId],
    queryFn: () => getCorrelations(investigationId),
  });
  const reports = useQuery({
    queryKey: ["reports", investigationId],
    queryFn: () => listReports(investigationId),
  });

  if (investigation.isLoading) {
    return <LoadingBlock label="Loading investigation" />;
  }
  if (investigation.isError) {
    return <ErrorBlock message={investigation.error.message} />;
  }

  const item = investigation.data;

  return (
    <>
      <PageHeader title={item?.title ?? "Investigation"} eyebrow="Investigation" />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard
          label="Entities"
          value={graph.data?.nodes.length ?? 0}
          icon={<Network className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Findings"
          value={findings.data?.length ?? 0}
          icon={<ShieldAlert className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Timeline"
          value={timeline.data?.total ?? 0}
          icon={<BrainCircuit className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Correlations"
          value={correlations.data?.total_edges ?? 0}
          icon={<GitGraph className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Reports"
          value={reports.data?.total ?? 0}
          icon={<FileText className="h-5 w-5" aria-hidden="true" />}
        />
      </div>

      <section className="mt-8 grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
        <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
          <h2 className="text-lg font-semibold">Scope</h2>
          <p className="mt-3 text-sm leading-6 text-raven-muted">
            {item?.scope_definition ?? item?.description ?? "No scope note stored."}
          </p>
          <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-raven-muted">
            Authorization
          </h3>
          <p className="mt-2 text-sm leading-6 text-raven-text">
            {item?.authorization_statement}
          </p>
        </div>

        <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
          <h2 className="text-lg font-semibold">Workspace</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <Detail label="Status" value={item?.status ?? "unknown"} />
            <Detail
              label="Created"
              value={item ? new Date(item.created_at).toLocaleString() : ""}
            />
            <Detail
              label="Updated"
              value={item ? new Date(item.updated_at).toLocaleString() : ""}
            />
          </dl>
          <div className="mt-5 grid gap-2">
            <LinkButton to="recon" label="Open recon results" />
            <LinkButton to="findings" label="Review findings" />
            <LinkButton to="reports" label="Download reports" />
          </div>
        </div>
      </section>
    </>
  );
}

function Detail({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-raven-muted">{label}</dt>
      <dd className="text-right text-raven-text">{value}</dd>
    </div>
  );
}

function LinkButton({ to, label }: { to: string; label: string }): JSX.Element {
  return (
    <Link
      to={to}
      className="rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm text-raven-text hover:border-raven-violet"
    >
      {label}
    </Link>
  );
}
