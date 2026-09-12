import { RadioTower, RefreshCw, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  discoverLan,
  getLanAsset,
  getLanAssetHistory,
  getLanServiceHistory,
  listLanAssets,
  listLanServices,
  listLanTelemetry,
  runLanServiceCheck,
  updateLanAsset,
  updateLanAssetCriticality,
} from "../lib/api";
import { safeArray, safeDate, safeNumber, safeString } from "../lib/safe";
import { useAuth } from "../lib/useAuth";
import type { LanAsset } from "../types";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "./StateBlock";
import { ToastBanner, type ToastState } from "./ToastBanner";

export function LanMonitoringPanel({ agentsOnly = false }: { agentsOnly?: boolean }): JSX.Element {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const isAdmin = user?.role === "admin";
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [cidr, setCidr] = useState("");
  const [toast, setToast] = useState<ToastState | null>(null);
  const [assetOwner, setAssetOwner] = useState("");
  const [businessFunction, setBusinessFunction] = useState("");
  const [assetEnvironment, setAssetEnvironment] = useState("");
  const listing = useQuery({
    queryKey: ["lan-assets"],
    queryFn: listLanAssets,
    enabled: isAdmin,
    refetchInterval: 30_000,
    retry: 1,
  });
  const allAssets = safeArray(listing.data?.items);
  const assets = agentsOnly ? allAssets.filter((asset) => asset.source === "agent") : allAssets;
  useEffect(() => {
    if (selectedId && !assets.some((asset) => asset.id === selectedId)) setSelectedId(null);
  }, [assets, selectedId]);

  const detail = useQuery({
    queryKey: ["lan-asset", selectedId],
    queryFn: () => getLanAsset(selectedId ?? ""),
    enabled: isAdmin && Boolean(selectedId),
  });
  const telemetry = useQuery({
    queryKey: ["lan-telemetry", selectedId],
    queryFn: () => listLanTelemetry(selectedId ?? ""),
    enabled: isAdmin && Boolean(selectedId),
  });
  const services = useQuery({
    queryKey: ["lan-services", selectedId],
    queryFn: () => listLanServices(selectedId ?? ""),
    enabled: isAdmin && Boolean(selectedId),
  });
  const history = useQuery({
    queryKey: ["lan-asset-history", selectedId],
    queryFn: () => getLanAssetHistory(selectedId ?? ""),
    enabled: isAdmin && Boolean(selectedId),
    retry: 1,
  });
  const serviceHistory = useQuery({
    queryKey: ["lan-service-history", selectedId],
    queryFn: () => getLanServiceHistory(selectedId ?? ""),
    enabled: isAdmin && Boolean(selectedId),
    retry: 1,
  });
  const selected = detail.data ?? assets.find((asset) => asset.id === selectedId);
  useEffect(() => {
    setAssetOwner(safeString(selected?.owner));
    setBusinessFunction(safeString(selected?.business_function));
    setAssetEnvironment(safeString(selected?.environment));
  }, [selected?.id, selected?.owner, selected?.business_function, selected?.environment]);
  const discovery = useMutation({
    mutationFn: () => discoverLan(cidr || undefined),
    onSuccess: async (result) => {
      setToast({ kind: result.limitation ? "error" : "success", message: result.limitation ?? result.message });
      await queryClient.invalidateQueries({ queryKey: ["lan-assets"] });
    },
    onError: (error) => setToast({ kind: "error", message: error instanceof Error ? error.message : "LAN discovery failed." }),
  });
  const update = useMutation({
    mutationFn: ({ asset, changes }: { asset: LanAsset; changes: Parameters<typeof updateLanAsset>[1] }) =>
      updateLanAsset(asset.id, changes),
    onSuccess: async (asset) => {
      setToast({ kind: "success", message: "LAN asset monitoring settings updated." });
      queryClient.setQueryData(["lan-asset", asset.id], asset);
      await queryClient.invalidateQueries({ queryKey: ["lan-assets"] });
    },
    onError: (error) => setToast({ kind: "error", message: error instanceof Error ? error.message : "Asset update failed." }),
  });
  const updateCriticality = useMutation({
    mutationFn: ({ asset, criticality }: { asset: LanAsset; criticality: LanAsset["criticality"] }) =>
      updateLanAssetCriticality(asset.id, {
        criticality,
        owner: assetOwner.trim() || null,
        business_function: businessFunction.trim() || null,
        environment: assetEnvironment.trim() || null,
      }),
    onSuccess: async (asset) => {
      setToast({ kind: "success", message: "Asset criticality and business context updated." });
      queryClient.setQueryData(["lan-asset", asset.id], asset);
      await queryClient.invalidateQueries({ queryKey: ["lan-assets"] });
    },
    onError: (error) => setToast({ kind: "error", message: error instanceof Error ? error.message : "Criticality update failed." }),
  });
  const serviceCheck = useMutation({
    mutationFn: (assetId: string) => runLanServiceCheck(assetId),
    onSuccess: async (result) => {
      setToast({ kind: "success", message: `${result.message} ${result.open_ports} open port(s) observed.` });
      await Promise.all([queryClient.invalidateQueries({ queryKey: ["lan-services", result.asset_id] }), queryClient.invalidateQueries({ queryKey: ["lan-service-history", result.asset_id] }), queryClient.invalidateQueries({ queryKey: ["lan-asset-history", result.asset_id] }), queryClient.invalidateQueries({ queryKey: ["lan-assets"] })]);
    },
    onError: () => setToast({ kind: "error", message: "The authorized service check could not run. Review enablement, authorization, and rate limits." }),
  });

  if (!isAdmin) {
    return <EmptyBlock title="Administrator access required" message="LAN addresses, endpoint telemetry, and authorization controls are restricted to platform administrators." />;
  }
  if (listing.isLoading) return <LoadingBlock label="Loading authorized LAN inventory" />;
  if (listing.error) return <ErrorBlock message={listing.error} onRetry={() => void listing.refetch()} />;
  const config = listing.data;

  return (
    <div className="space-y-4">
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}
      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-semibold">{agentsOnly ? "Endpoint agents" : "Authorized LAN inventory"}</h2>
            <p className="mt-1 max-w-3xl text-sm text-raven-muted">{safeString(config?.limitation, "LAN inventory uses explicit private ranges and safe observations only.")}</p>
          </div>
          <span className={`rounded-full border px-3 py-1 text-xs ${config?.enabled ? "border-emerald-400/30 text-emerald-200" : "border-amber-400/30 text-amber-100"}`}>
            {config?.enabled ? "LAN monitoring enabled" : "LAN monitoring disabled"}
          </span>
        </div>
        {!agentsOnly ? (
          <div className="mt-4 flex flex-wrap gap-2">
            <select value={cidr} onChange={(event) => setCidr(event.target.value)} className="rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm">
              <option value="">Configured default range</option>
              {safeArray(config?.allowed_cidrs).map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <button type="button" onClick={() => discovery.mutate()} disabled={!config?.enabled || discovery.isPending} title={!config?.enabled ? "Enable LAN_MONITORING_ENABLED as an administrator before discovery." : discovery.isPending ? "Authorized discovery is already running." : "Process authorized private-range observations."} className="inline-flex items-center gap-2 rounded-md bg-raven-violet px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50">
              <RadioTower className="h-4 w-4" aria-hidden="true" />
              {discovery.isPending ? "Checking observations" : "Run safe discovery"}
            </button>
            <button type="button" onClick={() => void listing.refetch()} className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm">
              <RefreshCw className="h-4 w-4" aria-hidden="true" /> Refresh
            </button>
          </div>
        ) : null}
        {!agentsOnly && !config?.enabled ? <p className="mt-2 text-xs text-amber-100">Run safe discovery is disabled because LAN monitoring is off. An administrator must enable it in local configuration.</p> : null}
        <p className="mt-3 text-xs text-raven-muted">Private ranges: {safeArray(config?.allowed_cidrs).join(", ") || "none"} · interval {safeNumber(config?.discovery_interval_seconds, 300)}s · ping {config?.ping_enabled ? "enabled" : "disabled"} · service observations {config?.service_check_enabled ? "enabled" : "disabled"}</p>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Metric label="Assets" value={agentsOnly ? assets.length : safeNumber(config?.total)} />
        <Metric label="Online" value={assets.filter((asset) => asset.status === "online").length} />
        <Metric label="Offline" value={assets.filter((asset) => asset.status === "offline").length} />
        <Metric label="Unauthorized" value={assets.filter((asset) => !asset.is_authorized).length} />
        <Metric label="Agents connected" value={assets.filter((asset) => asset.agent_connected).length} />
      </section>

      {!assets.length ? (
        <EmptyBlock title={agentsOnly ? "No endpoint agents are reporting" : "No authorized LAN observations yet"} message={agentsOnly ? "No optional host telemetry has registered. Platform health is unaffected; install and manually run the local agent only on an approved host." : "Docker cannot always read host neighbors. Enable LAN monitoring, then provide an authorized private range through router/static observations or the optional local agent."} nextStep={agentsOnly ? "Use the documented agent registration flow; no credentials or commands are collected." : "Host LAN discovery may be limited inside Docker; this is not a platform failure."} />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-raven-border">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="bg-raven-panelSoft text-xs uppercase tracking-wide text-raven-muted"><tr><th className="p-3">Asset</th><th className="p-3">Address</th><th className="p-3">Criticality</th><th className="p-3">Status</th><th className="p-3">Last seen</th><th className="p-3">Authorization</th><th className="p-3">Agent</th><th className="p-3">Attention</th></tr></thead>
            <tbody>{assets.map((asset) => (
              <tr key={asset.id} className="border-t border-raven-border align-top hover:bg-raven-panelSoft/60">
                <td className="p-3"><button type="button" className="text-left font-medium text-raven-cyan hover:underline" onClick={() => setSelectedId(asset.id)}>{safeString(asset.hostname, safeString(asset.asset_type, "Unknown asset"))}</button><p className="text-xs text-raven-muted">{safeString(asset.vendor, safeString(asset.source, "unknown"))}</p></td>
                <td className="p-3 font-mono text-xs">{safeString(asset.ip_address, "unknown")}<br /><span className="text-raven-muted">{safeString(asset.mac_address, "MAC unavailable")}</span></td>
                <td className="p-3 capitalize">{safeString(asset.criticality, "medium")}</td>
                <td className="p-3 capitalize">{safeString(asset.status, "unknown")}</td>
                <td className="p-3 text-raven-muted">{safeDate(asset.last_seen)?.toLocaleString() ?? "Never"}</td>
                <td className="p-3">{asset.is_authorized ? "Authorized" : "Review required"}<br /><span className="text-xs text-raven-muted">Monitoring {asset.monitoring_enabled ? "on" : "off"}</span></td>
                <td className="p-3">{asset.agent_connected ? "Connected" : asset.source === "agent" ? "Not reporting" : "Not installed"}</td>
                <td className="p-3">{safeArray(asset.risk_indicators).filter((item) => item.severity !== "info").length || "None"}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}

      {selected ? (
        <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-semibold">Endpoint detail · {safeString(selected.hostname, selected.ip_address)}</h2><p className="mt-1 font-mono text-xs text-raven-muted">{selected.ip_address} · {safeString(selected.mac_address, "MAC unavailable")}</p></div><div className="flex flex-wrap gap-2"><button type="button" onClick={() => update.mutate({ asset: selected, changes: { is_authorized: !selected.is_authorized } })} className="rounded-md border border-raven-border px-3 py-2 text-xs"><ShieldCheck className="mr-1 inline h-3.5 w-3.5" />{selected.is_authorized ? "Revoke authorization" : "Authorize asset"}</button><button type="button" onClick={() => update.mutate({ asset: selected, changes: { monitoring_enabled: !selected.monitoring_enabled } })} className="rounded-md border border-raven-border px-3 py-2 text-xs">Monitoring {selected.monitoring_enabled ? "on" : "off"}</button><button type="button" onClick={() => serviceCheck.mutate(selected.id)} disabled={!config?.service_check_enabled || !selected.is_authorized || !selected.monitoring_enabled || serviceCheck.isPending} title={serviceCheckReason(config?.service_check_enabled, selected)} className="rounded-md border border-raven-border px-3 py-2 text-xs disabled:cursor-not-allowed disabled:opacity-50">{serviceCheck.isPending ? "Checking configured ports" : "Run TCP service check"}</button></div></div>
          {!config?.service_check_enabled || !selected.is_authorized || !selected.monitoring_enabled ? <p className="mt-2 text-xs text-amber-100">{serviceCheckReason(config?.service_check_enabled, selected)}</p> : <p className="mt-2 text-xs text-emerald-200">Service-check eligible. TCP connect only; no authentication, commands, brute force, or exploit payloads.</p>}
          <p className="mt-1 text-xs text-raven-muted">Configured TCP ports: {safeArray(config?.service_ports).join(", ") || "see Activation"} · last check {safeDate(selected.last_checked_at)?.toLocaleString() ?? "never"}</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric label="CPU" value={percent(safeArray(telemetry.data?.items)[0]?.cpu_percent)} />
            <Metric label="Memory" value={percent(safeArray(telemetry.data?.items)[0]?.memory_percent)} />
            <Metric label="Disk" value={percent(safeArray(telemetry.data?.items)[0]?.disk_percent)} />
            <Metric label="Latency" value={selected.response_latency_ms == null ? "Unavailable" : `${selected.response_latency_ms.toFixed(1)} ms`} />
          </div>
          <div className="mt-4 flex flex-wrap items-end gap-2 rounded-md border border-raven-border p-3">
            <label className="text-xs text-raven-muted">Criticality<select defaultValue={safeString(selected.criticality, "medium")} id={`criticality-${selected.id}`} className="mt-1 block rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm text-raven-text"><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></label>
            <label className="text-xs text-raven-muted">Owner<input value={assetOwner} onChange={(event) => setAssetOwner(event.target.value)} maxLength={255} className="mt-1 block rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm text-raven-text" /></label>
            <label className="text-xs text-raven-muted">Business function<input value={businessFunction} onChange={(event) => setBusinessFunction(event.target.value)} maxLength={255} className="mt-1 block rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm text-raven-text" /></label>
            <label className="text-xs text-raven-muted">Environment<input value={assetEnvironment} onChange={(event) => setAssetEnvironment(event.target.value)} maxLength={80} className="mt-1 block rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm text-raven-text" /></label>
            <button type="button" disabled={updateCriticality.isPending} onClick={() => {
              const element = document.getElementById(`criticality-${selected.id}`) as HTMLSelectElement | null;
              const value = element?.value;
              const criticality: LanAsset["criticality"] = value === "low" || value === "high" || value === "critical" ? value : "medium";
              updateCriticality.mutate({ asset: selected, criticality });
            }} className="rounded-md border border-raven-border px-3 py-2 text-sm disabled:opacity-50">Save context</button>
          </div>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div><h3 className="text-sm font-medium">Risk indicators</h3>{safeArray(selected.risk_indicators).length ? <ul className="mt-2 space-y-2">{safeArray(selected.risk_indicators).map((item) => <li key={item.key} className="rounded-md border border-raven-border p-3 text-sm"><span className="font-medium">{safeString(item.label, "Indicator")}</span><p className="mt-1 text-raven-muted">{safeString(item.detail, "Review this asset.")}</p></li>)}</ul> : <p className="mt-2 text-sm text-raven-muted">No current risk indicators.</p>}</div>
            <div><h3 className="text-sm font-medium">Observed services</h3>{safeArray(services.data?.items).length ? <ul className="mt-2 space-y-2">{safeArray(services.data?.items).map((item) => <li key={item.id} className="min-w-0 rounded-md border border-raven-border p-3 text-sm"><div className="flex flex-wrap items-center gap-2"><span className="font-mono">{safeNumber(item.port)}/{safeString(item.protocol, "tcp")}</span><span>{safeString(item.service_label, safeString(item.service_name, "unidentified service"))}</span><span className="rounded-full border border-raven-border px-2 py-0.5 text-xs capitalize">{safeString(item.status, "unknown")}</span>{item.service_name === "ssh" ? <span className="rounded-full border border-cyan-300/30 bg-cyan-400/10 px-2 py-0.5 text-xs text-cyan-100">SSH indicator</span> : null}{item.non_standard_ssh ? <span className="rounded-full border border-amber-300/30 bg-amber-400/10 px-2 py-0.5 text-xs text-amber-100">Non-standard SSH</span> : null}</div><p className="mt-1 break-words text-xs text-raven-muted">Confidence {safeNumber(item.confidence)}% · observed {safeDate(item.observed_at)?.toLocaleString() ?? "unknown"} · source {safeString(item.source, "unknown")}{item.banner_hint ? ` · ${safeString(item.banner_hint)}` : ""}</p>{[445, 3389, 5432, 6379].includes(item.port) && item.status === "open" ? <p className="mt-1 text-xs text-amber-100">Advisory risk indicator only; manually review intended exposure.</p> : null}</li>)}</ul> : <p className="mt-2 text-sm text-raven-muted">No service observations. Enable authorized checks or provide approved router/static observations.</p>}</div>
          </div>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div><h3 className="text-sm font-medium">Change timeline</h3>{history.isLoading ? <p className="mt-2 text-sm text-raven-muted">Loading asset history…</p> : history.error ? <p className="mt-2 text-sm text-rose-100">Asset history is temporarily unavailable.</p> : safeArray(history.data?.changes?.items).length ? <ul className="mt-2 space-y-2">{safeArray(history.data?.changes?.items).slice(0, 8).map((item) => <li key={item.id} className="min-w-0 rounded-md border border-raven-border p-3 text-sm"><div className="flex flex-wrap items-center gap-2"><span className="font-medium">{safeString(item.title, "Monitoring change")}</span><span className="rounded-full border border-raven-border px-2 py-0.5 text-xs capitalize">{safeString(item.severity, "info")}</span></div><p className="mt-1 break-words text-xs text-raven-muted">{safeDate(item.detected_at)?.toLocaleString() ?? "time unavailable"} · {safeString(item.event_type, "change")}</p></li>)}</ul> : <p className="mt-2 text-sm text-raven-muted">No asset changes have been recorded yet.</p>}<p className="mt-2 text-xs text-raven-muted">Telemetry history: {safeNumber(history.data?.telemetry_samples)} sample(s) · latest {safeDate(history.data?.telemetry_last_at)?.toLocaleString() ?? "unavailable"}</p></div>
            <div><h3 className="text-sm font-medium">Service history</h3>{serviceHistory.isLoading ? <p className="mt-2 text-sm text-raven-muted">Loading service history…</p> : serviceHistory.error ? <p className="mt-2 text-sm text-rose-100">Service history is temporarily unavailable.</p> : safeArray(serviceHistory.data?.items).length ? <ul className="mt-2 space-y-2">{safeArray(serviceHistory.data?.items).slice(0, 8).map((item) => <li key={item.id} className="min-w-0 rounded-md border border-raven-border p-3 text-sm"><div className="flex flex-wrap items-center gap-2"><span className="font-mono">{safeNumber(item.port)}/{safeString(item.protocol, "tcp")}</span><span>{safeString(item.previous_status, "first observation")} → {safeString(item.current_status, "unknown")}</span></div><p className="mt-1 break-words text-xs text-raven-muted">{safeString(item.service_name, "unidentified service")} · confidence {safeNumber(item.confidence)}% · {safeDate(item.observed_at)?.toLocaleString() ?? "time unavailable"}</p></li>)}</ul> : <p className="mt-2 text-sm text-raven-muted">No service history has been recorded.</p>}</div>
          </div>
          <p className="mt-4 text-xs text-raven-muted">Notes: {safeString(selected.notes, "No notes.")} · telemetry samples: {safeNumber(telemetry.data?.total)} · OS: {safeString(safeArray(telemetry.data?.items)[0]?.os_name, "unavailable")} {safeString(safeArray(telemetry.data?.items)[0]?.os_version)}</p>
        </section>
      ) : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }): JSX.Element {
  return <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"><p className="text-xs uppercase tracking-wide text-raven-muted">{label}</p><p className="mt-2 text-xl font-semibold">{value}</p></div>;
}

function percent(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value) ? `${Math.round(value)}%` : "Unavailable";
}

function serviceCheckReason(enabled: boolean | undefined, asset: LanAsset): string {
  if (!enabled) return "Disabled because LAN_SERVICE_CHECK_ENABLED is false.";
  if (!asset.is_authorized) return "Authorize this private LAN asset before checking services.";
  if (!asset.monitoring_enabled) return "Enable monitoring for this asset before checking services.";
  return "Run a rate-limited TCP connect check against configured ports only.";
}
