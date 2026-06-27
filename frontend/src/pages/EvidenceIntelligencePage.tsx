import {
  Activity,
  AlertTriangle,
  BarChart3,
  DatabaseZap,
  GitBranch,
  Layers3,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { LongValue } from "../components/LongValue";
import { PageHeader } from "../components/PageHeader";
import { StatCard } from "../components/StatCard";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import {
  getEvidenceIntelligenceEvidence,
  getEvidenceIntelligenceIocs,
  getEvidenceIntelligenceOverview,
  getEvidenceIntelligencePriority,
  getEvidenceIntelligenceTimeline,
} from "../lib/api";
import type {
  EvidenceIntelligenceItem,
  EvidenceIntelligencePriorityItem,
  EvidenceIntelligenceTimelineEvent,
  EvidenceIOCIntelligenceItem,
  IntelligenceConfidence,
} from "../types";

type IntelligenceView = "overview" | "evidence" | "priority" | "timeline" | "iocs";

const views: Array<{ id: IntelligenceView; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "evidence", label: "Recurring Evidence" },
  { id: "priority", label: "Priority" },
  { id: "timeline", label: "Timeline" },
  { id: "iocs", label: "IOC Intelligence" },
];

export function EvidenceIntelligencePage(): JSX.Element {
  const [view, setView] = useState<IntelligenceView>("overview");
  const overview = useQuery({
    queryKey: ["evidence-intelligence-overview"],
    queryFn: getEvidenceIntelligenceOverview,
    staleTime: 30_000,
  });
  const evidence = useQuery({
    queryKey: ["evidence-intelligence-evidence"],
    queryFn: getEvidenceIntelligenceEvidence,
    staleTime: 30_000,
  });
  const priority = useQuery({
    queryKey: ["evidence-intelligence-priority"],
    queryFn: getEvidenceIntelligencePriority,
    staleTime: 30_000,
  });
  const timeline = useQuery({
    queryKey: ["evidence-intelligence-timeline"],
    queryFn: getEvidenceIntelligenceTimeline,
    staleTime: 30_000,
  });
  const iocs = useQuery({
    queryKey: ["evidence-intelligence-iocs"],
    queryFn: getEvidenceIntelligenceIocs,
    staleTime: 30_000,
  });
  const error =
    overview.error ?? evidence.error ?? priority.error ?? timeline.error ?? iocs.error;

  if (overview.isLoading || evidence.isLoading || priority.isLoading) {
    return <LoadingBlock label="Loading evidence intelligence" />;
  }
  if (error) {
    return <ErrorBlock message={error} />;
  }

  return (
    <>
      <PageHeader
        title="Evidence Intelligence"
        eyebrow="Cross-investigation recurrence"
        actions={
          <button
            type="button"
            onClick={() => {
              void overview.refetch();
              void evidence.refetch();
              void priority.refetch();
              void timeline.refetch();
              void iocs.refetch();
            }}
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm hover:border-raven-violet"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh intelligence
          </button>
        }
      />

      <section className="mb-5 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <div className="flex items-start gap-3">
          <ShieldCheck
            className="mt-0.5 h-5 w-5 flex-none text-raven-cyan"
            aria-hidden="true"
          />
          <p className="max-w-4xl text-sm leading-6 text-raven-muted">
            Evidence Intelligence highlights repeated passive evidence, recurring
            infrastructure, IOC visibility, and case priority using only stored
            investigations. It does not perform external enrichment or automated
            action.
          </p>
        </div>
        <nav className="themed-scrollbar mt-4 flex gap-2 overflow-x-auto pb-1">
          {views.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setView(item.id)}
              className={[
                "whitespace-nowrap rounded-md border px-3 py-2 text-sm",
                view === item.id
                  ? "border-raven-violet bg-raven-violet text-white"
                  : "border-raven-border text-raven-muted hover:text-raven-text",
              ].join(" ")}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </section>

      {view === "overview" ? (
        <OverviewPanel
          totalItems={overview.data?.total_items}
          domains={overview.data?.recurring_domains}
          ips={overview.data?.recurring_ips}
          technologies={overview.data?.recurring_technologies}
          findings={overview.data?.recurring_findings}
          frameworks={overview.data?.recurring_framework_mappings}
          highRisk={overview.data?.repeated_high_risk_items}
        />
      ) : null}
      {view === "evidence" ? (
        <EvidencePanel items={evidence.data?.items} />
      ) : null}
      {view === "priority" ? (
        <PriorityPanel items={priority.data?.items} />
      ) : null}
      {view === "timeline" ? (
        <TimelinePanel items={timeline.data?.items} isLoading={timeline.isLoading} />
      ) : null}
      {view === "iocs" ? (
        <IocPanel items={iocs.data?.items} isLoading={iocs.isLoading} />
      ) : null}
    </>
  );
}

function OverviewPanel({
  totalItems,
  domains,
  ips,
  technologies,
  findings,
  frameworks,
  highRisk,
}: {
  totalItems: number | undefined;
  domains: EvidenceIntelligenceItem[] | undefined;
  ips: EvidenceIntelligenceItem[] | undefined;
  technologies: EvidenceIntelligenceItem[] | undefined;
  findings: EvidenceIntelligenceItem[] | undefined;
  frameworks: EvidenceIntelligenceItem[] | undefined;
  highRisk: EvidenceIntelligenceItem[] | undefined;
}): JSX.Element {
  const domainItems = safeArray(domains);
  const ipItems = safeArray(ips);
  const technologyItems = safeArray(technologies);
  const findingItems = safeArray(findings);
  const frameworkItems = safeArray(frameworks);
  const highRiskItems = safeArray(highRisk);
  return (
    <div className="space-y-5">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard
          label="Evidence items"
          value={safeNumber(totalItems)}
          detail="Stored signals"
          icon={<DatabaseZap className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Recurring domains"
          value={domainItems.length}
          detail="Domains and subdomains"
          icon={<GitBranch className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Recurring IPs"
          value={ipItems.length}
          detail="Infrastructure signals"
          icon={<Layers3 className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Technologies"
          value={technologyItems.length}
          detail="Repeated stack signals"
          icon={<BarChart3 className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="High-risk repeats"
          value={highRiskItems.length}
          detail="Needs review"
          icon={<AlertTriangle className="h-5 w-5" aria-hidden="true" />}
        />
      </section>
      <section className="grid gap-5 xl:grid-cols-2">
        <ItemGroup title="Recurring infrastructure" items={[...domainItems, ...ipItems]} />
        <ItemGroup title="Recurring findings" items={findingItems} />
        <ItemGroup title="Recurring technologies" items={technologyItems} />
        <ItemGroup title="Framework mappings" items={frameworkItems} />
      </section>
    </div>
  );
}

function EvidencePanel({
  items,
}: {
  items: EvidenceIntelligenceItem[] | undefined;
}): JSX.Element {
  const allItems = safeArray(items);
  const grouped = useMemo(() => {
    return allItems.reduce<Record<string, EvidenceIntelligenceItem[]>>(
      (groups, item) => {
        const key = item.item_type || "evidence";
        groups[key] = [...(groups[key] ?? []), item];
        return groups;
      },
      {},
    );
  }, [allItems]);
  if (!allItems.length) {
    return (
      <EmptyBlock
        title="No recurring evidence yet"
        message="Evidence intelligence appears after passive evidence, findings, or framework mappings are stored across accessible investigations."
        nextStep="Run authorized passive recon and generate evidence-backed findings."
      />
    );
  }
  return (
    <div className="space-y-5">
      {Object.entries(grouped).map(([itemType, values]) => (
        <ItemGroup
          key={itemType}
          title={formatLabel(itemType)}
          items={values}
          expanded
        />
      ))}
    </div>
  );
}

function PriorityPanel({
  items,
}: {
  items: EvidenceIntelligencePriorityItem[] | undefined;
}): JSX.Element {
  const priorityItems = safeArray(items);
  if (!priorityItems.length) {
    return (
      <EmptyBlock
        title="No priority recommendations"
        message="Priority recommendations appear after accessible investigations contain findings, IOCs, tasks, or recurring evidence."
        nextStep="Continue analyst review and remediation tracking."
      />
    );
  }
  return (
    <section className="themed-scrollbar overflow-x-auto rounded-lg border border-raven-border">
      <table className="w-full min-w-[980px] text-left text-sm">
        <thead className="bg-raven-panelSoft text-xs uppercase text-raven-muted">
          <tr>
            <th className="px-4 py-3">Investigation</th>
            <th className="px-4 py-3">Suggested priority</th>
            <th className="px-4 py-3">Score</th>
            <th className="px-4 py-3">Why</th>
            <th className="px-4 py-3">Metrics</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-raven-border bg-raven-panel/70">
          {priorityItems.map((item) => (
            <tr key={item.investigation_id}>
              <td className="px-4 py-3">
                <Link
                  to={`/investigations/${item.investigation_id}`}
                  className="font-medium text-raven-cyan hover:text-raven-text"
                >
                  {item.investigation_title}
                </Link>
                <p className="mt-1 text-xs capitalize text-raven-muted">
                  Current: {item.current_priority}
                </p>
              </td>
              <td className="px-4 py-3">
                <PriorityBadge value={item.suggested_priority} />
              </td>
              <td className="px-4 py-3 text-lg font-semibold">{item.score}/100</td>
              <td className="px-4 py-3">
                <ul className="space-y-1 text-raven-muted">
                  {safeArray(item.reasons).map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </td>
              <td className="px-4 py-3 text-xs text-raven-muted">
                {Object.entries(item.metrics ?? {}).map(([key, value]) => (
                  <p key={key}>
                    {formatLabel(key)}: {safeNumber(value)}
                  </p>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function TimelinePanel({
  items,
  isLoading,
}: {
  items: EvidenceIntelligenceTimelineEvent[] | undefined;
  isLoading: boolean;
}): JSX.Element {
  if (isLoading) {
    return <LoadingBlock label="Loading intelligence timeline" />;
  }
  const events = safeArray(items);
  if (!events.length) {
    return (
      <EmptyBlock
        title="No intelligence timeline"
        message="Chronological recurrence events appear after evidence is observed or linked to remediation."
        nextStep="Collect passive evidence and update remediation status."
      />
    );
  }
  return (
    <div className="space-y-3">
      {events.map((event) => (
        <article
          key={event.id}
          className="flex min-w-0 gap-3 rounded-lg border border-raven-border bg-raven-panel/85 p-4"
        >
          <Activity className="mt-0.5 h-4 w-4 flex-none text-raven-cyan" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-medium">{event.title}</p>
                <p className="mt-1 text-sm leading-6 text-raven-muted">
                  {event.summary}
                </p>
              </div>
              <ConfidenceBadge value={event.confidence} />
            </div>
            <LongValue value={event.value} className="mt-3" />
            <p className="mt-2 text-xs text-raven-muted">
              {formatDate(event.timestamp)}
              {event.investigation_title ? ` | ${event.investigation_title}` : ""}
            </p>
          </div>
        </article>
      ))}
    </div>
  );
}

function IocPanel({
  items,
  isLoading,
}: {
  items: EvidenceIOCIntelligenceItem[] | undefined;
  isLoading: boolean;
}): JSX.Element {
  if (isLoading) {
    return <LoadingBlock label="Loading IOC intelligence" />;
  }
  const iocItems = safeArray(items);
  if (!iocItems.length) {
    return (
      <EmptyBlock
        title="No IOC intelligence"
        message="Normalized IOC visibility appears after recon entities are stored and synchronized as reusable indicators."
        nextStep="Run authorized passive recon in an investigation."
      />
    );
  }
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {iocItems.map((item) => (
        <article
          key={item.ioc_id}
          className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs uppercase tracking-wide text-raven-cyan">
                {item.type}
              </p>
              <LongValue value={item.value} className="mt-1 font-semibold" />
            </div>
            <span className="rounded border border-raven-border px-2 py-1 text-xs capitalize text-raven-muted">
              {item.confidence}
            </span>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <MiniMetric label="Frequency" value={item.frequency} />
            <MiniMetric label="Investigations" value={item.investigation_count} />
            <MiniMetric
              label="Findings"
              value={safeArray(item.seen_in_findings).length}
            />
          </div>
          <p className="mt-3 text-xs text-raven-muted">
            First seen {formatDate(item.first_seen)} | Last seen{" "}
            {formatDate(item.last_seen)}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {safeArray(item.seen_in_investigations).slice(0, 5).map((reference) => (
              <Link
                key={reference.investigation_id}
                to={`/investigations/${reference.investigation_id}`}
                className="max-w-full break-words rounded border border-raven-border px-2 py-1 text-xs text-raven-cyan hover:border-raven-violet"
              >
                {reference.investigation_title}
              </Link>
            ))}
          </div>
        </article>
      ))}
    </div>
  );
}

function ItemGroup({
  title,
  items,
  expanded = false,
}: {
  title: string;
  items: EvidenceIntelligenceItem[];
  expanded?: boolean;
}): JSX.Element {
  const safeItems = safeArray(items);
  return (
    <section className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-semibold">{title}</h2>
        <span className="text-xs text-raven-muted">{safeItems.length} signals</span>
      </div>
      {safeItems.length ? (
        <div className="mt-4 space-y-3">
          {safeItems.slice(0, expanded ? 50 : 5).map((item) => (
            <article
              key={item.id}
              className="min-w-0 rounded-md border border-raven-border bg-raven-panelSoft p-3"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <LongValue value={item.value} className="min-w-0 flex-1" />
                <ConfidenceBadge value={item.confidence} />
              </div>
              <p className="mt-3 text-xs text-raven-muted">
                {item.occurrence_count} observations across{" "}
                {item.investigation_count} investigations | {item.source_count} sources
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {safeArray(item.related_investigations).slice(0, 5).map((reference) => (
                  <Link
                    key={`${item.id}:${reference.investigation_id}`}
                    to={`/investigations/${reference.investigation_id}`}
                    className="max-w-full break-words rounded border border-raven-border px-2 py-1 text-xs text-raven-cyan hover:border-raven-violet"
                  >
                    {reference.investigation_title}
                  </Link>
                ))}
              </div>
              <ul className="mt-3 space-y-1 text-xs text-raven-muted">
                {safeArray(item.confidence_reasons).slice(0, 3).map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-raven-muted">
          No recurring {title.toLowerCase()} is visible yet.
        </p>
      )}
    </section>
  );
}

function MiniMetric({
  label,
  value,
}: {
  label: string;
  value: number;
}): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-bg/60 p-3">
      <p className="text-xs uppercase tracking-wide text-raven-muted">{label}</p>
      <p className="mt-1 text-xl font-semibold">{safeNumber(value)}</p>
    </div>
  );
}

function ConfidenceBadge({ value }: { value: IntelligenceConfidence }): JSX.Element {
  const tone =
    value === "Very High"
      ? "border-fuchsia-400/40 bg-fuchsia-500/10 text-fuchsia-100"
      : value === "High"
        ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-100"
        : value === "Medium"
          ? "border-amber-400/40 bg-amber-500/10 text-amber-100"
          : "border-slate-400/30 bg-slate-500/10 text-slate-200";
  return <span className={`rounded border px-2 py-1 text-xs ${tone}`}>{value}</span>;
}

function PriorityBadge({
  value,
}: {
  value: "Low" | "Medium" | "High" | "Critical";
}): JSX.Element {
  const tone =
    value === "Critical"
      ? "border-rose-400/40 bg-rose-500/10 text-rose-100"
      : value === "High"
        ? "border-orange-400/40 bg-orange-500/10 text-orange-100"
        : value === "Medium"
          ? "border-amber-400/40 bg-amber-500/10 text-amber-100"
          : "border-emerald-400/40 bg-emerald-500/10 text-emerald-100";
  return <span className={`rounded border px-2 py-1 text-xs ${tone}`}>{value}</span>;
}

function safeArray<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

function safeNumber(value: number | null | undefined): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function formatLabel(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "No timestamp";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Invalid timestamp";
  }
  return date.toLocaleString();
}
