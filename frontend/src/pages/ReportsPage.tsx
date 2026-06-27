import {
  Archive,
  Download,
  FileText,
  Loader2,
  RefreshCw,
  RotateCcw,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { BookmarkButton } from "../components/BookmarkButton";
import { InvestigationTabs } from "../components/InvestigationTabs";
import { LongValue } from "../components/LongValue";
import { PageHeader } from "../components/PageHeader";
import { ReportStatusBadge } from "../components/ReportStatusBadge";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import {
  archiveReport,
  createReport,
  decideReportApproval,
  downloadReport,
  getFeatureAvailability,
  listReports,
  listReportTemplates,
  previewReportQuality,
  restoreReport,
  retryReport,
  submitReportApproval,
} from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import { reportGuidance } from "../lib/reportGuidance";
import { useAuth } from "../lib/useAuth";
import type {
  ReportFormat,
  ReportSummary,
  ReportTemplate,
  ReportType,
} from "../types";

const formats: ReportFormat[] = ["pdf", "docx", "html", "md"];
const reportTypes: Array<{ type: ReportType; label: string }> = [
  { type: "executive", label: "Executive Summary" },
  { type: "technical", label: "Technical Assessment" },
  { type: "remediation", label: "Remediation Report" },
  { type: "evidence_appendix", label: "Evidence Appendix" },
  { type: "compliance_mapping", label: "Compliance Mapping" },
  { type: "playbook_progress", label: "Playbook Progress" },
  { type: "operational_dashboard", label: "Operational Dashboard" },
];

export function ReportsPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [toast, setToast] = useState<ToastState | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [reportType, setReportType] = useState<ReportType>("technical");
  const [format, setFormat] = useState<ReportFormat>("pdf");
  const [templateId, setTemplateId] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const features = useQuery({
    queryKey: ["feature-availability"],
    queryFn: getFeatureAvailability,
    staleTime: 30_000,
  });
  const allowedFormats = features.data?.allowed_export_formats ?? formats;
  useEffect(() => {
    if (allowedFormats.length && !allowedFormats.includes(format)) {
      setFormat(allowedFormats[0]);
    }
  }, [allowedFormats, format]);
  const reports = useQuery({
    queryKey: ["reports", investigationId, showArchived],
    queryFn: () => listReports(investigationId, showArchived),
    refetchInterval: (query) =>
      (query.state.data?.items ?? []).some((report) =>
        ["queued", "generating"].includes(report.status),
      )
        ? 3_000
        : false,
  });
  const templates = useQuery({
    queryKey: ["report-templates"],
    queryFn: () => listReportTemplates(),
    staleTime: 60_000,
  });
  const templateItems = templates.data?.items ?? [];
  const reportItems = reports.data?.items ?? [];
  const availableTemplates = useMemo(
    () =>
      templateItems.filter(
        (template) => template.report_type === reportType,
      ) ?? [],
    [reportType, templateItems],
  );
  const selectedTemplate =
    availableTemplates.find((template) => template.id === templateId) ??
    availableTemplates.find((template) => template.is_default) ??
    null;
  const quality = useQuery({
    queryKey: [
      "report-quality-preview",
      investigationId,
      reportType,
      selectedTemplate?.id,
    ],
    queryFn: () =>
      previewReportQuality(investigationId, reportType, selectedTemplate?.id),
    enabled: templates.isSuccess,
    staleTime: 30_000,
  });
  const generateReport = useMutation({
    mutationFn: () =>
      createReport(investigationId, {
        report_type: reportType,
        template_id: selectedTemplate?.id,
        output_format: format,
      }),
    onSuccess: async (report) => {
      await invalidateReports(queryClient, investigationId);
      setToast({
        kind: report.status === "failed" ? "error" : "success",
        message:
          report.status === "failed"
            ? report.failure_reason ?? "Report generation failed."
            : `${report.report_type.replace(/_/g, " ")} report is ready.`,
      });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message:
          error instanceof Error ? error.message : "Unable to generate report.",
      });
    },
  });
  const lifecycleMutation = useMutation({
    mutationFn: async ({
      action,
      reportId,
    }: {
      action: "archive" | "restore" | "retry";
      reportId: string;
    }) => {
      if (action === "archive") {
        return archiveReport(reportId);
      }
      if (action === "restore") {
        return restoreReport(reportId);
      }
      return retryReport(reportId);
    },
    onSuccess: async (response) => {
      await invalidateReports(queryClient, investigationId);
      setToast({ kind: "success", message: response.message });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Report action failed.",
      });
    },
  });
  const approvalMutation = useMutation({
    mutationFn: ({
      action,
      reportId,
      notes,
    }: {
      action: "submit" | "approve" | "reject";
      reportId: string;
      notes?: string;
    }) => {
      if (action === "submit") {
        return submitReportApproval(reportId, notes);
      }
      return decideReportApproval(reportId, {
        decision: action,
        notes: notes ?? "Report approval workflow updated.",
      });
    },
    onSuccess: async () => {
      await invalidateReports(queryClient, investigationId);
      await queryClient.invalidateQueries({ queryKey: ["review-board"] });
      setToast({ kind: "success", message: "Report approval updated." });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message:
          error instanceof Error ? error.message : "Report approval action failed.",
      });
    },
  });

  async function handleDownload(
    report: ReportSummary,
    outputFormat: ReportFormat,
  ): Promise<void> {
    const downloadKey = `${report.id}:${outputFormat}`;
    setToast(null);
    setDownloading(downloadKey);
    try {
      const download = await downloadReport(report.id, outputFormat);
      if (download.handledExternally || download.blob === null) {
        setToast({
          kind: "success",
          message: `${outputFormat.toUpperCase()} download was handed to the browser or download manager.`,
        });
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
      setToast({
        kind: "success",
        message: `${outputFormat.toUpperCase()} download ready.`,
      });
    } catch (error) {
      setToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Download failed.",
      });
    } finally {
      setDownloading(null);
    }
  }

  if (reports.isLoading) {
    return <LoadingBlock label="Loading reports" />;
  }
  if (reports.isError) {
    return <ErrorBlock message={reports.error} />;
  }

  return (
    <>
      <PageHeader
        title="Reports"
        eyebrow="Investigation exports"
        actions={
          <div className="flex flex-wrap gap-2">
            {user?.role === "admin" ? (
              <label className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-muted">
                <input
                  type="checkbox"
                  checked={showArchived}
                  onChange={(event) => setShowArchived(event.target.checked)}
                  className="accent-violet-500"
                />
                Show archived
              </label>
            ) : null}
            <button
              type="button"
              onClick={() => void reports.refetch()}
              className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm hover:border-raven-violet"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Refresh
            </button>
          </div>
        }
      />
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}
      <InvestigationTabs />

      <section className="mb-5 min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_150px_auto] xl:items-end">
          <Field label="Report type">
            <select
              value={reportType}
              onChange={(event) => {
                setReportType(event.target.value as ReportType);
                setTemplateId("");
              }}
              className="input-base"
            >
              {reportTypes.map((item) => (
                <option key={item.type} value={item.type}>
                  {item.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Template">
            <select
              value={selectedTemplate?.id ?? ""}
              onChange={(event) => setTemplateId(event.target.value)}
              disabled={templates.isLoading || availableTemplates.length === 0}
              className="input-base"
            >
              {availableTemplates.length === 0 ? (
                <option value="">Default section set</option>
              ) : null}
              {availableTemplates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name}
                  {template.is_default ? " (default)" : ""}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Preferred format">
            <select
              value={format}
              onChange={(event) => setFormat(event.target.value as ReportFormat)}
              className="input-base uppercase"
            >
              {allowedFormats.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </Field>
          <button
            type="button"
            onClick={() => generateReport.mutate()}
            disabled={generateReport.isPending || templates.isLoading}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-60"
          >
            {generateReport.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Sparkles className="h-4 w-4" aria-hidden="true" />
            )}
            Generate
          </button>
        </div>
        {selectedTemplate ? (
          <TemplatePreview template={selectedTemplate} />
        ) : (
          <TemplatePreview reportType={reportType} />
        )}
        <QualityWarnings
          isLoading={quality.isLoading}
          warnings={quality.data?.warnings ?? []}
          availableEvidence={quality.data?.available_evidence ?? {}}
          missingSections={quality.data?.missing_sections ?? []}
        />
      </section>

      {reportItems.length ? (
        <div className="space-y-4">
          {reportItems.map((report) => (
            <ReportCard
              key={report.id}
              report={report}
              template={templateItems.find(
                (item) => item.id === report.template_id,
              )}
              investigationId={investigationId}
              downloading={downloading}
              allowedFormats={allowedFormats}
              lifecyclePending={
                lifecycleMutation.isPending &&
                lifecycleMutation.variables?.reportId === report.id
              }
              approvalPending={
                approvalMutation.isPending &&
                approvalMutation.variables?.reportId === report.id
              }
              onDownload={handleDownload}
              onLifecycle={(action) =>
                lifecycleMutation.mutate({ action, reportId: report.id })
              }
              onApproval={(action) => {
                const notes = window.prompt("Approval notes") ?? "";
                if (action === "submit" || notes.trim()) {
                  approvalMutation.mutate({
                    action,
                    reportId: report.id,
                    notes,
                  });
                }
              }}
            />
          ))}
        </div>
      ) : (
        <EmptyBlock
          title="No reports generated"
          message="Reports turn stored findings, notes, evidence, and remediation progress into an analyst-approved deliverable."
          nextStep="Select a safe template above after findings, notes, or evidence are available."
          permission="Analysts with report permission can generate; viewers can download existing reports."
        />
      )}
    </>
  );
}

function TemplatePreview({
  template,
  reportType,
}: {
  template?: ReportTemplate;
  reportType?: ReportType;
}): JSX.Element {
  const type = template?.report_type ?? reportType ?? "technical";
  const guidance = reportGuidance[type];
  return (
    <div className="mt-3 rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <p className="text-sm text-raven-text">
        {template?.description ?? guidance.summary}
      </p>
      <p className="mt-1 text-xs text-raven-muted">
        Recommended when {guidance.recommendedWhen}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {(template?.sections ?? guidance.emphasis).map((section) => (
          <span
            key={section}
            className="rounded border border-raven-border px-2 py-0.5 text-xs text-raven-muted"
          >
            {section.replace(/_/g, " ")}
          </span>
        ))}
      </div>
    </div>
  );
}

function ReportCard({
  report,
  template,
  investigationId,
  downloading,
  allowedFormats,
  lifecyclePending,
  approvalPending,
  onDownload,
  onLifecycle,
  onApproval,
}: {
  report: ReportSummary;
  template: ReportTemplate | undefined;
  investigationId: string;
  downloading: string | null;
  allowedFormats: ReportFormat[];
  lifecyclePending: boolean;
  approvalPending: boolean;
  onDownload: (report: ReportSummary, format: ReportFormat) => Promise<void>;
  onLifecycle: (action: "archive" | "restore" | "retry") => void;
  onApproval: (action: "submit" | "approve" | "reject") => void;
}): JSX.Element {
  return (
    <article className="min-w-0 overflow-hidden rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <FileText className="h-4 w-4 text-raven-cyan" aria-hidden="true" />
            <h2 className="font-semibold">
              {report.title ?? "Investigation report"}
            </h2>
            <ReportStatusBadge status={report.status} />
          </div>
          <div className="mt-3 grid gap-2 text-sm text-raven-muted sm:grid-cols-2 xl:grid-cols-3">
            <ReportMetric label="Report ID" value={report.id} />
            <ReportMetric
              label="Type"
              value={report.report_type.replace(/_/g, " ")}
            />
            <ReportMetric label="Template" value={template?.name ?? "Default"} />
            <ReportMetric
              label="Created"
              value={new Date(report.created_at).toLocaleString()}
            />
            <ReportMetric
              label="Generated by"
              value={report.generated_by ?? "unknown"}
            />
            <ReportMetric
              label="File size"
              value={formatBytes(report.file_size_bytes)}
            />
            <ReportMetric
              label="Approval"
              value={report.approval_status.replace(/_/g, " ")}
            />
          </div>
          {report.rejection_reason ? (
            <p className="mt-3 rounded-md border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">
              Rejected: {report.rejection_reason}
            </p>
          ) : report.approval_notes ? (
            <p className="mt-3 rounded-md border border-raven-border bg-raven-panelSoft p-3 text-sm text-raven-muted">
              Approval note: {report.approval_notes}
            </p>
          ) : null}
          {report.progress_label ? (
            <p className="mt-3 text-sm text-raven-muted">
              {report.progress_label}
              {report.retry_count ? ` · ${report.retry_count} retries` : ""}
            </p>
          ) : null}
          {report.failure_reason ?? report.error_message ? (
            <p className="mt-3 whitespace-pre-wrap rounded-md border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">
              {report.failure_reason ?? report.error_message}
            </p>
          ) : null}
        </div>
        <div className="flex max-w-xl flex-wrap gap-2">
          <BookmarkButton
            investigationId={investigationId}
            reportId={report.id}
            title={`Report: ${report.title ?? report.report_type}`}
          />
          {allowedFormats.map((outputFormat) => {
            const key = `${report.id}:${outputFormat}`;
            return (
              <button
                key={outputFormat}
                type="button"
                onClick={() => void onDownload(report, outputFormat)}
                disabled={
                  !["ready", "archived"].includes(report.status) ||
                  downloading === key
                }
                className="inline-flex items-center gap-2 rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm uppercase hover:border-raven-violet disabled:opacity-50"
              >
                {downloading === key ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Download className="h-4 w-4" aria-hidden="true" />
                )}
                {outputFormat}
              </button>
            );
          })}
          {report.status === "failed" ? (
            <LifecycleButton
              label="Retry"
              icon={RotateCcw}
              pending={lifecyclePending}
              onClick={() => onLifecycle("retry")}
            />
          ) : null}
          {report.approval_status !== "pending_approval" &&
          report.approval_status !== "approved" &&
          report.status !== "archived" ? (
            <LifecycleButton
              label="Submit approval"
              icon={FileText}
              pending={approvalPending}
              onClick={() => onApproval("submit")}
            />
          ) : null}
          {report.approval_status === "pending_approval" ? (
            <>
              <LifecycleButton
                label="Approve"
                icon={FileText}
                pending={approvalPending}
                onClick={() => onApproval("approve")}
              />
              <LifecycleButton
                label="Reject"
                icon={Archive}
                pending={approvalPending}
                onClick={() => onApproval("reject")}
              />
            </>
          ) : null}
          {report.status === "archived" ? (
            <LifecycleButton
              label="Restore"
              icon={RotateCcw}
              pending={lifecyclePending}
              onClick={() => onLifecycle("restore")}
            />
          ) : report.status !== "generating" && report.status !== "queued" ? (
            <LifecycleButton
              label="Archive"
              icon={Archive}
              pending={lifecyclePending}
              onClick={() => onLifecycle("archive")}
            />
          ) : null}
        </div>
      </div>
    </article>
  );
}

function QualityWarnings({
  isLoading,
  warnings,
  availableEvidence,
  missingSections,
}: {
  isLoading: boolean;
  warnings: Array<{ code: string; message: string }>;
  availableEvidence: Record<string, number>;
  missingSections: string[];
}): JSX.Element {
  if (isLoading) {
    return (
      <p className="mt-4 inline-flex items-center gap-2 text-sm text-raven-muted">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        Checking report readiness
      </p>
    );
  }
  if (!warnings.length) {
    return (
      <ReportReadinessEvidence availableEvidence={availableEvidence} />
    );
  }
  return (
    <div className="mt-4 space-y-3">
      <ReportReadinessEvidence availableEvidence={availableEvidence} />
      <details className="rounded-md border border-amber-400/30 bg-amber-500/10 p-3">
        <summary className="cursor-pointer text-sm font-medium text-amber-100">
          <span className="inline-flex items-center gap-2">
            <TriangleAlert className="h-4 w-4" aria-hidden="true" />
            {warnings.length} quality warning{warnings.length === 1 ? "" : "s"}
          </span>
        </summary>
        {missingSections.length ? (
          <p className="mt-3 text-sm text-amber-100/80">
            Missing or incomplete: {missingSections.join(", ")}.
          </p>
        ) : null}
        <ul className="mt-3 min-w-0 space-y-2 break-words text-sm text-amber-100/80">
          {warnings.map((warning) => (
            <li key={warning.code}>{warning.message}</li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-amber-100/70">
          These readiness checks explain which sections may be sparse. They do
          not block analyst-approved generation.
        </p>
      </details>
    </div>
  );
}

function ReportReadinessEvidence({
  availableEvidence,
}: {
  availableEvidence: Record<string, number>;
}): JSX.Element {
  return (
    <div className="mt-4 rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <p className="text-sm font-medium">Available evidence</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {Object.entries(availableEvidence).map(([label, count]) => (
          <span
            key={label}
            className={[
              "rounded border px-2 py-1 text-xs capitalize",
              count
                ? "border-emerald-400/30 text-emerald-100"
                : "border-raven-border text-raven-muted",
            ].join(" ")}
          >
            {label.replace(/_/g, " ")}: {count}
          </span>
        ))}
      </div>
    </div>
  );
}

function LifecycleButton({
  label,
  icon: Icon,
  pending,
  onClick,
}: {
  label: string;
  icon: typeof Archive;
  pending: boolean;
  onClick: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={pending}
      className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm hover:border-raven-violet disabled:opacity-50"
    >
      {pending ? (
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      ) : (
        <Icon className="h-4 w-4" aria-hidden="true" />
      )}
      {label}
    </button>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}): JSX.Element {
  return (
    <label className="block text-sm text-raven-muted">
      <span className="mb-1 block">{label}</span>
      {children}
    </label>
  );
}

function ReportMetric({
  label,
  value,
}: {
  label: string;
  value: string | number;
}): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2">
      <p className="text-xs uppercase tracking-wide">{label}</p>
      <LongValue value={String(value)} className="mt-1" maxLength={44} />
    </div>
  );
}

async function invalidateReports(
  queryClient: ReturnType<typeof useQueryClient>,
  investigationId: string,
): Promise<void> {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["reports", investigationId] }),
    queryClient.invalidateQueries({ queryKey: ["reporting-center"] }),
    queryClient.invalidateQueries({
      queryKey: ["report-quality-preview", investigationId],
    }),
  ]);
}

function formatBytes(value: number | null): string {
  if (value === null) {
    return "Not available";
  }
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}
