import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { InvestigationTabs } from "../components/InvestigationTabs";
import { BookmarkButton } from "../components/BookmarkButton";
import { LongValue } from "../components/LongValue";
import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { getInvestigationGraph } from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import type { GraphNode } from "../types";

export function ReconResultsPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const graph = useQuery({
    queryKey: ["graph", investigationId],
    queryFn: () => getInvestigationGraph(investigationId),
  });

  const nodeById = useMemo(
    () => new Map((graph.data?.nodes ?? []).map((node) => [node.id, node])),
    [graph.data?.nodes],
  );
  const entityRows = useMemo(
    () => mergeEntityRows(graph.data?.nodes ?? []),
    [graph.data?.nodes],
  );
  const relationshipEdges = graph.data?.edges ?? [];
  const entityCounts = useMemo(
    () =>
      Array.from(
        entityRows.reduce<Map<string, number>>((counts, row) => {
          counts.set(row.entityType, (counts.get(row.entityType) ?? 0) + 1);
          return counts;
        }, new Map()),
      ).sort(([left], [right]) => safeLocaleCompare(left, right)),
    [entityRows],
  );

  if (graph.isLoading) {
    return <LoadingBlock label="Loading recon results" />;
  }
  if (graph.isError) {
    return <ErrorBlock message={graph.error} />;
  }

  return (
    <>
      <PageHeader title="Recon Results" eyebrow="Passive entities" />
      <InvestigationTabs />
      {(graph.data?.nodes ?? []).length ? (
        <div className="space-y-5">
          <section className="grid gap-3 md:grid-cols-4">
            {entityCounts.map(([entityType, count]) => (
              <div
                key={entityType}
                className="rounded-md border border-raven-border bg-raven-panel/85 p-3"
              >
                <p className="text-xs uppercase tracking-wide text-raven-muted">
                  {entityType}
                </p>
                <p className="mt-1 text-2xl font-semibold">{count}</p>
              </div>
            ))}
          </section>

          <div className="grid gap-5 xl:grid-cols-[1fr_0.9fr]">
            <section className="overflow-hidden rounded-lg border border-raven-border">
              <div className="border-b border-raven-border bg-raven-panel/85 px-4 py-3">
                <h2 className="font-semibold">Entities</h2>
                <p className="mt-1 text-sm text-raven-muted">
                  Duplicate values from separate recon runs are grouped into one row.
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[860px] text-left text-sm">
                  <thead className="bg-raven-panelSoft text-xs uppercase text-raven-muted">
                    <tr>
                      <th className="px-4 py-3">Type</th>
                      <th className="px-4 py-3">Value</th>
                      <th className="px-4 py-3">Sources</th>
                      <th className="px-4 py-3">Last seen</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-raven-border bg-raven-panel/70">
                    {entityRows.map((row) => (
                      <tr key={`${row.entityType}-${row.value}`}>
                        <td className="px-4 py-3 text-raven-cyan">
                          {row.entityType}
                        </td>
                        <td className="px-4 py-3 font-medium">
                          <LongValue
                            value={row.value}
                            secondary={`IDs: ${row.ids.join(", ")}`}
                            maxLength={64}
                          />
                          <div className="mt-2">
                            <BookmarkButton
                              investigationId={investigationId}
                              entityId={row.ids[0]}
                              title={`${row.entityType}: ${row.value}`}
                            />
                          </div>
                        </td>
                        <td className="px-4 py-3 text-raven-muted">
                          {row.sources.join(", ")}
                        </td>
                        <td className="px-4 py-3 text-raven-muted">
                          {new Date(row.lastSeen).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
              <h2 className="text-lg font-semibold">Relationships</h2>
              {relationshipEdges.length ? (
                <div className="mt-4 space-y-3">
                  {relationshipEdges.map((edge) => (
                    <div
                      key={edge.id}
                      className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
                    >
                      <p className="text-sm font-medium">{edge.relationship_type}</p>
                      <RelationshipValue
                        source={nodeById.get(edge.source_entity_id)}
                        target={nodeById.get(edge.target_entity_id)}
                        sourceId={edge.source_entity_id}
                        targetId={edge.target_entity_id}
                      />
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyBlock
                  title="No recon relationships"
                  message="Relationships connect stored domains, addresses, services, technologies, and certificates."
                  nextStep="Run passive recon on an authorized target to collect defensive evidence."
                />
              )}
            </section>
          </div>
        </div>
      ) : (
        <EmptyBlock
          title="No passive recon evidence"
          message="Passive recon collects defensive infrastructure metadata without active scanning."
          nextStep="Run passive recon from the Targets tab after confirming authorization."
          permission="Contributors can run recon; viewers have read-only access."
        />
      )}
    </>
  );
}

function RelationshipValue({
  source,
  target,
  sourceId,
  targetId,
}: {
  source: GraphNode | undefined;
  target: GraphNode | undefined;
  sourceId: string;
  targetId: string;
}): JSX.Element {
  return (
    <div className="mt-2 grid gap-3 text-xs text-raven-muted md:grid-cols-[1fr_auto_1fr] md:items-start">
      <LongValue
        value={entityLabel(source) ?? sourceId}
        secondary={source ? `${source.entity_type} ${source.id}` : sourceId}
        maxLength={48}
      />
      <span className="pt-1 text-center">to</span>
      <LongValue
        value={entityLabel(target) ?? targetId}
        secondary={target ? `${target.entity_type} ${target.id}` : targetId}
        maxLength={48}
      />
    </div>
  );
}

function entityLabel(node: GraphNode | undefined): string | null {
  if (!node) {
    return null;
  }
  return node.display_name || node.value || node.id;
}

interface EntityRow {
  entityType: string;
  value: string;
  sources: string[];
  ids: string[];
  lastSeen: string;
}

function mergeEntityRows(nodes: GraphNode[]): EntityRow[] {
  const rows = new Map<string, EntityRow>();
  for (const node of nodes) {
    const entityType = safeString(node.entity_type, "Unknown");
    const value = safeString(node.value, node.id);
    const key = `${entityType}:${value}`.toLowerCase();
    const row = rows.get(key);
    if (!row) {
      rows.set(key, {
        entityType,
        value,
        sources: [node.source ?? "recon"],
        ids: [node.id],
        lastSeen: node.last_seen ?? new Date(0).toISOString(),
      });
      continue;
    }
    const source = node.source ?? "recon";
    if (!row.sources.includes(source)) {
      row.sources.push(source);
    }
    if (!row.ids.includes(node.id)) {
      row.ids.push(node.id);
    }
    if (
      new Date(node.last_seen ?? 0).getTime() > new Date(row.lastSeen).getTime()
    ) {
      row.lastSeen = node.last_seen ?? row.lastSeen;
    }
  }
  return Array.from(rows.values()).sort(
    (left, right) =>
      safeLocaleCompare(left.entityType, right.entityType) ||
      safeLocaleCompare(left.value, right.value),
  );
}

function safeString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : String(value ?? fallback);
}

function safeLocaleCompare(left: unknown, right: unknown): number {
  return safeString(left).localeCompare(safeString(right));
}
