import {
  Archive,
  CheckCircle2,
  Edit3,
  PlusCircle,
  RotateCcw,
} from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { InvestigationTabs } from "../components/InvestigationTabs";
import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import {
  createTask,
  deleteTask,
  listInvestigationMembers,
  listTasks,
  updateTask,
} from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import { useAuth } from "../lib/useAuth";
import type {
  InvestigationMember,
  InvestigationTask,
  InvestigationTaskUpdateRequest,
  TaskPriority,
  TaskStatus,
} from "../types";

const statuses: Array<"all" | TaskStatus> = [
  "all",
  "todo",
  "in_progress",
  "blocked",
  "validation",
  "completed",
];
const priorities: TaskPriority[] = ["critical", "urgent", "high", "medium", "low"];
const priorityFilters: Array<"all" | TaskPriority> = ["all", ...priorities];

export function TasksPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [editing, setEditing] = useState<InvestigationTask | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [statusFilter, setStatusFilter] = useState<"all" | TaskStatus>("all");
  const [priorityFilter, setPriorityFilter] = useState<"all" | TaskPriority>("all");
  const [toast, setToast] = useState<ToastState | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const tasks = useQuery({
    queryKey: ["tasks", investigationId, showArchived],
    queryFn: () => listTasks(investigationId, showArchived),
  });
  const members = useQuery({
    queryKey: ["members", investigationId],
    queryFn: () => listInvestigationMembers(investigationId),
  });
  const createMutation = useMutation({
    mutationFn: (values: TaskFormValues) => createTask(investigationId, values),
    onSuccess: async () => {
      await invalidateTaskData(queryClient, investigationId);
      setIsCreating(false);
      setToast({ kind: "success", message: "Task created." });
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({
      id,
      values,
    }: {
      id: string;
      values: InvestigationTaskUpdateRequest;
    }) =>
      updateTask(investigationId, id, values),
    onSuccess: async () => {
      await invalidateTaskData(queryClient, investigationId);
      setEditing(null);
      setToast({ kind: "success", message: "Task updated." });
    },
  });
  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteTask(investigationId, id),
    onSuccess: async () => {
      await invalidateTaskData(queryClient, investigationId);
      setToast({ kind: "success", message: "Task archived." });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Unable to delete task.",
      });
    },
  });

  const filteredTasks = useMemo(() => {
    const items = tasks.data?.items ?? [];
    return items.filter((task) => {
      const statusMatch = statusFilter === "all" || task.status === statusFilter;
      const priorityMatch =
        priorityFilter === "all" || task.priority === priorityFilter;
      return statusMatch && priorityMatch;
    });
  }, [priorityFilter, statusFilter, tasks.data?.items]);

  if (tasks.isLoading) {
    return <LoadingBlock label="Loading tasks" />;
  }
  if (tasks.isError) {
    return <ErrorBlock message={tasks.error} />;
  }

  return (
    <>
      <PageHeader
        title="Tasks"
        eyebrow="Case tasking"
        actions={
          <button
            type="button"
            onClick={() => setIsCreating(true)}
            className="inline-flex items-center gap-2 rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500"
          >
            <PlusCircle className="h-4 w-4" aria-hidden="true" />
            New task
          </button>
        }
      />
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}
      <InvestigationTabs />

      <div className="mb-5 flex flex-wrap gap-2">
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
        {statuses.map((status) => (
          <button
            key={status}
            type="button"
            onClick={() => setStatusFilter(status)}
            className={[
              "rounded-md border px-3 py-2 text-sm capitalize",
              statusFilter === status
                ? "border-raven-violet bg-raven-violet text-white"
                : "border-raven-border text-raven-muted hover:border-raven-violet hover:text-raven-text",
            ].join(" ")}
          >
            {status.replace(/_/g, " ")}
          </button>
        ))}
        <span className="ex-1 hidden h-9 w-px bg-raven-border sm:block" />
        {priorityFilters.map((priority) => (
          <button
            key={priority}
            type="button"
            onClick={() => setPriorityFilter(priority)}
            className={[
              "rounded-md border px-3 py-2 text-sm capitalize",
              priorityFilter === priority
                ? "border-raven-violet bg-raven-violet text-white"
                : "border-raven-border text-raven-muted hover:border-raven-violet hover:text-raven-text",
            ].join(" ")}
          >
            {priority === "all" ? "All priorities" : priority}
          </button>
        ))}
      </div>

      {filteredTasks.length ? (
        <div className="space-y-4">
          {filteredTasks.map((task) => (
            <article
              key={task.id}
              className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"
            >
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusPill status={task.status} />
                    <PriorityPill priority={task.priority} />
                    {task.completed_at ? (
                      <span className="inline-flex items-center gap-1 rounded border border-emerald-400/30 bg-emerald-500/10 px-2 py-1 text-xs text-emerald-100">
                        <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
                        completed
                      </span>
                    ) : null}
                    {task.archived_at ? (
                      <span className="rounded border border-amber-400/30 bg-amber-500/10 px-2 py-1 text-xs text-amber-100">
                        archived
                      </span>
                    ) : null}
                  </div>
                  <h2 className="mt-3 font-semibold">{task.title}</h2>
                  {task.description ? (
                    <p className="mt-2 text-sm leading-6 text-raven-muted">
                      {task.description}
                    </p>
                  ) : null}
                  <p className="mt-3 text-xs text-raven-muted">
                    Created {new Date(task.created_at).toLocaleString()}
                    {task.due_date
                      ? ` - due ${new Date(task.due_date).toLocaleDateString()}`
                      : ""}
                    {task.finding_id ? ` - linked finding ${task.finding_id}` : ""}
                  </p>
                  {task.remediation_link ? (
                    <p className="mt-2 break-all text-xs text-raven-cyan">
                      Remediation: {task.remediation_link}
                    </p>
                  ) : null}
                  {task.blockers ? (
                    <p className="mt-2 break-words rounded-md border border-rose-400/20 bg-rose-500/5 p-2 text-xs text-rose-100">
                      Blockers: {task.blockers}
                    </p>
                  ) : null}
                  {task.playbook_run_id ? (
                    <p className="mt-2 break-all text-xs text-raven-muted">
                      Linked playbook run: {task.playbook_run_id}
                    </p>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-2">
                  {!task.archived_at && !taskClosed(task.status) ? (
                    <button
                      type="button"
                      onClick={() =>
                        updateMutation.mutate({
                          id: task.id,
                          values: { status: "completed" },
                        })
                      }
                      className="inline-flex items-center gap-2 rounded-md border border-emerald-400/30 px-3 py-2 text-sm text-emerald-100 hover:bg-emerald-500/10"
                    >
                      <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                      Coeplete
                    </button>
                  ) : null}
                  {!task.archived_at ? (
                  <button
                    type="button"
                    onClick={() => setEditing(task)}
                    className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-text hover:border-raven-violet"
                  >
                    <Edit3 className="h-4 w-4" aria-hidden="true" />
                    Edit
                  </button>
                  ) : null}
                  {task.archived_at ? (
                    <button
                      type="button"
                      onClick={() =>
                        updateMutation.mutate({
                          id: task.id,
                          values: { archived: false },
                        })
                      }
                      className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-text hover:border-raven-violet"
                    >
                      <RotateCcw className="h-4 w-4" aria-hidden="true" />
                      Restore
                    </button>
                  ) : (
                  <button
                    type="button"
                    onClick={() => deleteMutation.mutate(task.id)}
                    disabled={deleteMutation.isPending}
                    className="inline-flex items-center gap-2 rounded-md border border-rose-400/30 px-3 py-2 text-sm text-rose-100 hover:bg-rose-500/10 disabled:opacity-60"
                  >
                    <Archive className="h-4 w-4" aria-hidden="true" />
                    Archive
                  </button>
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyBlock
          title="No operational tasks"
          message="Tasks coordinate validation, remediation, reporting, and follow-up work."
          nextStep="Create or adjust a task filter to surface the next analyst action."
          permission="Contributors can manage assigned work; viewers have read-only access."
        />
      )}

      {isCreating ? (
        <TaskModal
          title="Create task"
          members={members.data ?? []}
          isSaving={createMutation.isPending}
          error={createMutation.error?.message}
          onClose={() => {
            createMutation.reset();
            setIsCreating(false);
          }}
          onSubmit={(values) => createMutation.mutate(values)}
        />
      ) : null}
      {editing ? (
        <TaskModal
          title="Edit task"
          task={editing}
          members={members.data ?? []}
          isSaving={updateMutation.isPending}
          error={updateMutation.error?.message}
          onClose={() => {
            updateMutation.reset();
            setEditing(null);
          }}
          onSubmit={(values) => updateMutation.mutate({ id: editing.id, values })}
        />
      ) : null}
    </>
  );
}

function taskClosed(status: TaskStatus): boolean {
  return status === "completed";
}

interface TaskFormValues {
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  due_date: string | null;
  assigned_to: string | null;
  remediation_link: string | null;
  blockers: string | null;
  finding_id: string | null;
  playbook_run_id: string | null;
}

function TaskModal({
  title,
  task,
  members,
  error,
  isSaving,
  onClose,
  onSubmit,
}: {
  title: string;
  task?: InvestigationTask;
  members: InvestigationMember[];
  error?: string;
  isSaving: boolean;
  onClose: () => void;
  onSubmit: (values: TaskFormValues) => void;
}): JSX.Element {
  const [taskTitle, setTaskTitle] = useState(task?.title ?? "");
  const [description, setDescription] = useState(task?.description ?? "");
  const [status, setStatus] = useState<TaskStatus>(task?.status ?? "todo");
  const [priority, setPriority] = useState<TaskPriority>(task?.priority ?? "medium");
  const [dueDate, setDueDate] = useState(
    task?.due_date ? task.due_date.slice(0, 10) : "",
  );
  const [assignedTo, setAssignedTo] = useState(task?.assigned_to ?? "");
  const [remediationLink, setRemediationLink] = useState(
    task?.remediation_link ?? "",
  );
  const [blockers, setBlockers] = useState(task?.blockers ?? "");
  const [findingId, setFindingId] = useState(task?.finding_id ?? "");
  const [playbookRunId, setPlaybookRunId] = useState(
    task?.playbook_run_id ?? "",
  );
  const [validationError, setValidationError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (!taskTitle.trim()) {
      setValidationError("Task title is required.");
      return;
    }
    setValidationError(null);
    onSubmit({
      title: taskTitle.trim(),
      description: description.trim() || null,
      status,
      priority,
      due_date: dueDate ? new Date(`${dueDate}T12:00:00Z`).toISOString() : null,
      assigned_to: assignedTo.trim() || null,
      remediation_link: remediationLink.trim() || null,
      blockers: blockers.trim() || null,
      finding_id: findingId.trim() || null,
      playbook_run_id: playbookRunId.trim() || null,
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-2xl rounded-lg border border-raven-border bg-raven-panel p-5 shadow-glow"
      >
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-xl font-semibold">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            className="rounded-md border border-raven-border px-3 py-1.5 text-sm text-raven-muted hover:text-raven-text disabled:opacity-60"
          >
            Close
          </button>
        </div>

        <label className="mt-5 block text-sm text-raven-muted" htmlFor="task-title">
          Title
        </label>
        <input
          id="task-title"
          value={taskTitle}
          onChange={(event) => setTaskTitle(event.target.value)}
          className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
        />

        <label
          className="mt-4 block text-sm text-raven-muted"
          htmlFor="task-description"
        >
          Description
        </label>
        <textarea
          id="task-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={4}
          className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
        />

        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <label className="block text-sm text-raven-muted" htmlFor="task-status">
            Status
            <select
              id="task-status"
              value={status}
              onChange={(event) => setStatus(event.target.value as TaskStatus)}
              className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
            >
              {statuses.filter((item) => item !== "all").map((item) => (
                <option key={item} value={item}>
                  {item.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm text-raven-muted" htmlFor="task-priority">
            Priority
            <select
              id="task-priority"
              value={priority}
              onChange={(event) => setPriority(event.target.value as TaskPriority)}
              className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
            >
              {priorities.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm text-raven-muted" htmlFor="task-due">
            Due date
            <input
              id="task-due"
              type="date"
              value={dueDate}
              onChange={(event) => setDueDate(event.target.value)}
              className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
            />
          </label>
        </div>

        <label className="mt-4 block text-sm text-raven-muted" htmlFor="task-assignee">
          Assigned member
        </label>
        <select
          id="task-assignee"
          value={assignedTo}
          onChange={(event) => setAssignedTo(event.target.value)}
          className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
        >
          <option value="">Unassigned</option>
          {members.map((member) => (
            <option key={member.id} value={member.user_id}>
              {member.username} ({member.role})
            </option>
          ))}
        </select>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="block text-sm text-raven-muted" htmlFor="task-finding">
            Linked finding ID
            <input
              id="task-finding"
              value={findingId}
              onChange={(event) => setFindingId(event.target.value)}
              placeholder="Optional finding UUID"
              className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
            />
          </label>
          <label
            className="block text-sm text-raven-muted"
            htmlFor="task-remediation"
          >
            Remediation link
            <input
              id="task-remediation"
              value={remediationLink}
              onChange={(event) => setRemediationLink(event.target.value)}
              placeholder="Optional ticket or evidence URL"
              className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
            />
          </label>
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="block text-sm text-raven-muted" htmlFor="task-playbook">
            Linked playbook run
            <input
              id="task-playbook"
              value={playbookRunId}
              onChange={(event) => setPlaybookRunId(event.target.value)}
              placeholder="Optional playbook run UUID"
              className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
            />
          </label>
          <label className="block text-sm text-raven-muted" htmlFor="task-blockers">
            Blockers
            <textarea
              id="task-blockers"
              value={blockers}
              onChange={(event) => setBlockers(event.target.value)}
              rows={3}
              placeholder="Dependencies or operational blockers"
              className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
            />
          </label>
        </div>

        {validationError ?? error ? (
          <div className="mt-4 rounded-md border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">
            {validationError ?? error}
          </div>
        ) : null}

        <div className="mt-5 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            className="rounded-md border border-raven-border px-4 py-2 text-sm text-raven-muted hover:text-raven-text disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSaving}
            className="rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-60"
          >
            {isSaving ? "Saving" : "Save task"}
          </button>
        </div>
      </form>
    </div>
  );
}

function StatusPill({ status }: { status: TaskStatus }): JSX.Element {
  const classes: Record<TaskStatus, string> = {
    todo: "border-slate-400/30 bg-slate-400/10 text-slate-200",
    in_progress: "border-cyan-400/30 bg-cyan-500/10 text-cyan-100",
    blocked: "border-rose-400/30 bg-rose-500/10 text-rose-100",
    validation: "border-amber-400/30 bg-amber-500/10 text-amber-100",
    completed: "border-emerald-400/30 bg-emerald-500/10 text-emerald-100",
  };
  return (
    <span
      className={[
        "rounded border px-2 py-1 text-xs capitalize",
        classes[status],
      ].join(" ")}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}

function PriorityPill({ priority }: { priority: TaskPriority }): JSX.Element {
  const classes: Record<TaskPriority, string> = {
    critical: "border-rose-400/30 bg-rose-500/10 text-rose-100",
    urgent: "border-fuchsia-400/30 bg-fuchsia-500/10 text-fuchsia-100",
    high: "border-orange-400/30 bg-orange-500/10 text-orange-100",
    medium: "border-cyan-400/30 bg-cyan-500/10 text-cyan-100",
    low: "border-raven-border text-raven-muted",
  };
  return (
    <span
      className={[
        "rounded border px-2 py-1 text-xs capitalize",
        classes[priority],
      ].join(" ")}
    >
      {priority}
    </span>
  );
}

async function invalidateTaskData(
  queryClient: ReturnType<typeof useQueryClient>,
  investigationId: string,
): Promise<void> {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["tasks", investigationId] }),
    queryClient.invalidateQueries({ queryKey: ["timeline", investigationId] }),
    queryClient.invalidateQueries({
      queryKey: ["investigation-analytics", investigationId],
    }),
  ]);
}
