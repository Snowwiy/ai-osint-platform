import { AlertTriangle, RefreshCw, ServerCog } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { LanMonitoringPanel } from "../components/LanMonitoringPanel";
import { VulnerabilityBaselinePanel } from "../components/VulnerabilityBaselinePanel";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { getMonitoringOverview } from "../lib/api";
import {
  safeArray,
  safeDate,
  safeInternalRoute,
  safeNumber,
  safeString,
} from "../lib/safe";
import type { MonitoringStatus } from "../types";

const fallbackIntervals = [15, 30, 60, 120, 300];
type MonitoringTab = "server" | "services" | "lan" | "agents" | "baseline" | "alerts";

export function MonitoringCenterPage(): JSX.Element {
  const [pollSeconds, setPollSeconds] = useState(30);
  const [tab, setTab] = useState<MonitoringTab>("server");
  const overview = useQuery({
    queryKey: ["monitoring-overview"],
    queryFn: getMonitoringOverview,
    refetchInterval: pollSeconds * 1000,
    retry: 1,
  });
  const data = overview.data;
  const intervals = safeArray(data?.polling_interval_options).filter(
    (value) => Number.isFinite(value) && value >= 10,
  );
  const serviceItems = safeArray(data?.services?.items);
  const assetItems = safeArray(data?.assets?.items);
  const alerts = safeArray(data?.alerts?.items);
  const errors = safeArray(data?.recent_errors);
  const system = data?.system;
  const overviewVisible = tab === "server" || tab === "services" || tab === "alerts";

  return (
    <>
      <PageHeader
        title="Monitoring Center"
        eyebrow="Local service telemetry and defensive asset watch"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-sm text-raven-muted" htmlFor="monitoring-poll">
              Refresh
            </label>
            <select
              id="monitoring-poll"
              value={pollSeconds}
              onChange={(event) => setPollSeconds(Number(event.target.value) || 30)}
              className="rounded-md border border-raven-border bg-raven-panel px-3 py-2 text-sm"
            >
              {(intervals.length ? intervals : fallbackIntervals).map((seconds) => (
                <option key={seconds} value={seconds}>{seconds}s</option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => void overview.refetch()}
              disabled={overview.isFetching}
              className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm hover:border-raven-cyan disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${overview.isFetching ? "animate-spin" : ""}`} aria-hidden="true" />
              Refresh now
            </button>
          </div>
        }
      />

      <nav className="tab-scrollbar mb-5 flex gap-2 overflow-x-auto pb-1" aria-label="Monitoring sections">
        {(["server", "services", "lan", "agents", "baseline", "alerts"] as MonitoringTab[]).map((item) => (
          <button key={item} type="button" onClick={() => setTab(item)} className={`whitespace-nowrap rounded-md border px-3 py-2 text-sm capitalize ${tab === item ? "border-raven-cyan bg-raven-panelSoft text-raven-text" : "border-raven-border text-raven-muted"}`}>
            {item === "lan" ? "LAN Assets" : item === "agents" ? "Endpoint Agents" : item === "baseline" ? "Vulnerability Baseline" : item}
          </button>
        ))}
      </nav>

      {overviewVisible && overview.isLoading ? <LoadingBlock label="Loading local telemetry" /> : null}
      {overviewVisible && overview.error ? (
        <ErrorBlock message={overview.error} onRetry={() => void overview.refetch()} />
      ) : null}
      {overviewVisible && !overview.isLoading && !overview.error && data ? (
        <div className="space-y-5">
          <section className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
            <div className="flex min-w-0 items-center gap-3">
              <ServerCog className="h-6 w-6 text-raven-cyan" aria-hidden="true" />
              <div className="min-w-0">
                <p className="font-semibold">Local platform {statusLabel(data.status)}</p>
                <p className="text-sm text-raven-muted">Release {safeString(data.release_version, "unknown")} · read-only polling every {pollSeconds}s</p>
              </div>
            </div>
            <StatusPill status={data.status} />
          </section>

          {tab === "services" ? <section>
            <h2 className="mb-3 text-lg font-semibold">Services</h2>
            {serviceItems.length ? (
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {serviceItems.map((service) => (
                  <div key={safeString(service.key, service.label)} className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-medium">{safeString(service.label, "Service")}</p>
                      <StatusPill status={service.status} />
                    </div>
                    <p className="mt-2 break-words text-sm leading-5 text-raven-muted">{safeString(service.detail, "No status detail available.")}</p>
                  </div>
                ))}
              </div>
            ) : <EmptyBlock message="No service telemetry is available." />}
          </section> : null}

          {tab === "server" ? <section>
            <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
              <h2 className="text-lg font-semibold">System metrics</h2>
              <p className="text-xs text-raven-muted">{safeString(system?.metric_scope, "local scope")} · {safeString(system?.source, "unavailable").replace(/_/g, " ")}</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <Metric label="CPU" value={percentage(system?.cpu_percent)} />
              <Metric label="Memory" value={percentage(system?.memory_percent)} />
              <Metric label="Disk" value={percentage(system?.disk_percent)} />
              <Metric label="Processes" value={metricValue(system?.process_count)} />
              <Metric label="Uptime" value={duration(system?.uptime_seconds)} />
            </div>
            <p className="mt-2 text-xs text-raven-muted">{safeString(system?.detail, "System metrics are unavailable.")} Last sample: {safeDate(system?.collected_at)?.toLocaleString() ?? "not available"}</p>
          </section> : null}

          {tab === "server" ? <section>
            <h2 className="mb-3 text-lg font-semibold">Asset watch</h2>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
              <Metric label="Investigations" value={metricValue(data.assets?.investigations)} />
              <Metric label="Targets" value={metricValue(data.assets?.targets)} />
              <Metric label="Needs review" value={metricValue(data.assets?.assets_needing_review)} />
              <Metric label="Stale targets" value={metricValue(data.assets?.stale_assets)} />
              <Metric label="High risk" value={metricValue(data.assets?.high_risk_assets)} />
              <Metric label="Authorization risks" value={metricValue(data.assets?.authorization_risks)} />
            </div>
            <p className="mt-3 text-xs text-raven-muted">Findings by severity: critical {safeNumber(data.assets?.findings_by_severity?.critical)} · high {safeNumber(data.assets?.findings_by_severity?.high)} · medium {safeNumber(data.assets?.findings_by_severity?.medium)} · low {safeNumber(data.assets?.findings_by_severity?.low)} · info {safeNumber(data.assets?.findings_by_severity?.info)}</p>
            {assetItems.length ? (
              <div className="mt-3 overflow-x-auto rounded-lg border border-raven-border">
                <table className="w-full min-w-[880px] text-left text-sm">
                  <thead className="bg-raven-panelSoft text-xs uppercase tracking-wide text-raven-muted">
                    <tr><th className="p-3">Investigation</th><th className="p-3">State</th><th className="p-3">Scope / authorization</th><th className="p-3">Targets</th><th className="p-3">Findings</th><th className="p-3">Evidence</th><th className="p-3">Report / closure</th></tr>
                  </thead>
                  <tbody>
                    {assetItems.map((asset) => (
                      <tr key={safeString(asset.investigation_id)} className="border-t border-raven-border align-top">
                        <td className="p-3"><Link className="font-medium text-raven-cyan hover:underline" to={safeInternalRoute(asset.action_url, "/investigations")}>{safeString(asset.title, "Untitled investigation")}</Link></td>
                        <td className="p-3"><StatusPill status={asset.status} /><p className="mt-1 text-xs text-raven-muted">{label(asset.investigation_status)}</p></td>
                        <td className="p-3 text-raven-muted">{label(asset.scope_status)}<br />{label(asset.authorization_status)}</td>
                        <td className="p-3">{safeNumber(asset.targets)} <span className="text-xs text-raven-muted">({safeNumber(asset.stale_targets)} stale)</span></td>
                        <td className="p-3">{safeNumber(asset.unresolved_critical)} critical<br />{safeNumber(asset.unresolved_high)} high</td>
                        <td className="p-3">{safeNumber(asset.evidence_records)}</td>
                        <td className="p-3 text-raven-muted">{label(asset.report_status)}<br />{label(asset.closure_status)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <div className="mt-3"><EmptyBlock message="No accessible investigations are available to watch." /></div>}
          </section> : null}

          {tab === "alerts" ? <section className="grid gap-5 xl:grid-cols-2">
            <div>
              <h2 className="mb-3 text-lg font-semibold">Alerts ({safeNumber(data.alerts?.total)})</h2>
              {alerts.length ? <div className="space-y-2">{alerts.map((alert) => (
                <Link key={safeString(alert.key, alert.title)} to={safeInternalRoute(alert.action_url, "/monitoring")} className="block rounded-lg border border-raven-border bg-raven-panel/85 p-4 hover:border-raven-violet">
                  <div className="flex items-start gap-2"><AlertTriangle className="mt-0.5 h-4 w-4 text-amber-200" aria-hidden="true" /><div className="min-w-0"><p className="font-medium">{safeString(alert.title, "Monitoring alert")}</p><p className="mt-1 break-words text-sm text-raven-muted">{safeString(alert.message, "Review local telemetry.")}</p></div></div>
                </Link>
              ))}</div> : <EmptyBlock title="No active alerts" message="Local services and accessible assets have no derived warning conditions." />}
            </div>
            <div>
              <h2 className="mb-3 text-lg font-semibold">Recent backend errors</h2>
              {errors.length ? <div className="space-y-2">{errors.map((error, index) => (
                <div key={`${safeString(error.action, "error")}-${index}`} className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
                  <p className="font-medium">{safeString(error.action, "Recorded backend error")}</p>
                  <p className="mt-1 text-xs text-raven-muted">{safeString(error.category, "system")} · {safeDate(error.occurred_at)?.toLocaleString() ?? "time unavailable"}</p>
                </div>
              ))}</div> : <EmptyBlock title="No recent errors" message="No accessible sanitized backend error events were found." />}
            </div>
          </section> : null}
        </div>
      ) : null}
      {tab === "lan" ? <LanMonitoringPanel /> : null}
      {tab === "agents" ? <LanMonitoringPanel agentsOnly /> : null}
      {tab === "baseline" ? <VulnerabilityBaselinePanel /> : null}
    </>
  );
}

function Metric({ label: metricLabel, value }: { label: string; value: string }): JSX.Element {
  return <div className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4"><p className="text-xs uppercase tracking-wide text-raven-muted">{metricLabel}</p><p className="mt-2 truncate text-xl font-semibold">{value}</p></div>;
}

function StatusPill({ status }: { status: MonitoringStatus | string | null | undefined }): JSX.Element {
  const normalized: MonitoringStatus = status === "healthy" || status === "unavailable" ? status : "degraded";
  const tone = normalized === "healthy" ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-200" : normalized === "unavailable" ? "border-rose-400/30 bg-rose-500/10 text-rose-100" : "border-amber-400/30 bg-amber-500/10 text-amber-100";
  return <span className={`whitespace-nowrap rounded-full border px-2 py-1 text-xs capitalize ${tone}`}>{normalized}</span>;
}

function percentage(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value) ? `${Math.round(value)}%` : "Unavailable";
}

function metricValue(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString() : "Unavailable";
}

function duration(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "Unavailable";
  const hours = Math.max(0, Math.floor(value / 3600));
  return hours >= 24 ? `${Math.floor(hours / 24)}d ${hours % 24}h` : `${hours}h`;
}

function label(value: unknown): string {
  return safeString(value, "unknown").replace(/_/g, " ");
}

function statusLabel(value: unknown): string {
  return label(value);
}
