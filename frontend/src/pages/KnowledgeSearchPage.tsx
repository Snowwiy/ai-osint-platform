import { Check, Copy, RadioTower, Search, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import {
  getDetectionKnowledge,
  getFrameworkKnowledge,
  getIocGuidance,
  searchKnowledge,
} from "../lib/api";
import type {
  DetectionKnowledgeCard,
  IOCGuidanceCard,
  KnowledgeSearchResponse,
  KnowledgeSearchResult,
} from "../types";

const examples = [
  "exposed RDP defensive controls",
  "SPF and DMARC mitigation",
  "NIST incident response containment",
  "OWASP access control guidance",
];

export function KnowledgeSearchPage(): JSX.Element {
  const [query, setQuery] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const search = useMutation<KnowledgeSearchResponse, Error, string>({
    mutationFn: searchKnowledge,
  });
  const detections = useQuery({
    queryKey: ["knowledge-detections"],
    queryFn: () => getDetectionKnowledge(),
  });
  const frameworks = useQuery({
    queryKey: ["knowledge-frameworks"],
    queryFn: getFrameworkKnowledge,
  });
  const iocGuidance = useQuery({
    queryKey: ["knowledge-ioc-guidance"],
    queryFn: () => getIocGuidance(),
  });

  function submitQuery(value: string): void {
    const clean = value.trim();
    if (clean.length < 2) {
      setValidationError("Enter at least two characters to search.");
      return;
    }
    setValidationError(null);
    search.reset();
    search.mutate(clean);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    submitQuery(query);
  }

  const searchItems = search.data?.items ?? [];
  const detectionItems = detections.data?.items ?? [];
  const iocGuidanceItems = iocGuidance.data?.items ?? [];

  return (
    <>
      <PageHeader title="Knowledge Search" eyebrow="Local defensive knowledge" />
      <section className="mb-6 rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <div className="flex items-start gap-3">
          <ShieldCheck
            className="mt-0.5 h-5 w-5 flex-none text-cyan-300"
            aria-hidden="true"
          />
          <div>
            <h2 className="font-semibold">Search curated defensive guidance</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-raven-muted">
              Results come only from the locally indexed RavenTech knowledge base.
              This search does not browse the internet or execute security actions.
            </p>
          </div>
        </div>

        <form
          onSubmit={handleSubmit}
          className="mt-5 flex flex-col gap-3 md:flex-row"
        >
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setValidationError(null);
            }}
            placeholder="Search a control, mitigation, framework, or defensive topic"
            aria-label="Knowledge search query"
            className="min-w-0 flex-1 rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
          />
          <button
            type="submit"
            disabled={search.isPending || query.trim().length < 2}
            className="inline-flex items-center justify-center gap-2 rounded-md bg-raven-violet px-4 py-2 font-medium text-white hover:bg-violet-500 disabled:opacity-50"
          >
            <Search className="h-4 w-4" aria-hidden="true" />
            {search.isPending ? "Searching" : "Search knowledge"}
          </button>
        </form>

        {validationError ? (
          <p className="mt-2 text-sm text-rose-200">{validationError}</p>
        ) : null}

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-xs uppercase text-raven-muted">Examples</span>
          {examples.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => {
                setQuery(example);
                submitQuery(example);
              }}
              disabled={search.isPending}
              className="rounded border border-raven-border px-2.5 py-1 text-xs text-raven-muted hover:border-raven-violet hover:text-raven-text disabled:opacity-50"
            >
              {example}
            </button>
          ))}
        </div>
      </section>

      {search.isPending ? <LoadingBlock label="Searching local knowledge" /> : null}
      {search.isError ? <ErrorBlock message={search.error} /> : null}
      {search.data ? (
        searchItems.length ? (
          <section className="space-y-4">
            <p className="text-sm text-raven-muted">
              {search.data.total} result{search.data.total === 1 ? "" : "s"} for
              {" "}
              <span className="text-raven-text">{search.data.query}</span>
            </p>
            {searchItems.map((item) => (
              <KnowledgeResultCard
                key={`${item.document_id}-${(item.chunk ?? "").slice(0, 20)}`}
                item={item}
              />
            ))}
          </section>
        ) : (
          <EmptyBlock
            title="No local guidance matched"
            message="The curated local library did not contain a matching defensive reference."
            nextStep="Try a control family, mitigation, framework, or technology name."
          />
        )
      ) : search.isIdle ? (
        <EmptyBlock
          title="Search local defensive knowledge"
          message="This library provides framework guidance, mitigations, and citation-ready references without browsing the internet."
          nextStep="Choose an example above or enter a defensive control, technology, or mitigation."
        />
      ) : null}

      <section className="mt-8">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-raven-cyan">
              Detection engineering library
            </p>
            <h2 className="mt-1 text-lg font-semibold">
              Sigma and YARA defensive references
            </h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-raven-muted">
              Analyst reference material only. Nothing is executed, deployed, or
              evaluated against live systems.
            </p>
          </div>
          <span className="text-xs text-raven-muted">
            {frameworks.data?.total ?? 0} supported knowledge frameworks
          </span>
        </div>
        {detections.isLoading ? (
          <LoadingBlock label="Loading defensive detection references" />
        ) : detections.isError ? (
          <ErrorBlock message={detections.error} />
        ) : detectionItems.length ? (
          <div className="grid gap-4 xl:grid-cols-2">
            {detectionItems.map((item) => (
              <DetectionReferenceCard key={item.id} item={item} />
            ))}
          </div>
        ) : (
          <EmptyBlock
            title="No detection references available"
            message="The local defensive library does not currently contain Sigma or YARA references."
            nextStep="An administrator can index approved local knowledge sources."
          />
        )}
      </section>

      <section className="mt-8">
        <div className="mb-3">
          <p className="text-xs uppercase tracking-wide text-raven-cyan">
            Threat intelligence knowledge
          </p>
          <h2 className="mt-1 text-lg font-semibold">
            IOC guidance and defensive investigation context
          </h2>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-raven-muted">
            Local analyst guidance for recurring infrastructure, exposed services,
            DNS posture, authentication telemetry, and remediation. No external
            enrichment is performed.
          </p>
        </div>
        {iocGuidance.isLoading ? (
          <LoadingBlock label="Loading IOC guidance" />
        ) : iocGuidance.isError ? (
          <ErrorBlock message={iocGuidance.error} />
        ) : iocGuidanceItems.length ? (
          <div className="grid gap-4 xl:grid-cols-2">
            {iocGuidanceItems.map((item) => (
              <IOCGuidanceCardView key={item.id} item={item} />
            ))}
          </div>
        ) : (
          <EmptyBlock
            title="No IOC guidance available"
            message="The local defensive library does not currently contain IOC guidance."
            nextStep="Continue using approved framework and detection references."
          />
        )}
      </section>
    </>
  );
}

function KnowledgeResultCard({
  item,
}: {
  item: KnowledgeSearchResult;
}): JSX.Element {
  const [copied, setCopied] = useState(false);
  const reference = `${item.title} | ${item.file_path} | ${item.document_id}`;
  const remediationGuidance = safeStringArray(item.remediation_guidance);
  const tags = safeStringArray(item.tags);
  const score =
    typeof item.score === "number" && Number.isFinite(item.score)
      ? item.score
      : 0;

  async function copyReference(): Promise<void> {
    try {
      await window.navigator.clipboard.writeText(reference);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  }

  return (
    <article className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="break-words font-semibold">{item.title}</h2>
          <p className="mt-1 text-xs text-raven-muted">
            {item.framework ?? item.source_type} | {item.category} | relevance{" "}
            {score.toFixed(2)}
          </p>
        </div>
        <button
          type="button"
          onClick={() => void copyReference()}
          className="inline-flex flex-none items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-xs text-raven-muted hover:border-raven-violet hover:text-raven-text"
        >
          {copied ? (
            <Check className="h-3.5 w-3.5" aria-hidden="true" />
          ) : (
            <Copy className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          {copied ? "Copied" : "Copy reference"}
        </button>
      </div>

      <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-raven-muted">
        {item.chunk ?? "No excerpt is available for this reference."}
      </p>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <KnowledgeContext
          title="Why this matters"
          text={item.why_this_matters}
        />
        <KnowledgeContext
          title="Defensive explanation"
          text={item.defensive_explanation}
        />
        {item.mitre_relevance ? (
          <KnowledgeContext title="MITRE relevance" text={item.mitre_relevance} />
        ) : null}
        {item.sigma_relevance ? (
          <KnowledgeContext title="Sigma relevance" text={item.sigma_relevance} />
        ) : null}
      </div>

      {remediationGuidance.length ? (
        <div className="mt-4">
          <p className="text-xs uppercase text-raven-muted">
            Remediation guidance
          </p>
          <ul className="mt-2 space-y-1 text-sm text-raven-muted">
            {remediationGuidance.map((guidance) => (
              <li key={guidance} className="break-words">
                {guidance}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <dl className="mt-4 grid min-w-0 gap-3 text-xs sm:grid-cols-2">
        <div className="min-w-0">
          <dt className="uppercase text-raven-muted">Source path</dt>
          <dd className="mt-1 break-all text-raven-text" title={item.file_path}>
            {item.file_path}
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="uppercase text-raven-muted">Document ID</dt>
          <dd className="mt-1 break-all text-raven-text">{item.document_id}</dd>
        </div>
      </dl>

      {tags.length ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {tags.map((tag) => (
            <span
              key={tag}
              className="rounded border border-raven-border px-2 py-0.5 text-xs text-raven-muted"
            >
              {tag}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function KnowledgeContext({
  title,
  text,
}: {
  title: string;
  text: string;
}): JSX.Element {
  return (
    <div className="min-w-0 rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <p className="text-xs uppercase text-raven-muted">{title}</p>
      <p className="mt-2 break-words text-sm leading-6 text-raven-text">{text}</p>
    </div>
  );
}

function DetectionReferenceCard({
  item,
}: {
  item: DetectionKnowledgeCard;
}): JSX.Element {
  const [copied, setCopied] = useState(false);
  const references = safeStringArray(item.references);
  async function copyReference(): Promise<void> {
    try {
      await window.navigator.clipboard.writeText(
        `${item.id} | ${item.title} | ${references.join(", ")}`,
      );
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  }
  return (
    <article className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-xs uppercase tracking-wide text-raven-cyan">
            <RadioTower className="h-4 w-4" aria-hidden="true" />
            {item.framework} | {item.category}
          </p>
          <h3 className="mt-2 break-words font-semibold">{item.title}</h3>
        </div>
        <button
          type="button"
          onClick={() => void copyReference()}
          className="inline-flex flex-none items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-xs text-raven-muted hover:border-raven-violet hover:text-raven-text"
        >
          {copied ? (
            <Check className="h-3.5 w-3.5" aria-hidden="true" />
          ) : (
            <Copy className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          {copied ? "Copied" : "Copy reference"}
        </button>
      </div>
      <p className="mt-3 text-sm leading-6 text-raven-muted">
        {item.description}
      </p>
      {item.log_source ? (
        <p className="mt-3 text-sm text-raven-text">
          <span className="text-raven-muted">Log source:</span> {item.log_source}
        </p>
      ) : null}
      <div className="mt-3 rounded-md border border-raven-border bg-raven-panelSoft p-3">
        <p className="text-xs uppercase text-raven-muted">Detection idea</p>
        <p className="mt-2 text-sm leading-6">{item.detection_idea}</p>
      </div>
      <p className="mt-3 text-sm leading-6 text-raven-muted">
        <span className="font-medium text-raven-text">Why this matters:</span>{" "}
        {item.why_this_matters}
      </p>
    </article>
  );
}

function IOCGuidanceCardView({
  item,
}: {
  item: IOCGuidanceCard;
}): JSX.Element {
  const appliesTo = safeStringArray(item.applies_to);
  return (
    <article className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <p className="text-xs uppercase tracking-wide text-raven-cyan">
        IOC defensive guidance
      </p>
      <h3 className="mt-2 break-words font-semibold">{item.title}</h3>
      <p className="mt-3 text-sm leading-6 text-raven-muted">
        <span className="font-medium text-raven-text">Why this matters:</span>{" "}
        {item.why_this_matters}
      </p>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <GuidanceList title="Monitoring" items={item.monitoring_guidance} />
        <GuidanceList title="Logging" items={item.logging_recommendations} />
        <GuidanceList title="MITRE relevance" items={item.mitre_relevance} />
        <GuidanceList title="Sigma references" items={item.sigma_references} />
      </div>
      <div className="mt-3">
        <GuidanceList title="Remediation" items={item.remediation_guidance} />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {appliesTo.map((value) => (
          <span
            key={value}
            className="rounded border border-raven-border px-2 py-1 text-xs text-raven-muted"
          >
            {value}
          </span>
        ))}
      </div>
    </article>
  );
}

function GuidanceList({
  title,
  items,
}: {
  title: string;
  items: string[];
}): JSX.Element {
  const safeItems = safeStringArray(items);
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <p className="text-xs uppercase text-raven-muted">{title}</p>
      {safeItems.length ? (
        <ul className="mt-2 space-y-1 text-sm leading-6">
          {safeItems.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-raven-muted">
          No forced mapping is applied.
        </p>
      )}
    </div>
  );
}

function safeStringArray(value: string[] | null | undefined): string[] {
  return Array.isArray(value) ? value : [];
}
