import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  Loader2,
  RefreshCw,
} from "lucide-react";
import { useMemo } from "react";
import { useMutation } from "@tanstack/react-query";

import { InvestigationTabs } from "../components/InvestigationTabs";
import { PageHeader } from "../components/PageHeader";
import { SeverityBadge } from "../components/SeverityBadge";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { analyzeInvestigation } from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import type {
  AnalysisCitation,
  AnalysisRecommendation,
  AnalysisResponse,
  CitedText,
} from "../types";

export function AnalysisPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const analysis = useMutation<AnalysisResponse, Error, string>({
    mutationFn: analyzeInvestigation,
  });

  function runAnalysis(): void {
    analysis.mutate(investigationId);
  }

  return (
    <>
      <PageHeader
        title="AI Analysis"
        eyebrow="Evidence-backed analysis"
        actions={
          <button
            type="button"
            onClick={runAnalysis}
            disabled={analysis.isPending}
            className="inline-flex items-center gap-2 rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-60"
          >
            {analysis.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : analysis.data ? (
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
            ) : (
              <BrainCircuit className="h-4 w-4" aria-hidden="true" />
            )}
            {analysis.data ? "Retry analysis" : "Analyze"}
          </button>
        }
      />
      <InvestigationTabs />

      {analysis.isPending ? <LoadingBlock label="Preparing analysis" /> : null}
      {analysis.isError ? <ErrorBlock message={analysis.error.message} /> : null}
      {analysis.data ? (
        <AnalysisResult response={analysis.data} onRetry={runAnalysis} />
      ) : !analysis.isPending ? (
        <EmptyBlock message="No analysis response is loaded. Run analysis to correlate stored findings, recon, threat intelligence, and local knowledge citations." />
      ) : null}
    </>
  );
}

function AnalysisResult({
  response,
  onRetry,
}: {
  response: AnalysisResponse;
  onRetry: () => void;
}): JSX.Element {
  const citationGroups = useMemo(
    () => groupCitations(response.citations),
    [response.citations],
  );
  const hasProviderIssue = response.status !== "completed";

  return (
    <div className="space-y-5">
      {hasProviderIssue ? (
        <ProviderIssuePanel response={response} onRetry={onRetry} />
      ) : null}

      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-lg font-semibold">Assessment</h2>
            <p className="mt-1 text-sm text-raven-muted">
              {statusLabel(response.status)} | {response.provider}
              {response.model ? ` | ${response.model}` : ""}
            </p>
          </div>
          <SeverityBadge severity={response.severity} />
        </div>
        <div className="mt-5">
          <ConfidenceBar confidence={response.confidence} />
        </div>
        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          <SummaryBlock
            title="Executive summary"
            item={response.executive_summary}
          />
          <SummaryBlock
            title="Technical summary"
            item={response.technical_summary}
          />
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <CitedCardList title="Suspicious findings" items={response.suspicious_findings} />
        <RecommendationList items={response.recommended_next_steps} />
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <CitedCardList title="Observed indicators" items={response.observed_indicators} />
        <FrameworkMappings response={response} />
      </section>

      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <h2 className="text-lg font-semibold">Citations</h2>
        {response.citations.length ? (
          <div className="mt-4 space-y-4">
            {Object.entries(citationGroups).map(([sourceType, citations]) => (
              <div key={sourceType}>
                <p className="text-xs uppercase tracking-wide text-raven-muted">
                  {sourceType.replace(/_/g, " ")}
                </p>
                <div className="mt-2 grid gap-3 md:grid-cols-2">
                  {citations.map((citation) => (
                    <CitationCard key={citation.id} citation={citation} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyBlock message="No citations were returned. Analysis should be treated as incomplete until evidence is available." />
        )}
      </section>
    </div>
  );
}

function ProviderIssuePanel({
  response,
  onRetry,
}: {
  response: AnalysisResponse;
  onRetry: () => void;
}): JSX.Element {
  return (
    <section className="rounded-lg border border-amber-300/30 bg-amber-400/10 p-4 text-amber-100">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="flex gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5 flex-none" aria-hidden="true" />
          <div>
            <h2 className="font-semibold">{statusLabel(response.status)}</h2>
            <p className="mt-1 text-sm leading-6 text-amber-100/80">
              The analyst provider did not complete the request. Any visible
              summaries below are deterministic fallback content grounded in stored
              evidence and citations.
            </p>
            {response.errors.length ? (
              <ul className="mt-3 space-y-1 text-sm text-amber-100/80">
                {response.errors.map((error) => (
                  <li key={error}>- {error}</li>
                ))}
              </ul>
            ) : null}
          </div>
        </div>
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center justify-center gap-2 rounded-md border border-amber-200/40 px-3 py-2 text-sm text-amber-50 hover:bg-amber-200/10"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Retry
        </button>
      </div>
    </section>
  );
}

function SummaryBlock({
  title,
  item,
}: {
  title: string;
  item: CitedText;
}): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft p-4">
      <h3 className="text-sm font-semibold text-raven-text">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-raven-muted">{item.text}</p>
      <CitationChips citationIds={item.citation_ids} />
    </div>
  );
}

function CitedCardList({
  title,
  items,
}: {
  title: string;
  items: CitedText[];
}): JSX.Element {
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <h2 className="text-lg font-semibold">{title}</h2>
      {items.length ? (
        <div className="mt-4 space-y-3">
          {items.map((item) => (
            <div
              key={`${title}-${item.text}`}
              className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
            >
              <p className="text-sm leading-6 text-raven-muted">{item.text}</p>
              <CitationChips citationIds={item.citation_ids} />
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4">
          <EmptyBlock message="No items returned for this section." />
        </div>
      )}
    </section>
  );
}

function RecommendationList({
  items,
}: {
  items: AnalysisRecommendation[];
}): JSX.Element {
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <h2 className="text-lg font-semibold">Recommended next steps</h2>
      {items.length ? (
        <div className="mt-4 space-y-3">
          {items.map((item) => (
            <div
              key={`${item.action}-${item.rationale}`}
              className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
            >
              <div className="flex gap-2">
                <CheckCircle2 className="mt-0.5 h-4 w-4 flex-none text-raven-emerald" />
                <div>
                  <p className="text-sm font-medium">{item.action}</p>
                  <p className="mt-1 text-sm leading-6 text-raven-muted">
                    {item.rationale}
                  </p>
                </div>
              </div>
              <CitationChips citationIds={item.citation_ids} />
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4">
          <EmptyBlock message="No recommendations were returned." />
        </div>
      )}
    </section>
  );
}

function FrameworkMappings({
  response,
}: {
  response: AnalysisResponse;
}): JSX.Element {
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <h2 className="text-lg font-semibold">Framework mapping</h2>
      {response.framework_mappings.length ? (
        <div className="mt-4 space-y-3">
          {response.framework_mappings.map((mapping) => (
            <div
              key={`${mapping.framework}-${mapping.control}`}
              className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
            >
              <p className="text-sm font-medium">
                {mapping.framework}: {mapping.control}
              </p>
              <p className="mt-1 text-sm leading-6 text-raven-muted">
                {mapping.rationale}
              </p>
              <CitationChips citationIds={mapping.citation_ids} />
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4">
          <EmptyBlock message="No framework mappings were returned." />
        </div>
      )}
    </section>
  );
}

function CitationCard({
  citation,
}: {
  citation: AnalysisCitation;
}): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <p className="break-words text-sm font-medium">{citation.title}</p>
      <p className="mt-1 text-xs text-raven-muted">{citation.id}</p>
      <p className="mt-2 text-sm leading-6 text-raven-muted">{citation.summary}</p>
    </div>
  );
}

function ConfidenceBar({ confidence }: { confidence: number }): JSX.Element {
  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="text-raven-muted">Confidence</span>
        <span className="font-medium">{confidence}%</span>
      </div>
      <div className="mt-2 h-2 rounded-full bg-raven-panelSoft">
        <div
          className="h-2 rounded-full bg-raven-cyan"
          style={{ width: `${Math.min(100, Math.max(0, confidence))}%` }}
        />
      </div>
    </div>
  );
}

function CitationChips({
  citationIds,
}: {
  citationIds: string[];
}): JSX.Element | null {
  if (!citationIds.length) {
    return null;
  }
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {citationIds.map((id) => (
        <span
          key={id}
          className="max-w-full truncate rounded border border-raven-border px-2 py-1 text-xs text-raven-muted"
          title={id}
        >
          {id}
        </span>
      ))}
    </div>
  );
}

function groupCitations(
  citations: AnalysisCitation[],
): Record<string, AnalysisCitation[]> {
  return citations.reduce<Record<string, AnalysisCitation[]>>((groups, citation) => {
    const group = groups[citation.source_type] ?? [];
    group.push(citation);
    groups[citation.source_type] = group;
    return groups;
  }, {});
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    completed: "Analysis completed",
    provider_unavailable: "AI provider unavailable",
    provider_timeout: "AI provider timed out",
    provider_failed: "AI provider failed",
    malformed_response: "AI response could not be parsed",
  };
  return labels[status] ?? status.replace(/_/g, " ");
}
