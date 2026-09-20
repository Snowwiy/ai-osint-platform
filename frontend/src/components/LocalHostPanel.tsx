import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { getAccessToken } from "../lib/api";
import { useI18n } from "../lib/i18n";

type Process = { pid: number; name: string; cpuPercent: number; memoryBytes: number; startedAtUnix: number; creationTicks: string | null; runtimeSeconds: number; actionAvailable: boolean; actionReason: string };
type Service = { name: string; displayName: string; state: string; startType: string | null; pid: number | null; description: string | null; actionAvailable: boolean; actionReason: string };
type Inventory = { available: boolean; processes: Process[]; services: Service[]; detail: string };
type Result = { success: boolean; previousState: string; resultingState: string; message: string };
type Core = { invoke: (command: string, args?: Record<string, unknown>) => Promise<unknown> };

function nativeCore(): Core | null {
  try {
    const own = (window as Window & { __TAURI__?: { core?: Core } }).__TAURI__?.core;
    const parent = window.parent !== window ? (window.parent as Window & { __TAURI__?: { core?: Core } }).__TAURI__?.core : undefined;
    return own ?? parent ?? null;
  } catch { return null; }
}

const bytes = (value: number) => `${(value / 1024 / 1024).toFixed(1)} MB`;
const elapsed = (value: number) => value < 60 ? `${value}s` : value < 3600 ? `${Math.round(value / 60)}m` : `${Math.round(value / 3600)}h`;

export function LocalHostPanel({ platformServices, serverHostConnected }: { platformServices: { key: string; label: string; status: string; detail: string }[]; serverHostConnected: boolean }): JSX.Element {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"cpu" | "memory" | "pid">("cpu");
  const [refreshSeconds, setRefreshSeconds] = useState(15);
  const [feedback, setFeedback] = useState("");
  const core = nativeCore();
  const token = getAccessToken();
  const inventory = useQuery({
    queryKey: ["local-host-inventory"],
    queryFn: async () => core?.invoke("get_local_host_inventory", { token }) as Promise<Inventory>,
    enabled: Boolean(core && token), refetchInterval: refreshSeconds * 1000, retry: false,
  });
  const snapshot = useQuery({
    queryKey: ["local-host-snapshot"],
    queryFn: async () => core?.invoke("probe_local_services") as Promise<{ dockerAvailability: string; frontendMode: string; backend: { healthy: boolean }; readiness: { healthy: boolean }; dockerServicesStatus: string | null }>,
    enabled: Boolean(core), refetchInterval: refreshSeconds * 1000, retry: false,
  });
  const processes = useMemo(() => {
    const items = (inventory.data?.processes ?? []).filter((item) => `${item.name} ${item.pid}`.toLowerCase().includes(search.toLowerCase()));
    return items.sort((a, b) => sort === "pid" ? a.pid - b.pid : sort === "memory" ? b.memoryBytes - a.memoryBytes : b.cpuPercent - a.cpuPercent);
  }, [inventory.data, search, sort]);
  const topCpu = [...(inventory.data?.processes ?? [])].sort((a, b) => b.cpuPercent - a.cpuPercent)[0];
  const topRam = [...(inventory.data?.processes ?? [])].sort((a, b) => b.memoryBytes - a.memoryBytes)[0];
  const desktopProcess = inventory.data?.processes.find((item) => item.name.toLowerCase().startsWith("raventech-osint-desktop"));

  async function terminate(item: Process) {
    if (!core || !token) return;
    const target = `${item.name} (${item.pid})`;
    if (!window.confirm(`${t("Terminate local process")}: ${target}?`)) return;
    try {
      const result = await core.invoke("terminate_local_process", { token, pid: item.pid, name: item.name, creationTicks: item.creationTicks, confirmation: target }) as Result;
      setFeedback(`${target}: ${result.previousState} → ${result.resultingState}`);
    } catch (error) { setFeedback(String(error)); }
    await inventory.refetch();
  }

  async function serviceAction(item: Service, action: "start" | "stop" | "restart") {
    if (!core || !token) return;
    const target = `${item.displayName} (${item.name})`;
    if (!window.confirm(`${t(action)} ${t("local Windows service")}: ${target}?`)) return;
    try {
      const result = await core.invoke("control_local_service", { token, name: item.name, displayName: item.displayName, action, confirmation: target }) as Result;
      setFeedback(`${target}: ${result.previousState} → ${result.resultingState}`);
    } catch (error) { setFeedback(String(error)); }
    await inventory.refetch();
  }

  return <div className="space-y-5">
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">{t("Local host overview")}</h2><label className="text-xs text-raven-muted">{t("Refresh interval")} <select value={refreshSeconds} onChange={(event) => setRefreshSeconds(Number(event.target.value))} className="ml-2 rounded border border-raven-border bg-raven-panelSoft p-1"><option value={5}>5s</option><option value={15}>15s</option><option value={30}>30s</option></select></label></div>
      {!core ? <p className="mt-2 text-sm text-raven-muted">{t("Local host controls require the desktop app.")}</p> : !token ? <p className="mt-2 text-sm text-raven-muted">{t("Admin sign-in required.")}</p> : inventory.error ? <p className="mt-2 text-sm text-amber-100">{t("Admin authorization or local inventory unavailable.")}</p> : null}
      {inventory.data ? <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Summary label={t("Services")} value={inventory.data.services.length} /><Summary label={t("Running services")} value={inventory.data.services.filter((item) => item.state === "running").length} /><Summary label={t("Processes")} value={inventory.data.processes.length} /><Summary label={t("Highest CPU process")} value={topCpu ? `${topCpu.name} ${topCpu.cpuPercent.toFixed(1)}%` : t("Unavailable")} /><Summary label={t("Highest RAM process")} value={topRam ? `${topRam.name} ${bytes(topRam.memoryBytes)}` : t("Unavailable")} /></div> : null}
      {inventory.data ? <p className="mt-2 text-xs text-raven-muted">{inventory.data.detail}</p> : null}
      {feedback ? <p role="status" className="mt-3 rounded border border-raven-border p-2 text-sm">{feedback}</p> : null}
      <p className="mt-2 text-xs text-raven-muted">{t("Local desktop only. No remote service or process actions.")}</p>
    </section>
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"><h2 className="text-lg font-semibold">{t("RavenTech Operations")}</h2><div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
      <Summary label="RavenTech Desktop" value={desktopProcess ? `${t("running")} · PID ${desktopProcess.pid} · ${bytes(desktopProcess.memoryBytes)} · ${elapsed(desktopProcess.runtimeSeconds)}` : core ? t("running") : t("unavailable")} />
      <Summary label={t("Backend")} value={snapshot.data?.backend.healthy ? t("healthy") : t("unavailable")} />
      <Summary label="PostgreSQL / Redis / Celery" value={snapshot.data?.dockerServicesStatus ?? t("unavailable")} />
      <Summary label={t("Frontend mode")} value={snapshot.data?.frontendMode ?? t("unavailable")} />
      <Summary label="ServerHost agent" value={serverHostConnected ? t("Connected") : t("Unavailable")} />
      <Summary label="Docker Desktop" value={snapshot.data?.dockerAvailability ?? t("unavailable")} />
    </div><h3 className="mt-4 font-medium">{t("Docker containers")}</h3><div className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">{platformServices.filter((item) => ["backend", "database", "redis", "worker"].includes(item.key)).map((item) => <Summary key={item.key} label={item.label} value={item.status} />)}</div><p className="mt-2 text-xs text-raven-muted">{t("Docker restarts use approved RavenTech platform controls; ServerHost restarts are manual; the desktop cannot restart itself during an action.")}</p></section>
    {inventory.data?.available ? <>
      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"><h2 className="text-lg font-semibold">{t("Windows Services")}</h2><div className="mt-3 max-h-96 overflow-auto"><table className="w-full text-left text-xs"><thead><tr><th>{t("Service")}</th><th>{t("State")}</th><th>{t("Start type")}</th><th>PID</th><th>{t("Actions")}</th></tr></thead><tbody>{inventory.data.services.map((item) => <tr key={item.name} className="border-t border-raven-border"><td className="py-2 pr-2"><strong>{item.displayName}</strong><br />{item.name}{item.description ? <span className="block max-w-md text-raven-muted">{item.description}</span> : null}</td><td>{t(item.state)}</td><td>{item.startType ? t(item.startType) : "—"}</td><td>{item.pid ?? "—"}</td><td>{item.actionAvailable ? <span className="flex gap-1">{(["start", "stop", "restart"] as const).map((action) => <button key={action} type="button" onClick={() => void serviceAction(item, action)} disabled={(action === "start" && item.state !== "stopped") || (action === "stop" && item.state !== "running") || (action === "restart" && item.state !== "running")} className="rounded border border-raven-border px-2 py-1 disabled:opacity-40">{t(action)}</button>)}</span> : <span title={item.actionReason}>{t("Protected")}</span>}</td></tr>)}</tbody></table></div></section>
      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"><div className="flex flex-wrap items-center gap-3"><h2 className="text-lg font-semibold">{t("Processes")}</h2><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("Search processes")} className="rounded border border-raven-border bg-raven-panelSoft px-2 py-1 text-sm" /><select value={sort} onChange={(event) => setSort(event.target.value as typeof sort)} className="rounded border border-raven-border bg-raven-panelSoft px-2 py-1 text-sm"><option value="cpu">CPU</option><option value="memory">{t("Memory")}</option><option value="pid">PID</option></select></div><div className="mt-3 max-h-[32rem] overflow-auto"><table className="w-full text-left text-xs"><thead><tr><th>{t("Process")}</th><th>PID</th><th>CPU</th><th>{t("Memory")}</th><th>{t("Started")}</th><th>{t("Runtime")}</th><th>{t("Action")}</th></tr></thead><tbody>{processes.map((item) => <tr key={`${item.pid}-${item.startedAtUnix}`} className="border-t border-raven-border"><td className="py-2">{item.name}</td><td>{item.pid}</td><td>{item.cpuPercent.toFixed(1)}%</td><td>{bytes(item.memoryBytes)}</td><td>{new Date(item.startedAtUnix * 1000).toLocaleString()}</td><td>{elapsed(item.runtimeSeconds)}</td><td>{item.actionAvailable ? <button type="button" className="rounded border border-rose-500/40 px-2 py-1 text-rose-200" onClick={() => void terminate(item)}>{t("Terminate")}</button> : <span title={item.actionReason}>{t("Protected")}</span>}</td></tr>)}</tbody></table></div></section>
    </> : null}
  </div>;
}

function Summary({ label, value }: { label: string; value: string | number }) { return <div className="rounded border border-raven-border p-3"><p className="text-xs text-raven-muted">{label}</p><p className="mt-1 font-medium">{value}</p></div>; }
