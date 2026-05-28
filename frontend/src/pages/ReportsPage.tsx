import { Download, FileText, Loader2, PlusCircle } from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { InvestigationTabs } from "../components/InvestigationTabs";
import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import { createReport, downloadReport, listReports } from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import type { ReportFormat, ReportSummary, ReportType } from "../types";

const formats: ReportFormat[] = ["pdf", "docx", "html", "md"];
const reportTypes: Array<{ type: ReportType; label: string }> = [
  { type: "executive", label: "Executive Report" },
  { type: "technical", label: "Technical Report" },
];

export function ReportsPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const queryClient = useQueryClient();
  const [toast, setToast] = useState<ToastState | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const reports = useQuery({
    queryKey: ["reports", investigationId],
    queryFn: () => listReports(investigationId),
  });
  const generateReport = useMutation({
    mutationFn: (reportType: ReportType) =>
      createReport(investigationId, { report_type: reportType }),
    onSuccess: async (report) => {
      await queryClient.invalidateQueries({ queryKey: ["reports", investigationId] });
      setToast({
        kind: "success",
        message: `${report.report_type} report generated and ready to download.`,
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

  async function handleDownload(
    report: ReportSummary,
    format: ReportFormat,
  ): Promise<void> {
    const downloadKey = `${report.id}:${format}`;
    setDownloading(downloadKey);
    try {
      const blob = await downloadReport(report.id, format);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${safeFilename(report.title ?? "report")}.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setToast({ kind: "success", message: `${format.toUpperCase()} download ready.` });
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
    return <ErrorBlock message={reports.error.message} />;
  }

  return (
    <>
      <PageHeader
        title="Reports"
        eyebrow="Exports"
        actions={
          <div className="flex flex-wrap gap-2">
            {reportTypes.map((item) => (
              <button
                key={item.type}
                type="button"
                onClick={() => generateReport.mutate(item.type)}
                disabled={generateReport.isPending}
                className="inline-flex items-center gap-2 rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-60"
              >
                {generateReport.isPending &&
                generateReport.variables === item.type ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <PlusCircle className="h-4 w-4" aria-hidden="true" />
                )}
                Generate {item.label}
              </button>
            ))}
          </div>
        }
      />
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}
      <InvestigationTabs />
      {reports.data?.items.length ? (
        <div className="space-y-4">
          {reports.data.items.map((report) => (
            <article
              key={report.id}
              className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"
            >
              <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-raven-cyan" aria-hidden="true" />
                    <h2 className="font-semibold">
                      {report.title ?? "Investigation report"}
                    </h2>
                  </div>
                  <div className="mt-3 grid gap-2 text-sm text-raven-muted sm:grid-cols-2">
                    <ReportMetric label="Type" value={report.report_type} />
                    <ReportMetric label="Status" value={report.status} />
                    <ReportMetric
                      label="Created"
                      value={new Date(report.created_at).toLocaleString()}
                    />
                    <ReportMetric
                      label="Generated by"
                      value={report.generated_by ?? "unknown"}
                    />
                  </div>
                  {report.error_message ? (
                    <p className="mt-3 rounded-md border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">
                      {report.error_message}
                    </p>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-2">
                  {formats.map((format) => {
                    const key = `${report.id}:${format}`;
                    return (
                      <button
                        key={format}
                        type="button"
                        onClick={() => void handleDownload(report, format)}
                        disabled={report.status !== "ready" || downloading === key}
                        className="inline-flex items-center gap-2 rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm uppercase text-raven-text hover:border-raven-violet disabled:opacity-60"
                      >
                        {downloading === key ? (
                          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                        ) : (
                          <Download className="h-4 w-4" aria-hidden="true" />
                        )}
                        {format}
                      </button>
                    );
                  })}
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyBlock message="No reports are stored for this investigation. Generate an executive or technical report from stored findings, recon, analysis, and citations." />
      )}
    </>
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
      <p className="mt-1 break-all text-raven-text">{value}</p>
    </div>
  );
}

function safeFilename(value: string): string {
  return (
    value
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "report"
  );
}
