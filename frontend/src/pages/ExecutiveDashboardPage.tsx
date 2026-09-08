import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  FileText,
  Network,
  RefreshCw,
  ShieldAlert,
  TrendingUp,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { StatCard } from "../components/StatCard";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import {
  getExecutivePosture,
  getExecutiveRecommendations,
  getExecutiveReportingDashboard,
  getExecutiveTrends,
} from "../lib/api";
import type {
  ExecutiveDashboardResponse,
  ExecutivePostureResponse,
  ExecutiveRecommendationItem,
  ExecutiveTrendPoint,
} from "../types";

function safeArray<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

function safeNumber(value: number | null | undefined): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

export function ExecutiveDashboardPage(): JSX.Element {
  const dashboard = useQuery({
    queryKey: ["executive-reporting-dashboard"],
    queryFn: getExecutiveReportingDashboard,
    staleTime: 30_000,
  });
  const posture = useQuery({
    queryKey: ["executive-posture"],
    queryFn: getExecutivePosture,
    staleTime: 30_000,
  });
  const trends = useQuery({
    queryKey: ["executive-trends"],
    queryFn: getExecutiveTrends,
    staleTime: 30_000,
  });
  const recommendations = useQuery({
    queryKey: ["executive-recommendations"],
    queryFn: getExecutiveRecommendations,
    staleTime: 30_000,
  });
  const isLoading = dashboard.isLoading || posture.isLoading;
  const error = dashboard.error ?? posture.error;

  if (isLoading) {
    return <LoadingBlock label="Loading executive reporting view" />;
  }
  if (error) {
    return <ErrorBlock message={error} />;
  }

  return (
    <>
      <PageHeader
        title="Executive Dashboard"
        eyebrow="Stakeholder reporting"
        actions={
          <button
            type="button"
            onClick={() => {
              void dashboard.refetch();
              void posture.refetch();
              void trends.refetch();
              void recommendations.refetch();
            }}
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-text hover:border-raven-violet"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </button>
        }
      />

      <PostureHero posture={posture.data} dashboard={dashboard.data} />

      <section className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard
          label="Critical findings"
          value={posture.data?.critical_findings ?? 0}
          detail="Unresolved"
          icon={<ShieldAlert className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="High findings"
          value={posture.data?.high_findings ?? 0}
          detail="Unresolved"
          icon={<AlertTriangle className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Open remediation"
          value={posture.data?.open_remediation ?? 0}
          detail={`${posture.data?.overdue_remediation ?? 0} overdue`}
          icon={<CheckCircle2 className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="High-risk cases"
          value={dashboard.data?.high_risk_investigations ?? 0}
          detail="Requiring attention"
          icon={<TrendingUp className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Reporting ready"
          value={dashboard.data?.reporting_ready_investigations ?? 0}
          detail="Stakeholder-ready"
          icon={<FileText className="h-5 w-5" aria-hidden="true" />}
        />
      </section>

      <section className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Recurring indicators"
          value={dashboard.data?.threat_intelligence?.recurring_indicators ?? 0}
          detail="Stored IOC visibility"
          icon={<Network className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Active campaigns"
          value={dashboard.data?.threat_intelligence?.active_campaigns ?? 0}
          detail="Analyst-created"
          icon={<FlagIcon />}
        />
        <StatCard
          label="ATT&CK coverage"
          value={dashboard.data?.threat_intelligence?.attack_coverage ?? 0}
          detail="Evidence-backed mappings"
          icon={<BarChart3 className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="High confidence observations"
          value={
            dashboard.data?.threat_intelligence?.high_confidence_observations ?? 0
          }
          detail="Corroborated internally"
          icon={<CheckCircle2 className="h-5 w-5" aria-hidden="true" />}
        />
      </section>

      <section className="mt-6 grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
        <TrendPanel
          points={trends.data?.points}
          summary={trends.data?.summary}
          isLoading={trends.isLoading}
          error={trends.error}
        />
        <RecommendationsPanel items={recommendations.data?.items} />
      </section>

      <section className="mt-6 grid gap-5 lg:grid-cols-2">
        <SignalPanel
          title="Recurring infrastructure"
          items={dashboard.data?.recurring_infrastructure}
        />
        <SignalPanel
          title="Repeated high-risk items"
          items={dashboard.data?.repeated_high_risk_items}
        />
        <SignalPanel
          title="Top recurring technologies"
          items={dashboard.data?.repeated_technologies}
        />
        <SignalPanel
          title="Top recurring findings"
          items={dashboard.data?.repeated_findings}
        />
      </section>
    </>
  );
}

function FlagIcon(): JSX.Element {
  return <FileText className="h-5 w-5" aria-hidden="true" />;
}

function PostureHero({
  posture,
  dashboard,
}: {
  posture: ExecutivePostureResponse | undefined;
  dashboard: ExecutiveDashboardResponse | undefined;
}): JSX.Element {
  const score = safeNumber(posture?.score);
  return (
    <section className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-raven-cyan">
            Organization posture
          </p>
          <h2 className="mt-1 text-2xl font-semibold">
            {posture?.category ?? "Low"} stakeholder risk posture
          </h2>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-raven-muted">
            Posture is deterministic and based on stored findings, remediation,
            recurrence, and investigation priority. It does not make unsupported
            compromise claims.
          </p>
        </div>
        <div className="w-full max-w-xs rounded-md border border-raven-violet bg-raven-violet/10 p-4 lg:text-right">
          <p className="text-4xl font-semibold">{score}/100</p>
          <p className="mt-1 text-sm text-violet-100">Current posture score</p>
        </div>
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        {safeArray(posture?.contributing_factors).map((factor) => (
          <div
            key={factor.key}
            className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
          >
            <p className="text-xs uppercase tracking-wide text-raven-muted">
              {factor.label}
            </p>
            <p className="mt-1 text-2xl font-semibold">{factor.value}</p>
            <p className="mt-2 text-xs leading-5 text-raven-muted">
              {factor.detail}
            </p>
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs text-raven-muted">
        Active investigations: {posture?.active_investigations ?? 0}. Missing
        reports: {dashboard?.investigations_missing_reports ?? 0}. Missing
        remediation: {dashboard?.investigations_without_remediation ?? 0}.
      </p>
    </section>
  );
}

function TrendPanel({
  points,
  summary,
  isLoading,
  error,
}: {
  points: ExecutiveTrendPoint[] | undefined;
  summary: string | undefined;
  isLoading: boolean;
  error: Error | null;
}): JSX.Element {
  if (isLoading) {
    return <LoadingBlock label="Loading risk trend" />;
  }
  if (error) {
    return <ErrorBlock message={error} />;
  }
  const items = safeArray(points);
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-raven-cyan">
            Risk trend
          </p>
          <h2 className="mt-1 text-lg font-semibold">Timeline</h2>
        </div>
        <BarChart3 className="h-5 w-5 text-raven-muted" aria-hidden="true" />
      </div>
      <p className="mt-3 text-sm leading-6 text-raven-muted">
        {summary ?? "No trend summary is available."}
      </p>
      {items.length ? (
        <div className="mt-4 space-y-3">
          {items.slice(-8).map((point) => (
            <div key={point.date}>
              <div className="flex items-center justify-between gap-3 text-xs">
                <span className="text-raven-muted">{point.date}</span>
                <span>{safeNumber(point.risk_score)}/100</span>
              </div>
              <div className="mt-1 h-2 rounded-full bg-raven-panelSoft">
                <div
                  className="h-2 rounded-full bg-raven-violet"
                  style={{ width: `${Math.min(100, safeNumber(point.risk_score))}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-raven-muted">
                {safeNumber(point.findings)} findings, {safeNumber(point.remediations_completed)} completed
                remediation tasks
              </p>
            </div>
          ))}
        </div>
      ) : (
        <EmptyBlock
          title="No trend data"
          message="Trend data appears after stored findings, remediation tasks, investigations, or reports exist."
        />
      )}
    </section>
  );
}

function RecommendationsPanel({
  items,
}: {
  items: ExecutiveRecommendationItem[] | undefined;
}): JSX.Element {
  const recommendations = safeArray(items);
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <p className="text-xs uppercase tracking-wide text-raven-cyan">
        Stakeholder recommendations
      </p>
      <h2 className="mt-1 text-lg font-semibold">Recommended actions</h2>
      {recommendations.length ? (
        <div className="mt-4 space-y-3">
          {recommendations.map((item) => {
            const refs = safeArray(item.evidence_refs);
            return (
              <article
                key={`${item.category}:${item.title}`}
                className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
              >
                <span className="rounded border border-raven-border px-2 py-1 text-xs text-raven-cyan">
                  {item.category}
                </span>
                <h3 className="mt-3 font-semibold">{item.title}</h3>
                <p className="mt-2 text-sm leading-6 text-raven-muted">
                  {item.recommendation}
                </p>
                {refs.length ? (
                  <p className="mt-2 break-words text-xs text-raven-muted">
                    Evidence: {refs.slice(0, 4).join(", ")}
                  </p>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : (
        <EmptyBlock
          title="No recommendations"
          message="Recommendations appear when stored findings, remediation, reports, or recurrence signals require stakeholder attention."
        />
      )}
    </section>
  );
}

function SignalPanel({
  title,
  items,
}: {
  title: string;
  items: Array<{ label: string; count: number }> | undefined;
}): JSX.Element {
  const signals = safeArray(items);
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <h2 className="text-lg font-semibold">{title}</h2>
      {signals.length ? (
        <div className="mt-4 space-y-2">
          {signals.map((item) => (
            <div
              key={`${item.label}:${item.count}`}
              className="flex min-w-0 items-center justify-between gap-3 rounded-md border border-raven-border bg-raven-panelSoft p-3"
            >
              <span className="min-w-0 break-words text-sm">{item.label}</span>
              <span className="flex-none text-sm text-raven-cyan">{item.count}</span>
            </div>
          ))}
        </div>
      ) : (
        <EmptyBlock
          title="No recurring signal"
          message="Recurring internal signals appear after multiple investigations share technologies or finding themes."
        />
      )}
    </section>
  );
}
