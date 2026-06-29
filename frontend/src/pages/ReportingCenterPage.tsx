import {
  Archive,
  Download,
  FilePlus2,
  FileText,
  Loader2,
  RefreshCw,
  RotateCcw,
  Settings2,
  TriangleAlert,
} from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { LongValue } from "../components/LongValue";
import { PageHeader } from "../components/PageHeader";
import { ReportStatusBadge } from "../components/ReportStatusBadge";
import { SavedViewsPanel } from "../components/SavedViewsPanel";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import {
  archiveReport,
  bulkGenerateReports,
  createReportTemplate,
  deactivateReportTemplate,
  downloadReport,
  getFeatureAvailability,
  getAnalystWorkload,
  getInvestigationQueue,
  listReportingCenterReports,
  listReportTemplates,
  previewReportQuality,
  restoreReport,
  retryReport,
  updateReportTemplate,
} from "../lib/api";
import { reportGuidance } from "../lib/reportGuidance";
import { useAuth } from "../lib/useAuth";
import type {
  ReportFormat,
  ReportingCenterFilters,
  ReportingCenterItem,
  ReportSection,
  ReportSort,
  ReportStatus,
  ReportTemplate,
  ReportTemplateCreateRequest,
  ReportType,
} from "../types";

const reportTypes: ReportType[] = [
  "executive",
  "technical",
  "remediation",
  "evidence_appendix",
  "compliance_mapping",
  "playbook_progress",
  "operational_dashboard",
];
const reportStatuses: ReportStatus[] = [
  "queued",
  "generating",
  "ready",
  "failed",
  "archived",
];
const formats: ReportFormat[] = ["pdf", "docx", "html", "md"];
const sortOptions: ReportSort[] = [
  "newest",
  "oldest",
  "status",
  "report_type",
  "investigation",
];
const safeSections: ReportSection[] = [
  "executive_summary",
  "scope",
  "authorization",
  "findings_summary",
  "severity_distribution",
  "threat_intelligence",
  "remediation_progress",
  "playbook_progress",
  "evidence_chains",
  "evidence_intelligence",
  "recurring_evidence",
  "related_investigations",
  "analyst_notes",
  "task_summary",
  "timeline_summary",
  "audit_summary",
  "framework_mapping",
  "appendix",
];

export function ReportingCenterPage(): JSX.Element {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [filters, setFilters] = useState<ReportingCenterFilters>({
    sort: "newest",
    limit: 100,
  });
  const [selectedInvestigations, setSelectedInvestigations] = useState<Set<string>>(
    new Set(),
  );
  const [reportType, setReportType] = useState<ReportType>("executive");
  const [templateId, setTemplateId] = useState("");
  const [format, setFormat] = useState<ReportFormat>("pdf");
  const [downloading, setDownloading] = useState<string | null>(null);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [showTemplateEditor, setShowTemplateEditor] = useState(false);
  const features = useQuery({
    queryKey: ["feature-availability"],
    queryFn: getFeatureAvailability,
    staleTime: 30_000,
  });
  const allowedFormats = features.data?.allowed_export_formats ?? formats;
  const bulkEnabled =
    features.data?.feature_flags.enable_bulk_actions !== false;
  useEffect(() => {
    if (allowedFormats.length && !allowedFormats.includes(format)) {
      setFormat(allowedFormats[0]);
    }
  }, [allowedFormats, format]);
  const reports = useQuery({
    queryKey: ["reporting-center", filters],
    queryFn: () => listReportingCenterReports(filters),
    refetchInterval: (query) =>
      (query.state.data?.items ?? []).some((report) =>
        ["queued", "generating"].includes(report.status),
      )
        ? 3_000
        : false,
  });
  const templates = useQuery({
    queryKey: ["report-templates", user?.role],
    queryFn: () => listReportTemplates(user?.role === "admin"),
    staleTime: 60_000,
  });
  const investigations = useQuery({
    queryKey: ["investigation-queue", "reporting-center"],
    queryFn: () => getInvestigationQueue({ sort: "newest", limit: 100 }),
    staleTime: 30_000,
  });
  const analysts = useQuery({
    queryKey: ["analyst-workload"],
    queryFn: getAnalystWorkload,
    staleTime: 30_000,
  });
  const reportItems = reports.data?.items ?? [];
  const templateItems = templates.data?.items ?? [];
  const availableTemplates = useMemo(
    () =>
      templateItems.filter(
        (template) => template.report_type === reportType && template.is_active,
      ) ?? [],
    [reportType, templateItems],
  );
  const selectedTemplate =
    availableTemplates.find((template) => template.id === templateId) ??
    availableTemplates.find((template) => template.is_default) ??
    null;
  const onlyInvestigationId =
    selectedInvestigations.size === 1
      ? [...selectedInvestigations][0]
      : undefined;
  const quality = useQuery({
    queryKey: [
      "report-quality-preview",
      onlyInvestigationId,
      reportType,
      selectedTemplate?.id,
    ],
    queryFn: () =>
      previewReportQuality(
        onlyInvestigationId as string,
        reportType,
        selectedTemplate?.id,
      ),
    enabled: Boolean(onlyInvestigationId),
    staleTime: 30_000,
  });
  const bulkMutation = useMutation({
    mutationFn: () =>
      bulkGenerateReports({
        investigation_ids: [...selectedInvestigations],
        report_type: reportType,
        template_id: selectedTemplate?.id,
        output_format: format,
      }),
    onSuccess: async (response) => {
      await invalidateReportingCenter(queryClient);
      setSelectedInvestigations(new Set());
      setToast({
        kind: response.failed ? "error" : "success",
        message: `${response.generated} generated, ${response.skipped} skipped, ${response.failed} failed.`,
      });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Bulk generation failed.",
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
      await invalidateReportingCenter(queryClient);
      setToast({ kind: "success", message: response.message });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Report action failed.",
      });
    },
  });

  async function handleDownload(
    report: ReportingCenterItem,
    outputFormat: ReportFormat,
  ): Promise<void> {
    const key = `${report.id}:${outputFormat}`;
    setToast(null);
    setDownloading(key);
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
    return <LoadingBlock label="Loading reporting center" />;
  }
  if (reports.isError) {
    return <ErrorBlock message={reports.error} />;
  }

  return (
    <>
      <PageHeader
        title="Reporting Center"
        eyebrow="Enterprise exports"
        actions={
          <div className="flex gap-2">
            {user?.role === "admin" ? (
              <button
                type="button"
                onClick={() => setShowTemplateEditor((current) => !current)}
                className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm hover:border-raven-violet"
              >
                <Settings2 className="h-4 w-4" aria-hidden="true" />
                Templates
              </button>
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
      {showTemplateEditor && user?.role === "admin" ? (
        <TemplateLibrary
          onChanged={() => void invalidateReportingCenter(queryClient)}
          onToast={setToast}
        />
      ) : null}

      <div className="mb-5">
        <SavedViewsPanel
          viewType="reports"
          route="/reports"
          filters={filters}
          onApply={(view) => {
            setFilters(normalizeReportFilters(view.filters));
            setToast({ kind: "success", message: `Loaded ${view.name}.` });
          }}
        />
      </div>

      <section className="mb-5 min-w-0 overflow-hidden rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <h2 className="font-semibold">Generate reports</h2>
        <div className="mt-4 grid gap-4 lg:grid-cols-4">
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
                <option key={item} value={item}>
                  {humanize(item)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Template">
            <select
              value={selectedTemplate?.id ?? ""}
              onChange={(event) => setTemplateId(event.target.value)}
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
          <div className="flex items-end">
            {bulkEnabled ? (
            <button
              type="button"
              onClick={() => {
                if (
                  window.confirm(
                    `Generate ${reportType.replace(/_/g, " ")} reports for ${selectedInvestigations.size} investigations?`,
                  )
                ) {
                  bulkMutation.mutate();
                }
              }}
              disabled={selectedInvestigations.size === 0 || bulkMutation.isPending}
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-raven-violet px-4 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50"
            >
              {bulkMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <FilePlus2 className="h-4 w-4" aria-hidden="true" />
              )}
              Generate selected
            </button>
            ) : (
              <p className="w-full rounded-md border border-raven-border px-3 py-2 text-sm text-raven-muted">
                Bulk report generation is disabled.
              </p>
            )}
          </div>
        </div>
        <ReportTemplatePreview
          template={selectedTemplate}
          reportType={reportType}
        />
        <InvestigationSelector
          items={investigations.data?.items ?? []}
          selected={selectedInvestigations}
          onChange={setSelectedInvestigations}
          error={investigations.error?.message}
        />
        {onlyInvestigationId ? (
          <QualityPreview
            isLoading={quality.isLoading}
            warnings={quality.data?.warnings ?? []}
            availableEvidence={quality.data?.available_evidence ?? {}}
            missingSections={quality.data?.missing_sections ?? []}
          />
        ) : (
          <p className="mt-3 text-sm text-raven-muted">
            Select one investigation to preview quality warnings, or several for
            partial-safe bulk generation.
          </p>
        )}
      </section>

      <ReportFilters
        filters={filters}
        allowedFormats={allowedFormats}
        investigations={investigations.data?.items ?? []}
        analysts={analysts.data?.items ?? []}
        onChange={setFilters}
      />

      {reportItems.length ? (
        <div className="overflow-x-auto rounded-lg border border-raven-border">
          <table className="min-w-[1180px] w-full text-left text-sm">
            <thead className="bg-raven-panelSoft text-xs uppercase text-raven-muted">
              <tr>
                <th className="px-4 py-3">Report</th>
                <th className="px-4 py-3">Investigation</th>
                <th className="px-4 py-3">Type / template</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Generated</th>
                <th className="px-4 py-3">Size</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-raven-border bg-raven-panel/75">
              {reportItems.map((report) => (
                <ReportRow
                  key={report.id}
                  report={report}
                  downloading={downloading}
                  allowedFormats={allowedFormats}
                  lifecyclePending={
                    lifecycleMutation.isPending &&
                    lifecycleMutation.variables?.reportId === report.id
                  }
                  onDownload={handleDownload}
                  onLifecycle={(action) =>
                    lifecycleMutation.mutate({ action, reportId: report.id })
                  }
                />
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyBlock
          title="No reports eatch"
          message="The Reporting Center collects analyst-approved exports across accessible investigations."
          nextStep="Clear filters or generate a report after findings, notes, or evidence are available."
          permission="Viewers can download existing reports; contributors can generate thee."
        />
      )}
      <p className="mt-3 text-sm text-raven-muted">
        Showing {reportItems.length} of {reports.data?.total ?? 0} reports.
      </p>
    </>
  );
}

function ReportFilters({
  filters,
  allowedFormats,
  investigations,
  analysts,
  onChange,
}: {
  filters: ReportingCenterFilters;
  allowedFormats: ReportFormat[];
  investigations: Array<{ id: string; title: string }>;
  analysts: Array<{ user_id: string; username: string }>;
  onChange: (filters: ReportingCenterFilters) => void;
}): JSX.Element {
  return (
    <section className="mb-5 grid min-w-0 gap-3 overflow-hidden rounded-lg border border-raven-border bg-raven-panel/85 p-4 md:grid-cols-2 xl:grid-cols-4">
      <FilterSelect
        label="Report type"
        value={filters.report_type ?? ""}
        options={reportTypes}
        onChange={(value) =>
          onChange({
            ...filters,
            report_type: value ? (value as ReportType) : undefined,
          })
        }
      />
      <FilterSelect
        label="Status"
        value={filters.status ?? ""}
        options={reportStatuses}
        onChange={(value) =>
          onChange({
            ...filters,
            status: value ? (value as ReportStatus) : undefined,
          })
        }
      />
      <FilterSelect
        label="Format"
        value={filters.format ?? ""}
        options={allowedFormats}
        onChange={(value) =>
          onChange({
            ...filters,
            format: value ? (value as ReportFormat) : undefined,
          })
        }
      />
      <FilterSelect
        label="Investigation"
        value={filters.investigation_id ?? ""}
        options={investigations.map((item) => item.id)}
        labels={Object.fromEntries(
          investigations.map((item) => [item.id, item.title]),
        )}
        onChange={(value) =>
          onChange({ ...filters, investigation_id: value || undefined })
        }
      />
      <FilterSelect
        label="Generated by"
        value={filters.generated_by ?? ""}
        options={analysts.map((item) => item.user_id)}
        labels={Object.fromEntries(
          analysts.map((item) => [item.user_id, item.username]),
        )}
        onChange={(value) =>
          onChange({ ...filters, generated_by: value || undefined })
        }
      />
      <FilterSelect
        label="Archive state"
        value={
          filters.archived === undefined
            ? ""
            : filters.archived
              ? "archived"
              : "active"
        }
        options={["active", "archived"]}
        onChange={(value) =>
          onChange({
            ...filters,
            archived: value ? value === "archived" : undefined,
          })
        }
      />
      <Field label="Start date">
        <input
          type="date"
          value={filters.start_date?.slice(0, 10) ?? ""}
          onChange={(event) =>
            onChange({
              ...filters,
              start_date: event.target.value
                ? `${event.target.value}T00:00:00Z`
                : undefined,
            })
          }
          className="input-base"
        />
      </Field>
      <Field label="End date">
        <input
          type="date"
          value={filters.end_date?.slice(0, 10) ?? ""}
          onChange={(event) =>
            onChange({
              ...filters,
              end_date: event.target.value
                ? `${event.target.value}T23:59:59Z`
                : undefined,
            })
          }
          className="input-base"
        />
      </Field>
      <FilterSelect
        label="Sort"
        value={filters.sort ?? "newest"}
        options={sortOptions}
        allowEmpty={false}
        onChange={(value) =>
          onChange({ ...filters, sort: value as ReportSort })
        }
      />
    </section>
  );
}

function ReportRow({
  report,
  downloading,
  allowedFormats,
  lifecyclePending,
  onDownload,
  onLifecycle,
}: {
  report: ReportingCenterItem;
  downloading: string | null;
  allowedFormats: ReportFormat[];
  lifecyclePending: boolean;
  onDownload: (
    report: ReportingCenterItem,
    format: ReportFormat,
  ) => Promise<void>;
  onLifecycle: (action: "archive" | "restore" | "retry") => void;
}): JSX.Element {
  return (
    <tr className="align-top">
      <td className="px-4 py-4">
        <div className="flex items-center gap-2 font-medium">
          <FileText className="h-4 w-4 text-raven-cyan" aria-hidden="true" />
          {report.title ?? "Investigation report"}
        </div>
        <LongValue
          value={report.id}
          className="mt-1 text-xs text-raven-muted"
          maxLength={32}
        />
      </td>
      <td className="px-4 py-4">
        <Link
          to={`/investigations/${report.investigation_id}/reports`}
          className="font-medium text-raven-cyan hover:underline"
        >
          {report.investigation_title}
        </Link>
        <LongValue
          value={report.investigation_id}
          className="mt-1 text-xs text-raven-muted"
          maxLength={28}
        />
      </td>
      <td className="px-4 py-4 text-raven-muted">
        <p className="capitalize">{humanize(report.report_type)}</p>
        <p className="mt-1 text-xs">{report.template_name ?? "Default template"}</p>
      </td>
      <td className="px-4 py-4">
        <ReportStatusBadge status={report.status} />
        <p className="mt-2 max-w-48 text-xs text-raven-muted">
          {report.progress_label}
        </p>
        {report.failure_reason ? (
          <p className="mt-2 max-w-64 whitespace-pre-wrap text-xs text-rose-200">
            {report.failure_reason}
          </p>
        ) : null}
      </td>
      <td className="px-4 py-4 text-raven-muted">
        <p>{new Date(report.created_at).toLocaleString()}</p>
        <p className="mt-1 text-xs">
          {report.generated_by_name ?? report.generated_by ?? "Unknown"}
        </p>
      </td>
      <td className="px-4 py-4 text-raven-muted">
        {formatBytes(report.file_size_bytes)}
      </td>
      <td className="px-4 py-4">
        <div className="flex max-w-72 flex-wrap gap-2">
          {allowedFormats.map((outputFormat) => {
            const key = `${report.id}:${outputFormat}`;
            return (
              <button
                key={outputFormat}
                type="button"
                title={`Download ${outputFormat.toUpperCase()}`}
                onClick={() => void onDownload(report, outputFormat)}
                disabled={
                  !["ready", "archived"].includes(report.status) ||
                  downloading === key
                }
                className="inline-flex h-8 items-center gap-1 rounded border border-raven-border px-2 text-xs uppercase hover:border-raven-violet disabled:opacity-40"
              >
                {downloading === key ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Download className="h-3.5 w-3.5" />
                )}
                {outputFormat}
              </button>
            );
          })}
          {report.status === "failed" ? (
            <RowAction
              label="Retry"
              icon={RotateCcw}
              pending={lifecyclePending}
              onClick={() => onLifecycle("retry")}
            />
          ) : null}
          {report.status === "archived" ? (
            <RowAction
              label="Restore"
              icon={RotateCcw}
              pending={lifecyclePending}
              onClick={() => onLifecycle("restore")}
            />
          ) : report.status === "ready" || report.status === "failed" ? (
            <RowAction
              label="Archive"
              icon={Archive}
              pending={lifecyclePending}
              onClick={() => onLifecycle("archive")}
            />
          ) : null}
        </div>
      </td>
    </tr>
  );
}

function TemplateLibrary({
  onChanged,
  onToast,
}: {
  onChanged: () => void;
  onToast: (toast: ToastState) => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const templates = useQuery({
    queryKey: ["report-templates", "admin"],
    queryFn: () => listReportTemplates(true),
  });
  const templateItems = templates.data?.items ?? [];
  const [draft, setDraft] = useState<ReportTemplateCreateRequest>({
    name: "",
    description: "",
    report_type: "technical",
    sections: ["scope", "findings_summary", "appendix"],
    is_default: false,
    is_active: true,
  });
  const [pendingRemoval, setPendingRemoval] = useState<ReportTemplate | null>(
    null,
  );
  const createMutation = useMutation({
    mutationFn: () => createReportTemplate(draft),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["report-templates"] });
      setDraft((current) => ({ ...current, name: "", description: "" }));
      onChanged();
      onToast({ kind: "success", message: "Report template created." });
    },
    onError: (error) =>
      onToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Template creation failed.",
      }),
  });
  const updateMutation = useMutation({
    mutationFn: ({
      id,
      isActive,
    }: {
      id: string;
      isActive: boolean;
    }) => updateReportTemplate(id, { is_active: isActive }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["report-templates"] });
      onChanged();
      onToast({ kind: "success", message: "Report template restored." });
    },
    onError: (error) =>
      onToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Template update failed.",
      }),
  });
  const deactivateMutation = useMutation({
    mutationFn: (templateId: string) => deactivateReportTemplate(templateId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["report-templates"] });
      setPendingRemoval(null);
      onChanged();
      onToast({
        kind: "success",
        message: "Custom report template removed from active use.",
      });
    },
    onError: (error) =>
      onToast({
        kind: "error",
        message:
          error instanceof Error ? error.message : "Template removal failed.",
      }),
  });

  return (
    <section className="mb-5 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <h2 className="font-semibold">Safe template library</h2>
      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <Field label="Name">
          <input
            value={draft.name}
            onChange={(event) =>
              setDraft((current) => ({ ...current, name: event.target.value }))
            }
            className="input-base"
          />
        </Field>
        <Field label="Report type">
          <select
            value={draft.report_type}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                report_type: event.target.value as ReportType,
              }))
            }
            className="input-base"
          >
            {reportTypes.map((item) => (
              <option key={item} value={item}>
                {humanize(item)}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Description">
          <input
            value={draft.description}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                description: event.target.value,
              }))
            }
            className="input-base"
          />
        </Field>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {safeSections.map((section) => {
          const selected = draft.sections.includes(section);
          return (
            <label
              key={section}
              className={[
                "inline-flex cursor-pointer items-center gap-2 rounded border px-2 py-1 text-xs",
                selected
                  ? "border-raven-violet bg-raven-violet/15 text-raven-text"
                  : "border-raven-border text-raven-muted",
              ].join(" ")}
            >
              <input
                type="checkbox"
                checked={selected}
                onChange={() =>
                  setDraft((current) => ({
                    ...current,
                    sections: selected
                      ? current.sections.filter((item) => item !== section)
                      : [...current.sections, section],
                  }))
                }
                className="sr-only"
              />
              {humanize(section)}
            </label>
          );
        })}
      </div>
      <div className="mt-4 flex items-center justify-between gap-3">
        <label className="inline-flex items-center gap-2 text-sm text-raven-muted">
          <input
            type="checkbox"
            checked={draft.is_default}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                is_default: event.target.checked,
              }))
            }
          />
          Default for this report type
        </label>
        <button
          type="button"
          onClick={() => createMutation.mutate()}
          disabled={
            createMutation.isPending ||
            draft.name.trim().length < 2 ||
            draft.description.trim().length < 2 ||
            draft.sections.length === 0
          }
          className="inline-flex items-center gap-2 rounded-md bg-raven-violet px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          {createMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <FilePlus2 className="h-4 w-4" />
          )}
          Create template
        </button>
      </div>
      <div className="mt-5 grid gap-3 lg:grid-cols-2">
        {templateItems.map((template) => (
          <div
            key={template.id}
            className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-medium">{template.name}</p>
                <p className="mt-1 text-xs text-raven-muted">
                  {humanize(template.report_type)} · {(template.sections ?? []).length} sections
                </p>
              </div>
              {template.created_by === null ? (
                <span className="rounded border border-raven-border px-2 py-1 text-xs text-raven-muted">
                  Built-in
                </span>
              ) : template.is_active ? (
                <button
                  type="button"
                  onClick={() => setPendingRemoval(template)}
                  className="rounded border border-rose-400/30 px-2 py-1 text-xs text-rose-100 hover:bg-rose-500/10"
                >
                  Remove
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() =>
                    updateMutation.mutate({
                      id: template.id,
                      isActive: true,
                    })
                  }
                  className="rounded border border-raven-border px-2 py-1 text-xs hover:border-raven-violet"
                >
                  Restore
                </button>
              )}
            </div>
            <p className="mt-2 text-sm text-raven-muted">{template.description}</p>
            <p className="mt-2 text-xs text-raven-muted">
              Recommended when{" "}
              {reportGuidance[template.report_type].recommendedWhen}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {(template.sections ?? []).map((section) => (
                <span
                  key={section}
                  className="rounded border border-raven-border px-2 py-0.5 text-xs text-raven-muted"
                >
                  {humanize(section)}
                </span>
              ))}
            </div>
            {!template.is_active ? (
              <p className="mt-2 text-xs text-amber-200">
                Inactive templates are hidden from report generation.
              </p>
            ) : null}
          </div>
        ))}
      </div>
      {pendingRemoval ? (
        <TemplateRemovalModal
          template={pendingRemoval}
          pending={deactivateMutation.isPending}
          onCancel={() => setPendingRemoval(null)}
          onConfirm={() => deactivateMutation.mutate(pendingRemoval.id)}
        />
      ) : null}
    </section>
  );
}

function ReportTemplatePreview({
  template,
  reportType,
}: {
  template: ReportTemplate | null;
  reportType: ReportType;
}): JSX.Element {
  const guidance = reportGuidance[template?.report_type ?? reportType];
  const sections = template?.sections ?? guidance?.emphasis ?? [];
  return (
    <div className="mt-4 rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <p className="text-sm text-raven-text">
        {template?.description ?? guidance.summary}
      </p>
      <p className="mt-1 text-xs text-raven-muted">
        Recommended when {guidance.recommendedWhen}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {sections.map((section) => (
          <span
            key={section}
            className="rounded border border-raven-border px-2 py-0.5 text-xs text-raven-muted"
          >
            {humanize(section)}
          </span>
        ))}
      </div>
    </div>
  );
}

function TemplateRemovalModal({
  template,
  pending,
  onCancel,
  onConfirm,
}: {
  template: ReportTemplate;
  pending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}): JSX.Element {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
      <div className="w-full max-w-md rounded-lg border border-raven-border bg-raven-panel p-5 shadow-glow">
        <h3 className="text-lg font-semibold">Remove custom template?</h3>
        <p className="mt-2 text-sm leading-6 text-raven-muted">
          <strong className="text-raven-text">{template.name}</strong> will be
          deactivated and hidden from generation menus. Existing reports are
          preserved, and the template can be restored later.
        </p>
        <div className="mt-5 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-raven-border px-4 py-2 text-sm text-raven-muted hover:text-raven-text disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={pending}
            className="rounded-md bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-500 disabled:opacity-60"
          >
            {pending ? "Removing" : "Remove template"}
          </button>
        </div>
      </div>
    </div>
  );
}

function InvestigationSelector({
  items,
  selected,
  onChange,
  error,
}: {
  items: Array<{ id: string; title: string; status: string; priority: string }>;
  selected: Set<string>;
  onChange: (selected: Set<string>) => void;
  error?: string;
}): JSX.Element {
  return (
    <div className="mt-4 max-h-48 overflow-y-auto rounded-md border border-raven-border bg-raven-panelSoft p-2">
      {error ? (
        <p className="p-2 text-sm text-rose-200">
          Investigation selection is unavailable: {error}
        </p>
      ) : items.length ? (
        items.map((item) => (
          <label
            key={item.id}
            className="flex cursor-pointer items-center justify-between gap-3 rounded px-2 py-2 text-sm hover:bg-white/5"
          >
            <span className="inline-flex min-w-0 items-center gap-2">
              <input
                type="checkbox"
                checked={selected.has(item.id)}
                onChange={(event) => {
                  const next = new Set(selected);
                  if (event.target.checked) {
                    next.add(item.id);
                  } else {
                    next.delete(item.id);
                  }
                  onChange(next);
                }}
              />
              <span className="truncate">{item.title}</span>
            </span>
            <span className="text-xs capitalize text-raven-muted">
              {item.priority} · {item.status}
            </span>
          </label>
        ))
      ) : (
        <p className="p-2 text-sm text-raven-muted">
          No accessible investigations are available.
        </p>
      )}
    </div>
  );
}

function QualityPreview({
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
      <p className="mt-3 inline-flex items-center gap-2 text-sm text-raven-muted">
        <Loader2 className="h-4 w-4 animate-spin" />
        Checking report quality
      </p>
    );
  }
  if (!warnings.length) {
    return (
      <div className="mt-3 rounded-md border border-emerald-400/30 bg-emerald-500/10 p-3">
        <p className="text-sm text-emerald-100">
          No report quality warnings detected.
        </p>
        <EvidenceCounts counts={availableEvidence} />
      </div>
    );
  }
  return (
    <details className="mt-3 rounded-md border border-amber-400/30 bg-amber-500/10 p-3">
      <summary className="cursor-pointer text-sm text-amber-100">
        <span className="inline-flex items-center gap-2">
          <TriangleAlert className="h-4 w-4" />
          {warnings.length} non-blocking quality warnings
        </span>
      </summary>
      <EvidenceCounts counts={availableEvidence} />
      {missingSections.length ? (
        <p className="mt-3 text-sm text-amber-100/80">
          Missing or incomplete: {missingSections.join(", ")}.
        </p>
      ) : null}
      <ul className="mt-3 min-w-0 space-y-1 break-words text-sm text-amber-100/80">
        {warnings.map((warning) => (
          <li key={warning.code}>{warning.message}</li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-amber-100/70">
        These readiness checks explain sparse sections and do not block
        analyst-approved generation.
      </p>
    </details>
  );
}

function EvidenceCounts({
  counts,
}: {
  counts: Record<string, number>;
}): JSX.Element {
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {Object.entries(counts).map(([label, count]) => (
        <span
          key={label}
          className="rounded border border-raven-border px-2 py-1 text-xs capitalize text-raven-muted"
        >
          {label.replace(/_/g, " ")}: {count}
        </span>
      ))}
    </div>
  );
}

function RowAction({
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
      className="inline-flex h-8 items-center gap-1 rounded border border-raven-border px-2 text-xs hover:border-raven-violet disabled:opacity-50"
    >
      {pending ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <Icon className="h-3.5 w-3.5" />
      )}
      {label}
    </button>
  );
}

function FilterSelect({
  label,
  value,
  options,
  labels = {},
  allowEmpty = true,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  labels?: Record<string, string>;
  allowEmpty?: boolean;
  onChange: (value: string) => void;
}): JSX.Element {
  return (
    <Field label={label}>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="input-base"
      >
        {allowEmpty ? <option value="">All</option> : null}
        {options.map((option) => (
          <option key={option} value={option}>
            {labels[option] ?? humanize(option)}
          </option>
        ))}
      </select>
    </Field>
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

async function invalidateReportingCenter(
  queryClient: ReturnType<typeof useQueryClient>,
): Promise<void> {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["reporting-center"] }),
    queryClient.invalidateQueries({ queryKey: ["report-templates"] }),
    queryClient.invalidateQueries({ queryKey: ["reports"] }),
  ]);
}

function normalizeReportFilters(
  value: Record<string, unknown>,
): ReportingCenterFilters {
  const next: ReportingCenterFilters = { sort: "newest", limit: 100 };
  if (typeof value.report_type === "string" && reportTypes.includes(value.report_type as ReportType)) {
    next.report_type = value.report_type as ReportType;
  }
  if (typeof value.status === "string" && reportStatuses.includes(value.status as ReportStatus)) {
    next.status = value.status as ReportStatus;
  }
  if (typeof value.format === "string" && formats.includes(value.format as ReportFormat)) {
    next.format = value.format as ReportFormat;
  }
  if (typeof value.investigation_id === "string") {
    next.investigation_id = value.investigation_id;
  }
  if (typeof value.generated_by === "string") {
    next.generated_by = value.generated_by;
  }
  if (typeof value.archived === "boolean") {
    next.archived = value.archived;
  }
  if (typeof value.start_date === "string") {
    next.start_date = value.start_date;
  }
  if (typeof value.end_date === "string") {
    next.end_date = value.end_date;
  }
  if (typeof value.sort === "string" && sortOptions.includes(value.sort as ReportSort)) {
    next.sort = value.sort as ReportSort;
  }
  return next;
}

function humanize(value: string): string {
  return value.replace(/_/g, " ");
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
