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
  listEndpointRecommendations,
  runLanServiceCheck,
  updateLanAsset,
  updateLanAssetCriticality,
} from "../lib/api";
import { safeArray, safeDate, safeNumber, safeString } from "../lib/safe";
import { useI18n } from "../lib/i18n";
import { useAuth } from "../lib/useAuth";
import type { LanAsset } from "../types";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "./StateBlock";
import { ToastBanner, type ToastState } from "./ToastBanner";
import { serviceHealthIcon, serviceHealthTone } from "../lib/serviceHealth";
import type { LanServiceObservation } from "../types";

type AssetFilter = "all" | "authorized" | "needs_review" | "unauthorized" | "agent" | "no_agent" | "online" | "offline" | "windows" | "linux" | "android" | "ios" | "mobile" | "tablet" | "server" | "router" | "iot" | "unknown";

export function LanMonitoringPanel({ agentsOnly = false }: { agentsOnly?: boolean }): JSX.Element {
  const { t } = useI18n();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const isAdmin = user?.role === "admin";
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [cidr, setCidr] = useState("");
  const [toast, setToast] = useState<ToastState | null>(null);
  const [assetOwner, setAssetOwner] = useState("");
  const [businessFunction, setBusinessFunction] = useState("");
  const [assetEnvironment, setAssetEnvironment] = useState("");
  const [assetFilter, setAssetFilter] = useState<AssetFilter>("all");
  const [serviceFilter, setServiceFilter] = useState("all");
  const listing = useQuery({
    queryKey: ["lan-assets"],
    queryFn: listLanAssets,
    enabled: isAdmin,
    refetchInterval: 30_000,
    retry: 1,
  });
  const allAssets = safeArray(listing.data?.items);
  const modeAssets = agentsOnly ? allAssets.filter((asset) => ["agent", "endpoint_agent"].includes(asset.source)) : allAssets;
  const assets = modeAssets.filter((asset) => assetMatchesFilter(asset, assetFilter));
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
  const recommendations = useQuery({
    queryKey: ["lan-recommendations", selectedId],
    queryFn: () => listEndpointRecommendations({ asset_id: selectedId ?? "" }),
    enabled: isAdmin && Boolean(selectedId),
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
  function selectServiceSummary(label: string): void {
    const filter = label === "Warnings" ? "warning" : label === "Open services" ? "open" : label === "Assets checked" ? "all" : label.toLowerCase();
    setServiceFilter(filter);
    const candidate = modeAssets.find((asset) => label === "Warnings" ? asset.service_warnings > 0 : label === "Critical" ? asset.service_critical > 0 : label === "Expected" ? asset.service_expected > 0 : label === "Unexpected" ? asset.service_unexpected > 0 : label === "Open services" ? asset.observed_service_preview.some((item) => item.endsWith(" open")) : asset.observed_services > 0);
    if (candidate) setSelectedId(candidate.id);
    window.setTimeout(() => document.getElementById("lan-service-detail")?.scrollIntoView({ behavior: "smooth" }), 50);
  }

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

      {!agentsOnly ? <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"><div className="flex flex-wrap gap-2"><State label={t("Automatic asset registration")} active={Boolean(config?.auto_registration_enabled)} /><State label={t("ServerHost agent")} active={Boolean(config?.server_host_agent_connected)} /><State label={t("Host neighbor collector")} active={Boolean(config?.neighbor_collector_active)} /></div><div className="mt-3 grid gap-2 text-xs text-raven-muted sm:grid-cols-2 lg:grid-cols-4"><p>{t("Last host neighbor sample")}: {safeDate(config?.last_host_neighbor_sample)?.toLocaleString() ?? t("Never")}</p><p>{t("Raw observations")}: {safeNumber(config?.neighbor_raw_observations)}</p><p>{t("Accepted observations")}: {safeNumber(config?.neighbor_accepted_observations)}</p><p>{t("Rejected observations")}: {safeNumber(config?.neighbor_rejected_observations)}</p><p>{t("Deduplicated observations")}: {safeNumber(config?.neighbor_deduplicated_observations)}</p><p>{t("Out-of-CIDR observations")}: {safeNumber(config?.neighbor_out_of_cidr_observations)}</p><p>{t("Assets created")}: {safeNumber(config?.neighbor_assets_created)}</p><p>{t("Assets updated")}: {safeNumber(config?.neighbor_assets_updated)}</p></div>{!config?.neighbor_collector_active ? <p className="mt-3 text-xs text-cyan-100">{t("Start the manual ServerHost agent to populate read-only host neighbor observations. An empty sample is informational, not a platform failure.")}</p> : null}</section> : null}

      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-3"><p className="mb-2 text-xs uppercase tracking-wide text-raven-muted">{t("Asset filters")}</p><div className="flex flex-wrap gap-2">{(["all", "authorized", "needs_review", "unauthorized", "agent", "no_agent", "online", "offline", "windows", "linux", "android", "ios", "mobile", "tablet", "server", "router", "iot", "unknown"] as AssetFilter[]).map((filter) => <button type="button" key={filter} onClick={() => setAssetFilter(filter)} className={`rounded-full border px-3 py-1 text-xs ${assetFilter === filter ? "border-raven-cyan bg-raven-cyan/10 text-raven-cyan" : "border-raven-border text-raven-muted"}`}>{t(filterLabel(filter))}</button>)}</div></section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Metric label="Assets" value={agentsOnly ? modeAssets.length : safeNumber(config?.total)} />
        <Metric label="Online" value={modeAssets.filter((asset) => asset.status === "online").length} />
        <Metric label="Needs review" value={modeAssets.filter((asset) => asset.trust_state === "needs_review" || asset.trust_state === "gateway").length} />
        <Metric label={t("Open services")} value={safeNumber(config?.open_service_observations)} />
        <Metric label="Agents connected" value={modeAssets.filter((asset) => asset.agent_connected).length} />
      </section>
      {!agentsOnly ? <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-3"><h2 className="text-sm font-semibold">{t("LAN services")}</h2><div className="mt-2 grid gap-2 sm:grid-cols-3 xl:grid-cols-6">{[["Assets checked", modeAssets.filter((asset) => asset.observed_services > 0).length], ["Open services", safeNumber(config?.open_service_observations)], ["Expected", modeAssets.reduce((n, asset) => n + asset.service_expected, 0)], ["Unexpected", modeAssets.reduce((n, asset) => n + asset.service_unexpected, 0)], ["Warnings", modeAssets.reduce((n, asset) => n + asset.service_warnings, 0)], ["Critical", modeAssets.reduce((n, asset) => n + asset.service_critical, 0)]].map(([label, value]) => <button key={String(label)} type="button" className="rounded border border-raven-border p-2 text-left text-xs hover:border-raven-cyan" onClick={() => selectServiceSummary(String(label))}>{t(String(label))}: <strong>{value}</strong></button>)}</div></section> : null}

      {!assets.length ? (
        <EmptyBlock title={agentsOnly ? "No endpoint agents are reporting" : "No authorized LAN observations yet"} message={agentsOnly ? "No optional host telemetry has registered. Platform health is unaffected; install and manually run the local agent only on an approved host." : t("Docker could not read host LAN neighbors. Start the ServerHost agent to collect read-only host neighbor observations, or import router observations manually.")} nextStep={agentsOnly ? "Use the documented agent registration flow; no credentials or commands are collected." : t("Agent self-registration does not require manual asset creation.")} />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-raven-border">
          <table className="w-full min-w-[1400px] text-left text-sm">
            <thead className="bg-raven-panelSoft text-xs uppercase tracking-wide text-raven-muted"><tr><th className="p-3">{t("Device")}</th><th className="p-3">IP</th><th className="p-3">MAC</th><th className="p-3">{t("Vendor")}</th><th className="p-3">{t("OS")}</th><th className="p-3">{t("Device type")}</th><th className="p-3">{t("Classification confidence")}</th><th className="p-3">{t("Classification source")}</th><th className="p-3">{t("Trust/source")}</th><th className="p-3">{t("Status")}</th><th className="p-3">{t("Last seen")}</th><th className="p-3">{t("Services")}</th><th className="p-3">{t("Agent")}</th><th className="p-3">{t("Posture")}</th></tr></thead>
            <tbody>{assets.map((asset) => (
              <tr key={asset.id} className="border-t border-raven-border align-top hover:bg-raven-panelSoft/60">
                <td className="p-3"><button type="button" className="text-left font-medium text-raven-cyan hover:underline" onClick={() => setSelectedId(asset.id)}>{safeString(asset.hostname, safeString(asset.asset_type, "Unknown asset"))}</button></td>
                <td className="p-3 font-mono text-xs">{safeString(asset.ip_address, "unknown")}</td>
                <td className="p-3 font-mono text-xs">{safeString(asset.mac_address, "MAC unavailable")}</td>
                <td className="p-3">{safeString(asset.vendor, t("Unknown"))}<br /><span className="text-xs text-raven-muted">{safeString(asset.vendor_source)} {safeString(asset.vendor_confidence)}</span></td>
                <td className="p-3">{t(asset.os_family)}<br /><span className="text-xs text-raven-muted">{safeString(asset.os_version)}</span></td>
                <td className="p-3">{t(asset.device_type)}</td>
                <td className="p-3">{t(asset.classification_confidence)}</td>
                <td className="p-3 text-xs">{t(asset.classification_source)}</td>
                <td className="p-3 capitalize">{safeString(asset.trust_state, "needs_review").replace(/_/g, " ")}<br /><span className="text-xs text-raven-muted">{safeString(asset.source, "unknown")}</span></td>
                <td className="p-3 capitalize">{safeString(asset.status, "unknown")}<br /><span className="text-xs text-raven-muted">Telemetry {safeString(asset.telemetry_freshness, "missing")}</span></td>
                <td className="p-3 text-raven-muted">{safeDate(asset.last_seen)?.toLocaleString() ?? "Never"}</td>
                <td className="p-3">{asset.service_check_eligible ? t("Eligible") : t("Not eligible")}<br /><span className="text-xs text-raven-muted">{safeNumber(asset.observed_services)} {t("Observed service")}</span><ul className="mt-1 space-y-0.5 text-xs">{safeArray(asset.observed_service_preview).map((item) => <li key={item} className="font-mono">{safeString(item)}</li>)}</ul>{asset.service_warnings || asset.service_critical ? <span className="text-xs text-amber-100">! {asset.service_warnings} {t("Warnings")} · × {asset.service_critical} {t("Critical")}</span> : null}</td>
                <td className="p-3">{asset.agent_connected ? "Connected" : ["agent", "endpoint_agent"].includes(asset.source) ? "Stale" : "No agent"}</td>
                <td className="p-3 capitalize">{safeString(asset.posture_status, "unknown").replace(/_/g, " ")}<br /><span className="text-xs text-raven-muted">{safeNumber(asset.recommendation_count)} recommendation(s)</span></td>
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
          <div className="mt-4 grid gap-3 rounded-md border border-raven-border p-3 text-sm sm:grid-cols-2 xl:grid-cols-4"><div><h3 className="font-medium">{t("Identity")}</h3><p>{safeString(selected.hostname, t("Unknown"))}</p></div><div><h3 className="font-medium">{t("Network")}</h3><p>{selected.ip_address} · {safeString(selected.mac_address, t("Unknown"))}</p></div><div><h3 className="font-medium">{t("Operating System")}</h3><p>{t(selected.os_family)} {safeString(selected.os_name)} {safeString(selected.os_version)} {safeString(selected.architecture)}</p></div><div><h3 className="font-medium">{t("Device Classification")}</h3><p>{t(selected.device_type)} · {t(selected.classification_confidence)} · {t(selected.classification_source)}</p><ul className="mt-1 list-inside list-disc text-xs text-raven-muted">{safeArray(selected.classification_evidence).map((evidence) => <li key={evidence}>{t(evidence)}</li>)}</ul></div><div><h3 className="font-medium">{t("Agent")}</h3><p>{selected.agent_connected ? t("Connected") : t("No agent")} · {safeString(selected.agent_mode)}</p></div><div><h3 className="font-medium">{t("Vendor")}</h3><p>{safeString(selected.vendor, t("Unknown"))} · {safeString(selected.vendor_source)} · {t(selected.vendor_confidence)}</p></div><div><h3 className="font-medium">{t("Security Posture")}</h3><p>{t(selected.posture_status)} · {selected.recommendation_count} {t("Recommendations")}</p></div><div><h3 className="font-medium">{t("Device type")}</h3><select value={safeString(selected.manual_device_type, "unknown")} onChange={(event) => update.mutate({ asset: selected, changes: { device_type: event.target.value } })} className="mt-1 rounded border border-raven-border bg-raven-panelSoft p-1"><option value="unknown">{t("No manual classification")}</option>{["desktop", "laptop", "server", "mobile", "tablet", "router", "network_device", "iot", "virtual_machine"].map((kind) => <option key={kind} value={kind}>{t(kind)}</option>)}</select><p className="mt-1 text-xs text-raven-muted">{t("Authenticated agent metadata takes priority.")}</p></div></div>
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
            <ObservedServicesPanel items={safeArray(services.data?.items)} filter={serviceFilter} onFilter={setServiceFilter} t={t} />
          </div>
          <section className="mt-4"><h3 className="text-sm font-medium">{t("Recommendations")}</h3>{safeArray(recommendations.data?.items).length ? <ul className="mt-2 grid gap-2 md:grid-cols-2">{safeArray(recommendations.data?.items).map((item) => <li key={item.id} className="rounded border border-raven-border p-3 text-sm"><p className="font-medium">{item.title} · {t(item.confidence)}</p><p className="mt-1 text-raven-muted">{item.reason}</p><p className="mt-1 text-xs">{item.recommended_action}</p></li>)}</ul> : <p className="mt-2 text-sm text-raven-muted">{t("No recommendations available.")}</p>}</section>
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

function ObservedServicesPanel({ items, filter, onFilter, t }: { items: LanServiceObservation[]; filter: string; onFilter: (value: string) => void; t: (key: string) => string }): JSX.Element {
  const filtered = items.filter((item) => {
    if (filter === "open") return item.status === "open";
    if (filter === "expected" || filter === "unexpected") return item.expectation === filter;
    if (filter === "warning" || filter === "critical") return item.advisory_severity === filter;
    if (filter === "changed") return item.changed_from_previous && Date.now() - new Date(item.observed_at).getTime() < 24 * 60 * 60 * 1000;
    return true;
  });
  const counts = [
    ["Observed ports", items.length], ["Open services", items.filter((item) => item.status === "open").length],
    ["Expected", items.filter((item) => item.expectation === "expected").length],
    ["Unexpected", items.filter((item) => item.expectation === "unexpected").length],
    ["Warnings", items.filter((item) => item.advisory_severity === "warning").length],
    ["Critical", items.filter((item) => item.advisory_severity === "critical").length],
  ] as const;
  return <div id="lan-service-detail"><h3 className="text-sm font-medium">{t("Observed Services")}</h3><p className="mt-1 text-xs text-raven-muted">{t("An open port indicates reachability, not a confirmed vulnerability.")} {t("Advisory risk indicator only.")}</p><div className="mt-2 grid grid-cols-2 gap-1 text-xs sm:grid-cols-3">{counts.map(([label, value]) => <button key={label} type="button" onClick={() => onFilter(label === "Open services" ? "open" : label === "Warnings" ? "warning" : label === "Observed ports" ? "all" : label.toLowerCase())} className="rounded border border-raven-border p-1 text-left hover:border-raven-cyan">{t(label)}: {value}</button>)}</div><div className="mt-2 flex flex-wrap gap-1">{["all", "open", "expected", "unexpected", "warning", "critical", "changed"].map((value) => <button key={value} type="button" aria-pressed={filter === value} onClick={() => onFilter(value)} className={`rounded-full border px-2 py-1 text-xs ${filter === value ? "border-raven-cyan text-raven-cyan" : "border-raven-border text-raven-muted"}`}>{t(value === "changed" ? "Changed recently" : value === "open" ? "Open only" : value)}</button>)}</div>{filtered.length ? <ul className="mt-2 space-y-2">{filtered.map((item) => <li key={item.id} className="rounded-md border border-raven-border p-3 text-sm"><div className="flex flex-wrap items-center gap-2"><span className="font-mono">{item.port}/{item.protocol}</span><strong>{safeString(item.service_label, safeString(item.service_name, t("Unknown TCP service")))}</strong><span>{t(item.status)}</span>{item.service_name === "ssh" ? <span className="text-xs text-cyan-100">SSH indicator</span> : null}<span className={`rounded-full border px-2 py-0.5 text-xs ${serviceHealthTone[item.advisory_severity]}`} aria-label={`${t(item.advisory_severity)}: ${item.advisory_reason}`}>{serviceHealthIcon[item.advisory_severity]} {t(item.advisory_severity)}</span><span className="text-xs">{t(item.expectation)}</span></div><p className="mt-1 text-xs text-raven-muted">{item.advisory_reason}</p><p className="mt-1 text-xs text-raven-muted">{t("Confidence")}: {t(item.identification_confidence)} ({item.confidence}%) · {t("First observed")}: {safeDate(item.first_observed_at)?.toLocaleString() ?? t("Unknown")} · {t("Last observed")}: {safeDate(item.observed_at)?.toLocaleString() ?? t("Unknown")}</p><p className="text-xs text-raven-muted">{t("Source")}: {safeString(item.source, t("Unknown"))} · {t("Previous state")}: {safeString(item.previous_status, t("Unknown"))}{item.changed_from_previous ? ` · ${t("Changed recently")}` : ""}</p></li>)}</ul> : <p className="mt-2 text-sm text-raven-muted">{t("No matching service observations.")}</p>}</div>;
}

function State({ label, active }: { label: string; active: boolean }): JSX.Element {
  return <span className={`rounded-full border px-2 py-1 text-xs ${active ? "border-emerald-400/30 text-emerald-200" : "border-cyan-300/30 text-cyan-100"}`}>{label}: {active ? "ready" : "needs action"}</span>;
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

function assetMatchesFilter(asset: LanAsset, filter: AssetFilter): boolean {
  if (filter === "all") return true;
  if (filter === "authorized") return asset.trust_state === "authorized" || asset.trust_state === "known_agent";
  if (filter === "needs_review") return asset.trust_state === "needs_review" || asset.trust_state === "gateway";
  if (filter === "unauthorized") return asset.trust_state === "unauthorized";
  if (filter === "agent") return ["agent", "endpoint_agent"].includes(asset.source);
  if (filter === "no_agent") return !["agent", "endpoint_agent"].includes(asset.source);
  if (["windows", "linux", "android", "ios"].includes(filter)) return asset.os_family === filter;
  if (["mobile", "tablet", "server", "router", "iot"].includes(filter)) return asset.device_type === filter;
  if (filter === "unknown") return asset.os_family === "unknown" || asset.device_type === "unknown";
  return asset.status === filter;
}

function filterLabel(filter: AssetFilter): string {
  const labels: Record<AssetFilter, string> = {
    all: "All",
    authorized: "Authorized",
    needs_review: "Needs review",
    unauthorized: "Unauthorized",
    agent: "Agent monitored",
    no_agent: "No agent",
    online: "Online",
    offline: "Offline",
    windows: "Windows", linux: "Linux", android: "Android", ios: "iOS", mobile: "Mobile", tablet: "Tablet", server: "Server", router: "Router", iot: "IoT", unknown: "Unknown",
  };
  return labels[filter];
}
