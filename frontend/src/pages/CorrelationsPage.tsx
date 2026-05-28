import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { getCorrelations } from "../lib/api";
import { useInvestigationId } from "../lib/hooks";

export function CorrelationsPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const correlations = useQuery({
    queryKey: ["correlations", investigationId],
    queryFn: () => getCorrelations(investigationId),
  });

  if (correlations.isLoading) {
    return <LoadingBlock label="Loading correlations" />;
  }
  if (correlations.isError) {
    return <ErrorBlock message={correlations.error.message} />;
  }

  return (
    <>
      <PageHeader title="Correlations" eyebrow="Defensive relationships" />
      {correlations.data?.edges.length ? (
        <div className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
          <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
            <h2 className="text-lg font-semibold">Nodes</h2>
            <div className="mt-4 space-y-2">
              {correlations.data.nodes.slice(0, 25).map((node) => (
                <div
                  key={node.id}
                  className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
                >
                  <p className="text-sm font-medium">{node.label}</p>
                  <p className="mt-1 text-xs text-raven-muted">
                    {node.node_type} · {node.source}
                  </p>
                </div>
              ))}
            </div>
          </section>

          <section className="space-y-3">
            {correlations.data.edges.map((edge) => (
              <article
                key={edge.id}
                className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"
              >
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <h2 className="font-semibold">{edge.correlation_type}</h2>
                    <p className="mt-2 text-sm leading-6 text-raven-muted">
                      {edge.summary}
                    </p>
                  </div>
                  <span className="rounded border border-raven-border px-2 py-1 text-xs capitalize text-raven-cyan">
                    {edge.confidence}
                  </span>
                </div>
                <p className="mt-3 text-xs text-raven-muted">
                  Evidence count: {edge.evidence_count}
                </p>
              </article>
            ))}
          </section>
        </div>
      ) : (
        <EmptyBlock message="No defensive correlations are available yet." />
      )}
    </>
  );
}
