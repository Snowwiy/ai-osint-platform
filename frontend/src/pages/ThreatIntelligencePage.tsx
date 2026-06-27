import {
  Activity,
  CalendarClock,
  FileSearch,
  Flag,
  GitBranch,
  Network,
  RefreshCw,
  Search,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { LongValue } from "../components/LongValue";
import { PageHeader } from "../components/PageHeader";
import { StatCard } from "../components/StatCard";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import {
  getThreatCampaigns,
  getThreatGroups,
  getThreatIndicators,
  getThreatInfrastructure,
  getThreatOverview,
  getThreatTechniques,
  getThreatTimeline,
} from "../lib/api";
import type {
  ThreatCampaignSummary,
  ThreatGroupSummary,
  ThreatIndicatorSummary,
  ThreatInfrastructureSummary,
  ThreatTechniqueSummary,
  ThreatTimelineEvent,
  ThreatWorkspaceConfidence,
} from "../types";

type ThreatView =
  | "overview"
  | "indicators"
  | "campaigns"
  | "groups"
  | "techniques"
  | "infrastructure"
  | "timeline";

const views: Array<{ id: ThreatView; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "indicators", label: "Indicators" },
  { id: "campaigns", label: "Campaigns" },
  { id: "groups", label: "Threat Groups" },
  { id: "techniques", label: "ATT&CK Techniques" },
  { id: "infrastructure", label: "Infrastructure" },
  { id: "timeline", label: "Timeline" },
];

export function ThreatIntelligencePage(): JSX.Element {
  const { id: investigationId } = useParams();
  const [view, setView] = useState<ThreatView>("overview");
  const [query, setQuery] = useState("");
  const overview = useQuery({
    queryKey: ["threat-overview"],
    queryFn: getThreatOverview,
    staleTime: 30_000,
  });
  const indicators = useQuery({
    queryKey: ["threat-indicators"],
    queryFn: getThreatIndicators,
    staleTime: 30_000,
  });
  const campaigns = useQuery({
    queryKey: ["threat-campaigns"],
    queryFn: getThreatCampaigns,
    staleTime: 30_000,
  });
  const groups = useQuery({
    queryKey: ["threat-groups"],
    queryFn: getThreatGroups,
    staleTime: 30_000,
  });
  const techniques = useQuery({
    queryKey: ["threat-techniques"],
    queryFn: getThreatTechniques,
    staleTime: 30_000,
  });
  const infrastructure = useQuery({
    queryKey: ["threat-infrastructure"],
    queryFn: getThreatInfrastructure,
    staleTime: 30_000,
  });
  const timeline = useQuery({
    queryKey: ["threat-timeline"],
    queryFn: getThreatTimeline,
    staleTime: 30_000,
  });
  const error =
    overview.error ??
    indicators.error ??
    campaigns.error ??
    groups.error ??
    techniques.error ??
    infrastructure.error ??
    timeline.error;

  const indicatorItems = useMemo(
    () =>
      scopeToInvestigation(
        filterIndicators(safeArray(indicators.data?.items), query),
        investigationId,
      ),
    [indicators.data?.items, investigationId, query],
  );
  const infrastructureItems = useMemo(
    () =>
      scopeToInvestigation(
        filterInfrastructure(safeArray(infrastructure.data?.items), query),
        investigationId,
      ),
    [infrastructure.data?.items, investigationId, query],
  );
  const timelineItems = useMemo(
    () =>
      safeArray(timeline.data?.items).filter(
        (item) =>
          !investigationId || item.investigation_id === investigationId,
      ),
    [timeline.data?.items, investigationId],
  );

  if (overview.isLoading || indicators.isLoading || infrastructure.isLoading) {
    return <LoadingBlock label="Loading threat intelligence workspace" />;
  }
  if (error) {
    return <ErrorBlock message={error} />;
  }

  return (
    <>
      <PageHeader
        title="Threat Intelligence"
        eyebrow="Defensive Intelligence Workspace"
        actions={
          <button
            type="button"
            onClick={() => {
              void overview.refetch();
              void indicators.refetch();
              void campaigns.refetch();
              void groups.refetch();
              void techniques.refetch();
              void infrastructure.refetch();
              void timeline.refetch();
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
            This workspace organizes stored indicators, analyst-created campaigns,
            analyst-approved threat groups, ATT&CK mappings, and recurring
            infrastructure. It does not perform attribution or external enrichment.
          </p>
        </div>
        <div className="mt-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <nav className="themed-scrollbar flex min-w-0 gap-2 overflow-x-auto pb-1">
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
          <label className="relative min-w-0 lg:w-72">
            <Search
              className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-raven-muted"
              aria-hidden="true"
            />
            <span className="sr-only">Filter threat intelligence</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Filter indicators or infrastructure"
              className="w-full rounded-md border border-raven-border bg-raven-bg py-2 pl-9 pr-3 text-sm outline-none focus:border-raven-violet"
            />
          </label>
        </div>
      </section>

      {view === "overview" ? (
        <OverviewPanel
          indicatorCount={overview.data?.indicator_count}
          activeCampaigns={overview.data?.active_campaigns}
          groupCount={overview.data?.threat_group_count}
          techniqueCount={overview.data?.technique_count}
          recurringInfrastructure={overview.data?.recurring_infrastructure_count}
          highConfidence={overview.data?.high_confidence_observations}
          attackCoverage={overview.data?.attack_coverage}
          recentActivity={safeArray(overview.data?.recent_activity)}
          indicators={indicatorItems}
          infrastructure={infrastructureItems}
        />
      ) : null}
      {view === "indicators" ? <IndicatorsPanel items={indicatorItems} /> : null}
      {view === "campaigns" ? (
        <CampaignsPanel items={safeArray(campaigns.data?.items)} />
      ) : null}
      {view === "groups" ? (
        <GroupsPanel items={safeArray(groups.data?.items)} />
      ) : null}
      {view === "techniques" ? (
        <TechniquesPanel items={safeArray(techniques.data?.items)} />
      ) : null}
      {view === "infrastructure" ? (
        <InfrastructurePanel items={infrastructureItems} />
      ) : null}
      {view === "timeline" ? (
        <TimelinePanel items={timelineItems} isLoading={timeline.isLoading} />
      ) : null}
    </>
  );
}

function OverviewPanel({
  indicatorCount,
  activeCampaigns,
  groupCount,
  techniqueCount,
  recurringInfrastructure,
  highConfidence,
  attackCoverage,
  recentActivity,
  indicators,
  infrastructure,
}: {
  indicatorCount: number | undefined;
  activeCampaigns: number | undefined;
  groupCount: number | undefined;
  techniqueCount: number | undefined;
  recurringInfrastructure: number | undefined;
  highConfidence: number | undefined;
  attackCoverage: number | undefined;
  recentActivity: ThreatTimelineEvent[];
  indicators: ThreatIndicatorSummary[];
  infrastructure: ThreatInfrastructureSummary[];
}): JSX.Element {
  return (
    <div className="space-y-5">
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <StatCard
          label="Indicators"
          value={safeNumber(indicatorCount)}
          detail="Stored IOC repository"
          icon={<FileSearch className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Campaigns"
          value={safeNumber(activeCampaigns)}
          detail="Active or monitored"
          icon={<Flag className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Threat groups"
          value={safeNumber(groupCount)}
          detail="Analyst-approved"
          icon={<UsersRound className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="ATT&CK coverage"
          value={safeNumber(attackCoverage)}
          detail={`${safeNumber(techniqueCount)} techniques visible`}
          icon={<GitBranch className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Recurring infra"
          value={safeNumber(recurringInfrastructure)}
          detail="Seen across stored evidence"
          icon={<Network className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="High confidence"
          value={safeNumber(highConfidence)}
          detail="Corroborated observations"
          icon={<Activity className="h-5 w-5" aria-hidden="true" />}
        />
      </section>
      <section className="grid gap-5 xl:grid-cols-3">
        <IndicatorList title="Top indicators" items={indicators.slice(0, 5)} />
        <InfrastructureList
          title="Recurring infrastructure"
          items={infrastructure.slice(0, 5)}
        />
        <RecentActivity items={recentActivity} />
      </section>
    </div>
  );
}

function IndicatorsPanel({
  items,
}: {
  items: ThreatIndicatorSummary[];
}): JSX.Element {
  if (!items.length) {
    return (
      <EmptyBlock
        title="No indicators available"
        message="Indicators appear after stored IOC observations are linked to accessible investigations."
        nextStep="Run authorized passive recon or review existing IOC intelligence."
      />
    );
  }
  return (
    <section className="themed-scrollbar overflow-x-auto rounded-lg border border-raven-border bg-raven-panel/85">
      <table className="min-w-[980px] w-full divide-y divide-raven-border text-left text-sm">
        <thead className="bg-raven-panelSoft text-xs uppercase tracking-wide text-raven-muted">
          <tr>
            <th className="px-4 py-3">Indicator</th>
            <th className="px-4 py-3">Confidence</th>
            <th className="px-4 py-3">Occurrences</th>
            <th className="px-4 py-3">Investigations</th>
            <th className="px-4 py-3">Evidence</th>
            <th className="px-4 py-3">Observed</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-raven-border">
          {items.map((item) => (
            <tr key={item.id} className="align-top">
              <td className="px-4 py-3">
                <LongValue
                  value={item.value}
                  label={formatLabel(item.type)}
                  secondary={`Source: ${item.source || "stored evidence"}`}
                  maxLength={80}
                />
              </td>
              <td className="px-4 py-3">
                <ConfidenceBadge value={item.confidence} />
                <p className="mt-2 max-w-xs text-xs leading-5 text-raven-muted">
                  {item.confidence_reason}
                </p>
              </td>
              <td className="px-4 py-3">{safeNumber(item.occurrence_count)}</td>
              <td className="px-4 py-3">
                <InvestigationLinks items={item.investigations} />
              </td>
              <td className="px-4 py-3 text-raven-muted">
                {safeNumber(item.findings_count)} findings
                <br />
                {safeNumber(item.reports_count)} reports
              </td>
              <td className="px-4 py-3 text-raven-muted">
                <span>{formatDate(item.first_seen)}</span>
                <br />
                <span>{formatDate(item.last_seen)}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function CampaignsPanel({
  items,
}: {
  items: ThreatCampaignSummary[];
}): JSX.Element {
  if (!items.length) {
    return (
      <EmptyBlock
        title="No analyst-created campaigns"
        message="Campaigns are created by analysts when evidence supports grouping related indicators, findings, and investigations."
        nextStep="Use campaign tracking only after evidence has been reviewed."
      />
    );
  }
  return (
    <section className="grid gap-4 lg:grid-cols-2">
      {items.map((item) => (
        <article
          key={item.id}
          className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="break-words text-lg font-semibold">{item.name}</h2>
              <p className="mt-1 text-sm capitalize text-raven-muted">
                {item.status}
              </p>
            </div>
            <ConfidenceBadge value={item.confidence} />
          </div>
          <p className="mt-3 text-sm leading-6 text-raven-muted">
            {item.description ?? "No campaign description has been recorded."}
          </p>
          <MetricGrid
            values={[
              ["Indicators", item.indicator_count],
              ["Findings", item.finding_count],
              ["Investigations", item.investigation_count],
              ["Techniques", item.technique_count],
            ]}
          />
          <p className="mt-3 text-xs text-raven-muted">
            Observed {formatDate(item.first_observed)} to{" "}
            {formatDate(item.last_observed)}
          </p>
        </article>
      ))}
    </section>
  );
}

function GroupsPanel({ items }: { items: ThreatGroupSummary[] }): JSX.Element {
  if (!items.length) {
    return (
      <EmptyBlock
        title="No threat groups recorded"
        message="Threat group records are analyst-approved context only. The platform does not infer attribution automatically."
        nextStep="Create group context only when supporting evidence is available."
      />
    );
  }
  return (
    <section className="grid gap-4 lg:grid-cols-2">
      {items.map((item) => (
        <article
          key={item.id}
          className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <h2 className="break-words text-lg font-semibold">{item.name}</h2>
            <ConfidenceBadge value={item.confidence} />
          </div>
          <p className="mt-2 text-sm leading-6 text-raven-muted">
            {item.description ?? "No threat group description has been recorded."}
          </p>
          {safeArray(item.aliases).length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {safeArray(item.aliases).map((alias) => (
                <span
                  key={alias}
                  className="rounded border border-raven-border bg-raven-panelSoft px-2 py-1 text-xs"
                >
                  {alias}
                </span>
              ))}
            </div>
          ) : null}
          <MetricGrid
            values={[
              ["Campaigns", item.campaign_count],
              ["Indicators", item.indicator_count],
              ["Techniques", item.technique_count],
            ]}
          />
          {item.notes ? (
            <p className="mt-3 text-sm leading-6 text-raven-muted">{item.notes}</p>
          ) : null}
        </article>
      ))}
    </section>
  );
}

function TechniquesPanel({
  items,
}: {
  items: ThreatTechniqueSummary[];
}): JSX.Element {
  if (!items.length) {
    return (
      <EmptyBlock
        title="No ATT&CK mappings"
        message="Technique mappings appear when findings, campaigns, or groups include evidence-backed ATT&CK references."
        nextStep="Map only relevant techniques and document why the mapping exists."
      />
    );
  }
  return (
    <section className="grid gap-4 lg:grid-cols-2">
      {items.map((item) => (
        <article
          key={item.id}
          className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-wide text-raven-cyan">
                {item.technique_id}
              </p>
              <h2 className="mt-1 break-words text-lg font-semibold">
                {item.name}
              </h2>
            </div>
            <ConfidenceBadge value={item.confidence} />
          </div>
          <p className="mt-2 text-sm text-raven-muted">
            {item.tactic ? `Tactic: ${item.tactic}` : "No tactic recorded."}
          </p>
          {item.procedure ? (
            <p className="mt-3 text-sm leading-6 text-raven-muted">
              {item.procedure}
            </p>
          ) : null}
          <MetricGrid
            values={[
              ["Findings", item.mapped_findings],
              ["Campaigns", item.mapped_campaigns],
              ["Groups", item.mapped_groups],
              ["Coverage", item.coverage_count],
            ]}
          />
          <p className="mt-3 text-sm leading-6 text-raven-muted">
            <span className="font-medium text-raven-text">Why this mapping exists: </span>
            {item.why_mapping_exists}
          </p>
        </article>
      ))}
    </section>
  );
}

function InfrastructurePanel({
  items,
}: {
  items: ThreatInfrastructureSummary[];
}): JSX.Element {
  if (!items.length) {
    return (
      <EmptyBlock
        title="No recurring infrastructure"
        message="Infrastructure intelligence appears when domains, IPs, technologies, certificates, or hosting references recur in stored evidence."
        nextStep="Run authorized passive recon and review recurring infrastructure."
      />
    );
  }
  return (
    <section className="grid gap-4 lg:grid-cols-2">
      {items.map((item) => (
        <article
          key={item.id}
          className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <LongValue
              value={item.value}
              label={formatLabel(item.infrastructure_type)}
              secondary={`${item.occurrence_count} observations across ${item.investigation_count} investigations`}
              maxLength={90}
            />
            <ConfidenceBadge value={item.confidence} />
          </div>
          <p className="mt-3 text-xs text-raven-muted">
            Observed {formatDate(item.first_seen)} to {formatDate(item.last_seen)}
          </p>
          <InvestigationLinks items={item.investigations} />
        </article>
      ))}
    </section>
  );
}

function TimelinePanel({
  items,
  isLoading,
}: {
  items: ThreatTimelineEvent[];
  isLoading: boolean;
}): JSX.Element {
  if (isLoading) {
    return <LoadingBlock label="Loading threat timeline" />;
  }
  if (!items.length) {
    return (
      <EmptyBlock
        title="No threat intelligence timeline"
        message="Timeline events appear when indicators repeat, campaigns are recorded, techniques are mapped, or remediation updates are stored."
        nextStep="Review stored indicators and evidence-backed mappings."
      />
    );
  }
  return (
    <section className="space-y-3">
      {items.map((item) => (
        <article
          key={item.id}
          className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs uppercase tracking-wide text-raven-cyan">
                {formatLabel(item.event_type)}
              </p>
              <h2 className="mt-1 break-words font-semibold">{item.title}</h2>
            </div>
            <ConfidenceBadge value={item.confidence} />
          </div>
          <p className="mt-2 text-sm leading-6 text-raven-muted">
            {item.summary}
          </p>
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-raven-muted">
            <span>{formatDate(item.timestamp)}</span>
            {item.investigation_id ? (
              <Link
                to={`/investigations/${item.investigation_id}`}
                className="text-raven-cyan hover:text-white"
              >
                {item.investigation_title ?? "Open investigation"}
              </Link>
            ) : null}
          </div>
        </article>
      ))}
    </section>
  );
}

function IndicatorList({
  title,
  items,
}: {
  title: string;
  items: ThreatIndicatorSummary[];
}): JSX.Element {
  const safeItems = safeArray(items);
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <h2 className="text-lg font-semibold">{title}</h2>
      {safeItems.length ? (
        <div className="mt-4 space-y-4">
          {safeItems.map((item) => (
            <div key={item.id} className="min-w-0">
              <LongValue
                value={item.value}
                label={formatLabel(item.type)}
                secondary={`${item.occurrence_count} observations`}
                maxLength={72}
              />
              <div className="mt-2">
                <ConfidenceBadge value={item.confidence} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-raven-muted">
          No indicators are visible yet.
        </p>
      )}
    </section>
  );
}

function InfrastructureList({
  title,
  items,
}: {
  title: string;
  items: ThreatInfrastructureSummary[];
}): JSX.Element {
  const safeItems = safeArray(items);
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <h2 className="text-lg font-semibold">{title}</h2>
      {safeItems.length ? (
        <div className="mt-4 space-y-4">
          {safeItems.map((item) => (
            <div key={item.id} className="min-w-0">
              <LongValue
                value={item.value}
                label={formatLabel(item.infrastructure_type)}
                secondary={`${item.investigation_count} investigations`}
                maxLength={72}
              />
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-raven-muted">
          No recurring infrastructure is visible yet.
        </p>
      )}
    </section>
  );
}

function RecentActivity({ items }: { items: ThreatTimelineEvent[] }): JSX.Element {
  const safeItems = safeArray(items);
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex items-center gap-2">
        <CalendarClock className="h-5 w-5 text-raven-cyan" aria-hidden="true" />
        <h2 className="text-lg font-semibold">Threat timeline</h2>
      </div>
      {safeItems.length ? (
        <div className="mt-4 space-y-3">
          {safeItems.slice(0, 5).map((item) => (
            <div key={item.id} className="min-w-0">
              <p className="break-words text-sm font-medium">{item.title}</p>
              <p className="mt-1 break-words text-xs leading-5 text-raven-muted">
                {item.summary}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-raven-muted">
          No threat intelligence events are stored yet.
        </p>
      )}
    </section>
  );
}

function InvestigationLinks({
  items,
}: {
  items: ThreatIndicatorSummary["investigations"];
}): JSX.Element {
  const references = safeArray(items);
  if (!references.length) {
    return <span className="text-sm text-raven-muted">No linked investigations</span>;
  }
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {references.slice(0, 5).map((item) => (
        <Link
          key={item.investigation_id}
          to={`/investigations/${item.investigation_id}`}
          className="rounded border border-raven-border bg-raven-panelSoft px-2 py-1 text-xs text-raven-cyan hover:border-raven-violet hover:text-white"
          title={item.investigation_title}
        >
          {item.investigation_title}
        </Link>
      ))}
      {references.length > 5 ? (
        <span className="rounded border border-raven-border px-2 py-1 text-xs text-raven-muted">
          +{references.length - 5} more
        </span>
      ) : null}
    </div>
  );
}

function MetricGrid({
  values,
}: {
  values: Array<[string, number]>;
}): JSX.Element {
  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {values.map(([label, value]) => (
        <div
          key={label}
          className="rounded-md border border-raven-border bg-raven-bg/60 p-3"
        >
          <p className="text-xs uppercase tracking-wide text-raven-muted">
            {label}
          </p>
          <p className="mt-1 text-xl font-semibold">{safeNumber(value)}</p>
        </div>
      ))}
    </div>
  );
}

function ConfidenceBadge({
  value,
}: {
  value: ThreatWorkspaceConfidence;
}): JSX.Element {
  const tone =
    value === "Confirmed"
      ? "border-fuchsia-400/40 bg-fuchsia-500/10 text-fuchsia-100"
      : value === "High"
        ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-100"
        : value === "Medium"
          ? "border-amber-400/40 bg-amber-500/10 text-amber-100"
          : "border-slate-400/30 bg-slate-500/10 text-slate-200";
  return <span className={`rounded border px-2 py-1 text-xs ${tone}`}>{value}</span>;
}

function scopeToInvestigation<
  T extends { investigations: ThreatIndicatorSummary["investigations"] },
>(items: T[], investigationId: string | undefined): T[] {
  if (!investigationId) {
    return items;
  }
  return items.filter((item) =>
    safeArray(item.investigations).some(
      (reference) => reference.investigation_id === investigationId,
    ),
  );
}

function filterIndicators(
  items: ThreatIndicatorSummary[],
  query: string,
): ThreatIndicatorSummary[] {
  const needle = query.trim().toLowerCase();
  if (!needle) {
    return items;
  }
  return items.filter((item) =>
    [item.value, item.type, item.source, ...item.tags]
      .join(" ")
      .toLowerCase()
      .includes(needle),
  );
}

function filterInfrastructure(
  items: ThreatInfrastructureSummary[],
  query: string,
): ThreatInfrastructureSummary[] {
  const needle = query.trim().toLowerCase();
  if (!needle) {
    return items;
  }
  return items.filter((item) =>
    [item.value, item.infrastructure_type].join(" ").toLowerCase().includes(needle),
  );
}

function safeArray<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

function safeNumber(value: number | null | undefined): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function formatLabel(value: string | null | undefined): string {
  return String(value ?? "unknown")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
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
