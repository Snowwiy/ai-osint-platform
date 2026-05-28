import { Download } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { downloadReport, listReports } from "../lib/api";
import { useInvestigationId } from "../lib/hooks";

const formats = ["html", "md", "pdf", "docx"] as const;

export function ReportsPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const reports = useQuery({
    queryKey: ["reports", investigationId],
    queryFn: () => listReports(investigationId),
  });

  async function handleDownload(
    reportId: string,
    format: (typeof formats)[number],
  ): Promise<void> {
    const blob = await downloadReport(reportId, format);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `report-${reportId}.${format}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  }

  if (reports.isLoading) {
    return <LoadingBlock label="Loading reports" />;
  }
  if (reports.isError) {
    return <ErrorBlock message={reports.error.message} />;
  }

  return (
    <>
      <PageHeader title="Reports" eyebrow="Exports" />
      {reports.data?.items.length ? (
        <div className="space-y-4">
          {reports.data.items.map((report) => (
            <article
              key={report.id}
              className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"
            >
              <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div>
                  <h2 className="font-semibold">{report.title ?? "Investigation report"}</h2>
                  <p className="mt-2 text-sm text-raven-muted">
                    {report.report_type} · {report.status} ·{" "}
                    {new Date(report.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {formats.map((format) => (
                    <button
                      key={format}
                      type="button"
                      onClick={() => void handleDownload(report.id, format)}
                      className="inline-flex items-center gap-2 rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm uppercase text-raven-text hover:border-raven-violet"
                    >
                      <Download className="h-4 w-4" aria-hidden="true" />
                      {format}
                    </button>
                  ))}
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyBlock message="No reports are stored for this investigation." />
      )}
    </>
  );
}

