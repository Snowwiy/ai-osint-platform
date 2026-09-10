import { Check, Clipboard, ExternalLink, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { safeArray, safeNumber, safeString } from "../lib/safe";
import type {
  AgentInventoryResponse,
  MonitoringActivationStatus,
  OperationsStatusResponse,
} from "../types";

type CopyKey = "start" | "stop" | "check" | "backup" | "agent";

const frontendUrl = import.meta.env.VITE_LOCAL_FRONTEND_URL ?? "http://localhost:5173";
const backendUrl = import.meta.env.VITE_LOCAL_BACKEND_URL ?? "http://localhost:8000";
const docsBaseUrl = "https://github.com/Snowwiy/ai-osint-platform/blob/dev";

export function LocalOperatorConsole({
  status,
  activation,
  agents,
  refreshing,
  onRefresh,
}: {
  status: OperationsStatusResponse;
  activation?: MonitoringActivationStatus;
  agents?: AgentInventoryResponse;
  refreshing: boolean;
  onRefresh: () => void;
}): JSX.Element {
  const [copied, setCopied] = useState<CopyKey | null>(null);
  const components = status.components ?? {};
  const coverage = agents?.coverage;
  const commands: Record<CopyKey, string> = {
    start: ".\\scripts\\local\\start_platform.ps1 -OpenFrontend",
    stop: ".\\scripts\\local\\stop_platform.ps1",
    check: ".\\scripts\\local\\check_platform.ps1",
    backup: ".\\scripts\\local\\backup_db.ps1",
    agent: ".\\scripts\\local\\local_monitor_agent.ps1 -Mode LanEndpoint -BackendUrl http://BACKEND_HOST:8000 -IntervalSeconds 30",
  };

  async function copyCommand(key: CopyKey): Promise<void> {
    try {
      await navigator.clipboard.writeText(commands[key]);
      setCopied(key);
      window.setTimeout(() => setCopied((current) => (current === key ? null : current)), 1800);
    } catch {
      setCopied(null);
    }
  }

  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-raven-cyan" aria-hidden="true" />
            <h2 className="text-lg font-semibold">Local Operator Console</h2>
          </div>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-raven-muted">
            Read-only local status and copy-ready operator commands. The browser never executes host commands or changes Docker state.
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={refreshing}
          className="inline-flex shrink-0 items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-muted hover:border-raven-cyan hover:text-raven-text disabled:opacity-50"
          title="Refresh local status"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} aria-hidden="true" />
          {refreshing ? "Refreshing" : "Refresh status"}
        </button>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatusCard label="Backend health" value={statusLabel(status.status)} />
        <StatusCard label="Readiness" value={statusLabel(components.migrations?.status ?? status.status)} />
        <StatusCard label="Database" value={statusLabel(components.database?.status)} />
        <StatusCard label="Redis / worker" value={`${statusLabel(components.redis?.status)} / ${statusLabel(components.worker?.status)}`} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="min-w-0 rounded-md border border-raven-border bg-raven-panelSoft p-4">
          <h3 className="font-medium">Local mode</h3>
          <dl className="mt-3 space-y-2 text-sm">
            <InfoRow label="Release" value={safeString(status.release?.version, "unknown")} />
            <InfoRow label="Frontend URL" value={frontendUrl} link={frontendUrl} />
            <InfoRow label="Backend URL" value={backendUrl} link={backendUrl} />
            <InfoRow label="LAN monitoring" value={activation ? (activation.lan_monitoring_enabled ? "enabled" : "disabled") : "unavailable"} />
            <InfoRow label="TCP service checks" value={activation ? (activation.service_check_enabled ? "enabled" : "disabled") : "unavailable"} />
            <InfoRow label="Allowed CIDRs" value={safeArray(activation?.allowed_cidrs).join(", ") || "not available"} />
            <InfoRow label="Configured ports" value={safeArray(activation?.service_ports).join(", ") || "not available"} />
          </dl>
          {activation?.discovery_disabled_reason ? <p className="mt-3 break-words rounded border border-amber-300/20 bg-amber-400/5 p-2 text-xs text-amber-100">{activation.discovery_disabled_reason}</p> : null}
          {activation?.service_check_disabled_reason ? <p className="mt-2 break-words rounded border border-amber-300/20 bg-amber-400/5 p-2 text-xs text-amber-100">{activation.service_check_disabled_reason}</p> : null}
          <p className="mt-3 text-xs text-raven-muted">Database, Redis, and worker values are status-only; connection strings and secrets are never returned.</p>
        </div>

        <div className="min-w-0 rounded-md border border-raven-border bg-raven-panelSoft p-4">
          <h3 className="font-medium">Agent status summary</h3>
          {coverage ? (
            <div className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
              <Summary label="LAN assets" value={safeNumber(coverage.total_lan_assets)} />
              <Summary label="Fresh agents" value={safeNumber(coverage.monitored_by_agent)} />
              <Summary label="Missing agents" value={safeNumber(coverage.missing_agent)} />
              <Summary label="Stale agents" value={safeNumber(coverage.stale_agents)} />
              <Summary label="Unauthorized" value={safeNumber(coverage.unauthorized_assets)} />
              <Summary label="Critical gaps" value={safeNumber(coverage.critical_assets_without_telemetry)} />
            </div>
          ) : <p className="mt-3 text-sm text-raven-muted">Agent inventory is temporarily unavailable. Refresh after the backend is ready.</p>}
          <p className="mt-3 text-xs leading-5 text-raven-muted">Agents are optional, manually started, and limited to bounded telemetry. No persistence, shell, credentials, files, or remote commands are collected.</p>
        </div>
      </div>

      <div className="mt-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-medium">Local operator commands</h3>
          <span className="text-xs text-raven-muted">Copy only; run manually in PowerShell from the repository root.</span>
        </div>
        <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-5">
          {(["start", "stop", "check", "backup", "agent"] as CopyKey[]).map((key) => (
            <div key={key} className="min-w-0 rounded-md border border-raven-border bg-raven-bg p-2">
              <p className="text-xs capitalize text-raven-muted">{key === "agent" ? "Agent" : key}</p>
              <code className="mt-1 block min-w-0 overflow-x-auto whitespace-nowrap text-[11px] text-raven-cyan">{commands[key]}</code>
              <button type="button" onClick={() => void copyCommand(key)} className="mt-2 inline-flex items-center gap-1 rounded border border-raven-border px-2 py-1 text-xs text-raven-muted hover:text-raven-text" title={`Copy ${key} command`}>
                {copied === key ? <Check className="h-3.5 w-3.5 text-emerald-200" aria-hidden="true" /> : <Clipboard className="h-3.5 w-3.5" aria-hidden="true" />}
                {copied === key ? "Copied" : "Copy"}
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-3 text-xs text-raven-muted">
        <a className="inline-flex items-center gap-1 hover:text-raven-cyan" href={`${docsBaseUrl}/LOCAL_BACKUP_RESTORE.md`} target="_blank" rel="noreferrer">
          Backup and restore guide <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
        </a>
        <a className="inline-flex items-center gap-1 hover:text-raven-cyan" href={`${docsBaseUrl}/LOCAL_HEALTH_REPAIR.md`} target="_blank" rel="noreferrer">
          Health repair guide <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
        </a>
      </div>
    </section>
  );
}

function StatusCard({ label, value }: { label: string; value: string }): JSX.Element {
  return <div className="min-w-0 rounded-md border border-raven-border bg-raven-panelSoft p-3"><p className="text-xs uppercase tracking-wide text-raven-muted">{label}</p><p className="mt-1 truncate text-sm font-semibold capitalize">{value}</p></div>;
}

function Summary({ label, value }: { label: string; value: number }): JSX.Element {
  return <div className="rounded border border-raven-border bg-raven-bg p-2"><p className="text-[11px] text-raven-muted">{label}</p><p className="mt-1 text-lg font-semibold">{value}</p></div>;
}

function InfoRow({ label, value, link }: { label: string; value: string; link?: string }): JSX.Element {
  return <div className="grid min-w-0 gap-1 sm:grid-cols-[130px_minmax(0,1fr)]"><dt className="text-raven-muted">{label}</dt><dd className="min-w-0 break-words font-mono text-raven-text">{link ? <a className="break-all hover:text-raven-cyan" href={link} target="_blank" rel="noreferrer">{value}</a> : value}</dd></div>;
}

function statusLabel(value: unknown): string {
  return typeof value === "string" && value.trim() ? value.replace(/_/g, " ") : "unavailable";
}
