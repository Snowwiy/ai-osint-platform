import {
  Bell,
  CheckCheck,
  ExternalLink,
  Filter,
  RefreshCw,
  X,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { SavedViewsPanel } from "../components/SavedViewsPanel";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import {
  dismissNotification,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "../lib/api";
import { safeArray, safeDate, safeInternalRoute, safeString } from "../lib/safe";
import type {
  NotificationFilters,
  NotificationItem,
  NotificationSeverity,
  NotificationStatus,
} from "../types";

const statusOptions: NotificationStatus[] = [
  "unread",
  "read",
  "dismissed",
  "archived",
];
const severityOptions: NotificationSeverity[] = [
  "critical",
  "warning",
  "success",
  "info",
];
const typeOptions = [
  "user_approval_pending",
  "investigation_assigned",
  "finding_assigned",
  "report_ready",
  "report_approval_pending",
  "closure_review_pending",
  "closure_blocked",
  "closure_approved",
  "case_closed",
  "case_reopened",
  "scope_warning",
  "authorization_expired",
  "governance_warning",
  "ai_degraded",
  "system_health_warning",
  "deliverable_ready",
  "evidence_package_ready",
];

export function NotificationsPage(): JSX.Element {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<NotificationFilters>({
    limit: 50,
    offset: 0,
  });
  const [form, setForm] = useState({
    status: "",
    severity: "",
    notification_type: "",
  });
  const [toast, setToast] = useState<ToastState | null>(null);

  const notifications = useQuery({
    queryKey: ["notifications", filters],
    queryFn: () => listNotifications(filters),
    staleTime: 20_000,
  });
  const items = safeArray(notifications.data?.items);
  const unread = notifications.data?.unread ?? 0;
  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["notifications"] });
    await queryClient.invalidateQueries({ queryKey: ["dashboard-notifications"] });
  };
  const readMutation = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: async (response) => {
      setToast({ kind: "success", message: response.message });
      await invalidate();
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message:
          error instanceof Error ? error.message : "Notification could not be read.",
      });
    },
  });
  const dismissMutation = useMutation({
    mutationFn: dismissNotification,
    onSuccess: async (response) => {
      setToast({ kind: "success", message: response.message });
      await invalidate();
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message:
          error instanceof Error
            ? error.message
            : "Notification could not be dismissed.",
      });
    },
  });
  const markAllMutation = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: async (response) => {
      setToast({ kind: "success", message: response.message });
      await invalidate();
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message:
          error instanceof Error ? error.message : "Notifications could not be updated.",
      });
    },
  });

  function applyFilters(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setToast(null);
    setFilters({
      status: form.status as NotificationStatus | "",
      severity: form.severity as NotificationSeverity | "",
      notification_type: form.notification_type,
      limit: 50,
      offset: 0,
    });
  }

  return (
    <>
      <PageHeader
        title="Activity Inbox"
        eyebrow="Workflow alerts"
        actions={
          <>
            <button
              type="button"
              onClick={() => void markAllMutation.mutate()}
              disabled={unread === 0 || markAllMutation.isPending}
              className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-text hover:border-raven-violet disabled:cursor-not-allowed disabled:opacity-50"
            >
              <CheckCheck className="h-4 w-4" aria-hidden="true" />
              Mark all read
            </button>
            <button
              type="button"
              onClick={() => {
                setToast(null);
                void notifications.refetch();
              }}
              className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-text hover:border-raven-violet"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Refresh
            </button>
          </>
        }
      />

      {toast ? (
        <ToastBanner toast={toast} onDismiss={() => setToast(null)} />
      ) : null}

      <div className="mb-5">
        <SavedViewsPanel
          viewType="notifications"
          route="/notifications"
          filters={filters}
          onApply={(view) => {
            const next = view.filters;
            const nextFilters: NotificationFilters = {
              status:
                typeof next.status === "string"
                  ? (next.status as NotificationStatus)
                  : "",
              severity:
                typeof next.severity === "string"
                  ? (next.severity as NotificationSeverity)
                  : "",
              notification_type:
                typeof next.notification_type === "string"
                  ? next.notification_type
                  : "",
              limit: 50,
              offset: 0,
            };
            setFilters(nextFilters);
            setForm({
              status: String(nextFilters.status ?? ""),
              severity: String(nextFilters.severity ?? ""),
              notification_type: nextFilters.notification_type ?? "",
            });
            setToast({ kind: "success", message: `Loaded ${view.name}.` });
          }}
        />
      </div>

      <section className="mb-6 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-raven-text">
              Internal notifications only
            </h2>
            <p className="mt-1 text-sm text-raven-muted">
              Alerts are generated inside RavenTech for approvals, assignments,
              closure workflow, scope governance, and report readiness. No email,
              SMS, browser push, or third-party delivery is used.
            </p>
          </div>
          <div className="inline-flex items-center gap-2 rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm text-raven-muted">
            <Bell className="h-4 w-4 text-raven-cyan" aria-hidden="true" />
            {unread} unread
          </div>
        </div>
        <form onSubmit={applyFilters} className="grid gap-3 md:grid-cols-4">
          <label className="text-sm text-raven-muted">
            <span className="mb-1 block">Status</span>
            <select
              value={form.status}
              onChange={(event) =>
                setForm({ ...form, status: event.target.value })
              }
              className="w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text"
            >
              <option value="">All statuses</option>
              {statusOptions.map((status) => (
                <option key={status} value={status}>
                  {humanize(status)}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm text-raven-muted">
            <span className="mb-1 block">Severity</span>
            <select
              value={form.severity}
              onChange={(event) =>
                setForm({ ...form, severity: event.target.value })
              }
              className="w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text"
            >
              <option value="">All severities</option>
              {severityOptions.map((severity) => (
                <option key={severity} value={severity}>
                  {humanize(severity)}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm text-raven-muted md:col-span-2">
            <span className="mb-1 block">Alert type</span>
            <select
              value={form.notification_type}
              onChange={(event) =>
                setForm({ ...form, notification_type: event.target.value })
              }
              className="w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text"
            >
              <option value="">All alert types</option>
              {typeOptions.map((type) => (
                <option key={type} value={type}>
                  {humanize(type)}
                </option>
              ))}
            </select>
          </label>
          <div className="flex flex-wrap items-end gap-2 md:col-span-4">
            <button
              type="submit"
              className="inline-flex items-center gap-2 rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500"
            >
              <Filter className="h-4 w-4" aria-hidden="true" />
              Apply filters
            </button>
            <button
              type="button"
              onClick={() => {
                setForm({ status: "", severity: "", notification_type: "" });
                setFilters({ limit: 50, offset: 0 });
                setToast(null);
              }}
              className="rounded-md border border-raven-border px-4 py-2 text-sm text-raven-muted hover:text-raven-text"
            >
              Reset
            </button>
          </div>
        </form>
      </section>

      {notifications.isLoading ? (
        <LoadingBlock label="Loading activity inbox" />
      ) : null}
      {notifications.isError ? <ErrorBlock message={notifications.error} /> : null}
      {notifications.data && items.length === 0 ? (
        <EmptyBlock
          title="No alerts found"
          message="The activity inbox shows pending approvals, assigned work, closure blockers, scope warnings, report readiness, and governance notifications."
          nextStep="Adjust filters or continue working through investigations and review workflows."
        />
      ) : null}

      {items.length ? (
        <section className="space-y-3">
          {items.map((item) => (
            <NotificationRow
              key={item.id}
              item={item}
              onRead={() => readMutation.mutate(item.id)}
              onDismiss={() => dismissMutation.mutate(item.id)}
            />
          ))}
        </section>
      ) : null}
    </>
  );
}

function NotificationRow({
  item,
  onRead,
  onDismiss,
}: {
  item: NotificationItem;
  onRead: () => void;
  onDismiss: () => void;
}): JSX.Element {
  const created = safeDate(item.created_at);
  const title = safeString(item.title, "Workflow alert");
  const message = safeString(item.message, "A workflow item needs attention.");
  return (
    <article className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={severityClass(item.severity)}>
              {humanize(item.severity)}
            </span>
            <span className={statusClass(item.status)}>{humanize(item.status)}</span>
            <span className="rounded border border-raven-border px-2 py-1 text-xs text-raven-muted">
              {humanize(item.notification_type)}
            </span>
          </div>
          <h2 className="mt-3 break-words text-base font-semibold text-raven-text">
            {title}
          </h2>
          <p className="mt-2 break-words text-sm leading-6 text-raven-muted">
            {message}
          </p>
          <dl className="mt-4 grid gap-3 text-xs text-raven-muted sm:grid-cols-3">
            <div>
              <dt className="uppercase tracking-wide">Created</dt>
              <dd className="mt-1 text-raven-text">
                {created ? created.toLocaleString() : "Unknown"}
              </dd>
            </div>
            <div>
              <dt className="uppercase tracking-wide">Entity</dt>
              <dd className="mt-1 break-words text-raven-text">
                {humanize(item.entity_type)}
              </dd>
            </div>
            <div>
              <dt className="uppercase tracking-wide">Context</dt>
              <dd className="mt-1 break-words text-raven-text">
                {item.investigation_id
                  ? "Investigation workflow"
                  : item.engagement_id
                    ? "Engagement governance"
                    : "Platform workflow"}
              </dd>
            </div>
          </dl>
        </div>
        <div className="flex flex-wrap gap-2 lg:justify-end">
          {item.status !== "read" ? (
            <button
              type="button"
              onClick={onRead}
              className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-text hover:border-raven-violet"
            >
              <CheckCheck className="h-4 w-4" aria-hidden="true" />
              Mark read
            </button>
          ) : null}
          <button
            type="button"
            onClick={onDismiss}
            disabled={item.status === "dismissed"}
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-muted hover:border-raven-violet hover:text-raven-text disabled:cursor-not-allowed disabled:opacity-50"
          >
            <X className="h-4 w-4" aria-hidden="true" />
            Dismiss
          </button>
          {item.action_url ? (
            <Link
              to={safeInternalRoute(item.action_url, "/notifications")}
              className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-cyan hover:border-raven-violet"
            >
              <ExternalLink className="h-4 w-4" aria-hidden="true" />
              Open
            </Link>
          ) : null}
        </div>
      </div>
    </article>
  );
}

function statusClass(value: string): string {
  const base = "rounded border px-2 py-1 text-xs";
  if (value === "unread") {
    return `${base} border-raven-violet/60 bg-raven-violet/15 text-violet-100`;
  }
  if (value === "dismissed" || value === "archived") {
    return `${base} border-raven-border bg-raven-bg text-raven-muted`;
  }
  return `${base} border-emerald-300/40 bg-emerald-500/10 text-emerald-100`;
}

function severityClass(value: string): string {
  const base = "rounded border px-2 py-1 text-xs";
  if (value === "critical") {
    return `${base} border-rose-400/50 bg-rose-500/10 text-rose-100`;
  }
  if (value === "warning") {
    return `${base} border-amber-300/50 bg-amber-500/10 text-amber-100`;
  }
  if (value === "success") {
    return `${base} border-emerald-300/50 bg-emerald-500/10 text-emerald-100`;
  }
  return `${base} border-raven-border bg-raven-panelSoft text-raven-cyan`;
}

function humanize(value: string | null | undefined): string {
  return safeString(value, "unknown").replace(/_/g, " ");
}
