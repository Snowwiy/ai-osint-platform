import {
  Archive,
  Ban,
  BookOpenCheck,
  CheckCircle2,
  CircleDot,
  Loader2,
  RotateCcw,
} from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { InvestigationTabs } from "../components/InvestigationTabs";
import { LongValue } from "../components/LongValue";
import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import {
  listInvestigationMembers,
  listPlaybookRuns,
  updatePlaybookRun,
  updatePlaybookRunArchive,
  updatePlaybookRunStep,
} from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import { safeArray } from "../lib/safe";
import { useAuth } from "../lib/useAuth";
import type {
  PlaybookRun,
  PlaybookRunStatus,
  PlaybookRunStep,
  PlaybookRunStepStatus,
} from "../types";

const stepStatuses: PlaybookRunStepStatus[] = [
  "pending",
  "in_progress",
  "completed",
  "skipped",
];

export function PlaybooksPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [toast, setToast] = useState<ToastState | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const runs = useQuery({
    queryKey: ["playbook-runs", investigationId, showArchived],
    queryFn: () => listPlaybookRuns(investigationId, showArchived),
  });
  const members = useQuery({
    queryKey: ["members", investigationId],
    queryFn: () => listInvestigationMembers(investigationId),
  });
  const currentMember = members.data?.find(
    (member) => member.user_id === user?.id,
  );
  const canUpdate =
    user?.role === "admin" ||
    currentMember?.role === "owner" ||
    currentMember?.role === "admin" ||
    currentMember?.role === "analyst";
  const canCancel =
    user?.role === "admin" ||
    currentMember?.role === "owner" ||
    currentMember?.role === "admin";

  const runMutation = useMutation({
    mutationFn: ({
      runId,
      status,
    }: {
      runId: string;
      status: PlaybookRunStatus;
    }) => updatePlaybookRun(runId, status),
    onSuccess: async () => {
      await invalidatePlaybooks(queryClient, investigationId);
      setToast({ kind: "success", message: "Playbook run updated." });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Unable to update run.",
      });
    },
  });
  const stepMutation = useMutation({
    mutationFn: ({
      runId,
      stepId,
      status,
      analystNote,
    }: {
      runId: string;
      stepId: string;
      status: PlaybookRunStepStatus;
      analystNote: string;
    }) =>
      updatePlaybookRunStep(runId, stepId, {
        status,
        analyst_note: analystNote.trim() || null,
      }),
    onSuccess: async () => {
      await invalidatePlaybooks(queryClient, investigationId);
      setToast({ kind: "success", message: "Playbook step updated." });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message:
          error instanceof Error ? error.message : "Unable to update playbook step.",
      });
    },
  });
  const archiveMutation = useMutation({
    mutationFn: ({ runId, archived }: { runId: string; archived: boolean }) =>
      updatePlaybookRunArchive(runId, archived),
    onSuccess: async (_run, variables) => {
      await invalidatePlaybooks(queryClient, investigationId);
      setToast({
        kind: "success",
        message: variables.archived
          ? "Playbook run archived."
          : "Playbook run restored.",
      });
    },
    onError: (error) => {
      setToast({ kind: "error", message: error.message });
    },
  });

  if (runs.isLoading) {
    return <LoadingBlock label="Loading defensive playbooks" />;
  }
  if (runs.isError) {
    return <ErrorBlock message={runs.error} />;
  }

  return (
    <>
      <PageHeader
        title="Playbooks"
        eyebrow="Defensive remediation workflow"
        actions={
          user?.role === "admin" ? (
            <label className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-muted">
              <input
                type="checkbox"
                checked={showArchived}
                onChange={(event) => setShowArchived(event.target.checked)}
                className="accent-violet-500"
              />
              Show archived
            </label>
          ) : null
        }
      />
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}
      <InvestigationTabs />

      {runs.data?.length ? (
        <div className="space-y-4">
          {runs.data.map((run) => (
            <PlaybookRunCard
              key={run.id}
              run={run}
              canUpdate={canUpdate}
              canCancel={canCancel}
              isUpdating={
                runMutation.isPending ||
                stepMutation.isPending ||
                archiveMutation.isPending
              }
              onArchive={(archived) =>
                archiveMutation.mutate({ runId: run.id, archived })
              }
              onRunStatus={(status) =>
                runMutation.mutate({ runId: run.id, status })
              }
              onStepStatus={(step, status, analystNote) =>
                stepMutation.mutate({
                  runId: run.id,
                  stepId: step.id,
                  status,
                  analystNote,
                })
              }
            />
          ))}
        </div>
      ) : (
        <EmptyBlock
          title="No defensive playbook runs"
          message="Playbooks provide analyst-approved guidance for evidence validation and remediation."
          nextStep="Open an evidence-backed finding to review recommended defensive playbooks."
          permission="Viewers can inspect runs but cannot start or update them."
        />
      )}
    </>
  );
}

function PlaybookRunCard({
  run,
  canUpdate,
  canCancel,
  isUpdating,
  onRunStatus,
  onArchive,
  onStepStatus,
}: {
  run: PlaybookRun;
  canUpdate: boolean;
  canCancel: boolean;
  isUpdating: boolean;
  onRunStatus: (status: PlaybookRunStatus) => void;
  onArchive: (archived: boolean) => void;
  onStepStatus: (
    step: PlaybookRunStep,
    status: PlaybookRunStepStatus,
    analystNote: string,
  ) => void;
}): JSX.Element {
  const steps = safeArray(run.steps);
  const complete = steps.filter((step) =>
    ["completed", "skipped"].includes(step.status),
  ).length;
  const progress = steps.length
    ? Math.round((complete / steps.length) * 100)
    : 0;

  return (
    <article className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <BookOpenCheck className="h-5 w-5 text-raven-cyan" aria-hidden="true" />
            <h2 className="font-semibold">{run.playbook_name}</h2>
            <WorkflowBadge value={run.status} />
            {run.archived_at ? (
              <span className="rounded border border-amber-400/30 bg-amber-500/10 px-2 py-1 text-xs text-amber-100">
                archived
              </span>
            ) : null}
          </div>
          <p className="mt-2 text-sm text-raven-muted">
            Finding: {run.finding_title}
          </p>
          <div className="mt-2 grid gap-1 text-xs text-raven-muted">
            <LongValue label="Run ID" value={run.id} maxLength={52} />
            <LongValue label="Finding ID" value={run.finding_id} maxLength={52} />
          </div>
        </div>
        {canUpdate && !run.archived_at ? (
          <div className="flex flex-wrap gap-2">
            {!["completed", "cancelled"].includes(run.status) &&
            run.status !== "in_progress" ? (
              <button
                type="button"
                disabled={isUpdating}
                onClick={() => onRunStatus("in_progress")}
                className="rounded-md border border-raven-border px-3 py-2 text-sm hover:border-raven-violet disabled:opacity-50"
              >
                Continue
              </button>
            ) : null}
            {!["completed", "cancelled"].includes(run.status) &&
            run.status !== "blocked" ? (
              <button
                type="button"
                disabled={isUpdating}
                onClick={() => onRunStatus("blocked")}
                className="rounded-md border border-amber-400/40 px-3 py-2 text-sm text-amber-100 disabled:opacity-50"
              >
                Block
              </button>
            ) : null}
            {canCancel && !["completed", "cancelled"].includes(run.status) ? (
              <button
                type="button"
                disabled={isUpdating}
                onClick={() => onRunStatus("cancelled")}
                className="inline-flex items-center gap-2 rounded-md border border-rose-400/40 px-3 py-2 text-sm text-rose-100 disabled:opacity-50"
              >
                <Ban className="h-4 w-4" aria-hidden="true" />
                Cancel
              </button>
            ) : null}
            {canCancel ? (
              <button
                type="button"
                disabled={isUpdating}
                onClick={() => onArchive(true)}
                className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-muted hover:text-raven-text disabled:opacity-50"
              >
                <Archive className="h-4 w-4" aria-hidden="true" />
                Archive
              </button>
            ) : null}
          </div>
        ) : canCancel && run.archived_at ? (
          <button
            type="button"
            disabled={isUpdating}
            onClick={() => onArchive(false)}
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm hover:border-raven-violet disabled:opacity-50"
          >
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            Restore
          </button>
        ) : null}
      </div>

      <div className="mt-4">
        <div className="mb-2 flex items-center justify-between text-xs text-raven-muted">
          <span>
            {complete} of {steps.length} steps complete
          </span>
          <span>{progress}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded bg-raven-bg">
          <div
            className="h-full bg-raven-violet"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div className="mt-4 space-y-3">
        {steps.map((step) => (
          <RunStep
            key={step.id}
            step={step}
            canUpdate={
              canUpdate &&
              !run.archived_at &&
              !["completed", "cancelled"].includes(run.status)
            }
            isUpdating={isUpdating}
            onUpdate={(status, note) => onStepStatus(step, status, note)}
          />
        ))}
      </div>
    </article>
  );
}

function RunStep({
  step,
  canUpdate,
  isUpdating,
  onUpdate,
}: {
  step: PlaybookRunStep;
  canUpdate: boolean;
  isUpdating: boolean;
  onUpdate: (status: PlaybookRunStepStatus, note: string) => void;
}): JSX.Element {
  const [status, setStatus] = useState<PlaybookRunStepStatus>(step.status);
  const [note, setNote] = useState(step.analyst_note ?? "");
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            {step.status === "completed" ? (
              <CheckCircle2
                className="h-4 w-4 text-emerald-300"
                aria-hidden="true"
              />
            ) : (
              <CircleDot className="h-4 w-4 text-raven-cyan" aria-hidden="true" />
            )}
            <h3 className="text-sm font-medium">{step.step.title}</h3>
            {step.step.required ? (
              <span className="text-xs text-amber-200">Required</span>
            ) : null}
          </div>
          <p className="mt-2 text-sm leading-6 text-raven-muted">
            {step.step.description}
          </p>
          {step.step.expected_output ? (
            <p className="mt-2 text-xs text-raven-muted">
              Expected: {step.step.expected_output}
            </p>
          ) : null}
        </div>
        <WorkflowBadge value={step.status} />
      </div>
      {canUpdate ? (
        <div className="mt-3 grid gap-2 md:grid-cols-[180px_1fr_auto]">
          <select
            value={status}
            onChange={(event) =>
              setStatus(event.target.value as PlaybookRunStepStatus)
            }
            className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm"
          >
            {stepStatuses
              .filter((value) => !step.step.required || value !== "skipped")
              .map((value) => (
                <option key={value} value={value}>
                  {label(value)}
                </option>
              ))}
          </select>
          <input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Analyst note"
            className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm outline-none focus:border-raven-violet"
          />
          <button
            type="button"
            disabled={isUpdating}
            onClick={() => onUpdate(status, note)}
            className="inline-flex items-center justify-center gap-2 rounded-md bg-raven-violet px-3 py-2 text-sm text-white disabled:opacity-50"
          >
            {isUpdating ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : null}
            Save
          </button>
        </div>
      ) : step.analyst_note ? (
        <p className="mt-3 text-sm text-raven-muted">{step.analyst_note}</p>
      ) : null}
    </div>
  );
}

function WorkflowBadge({ value }: { value: string }): JSX.Element {
  return (
    <span className="inline-flex rounded border border-raven-border bg-raven-bg px-2 py-1 text-xs capitalize text-raven-muted">
      {label(value)}
    </span>
  );
}

function label(value: string): string {
  return value.replace(/_/g, " ");
}

async function invalidatePlaybooks(
  queryClient: ReturnType<typeof useQueryClient>,
  investigationId: string,
): Promise<void> {
  await Promise.all([
    queryClient.invalidateQueries({
      queryKey: ["playbook-runs", investigationId],
    }),
    queryClient.invalidateQueries({ queryKey: ["timeline", investigationId] }),
    queryClient.invalidateQueries({ queryKey: ["findings", investigationId] }),
    queryClient.invalidateQueries({ queryKey: ["reports", investigationId] }),
  ]);
}
