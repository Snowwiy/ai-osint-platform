import { ShieldCheck, UserPlus, UsersRound } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { InvestigationTabs } from "../components/InvestigationTabs";
import { LongValue } from "../components/LongValue";
import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import {
  addInvestigationMember,
  listInvestigationMembers,
  removeInvestigationMember,
  updateInvestigationMember,
} from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import { useAuth } from "../lib/useAuth";
import type { InvestigationMember, InvestigationMemberRole } from "../types";

const roles: InvestigationMemberRole[] = ["owner", "admin", "analyst", "viewer"];

export function MembersPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [toast, setToast] = useState<ToastState | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const members = useQuery({
    queryKey: ["members", investigationId],
    queryFn: () => listInvestigationMembers(investigationId),
  });
  const currentMember = useMemo(
    () => members.data?.find((member) => member.user_id === user?.id) ?? null,
    [members.data, user?.id],
  );
  const canManage = user?.role === "admin" || currentMember?.role === "owner";

  const addMutation = useMutation({
    mutationFn: (values: AddMemberValues) =>
      addInvestigationMember(investigationId, addPayload(values)),
    onSuccess: async () => {
      await invalidateMembers(queryClient, investigationId);
      setShowAdd(false);
      setToast({ kind: "success", message: "Member added." });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Unable to add member.",
      });
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({
      member,
      role,
      transferOwnership,
    }: {
      member: InvestigationMember;
      role: InvestigationMemberRole;
      transferOwnership?: boolean;
    }) =>
      updateInvestigationMember(investigationId, member.id, {
        role,
        transfer_ownership: transferOwnership,
      }),
    onSuccess: async () => {
      await invalidateMembers(queryClient, investigationId);
      setToast({ kind: "success", message: "Member role updated." });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message:
          error instanceof Error ? error.message : "Unable to update member role.",
      });
    },
  });
  const removeMutation = useMutation({
    mutationFn: (member: InvestigationMember) =>
      removeInvestigationMember(investigationId, member.id),
    onSuccess: async () => {
      await invalidateMembers(queryClient, investigationId);
      setToast({ kind: "success", message: "Member removed." });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Unable to remove member.",
      });
    },
  });

  if (members.isLoading) {
    return <LoadingBlock label="Loading members" />;
  }
  if (members.isError) {
    return <ErrorBlock message={members.error.message} />;
  }

  return (
    <>
      <PageHeader
        title="Members"
        eyebrow="Collaboration access"
        actions={
          canManage ? (
            <button
              type="button"
              onClick={() => setShowAdd(true)}
              className="inline-flex items-center gap-2 rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500"
            >
              <UserPlus className="h-4 w-4" aria-hidden="true" />
              Add member
            </button>
          ) : null
        }
      />
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}
      <InvestigationTabs />

      {members.data?.length ? (
        <div className="space-y-3">
          {members.data.map((member) => (
            <article
              key={member.id}
              className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"
            >
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <RoleBadge role={member.role} />
                    {member.user_id === user?.id ? (
                      <span className="rounded border border-raven-border px-2 py-1 text-xs text-raven-muted">
                        you
                      </span>
                    ) : null}
                  </div>
                  <h2 className="mt-3 font-semibold">{member.username}</h2>
                  <p className="mt-1 text-sm text-raven-muted">{member.email}</p>
                  <div className="mt-3 grid gap-2 text-xs text-raven-muted">
                    <LongValue label="User ID" value={member.user_id} maxLength={48} />
                    <LongValue
                      label="Member ID"
                      value={member.id}
                      maxLength={48}
                    />
                    <span>Joined {new Date(member.created_at).toLocaleString()}</span>
                    {member.invited_by ? (
                      <LongValue
                        label="Invited by"
                        value={member.invited_by}
                        maxLength={48}
                      />
                    ) : null}
                  </div>
                </div>

                {canManage ? (
                  <div className="flex flex-wrap gap-2">
                    <RoleSelect
                      value={member.role}
                      disabled={updateMutation.isPending}
                      onChange={(role) =>
                        updateMutation.mutate({ member, role })
                      }
                    />
                    {member.role !== "owner" ? (
                      <button
                        type="button"
                        disabled={updateMutation.isPending}
                        onClick={() => {
                          if (
                            window.confirm(
                              "Transfer case ownership to this member?",
                            )
                          ) {
                            updateMutation.mutate({
                              member,
                              role: "owner",
                              transferOwnership: true,
                            });
                          }
                        }}
                        className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-text hover:border-raven-violet disabled:opacity-60"
                      >
                        <ShieldCheck className="h-4 w-4" aria-hidden="true" />
                        Transfer owner
                      </button>
                    ) : null}
                    <button
                      type="button"
                      disabled={removeMutation.isPending}
                      onClick={() => {
                        if (window.confirm("Remove this member from the case?")) {
                          removeMutation.mutate(member);
                        }
                      }}
                      className="rounded-md border border-rose-400/30 px-3 py-2 text-sm text-rose-100 hover:bg-rose-500/10 disabled:opacity-60"
                    >
                      Remove
                    </button>
                  </div>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyBlock message="No members are visible for this investigation." />
      )}

      {showAdd ? (
        <AddMemberModal
          isSaving={addMutation.isPending}
          error={addMutation.error?.message}
          onClose={() => {
            addMutation.reset();
            setShowAdd(false);
          }}
          onSubmit={(values) => addMutation.mutate(values)}
        />
      ) : null}
    </>
  );
}

interface AddMemberValues {
  lookup: string;
  role: InvestigationMemberRole;
}

function AddMemberModal({
  isSaving,
  error,
  onClose,
  onSubmit,
}: {
  isSaving: boolean;
  error?: string;
  onClose: () => void;
  onSubmit: (values: AddMemberValues) => void;
}): JSX.Element {
  const [lookup, setLookup] = useState("");
  const [role, setRole] = useState<InvestigationMemberRole>("analyst");
  const [validationError, setValidationError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (!lookup.trim()) {
      setValidationError("Enter a username, email, or user UUID.");
      return;
    }
    setValidationError(null);
    onSubmit({ lookup: lookup.trim(), role });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-lg rounded-lg border border-raven-border bg-raven-panel p-5 shadow-glow"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold">Add member</h2>
            <p className="mt-1 text-sm text-raven-muted">
              Invite an existing RavenTech user to this investigation.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            className="rounded-md border border-raven-border px-3 py-1.5 text-sm text-raven-muted hover:text-raven-text disabled:opacity-60"
          >
            Close
          </button>
        </div>

        <label className="mt-5 block text-sm text-raven-muted" htmlFor="member">
          User
        </label>
        <input
          id="member"
          value={lookup}
          onChange={(event) => setLookup(event.target.value)}
          placeholder="analyst@example.com, username, or UUID"
          className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
        />

        <label className="mt-4 block text-sm text-raven-muted" htmlFor="member-role">
          Role
        </label>
        <select
          id="member-role"
          value={role}
          onChange={(event) => setRole(event.target.value as InvestigationMemberRole)}
          className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
        >
          {roles.map((item) => (
            <option key={item} value={item}>
              {roleDescription(item)}
            </option>
          ))}
        </select>

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
            {isSaving ? "Adding" : "Add member"}
          </button>
        </div>
      </form>
    </div>
  );
}

function addPayload(values: AddMemberValues): {
  user_id?: string;
  email?: string;
  username?: string;
  role: InvestigationMemberRole;
} {
  if (values.lookup.includes("@")) {
    return { email: values.lookup, role: values.role };
  }
  if (isUuid(values.lookup)) {
    return { user_id: values.lookup, role: values.role };
  }
  return { username: values.lookup, role: values.role };
}

function RoleSelect({
  value,
  disabled,
  onChange,
}: {
  value: InvestigationMemberRole;
  disabled: boolean;
  onChange: (role: InvestigationMemberRole) => void;
}): JSX.Element {
  return (
    <select
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value as InvestigationMemberRole)}
      className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text outline-none focus:border-raven-violet disabled:opacity-60"
    >
      {roles.map((role) => (
        <option key={role} value={role}>
          {role}
        </option>
      ))}
    </select>
  );
}

function RoleBadge({ role }: { role: InvestigationMemberRole }): JSX.Element {
  const classes: Record<InvestigationMemberRole, string> = {
    owner: "border-emerald-400/30 bg-emerald-500/10 text-emerald-100",
    admin: "border-violet-400/30 bg-violet-500/10 text-violet-100",
    analyst: "border-cyan-400/30 bg-cyan-500/10 text-cyan-100",
    viewer: "border-raven-border bg-raven-panel text-raven-muted",
  };
  return (
    <span
      className={[
        "inline-flex items-center gap-1 rounded border px-2 py-1 text-xs capitalize",
        classes[role],
      ].join(" ")}
    >
      <UsersRound className="h-3 w-3" aria-hidden="true" />
      {role}
    </span>
  );
}

function roleDescription(role: InvestigationMemberRole): string {
  const descriptions: Record<InvestigationMemberRole, string> = {
    owner: "owner - full case control",
    admin: "admin - manage case resources",
    analyst: "analyst - contribute and run recon",
    viewer: "viewer - read only",
  };
  return descriptions[role];
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    value,
  );
}

async function invalidateMembers(
  queryClient: ReturnType<typeof useQueryClient>,
  investigationId: string,
): Promise<void> {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["members", investigationId] }),
    queryClient.invalidateQueries({ queryKey: ["timeline", investigationId] }),
    queryClient.invalidateQueries({ queryKey: ["dashboard-analytics"] }),
  ]);
}
