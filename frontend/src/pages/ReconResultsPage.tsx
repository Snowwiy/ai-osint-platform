import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { getInvestigationGraph } from "../lib/api";
import { useInvestigationId } from "../lib/hooks";

export function ReconResultsPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const graph = useQuery({
    queryKey: ["graph", investigationId],
    queryFn: () => getInvestigationGraph(investigationId),
  });

  if (graph.isLoading) {
    return <LoadingBlock label="Loading recon results" />;
  }
  if (graph.isError) {
    return <ErrorBlock message={graph.error.message} />;
  }

  return (
    <>
      <PageHeader title="Recon Results" eyebrow="Passive entities" />
      {graph.data?.nodes.length ? (
        <div className="grid gap-5 xl:grid-cols-[1fr_0.9fr]">
          <section className="overflow-hidden rounded-lg border border-raven-border">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="bg-raven-panelSoft text-xs uppercase text-raven-muted">
                <tr>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Value</th>
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3">Last seen</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-raven-border bg-raven-panel/70">
                {graph.data.nodes.map((node) => (
                  <tr key={node.id}>
                    <td className="px-4 py-3 text-raven-cyan">{node.entity_type}</td>
                    <td className="px-4 py-3 font-medium">{node.value}</td>
                    <td className="px-4 py-3 text-raven-muted">{node.source ?? "recon"}</td>
                    <td className="px-4 py-3 text-raven-muted">
                      {new Date(node.last_seen).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
            <h2 className="text-lg font-semibold">Relationships</h2>
            {graph.data.edges.length ? (
              <div className="mt-4 space-y-3">
                {graph.data.edges.map((edge) => (
                  <div
                    key={edge.id}
                    className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
                  >
                    <p className="text-sm font-medium">{edge.relationship_type}</p>
                    <p className="mt-1 break-all text-xs text-raven-muted">
                      {edge.source_entity_id} → {edge.target_entity_id}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyBlock message="No recon relationships are stored yet." />
            )}
          </section>
        </div>
      ) : (
        <EmptyBlock message="No passive recon entities are stored for this investigation." />
      )}
    </>
  );
}

