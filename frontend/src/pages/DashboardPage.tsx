import {
  Activity,
  BarChart3,
  FileText,
  FolderKanban,
  RefreshCw,
  ShieldAlert,
  Target,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { StatCard } from "../components/StatCard";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { getDashboardAnalytics, getDashboardMetrics } from "../lib/api";
import type {
  CountItem,
  DashboardAnalyticsResponse,
  DashboardMetricsResponse,
  InvestigationStatus,
  Severity,
} from "../types";

const severityOrder: Severity[] = ["critical", "high", "medium", "low", "info"];
const statusOrder: InvestigationStatus[] = [
  "active",
  "triage",
  "monitoring",
  "remediation",
  "draft",
  "validated",
  "archived",
];

export function DashboardPage(): JSX.Element {
  const dashboard = useQuery({
    queryKey: ["dashboard-analytics"],
    queryFn: getDashboardAnalytics,
  });
  const metrics = useQuery({
    queryKey: ["dashboard-metrics"],
    queryFn: getDashboardMetrics,
  });

  if (dashboard.isLoading) {
    return <LoadingBlock label="Loading dashboard analytics" />;
  }
  if (dashboard.isError) {
    return <ErrorBlock message={dashboard.error.message} />;
  }

  const data = dashboard.data;
  if (!data) {
    return <EmptyBlock message="No analytics data is available yet." />;
  }

  const highCritical =
    data.findings_summary.by_severity.critical +
    data.findings_summary.by_severity.high;

  return (
    <>
      <PageHeader
        title="Dashboard"
        eyebrow="Operations analytics"
        actions={
          <button
            type="button"
            onClick={() => void dashboard.refetch()}
            disabled={dashboard.isFetching}
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-text hover:border-raven-violet disabled:opacity-60"
          >
            <RefreshCw
              className={[
                "h-4 w-4",
                dashboard.isFetching ? "animate-spin" : "",
              ].join(" ")}
              aria-hidden="true"
            />
            Refresh
          </button>
        }
      />

      <p className="-mt-3 mb-5 text-sm text-raven-muted">
        Last updated {formatDateTime(data.generated_at)}
      </p>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        <StatCard
          label="Active investigations"
          value={data.investigation_summary.active}
          detail={`${data.investigation_summary.total} total accessible`}
          icon={<FolderKanban className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Total targets"
          value={data.target_summary.total}
          detail={formatCountSummary(data.target_summary.by_type)}
          icon={<Target className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Total findings"
          value={data.findings_summary.total}
          detail={`${data.findings_summary.average_confidence}% avg confidence`}
          icon={<ShieldAlert className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="High/Critical"
          value={highCritical}
          detail="Open items need priority review"
          icon={<Activity className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Reports generated"
          value={data.report_summary.total}
          detail={`${data.report_summary.ready} ready`}
          icon={<FileText className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Latest activity"
          value={data.recent_activity.length}
          detail={
            data.recent_activity[0]
              ? formatDateTime(data.recent_activity[0].timestamp)
              : "No activity yet"
          }
          icon={<BarChart3 className="h-5 w-5" aria-hidden="true" />}
        />
      </div>

      {data.investigation_summary.total === 0 ? (
        <section className="mt-8">
          <EmptyBlock message="No investigations are available for this account yet." />
        </section>
      ) : (
        <DashboardAnalyticsContent data={data} metrics={metrics.data} />
      )}
    </>
  );
}

function DashboardAnalyticsContent({
  data,
  metrics,
}: {
  data: DashboardAnalyticsResponse;
  metrics: DashboardMetricsResponse | undefined;
}): JSX.Element {
  return (
    <>
      {metrics ? (
        <section className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-6">
          <StatCard
            label="Health score"
            value={`${metrics.investigation_metrics.health_score}/100`}
            detail="Deterministic case posture"
            icon={<Activity className="h-5 w-5" aria-hidden="true" />}
          />
          <StatCard
            label="Pending reviews"
            value={metrics.analyst_metrics.pending_reviews}
            detail={`${metrics.analyst_metrics.assigned_findings} assigned findings`}
            icon={<ShieldAlert className="h-5 w-5" aria-hidden="true" />}
          />
          <StatCard
            label="Overdue tasks"
            value={metrics.investigation_metrics.overdue_tasks}
            detail={`${metrics.investigation_metrics.open_tasks} open tasks`}
            icon={<Target className="h-5 w-5" aria-hidden="true" />}
          />
          <StatCard
            label="Unresolved findings"
            value={metrics.risk_metrics.unresolved_findings}
            detail={`${metrics.risk_metrics.confidence_average}% avg confidence`}
            icon={<BarChart3 className="h-5 w-5" aria-hidden="true" />}
          />
          <StatCard
            label="Urgent investigations"
            value={metrics.investigation_metrics.urgent_investigations}
            detail="Accessible cases marked urgent"
            icon={<ShieldAlert className="h-5 w-5" aria-hidden="true" />}
          />
          <StatCard
            label="Overdue investigations"
            value={metrics.investigation_metrics.overdue_investigations}
            detail="Open cases past due date"
            icon={<Activity className="h-5 w-5" aria-hidden="true" />}
          />
        </section>
      ) : null}

      <section className="mt-8 grid gap-4 xl:grid-cols-5">
        <DistributionPanel
          title="Severity distribution"
          items={severityOrder.map((severity) => ({
            label: severity,
            count: data.findings_summary.by_severity[severity],
          }))}
          emptyMessage="No findings have been generated."
          tone="severity"
        />
        <DistributionPanel
          title="Targets by type"
          items={recordItems(data.target_summary.by_type)}
          emptyMessage="No targets are stored yet."
        />
        <DistributionPanel
          title="Entity distribution"
          items={recordItems(data.recon_summary.entity_counts)}
          emptyMessage="No recon entities are stored yet."
        />
        <DistributionPanel
          title="Reports by type"
          items={recordItems(data.report_summary.by_type)}
          emptyMessage="No reports have been generated."
        />
        <DistributionPanel
          title="Investigation status"
          items={statusOrder.map((status) => ({
            label: status,
            count: data.investigation_summary.by_status[status],
          }))}
          emptyMessage="No investigation statuses are available."
        />
      </section>

      <section className="mt-8 grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
        <LatestInvestigations data={data} />
        <RecentActivity data={data} />
      </section>

      <section className="mt-6 grid gap-5 xl:grid-cols-2">
        <OpenHighRiskItems data={data} />
        <LatestReports data={data} />
      </section>
    </>
  );
}

function DistributionPanel({
  title,
  items,
  emptyMessage,
  tone,
}: {
  title: string;
  items: CountItem[];
  emptyMessage: string;
  tone?: "severity";
}): JSX.Element {
  const visibleItems = items.filter((item) => item.count > 0);
  const max = Math.max(...visibleItems.map((item) => item.count), 1);
  return (
    <article className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <h2 className="text-sm font-semibold">{title}</h2>
      {visibleItems.length ? (
        <div className="mt-4 space-y-3">
          {visibleItems.map((item) => (
            <div key={item.label}>
              <div className="mb-1 flex items-center justify-between gap-3 text-xs">
                <span className="capitalize text-raven-muted">
                  {labelize(item.label)}
                </span>
                <span className="font-medium text-raven-text">{item.count}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-raven-panelSoft">
                <div
                  className={[
                    "h-full rounded-full",
                    tone === "severity"
                      ? severityBarClass(item.label as Severity)
                      : "bg-raven-cyan",
                  ].join(" ")}
                  style={{ width: `${Math.max((item.count / max) * 100, 8)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-raven-muted">{emptyMessage}</p>
      )}
    </article>
  );
}

function LatestInvestigations({
  data,
}: {
  data: DashboardAnalyticsResponse;
}): JSX.Element {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Latest investigations</h2>
        <Link
          to="/investigations"
          className="rounded-md border border-raven-border px-3 py-1.5 text-sm text-raven-muted hover:border-raven-violet hover:text-raven-text"
        >
          View all
        </Link>
      </div>
      {data.latest_investigations.length ? (
        <div className="overflow-hidden rounded-lg border border-raven-border">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="bg-raven-panelSoft text-xs uppercase text-raven-muted">
              <tr>
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-raven-border bg-raven-panel/70">
              {data.latest_investigations.map((item) => (
                <tr key={item.id}>
                  <td className="px-4 py-3">
                    <Link
                      to={`/investigations/${item.id}`}
                      className="font-medium text-raven-text hover:text-raven-cyan"
                    >
                      {item.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3 capitalize text-raven-muted">
                    {item.status}
                  </td>
                  <td className="px-4 py-3 text-raven-muted">
                    {formatDateTime(item.updated_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyBlock message="No investigations are available for this account." />
      )}
    </section>
  );
}

function RecentActivity({
  data,
}: {
  data: DashboardAnalyticsResponse;
}): JSX.Element {
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <h2 className="text-lg font-semibold">Recent activity</h2>
      {data.recent_activity.length ? (
        <div className="mt-4 space-y-3">
          {data.recent_activity.slice(0, 6).map((item) => (
            <article
              key={item.id}
              className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-raven-cyan">
                    {item.source}
                  </p>
                  <h3 className="mt-1 text-sm font-medium">{item.title}</h3>
                </div>
                <span className="text-xs text-raven-muted">
                  {formatDateTime(item.timestamp)}
                </span>
              </div>
              <p className="mt-2 line-clamp-2 text-sm text-raven-muted">
                {item.summary}
              </p>
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-raven-muted">
          No investigation activity has been recorded yet.
        </p>
      )}
    </section>
  );
}

function OpenHighRiskItems({
  data,
}: {
  data: DashboardAnalyticsResponse;
}): JSX.Element {
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <h2 className="text-lg font-semibold">Open high risk items</h2>
      {data.open_high_risk_items.length ? (
        <div className="mt-4 space-y-3">
          {data.open_high_risk_items.map((item) => (
            <Link
              key={item.finding_id}
              to={`/investigations/${item.investigation_id}/findings`}
              className="block rounded-md border border-raven-border bg-raven-panelSoft p-3 hover:border-raven-violet"
            >
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-medium">{item.title}</h3>
                <span
                  className={[
                    "rounded border px-2 py-1 text-xs capitalize",
                    severityBadgeClass(item.severity),
                  ].join(" ")}
                >
                  {item.severity}
                </span>
              </div>
              <p className="mt-2 text-sm text-raven-muted">
                {item.investigation_title} - risk {item.risk_score}/100
              </p>
            </Link>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-raven-muted">
          No open high or critical findings are visible to this account.
        </p>
      )}
    </section>
  );
}

function LatestReports({
  data,
}: {
  data: DashboardAnalyticsResponse;
}): JSX.Element {
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <h2 className="text-lg font-semibold">Latest reports</h2>
      {data.latest_reports.length ? (
        <div className="mt-4 space-y-3">
          {data.latest_reports.map((report) => (
            <Link
              key={report.id}
              to={`/investigations/${report.investigation_id}/reports`}
              className="block rounded-md border border-raven-border bg-raven-panelSoft p-3 hover:border-raven-violet"
            >
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-medium">
                  {report.title ?? "Investigation report"}
                </h3>
                <span className="rounded border border-raven-border px-2 py-1 text-xs capitalize text-raven-cyan">
                  {report.status}
                </span>
              </div>
              <p className="mt-2 text-sm capitalize text-raven-muted">
                {report.report_type} - {formatDateTime(report.created_at)}
              </p>
            </Link>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-raven-muted">
          No generated reports are available yet.
        </p>
      )}
    </section>
  );
}

function recordItems(record: Record<string, number>): CountItem[] {
  return Object.entries(record)
    .map(([label, count]) => ({ label, count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
}

function formatCountSummary(record: Record<string, number>): string {
  const items = recordItems(record).slice(0, 2);
  if (!items.length) {
    return "No targets yet";
  }
  return items.map((item) => `${item.count} ${labelize(item.label)}`).join(", ");
}

function labelize(value: string): string {
  return value.replace(/_/g, " ");
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString();
}

function severityBarClass(severity: Severity): string {
  switch (severity) {
    case "critical":
      return "bg-rose-500";
    case "high":
      return "bg-orange-400";
    case "medium":
      return "bg-amber-300";
    case "low":
      return "bg-cyan-400";
    case "info":
      return "bg-slate-400";
    default:
      return "bg-raven-cyan";
  }
}

function severityBadgeClass(severity: Severity): string {
  switch (severity) {
    case "critical":
      return "border-rose-400/40 bg-rose-500/10 text-rose-100";
    case "high":
      return "border-orange-400/40 bg-orange-500/10 text-orange-100";
    case "medium":
      return "border-amber-400/40 bg-amber-500/10 text-amber-100";
    case "low":
      return "border-cyan-400/40 bg-cyan-500/10 text-cyan-100";
    case "info":
      return "border-raven-border bg-raven-panel text-raven-muted";
    default:
      return "border-raven-border bg-raven-panel text-raven-muted";
  }
}
