import {
  Bookmark,
  BrainCircuit,
  CalendarClock,
  CheckCircle2,
  FileText,
  GitGraph,
  Gauge,
  ArchiveRestore,
  ListTodo,
  Network,
  Pencil,
  RefreshCw,
  Sparkles,
  ShieldAlert,
  StickyNote,
  Tags,
  Target,
  Trash2,
  UserPlus,
  Wrench,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DeleteInvestigationModal } from "../components/DeleteInvestigationModal";
import {
  InvestigationEditModal,
  type InvestigationEditValues,
} from "../components/InvestigationEditModal";
import { InvestigationTabs } from "../components/InvestigationTabs";
import { OperationalCoordinationPanel } from "../components/OperationalCoordinationPanel";
import { PageHeader } from "../components/PageHeader";
import { PurgeInvestigationModal } from "../components/PurgeInvestigationModal";
import { StatCard } from "../components/StatCard";
import { ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { StatusBadge } from "../components/StatusBadge";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import {
  deleteInvestigation,
  closeCase,
  decideCaseReview,
  generateInvestigationSummary,
  getCorrelations,
  getEngagement,
  getExecutiveInvestigationSummary,
  getInvestigation,
  getInvestigationAnalytics,
  getInvestigationGraph,
  getInvestigationReadiness,
  getInvestigationRiskScore,
  getCaseReview,
  getEvidenceCompleteness,
  getInvestigationTags,
  getTimeline,
  listFindings,
  listBookmarks,
  listAuthorizationEvidence,
  listEngagementScopeItems,
  listEngagements,
  listInvestigationMembers,
  listPlaybookRuns,
  listNotes,
  listReports,
  listTags,
  listTargets,
  listTasks,
  purgeInvestigation,
  restoreInvestigation,
  submitCaseReview,
  updateInvestigation,
  updateInvestigationPriority,
  updateInvestigationStage,
  updateInvestigationTags,
} from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import { rememberInvestigation } from "../lib/recentInvestigations";
import { useAuth } from "../lib/useAuth";
import type {
  CountItem,
  CaseReviewResponse,
  AuthorizationEvidence,
  Engagement,
  EngagementScopeItem,
  EvidenceCompletenessResponse,
  ExecutiveInvestigationSummaryResponse,
  Finding,
  Investigation,
  InvestigationAnalyticsResponse,
  InvestigationNote,
  InvestigationPriority,
  InvestigationReadinessResponse,
  InvestigationRiskScoreResponse,
  InvestigationStage,
  InvestigationSummaryResponse,
  InvestigationTag,
  InvestigationStatus,
  InvestigationTask,
  PlaybookRun,
  Severity,
} from "../types";

export function InvestigationDetailPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isPurging, setIsPurging] = useState(false);
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
  const analytics = useQuery({
    queryKey: ["investigation-analytics", investigationId],
    queryFn: () => getInvestigationAnalytics(investigationId),
  });
  const readiness = useQuery({
    queryKey: ["investigation-readiness", investigationId],
    queryFn: () => getInvestigationReadiness(investigationId),
  });
  const executiveSummary = useQuery({
    queryKey: ["executive-summary", investigationId],
    queryFn: () => getExecutiveInvestigationSummary(investigationId),
  });
  const riskScore = useQuery({
    queryKey: ["investigation-risk-score", investigationId],
    queryFn: () => getInvestigationRiskScore(investigationId),
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
  const notes = useQuery({
    queryKey: ["notes", investigationId],
    queryFn: () => listNotes(investigationId),
  });
  const tasks = useQuery({
    queryKey: ["tasks", investigationId],
    queryFn: () => listTasks(investigationId),
  });
  const bookmarks = useQuery({
    queryKey: ["bookmarks", investigationId],
    queryFn: () => listBookmarks(investigationId),
  });
  const playbookRuns = useQuery({
    queryKey: ["playbook-runs", investigationId],
    queryFn: () => listPlaybookRuns(investigationId),
  });
  const members = useQuery({
    queryKey: ["members", investigationId],
    queryFn: () => listInvestigationMembers(investigationId),
  });
  const tags = useQuery({
    queryKey: ["investigation-tags", investigationId],
    queryFn: () => getInvestigationTags(investigationId),
  });
  const caseReview = useQuery({
    queryKey: ["case-review", investigationId],
    queryFn: () => getCaseReview(investigationId),
  });
  const completeness = useQuery({
    queryKey: ["evidence-completeness", investigationId],
    queryFn: () => getEvidenceCompleteness(investigationId),
  });
  const availableTags = useQuery({
    queryKey: ["tags"],
    queryFn: listTags,
  });
  const engagementOptions = useQuery({
    queryKey: ["engagements", false],
    queryFn: () => listEngagements(false),
  });
  const linkedEngagementId = investigation.data?.engagement_id ?? "";
  const linkedEngagement = useQuery({
    queryKey: ["engagement", linkedEngagementId],
    queryFn: () => getEngagement(linkedEngagementId),
    enabled: Boolean(linkedEngagementId),
  });
  const linkedEngagementScope = useQuery({
    queryKey: ["engagement-scope", linkedEngagementId],
    queryFn: () => listEngagementScopeItems(linkedEngagementId),
    enabled: Boolean(linkedEngagementId),
  });
  const linkedAuthorizationEvidence = useQuery({
    queryKey: ["engagement-authorization", linkedEngagementId],
    queryFn: () => listAuthorizationEvidence(linkedEngagementId),
    enabled: Boolean(linkedEngagementId),
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
        queryClient.invalidateQueries({
          queryKey: ["investigation-analytics", investigationId],
        }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-analytics"] }),
        queryClient.invalidateQueries({ queryKey: ["timeline", investigationId] }),
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
      await queryClient.invalidateQueries({ queryKey: ["dashboard-analytics"] });
      navigate("/investigations", {
        replace: true,
        state: {
          toast: {
            kind: "success",
            message: "Investigation archived.",
          } satisfies ToastState,
        },
      });
    },
  });
  const restoreMutation = useMutation({
    mutationFn: () => restoreInvestigation(investigationId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["investigation", investigationId],
        }),
        queryClient.invalidateQueries({ queryKey: ["investigations"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-analytics"] }),
        queryClient.invalidateQueries({ queryKey: ["timeline", investigationId] }),
      ]);
      setToast({ kind: "success", message: "Investigation restored." });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message:
          error instanceof Error
            ? error.message
            : "Unable to restore investigation.",
      });
    },
  });
  const purgeMutation = useMutation({
    mutationFn: () => purgeInvestigation(investigationId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["investigations"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-analytics"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-executive"] }),
      ]);
      navigate("/investigations", {
        replace: true,
        state: {
          toast: {
            kind: "success",
            message: "Archived investigation permanently deleted.",
          } satisfies ToastState,
        },
      });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message:
          error instanceof Error
            ? error.message
            : "Unable to permanently delete investigation.",
      });
    },
  });
  const summaryMutation = useMutation({
    mutationFn: () => generateInvestigationSummary(investigationId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["timeline", investigationId] });
      setToast({ kind: "success", message: "Deterministic summary generated." });
    },
    onError: (error) => {
      setToast({ kind: "error", message: error.message });
    },
  });
  const priorityMutation = useMutation({
    mutationFn: (values: {
      priority: InvestigationPriority;
      business_impact: string | null;
      due_date: string | null;
    }) => updateInvestigationPriority(investigationId, values),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["investigation", investigationId],
        }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-metrics"] }),
        queryClient.invalidateQueries({ queryKey: ["timeline", investigationId] }),
      ]);
      setToast({ kind: "success", message: "Investigation priority updated." });
    },
    onError: (error) => {
      setToast({ kind: "error", message: error.message });
    },
  });
  const tagMutation = useMutation({
    mutationFn: (tagIds: string[]) =>
      updateInvestigationTags(investigationId, tagIds),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["investigation-tags", investigationId],
        }),
        queryClient.invalidateQueries({ queryKey: ["timeline", investigationId] }),
      ]);
      setToast({ kind: "success", message: "Investigation tags updated." });
    },
    onError: (error) => {
      setToast({ kind: "error", message: error.message });
    },
  });
  const stageMutation = useMutation({
    mutationFn: ({
      stage,
      reason,
    }: {
      stage: InvestigationStage;
      reason: string;
    }) => updateInvestigationStage(investigationId, stage, reason),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["investigation", investigationId],
        }),
        queryClient.invalidateQueries({
          queryKey: ["investigation-readiness", investigationId],
        }),
        queryClient.invalidateQueries({ queryKey: ["timeline", investigationId] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-highlights"] }),
      ]);
      setToast({ kind: "success", message: "Investigation stage updated." });
    },
    onError: (error) => {
      setToast({ kind: "error", message: error.message });
    },
  });
  const reviewMutation = useMutation({
    mutationFn: async (action: {
      kind: "submit" | "approve" | "reject" | "request_changes" | "close";
      notes?: string;
      overrideReason?: string | null;
    }) => {
      if (action.kind === "submit") {
        return submitCaseReview(investigationId, action.notes);
      }
      if (action.kind === "close") {
        return closeCase(investigationId, {
          closure_reason: action.notes ?? "Case closure approved.",
          override_reason: action.overrideReason ?? null,
        });
      }
      const decision = (
        action.kind === "request_changes" ? "request_changes" : action.kind
      ) as "approve" | "reject" | "request_changes";
      return decideCaseReview(investigationId, {
        decision,
        notes: action.notes ?? "Reviewed in case workflow.",
      });
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["case-review", investigationId] }),
        queryClient.invalidateQueries({
          queryKey: ["evidence-completeness", investigationId],
        }),
        queryClient.invalidateQueries({ queryKey: ["timeline", investigationId] }),
        queryClient.invalidateQueries({ queryKey: ["review-board"] }),
        queryClient.invalidateQueries({ queryKey: ["investigation", investigationId] }),
      ]);
      setToast({ kind: "success", message: "Case review workflow updated." });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message:
          error instanceof Error
            ? error.message
            : "Unable to update case review workflow.",
      });
    },
  });
  useEffect(() => {
    if (investigation.data) {
      rememberInvestigation(investigation.data);
    }
  }, [investigation.data]);

  if (investigation.isLoading) {
    return <LoadingBlock label="Loading investigation" />;
  }
  if (investigation.isError) {
    return <ErrorBlock message={investigation.error} />;
  }

  const item = investigation.data;
  const currentMember = members.data?.find((member) => member.user_id === user?.id);
  const canManage = item
    ? canManageInvestigation(
        item.owner_id,
        user?.id,
        user?.role,
        currentMember?.role,
      )
    : false;
  const canSubmitReview =
    canManage || currentMember?.role === "analyst" || user?.role === "admin";
  return (
    <>
      <PageHeader
        title={item?.title ?? "Investigation"}
        eyebrow="Investigation"
        actions={
          canManage ? (
            <>
              {item?.status === "archived" ? (
                <>
                  <button
                    type="button"
                    onClick={() => restoreMutation.mutate()}
                    disabled={restoreMutation.isPending || purgeMutation.isPending}
                    className="inline-flex items-center gap-2 rounded-md border border-emerald-400/30 px-3 py-2 text-sm text-emerald-100 hover:bg-emerald-500/10 disabled:opacity-60"
                  >
                    <ArchiveRestore className="h-4 w-4" aria-hidden="true" />
                    {restoreMutation.isPending ? "Restoring" : "Restore"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      purgeMutation.reset();
                      setIsPurging(true);
                    }}
                    disabled={restoreMutation.isPending || purgeMutation.isPending}
                    className="inline-flex items-center gap-2 rounded-md border border-rose-400/30 px-3 py-2 text-sm text-rose-100 hover:bg-rose-500/10 disabled:opacity-60"
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                    Delete permanently
                  </button>
                </>
              ) : (
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
                    Archive
                  </button>
                </>
              )}
            </>
          ) : null
        }
      />
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}
      {item?.status === "archived" ? (
        <div className="mb-5 rounded-lg border border-amber-400/30 bg-amber-500/10 p-4 text-sm text-amber-100">
          This investigation is archived and preserved by the configured retention
          policy. Restore it before making case changes, or permanently delete it
          if governance policy allows removal.
        </div>
      ) : null}
      <InvestigationTabs />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        <StatCard
          label="Targets"
          value={analytics.data?.target_summary.total ?? targets.data?.total ?? 0}
          icon={<Target className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Entities"
          value={
            analytics.data?.recon_summary.total_entities ??
            (graph.data?.nodes ?? []).length ??
            0
          }
          icon={<Network className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Findings"
          value={analytics.data?.findings_summary.total ?? findings.data?.length ?? 0}
          icon={<ShieldAlert className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Timeline"
          value={analytics.data?.timeline_summary.total ?? timeline.data?.total ?? 0}
          icon={<BrainCircuit className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Correlations"
          value={
            analytics.data?.correlation_summary.total_edges ??
            correlations.data?.total_edges ??
            0
          }
          icon={<GitGraph className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Reports"
          value={analytics.data?.report_summary.total ?? reports.data?.total ?? 0}
          icon={<FileText className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Notes"
          value={notes.data?.total ?? 0}
          icon={<StickyNote className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Open tasks"
          value={
            (tasks.data?.items ?? []).filter((task) => !taskClosed(task.status))
              .length
          }
          icon={<ListTodo className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Bookmarks"
          value={bookmarks.data?.total ?? 0}
          icon={<Bookmark className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Playbooks complete"
          value={
            playbookRuns.data?.filter((run) => run.status === "completed").length ?? 0
          }
          detail={`${playbookRuns.data?.length ?? 0} total runs`}
          icon={<Sparkles className="h-5 w-5" aria-hidden="true" />}
        />
      </div>

      {item ? (
        <ScopeAuthorizationPanel
          investigation={item}
          engagement={linkedEngagement.data}
          scopeItems={linkedEngagementScope.data ?? []}
          authorizationEvidence={linkedAuthorizationEvidence.data ?? []}
          isLoading={
            linkedEngagement.isLoading ||
            linkedEngagementScope.isLoading ||
            linkedAuthorizationEvidence.isLoading
          }
        />
      ) : null}

      <CaseReviewPanel
        review={caseReview.data}
        completeness={completeness.data}
        canSubmit={canSubmitReview}
        canReview={canManage}
        isSaving={reviewMutation.isPending}
        onSubmit={() => {
          const notes = window.prompt("Optional submission notes") ?? undefined;
          reviewMutation.mutate({ kind: "submit", notes });
        }}
        onDecision={(kind) => {
          const notes = window.prompt("Review notes") ?? "";
          if (notes.trim()) {
            reviewMutation.mutate({ kind, notes });
          }
        }}
        onClose={() => {
          const notes = window.prompt("Closure reason") ?? "";
          if (notes.trim()) {
            const overrideReason =
              caseReview.data?.review_status === "approved"
                ? null
                : window.prompt("Override reason required") ?? "";
            reviewMutation.mutate({
              kind: "close",
              notes,
              overrideReason,
            });
          }
        }}
      />

      <ExecutiveSummaryPanel
        summary={executiveSummary.data}
        risk={riskScore.data}
        isLoading={executiveSummary.isLoading || riskScore.isLoading}
        error={executiveSummary.error ?? riskScore.error}
        onRefresh={() => {
          void executiveSummary.refetch();
          void riskScore.refetch();
        }}
      />

      <AnalyticsOverview
        analytics={analytics}
        onRefresh={() => void analytics.refetch()}
      />
      <CaseWorkflowPanel
        status={item?.status ?? "intake"}
        notes={notes.data?.items ?? []}
        tasks={tasks.data?.items ?? []}
        currentUserId={user?.id}
      />
      {item ? (
        <InvestigationMaturityPanel
          investigation={item}
          readiness={readiness.data}
          isLoading={readiness.isLoading}
          canManage={canManage}
          isSaving={stageMutation.isPending}
          onStageChange={(stage, reason) =>
            stageMutation.mutate({ stage, reason })
          }
        />
      ) : null}
      {item ? <WorkspaceQuickActions investigationId={item.id} /> : null}
      {item ? (
        <OperationalCoordinationPanel
          investigation={item}
          currentUserId={user?.id}
          platformRole={user?.role}
        />
      ) : null}
      {item ? (
        <ProductivityWorkspace
          investigation={item}
          findings={findings.data ?? []}
          bookmarks={bookmarks.data?.total ?? 0}
          playbookRuns={playbookRuns.data ?? []}
          tags={tags.data?.items ?? []}
          availableTags={availableTags.data?.items ?? []}
          summary={summaryMutation.data}
          canManage={canManage}
          isGeneratingSummary={summaryMutation.isPending}
          isSavingPriority={priorityMutation.isPending}
          isSavingTags={tagMutation.isPending}
          onGenerateSummary={() => summaryMutation.mutate()}
          onSavePriority={(values) => priorityMutation.mutate(values)}
          onSaveTags={(tagIds) => tagMutation.mutate(tagIds)}
        />
      ) : null}

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
                <StatusBadge status={item?.status ?? "intake"} />
              </dd>
            </div>
            <Detail
              label="Owner"
              value={item ? ownerContext(item.owner_id, user?.id, user?.role) : ""}
            />
            <Detail label="Reviewer" value={item?.reviewer_id ?? "Unassigned"} />
            <Detail label="Priority" value={item?.priority ?? "medium"} />
            <Detail label="Due date" value={item?.due_date ?? "Not set"} />
            <Detail label="Targets" value={`${targets.data?.total ?? 0}`} />
            <Detail label="Findings" value={`${findings.data?.length ?? 0}`} />
            <Detail label="Notes" value={`${notes.data?.total ?? 0}`} />
            <Detail
              label="Open tasks"
              value={`${
                (tasks.data?.items ?? []).filter(
                  (task) => !taskClosed(task.status),
                ).length
              }`}
            />
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
            <LinkButton to="notes" label="Create analyst note" />
            <LinkButton to="bookmarks" label="Review bookmarks" />
            <LinkButton to="tasks" label="Create remediation task" />
            <LinkButton to="playbooks" label="Start defensive playbook" />
            <LinkButton to="reports" label="Download reports" />
          </div>
        </div>
      </section>
      {item && isEditing ? (
        <InvestigationEditModal
          investigation={item}
          engagementOptions={engagementOptions.data?.items ?? []}
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
      {item && isPurging ? (
        <PurgeInvestigationModal
          investigation={item}
          error={purgeMutation.error?.message}
          isPurging={purgeMutation.isPending}
          onClose={() => {
            purgeMutation.reset();
            setIsPurging(false);
          }}
          onConfirm={() => purgeMutation.mutate()}
        />
      ) : null}
    </>
  );
}

function ScopeAuthorizationPanel({
  investigation,
  engagement,
  scopeItems,
  authorizationEvidence,
  isLoading,
}: {
  investigation: Investigation;
  engagement: Engagement | undefined;
  scopeItems: EngagementScopeItem[];
  authorizationEvidence: AuthorizationEvidence[];
  isLoading: boolean;
}): JSX.Element {
  const inScope = scopeItems.filter((item) => item.status === "in_scope").length;
  const pending = scopeItems.filter((item) => item.status === "pending_review").length;
  const outOfScope = scopeItems.filter((item) => item.status === "out_of_scope").length;
  const hasAuthorizationConcern =
    engagement?.authorization_status === "not_provided" ||
    engagement?.authorization_status === "expired" ||
    engagement?.authorization_status === "revoked" ||
    engagement?.authorization_status === "pending_review";

  return (
    <section className="mt-6 rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-raven-cyan">
            Scope governance
          </p>
          <h2 className="mt-1 text-lg font-semibold">
            Scope and authorization
          </h2>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-raven-muted">
            Engagement metadata documents authorized scope, client context, and
            defensive-use approval without requiring old investigations to be
            migrated immediately.
          </p>
        </div>
        <Link
          to={engagement ? `/engagements?selected=${engagement.id}` : "/engagements"}
          className="rounded-md border border-raven-border px-3 py-2 text-sm text-raven-text hover:border-raven-violet"
        >
          {engagement ? "Open engagement" : "Manage engagements"}
        </Link>
      </div>

      {isLoading ? (
        <p className="mt-4 text-sm text-raven-muted">Loading scope metadata.</p>
      ) : engagement ? (
        <>
          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <ScopeMetric label="Client" value={engagement.client_name} />
            <ScopeMetric
              label="Authorization"
              value={formatLabel(engagement.authorization_status)}
            />
            <ScopeMetric
              label="Investigation scope"
              value={formatLabel(investigation.scope_review_status)}
            />
            <ScopeMetric label="Approved scope" value={`${inScope}`} />
            <ScopeMetric label="Pending / out" value={`${pending} / ${outOfScope}`} />
          </div>

          {hasAuthorizationConcern ? (
            <div className="mt-4 rounded-md border border-amber-300/30 bg-amber-400/10 p-3 text-sm text-amber-100">
              Authorization is {formatLabel(engagement.authorization_status)}.
              Confirm approval before expanding targets or publishing client-ready
              deliverables.
            </div>
          ) : null}
          {investigation.scope_notes ? (
            <p className="mt-4 break-words text-sm leading-6 text-raven-muted">
              {investigation.scope_notes}
            </p>
          ) : null}
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
              <p className="text-sm font-semibold">Scope items</p>
              {scopeItems.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {scopeItems.slice(0, 8).map((item) => (
                    <span
                      key={item.id}
                      className="max-w-full rounded border border-raven-border px-2 py-1 text-xs text-raven-muted"
                      title={item.value}
                    >
                      {formatLabel(item.scope_type)}:{" "}
                      <span className="break-all">{item.value}</span>
                    </span>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-sm text-raven-muted">
                  No scope items are stored for this engagement yet.
                </p>
              )}
            </div>
            <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
              <p className="text-sm font-semibold">Authorization references</p>
              {authorizationEvidence.length ? (
                <ul className="mt-3 space-y-2 text-sm text-raven-muted">
                  {authorizationEvidence.slice(0, 4).map((evidence) => (
                    <li key={evidence.id} className="break-words">
                      {evidence.title} ({formatLabel(evidence.evidence_type)})
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-raven-muted">
                  No authorization metadata has been recorded yet.
                </p>
              )}
            </div>
          </div>
        </>
      ) : (
        <div className="mt-4 rounded-md border border-raven-border bg-raven-panelSoft p-4 text-sm text-raven-muted">
          This investigation is not linked to an engagement. Existing cases remain
          usable, but linking an engagement adds client context, approved scope, and
          authorization status to reports and target review.
        </div>
      )}
    </section>
  );
}

function ScopeMetric({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="min-w-0 rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <p className="text-xs uppercase tracking-wide text-raven-muted">{label}</p>
      <p className="mt-2 break-words text-sm font-medium">{value}</p>
    </div>
  );
}

function ExecutiveSummaryPanel({
  summary,
  risk,
  isLoading,
  error,
  onRefresh,
}: {
  summary: ExecutiveInvestigationSummaryResponse | undefined;
  risk: InvestigationRiskScoreResponse | undefined;
  isLoading: boolean;
  error: Error | null;
  onRefresh: () => void;
}): JSX.Element {
  if (isLoading) {
    return (
      <section className="mt-6">
        <LoadingBlock label="Building executive intelligence" />
      </section>
    );
  }
  if (error || !summary || !risk) {
    return (
      <section className="mt-6">
        <ErrorBlock
          message={error?.message ?? "Executive intelligence is unavailable."}
        />
      </section>
    );
  }
  return (
    <section className="mt-6 min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-raven-cyan">
            Executive intelligence
          </p>
          <h2 className="mt-1 text-xl font-semibold">Investigation Summary</h2>
          <p className="mt-3 max-w-4xl break-words text-sm leading-6 text-raven-muted">
            {summary.objective}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="rounded-md border border-raven-violet bg-raven-violet/10 px-4 py-3 text-right">
            <p className="text-3xl font-semibold">{risk.score}/100</p>
            <p className="text-xs text-violet-100">{risk.category}</p>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            className="rounded-md border border-raven-border p-2 text-raven-muted hover:text-raven-text"
            title="Refresh executive intelligence"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-3">
        <ExecutiveTextCard
          title="Authorized scope"
          text={summary.authorized_scope}
        />
        <ExecutiveTextCard
          title="Business impact"
          text={summary.business_impact}
        />
        <ExecutiveTextCard
          title="Remediation urgency"
          text={summary.remediation_urgency}
        />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-md border border-raven-border bg-raven-panelSoft p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-semibold">Key findings</h3>
            <span className="text-xs text-raven-muted">
              Defensive confidence {summary.confidence}%
            </span>
          </div>
          {summary.key_findings.length ? (
            <div className="mt-3 space-y-3">
              {summary.key_findings.map((finding) => (
                <article
                  key={finding.id}
                  className="rounded-md border border-raven-border bg-raven-bg/50 p-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <p className="min-w-0 break-words text-sm font-medium">
                      {finding.title}
                    </p>
                    <span
                      className={[
                        "rounded border px-2 py-1 text-xs capitalize",
                        severityBadgeClass(finding.severity),
                      ].join(" ")}
                    >
                      {finding.severity}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-raven-muted">
                    Risk {finding.risk_score}/100 | Confidence{" "}
                    {finding.confidence_score}%
                  </p>
                </article>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-sm text-raven-muted">
              No unresolved evidence-backed findings are stored.
            </p>
          )}
        </div>
        <div className="space-y-4">
          <ExecutiveListCard
            title="Defensive concerns"
            items={summary.defensive_concerns}
          />
          <ExecutiveListCard
            title="Recurring issues"
            items={summary.recurring_issues}
            empty="No recurrence is visible across accessible investigations."
          />
          <ExecutiveListCard
            title="Notable technologies"
            items={summary.notable_technologies}
            empty="No technology observations are stored."
          />
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {risk.contributors.map((contributor) => (
          <div
            key={contributor.key}
            className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
          >
            <div className="flex items-center justify-between gap-3 text-sm">
              <span>{contributor.label}</span>
              <span className="text-raven-cyan">
                {contributor.points}/{contributor.max_points}
              </span>
            </div>
            <p className="mt-2 break-words text-xs leading-5 text-raven-muted">
              {contributor.detail}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function ExecutiveTextCard({
  title,
  text,
}: {
  title: string;
  text: string;
}): JSX.Element {
  return (
    <div className="min-w-0 rounded-md border border-raven-border bg-raven-panelSoft p-4">
      <p className="text-xs uppercase tracking-wide text-raven-muted">{title}</p>
      <p className="mt-2 break-words text-sm leading-6">{text}</p>
    </div>
  );
}

function ExecutiveListCard({
  title,
  items,
  empty = "No elevated concerns are currently established.",
}: {
  title: string;
  items: string[];
  empty?: string;
}): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft p-4">
      <h3 className="text-sm font-semibold">{title}</h3>
      {items.length ? (
        <ul className="mt-2 space-y-2 text-sm text-raven-muted">
          {items.map((item) => (
            <li key={item} className="break-words">
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-raven-muted">{empty}</p>
      )}
    </div>
  );
}

function ProductivityWorkspace({
  investigation,
  findings,
  bookmarks,
  playbookRuns,
  tags,
  availableTags,
  summary,
  canManage,
  isGeneratingSummary,
  isSavingPriority,
  isSavingTags,
  onGenerateSummary,
  onSavePriority,
  onSaveTags,
}: {
  investigation: Investigation;
  findings: Finding[];
  bookmarks: number;
  playbookRuns: PlaybookRun[];
  tags: InvestigationTag[];
  availableTags: InvestigationTag[];
  summary: InvestigationSummaryResponse | undefined;
  canManage: boolean;
  isGeneratingSummary: boolean;
  isSavingPriority: boolean;
  isSavingTags: boolean;
  onGenerateSummary: () => void;
  onSavePriority: (values: {
    priority: InvestigationPriority;
    business_impact: string | null;
    due_date: string | null;
  }) => void;
  onSaveTags: (tagIds: string[]) => void;
}): JSX.Element {
  const [priority, setPriority] = useState(investigation.priority);
  const [businessImpact, setBusinessImpact] = useState(
    investigation.business_impact ?? "",
  );
  const [dueDate, setDueDate] = useState(investigation.due_date ?? "");
  const [selectedTags, setSelectedTags] = useState<string[]>(
    tags.map((tag) => tag.id),
  );

  useEffect(() => {
    setPriority(investigation.priority);
    setBusinessImpact(investigation.business_impact ?? "");
    setDueDate(investigation.due_date ?? "");
  }, [
    investigation.business_impact,
    investigation.due_date,
    investigation.priority,
  ]);
  useEffect(() => {
    setSelectedTags(tags.map((tag) => tag.id));
  }, [tags]);

  const unresolved = findings.filter(
    (finding) =>
      !["mitigated", "false_positive", "archived", "resolved"].includes(
        finding.status,
      ),
  ).length;
  const remediationComplete = findings.filter((finding) =>
    ["remediated", "accepted_risk", "false_positive"].includes(
      finding.remediation_status,
    ),
  ).length;
  const overdueRemediation = findings.filter(
    (finding) =>
      finding.remediation_due_date &&
      new Date(finding.remediation_due_date).getTime() < Date.now() &&
      !["remediated", "accepted_risk", "false_positive"].includes(
        finding.remediation_status,
      ),
  ).length;
  const playbookCompleted = playbookRuns.filter(
    (run) => run.status === "completed",
  ).length;

  function toggleTag(tagId: string): void {
    setSelectedTags((current) =>
      current.includes(tagId)
        ? current.filter((item) => item !== tagId)
        : [...current, tagId],
    );
  }

  return (
    <section className="mt-6 space-y-4">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MiniMetric
          label="Remediation progress"
          value={
            findings.length
              ? `${Math.round((remediationComplete / findings.length) * 100)}%`
              : "0%"
          }
          detail={`${remediationComplete}/${findings.length} findings`}
        />
        <MiniMetric
          label="Playbook completion"
          value={`${playbookCompleted}/${playbookRuns.length}`}
          detail="Completed defensive runs"
        />
        <MiniMetric
          label="Unresolved findings"
          value={String(unresolved)}
          detail="Require analyst review"
        />
        <MiniMetric
          label="Saved evidence"
          value={String(bookmarks)}
          detail={`${overdueRemediation} overdue remediation`}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <article className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Investigation summary</h2>
              <p className="mt-1 text-sm text-raven-muted">
                Deterministic summary from stored evidence only.
              </p>
            </div>
            <button
              type="button"
              onClick={onGenerateSummary}
              disabled={isGeneratingSummary}
              className="inline-flex items-center gap-2 rounded-md bg-raven-violet px-3 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-60"
            >
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              {isGeneratingSummary ? "Generating" : "Generate summary"}
            </button>
          </div>
          {summary ? (
            <div className="mt-5 space-y-4 text-sm">
              <div>
                <p className="text-xs uppercase tracking-wide text-raven-muted">
                  Scope
                </p>
                <p className="mt-1 break-words text-raven-text">{summary.scope}</p>
              </div>
              <SummaryList
                title="Observed defensive concerns"
                items={summary.observed_defensive_concerns}
              />
              <SummaryList
                title="Next analyst actions"
                items={summary.next_recommended_analyst_actions}
              />
              <p className="text-xs text-raven-muted">
                {summary.remediation_progress.completion_percent}% remediation
                complete, {summary.evidence_references.length} evidence references.
              </p>
            </div>
          ) : (
            <p className="mt-5 text-sm text-raven-muted">
              Generate a summary to review scope, concerns, remediation progress,
              and the next evidence-backed analyst actions.
            </p>
          )}
        </article>

        <article className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
          <div className="flex items-center gap-2">
            <CalendarClock className="h-5 w-5 text-raven-cyan" aria-hidden="true" />
            <h2 className="text-lg font-semibold">Priority and ownership</h2>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <label className="text-sm text-raven-muted">
              Priority
              <select
                value={priority}
                onChange={(event) =>
                  setPriority(event.target.value as InvestigationPriority)
                }
                disabled={!canManage}
                className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet disabled:opacity-70"
              >
                {(["low", "medium", "high", "urgent"] as const).map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm text-raven-muted">
              Due date
              <input
                type="date"
                value={dueDate}
                onChange={(event) => setDueDate(event.target.value)}
                disabled={!canManage}
                className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet disabled:opacity-70"
              />
            </label>
          </div>
          <label className="mt-3 block text-sm text-raven-muted">
            Business impact
            <textarea
              value={businessImpact}
              onChange={(event) => setBusinessImpact(event.target.value)}
              disabled={!canManage}
              rows={3}
              className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet disabled:opacity-70"
            />
          </label>
          <p className="mt-3 break-all text-xs text-raven-muted">
            Owner: {investigation.owner_id}
          </p>
          {canManage ? (
            <button
              type="button"
              onClick={() =>
                onSavePriority({
                  priority,
                  business_impact: businessImpact.trim() || null,
                  due_date: dueDate || null,
                })
              }
              disabled={isSavingPriority}
              className="mt-4 rounded-md border border-raven-violet px-3 py-2 text-sm text-raven-text hover:bg-raven-violet/20 disabled:opacity-60"
            >
              {isSavingPriority ? "Saving" : "Save priority"}
            </button>
          ) : null}
        </article>
      </div>

      <article className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <div className="flex items-center gap-2">
          <Tags className="h-5 w-5 text-raven-cyan" aria-hidden="true" />
          <h2 className="text-lg font-semibold">Investigation tags</h2>
        </div>
        {availableTags.length ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {availableTags.map((tag) => {
              const selected = selectedTags.includes(tag.id);
              return (
                <button
                  key={tag.id}
                  type="button"
                  onClick={() => toggleTag(tag.id)}
                  disabled={!canManage}
                  className={[
                    "rounded-md border px-3 py-1.5 text-sm transition disabled:cursor-default",
                    selected
                      ? "border-raven-violet bg-raven-violet/20 text-raven-text"
                      : "border-raven-border text-raven-muted hover:border-raven-violet",
                  ].join(" ")}
                >
                  {tag.name}
                </button>
              );
            })}
          </div>
        ) : (
          <p className="mt-4 text-sm text-raven-muted">No tags are available.</p>
        )}
        {canManage ? (
          <button
            type="button"
            onClick={() => onSaveTags(selectedTags)}
            disabled={isSavingTags}
            className="mt-4 rounded-md border border-raven-violet px-3 py-2 text-sm text-raven-text hover:bg-raven-violet/20 disabled:opacity-60"
          >
            {isSavingTags ? "Saving" : "Save tags"}
          </button>
        ) : null}
      </article>
    </section>
  );
}

function MiniMetric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}): JSX.Element {
  return (
    <article className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <p className="text-xs uppercase tracking-wide text-raven-muted">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
      <p className="mt-1 text-xs text-raven-muted">{detail}</p>
    </article>
  );
}

function SummaryList({
  title,
  items,
}: {
  title: string;
  items: string[];
}): JSX.Element {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-raven-muted">{title}</p>
      <ul className="mt-2 space-y-1 text-raven-text">
        {items.map((item) => (
          <li key={item} className="break-words">
            - {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function AnalyticsOverview({
  analytics,
  onRefresh,
}: {
  analytics: {
    data: InvestigationAnalyticsResponse | undefined;
    isLoading: boolean;
    isError: boolean;
    isFetching: boolean;
    error: Error | null;
  };
  onRefresh: () => void;
}): JSX.Element {
  if (analytics.isLoading) {
    return (
      <section className="mt-6">
        <LoadingBlock label="Loading investigation analytics" />
      </section>
    );
  }
  if (analytics.isError) {
    return (
      <section className="mt-6">
        <ErrorBlock message={analytics.error ?? "Analytics failed"} />
      </section>
    );
  }
  const data = analytics.data;
  if (!data) {
    return (
      <section className="mt-6">
        <ErrorBlock message="No analytics payload was returned." />
      </section>
    );
  }
  const reconCompleted =
    data.recon_summary.total_entities > 0 || data.timeline_summary.total > 1;

  return (
    <section className="mt-6 space-y-4">
      <div className="flex flex-col gap-3 rounded-lg border border-raven-border bg-raven-panel/85 p-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-lg font-semibold">Investigation analytics</h2>
          <p className="mt-1 text-sm text-raven-muted">
            Last updated {new Date(data.generated_at).toLocaleString()}
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={analytics.isFetching}
          className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-text hover:border-raven-violet disabled:opacity-60"
        >
          <RefreshCw
            className={[
              "h-4 w-4",
              analytics.isFetching ? "animate-spin" : "",
            ].join(" ")}
            aria-hidden="true"
          />
          Refresh analytics
        </button>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
      <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <h2 className="text-lg font-semibold">Finding Signal Overview</h2>
        <p className="mt-2 text-sm text-raven-muted">
          {data.risk_summary.risk_score === 0
            ? "No elevated finding signal is currently recorded."
            : `${data.risk_summary.risk_level} highest stored finding signal at ${data.risk_summary.risk_score}/100`}
        </p>
        <div className="mt-4 grid grid-cols-5 gap-2 text-center text-xs">
          {(["critical", "high", "medium", "low", "info"] as const).map((severity) => (
            <div
              key={severity}
              className="rounded-md border border-raven-border bg-raven-panelSoft p-2"
            >
              <p className="capitalize text-raven-muted">{severity}</p>
              <p className="mt-1 text-lg font-semibold">
                {data.findings_summary.by_severity[severity] ?? 0}
              </p>
            </div>
          ))}
        </div>
        <p className="mt-4 text-xs text-raven-muted">
          Average confidence {data.findings_summary.average_confidence}% -{" "}
          {data.risk_summary.high_or_critical_findings} high/critical findings
        </p>
      </div>

      <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <h2 className="text-lg font-semibold">Recon Overview</h2>
        <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
          {overviewCounts(data).map(({ label, count }) => (
            <div
              key={label}
              className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
            >
              <p className="text-xs uppercase tracking-wide text-raven-muted">
                {label}
              </p>
              <p className="mt-1 text-xl font-semibold">{count}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <h2 className="text-lg font-semibold">Analysis Status</h2>
        <div className="mt-4 space-y-3">
          <StatusRow active={reconCompleted} label="Recon completed" />
          <StatusRow
            active={data.ai_analysis_summary.available}
            label="Analysis available"
          />
          <StatusRow
            active={data.report_summary.ready > 0}
            label="Reports generated"
          />
        </div>
      </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <CountList
          title="Top affected assets"
          items={data.top_assets}
          emptyMessage="No affected assets are available yet."
        />
        <CountList
          title="Top technologies"
          items={data.top_technologies}
          emptyMessage="No technology entities are available yet."
        />
        <LatestActivityList items={data.latest_activity} />
      </div>
    </section>
  );
}

function overviewCounts(data: InvestigationAnalyticsResponse): CountItem[] {
  return [
    { label: "Targets", count: data.target_summary.total },
    { label: "Entities", count: data.recon_summary.total_entities },
    { label: "Relationships", count: data.recon_summary.relationship_count },
    { label: "Correlations", count: data.correlation_summary.total_edges },
    { label: "Reports", count: data.report_summary.total },
    { label: "AI artifacts", count: data.ai_analysis_summary.total },
  ];
}

function CountList({
  title,
  items,
  emptyMessage,
}: {
  title: string;
  items: CountItem[];
  emptyMessage: string;
}): JSX.Element {
  return (
    <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <h2 className="text-lg font-semibold">{title}</h2>
      {items.length ? (
        <div className="mt-4 space-y-2">
          {items.map((item) => (
            <div
              key={item.label}
              className="flex items-center justify-between rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm"
            >
              <span className="break-all text-raven-muted">{item.label}</span>
              <span className="font-medium text-raven-text">{item.count}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-raven-muted">{emptyMessage}</p>
      )}
    </div>
  );
}

function LatestActivityList({
  items,
}: {
  items: InvestigationAnalyticsResponse["latest_activity"];
}): JSX.Element {
  return (
    <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <h2 className="text-lg font-semibold">Latest activity</h2>
      {items.length ? (
        <div className="mt-4 space-y-3">
          {items.slice(0, 4).map((item) => (
            <article key={item.id} className="text-sm">
              <div className="flex items-center justify-between gap-3">
                <p className="font-medium">{item.title}</p>
                <span
                  className={[
                    "rounded border px-2 py-1 text-xs capitalize",
                    severityBadgeClass(item.severity),
                  ].join(" ")}
                >
                  {item.severity}
                </span>
              </div>
              <p className="mt-1 text-xs text-raven-muted">
                {item.source} - {new Date(item.timestamp).toLocaleString()}
              </p>
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-raven-muted">
          No activity is available for this investigation yet.
        </p>
      )}
    </div>
  );
}

const maturityStages: InvestigationStage[] = [
  "intake",
  "scoping",
  "recon",
  "analysis",
  "remediation",
  "validation",
  "reporting",
  "completed",
  "archived",
];

const allowedStageTransitions: Record<InvestigationStage, InvestigationStage[]> = {
  intake: ["scoping"],
  scoping: ["intake", "recon"],
  recon: ["scoping", "analysis"],
  analysis: ["recon", "remediation"],
  remediation: ["analysis", "validation"],
  validation: ["remediation", "reporting"],
  reporting: ["validation", "completed"],
  completed: ["reporting", "archived"],
  archived: ["completed"],
};

function InvestigationMaturityPanel({
  investigation,
  readiness,
  isLoading,
  canManage,
  isSaving,
  onStageChange,
}: {
  investigation: Investigation;
  readiness: InvestigationReadinessResponse | undefined;
  isLoading: boolean;
  canManage: boolean;
  isSaving: boolean;
  onStageChange: (stage: InvestigationStage, reason: string) => void;
}): JSX.Element {
  const [nextStage, setNextStage] = useState<InvestigationStage>(
    allowedStageTransitions[investigation.stage][0] ?? investigation.stage,
  );
  const [reason, setReason] = useState("Analyst workflow progression.");

  useEffect(() => {
    setNextStage(
      allowedStageTransitions[investigation.stage][0] ?? investigation.stage,
    );
  }, [investigation.stage]);

  const activeIndex = maturityStages.indexOf(investigation.stage);
  return (
    <section className="mt-6 rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <Gauge className="h-5 w-5 text-raven-cyan" aria-hidden="true" />
            <h2 className="text-lg font-semibold">Investigation readiness</h2>
            <span className="rounded border border-raven-border px-2 py-1 text-xs capitalize text-raven-muted">
              {investigation.stage}
            </span>
          </div>
          <p className="mt-2 text-sm text-raven-muted">
            Deterministic maturity from authorized scope, stored evidence, analyst
            review, remediation, and reporting.
          </p>
        </div>
        <div className="text-left xl:text-right">
          <p className="text-3xl font-semibold">
            {isLoading ? "..." : `${readiness?.score ?? 0}/100`}
          </p>
          <p className="text-sm text-raven-cyan">
            {readiness?.category ?? "Calculating readiness"}
          </p>
        </div>
      </div>

      <div className="mt-5 overflow-x-auto pb-2">
        <div className="flex min-w-[820px] items-center gap-2">
          {maturityStages.map((stage, index) => (
            <div key={stage} className="flex min-w-0 flex-1 items-center gap-2">
              <div
                className={[
                  "min-w-0 flex-1 rounded-md border px-2 py-2 text-center text-xs capitalize",
                  index <= activeIndex
                    ? "border-raven-violet bg-raven-violet/15 text-violet-100"
                    : "border-raven-border text-raven-muted",
                ].join(" ")}
              >
                {stage}
              </div>
              {index < maturityStages.length - 1 ? (
                <span className="text-raven-muted">›</span>
              ) : null}
            </div>
          ))}
        </div>
      </div>

      {readiness ? (
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {readiness.components.map((component) => (
            <div
              key={component.key}
              className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium">{component.label}</p>
                <span
                  className={
                    component.complete ? "text-emerald-200" : "text-raven-muted"
                  }
                >
                  {component.points}/{component.max_points}
                </span>
              </div>
              <p className="mt-2 text-xs text-raven-muted">{component.detail}</p>
            </div>
          ))}
        </div>
      ) : null}

      <div className="mt-5 grid gap-4 xl:grid-cols-[1fr_0.9fr]">
        <div className="rounded-md border border-raven-border bg-raven-panelSoft p-4">
          <h3 className="font-semibold">Workspace guidance</h3>
          <ul className="mt-3 space-y-2 text-sm text-raven-muted">
            {(readiness?.guidance ?? ["Readiness guidance is loading."]).map(
              (item) => (
                <li key={item}>• {item}</li>
              ),
            )}
          </ul>
        </div>
        <div className="rounded-md border border-raven-border bg-raven-panelSoft p-4">
          <h3 className="font-semibold">Advance lifecycle stage</h3>
          {canManage ? (
            <div className="mt-3 grid gap-3">
              <select
                value={nextStage}
                onChange={(event) =>
                  setNextStage(event.target.value as InvestigationStage)
                }
                className="input-base capitalize"
              >
                {allowedStageTransitions[investigation.stage].map((stage) => (
                  <option key={stage} value={stage}>
                    {stage}
                  </option>
                ))}
              </select>
              <input
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                className="input-base"
                placeholder="Reason for stage change"
              />
              <button
                type="button"
                onClick={() => onStageChange(nextStage, reason.trim())}
                disabled={isSaving || reason.trim().length < 3}
                className="rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50"
              >
                {isSaving ? "Updating" : "Update stage"}
              </button>
            </div>
          ) : (
            <p className="mt-3 text-sm text-raven-muted">
              Only the investigation owner or an administrator can change the
              maturity stage.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function WorkspaceQuickActions({
  investigationId,
}: {
  investigationId: string;
}): JSX.Element {
  const actions = [
    { label: "Create note", to: "notes", icon: StickyNote },
    { label: "Create finding", to: "findings", icon: ShieldAlert },
    { label: "Create remediation", to: "tasks", icon: Wrench },
    { label: "Run passive recon", to: "targets", icon: Target },
    { label: "Generate report", to: "reports", icon: FileText },
    { label: "Bookmark evidence", to: "bookmarks", icon: Bookmark },
    { label: "Assign analyst", to: "members", icon: UserPlus },
  ];
  return (
    <section className="mt-6 rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <h2 className="text-lg font-semibold">Investigation quick actions</h2>
      <p className="mt-1 text-sm text-raven-muted">
        Continue the authorized defensive assessment without leaving the case
        workspace.
      </p>
      <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        {actions.map(({ label, to, icon: Icon }) => (
          <Link
            key={label}
            to={`/investigations/${investigationId}/${to}`}
            className="flex min-h-20 items-center gap-3 rounded-md border border-raven-border bg-raven-panelSoft p-3 text-sm hover:border-raven-violet"
          >
            <Icon className="h-4 w-4 shrink-0 text-raven-cyan" aria-hidden="true" />
            <span>{label}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}

function CaseWorkflowPanel({
  status,
  notes,
  tasks,
  currentUserId,
}: {
  status: InvestigationStatus;
  notes: InvestigationNote[];
  tasks: InvestigationTask[];
  currentUserId: string | undefined;
}): JSX.Element {
  const assignedOpenTasks = tasks.filter(
    (task) => task.assigned_to === currentUserId && !taskClosed(task.status),
  );
  const openTasks = tasks.filter((task) => !taskClosed(task.status));
  const latestActivity = latestCaseActivity(notes, tasks);
  return (
    <section className="mt-6 grid gap-4 xl:grid-cols-4">
      <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <h2 className="text-lg font-semibold">Workflow</h2>
        <div className="mt-4">
          <StatusBadge status={status} />
        </div>
        <p className="mt-3 text-sm text-raven-muted">
          {workflowDescription(status)}
        </p>
      </div>
      <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <h2 className="text-lg font-semibold">Tasking</h2>
        <p className="mt-3 text-3xl font-semibold">{assignedOpenTasks.length}</p>
        <p className="mt-1 text-sm text-raven-muted">
          Assigned open tasks - {openTasks.length} open total
        </p>
      </div>
      <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <h2 className="text-lg font-semibold">Notes</h2>
        <p className="mt-3 text-3xl font-semibold">{notes.length}</p>
        <p className="mt-1 text-sm text-raven-muted">
          Latest: {notes[0] ? notes[0].title : "No analyst notes yet"}
        </p>
      </div>
      <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <h2 className="text-lg font-semibold">Next action</h2>
        <p className="mt-3 text-sm leading-6 text-raven-muted">
          {nextRecommendedAction(status, tasks, notes)}
        </p>
        {latestActivity ? (
          <p className="mt-3 text-xs text-raven-muted">
            Latest analyst activity: {latestActivity}
          </p>
        ) : null}
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

function latestCaseActivity(
  notes: InvestigationNote[],
  tasks: InvestigationTask[],
): string | null {
  const noteActivity = notes.map((note) => ({
    timestamp: note.updated_at,
    label: `note "${note.title}"`,
  }));
  const taskActivity = tasks.map((task) => ({
    timestamp: task.completed_at ?? task.created_at,
    label: `task "${task.title}"`,
  }));
  const latest = [...noteActivity, ...taskActivity].sort(
    (left, right) =>
      new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime(),
  )[0];
  return latest
    ? `${latest.label} on ${new Date(latest.timestamp).toLocaleString()}`
    : null;
}

function nextRecommendedAction(
  status: InvestigationStatus,
  tasks: InvestigationTask[],
  notes: InvestigationNote[],
): string {
  if (tasks.some((task) => task.status === "blocked")) {
    return "Resolve blocked tasks before moving the case forward.";
  }
  if (!notes.length) {
    return "Add an analyst note summarizing current scope and evidence.";
  }
  if (!tasks.length) {
    return "Create validation or remediation tasks for the active evidence.";
  }
  if (status === "intake") {
    return "Move the investigation to active once scope and authorization are ready.";
  }
  if (status === "remediation") {
    return "Track mitigation work and confirm affected findings are addressed.";
  }
  if (status === "validation") {
    return "Validate completed work and preserve final supporting evidence.";
  }
  if (status === "completed") {
    return "Archive the case after final evidence and reports are preserved.";
  }
  return "Continue passive review and keep notes, tasks, and evidence current.";
}

function CaseReviewPanel({
  review,
  completeness,
  canSubmit,
  canReview,
  isSaving,
  onSubmit,
  onDecision,
  onClose,
}: {
  review: CaseReviewResponse | undefined;
  completeness: EvidenceCompletenessResponse | undefined;
  canSubmit: boolean;
  canReview: boolean;
  isSaving: boolean;
  onSubmit: () => void;
  onDecision: (kind: "approve" | "reject" | "request_changes") => void;
  onClose: () => void;
}): JSX.Element {
  const status = review?.review_status ?? "not_submitted";
  const score =
    completeness?.score ?? review?.evidence_completeness_score ?? 0;
  const label =
    completeness?.label ?? review?.evidence_completeness_label ?? "incomplete";
  const checklist = review?.checklist ?? [];
  return (
    <section className="mt-6 rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-raven-cyan">
            Case review workflow
          </p>
          <h2 className="mt-1 text-lg font-semibold">
            Review status: {formatLabel(status)}
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-raven-muted">
            Formal review is analyst-driven. The checklist and evidence
            completeness score are deterministic and based on stored case data.
          </p>
        </div>
        <div className="rounded-md border border-raven-violet bg-raven-violet/10 p-4 lg:text-right">
          <p className="text-3xl font-semibold">{score}/100</p>
          <p className="mt-1 text-sm capitalize text-violet-100">
            {formatLabel(label)}
          </p>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {canSubmit || canReview ? (
          <>
            {canSubmit ? (
              <button
                type="button"
                onClick={onSubmit}
                disabled={isSaving || status === "closed"}
                className="rounded-md bg-raven-violet px-3 py-2 text-sm text-white hover:bg-violet-500 disabled:opacity-60"
              >
                Submit for review
              </button>
            ) : null}
            {canReview ? (
              <>
                <button
                  type="button"
                  onClick={() => onDecision("approve")}
                  disabled={isSaving || status === "closed"}
                  className="rounded-md border border-emerald-400/30 px-3 py-2 text-sm text-emerald-100 hover:bg-emerald-500/10 disabled:opacity-60"
                >
                  Approve
                </button>
                <button
                  type="button"
                  onClick={() => onDecision("request_changes")}
                  disabled={isSaving || status === "closed"}
                  className="rounded-md border border-amber-400/30 px-3 py-2 text-sm text-amber-100 hover:bg-amber-500/10 disabled:opacity-60"
                >
                  Request changes
                </button>
                <button
                  type="button"
                  onClick={() => onDecision("reject")}
                  disabled={isSaving || status === "closed"}
                  className="rounded-md border border-rose-400/30 px-3 py-2 text-sm text-rose-100 hover:bg-rose-500/10 disabled:opacity-60"
                >
                  Reject
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  disabled={isSaving || status === "closed"}
                  className="rounded-md border border-raven-border px-3 py-2 text-sm hover:border-raven-violet disabled:opacity-60"
                >
                  Close case
                </button>
              </>
            ) : null}
          </>
        ) : (
          <span className="text-sm text-raven-muted">
            You can read review status, but cannot mutate case review workflow.
          </span>
        )}
      </div>
      {review?.review_notes ? (
        <p className="mt-4 rounded-md border border-raven-border bg-raven-panelSoft p-3 text-sm text-raven-muted">
          {review.review_notes}
        </p>
      ) : null}
      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        {checklist.length ? (
          checklist.map((item) => (
            <div
              key={item.key}
              className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
            >
              <span
                className={[
                  "rounded border px-2 py-1 text-xs capitalize",
                  checklistTone(item.status),
                ].join(" ")}
              >
                {formatLabel(item.status)}
              </span>
              <p className="mt-3 text-sm font-medium">{item.label}</p>
              <p className="mt-2 text-xs leading-5 text-raven-muted">
                {item.detail}
              </p>
            </div>
          ))
        ) : (
          <p className="text-sm text-raven-muted">
            Review checklist will appear after the backend calculates stored case
            evidence.
          </p>
        )}
      </div>
    </section>
  );
}

function workflowDescription(status: InvestigationStatus): string {
  const descriptions: Record<InvestigationStatus, string> = {
    intake: "Initial setup and scope confirmation.",
    active: "Investigation work is in progress.",
    monitoring: "Passive observation and follow-up are ongoing.",
    remediation: "Remediation work is being tracked.",
    validation: "Remediation and evidence are being validated.",
    completed: "Investigation work has been completed.",
    archived: "Case is closed and retained for reference.",
  };
  return descriptions[status] ?? "Workflow status is available.";
}

function checklistTone(status: string): string {
  if (status === "passed") {
    return "border-emerald-400/40 bg-emerald-500/10 text-emerald-100";
  }
  if (status === "warning") {
    return "border-amber-400/40 bg-amber-500/10 text-amber-100";
  }
  if (status === "failed") {
    return "border-rose-400/40 bg-rose-500/10 text-rose-100";
  }
  return "border-raven-border bg-raven-panel text-raven-muted";
}

function formatLabel(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function canManageInvestigation(
  ownerId: string,
  userId: string | undefined,
  role: string | undefined,
  memberRole: string | undefined,
): boolean {
  return (
    ownerId === userId ||
    role === "admin" ||
    memberRole === "owner" ||
    memberRole === "admin"
  );
}

function taskClosed(status: InvestigationTask["status"]): boolean {
  return status === "completed";
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

function severityBadgeClass(severity: Severity): string {
  switch (severity) {
    case "critical":
      return "border-rose-400/40 bg-rose-500/10 text-rose-100";
    case "high":
      return "border-orange-400/40 bg-orange-500/10 text-orange-100";
    case "medium":
      return "border-amber-400/40 bg-amber-500/10 text-amber-100";
    case "low":
      return "border-cyan-400/40 bg-cyan-500/10 text-cyan-100";
    case "info":
      return "border-raven-border bg-raven-panel text-raven-muted";
    default:
      return "border-raven-border bg-raven-panel text-raven-muted";
  }
}
