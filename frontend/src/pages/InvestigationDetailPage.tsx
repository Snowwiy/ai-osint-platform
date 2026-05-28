import {
  BrainCircuit,
  CheckCircle2,
  FileText,
  GitGraph,
  Network,
  Pencil,
  ShieldAlert,
  Target,
  Trash2,
} from "lucide-react";
import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DeleteInvestigationModal } from "../components/DeleteInvestigationModal";
import {
  InvestigationEditModal,
  type InvestigationEditValues,
} from "../components/InvestigationEditModal";
import { InvestigationTabs } from "../components/InvestigationTabs";
import { PageHeader } from "../components/PageHeader";
import { StatCard } from "../components/StatCard";
import { ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { StatusBadge } from "../components/StatusBadge";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import {
  deleteInvestigation,
  getCorrelations,
  getInvestigation,
  getInvestigationGraph,
  getTimeline,
  listFindings,
  listReports,
  listTargets,
  updateInvestigation,
} from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import { useAuth } from "../lib/useAuth";
import type { Finding, GraphNode, Target as InvestigationTarget } from "../types";

export function InvestigationDetailPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);

  const investigation = useQuery({
    queryKey: ["investigation", investigationId],
    queryFn: () => getInvestigation(investigationId),
  });
  const targets = useQuery({
    queryKey: ["targets", investigationId],
    queryFn: () => listTargets(investigationId),
  });
  const graph = useQuery({
    queryKey: ["graph", investigationId],
    queryFn: () => getInvestigationGraph(investigationId),
  });
  const findings = useQuery({
    queryKey: ["findings", investigationId],
    queryFn: () => listFindings(investigationId),
  });
  const timeline = useQuery({
    queryKey: ["timeline", investigationId],
    queryFn: () => getTimeline(investigationId),
  });
  const correlations = useQuery({
    queryKey: ["correlations", investigationId],
    queryFn: () => getCorrelations(investigationId),
  });
  const reports = useQuery({
    queryKey: ["reports", investigationId],
    queryFn: () => listReports(investigationId),
  });

  const updateMutation = useMutation({
    mutationFn: (values: InvestigationEditValues) =>
      updateInvestigation(investigationId, values),
    onSuccess: async (updated) => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["investigation", investigationId],
        }),
        queryClient.invalidateQueries({ queryKey: ["investigations"] }),
      ]);
      setIsEditing(false);
      if (updated.status === "archived") {
        navigate("/investigations", {
          replace: true,
          state: {
            toast: {
              kind: "success",
              message: "Investigation archived.",
            } satisfies ToastState,
          },
        });
        return;
      }
      setToast({ kind: "success", message: "Investigation updated." });
    },
  });
  const deleteMutation = useMutation({
    mutationFn: () => deleteInvestigation(investigationId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["investigations"] });
      navigate("/investigations", {
        replace: true,
        state: {
          toast: {
            kind: "success",
            message: "Investigation deleted.",
          } satisfies ToastState,
        },
      });
    },
  });

  if (investigation.isLoading) {
    return <LoadingBlock label="Loading investigation" />;
  }
  if (investigation.isError) {
    return <ErrorBlock message={investigation.error.message} />;
  }

  const item = investigation.data;
  if (item?.status === "archived") {
    return <Navigate to="/investigations" replace />;
  }
  const canManage = item
    ? canManageInvestigation(item.owner_id, user?.id, user?.role)
    : false;
  const findingItems = findings.data ?? [];
  const graphNodes = graph.data?.nodes ?? [];
  const targetItems = targets.data?.items ?? [];
  const health = buildHealthSummary(
    findingItems,
    graphNodes,
    targetItems,
    timeline.data?.total ?? 0,
    reports.data?.total ?? 0,
  );

  return (
    <>
      <PageHeader
        title={item?.title ?? "Investigation"}
        eyebrow="Investigation"
        actions={
          canManage ? (
            <>
              <button
                type="button"
                onClick={() => {
                  updateMutation.reset();
                  setIsEditing(true);
                }}
                className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-text hover:border-raven-violet"
              >
                <Pencil className="h-4 w-4" aria-hidden="true" />
                Edit
              </button>
              <button
                type="button"
                onClick={() => {
                  deleteMutation.reset();
                  setIsDeleting(true);
                }}
                className="inline-flex items-center gap-2 rounded-md border border-rose-400/30 px-3 py-2 text-sm text-rose-100 hover:bg-rose-500/10"
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
                Delete
              </button>
            </>
          ) : null
        }
      />
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}
      <InvestigationTabs />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        <StatCard
          label="Targets"
          value={targets.data?.total ?? 0}
          icon={<Target className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Entities"
          value={graph.data?.nodes.length ?? 0}
          icon={<Network className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Findings"
          value={findings.data?.length ?? 0}
          icon={<ShieldAlert className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Timeline"
          value={timeline.data?.total ?? 0}
          icon={<BrainCircuit className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Correlations"
          value={correlations.data?.total_edges ?? 0}
          icon={<GitGraph className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Reports"
          value={reports.data?.total ?? 0}
          icon={<FileText className="h-5 w-5" aria-hidden="true" />}
        />
      </div>

      <HealthSummary health={health} />

      <section className="mt-8 grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
        <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
          <h2 className="text-lg font-semibold">Scope</h2>
          <p className="mt-3 text-sm leading-6 text-raven-muted">
            {item?.scope_definition ?? item?.description ?? "No scope note stored."}
          </p>
          <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-raven-muted">
            Authorization
          </h3>
          <div className="mt-2 flex items-center gap-2 text-sm text-emerald-100">
            <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            Authorization statement stored
          </div>
          <p className="mt-3 text-sm leading-6 text-raven-text">
            {item?.authorization_statement}
          </p>
        </div>

        <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
          <h2 className="text-lg font-semibold">Workspace</h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex items-center justify-between gap-4">
              <dt className="text-raven-muted">Status</dt>
              <dd>
                <StatusBadge status={item?.status ?? "draft"} />
              </dd>
            </div>
            <Detail
              label="Owner"
              value={item ? ownerContext(item.owner_id, user?.id, user?.role) : ""}
            />
            <Detail label="Targets" value={`${targets.data?.total ?? 0}`} />
            <Detail label="Findings" value={`${findings.data?.length ?? 0}`} />
            <Detail
              label="Created"
              value={item ? new Date(item.created_at).toLocaleString() : ""}
            />
            <Detail
              label="Updated"
              value={item ? new Date(item.updated_at).toLocaleString() : ""}
            />
          </dl>
          <div className="mt-5 grid gap-2">
            <LinkButton to="targets" label="Add or review targets" />
            <LinkButton to="recon" label="Open recon results" />
            <LinkButton to="findings" label="Review findings" />
            <LinkButton to="reports" label="Download reports" />
          </div>
        </div>
      </section>
      {item && isEditing ? (
        <InvestigationEditModal
          investigation={item}
          error={updateMutation.error?.message}
          isSaving={updateMutation.isPending}
          onClose={() => {
            updateMutation.reset();
            setIsEditing(false);
          }}
          onSubmit={(values) => updateMutation.mutate(values)}
        />
      ) : null}
      {item && isDeleting ? (
        <DeleteInvestigationModal
          investigation={item}
          error={deleteMutation.error?.message}
          isDeleting={deleteMutation.isPending}
          onClose={() => {
            deleteMutation.reset();
            setIsDeleting(false);
          }}
          onConfirm={() => deleteMutation.mutate()}
        />
      ) : null}
    </>
  );
}

interface HealthSummaryData {
  highestRisk: number | null;
  severityCounts: Record<string, number>;
  reconCounts: Record<string, number>;
  reconCompleted: boolean;
  analysisAvailable: boolean;
  reportsGenerated: boolean;
}

function HealthSummary({ health }: { health: HealthSummaryData }): JSX.Element {
  return (
    <section className="mt-6 grid gap-4 xl:grid-cols-3">
      <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <h2 className="text-lg font-semibold">Risk Overview</h2>
        <p className="mt-2 text-sm text-raven-muted">
          {health.highestRisk === null
            ? "No risk score is available yet."
            : `Highest current risk score: ${health.highestRisk}/100`}
        </p>
        <div className="mt-4 grid grid-cols-5 gap-2 text-center text-xs">
          {(["critical", "high", "medium", "low", "info"] as const).map((severity) => (
            <div
              key={severity}
              className="rounded-md border border-raven-border bg-raven-panelSoft p-2"
            >
              <p className="capitalize text-raven-muted">{severity}</p>
              <p className="mt-1 text-lg font-semibold">
                {health.severityCounts[severity] ?? 0}
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <h2 className="text-lg font-semibold">Recon Overview</h2>
        <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
          {Object.entries(health.reconCounts).map(([label, value]) => (
            <div
              key={label}
              className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
            >
              <p className="text-xs uppercase tracking-wide text-raven-muted">
                {label}
              </p>
              <p className="mt-1 text-xl font-semibold">{value}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <h2 className="text-lg font-semibold">Analysis Status</h2>
        <div className="mt-4 space-y-3">
          <StatusRow active={health.reconCompleted} label="Recon completed" />
          <StatusRow active={health.analysisAvailable} label="Analysis available" />
          <StatusRow active={health.reportsGenerated} label="Reports generated" />
        </div>
      </div>
    </section>
  );
}

function StatusRow({
  active,
  label,
}: {
  active: boolean;
  label: string;
}): JSX.Element {
  return (
    <div className="flex items-center justify-between rounded-md border border-raven-border bg-raven-panelSoft p-3 text-sm">
      <span className="text-raven-muted">{label}</span>
      <span
        className={[
          "rounded border px-2 py-1 text-xs",
          active
            ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-100"
            : "border-raven-border text-raven-muted",
        ].join(" ")}
      >
        {active ? "Ready" : "Pending"}
      </span>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-raven-muted">{label}</dt>
      <dd className="text-right text-raven-text">{value}</dd>
    </div>
  );
}

function ownerContext(
  ownerId: string,
  userId: string | undefined,
  role: string | undefined,
): string {
  if (ownerId === userId) {
    return "You";
  }
  if (role === "admin") {
    return "Admin access";
  }
  return ownerId;
}

function canManageInvestigation(
  ownerId: string,
  userId: string | undefined,
  role: string | undefined,
): boolean {
  return ownerId === userId || role === "admin";
}

function buildHealthSummary(
  findings: Finding[],
  graphNodes: GraphNode[],
  targets: InvestigationTarget[],
  timelineCount: number,
  reportCount: number,
): HealthSummaryData {
  const severityCounts = {
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
    info: 0,
  };
  for (const finding of findings) {
    severityCounts[finding.severity] += 1;
  }
  const highestRisk =
    findings.length > 0
      ? Math.max(...findings.map((finding) => finding.risk_score))
      : null;
  return {
    highestRisk,
    severityCounts,
    reconCounts: {
      domains: countEntities(graphNodes, "Domain"),
      subdomains: countEntities(graphNodes, "Subdomain"),
      ips: countEntities(graphNodes, "IPAddress"),
      urls: targets.filter((target) => target.target_type === "url").length,
      technologies: countEntities(graphNodes, "Technology"),
      services: countEntities(graphNodes, "Service"),
    },
    reconCompleted: graphNodes.length > 0 || timelineCount > 0,
    analysisAvailable: findings.length > 0,
    reportsGenerated: reportCount > 0,
  };
}

function countEntities(nodes: GraphNode[], entityType: string): number {
  return nodes.filter((node) => node.entity_type === entityType).length;
}

function LinkButton({ to, label }: { to: string; label: string }): JSX.Element {
  return (
    <Link
      to={to}
      className="rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm text-raven-text hover:border-raven-violet"
    >
      {label}
    </Link>
  );
}
