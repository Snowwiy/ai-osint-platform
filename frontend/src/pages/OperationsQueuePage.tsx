import { Archive, Pin, RefreshCw, SlidersHorizontal } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import {
  applyInvestigationBulkAction,
  getAnalystWorkload,
  getFeatureAvailability,
  getInvestigationQueue,
  listPlaybooks,
  listTags,
  setInvestigationPinned,
} from "../lib/api";
import type {
  InvestigationBulkAction,
  InvestigationBulkRequest,
  InvestigationPriority,
  InvestigationQueueFilters,
  InvestigationStatus,
  QueueSort,
  QueueStatusFilter,
  RiskFilter,
} from "../types";

const queueStatuses: QueueStatusFilter[] = [
  "active",
  "monitoring",
  "remediation",
  "completed",
  "archived",
];
const priorities: InvestigationPriority[] = ["urgent", "high", "medium", "low"];
const riskLevels: RiskFilter[] = ["critical", "high", "medium", "low"];
const sortOptions: QueueSort[] = [
  "highest_risk",
  "overdue",
  "most_findings",
  "least_activity",
  "newest",
  "oldest",
];
const bulkActions: InvestigationBulkAction[] = [
  "assign_owner",
  "assign_reviewer",
  "update_priority",
  "update_tags",
  "change_status",
  "add_playbook",
  "generate_summary",
  "archive",
];

export function OperationsQueuePage(): JSX.Element {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<InvestigationQueueFilters>({
    sort: "highest_risk",
    limit: 100,
  });
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkAction, setBulkAction] =
    useState<InvestigationBulkAction>("update_priority");
  const [bulkValue, setBulkValue] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);
  const queue = useQuery({
    queryKey: ["investigation-queue", filters],
    queryFn: () => getInvestigationQueue(filters),
  });
  const features = useQuery({
    queryKey: ["feature-availability"],
    queryFn: getFeatureAvailability,
    staleTime: 30_000,
  });
  const bulkEnabled =
    features.data?.feature_flags?.enable_bulk_actions !== false;
  const playbooksEnabled =
    features.data?.feature_flags?.enable_playbooks !== false;
  const tags = useQuery({ queryKey: ["tags"], queryFn: listTags });
  const analysts = useQuery({
    queryKey: ["analyst-workload"],
    queryFn: getAnalystWorkload,
  });
  const playbooks = useQuery({
    queryKey: ["playbooks"],
    queryFn: listPlaybooks,
    enabled: playbooksEnabled,
  });
  const queueItems = useMemo(
    () => queue.data?.items ?? [],
    [queue.data?.items],
  );
  const tagItems = tags.data?.items ?? [];
  const analystItems = analysts.data?.items ?? [];
  const visibleIds = useMemo(
    () => queueItems.map((item) => item.id),
    [queueItems],
  );
  const pinMutation = useMutation({
    mutationFn: ({
      investigationId,
      pinned,
    }: {
      investigationId: string;
      pinned: boolean;
    }) => setInvestigationPinned(investigationId, pinned),
    onSuccess: async () => {
      await invalidateOperations(queryClient);
    },
  });
  const bulkMutation = useMutation({
    mutationFn: (body: InvestigationBulkRequest) =>
      applyInvestigationBulkAction(body),
    onSuccess: async (response) => {
      await invalidateOperations(queryClient);
      setSelected(new Set());
      setConfirming(false);
      setToast({
        kind: response.failed ? "error" : "success",
        message: `${response.succeeded} completed, ${response.failed} failed.`,
      });
    },
    onError: (error) => {
      setToast({ kind: "error", message: error.message });
    },
  });

  if (queue.isLoading) {
    return <LoadingBlock label="Loading investigation queue" />;
  }
  if (queue.isError) {
    return <ErrorBlock message={queue.error} />;
  }

  const allSelected =
    visibleIds.length > 0 && visibleIds.every((id) => selected.has(id));

  return (
    <>
      <PageHeader
        title="Investigation Queue"
        eyebrow="Cross-case triage"
        actions={
          <button
            type="button"
            onClick={() => void queue.refetch()}
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-text hover:border-raven-violet"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </button>
        }
      />
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}

      <section className="mb-5 grid gap-3 rounded-lg border border-raven-border bg-raven-panel/85 p-4 md:grid-cols-2 xl:grid-cols-6">
        <FilterSelect
          label="Status"
          value={filters.status ?? ""}
          options={queueStatuses}
          onChange={(value) =>
            setFilters((current) => ({
              ...current,
              status: value ? (value as QueueStatusFilter) : undefined,
            }))
          }
        />
        <FilterSelect
          label="Priority"
          value={filters.priority ?? ""}
          options={priorities}
          onChange={(value) =>
            setFilters((current) => ({
              ...current,
              priority: value ? (value as InvestigationPriority) : undefined,
            }))
          }
        />
        <FilterSelect
          label="Risk"
          value={filters.risk_level ?? ""}
          options={riskLevels}
          onChange={(value) =>
            setFilters((current) => ({
              ...current,
              risk_level: value ? (value as RiskFilter) : undefined,
            }))
          }
        />
        <FilterSelect
          label="Tag"
          value={filters.tag ?? ""}
          options={tagItems.map((tag) => tag.id)}
          labels={Object.fromEntries(
            tagItems.map((tag) => [tag.id, tag.name]),
          )}
          onChange={(value) =>
            setFilters((current) => ({
              ...current,
              tag: value || undefined,
            }))
          }
        />
        <FilterSelect
          label="Assigned analyst"
          value={filters.assigned_analyst ?? ""}
          options={analystItems.map((analyst) => analyst.user_id)}
          labels={Object.fromEntries(
            analystItems.map((analyst) => [
              analyst.user_id,
              analyst.username,
            ]),
          )}
          onChange={(value) =>
            setFilters((current) => ({
              ...current,
              assigned_analyst: value || undefined,
            }))
          }
        />
        <FilterSelect
          label="Sort"
          value={filters.sort ?? "highest_risk"}
          options={sortOptions}
          onChange={(value) =>
            setFilters((current) => ({
              ...current,
              sort: value as QueueSort,
            }))
          }
          allowEmpty={false}
        />
      </section>

      {bulkEnabled ? (
      <section className="mb-5 flex flex-wrap items-end gap-3 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-raven-muted">
            Bulk action
          </p>
          <select
            value={bulkAction}
            onChange={(event) => {
              setBulkAction(event.target.value as InvestigationBulkAction);
              setBulkValue("");
            }}
            className="mt-2 rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm"
          >
            {bulkActions.map((action) => (
              <option key={action} value={action}>
                {labelize(action)}
              </option>
            ))}
          </select>
        </div>
        <BulkValueControl
          action={bulkAction}
          value={bulkValue}
          onChange={setBulkValue}
          tags={tagItems}
          analysts={analystItems}
          playbooks={playbooks.data ?? []}
        />
        <button
          type="button"
          onClick={() => setConfirming(true)}
          disabled={!selected.size || !bulkValueReady(bulkAction, bulkValue)}
          className="inline-flex items-center gap-2 rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
          Apply to {selected.size}
        </button>
        <button
          type="button"
          onClick={() => setSelected(new Set())}
          disabled={!selected.size}
          className="rounded-md border border-raven-border px-3 py-2 text-sm text-raven-muted disabled:opacity-50"
        >
          Clear
        </button>
      </section>
      ) : (
        <div className="mb-5 rounded-lg border border-raven-border bg-raven-panel/70 p-4 text-sm text-raven-muted">
          Bulk actions are disabled by an administrator.
        </div>
      )}

      {queueItems.length ? (
        <div className="overflow-x-auto rounded-lg border border-raven-border">
          <table className="w-full min-w-[1180px] text-left text-sm">
            <thead className="bg-raven-panelSoft text-xs uppercase text-raven-muted">
              <tr>
                <th className="px-4 py-3">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={() =>
                      setSelected(
                        allSelected ? new Set() : new Set(visibleIds),
                      )
                    }
                    aria-label="Select all visible investigations"
                  />
                </th>
                <th className="px-4 py-3">Investigation</th>
                <th className="px-4 py-3">Triage</th>
                <th className="px-4 py-3">Risk</th>
                <th className="px-4 py-3">Findings</th>
                <th className="px-4 py-3">Tasks</th>
                <th className="px-4 py-3">Assignment</th>
                <th className="px-4 py-3">Activity</th>
                <th className="px-4 py-3">Pin</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-raven-border bg-raven-panel/70">
              {queueItems.map((item) => (
                <tr key={item.id}>
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selected.has(item.id)}
                      onChange={() => toggleSelection(selected, setSelected, item.id)}
                      aria-label={`Select ${item.title}`}
                    />
                  </td>
                  <td className="max-w-[280px] px-4 py-3">
                    <Link
                      to={`/investigations/${item.id}`}
                      className="break-words font-medium hover:text-raven-cyan"
                    >
                      {item.title}
                    </Link>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      <Pill value={item.status} />
                      <Pill value={`${item.priority} priority`} />
                      {(item.tags ?? []).map((tag) => (
                        <Pill key={tag.id} value={tag.name} />
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <strong>{item.triage_score}/100</strong>
                    <p className="mt-1 capitalize text-raven-muted">
                      {labelize(item.triage_category)}
                    </p>
                  </td>
                  <td className="px-4 py-3">
                    <strong>{item.risk_score}/100</strong>
                    <p className="mt-1 capitalize text-raven-muted">
                      {item.risk_level}
                    </p>
                  </td>
                  <td className="px-4 py-3">
                    {item.findings_count} total
                    <p className="mt-1 text-raven-muted">
                      {item.unresolved_findings} unresolved
                    </p>
                  </td>
                  <td className="px-4 py-3">
                    {item.open_tasks} open
                    <p
                      className={[
                        "mt-1",
                        item.overdue_tasks ? "text-rose-200" : "text-raven-muted",
                      ].join(" ")}
                    >
                      {item.overdue_tasks} overdue
                    </p>
                  </td>
                  <td className="px-4 py-3">
                    <p className="break-all text-xs">Owner {item.owner_id}</p>
                    <p className="mt-1 text-raven-muted">
                      {(item.assigned_analyst_ids ?? []).length} assigned
                    </p>
                  </td>
                  <td className="px-4 py-3 text-raven-muted">
                    {item.last_activity_at
                      ? new Date(item.last_activity_at).toLocaleString()
                      : "No activity yet"}
                    {item.overdue ? (
                      <p className="mt-1 text-rose-200">Case overdue</p>
                    ) : null}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() =>
                        pinMutation.mutate({
                          investigationId: item.id,
                          pinned: !item.pinned,
                        })
                      }
                      className={[
                        "rounded-md border p-2",
                        item.pinned
                          ? "border-raven-violet text-violet-100"
                          : "border-raven-border text-raven-muted",
                      ].join(" ")}
                      title={item.pinned ? "Unpin" : "Pin"}
                    >
                      <Pin className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyBlock
          title="No investigations in this queue"
          message="The queue organizes accessible cases by status, priority, risk, ownership, and activity."
          nextStep="Clear a filter or create an authorized investigation."
        />
      )}

      {confirming ? (
        <ConfirmationModal
          action={bulkAction}
          count={selected.size}
          isPending={bulkMutation.isPending}
          onCancel={() => setConfirming(false)}
          onConfirm={() =>
            bulkMutation.mutate(
              buildBulkRequest([...selected], bulkAction, bulkValue),
            )
          }
        />
      ) : null}
    </>
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
    <label className="text-xs text-raven-muted">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
      >
        {allowEmpty ? <option value="">All</option> : null}
        {options.map((option) => (
          <option key={option} value={option}>
            {labels[option] ?? labelize(option)}
          </option>
        ))}
      </select>
    </label>
  );
}

function BulkValueControl({
  action,
  value,
  onChange,
  tags,
  analysts,
  playbooks,
}: {
  action: InvestigationBulkAction;
  value: string;
  onChange: (value: string) => void;
  tags: Array<{ id: string; name: string }>;
  analysts: Array<{ user_id: string; username: string }>;
  playbooks: Array<{ id: string; name: string }>;
}): JSX.Element | null {
  if (["archive", "generate_summary"].includes(action)) {
    return null;
  }
  let options: Array<{ value: string; label: string }> = [];
  if (action === "update_priority") {
    options = priorities.map((item) => ({ value: item, label: item }));
  } else if (action === "update_tags") {
    options = tags.map((item) => ({ value: item.id, label: item.name }));
  } else if (action === "change_status") {
    options = [
      "intake",
      "active",
      "monitoring",
      "remediation",
      "validation",
      "completed",
      "archived",
    ].map((item) => ({ value: item, label: item }));
  } else if (action === "add_playbook") {
    options = playbooks.map((item) => ({ value: item.id, label: item.name }));
  } else if (action === "assign_owner" || action === "assign_reviewer") {
    options = analysts.map((item) => ({
      value: item.user_id,
      label: item.username,
    }));
  }
  return (
    <label className="min-w-56 text-xs text-raven-muted">
      Value
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
      >
        <option value="">Select value</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {labelize(option.label)}
          </option>
        ))}
      </select>
    </label>
  );
}

function ConfirmationModal({
  action,
  count,
  isPending,
  onCancel,
  onConfirm,
}: {
  action: InvestigationBulkAction;
  count: number;
  isPending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}): JSX.Element {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
      <section className="w-full max-w-lg rounded-lg border border-raven-border bg-raven-panel p-5">
        <div className="flex items-start gap-3">
          <Archive className="mt-1 h-5 w-5 text-amber-200" aria-hidden="true" />
          <div>
            <h2 className="text-lg font-semibold">Confirm bulk action</h2>
            <p className="mt-2 text-sm text-raven-muted">
              Apply <strong>{labelize(action)}</strong> to {count} selected
              investigation{count === 1 ? "" : "s"}? Each case is validated
              independently and partial failures are reported.
            </p>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={isPending}
            className="rounded-md border border-raven-border px-4 py-2 text-sm text-raven-muted"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isPending}
            className="rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {isPending ? "Applying" : "Confirm"}
          </button>
        </div>
      </section>
    </div>
  );
}

function buildBulkRequest(
  investigationIds: string[],
  action: InvestigationBulkAction,
  value: string,
): InvestigationBulkRequest {
  const request: InvestigationBulkRequest = {
    investigation_ids: investigationIds,
    action,
  };
  if (action === "assign_owner") request.owner_id = value;
  if (action === "assign_reviewer") request.reviewer_id = value;
  if (action === "update_priority") {
    request.priority = value as InvestigationPriority;
  }
  if (action === "update_tags") request.tag_ids = value ? [value] : [];
  if (action === "change_status") request.status = value as InvestigationStatus;
  if (action === "add_playbook") request.playbook_id = value;
  return request;
}

function bulkValueReady(action: InvestigationBulkAction, value: string): boolean {
  return ["archive", "generate_summary"].includes(action) || Boolean(value);
}

function toggleSelection(
  current: Set<string>,
  update: (value: Set<string>) => void,
  id: string,
): void {
  const next = new Set(current);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  update(next);
}

function Pill({ value }: { value: string }): JSX.Element {
  return (
    <span className="rounded border border-raven-border px-2 py-1 capitalize text-raven-muted">
      {labelize(value)}
    </span>
  );
}

function labelize(value: string): string {
  return value.replace(/_/g, " ");
}

async function invalidateOperations(
  queryClient: ReturnType<typeof useQueryClient>,
): Promise<void> {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["investigation-queue"] }),
    queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] }),
    queryClient.invalidateQueries({ queryKey: ["dashboard-triage"] }),
    queryClient.invalidateQueries({ queryKey: ["investigations"] }),
  ]);
}
