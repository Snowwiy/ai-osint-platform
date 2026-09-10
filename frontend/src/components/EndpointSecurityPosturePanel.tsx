import { CheckCircle2, RefreshCw, ShieldAlert } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import {
  acknowledgeEndpointRecommendation,
  assessEndpointPosture,
  getEndpointPostureOverview,
  listEndpointRecommendations,
  listLanAssets,
  resolveEndpointRecommendation,
} from "../lib/api";
import { safeArray, safeDate, safeNumber, safeString } from "../lib/safe";
import { useAuth } from "../lib/useAuth";
import type { EndpointRecommendation, EndpointSecurityPosture, Severity } from "../types";
import { SeverityBadge } from "./SeverityBadge";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "./StateBlock";
import { ToastBanner, type ToastState } from "./ToastBanner";

export function EndpointSecurityPosturePanel(): JSX.Element {
  const { user } = useAuth();
  const admin = user?.role === "admin";
  const queryClient = useQueryClient();
  const [assetId, setAssetId] = useState("");
  const [status, setStatus] = useState("");
  const [toast, setToast] = useState<ToastState | null>(null);
  const overview = useQuery({ queryKey: ["endpoint-posture-overview"], queryFn: getEndpointPostureOverview, enabled: admin, retry: 1 });
  const assets = useQuery({ queryKey: ["lan-assets"], queryFn: listLanAssets, enabled: admin, retry: 1 });
  const recommendations = useQuery({
    queryKey: ["endpoint-recommendations", assetId, status],
    queryFn: () => listEndpointRecommendations({ asset_id: assetId || undefined, status: status === "open" || status === "acknowledged" || status === "resolved" ? status : undefined }),
    enabled: admin,
    retry: 1,
  });
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["endpoint-posture-overview"] }),
      queryClient.invalidateQueries({ queryKey: ["endpoint-recommendations"] }),
      queryClient.invalidateQueries({ queryKey: ["monitoring-overview"] }),
    ]);
  };
  const assess = useMutation({
    mutationFn: assessEndpointPosture,
    onSuccess: async () => { setToast({ kind: "success", message: "Local posture assessment completed from stored observations." }); await refresh(); },
    onError: () => setToast({ kind: "error", message: "Posture assessment is temporarily unavailable. Verify the selected LAN asset and retry." }),
  });
  const transition = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "acknowledge" | "resolve" }) => action === "acknowledge" ? acknowledgeEndpointRecommendation(id) : resolveEndpointRecommendation(id),
    onSuccess: async () => { setToast({ kind: "success", message: "Recommendation status updated." }); await refresh(); },
    onError: () => setToast({ kind: "error", message: "The recommendation could not be updated. Refresh and retry." }),
  });
  const selected = useMemo(() => safeArray(overview.data?.items).find((item) => item.lan_asset_id === assetId), [overview.data?.items, assetId]);

  if (!admin) return <EmptyBlock title="Administrator access required" message="Endpoint posture includes LAN identifiers and is restricted to platform administrators." />;
  if (overview.isLoading || assets.isLoading || recommendations.isLoading) return <LoadingBlock label="Loading endpoint security posture" />;
  if (overview.error) return <ErrorBlock message="Endpoint posture is temporarily unavailable." onRetry={() => void overview.refetch()} />;
  if (assets.error || recommendations.error) return <ErrorBlock message="Endpoint posture details are temporarily unavailable." onRetry={() => void refresh()} />;
  const summary = overview.data;
  const items = safeArray(recommendations.data?.items);
  const assetItems = safeArray(assets.data?.items);
  return (
    <div className="space-y-4">
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}
      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><h2 className="font-semibold">Endpoint security posture</h2><p className="mt-1 max-w-3xl text-sm text-raven-muted">Deterministic advisory posture from authorized endpoint telemetry and stored LAN observations. No exploit validation, remote command, or automatic isolation occurs.</p></div>
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-xs text-raven-muted">Asset<select value={assetId} onChange={(event) => setAssetId(event.target.value)} className="mt-1 block max-w-[18rem] rounded border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm text-raven-text"><option value="">All assessed assets</option>{assetItems.map((item) => <option key={item.id} value={item.id}>{safeString(item.hostname, item.ip_address)} · {item.ip_address}</option>)}</select></label>
            <button type="button" title={!assetId ? "Choose a stored LAN asset to run an advisory assessment." : undefined} disabled={!assetId || assess.isPending} onClick={() => assess.mutate(assetId)} className="rounded-md bg-raven-violet px-3 py-2 text-sm text-white disabled:opacity-50">{assess.isPending ? "Assessing…" : "Assess selected asset"}</button>
            <button type="button" onClick={() => void refresh()} className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm"><RefreshCw className="h-4 w-4" />Refresh</button>
          </div>
        </div>
        <p className="mt-3 text-xs text-raven-muted">{safeString(summary?.advisory, "Posture is advisory and requires manual review.")}</p>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        <Metric label="Assessed" value={safeNumber(summary?.assessed_assets)} />
        <Metric label="Healthy" value={safeNumber(summary?.healthy)} />
        <Metric label="Needs review" value={safeNumber(summary?.needs_review)} />
        <Metric label="At risk" value={safeNumber(summary?.at_risk)} />
        <Metric label="Critical" value={safeNumber(summary?.critical)} />
        <Metric label="Manual isolation" value={safeNumber(summary?.isolation_recommendations)} />
      </section>

      {selected ? <PostureDetail item={selected} /> : !safeArray(summary?.items).length ? <EmptyBlock title="No posture assessments yet" message="Choose a stored authorized or observed LAN asset and run a local advisory assessment. This action performs no network scan." /> : null}

      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <div className="flex flex-wrap items-end justify-between gap-3"><div><h3 className="font-medium">Remediation recommendations</h3><p className="mt-1 text-sm text-raven-muted">Manual actions only. Router blocks, VLAN isolation, patching, and endpoint changes are never automated.</p></div><label className="text-xs text-raven-muted">Status<select value={status} onChange={(event) => setStatus(event.target.value)} className="mt-1 block rounded border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm"><option value="">All</option><option value="open">Open</option><option value="acknowledged">Acknowledged</option><option value="resolved">Resolved</option></select></label></div>
        {!items.length ? <EmptyBlock title="No matching recommendations" message="Assess an asset or adjust filters. No automatic remediation is performed." /> : <div className="mt-3 grid gap-3 lg:grid-cols-2">{items.map((item) => <RecommendationCard key={item.id} item={item} pending={transition.isPending} act={(action) => transition.mutate({ id: item.id, action })} />)}</div>}
      </section>
    </div>
  );
}

function PostureDetail({ item }: { item: EndpointSecurityPosture }): JSX.Element {
  return <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">{safeString(item.asset_hostname, item.asset_ip)}</h3><p className="font-mono text-xs text-raven-muted">{item.asset_ip}</p></div><div className="text-right"><p className="text-2xl font-semibold">{safeNumber(item.posture_score)}/100</p><p className="text-xs capitalize text-raven-muted">{safeString(item.posture_status).replace(/_/g, " ")}</p></div></div><div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Fact label="Firewall" value={item.firewall_status} /><Fact label="Antivirus / Defender" value={item.antivirus_status} /><Fact label="Patch awareness" value={item.patch_status} /><Fact label="Pending reboot" value={item.pending_reboot == null ? "unknown" : item.pending_reboot ? "yes" : "no"} /><Fact label="Agent freshness" value={item.agent_freshness} /><Fact label="Disk health" value={item.disk_health} /><Fact label="OS" value={[item.os_name, item.os_version].filter(Boolean).join(" ")} /><Fact label="Risky services" value={String(safeNumber(item.risky_services_count))} /></div><p className="mt-3 text-xs text-raven-muted">Evidence: {safeString(item.metadata?.evidence_mode, "stored observations")} · assessed {safeDate(item.assessed_at)?.toLocaleString() ?? "time unavailable"}</p></section>;
}

function RecommendationCard({ item, pending, act }: { item: EndpointRecommendation; pending: boolean; act: (action: "acknowledge" | "resolve") => void }): JSX.Element {
  return <article className="min-w-0 rounded-md border border-raven-border bg-raven-panelSoft/60 p-4"><div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0"><div className="flex flex-wrap gap-2"><SeverityBadge severity={safeSeverity(item.severity)} /><span className="rounded border border-raven-border px-2 py-0.5 text-xs capitalize">{item.status}</span>{item.isolation_recommended ? <span className="inline-flex items-center gap-1 rounded bg-rose-500/10 px-2 py-0.5 text-xs text-rose-100"><ShieldAlert className="h-3.5 w-3.5" />Manual isolation review</span> : null}</div><h4 className="mt-2 font-medium">{safeString(item.title, "Remediation recommendation")}</h4><p className="mt-1 break-words text-sm text-raven-muted">{safeString(item.reason, "Manual review is required.")}</p></div><p className="text-right text-xs text-raven-muted">{safeString(item.asset_hostname, item.affected_asset)}<br />{safeString(item.evidence_source, "stored observation")} · {safeString(item.confidence, "low")} confidence</p></div><p className="mt-3 text-sm"><span className="font-medium">Recommended action:</span> {safeString(item.recommended_action, "Review manually.")}</p><ol className="mt-2 list-decimal space-y-1 pl-5 text-xs text-raven-muted">{safeArray(item.manual_steps).map((step, index) => <li key={`${item.id}-${index}`}>{safeString(step, "Review manually.")}</li>)}</ol>{item.status !== "resolved" ? <div className="mt-3 flex flex-wrap gap-2">{item.status === "open" ? <button disabled={pending} onClick={() => act("acknowledge")} className="inline-flex items-center gap-1 rounded border border-raven-border px-2 py-1 text-xs disabled:opacity-50"><CheckCircle2 className="h-3.5 w-3.5" />Acknowledge</button> : null}<button disabled={pending} onClick={() => act("resolve")} className="rounded border border-raven-border px-2 py-1 text-xs disabled:opacity-50">Mark resolved</button></div> : null}</article>;
}

function Metric({ label, value }: { label: string; value: number }): JSX.Element { return <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"><p className="text-xs uppercase tracking-wide text-raven-muted">{label}</p><p className="mt-2 text-xl font-semibold">{value}</p></div>; }
function Fact({ label, value }: { label: string; value: unknown }): JSX.Element { return <div className="min-w-0 rounded border border-raven-border p-3"><p className="text-xs uppercase tracking-wide text-raven-muted">{label}</p><p className="mt-1 break-words text-sm capitalize">{safeString(value, "unknown").replace(/_/g, " ")}</p></div>; }
function safeSeverity(value: unknown): Severity { return value === "low" || value === "medium" || value === "high" || value === "critical" ? value : "info"; }
