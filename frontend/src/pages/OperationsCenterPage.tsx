import {
  Archive,
  CheckCircle2,
  Database,
  Download,
  FileArchive,
  HardDrive,
  RefreshCw,
  ShieldCheck,
  Upload,
} from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { ToastBanner } from "../components/ToastBanner";
import {
  downloadOperationsBackup,
  downloadOperationsDiagnostics,
  getOperationsEnvironment,
  getOperationsStatus,
  validateRestoreBackup,
} from "../lib/api";
import { safeArray, safeDate, safeNumber, safeString } from "../lib/safe";
import type { FileDownloadResult } from "../lib/api";
import type {
  EnvironmentValidationItem,
  OperationsComponentStatus,
  OperationsStatusResponse,
  RestoreValidationResponse,
  ValidationStatus,
} from "../types";

type ToastState = { kind: "success" | "error"; message: string } | null;

export function OperationsCenterPage(): JSX.Element {
  const [toast, setToast] = useState<ToastState>(null);
  const [downloadKey, setDownloadKey] = useState<string | null>(null);
  const [restoreText, setRestoreText] = useState("");
  const [restoreArchiveBase64, setRestoreArchiveBase64] = useState<string | null>(null);
  const [restoreFileName, setRestoreFileName] = useState("");
  const status = useQuery({
    queryKey: ["operations-status"],
    queryFn: getOperationsStatus,
  });
  const environment = useQuery({
    queryKey: ["operations-environment"],
    queryFn: getOperationsEnvironment,
  });
  const restore = useMutation({
    mutationFn: validateRestoreBackup,
    onSuccess: () => {
      setToast({ kind: "success", message: "Restore dry-run validation completed." });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message:
          error instanceof Error
            ? error.message
            : "Restore validation could not be completed.",
      });
    },
  });

  async function handleDownload(
    kind: "diagnostics" | "backup",
    format: "json" | "zip",
  ): Promise<void> {
    setToast(null);
    const key = `${kind}:${format}`;
    setDownloadKey(key);
    try {
      const download =
        kind === "diagnostics"
          ? await downloadOperationsDiagnostics(format)
          : await downloadOperationsBackup(format);
      triggerDownload(download);
      setToast({
        kind: "success",
        message: `${kind === "diagnostics" ? "Diagnostics" : "Backup"} ${format.toUpperCase()} export ready.`,
      });
    } catch (error) {
      setToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Export failed.",
      });
    } finally {
      setDownloadKey(null);
    }
  }

  async function handleRestoreFile(file: File | null): Promise<void> {
    setRestoreFileName(file?.name ?? "");
    setRestoreArchiveBase64(null);
    setRestoreText("");
    if (!file) {
      return;
    }
    if (file.name.toLowerCase().endsWith(".zip")) {
      setRestoreArchiveBase64(await readFileAsBase64(file));
      return;
    }
    setRestoreText(await file.text());
  }

  function runRestoreValidation(): void {
    setToast(null);
    try {
      const body = restoreArchiveBase64
        ? { dry_run: true, archive_base64: restoreArchiveBase64 }
        : { dry_run: true, backup: JSON.parse(restoreText) as Record<string, unknown> };
      restore.mutate(body);
    } catch {
      setToast({
        kind: "error",
        message: "Backup JSON could not be parsed. Select an exported JSON or ZIP file.",
      });
    }
  }

  const error = status.error ?? environment.error;
  if (status.isLoading || environment.isLoading) {
    return <LoadingBlock label="Loading operations center" />;
  }
  if (error) {
    return <ErrorBlock message={error} />;
  }
  if (!status.data || !environment.data) {
    return (
      <EmptyBlock
        title="Operations data unavailable"
        message="Operational status is not available yet."
        nextStep="Refresh after the backend health endpoint is reachable."
      />
    );
  }

  return (
    <>
      <PageHeader
        title="Operations Center"
        eyebrow="Production readiness"
        actions={
          <button
            type="button"
            onClick={() => {
              void status.refetch();
              void environment.refetch();
            }}
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-muted hover:border-raven-violet hover:text-raven-text"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </button>
        }
      />
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}

      <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <PlatformHealthPanel data={status.data} />
        <ReleasePanel data={status.data} />
      </section>

      <section className="mt-5 grid gap-4 xl:grid-cols-[1fr_1fr]">
        <EnvironmentPanel items={environment.data.items} />
        <StoragePanel data={status.data} />
      </section>

      <section className="mt-5 grid gap-4 xl:grid-cols-[1fr_1fr]">
        <ExportPanel
          title="Diagnostics Package"
          description="Exports health, migrations, feature flags, retention, governance, and report configuration without secrets."
          icon={<FileArchive className="h-5 w-5 text-raven-cyan" aria-hidden="true" />}
          busyKey={downloadKey}
          actionKey="diagnostics"
          onDownload={handleDownload}
        />
        <ExportPanel
          title="Backup Readiness"
          description="Exports investigation, finding, report, template, settings, governance, and knowledge metadata for restore planning."
          icon={<Archive className="h-5 w-5 text-raven-cyan" aria-hidden="true" />}
          busyKey={downloadKey}
          actionKey="backup"
          onDownload={handleDownload}
        />
      </section>

      <section className="mt-5 grid gap-4 xl:grid-cols-[1fr_1fr]">
        <RestorePanel
          fileName={restoreFileName}
          restoreText={restoreText}
          hasArchive={Boolean(restoreArchiveBase64)}
          isPending={restore.isPending}
          result={restore.data}
          onFile={handleRestoreFile}
          onText={setRestoreText}
          onValidate={runRestoreValidation}
        />
        <RecentOperationsPanel events={status.data.recent_operations} />
      </section>
    </>
  );
}

function PlatformHealthPanel({
  data,
}: {
  data: OperationsStatusResponse;
}): JSX.Element {
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Platform Health</h2>
          <p className="mt-1 text-sm text-raven-muted">
            Uptime {formatDuration(data.uptime_seconds)} | generated{" "}
            {safeDate(data.generated_at)?.toLocaleString() ?? "time unavailable"}
          </p>
        </div>
        <StatusPill status={data.status} />
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {Object.entries(data.components ?? {}).map(([name, component]) => (
          <ComponentCard key={name} name={name} component={component} />
        ))}
      </div>
    </section>
  );
}

function ComponentCard({
  name,
  component,
}: {
  name: string;
  component: OperationsComponentStatus;
}): JSX.Element {
  return (
    <div className="min-w-0 rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="capitalize">{name.replace(/_/g, " ")}</p>
        <StatusPill status={component.status} />
      </div>
      {component.detail ? (
        <p className="mt-2 break-words text-xs text-raven-muted">{component.detail}</p>
      ) : null}
      {Object.keys(component.metadata ?? {}).length ? (
        <dl className="mt-2 space-y-1 text-xs text-raven-muted">
          {Object.entries(component.metadata ?? {}).map(([key, value]) => (
            <div key={key} className="flex justify-between gap-3">
              <dt className="capitalize">{key.replace(/_/g, " ")}</dt>
              <dd className="break-all text-right text-raven-text">{String(value)}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}

function ReleasePanel({ data }: { data: OperationsStatusResponse }): JSX.Element {
  const release: Partial<OperationsStatusResponse["release"]> = data.release ?? {};
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-5 w-5 text-raven-cyan" aria-hidden="true" />
        <h2 className="text-lg font-semibold">Release Information</h2>
      </div>
      <dl className="mt-4 space-y-3 text-sm">
        <InfoRow label="App" value={safeString(release.app_name, "RavenTech OSINT")} />
        <InfoRow label="Version" value={safeString(release.version, "unknown")} />
        <InfoRow label="Channel" value={safeString(release.release_channel, "unknown")} />
        <InfoRow label="Build date" value={safeString(release.build_date, "unknown")} />
        <InfoRow label="Git commit" value={safeString(release.git_commit, "unknown")} />
        <InfoRow label="Build" value={safeString(release.build, "unknown")} />
        <InfoRow label="Environment" value={safeString(release.environment, "unknown")} />
        <InfoRow
          label="Migration"
          value={safeString(release.current_migration, "unknown")}
        />
        <InfoRow
          label="Head migration"
          value={safeString(release.head_migration, "unknown")}
        />
        <InfoRow
          label="Migration status"
          value={safeString(release.migration_status, "unknown")}
        />
        <InfoRow label="Database" value={safeString(release.database_version, "unknown")} />
      </dl>
    </section>
  );
}

function EnvironmentPanel({
  items,
}: {
  items: EnvironmentValidationItem[];
}): JSX.Element {
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <h2 className="text-lg font-semibold">Environment Validation</h2>
      <p className="mt-1 text-sm text-raven-muted">
        Values are never displayed. Only configured, missing, or misconfigured status
        is shown.
      </p>
      <div className="mt-4 space-y-3">
        {safeArray(items).map((item) => (
          <div
            key={`${item.scope}-${item.name}`}
            className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-medium">{item.name}</p>
              <ValidationPill status={item.status} />
            </div>
            <p className="mt-1 text-xs uppercase tracking-wide text-raven-muted">
              {item.scope} {item.required ? "| required" : "| optional"}
            </p>
            <p className="mt-2 break-words text-sm text-raven-muted">{item.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function StoragePanel({ data }: { data: OperationsStatusResponse }): JSX.Element {
  const storage = data.storage;
  const storageMetrics: Partial<OperationsStatusResponse["storage"]> = storage ?? {};
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <div className="flex items-center gap-2">
        <Database className="h-5 w-5 text-raven-cyan" aria-hidden="true" />
        <h2 className="text-lg font-semibold">Storage Visibility</h2>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Metric
          label="Investigations"
          value={safeNumber(storageMetrics.investigations_count)}
        />
        <Metric label="Findings" value={safeNumber(storageMetrics.findings_count)} />
        <Metric label="Reports" value={safeNumber(storageMetrics.reports_count)} />
        <Metric label="Templates" value={safeNumber(storageMetrics.templates_count)} />
        <Metric
          label="Audit events"
          value={safeNumber(storageMetrics.audit_events_count)}
        />
        <Metric
          label="Knowledge docs"
          value={safeNumber(storageMetrics.knowledge_documents_count)}
        />
        <Metric
          label="Report storage"
          value={formatBytes(safeNumber(storageMetrics.report_storage_bytes))}
        />
        <Metric
          label="Database size"
          value={formatBytes(safeNumber(storageMetrics.database_size_bytes))}
        />
      </div>
    </section>
  );
}

function ExportPanel({
  title,
  description,
  icon,
  busyKey,
  actionKey,
  onDownload,
}: {
  title: string;
  description: string;
  icon: JSX.Element;
  busyKey: string | null;
  actionKey: "diagnostics" | "backup";
  onDownload: (kind: "diagnostics" | "backup", format: "json" | "zip") => void;
}): JSX.Element {
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <div className="flex items-center gap-2">
        {icon}
        <h2 className="text-lg font-semibold">{title}</h2>
      </div>
      <p className="mt-2 text-sm leading-6 text-raven-muted">{description}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {(["json", "zip"] as const).map((format) => {
          const key = `${actionKey}:${format}`;
          return (
            <button
              key={format}
              type="button"
              onClick={() => onDownload(actionKey, format)}
              disabled={busyKey === key}
              className="inline-flex items-center gap-2 rounded-md bg-raven-violet px-3 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-60"
            >
              <Download className="h-4 w-4" aria-hidden="true" />
              {busyKey === key ? "Preparing" : `Export ${format.toUpperCase()}`}
            </button>
          );
        })}
      </div>
    </section>
  );
}

function RestorePanel({
  fileName,
  restoreText,
  hasArchive,
  isPending,
  result,
  onFile,
  onText,
  onValidate,
}: {
  fileName: string;
  restoreText: string;
  hasArchive: boolean;
  isPending: boolean;
  result: RestoreValidationResponse | undefined;
  onFile: (file: File | null) => void;
  onText: (value: string) => void;
  onValidate: () => void;
}): JSX.Element {
  const canValidate = hasArchive || restoreText.trim().length > 0;
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <div className="flex items-center gap-2">
        <Upload className="h-5 w-5 text-raven-cyan" aria-hidden="true" />
        <h2 className="text-lg font-semibold">Restore Readiness</h2>
      </div>
      <p className="mt-2 text-sm leading-6 text-raven-muted">
        Validate a RavenTech JSON or ZIP backup before any restore planning. Phase 5A
        performs dry-run validation only and never overwrites data.
      </p>
      <label className="mt-4 block text-sm text-raven-muted">
        Backup file
        <input
          type="file"
          accept=".json,.zip,application/json,application/zip"
          onChange={(event) => void onFile(event.target.files?.[0] ?? null)}
          className="mt-2 block w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text file:mr-3 file:rounded file:border-0 file:bg-raven-panelSoft file:px-3 file:py-1.5 file:text-raven-text"
        />
      </label>
      {fileName ? (
        <p className="mt-2 break-all text-xs text-raven-muted">Selected: {fileName}</p>
      ) : null}
      {!hasArchive ? (
        <label className="mt-4 block text-sm text-raven-muted">
          Backup JSON
          <textarea
            value={restoreText}
            onChange={(event) => onText(event.target.value)}
            rows={6}
            placeholder='Paste a RavenTech backup JSON payload here.'
            className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 font-mono text-xs text-raven-text"
          />
        </label>
      ) : null}
      <button
        type="button"
        onClick={onValidate}
        disabled={!canValidate || isPending}
        className="mt-4 inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-muted hover:border-raven-violet hover:text-raven-text disabled:opacity-50"
      >
        <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
        {isPending ? "Validating" : "Validate dry run"}
      </button>
      {result ? <RestoreResult result={result} /> : null}
    </section>
  );
}

function RestoreResult({
  result,
}: {
  result: RestoreValidationResponse;
}): JSX.Element {
  return (
    <div className="mt-4 rounded-md border border-raven-border bg-raven-panelSoft p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-medium">
          {result.valid ? "Backup is valid" : "Backup needs attention"}
        </p>
        <span className={result.valid ? "text-raven-emerald" : "text-amber-100"}>
          {result.compatible ? "Compatible" : "Not compatible"}
        </span>
      </div>
      {Object.keys(result.record_counts ?? {}).length ? (
        <dl className="mt-3 grid gap-2 sm:grid-cols-2">
          {Object.entries(result.record_counts ?? {}).map(([key, value]) => (
            <div key={key} className="flex justify-between gap-3 text-xs">
              <dt className="capitalize text-raven-muted">{key.replace(/_/g, " ")}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {[...safeArray(result.warnings), ...safeArray(result.errors)].length ? (
        <ul className="mt-3 space-y-1 text-xs text-raven-muted">
          {[...safeArray(result.warnings), ...safeArray(result.errors)].map((item) => (
            <li key={item}>- {item}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function RecentOperationsPanel({
  events,
}: {
  events: OperationsStatusResponse["recent_operations"];
}): JSX.Element {
  const safeEvents = safeArray(events);
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <div className="flex items-center gap-2">
        <HardDrive className="h-5 w-5 text-raven-cyan" aria-hidden="true" />
        <h2 className="text-lg font-semibold">Recent Operational Activity</h2>
      </div>
      {safeEvents.length ? (
        <div className="mt-4 space-y-3">
          {safeEvents.map((event) => (
            <div
              key={`${event.action}-${event.created_at}`}
              className="rounded-md border border-raven-border bg-raven-panelSoft p-3 text-sm"
            >
              <p className="font-medium">{event.action.replace(/\./g, " ")}</p>
              <p className="mt-1 text-xs text-raven-muted">
                {event.resource_type ?? "operation"} |{" "}
                {safeDate(event.created_at)?.toLocaleString() ?? "time unavailable"}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4">
          <EmptyBlock
            title="No recent operations"
            message="Governance changes, diagnostics, backup exports, and restore validations will appear here."
          />
        </div>
      )}
    </section>
  );
}

function InfoRow({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="grid gap-1 sm:grid-cols-[150px_minmax(0,1fr)]">
      <dt className="text-raven-muted">{label}</dt>
      <dd className="break-words font-mono text-raven-text">{value || "n/a"}</dd>
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: number | string;
}): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <p className="text-xs uppercase tracking-wide text-raven-muted">{label}</p>
      <p className="mt-1 break-words text-xl font-semibold">{value}</p>
    </div>
  );
}

function StatusPill({ status }: { status: string }): JSX.Element {
  const classes =
    status === "healthy"
      ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-100"
      : status === "degraded"
        ? "border-amber-400/30 bg-amber-500/10 text-amber-100"
        : "border-rose-400/30 bg-rose-500/10 text-rose-100";
  return (
    <span className={["rounded-full border px-2 py-1 text-xs capitalize", classes].join(" ")}>
      {status}
    </span>
  );
}

function ValidationPill({ status }: { status: ValidationStatus }): JSX.Element {
  const classes =
    status === "configured"
      ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-100"
      : status === "missing"
        ? "border-amber-400/30 bg-amber-500/10 text-amber-100"
        : "border-rose-400/30 bg-rose-500/10 text-rose-100";
  return (
    <span className={["rounded-full border px-2 py-1 text-xs capitalize", classes].join(" ")}>
      {status}
    </span>
  );
}

function formatDuration(seconds: number): string {
  const days = Math.floor(seconds / 86_400);
  const hours = Math.floor((seconds % 86_400) / 3_600);
  const minutes = Math.floor((seconds % 3_600) / 60);
  if (days > 0) {
    return `${days}d ${hours}h`;
  }
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
}

function formatBytes(value: number): string {
  if (value < 1024) {
    return `${value} B`;
  }
  const units = ["KB", "MB", "GB", "TB"];
  let size = value / 1024;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

function triggerDownload(download: FileDownloadResult): void {
  if (download.handledExternally || download.blob === null) {
    return;
  }
  const url = window.URL.createObjectURL(
    new Blob([download.blob], { type: download.mimeType }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = download.filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result ?? "");
      resolve(result.includes(",") ? result.split(",")[1] : result);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}
