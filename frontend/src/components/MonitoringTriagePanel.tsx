import { AlertTriangle, CheckCircle2, ExternalLink, UserRoundCheck, Volume2, VolumeX } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import {
  assignMonitoringTriage,
  falsePositiveMonitoringTriage,
  listMonitoringTriage,
  muteMonitoringTriage,
  resolveMonitoringTriage,
  updateMonitoringTriage,
} from "../lib/api";
import { safeArray, safeDate, safeInternalRoute, safeString } from "../lib/safe";
import { useAuth } from "../lib/useAuth";
import type { MonitoringTriageItem, MonitoringTriageStatus } from "../types";
import { EmptyBlock, LoadingBlock } from "./StateBlock";

type FilterStatus = MonitoringTriageStatus | "";
type FilterSeverity = "info" | "success" | "warning" | "critical" | "";

export function MonitoringTriagePanel(): JSX.Element {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<FilterStatus>("");
  const [severity, setSeverity] = useState<FilterSeverity>("");
  const [source, setSource] = useState("");
  const [assetId, setAssetId] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const triage = useQuery({
    queryKey: ["monitoring-triage", status, severity, source, assetId],
    queryFn: () => listMonitoringTriage({ status: status || undefined, severity: severity || undefined, source: source.trim() || undefined, asset_id: validUuid(assetId) ? assetId : undefined }),
    retry: 1,
    refetchInterval: 30_000,
  });
  const action = useMutation({
    mutationFn: async ({ item, kind }: { item: MonitoringTriageItem; kind: string }) => {
      if (kind === "assign") return assignMonitoringTriage(item.alert_id, user?.id ?? null);
      if (kind === "investigate") return updateMonitoringTriage(item.alert_id, { status: "investigating" });
      if (kind === "unmute") return updateMonitoringTriage(item.alert_id, { status: "triaged" });
      const promptLabel = kind === "mute" ? "Reason for muting this alert" : kind === "false_positive" ? "Why is this a false positive?" : "Resolution summary";
      const value = window.prompt(promptLabel);
      if (!value?.trim()) throw new Error("A brief reason is required.");
      if (kind === "mute") return muteMonitoringTriage(item.alert_id, value.trim());
      if (kind === "false_positive") return falsePositiveMonitoringTriage(item.alert_id, value.trim());
      return resolveMonitoringTriage(item.alert_id, value.trim());
    },
    onSuccess: async () => {
      setMessage(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["monitoring-triage"] }),
        queryClient.invalidateQueries({ queryKey: ["notifications"] }),
        queryClient.invalidateQueries({ queryKey: ["monitoring-overview"] }),
      ]);
    },
    onError: (error) => setMessage(error instanceof Error && error.message === "A brief reason is required." ? error.message : "The triage action could not be completed. Check your access and try again."),
  });
  const items = safeArray(triage.data?.items);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h2 className="text-lg font-semibold">Alert triage queue</h2><p className="mt-1 text-sm text-raven-muted">Monitoring notifications stay preserved while analysts track ownership and resolution.</p></div>
        <p className="text-xs text-raven-muted">{triage.data?.total ?? 0} matching alerts</p>
      </div>
      <div className="grid gap-3 rounded-lg border border-raven-border bg-raven-panel/70 p-3 sm:grid-cols-2 xl:grid-cols-4">
        <Filter label="Status" value={status} onChange={(value) => setStatus(value as FilterStatus)} options={["", "new", "triaged", "investigating", "muted", "resolved", "false_positive"]} />
        <Filter label="Severity" value={severity} onChange={(value) => setSeverity(value as FilterSeverity)} options={["", "critical", "warning", "info", "success"]} />
        <label className="min-w-0 text-xs text-raven-muted">Source<input value={source} onChange={(event) => setSource(event.target.value)} placeholder="All sources" className="mt-1 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text" /></label>
        <label className="min-w-0 text-xs text-raven-muted">Asset ID<input value={assetId} onChange={(event) => setAssetId(event.target.value.trim())} placeholder="All assets" aria-invalid={Boolean(assetId) && !validUuid(assetId)} className="mt-1 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text aria-[invalid=true]:border-amber-300/60" /></label>
      </div>
      {message ? <div className="rounded-lg border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100" role="alert">{message}</div> : null}
      {triage.isLoading ? <LoadingBlock label="Loading alert triage queue" /> : null}
      {triage.isError ? <div className="rounded-lg border border-amber-300/30 bg-amber-500/10 p-4 text-sm text-amber-100" role="alert">The triage queue is temporarily unavailable.<button type="button" onClick={() => void triage.refetch()} className="ml-2 underline">Retry</button></div> : null}
      {!triage.isLoading && !triage.isError && !items.length ? <EmptyBlock title="No alerts match" message="Try clearing filters, or return after monitoring creates a new actionable notification." /> : null}
      <div className="grid min-w-0 gap-3 xl:grid-cols-2">
        {items.map((item) => <TriageCard key={item.alert_id} item={item} pending={action.isPending} onAction={(kind) => action.mutate({ item, kind })} />)}
      </div>
    </section>
  );
}

function TriageCard({ item, pending, onAction }: { item: MonitoringTriageItem; pending: boolean; onAction: (kind: string) => void }): JSX.Element {
  const terminal = item.status === "resolved" || item.status === "false_positive";
  return <article className="min-w-0 overflow-hidden rounded-lg border border-raven-border bg-raven-panel/85 p-4">
    <div className="flex items-start gap-3"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-200" aria-hidden="true" /><div className="min-w-0 flex-1"><div className="flex flex-wrap gap-2"><Badge value={item.severity} /><Badge value={item.status} />{item.suppressed ? <Badge value={item.suppressed_due_to_maintenance ? "maintenance suppressed" : "muted"} /> : null}</div><h3 className="mt-2 break-words font-medium">{safeString(item.title, "Monitoring alert")}</h3><p className="mt-1 break-words text-sm text-raven-muted">{safeString(item.description, "Review this monitoring condition.")}</p></div></div>
    <dl className="mt-3 grid gap-2 text-xs text-raven-muted sm:grid-cols-2"><div><dt>Owner</dt><dd className="text-raven-text">{safeString(item.owner_name, "Unassigned")}</dd></div><div><dt>Source</dt><dd className="break-words text-raven-text">{safeString(item.source, "monitoring")}</dd></div><div><dt>First seen</dt><dd className="text-raven-text">{safeDate(item.first_seen)?.toLocaleString() ?? "Unavailable"}</dd></div><div><dt>Last seen</dt><dd className="text-raven-text">{safeDate(item.last_seen)?.toLocaleString() ?? "Unavailable"}</dd></div></dl>
    {item.resolution_summary ? <p className="mt-3 break-words rounded-md bg-raven-bg/60 p-2 text-xs text-raven-muted">Resolution: {item.resolution_summary}</p> : null}
    <div className="mt-4 flex flex-wrap gap-2">
      {!terminal && !item.owner_id ? <Action icon={UserRoundCheck} label="Assign to me" pending={pending} onClick={() => onAction("assign")} /> : null}
      {!terminal && item.status !== "investigating" && item.status !== "muted" ? <Action label="Investigate" pending={pending} onClick={() => onAction("investigate")} /> : null}
      {!terminal && item.status === "muted" ? <Action icon={Volume2} label="Unmute" pending={pending} onClick={() => onAction("unmute")} /> : null}
      {!terminal && item.status !== "muted" ? <Action icon={VolumeX} label="Mute" pending={pending} onClick={() => onAction("mute")} /> : null}
      {!terminal ? <Action icon={CheckCircle2} label="Resolve" pending={pending} onClick={() => onAction("resolve")} /> : null}
      {!terminal ? <Action label="False positive" pending={pending} onClick={() => onAction("false_positive")} /> : null}
      {item.action_url ? <Link to={safeInternalRoute(item.action_url, "/monitoring")} className="inline-flex items-center gap-1 rounded-md border border-raven-border px-2 py-1 text-xs text-raven-cyan"><ExternalLink className="h-3 w-3" />Open related</Link> : null}
    </div>
  </article>;
}

function Filter({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: string[] }): JSX.Element {
  return <label className="text-xs text-raven-muted">{label}<select value={value} onChange={(event) => onChange(event.target.value)} className="mt-1 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm capitalize text-raven-text">{options.map((option) => <option key={option || "all"} value={option}>{option ? option.replace(/_/g, " ") : `All ${label.toLowerCase()}es`}</option>)}</select></label>;
}

function Badge({ value }: { value: string }): JSX.Element { return <span className="max-w-full break-words rounded-full border border-raven-border px-2 py-0.5 text-xs capitalize text-raven-muted">{value.replace(/_/g, " ")}</span>; }
function Action({ label, onClick, pending, icon: Icon }: { label: string; onClick: () => void; pending: boolean; icon?: typeof AlertTriangle }): JSX.Element { return <button type="button" onClick={onClick} disabled={pending} title={pending ? "Another triage action is in progress." : undefined} className="inline-flex items-center gap-1 rounded-md border border-raven-border px-2 py-1 text-xs hover:border-raven-cyan disabled:cursor-not-allowed disabled:opacity-50">{Icon ? <Icon className="h-3 w-3" /> : null}{label}</button>; }
function validUuid(value: string): boolean { return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value); }
