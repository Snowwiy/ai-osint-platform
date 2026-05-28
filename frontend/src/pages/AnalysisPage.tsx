import { BrainCircuit } from "lucide-react";
import { useMutation } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { SeverityBadge } from "../components/SeverityBadge";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { analyzeInvestigation } from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import type { AnalysisResponse } from "../types";

export function AnalysisPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const analysis = useMutation<AnalysisResponse, Error, string>({
    mutationFn: analyzeInvestigation,
  });

  return (
    <>
      <PageHeader
        title="AI Analysis"
        eyebrow="Evidence-backed analysis"
        actions={
          <button
            type="button"
            onClick={() => analysis.mutate(investigationId)}
            disabled={analysis.isPending}
            className="inline-flex items-center gap-2 rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-60"
          >
            <BrainCircuit className="h-4 w-4" aria-hidden="true" />
            Analyze
          </button>
        }
      />

      {analysis.isPending ? <LoadingBlock label="Preparing analysis" /> : null}
      {analysis.isError ? <ErrorBlock message={analysis.error.message} /> : null}
      {analysis.data ? (
        <AnalysisResult response={analysis.data} />
      ) : (
        <EmptyBlock message="No analysis response is loaded for this view." />
      )}
    </>
  );
}

function AnalysisResult({ response }: { response: AnalysisResponse }): JSX.Element {
  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-lg font-semibold">Assessment</h2>
            <p className="mt-1 text-sm text-raven-muted">
              {response.status} · {response.provider}
              {response.model ? ` · ${response.model}` : ""}
            </p>
          </div>
          <SeverityBadge severity={response.severity} />
        </div>
        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          <SummaryBlock title="Executive summary" value={response.executive_summary.text} />
          <SummaryBlock title="Technical summary" value={response.technical_summary.text} />
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <ListBlock
          title="Suspicious findings"
          items={response.suspicious_findings.map((item) => item.text)}
        />
        <ListBlock
          title="Recommended next steps"
          items={response.recommended_next_steps.map((item) => item.action)}
        />
      </section>

      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <h2 className="text-lg font-semibold">Citations</h2>
        {response.citations.length ? (
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {response.citations.slice(0, 12).map((citation) => (
              <div
                key={citation.id}
                className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
              >
                <p className="text-sm font-medium">{citation.title}</p>
                <p className="mt-1 text-xs text-raven-muted">
                  {citation.source_type} · {citation.id}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <EmptyBlock message="No citations were returned." />
        )}
      </section>
    </div>
  );
}

function SummaryBlock({ title, value }: { title: string; value: string }): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft p-4">
      <h3 className="text-sm font-semibold text-raven-text">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-raven-muted">{value}</p>
    </div>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }): JSX.Element {
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <h2 className="text-lg font-semibold">{title}</h2>
      {items.length ? (
        <ul className="mt-4 space-y-2 text-sm text-raven-muted">
          {items.map((item) => (
            <li key={item} className="rounded-md bg-raven-panelSoft p-3">
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <div className="mt-4">
          <EmptyBlock message="No items returned." />
        </div>
      )}
    </section>
  );
}
