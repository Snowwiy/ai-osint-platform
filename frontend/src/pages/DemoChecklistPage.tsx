import {
  CheckCircle2,
  CircleAlert,
  Database,
  FileCheck2,
  FlaskConical,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import { clearDemoWorkspace, getAdminQaStatus, seedDemoWorkspace } from "../lib/api";
import { safeArray, safeDate, safeNumber } from "../lib/safe";
import { useAuth } from "../lib/useAuth";
import { useState } from "react";

export function DemoChecklistPage(): JSX.Element {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [toast, setToast] = useState<ToastState | null>(null);
  const qa = useQuery({
    queryKey: ["admin-qa-status"],
    queryFn: getAdminQaStatus,
    enabled: user?.role === "admin",
    staleTime: 15_000,
  });
  const seedDemo = useMutation({
    mutationFn: seedDemoWorkspace,
    onSuccess: async (result) => {
      setToast({ kind: "success", message: result.message });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-qa-status"] }),
        queryClient.invalidateQueries({ queryKey: ["investigations"] }),
      ]);
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Demo setup failed.",
      });
    },
  });
  const clearDemo = useMutation({
    mutationFn: clearDemoWorkspace,
    onSuccess: async (result) => {
      setToast({ kind: "success", message: result.message });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-qa-status"] }),
        queryClient.invalidateQueries({ queryKey: ["investigations"] }),
      ]);
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Demo clear failed.",
      });
    },
  });

  if (user?.role !== "admin") {
    return (
      <>
        <PageHeader title="Demo Checklist" eyebrow="Admin only" />
        <ErrorBlock message="Administrator access is required." />
      </>
    );
  }
  if (qa.isLoading) {
    return <LoadingBlock label="Checking commercial demo readiness" />;
  }
  if (qa.isError || !qa.data) {
    return (
      <ErrorBlock
        message={qa.error?.message ?? "QA readiness data is unavailable."}
      />
    );
  }

  const status = qa.data;
  const featureFlags = status.feature_flags ?? {};
  const components = status.components ?? {};
  const warnings = safeArray(status.warnings);
  const generatedAt = safeDate(status.generated_at);
  const enabledFlags = Object.values(featureFlags).filter(Boolean).length;
  const exportReady =
    featureFlags.enable_report_exports &&
    components.storage?.status === "ok";

  return (
    <>
      <PageHeader
        title="Demo Checklist"
        eyebrow="Commercial readiness"
        actions={
          <button
            type="button"
            onClick={() => {
              setToast(null);
              void qa.refetch();
            }}
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm hover:border-raven-violet"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </button>
        }
      />
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}

      <section className="mb-5 rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <h2 className="font-semibold">RavenTech OSINT {status.app_version}</h2>
            <p className="mt-1 text-sm text-raven-muted">
              Environment: {status.environment}. Generated{" "}
              {generatedAt ? generatedAt.toLocaleString() : "time unavailable"}.
            </p>
          </div>
          <ReadinessBadge
            ready={
              status.migration_status === "ok" &&
              warnings.length === 0
            }
          />
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <ChecklistCard
          icon={ShieldCheck}
          title="Platform health"
          status={components.database?.status ?? "error"}
          detail={
            components.database?.detail ?? "Database status unavailable."
          }
        />
        <ChecklistCard
          icon={Database}
          title="Database migrations"
          status={status.migration_status}
          detail={`${status.current_migration || "unknown"} / ${status.head_migration || "unknown"}`}
        />
        <ChecklistCard
          icon={FileCheck2}
          title="Report exports"
          status={exportReady ? "ok" : "degraded"}
          detail={
            exportReady
              ? "Export feature and report storage are available."
              : "Review export controls, feature flags, or storage readiness."
          }
        />
        <ChecklistCard
          icon={ShieldCheck}
          title="Audit readiness"
          status={status.audit_count > 0 ? "ok" : "degraded"}
          detail={`${safeNumber(status.audit_count)} audit event${safeNumber(status.audit_count) === 1 ? "" : "s"} stored.`}
        />
        <ChecklistCard
          icon={FileCheck2}
          title="Report templates"
          status={safeNumber(status.report_templates_count) > 0 ? "ok" : "error"}
          detail={`${safeNumber(status.report_templates_count)} safe template${safeNumber(status.report_templates_count) === 1 ? "" : "s"} available.`}
        />
        <ChecklistCard
          icon={ShieldCheck}
          title="Governance"
          status={enabledFlags > 0 ? "ok" : "degraded"}
          detail={`${enabledFlags} of ${Object.keys(featureFlags).length} feature flags enabled.`}
        />
        <ChecklistCard
          icon={FlaskConical}
          title="Sample investigation"
          status={
            !status.demo_mode_enabled
              ? "degraded"
              : status.demo_investigation_ready
                ? "ok"
                : "degraded"
          }
          detail={
            !status.demo_mode_enabled
              ? "Demo mode is disabled. This is the production-safe default."
              : status.demo_investigation_ready
                ? "Synthetic defensive sample data is ready."
                : "Demo mode is enabled, but sample data has not been prepared."
          }
        />
        <ChecklistCard
          icon={ShieldCheck}
          title="Investigation posture"
          status="ok"
          detail={`${safeNumber(status.active_investigations_count)} active and ${safeNumber(status.archived_investigations_count)} archived.`}
        />
      </div>

      {status.demo_mode_enabled ? (
        <section className="mt-5 rounded-lg border border-cyan-400/25 bg-cyan-500/10 p-4">
          <h2 className="font-semibold text-cyan-100">Defensive demo workspace</h2>
          <p className="mt-1 text-sm text-cyan-100/75">
            The sample uses reserved identifiers, makes no live requests, and is
            clearly labeled as synthetic.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {status.demo_investigation_ready &&
            status.demo_investigation_id ? (
              <>
                <Link
                  to={`/investigations/${status.demo_investigation_id}`}
                  className="rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white"
                >
                  Open demo investigation
                </Link>
                <button
                  type="button"
                  onClick={() => clearDemo.mutate()}
                  disabled={clearDemo.isPending}
                  className="rounded-md border border-raven-border px-4 py-2 text-sm font-medium text-raven-muted hover:border-rose-400/60 hover:text-rose-100 disabled:opacity-50"
                >
                  {clearDemo.isPending ? "Clearing demo" : "Clear demo data"}
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => seedDemo.mutate()}
                disabled={seedDemo.isPending}
                className="rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {seedDemo.isPending ? "Preparing demo" : "Prepare demo workspace"}
              </button>
            )}
          </div>
        </section>
      ) : null}

      <section className="mt-5 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <h2 className="font-semibold">Known warnings</h2>
        {warnings.length ? (
          <ul className="mt-3 space-y-2 text-sm text-amber-100">
            {warnings.map((warning) => (
              <li key={warning} className="flex gap-2">
                <CircleAlert className="mt-0.5 h-4 w-4 flex-none" />
                <span>{warning}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 inline-flex items-center gap-2 text-sm text-emerald-200">
            <CheckCircle2 className="h-4 w-4" />
            No blocking demo-readiness warnings were detected.
          </p>
        )}
      </section>
    </>
  );
}

function ChecklistCard({
  icon: Icon,
  title,
  status,
  detail,
}: {
  icon: typeof ShieldCheck;
  title: string;
  status: string;
  detail: string;
}): JSX.Element {
  const tone =
    status === "ok"
      ? "text-emerald-200"
      : status === "degraded"
        ? "text-amber-200"
        : "text-rose-200";
  return (
    <article className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex items-center justify-between gap-3">
        <Icon className="h-5 w-5 text-raven-cyan" aria-hidden="true" />
        <span className={`text-xs font-medium uppercase ${tone}`}>{status}</span>
      </div>
      <h2 className="mt-3 font-semibold">{title}</h2>
      <p className="mt-1 break-words text-sm leading-5 text-raven-muted">
        {detail}
      </p>
    </article>
  );
}

function ReadinessBadge({ ready }: { ready: boolean }): JSX.Element {
  return (
    <span
      className={[
        "rounded-md border px-3 py-1.5 text-sm font-medium",
        ready
          ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-200"
          : "border-amber-400/30 bg-amber-500/10 text-amber-200",
      ].join(" ")}
    >
      {ready ? "Demo ready" : "Review recommended"}
    </span>
  );
}
