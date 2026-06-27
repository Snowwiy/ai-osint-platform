import { RefreshCw, Search, ShieldCheck, UserCheck, UserX } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { LongValue } from "../components/LongValue";
import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import {
  adminUserAction,
  listAdminUsers,
  updateAdminUserRole,
} from "../lib/api";
import { safeArray, safeDate, safeString } from "../lib/safe";
import { useAuth } from "../lib/useAuth";
import type {
  AccountStatus,
  AdminUser,
  AdminUserFilters,
  PlatformUserRole,
} from "../types";

type PendingAction =
  | { kind: "approve" | "reject" | "disable" | "reactivate"; user: AdminUser }
  | { kind: "role"; user: AdminUser; role: PlatformUserRole };

const statusOptions: AccountStatus[] = [
  "active",
  "pending",
  "disabled",
  "rejected",
];
const roleOptions: PlatformUserRole[] = ["admin", "analyst"];

export function AdminUsersPage(): JSX.Element {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<AdminUserFilters>({
    limit: 50,
    offset: 0,
  });
  const [form, setForm] = useState({
    search: "",
    status: "",
    role: "",
  });
  const [toast, setToast] = useState<ToastState | null>(null);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);

  const users = useQuery({
    queryKey: ["admin-users", filters],
    queryFn: () => listAdminUsers(filters),
    enabled: user?.role === "admin",
  });

  const actionMutation = useMutation({
    mutationFn: async (action: PendingAction) => {
      if (action.kind === "role") {
        return updateAdminUserRole(action.user.id, action.role);
      }
      return adminUserAction(action.user.id, action.kind);
    },
    onSuccess: async (response) => {
      setToast({ kind: "success", message: response.message });
      setPendingAction(null);
      await queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      await queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message:
          error instanceof Error ? error.message : "User action could not complete.",
      });
      setPendingAction(null);
    },
  });

  if (user?.role !== "admin") {
    return (
      <>
        <PageHeader title="Users" eyebrow="Admin only" />
        <ErrorBlock message="Administrator access is required to manage users." />
      </>
    );
  }

  function applyFilters(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setToast(null);
    setFilters({
      search: form.search,
      status: form.status as AccountStatus | "",
      role: form.role as PlatformUserRole | "",
      limit: 50,
      offset: 0,
    });
  }

  const items = safeArray(users.data?.items);

  return (
    <>
      <PageHeader
        title="User Administration"
        eyebrow="Access governance"
        actions={
          <button
            type="button"
            onClick={() => {
              setToast(null);
              void users.refetch();
            }}
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm hover:border-raven-violet"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </button>
        }
      />

      {toast ? (
        <ToastBanner toast={toast} onDismiss={() => setToast(null)} />
      ) : null}

      <section className="mb-6 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <div className="mb-4">
          <h2 className="text-base font-semibold text-raven-text">
            Registration governance
          </h2>
          <p className="mt-1 text-sm text-raven-muted">
            Public registration is controlled by environment settings. Invite
            codes are validated server-side only and are never displayed here.
          </p>
        </div>
        <form onSubmit={applyFilters} className="grid gap-3 md:grid-cols-4">
          <label className="text-sm text-raven-muted md:col-span-2">
            <span className="mb-1 block">Search users</span>
            <input
              value={form.search}
              onChange={(event) =>
                setForm({ ...form, search: event.target.value })
              }
              placeholder="username or email"
              className="w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
            />
          </label>
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
            <span className="mb-1 block">Role</span>
            <select
              value={form.role}
              onChange={(event) => setForm({ ...form, role: event.target.value })}
              className="w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text"
            >
              <option value="">All roles</option>
              {roleOptions.map((role) => (
                <option key={role} value={role}>
                  {humanize(role)}
                </option>
              ))}
            </select>
          </label>
          <div className="flex items-end gap-2 md:col-span-4">
            <button
              type="submit"
              className="inline-flex items-center gap-2 rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500"
            >
              <Search className="h-4 w-4" aria-hidden="true" />
              Apply filters
            </button>
            <button
              type="button"
              onClick={() => {
                setForm({ search: "", role: "", status: "" });
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

      {users.isLoading ? <LoadingBlock label="Loading users" /> : null}
      {users.isError ? <ErrorBlock message={users.error} /> : null}
      {users.data && items.length === 0 ? (
        <EmptyBlock
          title="No users found"
          message="User administration lists registered and bootstrap-created accounts without exposing password hashes or secrets."
          nextStep="Clear filters, approve pending accounts, or create users through the existing admin bootstrap workflow."
          permission="Platform administrator access is required."
        />
      ) : null}

      {items.length ? (
        <div className="overflow-hidden rounded-lg border border-raven-border bg-raven-panel/85">
          <div className="border-b border-raven-border px-4 py-3 text-sm text-raven-muted">
            Showing {items.length} of {users.data?.total ?? items.length} users
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-[980px] divide-y divide-raven-border text-sm">
              <thead className="bg-raven-panelSoft text-left text-xs uppercase tracking-wide text-raven-muted">
                <tr>
                  <th className="px-4 py-3">User</th>
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3">Last login</th>
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-raven-border">
                {items.map((item) => (
                  <UserRow
                    key={item.id}
                    user={item}
                    currentUserId={user.id}
                    onAction={setPendingAction}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {pendingAction ? (
        <ConfirmUserActionModal
          action={pendingAction}
          pending={actionMutation.isPending}
          onCancel={() => setPendingAction(null)}
          onConfirm={() => actionMutation.mutate(pendingAction)}
        />
      ) : null}
    </>
  );
}

function UserRow({
  user,
  currentUserId,
  onAction,
}: {
  user: AdminUser;
  currentUserId: string;
  onAction: (action: PendingAction) => void;
}): JSX.Element {
  const status = normalizeStatus(user.status || user.account_status);
  const role = normalizeRole(user.role);
  const isSelf = user.id === currentUserId;
  const canMakeAdmin = role !== "admin";
  const canMakeAnalyst = role === "admin";

  return (
    <tr className="align-top">
      <td className="px-4 py-3">
        <p className="font-medium text-raven-text">
          {safeString(user.full_name, user.username)}
          {isSelf ? (
            <span className="ml-2 rounded-full border border-raven-border px-2 py-0.5 text-xs text-raven-muted">
              You
            </span>
          ) : null}
        </p>
        <p className="mt-1 text-xs text-raven-muted">{user.username}</p>
        <p className="mt-1 break-all text-xs text-raven-muted">{user.email}</p>
        <LongValue
          value={user.id}
          maxLength={26}
          className="mt-1 text-xs text-raven-muted"
        />
      </td>
      <td className="px-4 py-3">
        <RoleBadge role={role} />
      </td>
      <td className="px-4 py-3">
        <StatusBadge status={status} />
        {status === "pending" ? (
          <p className="mt-2 max-w-xs text-xs text-raven-muted">
            Pending users cannot access protected workspaces until approved.
          </p>
        ) : null}
      </td>
      <td className="px-4 py-3 text-raven-muted">{formatDate(user.created_at)}</td>
      <td className="px-4 py-3 text-raven-muted">
        {formatDate(user.last_login)}
      </td>
      <td className="px-4 py-3 text-raven-muted">
        {humanize(user.registration_source ?? "unknown")}
      </td>
      <td className="px-4 py-3">
        <div className="flex min-w-[220px] flex-wrap gap-2">
          {status === "pending" || status === "rejected" ? (
            <ActionButton
              label="Approve"
              icon={<UserCheck className="h-3.5 w-3.5" />}
              onClick={() => onAction({ kind: "approve", user })}
            />
          ) : null}
          {status === "pending" ? (
            <ActionButton
              label="Reject"
              destructive
              icon={<UserX className="h-3.5 w-3.5" />}
              onClick={() => onAction({ kind: "reject", user })}
            />
          ) : null}
          {status === "active" ? (
            <ActionButton
              label="Disable"
              destructive
              onClick={() => onAction({ kind: "disable", user })}
            />
          ) : null}
          {status === "disabled" ? (
            <ActionButton
              label="Reactivate"
              onClick={() => onAction({ kind: "reactivate", user })}
            />
          ) : null}
          {canMakeAdmin ? (
            <ActionButton
              label="Make admin"
              onClick={() => onAction({ kind: "role", user, role: "admin" })}
            />
          ) : null}
          {canMakeAnalyst ? (
            <ActionButton
              label="Make analyst"
              destructive
              onClick={() => onAction({ kind: "role", user, role: "analyst" })}
            />
          ) : null}
        </div>
      </td>
    </tr>
  );
}

function ConfirmUserActionModal({
  action,
  pending,
  onCancel,
  onConfirm,
}: {
  action: PendingAction;
  pending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}): JSX.Element {
  const { title, description, confirmLabel } = describeAction(action);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
      <div className="w-full max-w-lg rounded-lg border border-raven-border bg-raven-panel p-5 shadow-glow">
        <h2 className="text-lg font-semibold text-raven-text">{title}</h2>
        <p className="mt-2 text-sm leading-6 text-raven-muted">{description}</p>
        <div className="mt-4 rounded-md border border-raven-border bg-raven-bg/60 p-3 text-sm">
          <p className="font-medium text-raven-text">
            {safeString(action.user.full_name, action.user.username)}
          </p>
          <p className="mt-1 break-all text-xs text-raven-muted">
            {action.user.email}
          </p>
          <p className="mt-2 text-xs text-raven-muted">
            Last active administrator protection is enforced by the backend.
          </p>
        </div>
        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={pending}
            className="rounded-md border border-raven-border px-4 py-2 text-sm text-raven-muted hover:text-raven-text disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={pending}
            className="rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50"
          >
            {pending ? "Working" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function describeAction(action: PendingAction): {
  title: string;
  description: string;
  confirmLabel: string;
} {
  if (action.kind === "role") {
    return {
      title: `Change role to ${humanize(action.role)}?`,
      description:
        "Role changes affect platform access immediately. Public registration cannot create administrator accounts.",
      confirmLabel: "Change role",
    };
  }
  const labels = {
    approve: "Approve user",
    reject: "Reject registration",
    disable: "Disable user",
    reactivate: "Reactivate user",
  };
  const descriptions = {
    approve:
      "The user will become active and can sign in after approval is saved.",
    reject:
      "The user will remain unable to sign in. This action is audited and can be revisited by an administrator.",
    disable:
      "The user will lose access to protected platform areas. This does not delete investigation records.",
    reactivate:
      "The user will regain access according to their current platform role.",
  };
  return {
    title: `${labels[action.kind]}?`,
    description: descriptions[action.kind],
    confirmLabel: labels[action.kind],
  };
}

function ActionButton({
  label,
  onClick,
  icon,
  destructive = false,
}: {
  label: string;
  onClick: () => void;
  icon?: JSX.Element;
  destructive?: boolean;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium",
        destructive
          ? "border-rose-400/30 text-rose-100 hover:bg-rose-500/10"
          : "border-raven-border text-raven-text hover:border-raven-violet",
      ].join(" ")}
    >
      {icon}
      {label}
    </button>
  );
}

function StatusBadge({ status }: { status: AccountStatus | string }): JSX.Element {
  const classes: Record<AccountStatus, string> = {
    active: "border-emerald-400/30 bg-emerald-500/10 text-emerald-100",
    pending: "border-amber-400/30 bg-amber-500/10 text-amber-100",
    disabled: "border-raven-border bg-raven-bg text-raven-muted",
    rejected: "border-rose-400/30 bg-rose-500/10 text-rose-100",
  };
  const normalized = normalizeStatus(status);
  return (
    <span
      className={[
        "inline-flex rounded-full border px-2 py-0.5 text-xs font-medium",
        classes[normalized],
      ].join(" ")}
    >
      {humanize(normalized)}
    </span>
  );
}

function RoleBadge({ role }: { role: PlatformUserRole | string }): JSX.Element {
  return (
    <span
      className={[
        "inline-flex rounded-full border px-2 py-0.5 text-xs font-medium",
        role === "admin"
          ? "border-violet-400/30 bg-violet-500/10 text-violet-100"
          : "border-cyan-400/30 bg-cyan-500/10 text-cyan-100",
      ].join(" ")}
    >
      {humanize(role)}
    </span>
  );
}

function normalizeStatus(value: unknown): AccountStatus {
  if (
    value === "active" ||
    value === "pending" ||
    value === "disabled" ||
    value === "rejected"
  ) {
    return value;
  }
  return "disabled";
}

function normalizeRole(value: unknown): PlatformUserRole {
  return value === "admin" ? "admin" : "analyst";
}

function formatDate(value: string | null): string {
  const parsed = safeDate(value);
  if (!parsed) {
    return "Never";
  }
  return parsed.toLocaleString();
}

function humanize(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (match: string) =>
    match.toUpperCase(),
  );
}
