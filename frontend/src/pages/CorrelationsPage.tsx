import { GitGraph, Network, Table2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { CorrelationNetwork } from "../components/CorrelationNetwork";
import { InvestigationTabs } from "../components/InvestigationTabs";
import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { getCorrelations } from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import type { CorrelationEdge, CorrelationNode } from "../types";

type ViewMode = "cards" | "graph" | "table";

export function CorrelationsPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const [viewMode, setViewMode] = useState<ViewMode>("cards");
  const correlations = useQuery({
    queryKey: ["correlations", investigationId],
    queryFn: () => getCorrelations(investigationId),
  });
  const nodeById = useMemo(() => {
    return new Map(
      correlations.data?.nodes.map((node) => [node.id, node]) ?? [],
    );
  }, [correlations.data?.nodes]);

  if (correlations.isLoading) {
    return <LoadingBlock label="Loading correlations" />;
  }
  if (correlations.isError) {
    return <ErrorBlock message={correlations.error.message} />;
  }

  const data = correlations.data;
  const hasGraph = Boolean(data?.nodes.length && data.edges.length);

  return (
    <>
      <PageHeader
        title="Correlations"
        eyebrow="Defensive relationships"
        actions={
          <div className="flex flex-wrap gap-2">
            <ModeButton
              mode="cards"
              active={viewMode === "cards"}
              icon={<GitGraph className="h-4 w-4" aria-hidden="true" />}
              onClick={setViewMode}
            />
            <ModeButton
              mode="graph"
              active={viewMode === "graph"}
              icon={<Network className="h-4 w-4" aria-hidden="true" />}
              onClick={setViewMode}
              disabled={!hasGraph}
            />
            <ModeButton
              mode="table"
              active={viewMode === "table"}
              icon={<Table2 className="h-4 w-4" aria-hidden="true" />}
              onClick={setViewMode}
            />
          </div>
        }
      />
      <InvestigationTabs />

      {hasGraph && data ? (
        <div className="space-y-5">
          <SummaryStrip nodes={data.nodes} edges={data.edges} />
          {viewMode === "graph" ? (
            <CorrelationNetwork nodes={data.nodes} edges={data.edges} />
          ) : null}
          {viewMode === "cards" ? (
            <RelationshipCards edges={data.edges} nodeById={nodeById} />
          ) : null}
          {viewMode === "table" ? (
            <RelationshipTable edges={data.edges} nodeById={nodeById} />
          ) : null}
        </div>
      ) : (
        <EmptyBlock message="No defensive correlations are available yet. Correlations appear after stored recon entities, findings, reports, or repeated indicators overlap." />
      )}
    </>
  );
}

function SummaryStrip({
  nodes,
  edges,
}: {
  nodes: CorrelationNode[];
  edges: CorrelationEdge[];
}): JSX.Element {
  const confidenceCounts = edges.reduce<Record<string, number>>((counts, edge) => {
    counts[edge.confidence] = (counts[edge.confidence] ?? 0) + 1;
    return counts;
  }, {});
  return (
    <div className="grid gap-3 md:grid-cols-4">
      <SummaryMetric label="Nodes" value={nodes.length} />
      <SummaryMetric label="Relationships" value={edges.length} />
      <SummaryMetric label="High confidence" value={confidenceCounts.high ?? 0} />
      <SummaryMetric
        label="Relationship types"
        value={new Set(edges.map((edge) => edge.correlation_type)).size}
      />
    </div>
  );
}

function RelationshipCards({
  edges,
  nodeById,
}: {
  edges: CorrelationEdge[];
  nodeById: Map<string, CorrelationNode>;
}): JSX.Element {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {edges.map((edge) => (
        <article
          key={edge.id}
          className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"
        >
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-wide text-raven-cyan">
                {edge.correlation_type.replace(/_/g, " ")}
              </p>
              <h2 className="mt-1 font-semibold">{edge.summary}</h2>
            </div>
            <span className="rounded border border-raven-border px-2 py-1 text-xs capitalize text-raven-cyan">
              {edge.confidence}
            </span>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto_1fr] md:items-center">
            <NodePill node={nodeById.get(edge.source_node_id)} fallback="Source" />
            <span className="text-center text-xs uppercase tracking-wide text-raven-muted">
              linked to
            </span>
            <NodePill node={nodeById.get(edge.target_node_id)} fallback="Target" />
          </div>
          <p className="mt-4 text-xs text-raven-muted">
            Evidence count: {edge.evidence_count}
          </p>
        </article>
      ))}
    </div>
  );
}

function RelationshipTable({
  edges,
  nodeById,
}: {
  edges: CorrelationEdge[];
  nodeById: Map<string, CorrelationNode>;
}): JSX.Element {
  return (
    <section className="overflow-hidden rounded-lg border border-raven-border">
      <table className="w-full min-w-[860px] text-left text-sm">
        <thead className="bg-raven-panelSoft text-xs uppercase text-raven-muted">
          <tr>
            <th className="px-4 py-3">Relationship</th>
            <th className="px-4 py-3">Source</th>
            <th className="px-4 py-3">Target</th>
            <th className="px-4 py-3">Confidence</th>
            <th className="px-4 py-3">Evidence</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-raven-border bg-raven-panel/70">
          {edges.map((edge) => (
            <tr key={edge.id}>
              <td className="px-4 py-3 text-raven-cyan">
                {edge.correlation_type.replace(/_/g, " ")}
              </td>
              <td className="px-4 py-3">
                {nodeById.get(edge.source_node_id)?.label ?? edge.source_node_id}
              </td>
              <td className="px-4 py-3">
                {nodeById.get(edge.target_node_id)?.label ?? edge.target_node_id}
              </td>
              <td className="px-4 py-3 capitalize text-raven-muted">
                {edge.confidence}
              </td>
              <td className="px-4 py-3 text-raven-muted">{edge.evidence_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function ModeButton({
  mode,
  active,
  disabled,
  icon,
  onClick,
}: {
  mode: ViewMode;
  active: boolean;
  disabled?: boolean;
  icon: JSX.Element;
  onClick: (mode: ViewMode) => void;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={() => onClick(mode)}
      disabled={disabled}
      className={[
        "inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm capitalize",
        active
          ? "border-raven-violet bg-raven-violet text-white"
          : "border-raven-border bg-raven-panel text-raven-muted hover:text-raven-text",
        disabled ? "cursor-not-allowed opacity-50" : "",
      ].join(" ")}
    >
      {icon}
      {mode}
    </button>
  );
}

function SummaryMetric({
  label,
  value,
}: {
  label: string;
  value: string | number;
}): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-panel/85 p-3">
      <p className="text-xs uppercase tracking-wide text-raven-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function NodePill({
  node,
  fallback,
}: {
  node: CorrelationNode | undefined;
  fallback: string;
}): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <p className="break-words text-sm font-medium">{node?.label ?? fallback}</p>
      <p className="mt-1 text-xs capitalize text-raven-muted">
        {node?.node_type.replace(/_/g, " ") ?? "unknown"}
      </p>
    </div>
  );
}
