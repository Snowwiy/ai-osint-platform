import { ChevronDown, ChevronRight, SearchX } from "lucide-react";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { InvestigationTabs } from "../components/InvestigationTabs";
import { PageHeader } from "../components/PageHeader";
import { SeverityBadge } from "../components/SeverityBadge";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { listFindings } from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import type { Finding, FindingEvidence, Severity } from "../types";

const severities: Array<Severity | "all"> = [
  "all",
  "critical",
  "high",
  "medium",
  "low",
  "info",
];
const severityRank: Record<Severity, number> = {
  critical: 5,
  high: 4,
  medium: 3,
  low: 2,
  info: 1,
};
type SortMode = "newest" | "severity";

export function FindingsPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [source, setSource] = useState("all");
  const [target, setTarget] = useState("all");
  const [sortMode, setSortMode] = useState<SortMode>("newest");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const findings = useQuery({
    queryKey: ["findings", investigationId],
    queryFn: () => listFindings(investigationId),
  });

  const sources = useMemo(() => {
    const unique = new Set((findings.data ?? []).map((item) => item.source));
    return ["all", ...Array.from(unique).sort()];
  }, [findings.data]);

  const targets = useMemo(() => {
    const unique = new Set((findings.data ?? []).flatMap(findingTargets));
    return ["all", ...Array.from(unique).sort()];
  }, [findings.data]);

  const filtered = useMemo(() => {
    const items = findings.data ?? [];
    return items
      .filter((item) => severity === "all" || item.severity === severity)
      .filter((item) => source === "all" || item.source === source)
      .filter((item) => target === "all" || findingTargets(item).includes(target))
      .sort((left, right) => {
        if (sortMode === "severity") {
          return (
            severityRank[right.severity] - severityRank[left.severity] ||
            right.risk_score - left.risk_score
          );
        }
        return (
          new Date(right.created_at).getTime() -
          new Date(left.created_at).getTime()
        );
      });
  }, [findings.data, severity, sortMode, source, target]);

  function toggleExpanded(id: string): void {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

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
          <div className="flex flex-wrap gap-2">
            <FilterSelect
              label="Severity"
              value={severity}
              options={severities}
              onChange={(value) => setSeverity(value as Severity | "all")}
            />
            <FilterSelect
              label="Source"
              value={source}
              options={sources}
              onChange={setSource}
            />
            <FilterSelect
              label="Target"
              value={target}
              options={targets}
              onChange={setTarget}
            />
            <FilterSelect
              label="Sort"
              value={sortMode}
              options={["newest", "severity"]}
              onChange={(value) => setSortMode(value as SortMode)}
            />
          </div>
        }
      />
      <InvestigationTabs />

      {filtered.length ? (
        <div className="space-y-4">
          {filtered.map((finding) => {
            const isExpanded = expanded.has(finding.id);
            return (
              <article
                key={finding.id}
                className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"
              >
                <button
                  type="button"
                  onClick={() => toggleExpanded(finding.id)}
                  className="flex w-full flex-col gap-3 text-left md:flex-row md:items-start md:justify-between"
                >
                  <div className="flex gap-3">
                    <span className="mt-1 text-raven-cyan">
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4" aria-hidden="true" />
                      ) : (
                        <ChevronRight className="h-4 w-4" aria-hidden="true" />
                      )}
                    </span>
                    <div>
                      <h2 className="font-semibold">{finding.title}</h2>
                      <p className="mt-2 line-clamp-2 text-sm leading-6 text-raven-muted">
                        {finding.description}
                      </p>
                    </div>
                  </div>
                  <SeverityBadge severity={finding.severity} />
                </button>

                <div className="mt-4 grid gap-3 text-sm text-raven-muted md:grid-cols-5">
                  <Metric label="Risk" value={`${finding.risk_score}/100`} />
                  <Metric
                    label="Confidence"
                    value={`${finding.confidence_score}%`}
                  />
                  <Metric label="Source" value={finding.source} />
                  <Metric label="Status" value={finding.status} />
                  <Metric
                    label="Created"
                    value={new Date(finding.created_at).toLocaleString()}
                  />
                </div>

                {isExpanded ? <FindingDetails finding={finding} /> : null}
              </article>
            );
          })}
        </div>
      ) : findings.data?.length ? (
        <EmptyBlock message="No findings match the current filters. Clear a filter or change the sort to review stored findings." />
      ) : (
        <EmptyBlock message="No findings have been generated yet. Run passive recon and threat intelligence, then correlation can create evidence-backed findings." />
      )}
    </>
  );
}

function FindingDetails({ finding }: { finding: Finding }): JSX.Element {
  const targets = findingTargets(finding);
  return (
    <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_0.8fr]">
      <section className="rounded-md border border-raven-border bg-raven-panelSoft p-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-raven-muted">
          Evidence Summary
        </h3>
        {finding.evidence.length ? (
          <div className="mt-3 space-y-3">
            {finding.evidence.map((item) => (
              <EvidenceCard key={item.id} evidence={item} />
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-raven-muted">
            No detailed evidence records are linked to this finding yet.
          </p>
        )}
      </section>

      <section className="rounded-md border border-raven-border bg-raven-panelSoft p-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-raven-muted">
          Citations and Context
        </h3>
        <div className="mt-3 space-y-3 text-sm text-raven-muted">
          <div>
            <p className="text-xs uppercase tracking-wide">Targets</p>
            <ChipList values={targets} empty="No target metadata found." />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide">Tags</p>
            <ChipList values={finding.tags} empty="No tags stored." />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide">Evidence IDs</p>
            <ChipList
              values={finding.evidence.map((item) => item.id)}
              empty="No evidence citations stored."
            />
          </div>
          <div className="grid gap-2 pt-1 text-xs">
            <p>Updated {new Date(finding.updated_at).toLocaleString()}</p>
            <p>Finding ID {finding.id}</p>
          </div>
        </div>
      </section>
    </div>
  );
}

function EvidenceCard({ evidence }: { evidence: FindingEvidence }): JSX.Element {
  const citations = [
    evidence.recon_entity_id ? `recon:${evidence.recon_entity_id}` : null,
    evidence.threat_finding_id ? `threat:${evidence.threat_finding_id}` : null,
  ].filter((item): item is string => item !== null);

  return (
    <div className="rounded-md border border-raven-border bg-raven-bg/60 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium">{evidence.evidence_type}</p>
        <span className="rounded border border-raven-border px-2 py-0.5 text-xs text-raven-cyan">
          {evidence.source}
        </span>
      </div>
      <p className="mt-2 text-sm leading-6 text-raven-muted">
        {evidence.description}
      </p>
      {citations.length ? (
        <div className="mt-3">
          <ChipList values={citations} empty="" />
        </div>
      ) : null}
    </div>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}): JSX.Element {
  return (
    <label className="flex items-center gap-2 rounded-md border border-raven-border bg-raven-panel px-3 py-2 text-sm text-raven-muted">
      <span>{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="bg-transparent text-raven-text outline-none"
      >
        {options.map((item) => (
          <option key={item} value={item}>
            {labelForOption(item)}
          </option>
        ))}
      </select>
    </label>
  );
}

function Metric({ label, value }: { label: string; value: string | number }): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2">
      <p className="text-xs uppercase tracking-wide">{label}</p>
      <p className="mt-1 break-words text-raven-text">{value}</p>
    </div>
  );
}

function ChipList({
  values,
  empty,
}: {
  values: string[];
  empty: string;
}): JSX.Element {
  if (!values.length) {
    return (
      <div className="mt-2 flex items-center gap-2 text-xs text-raven-muted">
        <SearchX className="h-3.5 w-3.5" aria-hidden="true" />
        {empty}
      </div>
    );
  }
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {values.map((value) => (
        <span
          key={value}
          className="max-w-full truncate rounded border border-raven-border px-2 py-1 text-xs text-raven-muted"
          title={value}
        >
          {value}
        </span>
      ))}
    </div>
  );
}

function findingTargets(finding: Finding): string[] {
  const values = new Set<string>();
  for (const evidence of finding.evidence) {
    for (const key of ["target", "target_value", "value", "domain", "ip", "url", "host", "hostname"]) {
      const raw = evidence.data[key];
      if (typeof raw === "string" && raw.trim()) {
        values.add(raw.trim());
      }
    }
  }
  return Array.from(values);
}

function labelForOption(value: string): string {
  if (value === "all") {
    return "All";
  }
  if (value === "severity") {
    return "Highest severity";
  }
  return value.replace(/_/g, " ");
}
