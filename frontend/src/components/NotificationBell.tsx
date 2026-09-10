import { Bell, CheckCheck, ExternalLink, Inbox, Loader2, X } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { createPortal } from "react-dom";
import { useEffect, useRef, useState } from "react";

import {
  ApiError,
  dismissNotification,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "../lib/api";
import { safeArray, safeInternalRoute, safeNumber, safeString } from "../lib/safe";
import type { NotificationItem } from "../types";

export function NotificationBell(): JSX.Element {
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const notifications = useQuery({
    queryKey: ["notifications", "bell"],
    queryFn: () => listNotifications({ status: "unread", limit: 5 }),
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
  });
  const unread = safeNumber(notifications.data?.unread);
  const items = safeArray(notifications.data?.items);
  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["notifications"] });
    await queryClient.invalidateQueries({ queryKey: ["dashboard-notifications"] });
  };
  const readMutation = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: invalidate,
  });
  const dismissMutation = useMutation({
    mutationFn: dismissNotification,
    onSuccess: invalidate,
  });
  const markAllMutation = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: invalidate,
  });
  useEffect(() => {
    if (!open) return undefined;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    const closeOnOutsideClick = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!panelRef.current?.contains(target) && !buttonRef.current?.contains(target)) setOpen(false);
    };
    document.addEventListener("keydown", closeOnEscape);
    document.addEventListener("pointerdown", closeOnOutsideClick);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      document.removeEventListener("pointerdown", closeOnOutsideClick);
    };
  }, [open]);

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="relative inline-flex h-9 w-9 items-center justify-center rounded-md border border-raven-border bg-raven-panelSoft text-raven-muted hover:border-raven-violet hover:text-raven-text"
        aria-label="Open activity inbox"
        aria-expanded={open}
        aria-controls="activity-inbox-overlay"
      >
        <Bell className="h-4 w-4" aria-hidden="true" />
        {unread > 0 ? (
          <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-raven-violet px-1.5 py-0.5 text-center text-[10px] font-semibold text-white">
            {unread > 99 ? "99+" : unread}
          </span>
        ) : null}
      </button>

      {open ? createPortal(
        <div ref={panelRef} id="activity-inbox-overlay" role="dialog" aria-label="Activity Inbox" className="fixed inset-x-3 top-16 z-[100] flex max-h-[calc(100dvh-5rem)] flex-col overflow-hidden rounded-lg border border-raven-border bg-raven-panel shadow-glow sm:left-auto sm:right-4 sm:w-[min(22rem,calc(100vw-1.5rem))] lg:bottom-4 lg:left-72 lg:right-auto lg:top-auto lg:max-h-[min(36rem,calc(100dvh-2rem))]">
          <div className="flex items-center justify-between gap-3 border-b border-raven-border px-4 py-3">
            <div>
              <p className="text-sm font-semibold text-raven-text">Activity Inbox</p>
              <p className="text-xs text-raven-muted">{unread} unread alerts</p>
            </div>
            <div className="flex items-center gap-2"><button
                type="button"
                onClick={() => void markAllMutation.mutate()}
                disabled={unread === 0 || markAllMutation.isPending}
                title={unread === 0 ? "There are no unread alerts." : undefined}
                className="inline-flex items-center gap-1 rounded border border-raven-border px-2 py-1 text-xs text-raven-muted hover:border-raven-violet hover:text-raven-text disabled:cursor-not-allowed disabled:opacity-50"
              ><CheckCheck className="h-3.5 w-3.5" aria-hidden="true" />Read all</button><button type="button" onClick={() => setOpen(false)} className="rounded border border-raven-border p-1 text-raven-muted hover:text-raven-text" aria-label="Close activity inbox"><X className="h-4 w-4" /></button></div>
          </div>

          <div className="themed-scrollbar min-h-0 flex-1 overscroll-contain overflow-y-auto p-3">
            {notifications.isLoading ? (
              <div className="flex items-center justify-center gap-2 py-8 text-sm text-raven-muted">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                Loading alerts
              </div>
            ) : notifications.isError ? (
              <div className="rounded-md border border-amber-300/30 bg-amber-500/10 p-3 text-sm text-amber-100">
                {friendlyError(notifications.error)}
              </div>
            ) : items.length === 0 ? (
              <div className="rounded-md border border-dashed border-raven-border p-5 text-center text-sm text-raven-muted">
                <Inbox className="mx-auto mb-2 h-5 w-5" aria-hidden="true" />
                No pending alerts.
              </div>
            ) : (
              <div className="space-y-2">
                {items.map((item) => (
                  <NotificationPreview
                    key={item.id}
                    item={item}
                    onRead={() => readMutation.mutate(item.id)}
                    onDismiss={() => dismissMutation.mutate(item.id)}
                    onOpen={() => setOpen(false)}
                  />
                ))}
              </div>
            )}
          </div>

          <div className="border-t border-raven-border px-4 py-3">
            <Link
              to="/notifications"
              onClick={() => setOpen(false)}
              className="inline-flex w-full items-center justify-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-text hover:border-raven-violet"
            >
              <Inbox className="h-4 w-4" aria-hidden="true" />
              Open activity inbox
            </Link>
          </div>
        </div>, document.body,
      ) : null}
    </div>
  );
}

function NotificationPreview({
  item,
  onRead,
  onDismiss,
  onOpen,
}: {
  item: NotificationItem;
  onRead: () => void;
  onDismiss: () => void;
  onOpen: () => void;
}): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-bg/50 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <span className={severityClass(item.severity)}>{label(item.severity)}</span>
          <p className="mt-2 break-words text-sm font-medium text-raven-text">
            {safeString(item.title, "Workflow alert")}
          </p>
          <p className="mt-1 break-words text-xs leading-5 text-raven-muted">
            {safeString(item.message, "A workflow item needs attention.")}
          </p>
          <p className="mt-2 text-[11px] text-raven-muted">{label(item.notification_type)} · {new Date(item.created_at).toLocaleString()}</p>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          className="rounded border border-raven-border p-1 text-raven-muted hover:border-raven-violet hover:text-raven-text"
          aria-label="Dismiss notification"
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={onRead}
          className="rounded border border-raven-border px-2 py-1 text-xs text-raven-muted hover:border-raven-violet hover:text-raven-text"
        >
          Mark read
        </button>
        {item.action_url ? (
          <Link
            to={safeInternalRoute(item.action_url, "/notifications")}
            onClick={onOpen}
            className="inline-flex items-center gap-1 rounded border border-raven-border px-2 py-1 text-xs text-raven-cyan hover:border-raven-violet"
          >
            Open
            <ExternalLink className="h-3 w-3" aria-hidden="true" />
          </Link>
        ) : null}
      </div>
    </div>
  );
}

function severityClass(value: string): string {
  const base = "inline-flex rounded border px-2 py-0.5 text-[11px] font-medium";
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

function label(value: string): string {
  return value ? value.replace(/_/g, " ") : "info";
}

function friendlyError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.status >= 500 || error.status === 0
      ? "Activity alerts are temporarily unavailable."
      : error.message;
  }
  return "Activity alerts are temporarily unavailable.";
}
