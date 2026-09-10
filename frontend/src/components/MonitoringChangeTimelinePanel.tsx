import { Check, RefreshCw } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  acknowledgeMonitoringChange,
  getMonitoringChangesOverview,
  listMonitoringChanges,
} from "../lib/api";
import { safeArray, safeDate, safeNumber, safeString } from "../lib/safe";
import type { MonitoringChangeSeverity } from "../types";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "./StateBlock";

export function MonitoringChangeTimelinePanel(): JSX.Element {
  const queryClient = useQueryClient();
  const [eventType, setEventType] = useState("");
  const [severity, setSeverity] = useState<MonitoringChangeSeverity | "">("");
  const [acknowledgement, setAcknowledgement] = useState<"" | "acknowledged" | "unacknowledged">("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const filters = {
    event_type: eventType || undefined,
    severity: severity || undefined,
    acknowledgement: acknowledgement || undefined,
    date_from: dateFrom ? new Date(`${dateFrom}T00:00:00`).toISOString() : undefined,
    date_to: dateTo ? new Date(`${dateTo}T23:59:59`).toISOString() : undefined,
  };
  const changes = useQuery({
    queryKey: ["monitoring-changes", filters],
    queryFn: () => listMonitoringChanges(filters),
    refetchInterval: 30_000,
    retry: 1,
  });
  const overview = useQuery({
    queryKey: ["monitoring-changes-overview"],
    queryFn: getMonitoringChangesOverview,
    refetchInterval: 30_000,
    retry: 1,
  });
  const acknowledge = useMutation({
    mutationFn: acknowledgeMonitoringChange,
    onSuccess: async () => {
      setActionError(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["monitoring-changes"] }),
        queryClient.invalidateQueries({ queryKey: ["monitoring-changes-overview"] }),
      ]);
    },
    onError: () => setActionError("The monitoring change could not be acknowledged. Check your role and retry."),
  });

  if (changes.isLoading || overview.isLoading) return <LoadingBlock label="Loading monitoring change timeline" />;
  if (changes.error) return <ErrorBlock message={changes.error} onRetry={() => void changes.refetch()} />;
  const items = safeArray(changes.data?.items);

  return (
    <div className="space-y-4">
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Recorded changes" value={safeNumber(overview.data?.total)} />
        <Metric label="Unacknowledged" value={safeNumber(overview.data?.unacknowledged)} />
        <Metric label="Port changes" value={safeNumber(overview.data?.port_changes)} />
        <Metric label="Agent / baseline" value={safeNumber(overview.data?.agent_changes) + safeNumber(overview.data?.baseline_changes)} />
      </section>
      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <div className="flex flex-wrap items-end gap-2">
          <label className="min-w-0 text-xs text-raven-muted">Event type<input value={eventType} onChange={(event) => setEventType(event.target.value)} maxLength={80} placeholder="port_opened" className="mt-1 block w-full rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm text-raven-text" /></label>
          <label className="text-xs text-raven-muted">Severity<select value={severity} onChange={(event) => setSeverity(event.target.value as MonitoringChangeSeverity | "")} className="mt-1 block rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm text-raven-text"><option value="">All</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option><option value="info">Info</option></select></label>
          <label className="text-xs text-raven-muted">Acknowledgement<select value={acknowledgement} onChange={(event) => setAcknowledgement(event.target.value as typeof acknowledgement)} className="mt-1 block rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm text-raven-text"><option value="">All</option><option value="unacknowledged">Unacknowledged</option><option value="acknowledged">Acknowledged</option></select></label>
          <label className="text-xs text-raven-muted">From<input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} className="mt-1 block rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm text-raven-text" /></label>
          <label className="text-xs text-raven-muted">To<input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} className="mt-1 block rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm text-raven-text" /></label>
          <button type="button" onClick={() => void Promise.all([changes.refetch(), overview.refetch()])} disabled={changes.isFetching} className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm disabled:opacity-50"><RefreshCw className={`h-4 w-4 ${changes.isFetching ? "animate-spin" : ""}`} />Refresh</button>
        </div>
        <p className="mt-3 text-xs text-raven-muted">Historical entries are monitoring changes and risk indicators only. Collection remains authorized, local, and non-exploitative.</p>
      </section>
      {actionError ? <div role="alert" className="rounded-md border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">{actionError}</div> : null}
      {!items.length ? <EmptyBlock title="No matching monitoring changes" message="No authorized asset, service, agent, telemetry, or baseline transitions match these filters." /> : (
        <ol className="space-y-3">
          {items.map((item) => (
            <li key={item.id} className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h3 className="break-words font-medium">{safeString(item.title, "Monitoring change")}</h3><span className="rounded-full border border-raven-border px-2 py-0.5 text-xs capitalize">{safeString(item.severity, "info")}</span><span className="rounded-full border border-raven-border px-2 py-0.5 text-xs">{safeString(item.event_type, "change")}</span></div><p className="mt-2 break-words text-sm text-raven-muted">{safeString(item.description, "Review this monitoring change.")}</p>{item.old_value || item.new_value ? <p className="mt-2 break-words text-xs text-raven-muted">{safeString(item.old_value, "not previously observed")} → {safeString(item.new_value, "not currently observed")}</p> : null}<p className="mt-2 text-xs text-raven-muted">{safeDate(item.detected_at)?.toLocaleString() ?? "Time unavailable"} · source {safeString(item.source, "local monitoring")}</p></div>
                {item.acknowledged_at ? <span className="inline-flex items-center gap-1 text-xs text-emerald-200"><Check className="h-3.5 w-3.5" />Acknowledged</span> : <button type="button" onClick={() => acknowledge.mutate(item.id)} disabled={acknowledge.isPending} title={acknowledge.isPending ? "Another acknowledgement is in progress." : "Acknowledge this monitoring change."} className="rounded-md border border-raven-border px-3 py-2 text-xs disabled:cursor-not-allowed disabled:opacity-50">Acknowledge</button>}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }): JSX.Element {
  return <div className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4"><p className="text-xs uppercase tracking-wide text-raven-muted">{label}</p><p className="mt-2 text-xl font-semibold">{value}</p></div>;
}
