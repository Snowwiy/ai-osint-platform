import { Activity, FileText, FolderKanban, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { StatCard } from "../components/StatCard";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { listFindings, listInvestigations, listReports } from "../lib/api";

export function DashboardPage(): JSX.Element {
  const investigations = useQuery({
    queryKey: ["investigations"],
    queryFn: listInvestigations,
  });

  const firstInvestigation = investigations.data?.items[0];
  const findings = useQuery({
    queryKey: ["findings", firstInvestigation?.id],
    queryFn: () => listFindings(firstInvestigation?.id ?? ""),
    enabled: Boolean(firstInvestigation),
  });
  const reports = useQuery({
    queryKey: ["reports", firstInvestigation?.id],
    queryFn: () => listReports(firstInvestigation?.id ?? ""),
    enabled: Boolean(firstInvestigation),
  });

  if (investigations.isLoading) {
    return <LoadingBlock label="Loading dashboard" />;
  }
  if (investigations.isError) {
    return <ErrorBlock message={investigations.error.message} />;
  }

  const totalInvestigations = investigations.data?.total ?? 0;
  const active = investigations.data?.items.filter((item) => item.status === "active");
  const highFindings =
    findings.data?.filter((item) => item.severity === "high" || item.severity === "critical")
      .length ?? 0;

  return (
    <>
      <PageHeader title="Dashboard" eyebrow="Operations" />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Investigations"
          value={totalInvestigations}
          detail={`${active?.length ?? 0} active`}
          icon={<FolderKanban className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Recent findings"
          value={findings.data?.length ?? 0}
          detail={firstInvestigation ? firstInvestigation.title : "No investigation selected"}
          icon={<ShieldAlert className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="High risk"
          value={highFindings}
          detail="From the most recent investigation"
          icon={<Activity className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Reports"
          value={reports.data?.total ?? 0}
          detail="Available for download"
          icon={<FileText className="h-5 w-5" aria-hidden="true" />}
        />
      </div>

      <section className="mt-8">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Recent investigations</h2>
          <Link
            to="/investigations"
            className="rounded-md border border-raven-border px-3 py-1.5 text-sm text-raven-muted hover:border-raven-violet hover:text-raven-text"
          >
            View all
          </Link>
        </div>
        {investigations.data?.items.length ? (
          <div className="overflow-hidden rounded-lg border border-raven-border">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="bg-raven-panelSoft text-xs uppercase text-raven-muted">
                <tr>
                  <th className="px-4 py-3">Title</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-raven-border bg-raven-panel/70">
                {investigations.data.items.slice(0, 6).map((item) => (
                  <tr key={item.id}>
                    <td className="px-4 py-3">
                      <Link
                        to={`/investigations/${item.id}`}
                        className="font-medium text-raven-text hover:text-raven-cyan"
                      >
                        {item.title}
                      </Link>
                    </td>
                    <td className="px-4 py-3 capitalize text-raven-muted">{item.status}</td>
                    <td className="px-4 py-3 text-raven-muted">
                      {new Date(item.updated_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyBlock message="No investigations are available for this account." />
        )}
      </section>
    </>
  );
}

