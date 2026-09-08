import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  Eye,
  SearchCheck,
  ShieldAlert,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { ToastBanner } from "../components/ToastBanner";
import {
  archiveStaleNotifications,
  getDataQualityOverview,
  listDataQualityIssues,
  runDataQualityScan,
  runMaintenanceDryRun,
  updateDataQualityIssueStatus,
} from "../lib/api";
import { safeArray, safeDate, safeNumber, safeString } from "../lib/safe";
import type {
  DataQualityEntityType,
  DataQualityIssue,
  DataQualitySeverity,
  DataQualityStatus,
} from "../types";

type ToastState = { kind: "success" | "error"; message: string } | null;
type IssueAction = "acknowledge" | "ignore" | "resolve";

const severityOptions: DataQualitySeverity[] = ["critical", "high", "warning", "info"];
const statusOptions: DataQualityStatus[] = ["open", "acknowledged", "ignored", "resolved"];
const entityOptions: DataQualityEntityType[] = [
  "investigation",
  "engagement",
  "scope_item",
  "finding",
  "evidence",
  "report",
  "deliverable",
  "closure",
  "notification",
  "saved_view",
  "user",
  "demo_data",
  "system",
];

export function DataQualityPage(): JSX.Element {
  const queryClient = useQueryClient();
  const [severity, setSeverity] = useState<DataQualitySeverity | "">("");
  const [status, setStatus] = useState<DataQualityStatus | "">("");
  const [entityType, setEntityType] = useState<DataQualityEntityType | "">("");
  const [issueType, setIssueType] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<DataQualityIssue | null>(null);
  const [toast, setToast] = useState<ToastState>(null);
  const limit = 50;

  const overview = useQuery({
    queryKey: ["data-quality-overview"],
    queryFn: getDataQualityOverview,
    retry: 1,
  });
  const issues = useQuery({
    queryKey: ["data-quality-issues", severity, status, entityType, issueType, offset],
    queryFn: () =>
      listDataQualityIssues({
        severity,
        status,
        entity_type: entityType,
        issue_type: issueType,
        limit,
        offset,
      }),
    retry: 1,
  });

  async function refreshQualityData(): Promise<void> {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["data-quality-overview"] }),
      queryClient.invalidateQueries({ queryKey: ["data-quality-issues"] }),
    ]);
  }

  const scan = useMutation({
    mutationFn: runDataQualityScan,
    onMutate: () => setToast(null),
    onSuccess: async (result) => {
      setToast({
        kind: "success",
        message: `Scan completed: ${safeNumber(result.detected)} detected, ${safeNumber(result.created)} new. No records were changed or deleted.`,
      });
      await refreshQualityData();
    },
    onError: (error) => setToast({ kind: "error", message: errorMessage(error) }),
  });
  const dryRun = useMutation({
    mutationFn: runMaintenanceDryRun,
    onMutate: () => setToast(null),
    onSuccess: (result) => {
      setToast({
        kind: "success",
        message: `Dry run found ${safeNumber(result.would_detect)} recommendations. No destructive changes were made.`,
      });
    },
    onError: (error) => setToast({ kind: "error", message: errorMessage(error) }),
  });
  const archiveNotifications = useMutation({
    mutationFn: () => archiveStaleNotifications(90),
    onMutate: () => setToast(null),
    onSuccess: async (result) => {
      setToast({ kind: "success", message: result.message });
      await refreshQualityData();
    },
    onError: (error) => setToast({ kind: "error", message: errorMessage(error) }),
  });
  const transition = useMutation({
    mutationFn: ({ issueId, action }: { issueId: string; action: IssueAction }) =>
      updateDataQualityIssueStatus(issueId, action),
    onMutate: () => setToast(null),
    onSuccess: async (result) => {
      setSelected(result);
      setToast({
        kind: "success",
        message: `Issue marked ${safeString(result.status, "updated").replace(/_/g, " ")}.`,
      });
      await refreshQualityData();
    },
    onError: (error) => setToast({ kind: "error", message: errorMessage(error) }),
  });

  const issueItems = safeArray(issues.data?.items);
  const total = safeNumber(issues.data?.total);
  const summary = overview.data;
  const cards = useMemo(
    () => [
      { label: "Open issues", value: safeNumber(summary?.open_issues), tone: "text-raven-cyan" },
      { label: "Critical", value: safeNumber(summary?.critical_issues), tone: "text-rose-200" },
      { label: "High", value: safeNumber(summary?.high_issues), tone: "text-orange-200" },
      { label: "Warnings", value: safeNumber(summary?.warning_issues), tone: "text-amber-100" },
      { label: "Resolved", value: safeNumber(summary?.resolved_issues), tone: "text-emerald-200" },
    ],
    [summary],
  );

  return (
    <>
      <PageHeader
        title="Data Quality Center"
        eyebrow="Safe maintenance and consistency"
        actions={
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => dryRun.mutate()}
              disabled={dryRun.isPending || scan.isPending}
              title="Preview current findings without persisting or changing application data"
              className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-muted hover:border-raven-cyan hover:text-raven-text disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Eye className="h-4 w-4" aria-hidden="true" />
              {dryRun.isPending ? "Checking" : "Dry run"}
            </button>
            <button
              type="button"
              onClick={() => scan.mutate()}
              disabled={scan.isPending || dryRun.isPending}
              title="Detect and persist recommendations without changing affected records"
              className="inline-flex items-center gap-2 rounded-md bg-raven-violet px-3 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <SearchCheck className="h-4 w-4" aria-hidden="true" />
              {scan.isPending ? "Scanning" : "Run scan"}
            </button>
          </div>
        }
      />

      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}

      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-semibold">Non-destructive by design</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-raven-muted">
              Scans identify consistency risks and recommend manual corrections. They never
              delete investigations, findings, reports, users, evidence, or scope records.
            </p>
          </div>
          <span className="rounded-full border border-raven-border bg-raven-panelSoft px-3 py-1 text-xs capitalize text-raven-muted">
            {safeString(summary?.scan_status, "not run").replace(/_/g, " ")}
          </span>
        </div>
        <p className="mt-3 text-xs text-raven-muted">
          Last scan: {safeDate(summary?.last_scan_at)?.toLocaleString() ?? "not run yet"}
        </p>
      </section>

      {overview.isLoading ? (
        <div className="mt-4"><LoadingBlock label="Loading quality summary" /></div>
      ) : overview.error ? (
        <div className="mt-4"><ErrorBlock message={overview.error} /></div>
      ) : (
        <section className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {cards.map((card) => (
            <div key={card.label} className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
              <p className="text-xs uppercase tracking-wide text-raven-muted">{card.label}</p>
              <p className={`mt-2 text-2xl font-semibold ${card.tone}`}>{card.value}</p>
            </div>
          ))}
        </section>
      )}

      <section className="mt-5 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <FilterSelect label="Severity" value={severity} onChange={(value) => { setSeverity(value as DataQualitySeverity | ""); setOffset(0); }} options={severityOptions} />
          <FilterSelect label="Status" value={status} onChange={(value) => { setStatus(value as DataQualityStatus | ""); setOffset(0); }} options={statusOptions} />
          <FilterSelect label="Entity" value={entityType} onChange={(value) => { setEntityType(value as DataQualityEntityType | ""); setOffset(0); }} options={entityOptions} />
          <label className="text-sm text-raven-muted">
            Issue type
            <input
              value={issueType}
              onChange={(event) => { setIssueType(event.target.value); setOffset(0); }}
              placeholder="e.g. duplicate_finding"
              className="mt-1 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
            />
          </label>
        </div>
      </section>

      <section className="mt-4 min-w-0 overflow-hidden rounded-lg border border-raven-border bg-raven-panel/85">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-raven-border px-4 py-3">
          <div>
            <h2 className="font-semibold">Consistency issues</h2>
            <p className="mt-1 text-xs text-raven-muted">{total} matching records</p>
          </div>
          <button
            type="button"
            onClick={() => {
              if (window.confirm("Archive read or dismissed notifications older than 90 days? No notification content will be deleted.")) {
                archiveNotifications.mutate();
              }
            }}
            disabled={archiveNotifications.isPending}
            title="Only read or dismissed notifications older than 90 days are soft archived"
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-xs text-raven-muted hover:border-raven-violet hover:text-raven-text disabled:opacity-50"
          >
            <Archive className="h-4 w-4" aria-hidden="true" />
            {archiveNotifications.isPending ? "Archiving" : "Archive stale notifications"}
          </button>
        </div>

        {issues.isLoading ? (
          <div className="p-4"><LoadingBlock label="Loading quality issues" /></div>
        ) : issues.error ? (
          <div className="p-4"><ErrorBlock message={issues.error} /></div>
        ) : issueItems.length === 0 ? (
          <div className="p-4">
            <EmptyBlock
              title={summary?.last_scan_at ? "No matching issues" : "No quality scan yet"}
              message={summary?.last_scan_at ? "No persisted issues match the current filters." : "Run a scan to create a bounded, non-destructive consistency report."}
              nextStep="Use Dry run first to preview recommendations without persistence."
              permission="Administrator access is required for maintenance actions."
            />
          </div>
        ) : (
          <div className="themed-scrollbar overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead className="bg-raven-panelSoft text-xs uppercase tracking-wide text-raven-muted">
                <tr>
                  <th className="px-4 py-3">Severity</th>
                  <th className="px-4 py-3">Issue</th>
                  <th className="px-4 py-3">Entity</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Detected</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-raven-border">
                {issueItems.map((issue) => (
                  <tr key={issue.id} className="align-top hover:bg-raven-panelSoft/60">
                    <td className="px-4 py-3"><SeverityPill value={issue.severity} /></td>
                    <td className="max-w-lg px-4 py-3">
                      <p className="break-words font-medium">{safeString(issue.title, "Quality issue")}</p>
                      <p className="mt-1 line-clamp-2 break-words text-xs text-raven-muted">{safeString(issue.description, "No description available.")}</p>
                    </td>
                    <td className="px-4 py-3">
                      <p className="capitalize">{safeString(issue.entity_type, "system").replace(/_/g, " ")}</p>
                      {issue.entity_id ? <p className="mt-1 max-w-44 truncate font-mono text-xs text-raven-muted" title={issue.entity_id}>{issue.entity_id}</p> : null}
                    </td>
                    <td className="px-4 py-3"><StatusPill value={issue.status} /></td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-raven-muted">{safeDate(issue.detected_at)?.toLocaleString() ?? "Unknown"}</td>
                    <td className="px-4 py-3 text-right">
                      <button type="button" onClick={() => setSelected(issue)} className="rounded-md border border-raven-border px-3 py-2 text-xs text-raven-muted hover:border-raven-cyan hover:text-raven-text">Review</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {total > limit ? (
          <div className="flex items-center justify-between gap-3 border-t border-raven-border px-4 py-3 text-sm">
            <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))} className="rounded-md border border-raven-border px-3 py-2 disabled:opacity-40">Previous</button>
            <span className="text-raven-muted">{offset + 1}-{Math.min(offset + limit, total)} of {total}</span>
            <button type="button" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)} className="rounded-md border border-raven-border px-3 py-2 disabled:opacity-40">Next</button>
          </div>
        ) : null}
      </section>

      {selected ? (
        <IssueModal
          issue={selected}
          pending={transition.isPending}
          onClose={() => setSelected(null)}
          onAction={(action) => transition.mutate({ issueId: selected.id, action })}
        />
      ) : null}
    </>
  );
}

function FilterSelect({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }): JSX.Element {
  return (
    <label className="text-sm text-raven-muted">
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)} className="mt-1 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text">
        <option value="">All</option>
        {options.map((option) => <option key={option} value={option}>{option.replace(/_/g, " ")}</option>)}
      </select>
    </label>
  );
}

function IssueModal({ issue, pending, onClose, onAction }: { issue: DataQualityIssue; pending: boolean; onClose: () => void; onAction: (action: IssueAction) => void }): JSX.Element {
  const metadata = issue.metadata && typeof issue.metadata === "object" ? issue.metadata : {};
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section role="dialog" aria-modal="true" aria-label="Data quality issue detail" className="themed-scrollbar max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-lg border border-raven-border bg-raven-bg p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap gap-2"><SeverityPill value={issue.severity} /><StatusPill value={issue.status} /></div>
            <h2 className="mt-3 break-words text-xl font-semibold">{safeString(issue.title, "Quality issue")}</h2>
            <p className="mt-1 break-all font-mono text-xs text-raven-muted">{issue.id}</p>
          </div>
          <button type="button" onClick={onClose} title="Close issue detail" className="rounded-md p-2 text-raven-muted hover:bg-raven-panelSoft hover:text-raven-text"><X className="h-5 w-5" aria-hidden="true" /></button>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <DetailBlock title="Why it matters" text={safeString(issue.description, "No description available.")} icon={<AlertTriangle className="h-4 w-4 text-amber-200" aria-hidden="true" />} />
          <DetailBlock title="Recommended action" text={safeString(issue.recommendation, "Review the affected record manually.")} icon={<CheckCircle2 className="h-4 w-4 text-emerald-200" aria-hidden="true" />} />
        </div>
        <dl className="mt-5 grid gap-3 rounded-md border border-raven-border bg-raven-panel p-4 text-sm sm:grid-cols-2">
          <Info label="Issue type" value={issue.issue_type} />
          <Info label="Entity type" value={issue.entity_type} />
          <Info label="Entity ID" value={issue.entity_id ?? "not applicable"} />
          <Info label="Detected" value={safeDate(issue.detected_at)?.toLocaleString() ?? "unknown"} />
        </dl>
        {Object.keys(metadata).length ? (
          <details className="mt-4 rounded-md border border-raven-border bg-raven-panel p-4">
            <summary className="cursor-pointer text-sm font-medium">Safe diagnostic metadata</summary>
            <pre className="themed-scrollbar mt-3 max-h-48 overflow-auto whitespace-pre-wrap break-all text-xs text-raven-muted">{JSON.stringify(metadata, null, 2)}</pre>
          </details>
        ) : null}
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-raven-border pt-4">
          <div>{issue.action_url ? <Link to={issue.action_url} className="inline-flex items-center gap-2 text-sm text-raven-cyan hover:underline"><ShieldAlert className="h-4 w-4" aria-hidden="true" />Open affected area</Link> : <span className="text-xs text-raven-muted">No direct action link is available.</span>}</div>
          <div className="flex flex-wrap gap-2">
            {issue.status === "open" ? <ActionButton label="Acknowledge" disabled={pending} onClick={() => onAction("acknowledge")} /> : null}
            {issue.status === "open" || issue.status === "acknowledged" ? <ActionButton label="Ignore" disabled={pending} onClick={() => onAction("ignore")} /> : null}
            {issue.status !== "resolved" ? <ActionButton label="Mark resolved" disabled={pending} primary onClick={() => onAction("resolve")} /> : null}
          </div>
        </div>
      </section>
    </div>
  );
}

function DetailBlock({ title, text, icon }: { title: string; text: string; icon: JSX.Element }): JSX.Element {
  return <div className="min-w-0 rounded-md border border-raven-border bg-raven-panel p-4"><div className="flex items-center gap-2 font-medium">{icon}<h3>{title}</h3></div><p className="mt-2 break-words text-sm leading-6 text-raven-muted">{text}</p></div>;
}

function Info({ label, value }: { label: string; value: string }): JSX.Element {
  return <div className="min-w-0"><dt className="text-xs uppercase tracking-wide text-raven-muted">{label}</dt><dd className="mt-1 break-all font-mono text-xs text-raven-text">{safeString(value, "n/a")}</dd></div>;
}

function ActionButton({ label, disabled, primary = false, onClick }: { label: string; disabled: boolean; primary?: boolean; onClick: () => void }): JSX.Element {
  return <button type="button" disabled={disabled} onClick={onClick} className={primary ? "rounded-md bg-raven-violet px-3 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50" : "rounded-md border border-raven-border px-3 py-2 text-sm text-raven-muted hover:border-raven-violet hover:text-raven-text disabled:opacity-50"}>{label}</button>;
}

function SeverityPill({ value }: { value: string }): JSX.Element {
  const normalized = safeString(value, "info");
  const classes = normalized === "critical" ? "border-rose-400/30 bg-rose-500/10 text-rose-100" : normalized === "high" ? "border-orange-400/30 bg-orange-500/10 text-orange-100" : normalized === "warning" ? "border-amber-400/30 bg-amber-500/10 text-amber-100" : "border-cyan-400/30 bg-cyan-500/10 text-cyan-100";
  return <span className={`inline-flex rounded-full border px-2 py-1 text-xs capitalize ${classes}`}>{normalized}</span>;
}

function StatusPill({ value }: { value: string }): JSX.Element {
  const normalized = safeString(value, "open");
  const classes = normalized === "resolved" ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-100" : normalized === "ignored" ? "border-slate-400/30 bg-slate-500/10 text-slate-200" : normalized === "acknowledged" ? "border-violet-400/30 bg-violet-500/10 text-violet-100" : "border-cyan-400/30 bg-cyan-500/10 text-cyan-100";
  return <span className={`inline-flex rounded-full border px-2 py-1 text-xs capitalize ${classes}`}>{normalized.replace(/_/g, " ")}</span>;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "The maintenance request could not be completed.";
}
