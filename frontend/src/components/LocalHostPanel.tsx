import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { approveActionProposal, createActionProposal, getAccessToken, rejectActionProposal, type ActionProposal } from "../lib/api";
import { useI18n } from "../lib/i18n";
import { coreServiceHealth, localServiceHealth, serviceHealthIcon, serviceHealthTone, type LocalServiceExpectation, type ServiceHealth } from "../lib/serviceHealth";

type Process = { pid: number; name: string; cpuPercent: number; memoryBytes: number; startedAtUnix: number; creationTicks: string | null; runtimeSeconds: number; actionAvailable: boolean; actionReason: string };
type Service = { name: string; displayName: string; state: string; startType: string | null; pid: number | null; description: string | null; actionAvailable: boolean; actionReason: string };
type Inventory = { available: boolean; processes: Process[]; services: Service[]; detail: string };
type Result = { success: boolean; previousState: string; resultingState: string; message: string };
type Core = { invoke: (command: string, args?: Record<string, unknown>) => Promise<unknown> };
type Snapshot = { dockerAvailability: string; frontendMode: string; frontend: { healthy: boolean }; backend: { healthy: boolean }; readiness: { healthy: boolean }; dockerServicesStatus: string | null; dependencyStatuses: Record<string, string>; backgroundJobBackend?: string };
const BASELINE_KEY = "raventech.local-service-expectations.v1";
function readExpectations(): Record<string, LocalServiceExpectation> {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(BASELINE_KEY) ?? "{}");
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return Object.fromEntries(Object.entries(parsed).filter(([name, value]) => name.length <= 256 && value && typeof value === "object" && ["running", "stopped"].includes((value as LocalServiceExpectation).expectedState)) as [string, LocalServiceExpectation][]);
  } catch { return {}; }
}

function nativeCore(): Core | null {
  try {
    const own = (window as Window & { __TAURI__?: { core?: Core } }).__TAURI__?.core;
    const parent = window.parent !== window ? (window.parent as Window & { __TAURI__?: { core?: Core } }).__TAURI__?.core : undefined;
    return own ?? parent ?? null;
  } catch { return null; }
}

const bytes = (value: number) => `${(value / 1024 / 1024).toFixed(1)} MB`;
const elapsed = (value: number) => value < 60 ? `${value}s` : value < 3600 ? `${Math.round(value / 60)}m` : `${Math.round(value / 3600)}h`;

export function LocalHostPanel({ platformServices, serverHostConnected, nativeRuntime = false, nativeProviderAvailable = false }: { platformServices: { key: string; label: string; status: string; detail: string }[]; serverHostConnected: boolean; nativeRuntime?: boolean; nativeProviderAvailable?: boolean }): JSX.Element {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"cpu" | "memory" | "pid">("cpu");
  const [refreshSeconds, setRefreshSeconds] = useState(15);
  const [feedback, setFeedback] = useState("");
  const [review, setReview] = useState<ActionProposal | null>(null);
  const [confirmationText, setConfirmationText] = useState("");
  const [actionBusy, setActionBusy] = useState(false);
  const [expectations, setExpectations] = useState<Record<string, LocalServiceExpectation>>(readExpectations);
  const [healthFilter, setHealthFilter] = useState<ServiceHealth | "all">("all");
  const core = nativeCore();
  const token = getAccessToken();
  const inventory = useQuery({
    queryKey: ["local-host-inventory"],
    queryFn: async () => core?.invoke("get_local_host_inventory", { token }) as Promise<Inventory>,
    enabled: Boolean(core && token), refetchInterval: refreshSeconds * 1000, retry: false,
  });
  const snapshot = useQuery({
    queryKey: ["local-host-snapshot"],
    queryFn: async () => core?.invoke("probe_local_services") as Promise<Snapshot>,
    enabled: Boolean(core), refetchInterval: refreshSeconds * 1000, retry: false,
  });
  const processes = useMemo(() => {
    const items = (inventory.data?.processes ?? []).filter((item) => `${item.name} ${item.pid}`.toLowerCase().includes(search.toLowerCase()));
    return items.sort((a, b) => sort === "pid" ? a.pid - b.pid : sort === "memory" ? b.memoryBytes - a.memoryBytes : b.cpuPercent - a.cpuPercent);
  }, [inventory.data, search, sort]);
  const topCpu = [...(inventory.data?.processes ?? [])].sort((a, b) => b.cpuPercent - a.cpuPercent)[0];
  const topRam = [...(inventory.data?.processes ?? [])].sort((a, b) => b.memoryBytes - a.memoryBytes)[0];
  const desktopProcess = inventory.data?.processes.find((item) => item.name.toLowerCase().startsWith("raventech-osint-desktop"));
  const inventoryStale = Boolean(inventory.dataUpdatedAt && Date.now() - inventory.dataUpdatedAt > refreshSeconds * 3000);
  const serviceRows = (inventory.data?.services ?? []).map((service) => ({ service, assessment: localServiceHealth(service.state, expectations[service.name], inventoryStale) }));
  const shownServices = serviceRows.filter(({ assessment }) => healthFilter === "all" || assessment.health === healthFilter);
  const coreRows = [
    { name: "RavenTech Desktop", status: desktopProcess ? "running" : core ? "running" : "unknown", required: true, detail: desktopProcess ? `PID ${desktopProcess.pid} · ${bytes(desktopProcess.memoryBytes)} · ${elapsed(desktopProcess.runtimeSeconds)}` : "" },
    { name: t("Backend"), status: snapshot.data?.backend.healthy ? "healthy" : snapshot.data?.backend ? "down" : "unknown", required: true, detail: "" },
    { name: "PostgreSQL", status: snapshot.data?.dependencyStatuses?.database === "ok" ? "healthy" : snapshot.data?.dependencyStatuses?.database ? "down" : "unknown", required: true, detail: "" },
    { name: "Redis", status: snapshot.data?.backgroundJobBackend === "native" ? "optional" : snapshot.data?.dependencyStatuses?.redis === "ok" ? "healthy" : snapshot.data?.dependencyStatuses?.redis ? "down" : "unknown", required: snapshot.data?.backgroundJobBackend !== "native", detail: snapshot.data?.backgroundJobBackend === "native" ? "Not required by desktop runtime" : "" },
    { name: snapshot.data?.backgroundJobBackend === "native" ? "Native Worker" : "Celery Worker", status: snapshot.data?.dependencyStatuses?.worker === "ok" ? "healthy" : snapshot.data?.dependencyStatuses?.worker ? "down" : "unknown", required: true, detail: "" },
    ...(snapshot.data?.backgroundJobBackend === "native" ? [{ name: "Celery", status: "optional", required: false, detail: "Compatibility only" }] : []),
    { name: nativeRuntime ? "Native host provider" : "ServerHost Agent", status: nativeRuntime ? nativeProviderAvailable ? "healthy" : "unavailable" : serverHostConnected ? "connected" : "unavailable", required: false, detail: "" },
    { name: "Docker Desktop", status: snapshot.data?.dockerAvailability === "running" ? "running" : snapshot.data?.dockerAvailability === "installed" ? "unavailable" : "unknown", required: false, detail: "" },
    { name: "Embedded Frontend", status: snapshot.data?.frontend.healthy ? "healthy" : snapshot.data?.frontend ? "down" : "unknown", required: true, detail: snapshot.data?.frontendMode ?? "" },
  ];
  function setExpectation(name: string, value: LocalServiceExpectation | undefined) {
    const next = { ...expectations };
    if (value) next[name] = value; else delete next[name];
    setExpectations(next);
    localStorage.setItem(BASELINE_KEY, JSON.stringify(next));
  }

  async function terminate(item: Process) {
    if (!core || !token) return;
    try {
      const proposal = await createActionProposal({
        action_id: "raventech.process.terminate",
        origin: "manual_ui",
        target_id: String(item.pid),
        target_display_name: `${item.name} (${item.pid})`,
        reason: "Operator requested termination of this selected local process.",
        target_snapshot: { pid: item.pid, name: item.name, started_at_unix: item.startedAtUnix, creation_ticks: item.creationTicks, action_available: item.actionAvailable },
      });
      setReview(proposal);
      setConfirmationText("");
    } catch (error) { setFeedback(String(error)); }
  }

  async function serviceAction(item: Service, action: "start" | "stop" | "restart") {
    if (!core || !token) return;
    try {
      const proposal = await createActionProposal({
        action_id: `raventech.service.${action}`,
        origin: "manual_ui",
        target_id: item.name,
        target_display_name: `${item.displayName} (${item.name})`,
        reason: `Operator requested ${action} for this selected local service.`,
        target_snapshot: { name: item.name, display_name: item.displayName, state: item.state, pid: item.pid, start_type: item.startType, action_available: item.actionAvailable },
      });
      setReview(proposal);
      setConfirmationText("");
    } catch (error) { setFeedback(String(error)); }
  }

  async function approveAndExecute() {
    if (!core || !token || !review || actionBusy) return;
    setActionBusy(true);
    try {
      const refreshed = await inventory.refetch();
      const latest = refreshed.data;
      if (!latest?.available) throw new Error(t("Refresh local inventory before approval."));
      const expectedName = String(review.target_snapshot.name ?? "");
      const expectedPid = Number(review.target_snapshot.pid ?? -1);
      const currentSnapshot = review.target_type === "local_service"
        ? (() => {
          const item = latest.services.find((service) => service.name === expectedName);
          return item ? { name: item.name, display_name: item.displayName, state: item.state, pid: item.pid, start_type: item.startType, action_available: item.actionAvailable } : undefined;
        })()
        : (() => {
          const item = latest.processes.find((process) => process.pid === expectedPid);
          return item ? { pid: item.pid, name: item.name, started_at_unix: item.startedAtUnix, creation_ticks: item.creationTicks, action_available: item.actionAvailable } : undefined;
        })();
      if (!currentSnapshot) throw new Error(t("Local target changed. Create a fresh proposal."));
      await approveActionProposal(review.id, confirmationText || undefined, currentSnapshot);
      const result = await core.invoke("execute_action_proposal", { token, proposalId: review.id }) as Result;
      setFeedback(`${review.target_display_name}: ${result.previousState} → ${result.resultingState}; ${t("Post-action state verified")}`);
      setReview(null);
      setConfirmationText("");
      await inventory.refetch();
    } catch (error) {
      setFeedback(String(error));
      await inventory.refetch();
    } finally {
      setActionBusy(false);
    }
  }

  async function rejectReview() {
    if (!review) return;
    try { await rejectActionProposal(review.id); setFeedback(t("Action proposal rejected.")); }
    catch (error) { setFeedback(String(error)); }
    setReview(null);
    setConfirmationText("");
  }

  return <div className="space-y-5">
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">{t("Local host overview")}</h2><label className="text-xs text-raven-muted">{t("Refresh interval")} <select value={refreshSeconds} onChange={(event) => setRefreshSeconds(Number(event.target.value))} className="ml-2 rounded border border-raven-border bg-raven-panelSoft p-1"><option value={5}>5s</option><option value={15}>15s</option><option value={30}>30s</option></select></label></div>
      {!core ? <p className="mt-2 text-sm text-raven-muted">{t("Local host controls require the desktop app.")}</p> : !token ? <p className="mt-2 text-sm text-raven-muted">{t("Admin sign-in required.")}</p> : inventory.error ? <p className="mt-2 text-sm text-amber-100">{t("Admin authorization or local inventory unavailable.")}</p> : null}
      {inventory.data ? <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Summary label={t("Services")} value={inventory.data.services.length} /><Summary label={t("Running services")} value={inventory.data.services.filter((item) => item.state === "running").length} /><Summary label={t("Processes")} value={inventory.data.processes.length} /><Summary label={t("Highest CPU process")} value={topCpu ? `${topCpu.name} ${topCpu.cpuPercent.toFixed(1)}%` : t("Unavailable")} /><Summary label={t("Highest RAM process")} value={topRam ? `${topRam.name} ${bytes(topRam.memoryBytes)}` : t("Unavailable")} /></div> : null}
      {inventory.data ? <p className="mt-2 text-xs text-raven-muted">{inventory.data.detail}</p> : null}
      {feedback ? <p role="status" className="mt-3 rounded border border-raven-border p-2 text-sm">{feedback}</p> : null}
      {review ? <div role="dialog" aria-modal="true" aria-labelledby="action-review-title" className="mt-4 rounded-lg border border-amber-400/60 bg-raven-panelSoft p-4">
        <div className="flex items-start justify-between gap-4"><div><h3 id="action-review-title" className="font-semibold">{t("Review action")}: {review.target_display_name}</h3><p className="mt-1 text-sm">{t("Risk")}: <strong className="uppercase">{t(review.risk_level)}</strong> · {t(review.action_id)}</p></div><span aria-label={`${t("Risk")}: ${t(review.risk_level)}`} className="rounded border border-amber-400/60 px-2 py-1 text-xs">{t(review.risk_level)}</span></div>
        <p className="mt-3 text-sm">{review.reason}</p><p className="mt-2 text-sm"><strong>{t("Expected effect")}:</strong> {review.expected_effect}</p><p className="mt-2 text-sm"><strong>{t("Possible impact")}:</strong> {review.possible_impact}</p><p className="mt-2 text-sm"><strong>{t("Recovery guidance")}:</strong> {review.rollback_guidance}</p>
        <p className="mt-2 break-all text-xs text-raven-muted">{t("Proposal hash")}: {review.proposal_hash}</p>
        {review.risk_level === "high" ? <label className="mt-3 block text-sm">{t("Type the exact confirmation to approve")}: <strong className="select-all">{review.approval_confirmation}</strong><input autoComplete="off" value={confirmationText} onChange={(event) => setConfirmationText(event.target.value)} className="mt-1 block w-full rounded border border-raven-border bg-raven-panel px-3 py-2" /></label> : null}
        <div className="mt-4 flex flex-wrap gap-2"><button type="button" disabled={actionBusy || (review.risk_level === "high" && confirmationText !== review.approval_confirmation)} onClick={() => void approveAndExecute()} className="rounded bg-raven-violet px-3 py-2 text-sm font-medium disabled:opacity-50">{actionBusy ? t("Processing") : t("Approve and execute")}</button><button type="button" disabled={actionBusy} onClick={() => void rejectReview()} className="rounded border border-raven-border px-3 py-2 text-sm">{t("Reject proposal")}</button><button type="button" disabled={actionBusy} onClick={() => setReview(null)} className="rounded border border-raven-border px-3 py-2 text-sm">{t("Close")}</button></div>
        <p className="mt-3 text-xs text-raven-muted">{t("AI can recommend actions but cannot approve or execute them. Approval is one-use and expires shortly.")}</p>
      </div> : null}
      <p className="mt-2 text-xs text-raven-muted">{t("Local desktop only. No remote service or process actions.")}</p>
    </section>
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"><h2 className="text-lg font-semibold">{t("Server services")}</h2><div className="mt-3 flex flex-wrap gap-2">{(["healthy", "warning", "critical", "neutral"] as const).map((health) => <button key={health} type="button" onClick={() => setHealthFilter(healthFilter === health ? "all" : health)} className={`rounded border px-3 py-2 text-xs ${serviceHealthTone[health]}`} aria-pressed={healthFilter === health}>{serviceHealthIcon[health]} {t(health)}: {serviceRows.filter((row) => row.assessment.health === health).length}</button>)}</div><h3 className="mt-4 font-medium">{t("RavenTech Operations")}</h3><div className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">{coreRows.map((row) => { const assessment = coreServiceHealth(row.status, row.required, Boolean(snapshot.dataUpdatedAt && Date.now() - snapshot.dataUpdatedAt > refreshSeconds * 3000)); return <div key={row.name} className="rounded border border-raven-border p-3 text-xs"><strong>{row.name}</strong><p className="mt-1">{t("Status")}: {t(row.status)} {row.detail}</p><HealthBadge health={assessment.health} reason={assessment.reason} t={t} /><p className="mt-1 text-raven-muted">{assessment.reason}</p><p className="mt-1 text-raven-muted">{t("Last health check")}: {snapshot.dataUpdatedAt ? new Date(snapshot.dataUpdatedAt).toLocaleString() : t("Unknown")}</p><p className="mt-1 text-raven-muted">{t("Recommended action")}: {assessment.health === "healthy" ? t("Continue monitoring.") : t("Review this component locally.")}</p></div>; })}</div><h3 className="mt-4 font-medium">{t("Docker containers")}</h3><div className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">{platformServices.filter((item) => ["backend", "database", "redis", "worker"].includes(item.key)).map((item) => <Summary key={item.key} label={item.label} value={item.status} />)}</div><p className="mt-2 text-xs text-raven-muted">{t("Docker restarts use approved RavenTech platform controls; ServerHost restarts are manual; the desktop cannot restart itself during an action.")}</p></section>
    {inventory.data?.available ? <>
      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"><h2 className="text-lg font-semibold">{t("Local Services")}</h2><p className="mt-1 text-xs text-raven-muted">{t("Expected states are stored in this desktop profile; unconfigured services remain neutral.")}</p><div className="mt-3 max-h-96 overflow-auto"><table className="w-full min-w-[1000px] text-left text-xs"><thead><tr><th>{t("Service")}</th><th>{t("State")}</th><th>{t("Start type")}</th><th>PID</th><th>{t("Expected state")}</th><th>{t("Health")}</th><th>{t("Reason")}</th><th>{t("Actions")}</th></tr></thead><tbody>{shownServices.map(({ service: item, assessment }) => <tr key={item.name} className="border-t border-raven-border"><td className="py-2 pr-2"><strong>{item.displayName}</strong><br />{item.name}{item.description ? <span className="block max-w-md text-raven-muted">{item.description}</span> : null}</td><td>{t(item.state)}</td><td>{item.startType ? t(item.startType) : "—"}</td><td>{item.pid ?? "—"}</td><td><select aria-label={`${t("Expected state")} ${item.displayName}`} value={expectations[item.name]?.expectedState ?? ""} onChange={(event) => setExpectation(item.name, event.target.value ? { expectedState: event.target.value as "running" | "stopped", required: expectations[item.name]?.required ?? false, criticality: expectations[item.name]?.criticality ?? "medium", notes: expectations[item.name]?.notes ?? "" } : undefined)} className="rounded border border-raven-border bg-raven-panelSoft p-1"><option value="">{t("Unconfigured")}</option><option value="running">{t("running")}</option><option value="stopped">{t("stopped")}</option></select>{expectations[item.name] ? <><label className="mt-1 block"><input type="checkbox" checked={expectations[item.name].required} onChange={(event) => setExpectation(item.name, { ...expectations[item.name], required: event.target.checked })} /> {t("Required")}</label><select aria-label={`${t("Criticality")} ${item.displayName}`} value={expectations[item.name].criticality} onChange={(event) => setExpectation(item.name, { ...expectations[item.name], criticality: event.target.value as LocalServiceExpectation["criticality"] })} className="mt-1 rounded border border-raven-border bg-raven-panelSoft p-1">{["low", "medium", "high", "critical"].map((value) => <option key={value} value={value}>{t(value)}</option>)}</select><input aria-label={`${t("Notes")} ${item.displayName}`} value={expectations[item.name].notes} maxLength={200} onChange={(event) => setExpectation(item.name, { ...expectations[item.name], notes: event.target.value })} placeholder={t("Notes")} className="mt-1 w-32 rounded border border-raven-border bg-raven-panelSoft p-1" /></> : null}</td><td><HealthBadge health={assessment.health} reason={assessment.reason} t={t} /></td><td className="max-w-xs text-raven-muted">{assessment.reason}</td><td>{item.actionAvailable ? <span className="flex gap-1">{(["start", "stop", "restart"] as const).map((action) => <button key={action} type="button" onClick={() => void serviceAction(item, action)} disabled={(action === "start" && item.state !== "stopped") || (action === "stop" && item.state !== "running") || (action === "restart" && item.state !== "running")} className="rounded border border-raven-border px-2 py-1 disabled:opacity-40">{t(action)}</button>)}</span> : <span title={item.actionReason}>{t("Protected")}</span>}</td></tr>)}</tbody></table></div></section>
      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"><div className="flex flex-wrap items-center gap-3"><h2 className="text-lg font-semibold">{t("Processes")}</h2><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("Search processes")} className="rounded border border-raven-border bg-raven-panelSoft px-2 py-1 text-sm" /><select value={sort} onChange={(event) => setSort(event.target.value as typeof sort)} className="rounded border border-raven-border bg-raven-panelSoft px-2 py-1 text-sm"><option value="cpu">CPU</option><option value="memory">{t("Memory")}</option><option value="pid">PID</option></select></div><div className="mt-3 max-h-[32rem] overflow-auto"><table className="w-full text-left text-xs"><thead><tr><th>{t("Process")}</th><th>PID</th><th>CPU</th><th>{t("Memory")}</th><th>{t("Started")}</th><th>{t("Runtime")}</th><th>{t("Action")}</th></tr></thead><tbody>{processes.map((item) => <tr key={`${item.pid}-${item.startedAtUnix}`} className="border-t border-raven-border"><td className="py-2">{item.name}</td><td>{item.pid}</td><td>{item.cpuPercent.toFixed(1)}%</td><td>{bytes(item.memoryBytes)}</td><td>{new Date(item.startedAtUnix * 1000).toLocaleString()}</td><td>{elapsed(item.runtimeSeconds)}</td><td>{item.actionAvailable ? <button type="button" className="rounded border border-rose-500/40 px-2 py-1 text-rose-200" onClick={() => void terminate(item)}>{t("Terminate")}</button> : <span title={item.actionReason}>{t("Protected")}</span>}</td></tr>)}</tbody></table></div></section>
    </> : null}
  </div>;
}

function Summary({ label, value }: { label: string; value: string | number }) { return <div className="rounded border border-raven-border p-3"><p className="text-xs text-raven-muted">{label}</p><p className="mt-1 font-medium">{value}</p></div>; }
function HealthBadge({ health, reason, t }: { health: ServiceHealth; reason: string; t: (key: string) => string }) { return <span role="status" aria-label={`${t(health)}: ${reason}`} className={`inline-flex rounded-full border px-2 py-0.5 text-xs ${serviceHealthTone[health]}`}>{serviceHealthIcon[health]} {t(health)}</span>; }
