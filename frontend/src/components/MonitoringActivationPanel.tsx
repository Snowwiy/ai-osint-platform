import { CheckCircle2, Clipboard, Info, ShieldAlert } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { getMonitoringActivation } from "../lib/api";
import { safeArray, safeString } from "../lib/safe";
import { useI18n } from "../lib/i18n";
import { ErrorBlock, LoadingBlock } from "./StateBlock";
import { LanBootstrapPanel } from "./LanBootstrapPanel";

export function MonitoringActivationPanel(): JSX.Element {
  const { t } = useI18n();
  const activation = useQuery({
    queryKey: ["monitoring-activation"],
    queryFn: getMonitoringActivation,
    retry: 1,
  });
  if (activation.isLoading) return <LoadingBlock label="Loading local activation status" />;
  if (activation.error) return <ErrorBlock message="Local activation guidance is temporarily unavailable." onRetry={() => void activation.refetch()} />;
  const data = activation.data;
  if (!data) return <ErrorBlock message="Local activation guidance is temporarily unavailable." />;
  return (
    <div className="min-w-0 space-y-5">
      <LanBootstrapPanel />
      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div><h2 className="font-semibold">Local monitoring activation</h2><p className="mt-1 text-sm text-raven-muted">Read-only guidance for this local Docker environment. The UI never edits <code>.env</code>.</p></div>
          <div className="flex flex-wrap gap-2"><State enabled={data.auto_refresh_enabled} label={t("Auto refresh")} /><State enabled={data.server_host_metrics_enabled} label={t("Server host metrics")} /><State enabled={data.lan_monitoring_enabled} label={t("LAN monitoring")} /><State enabled={data.service_check_enabled} label={t("TCP service checks")} /></div>
        </div>
        <p className="mt-3 text-sm text-raven-muted">Allowed private ranges: {safeArray(data.allowed_cidrs).join(", ") || "none"}</p>
        <p className="mt-1 text-sm text-raven-muted">{t("Gateway hint")}: {safeString(data.gateway_hint, "unavailable")}</p>
        <p className="mt-1 text-sm text-raven-muted">Configured TCP ports: {safeArray(data.service_ports).join(", ") || "none"}</p>
        <p className="mt-1 text-sm text-raven-muted">{t("Auto refresh")}: {data.auto_refresh_seconds}s · {t("LAN discovery")}: {data.lan_auto_discovery_on_start ? t("Enabled by configuration") : t("Disabled by configuration")} ({data.lan_auto_discovery_interval_seconds}s) · {t("Service checks")}: {data.lan_auto_service_check_on_start ? t("Enabled by configuration") : t("Disabled by configuration")} ({data.lan_auto_service_check_interval_seconds}s)</p>
        <p className="mt-1 text-sm text-raven-muted">{t("Server host metrics")}: {data.server_host_metrics_interval_seconds}s · {t("LAN endpoint agents")}: {data.lan_endpoint_agent_interval_seconds}s · {t("Posture recompute")}: {data.posture_recompute_interval_seconds}s</p>
        {!data.lan_monitoring_enabled ? <Notice text={t("Monitoring ready, LAN discovery disabled by configuration.")} informational /> : null}
        {data.discovery_disabled_reason ? <Notice text={data.discovery_disabled_reason} informational /> : null}
        {data.service_check_disabled_reason ? <Notice text={data.service_check_disabled_reason} informational /> : null}
        <div className="mt-3 grid gap-2 md:grid-cols-2"><Notice text={data.docker_limitation} /><Notice text={data.optional_telemetry_note} /></div>
      </section>

      <section className="grid min-w-0 gap-4 lg:grid-cols-2">
        <CommandCard title="Local .env lines" lines={safeArray(data.env_lines)} note="Review the private CIDR and ports before saving locally. No token or secret belongs in these lines." />
        <CommandCard title="Restart and verify" lines={safeArray(data.restart_commands)} note="Run from the repository root after editing .env locally." />
      </section>

      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <div className="flex items-start gap-2"><ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-200" /><div><h3 className="font-medium">Windows firewall</h3><p className="mt-1 text-sm text-raven-muted">{safeString(data.windows_firewall_note)}</p><p className="mt-1 text-xs text-amber-100">Do not expose port 8000 publicly. Scope any inbound rule to the approved private CIDR only.</p></div></div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <Steps title="Agent setup" items={safeArray(data.agent_setup_steps)} />
        <Steps title="Token enrollment" items={safeArray(data.token_enrollment_steps)} />
      </section>
    </div>
  );
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
