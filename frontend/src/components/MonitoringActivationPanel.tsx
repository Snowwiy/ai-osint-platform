import { CheckCircle2, Clipboard, Info, ShieldAlert } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { getMonitoringActivation } from "../lib/api";
import { safeArray, safeString } from "../lib/safe";
import { useI18n } from "../lib/i18n";
import { ErrorBlock, LoadingBlock } from "./StateBlock";
import { LanBootstrapPanel } from "./LanBootstrapPanel";

export function MonitoringActivationPanel(): JSX.Element {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [desktopAction, setDesktopAction] = useState<DesktopActionState | null>(null);
  const [authorizedCidrs, setAuthorizedCidrs] = useState("");
  const [gatewayHint, setGatewayHint] = useState("");
  const [servicePorts, setServicePorts] = useState("");
  const activation = useQuery({
    queryKey: ["monitoring-activation"],
    queryFn: getMonitoringActivation,
    retry: 1,
  });
  const data = activation.data;
  useEffect(() => {
    if (!data) return;
    setAuthorizedCidrs(data.allowed_cidrs.join(", "));
    setGatewayHint(data.gateway_hint);
    setServicePorts(data.service_ports.join(", "));
  }, [data?.allowed_cidrs, data?.gateway_hint, data?.service_ports]);
  if (activation.isLoading) return <LoadingBlock label="Loading local activation status" />;
  if (activation.error) return <ErrorBlock message="Local activation guidance is temporarily unavailable." onRetry={() => void activation.refetch()} />;
  if (!data) return <ErrorBlock message="Local activation guidance is temporarily unavailable." />;
  const applyProfile = async (): Promise<void> => {
    const cidrs = authorizedCidrs.split(",").map((value) => value.trim()).filter(Boolean);
    const ports = servicePorts.split(",").map((value) => Number(value.trim()));
    if (!cidrs.length || !gatewayHint.trim() || !ports.length || ports.some((port) => !Number.isInteger(port) || port < 1 || port > 65535)) {
      setDesktopAction({ success: false, message: t("Review the private CIDR, gateway, and TCP port values."), output: "", appliedAt: null, restartRequired: false });
      return;
    }
    if (!window.confirm(t("Apply the reviewed private LAN settings after creating a timestamped configuration backup?"))) return;
    const invoke = desktopInvoke();
    if (!invoke) {
      const lines = safeArray(data.env_lines).map((line) => line.startsWith("LAN_ALLOWED_CIDRS=") ? `LAN_ALLOWED_CIDRS=${cidrs.join(",")}` : line.startsWith("LAN_GATEWAY_HINT=") ? `LAN_GATEWAY_HINT=${gatewayHint.trim()}` : line.startsWith("LAN_SERVICE_CHECK_PORTS=") ? `LAN_SERVICE_CHECK_PORTS=${[...new Set(ports)].sort((a, b) => a - b).join(",")}` : line);
      await navigator.clipboard.writeText(lines.join("\n"));
      setDesktopAction({ success: false, message: t("Desktop execution is unavailable; the reviewed settings were copied only."), output: "", appliedAt: null, restartRequired: false });
      return;
    }
    let result: DesktopLauncherResult;
    try {
      result = await invoke("apply_lan_monitoring_config", {
        confirmed: true,
        profile: { allowedCidrs: cidrs, gatewayHint: gatewayHint.trim(), servicePorts: [...new Set(ports)].sort((a, b) => a - b) },
      });
    } catch {
      setDesktopAction({ success: false, message: t("Native configuration could not be safely updated. Check local permissions and try again."), output: "", appliedAt: null, restartRequired: false });
      return;
    }
    setDesktopAction({ success: result.success, message: result.message, output: result.output, appliedAt: result.success ? new Date() : null, restartRequired: result.success });
  };
  const restartAndVerify = async (): Promise<void> => {
    if (!window.confirm(t("Restart the approved local services and verify health, readiness, and RC6?"))) return;
    const invoke = desktopInvoke();
    if (!invoke) {
      setDesktopAction((current) => current ? { ...current, message: t("Desktop execution is unavailable; use the copy-only restart command.") } : current);
      return;
    }
    const result = await invoke("restart_platform");
    setDesktopAction((current) => ({ success: result.success, message: result.message, output: result.output, appliedAt: current?.appliedAt ?? null, restartRequired: !result.success }));
    await Promise.all([activation.refetch(), queryClient.invalidateQueries({ queryKey: ["monitoring-startup"] }), queryClient.invalidateQueries({ queryKey: ["monitoring-overview"] })]);
  };
  return (
    <div className="min-w-0 space-y-5">
      <LanBootstrapPanel />
      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><h2 className="font-semibold">{t("Local monitoring activation")}</h2><p className="mt-1 text-sm text-raven-muted">{t("The desktop may apply only the reviewed non-secret profile after confirmation and backup; browser mode remains copy-only.")}</p></div>
          <div className="flex flex-wrap gap-2"><State enabled={data.auto_refresh_enabled} label={t("Auto refresh")} /><State enabled={data.server_host_metrics_enabled} label={t("Server host metrics")} /><State enabled={data.lan_monitoring_enabled} label={t("LAN monitoring")} /><State enabled={data.service_check_enabled} label={t("TCP service checks")} /><State enabled={data.auto_registration_enabled} label={t("Automatic asset registration")} /><State enabled={data.host_neighbor_collection_enabled} label={t("Read-only host neighbors")} /></div>
        </div>
        <p className="mt-3 text-sm text-raven-muted">Allowed private ranges: {safeArray(data.allowed_cidrs).join(", ") || "none"}</p>
        <p className="mt-1 text-sm text-raven-muted">{t("Gateway hint")}: {safeString(data.gateway_hint, "unavailable")}</p>
        <p className="mt-1 text-sm text-raven-muted">Configured TCP ports: {safeArray(data.service_ports).join(", ") || "none"}</p>
        <p className="mt-1 text-sm text-raven-muted">{t("Auto refresh")}: {data.auto_refresh_seconds}s · {t("LAN discovery")}: {data.lan_auto_discovery_on_start ? t("Enabled by configuration") : t("Disabled by configuration")} ({data.lan_auto_discovery_interval_seconds}s) · {t("Service checks")}: {data.lan_auto_service_check_on_start ? t("Enabled by configuration") : t("Disabled by configuration")} ({data.lan_auto_service_check_interval_seconds}s)</p>
        <p className="mt-1 text-sm text-raven-muted">{t("Server host metrics")}: {data.server_host_metrics_interval_seconds}s · {t("LAN endpoint agents")}: {data.lan_endpoint_agent_interval_seconds}s · {t("Posture recompute")}: {data.posture_recompute_interval_seconds}s</p>
        <p className="mt-1 text-sm text-raven-muted">{t("Config source")}: {t(data.configuration_source === "native_desktop" ? "Native desktop configuration" : data.configuration_source === "docker_compose" ? "Docker Compose configuration" : "Environment configuration")}</p>
        {!data.lan_monitoring_enabled ? <Notice text={t("Monitoring ready, LAN discovery disabled by configuration.")} informational /> : null}
        {data.discovery_disabled_reason ? <Notice text={data.discovery_disabled_reason} informational /> : null}
        {data.service_check_disabled_reason ? <Notice text={data.service_check_disabled_reason} informational /> : null}
        <div className="mt-3 grid gap-2 md:grid-cols-2">{data.runtime_profile === "desktop" ? <Notice text={`${t("Provider source")}: ${t(data.provider_source === "native_host_provider" ? "Native host provider" : data.provider_source)} · ${t(data.provider_status)}`} informational /> : <Notice text={data.docker_limitation} />}<Notice text={data.optional_telemetry_note} informational /></div>
        <p className="mt-3 rounded border border-cyan-300/20 bg-cyan-400/5 p-3 text-xs text-cyan-100">{t(data.runtime_profile === "desktop" ? "The native host provider collects local interfaces, routes, and neighbor observations without a manually launched agent." : data.host_neighbor_guidance)}</p>
      </section>

      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-medium">{t("Controlled LAN activation")}</h3><p className="mt-1 max-w-3xl text-sm text-raven-muted">{t("Review the private ranges, gateway, and configured TCP ports. Existing secrets and unknown settings are preserved and never displayed.")}</p></div><div className="flex flex-wrap gap-2"><button type="button" onClick={() => void applyProfile()} className="rounded border border-raven-border px-3 py-2 text-sm">{t("Apply reviewed LAN settings")}</button><button type="button" disabled={!desktopAction?.restartRequired} onClick={() => void restartAndVerify()} className="rounded bg-raven-violet px-3 py-2 text-sm text-white disabled:opacity-50">{t("Restart and verify")}</button></div></div>
        <div className="mt-3 grid gap-3 md:grid-cols-3"><label className="text-xs text-raven-muted">{t("Authorized CIDRs")}<input value={authorizedCidrs} onChange={(event) => setAuthorizedCidrs(event.target.value)} maxLength={800} className="mt-1 w-full rounded border border-raven-border bg-raven-panelSoft px-2 py-2 text-sm" aria-label={t("Authorized CIDRs")} /></label><label className="text-xs text-raven-muted">{t("Gateway hint")}<input value={gatewayHint} onChange={(event) => setGatewayHint(event.target.value)} maxLength={45} className="mt-1 w-full rounded border border-raven-border bg-raven-panelSoft px-2 py-2 text-sm" aria-label={t("Gateway hint")} /></label><label className="text-xs text-raven-muted">{t("Configured TCP ports")}<input value={servicePorts} onChange={(event) => setServicePorts(event.target.value)} maxLength={160} className="mt-1 w-full rounded border border-raven-border bg-raven-panelSoft px-2 py-2 text-sm" aria-label={t("Configured TCP ports")} /></label></div>
        <div className="mt-3 grid gap-2 text-xs text-raven-muted sm:grid-cols-3"><p>{t("Last config apply")}: {desktopAction?.appliedAt?.toLocaleString() ?? t("Not available")}</p><p>{t("Backup")}: {desktopAction?.success ? t("Created in native configuration directory") : t("Created only after a successful desktop apply")}</p><p>{t("Restart required")}: {desktopAction?.restartRequired ? t("Yes") : t("No")}</p></div>
        {desktopAction ? <div className={`mt-3 rounded border p-3 text-sm ${desktopAction.success ? "border-emerald-400/30 text-emerald-100" : "border-cyan-300/30 text-cyan-100"}`}><p>{desktopAction.message}</p>{desktopAction.output ? <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-xs text-raven-muted">{desktopAction.output}</pre> : null}</div> : null}
      </section>

      {data.runtime_profile !== "desktop" ? <section className="grid min-w-0 gap-4 lg:grid-cols-2">
        <CommandCard title="Local .env lines" lines={safeArray(data.env_lines)} note="Review the private CIDR and ports before saving locally. No token or secret belongs in these lines." />
        <CommandCard title="Restart and verify" lines={safeArray(data.restart_commands)} note="Run from the repository root after editing .env locally." />
      </section> : null}

      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <div className="flex items-start gap-2"><ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-200" /><div><h3 className="font-medium">Windows firewall</h3><p className="mt-1 text-sm text-raven-muted">{safeString(data.windows_firewall_note)}</p><p className="mt-1 text-xs text-amber-100">Do not expose port 8000 publicly. Scope any inbound rule to the approved private CIDR only.</p></div></div>
      </section>

      {data.runtime_profile !== "desktop" ? <section className="grid gap-4 lg:grid-cols-2">
        <Steps title="Agent setup" items={safeArray(data.agent_setup_steps)} />
        <Steps title="Token enrollment" items={safeArray(data.token_enrollment_steps)} />
      </section> : null}
    </div>
  );
}

interface DesktopLauncherResult { success: boolean; message: string; output: string }
interface DesktopActionState extends DesktopLauncherResult { appliedAt: Date | null; restartRequired: boolean }
type DesktopInvoke = (command: string, args?: Record<string, unknown>) => Promise<DesktopLauncherResult>;

function desktopInvoke(): DesktopInvoke | null {
  try {
    const own = (window as typeof window & { __TAURI__?: { core?: { invoke?: DesktopInvoke } } }).__TAURI__?.core?.invoke;
    const parent = window.parent !== window ? (window.parent as typeof window & { __TAURI__?: { core?: { invoke?: DesktopInvoke } } }).__TAURI__?.core?.invoke : undefined;
    return own ?? parent ?? null;
  } catch {
    return null;
  }
}

function backupName(output?: string): string | null {
  return output?.match(/Backup: (\.env\.backup-[A-Za-z0-9-]+)/)?.[1] ?? null;
}

function State({ enabled, label }: { enabled: boolean; label: string }): JSX.Element {
  const { t } = useI18n();
  return <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs ${enabled ? "border-emerald-400/30 text-emerald-200" : "border-cyan-300/30 text-cyan-100"}`}>{enabled ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Info className="h-3.5 w-3.5" />}{label}: {enabled ? t("enabled") : t("disabled")}</span>;
}

function Notice({ text, informational = false }: { text: string; informational?: boolean }): JSX.Element {
  return <p className={`mt-2 rounded-md border p-3 text-sm ${informational ? "border-cyan-300/20 bg-cyan-400/5 text-cyan-100" : "border-amber-300/20 bg-amber-400/5 text-amber-100"}`}>{text}</p>;
}

function CommandCard({ title, lines, note }: { title: string; lines: string[]; note: string }): JSX.Element {
  const value = lines.join("\n");
  return <section className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4"><div className="flex items-center justify-between gap-2"><h3 className="font-medium">{title}</h3><button type="button" onClick={() => void navigator.clipboard.writeText(value)} className="inline-flex items-center gap-1 rounded border border-raven-border px-2 py-1 text-xs"><Clipboard className="h-3.5 w-3.5" />Copy</button></div><pre className="mt-3 max-w-full overflow-x-auto rounded bg-raven-bg p-3 text-xs text-raven-cyan">{value}</pre><p className="mt-2 text-xs text-raven-muted">{note}</p></section>;
}

function Steps({ title, items }: { title: string; items: string[] }): JSX.Element {
  return <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"><h3 className="font-medium">{title}</h3><ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-raven-muted">{items.map((item) => <li key={item}>{item}</li>)}</ol></section>;
}
