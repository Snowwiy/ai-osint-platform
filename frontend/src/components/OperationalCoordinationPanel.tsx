import {
  AlertTriangle,
  ArrowRightLeft,
  Eye,
  Save,
  ShieldCheck,
  UserRoundCheck,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  escalateInvestigation,
  getInvestigationOwnership,
  handoffInvestigation,
  listInvestigationEscalations,
  listInvestigationMembers,
  updateInvestigationOwnership,
  updateInvestigationState,
} from "../lib/api";
import type {
  EscalationLevel,
  Investigation,
  InvestigationMember,
  InvestigationStatus,
} from "../types";
import { safeArray } from "../lib/safe";
import { ErrorBlock, LoadingBlock } from "./StateBlock";
import { ToastBanner, type ToastState } from "./ToastBanner";

const stateTransitions: Record<InvestigationStatus, InvestigationStatus[]> = {
  intake: ["active"],
  active: ["monitoring", "remediation"],
  monitoring: ["active", "remediation"],
  remediation: ["validation"],
  validation: ["remediation", "completed"],
  completed: ["active", "archived"],
  archived: [],
};

const escalationLevels: EscalationLevel[] = [
  "informational",
  "analyst_review",
  "senior_review",
  "urgent_review",
];

export function OperationalCoordinationPanel({
  investigation,
  currentUserId,
  platformRole,
}: {
  investigation: Investigation;
  currentUserId: string | undefined;
  platformRole: string | undefined;
}): JSX.Element {
  const queryClient = useQueryClient();
  const [toast, setToast] = useState<ToastState | null>(null);
  const [ownerId, setOwnerId] = useState(investigation.owner_id);
  const [assignedIds, setAssignedIds] = useState<string[]>([]);
  const [watcherIds, setWatcherIds] = useState<string[]>([]);
  const [state, setState] = useState<InvestigationStatus | "">("");
  const [stateReason, setStateReason] = useState("");
  const [handoffOwner, setHandoffOwner] = useState("");
  const [handoffReason, setHandoffReason] = useState("");
  const [pendingWork, setPendingWork] = useState("");
  const [escalationLevel, setEscalationLevel] =
    useState<EscalationLevel>("analyst_review");
  const [escalationReason, setEscalationReason] = useState("");

  const ownership = useQuery({
    queryKey: ["ownership", investigation.id],
    queryFn: () => getInvestigationOwnership(investigation.id),
  });
  const members = useQuery({
    queryKey: ["members", investigation.id],
    queryFn: () => listInvestigationMembers(investigation.id),
  });
  const escalations = useQuery({
    queryKey: ["escalations", investigation.id],
    queryFn: () => listInvestigationEscalations(investigation.id),
  });

  useEffect(() => {
    if (!ownership.data) {
      return;
    }
    setOwnerId(ownership.data.owner?.id ?? investigation.owner_id);
    setAssignedIds(safeArray(ownership.data.assigned_analysts).map((item) => item.id));
    setWatcherIds(safeArray(ownership.data.watchers).map((item) => item.id));
  }, [investigation.owner_id, ownership.data]);

  const currentMember = members.data?.find(
    (member) => member.user_id === currentUserId,
  );
  const canManage =
    platformRole === "admin" ||
    currentMember?.role === "owner" ||
    currentMember?.role === "admin";
  const canCollaborate = canManage || currentMember?.role === "analyst";
  const nonOwnerMembers = useMemo(
    () => safeArray(members.data).filter((member) => member.user_id !== ownerId),
    [members.data, ownerId],
  );
  const availableStateTransitions =
    stateTransitions[investigation.status] ?? [];

  const ownershipMutation = useMutation({
    mutationFn: () =>
      updateInvestigationOwnership(investigation.id, {
        owner_id: ownerId,
        assigned_analyst_ids: assignedIds,
        watcher_ids: watcherIds,
        reason: "Ownership roster updated from investigation workspace",
      }),
    onSuccess: async () => {
      await invalidateCoordination(queryClient, investigation.id);
      setToast({ kind: "success", message: "Ownership roster updated." });
    },
    onError: (error) => setToast({ kind: "error", message: error.message }),
  });
  const stateMutation = useMutation({
    mutationFn: () =>
      updateInvestigationState(investigation.id, state as InvestigationStatus, stateReason),
    onSuccess: async () => {
      await invalidateCoordination(queryClient, investigation.id);
      setState("");
      setStateReason("");
      setToast({ kind: "success", message: "Investigation state updated." });
    },
    onError: (error) => setToast({ kind: "error", message: error.message }),
  });
  const handoffMutation = useMutation({
    mutationFn: () =>
      handoffInvestigation(investigation.id, {
        new_owner_id: handoffOwner,
        reason: handoffReason,
        pending_work_summary: pendingWork.trim() || null,
      }),
    onSuccess: async () => {
      await invalidateCoordination(queryClient, investigation.id);
      setHandoffOwner("");
      setHandoffReason("");
      setPendingWork("");
      setToast({ kind: "success", message: "Investigation handed off." });
    },
    onError: (error) => setToast({ kind: "error", message: error.message }),
  });
  const escalationMutation = useMutation({
    mutationFn: () =>
      escalateInvestigation(
        investigation.id,
        escalationLevel,
        escalationReason,
      ),
    onSuccess: async () => {
      await invalidateCoordination(queryClient, investigation.id);
      setEscalationReason("");
      setToast({ kind: "success", message: "Escalation recorded." });
    },
    onError: (error) => setToast({ kind: "error", message: error.message }),
  });

  if (ownership.isLoading || members.isLoading || escalations.isLoading) {
    return (
      <section className="mt-6">
        <LoadingBlock label="Loading operational coordination" />
      </section>
    );
  }
  if (ownership.isError || members.isError || escalations.isError) {
    const message =
      ownership.error?.message ??
      members.error?.message ??
      escalations.error?.message ??
      "Unable to load operational coordination.";
    return (
      <section className="mt-6">
        <ErrorBlock message={message} />
      </section>
    );
  }

  return (
    <section className="mt-6 min-w-0 space-y-4">
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}
      <div className="grid min-w-0 gap-4 xl:grid-cols-3">
        <article className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-5">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-raven-cyan" aria-hidden="true" />
            <h2 className="text-lg font-semibold">Ownership</h2>
          </div>
          <p className="mt-3 break-words text-sm font-medium">
            {ownership.data?.owner?.username ?? "Owner information unavailable"}
          </p>
          <p className="break-all text-xs text-raven-muted">
            {ownership.data?.owner?.email ?? "No owner email available"}
          </p>
          <ChipList
            icon={<UserRoundCheck className="h-3.5 w-3.5" aria-hidden="true" />}
            label="Assigned analysts"
            values={
              (ownership.data?.assigned_analysts ?? []).map(
                (item) => item.username,
              )
            }
          />
          <ChipList
            icon={<Eye className="h-3.5 w-3.5" aria-hidden="true" />}
            label="Watchers"
            values={(ownership.data?.watchers ?? []).map((item) => item.username)}
          />
        </article>

        <article className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-5">
          <h2 className="text-lg font-semibold">Lifecycle</h2>
          <p className="mt-2 text-sm capitalize text-raven-cyan">
            Current state: {investigation.status}
          </p>
          {canManage && availableStateTransitions.length ? (
            <>
              <select
                value={state}
                onChange={(event) =>
                  setState(event.target.value as InvestigationStatus | "")
                }
                className="mt-4 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
              >
                <option value="">Select next state</option>
                {availableStateTransitions.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
              <textarea
                value={stateReason}
                onChange={(event) => setStateReason(event.target.value)}
                placeholder="Reason for state transition"
                rows={3}
                className="mt-3 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
              />
              <button
                type="button"
                onClick={() => stateMutation.mutate()}
                disabled={!state || !stateReason.trim() || stateMutation.isPending}
                className="mt-3 rounded-md bg-raven-violet px-3 py-2 text-sm text-white disabled:opacity-50"
              >
                Update state
              </button>
            </>
          ) : (
            <p className="mt-4 text-sm text-raven-muted">
              {canManage
                ? "No forward transition is available from this state."
                : "Owner or investigation admin access is required to change state."}
            </p>
          )}
        </article>

        <article className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-5">
          <div className="flex items-center gap-2">
            <AlertTriangle
              className="h-5 w-5 text-amber-200"
              aria-hidden="true"
            />
            <h2 className="text-lg font-semibold">Escalations</h2>
          </div>
          <p className="mt-2 text-sm text-raven-muted">
            {escalations.data?.length ?? 0} analyst-triggered escalations
          </p>
          {canCollaborate ? (
            <>
              <select
                value={escalationLevel}
                onChange={(event) =>
                  setEscalationLevel(event.target.value as EscalationLevel)
                }
                className="mt-4 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
              >
                {escalationLevels.map((item) => (
                  <option key={item} value={item}>
                    {item.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
              <textarea
                value={escalationReason}
                onChange={(event) => setEscalationReason(event.target.value)}
                placeholder="Operational reason for escalation"
                rows={3}
                className="mt-3 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
              />
              <button
                type="button"
                onClick={() => escalationMutation.mutate()}
                disabled={
                  !escalationReason.trim() || escalationMutation.isPending
                }
                className="mt-3 rounded-md border border-amber-400/30 px-3 py-2 text-sm text-amber-100 disabled:opacity-50"
              >
                Record escalation
              </button>
            </>
          ) : null}
        </article>
      </div>

      {canManage ? (
        <div className="grid min-w-0 gap-4 xl:grid-cols-2">
          <article className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-5">
            <h2 className="text-lg font-semibold">Ownership roster</h2>
            <label className="mt-4 block text-sm text-raven-muted">
              Primary owner
              <select
                value={ownerId}
                onChange={(event) => {
                  setOwnerId(event.target.value);
                  setAssignedIds((items) =>
                    items.filter((item) => item !== event.target.value),
                  );
                  setWatcherIds((items) =>
                    items.filter((item) => item !== event.target.value),
                  );
                }}
                className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text"
              >
                {(members.data ?? []).map((member) => (
                  <option key={member.id} value={member.user_id}>
                    {member.username} ({member.role})
                  </option>
                ))}
              </select>
            </label>
            <div className="mt-4 space-y-2">
              {nonOwnerMembers.map((member) => (
                <RosterRow
                  key={member.id}
                  member={member}
                  role={
                    watcherIds.includes(member.user_id) ? "watcher" : "analyst"
                  }
                  onChange={(role) => {
                    if (role === "watcher") {
                      setWatcherIds((items) => [
                        ...items.filter((item) => item !== member.user_id),
                        member.user_id,
                      ]);
                      setAssignedIds((items) =>
                        items.filter((item) => item !== member.user_id),
                      );
                    } else {
                      setAssignedIds((items) => [
                        ...items.filter((item) => item !== member.user_id),
                        member.user_id,
                      ]);
                      setWatcherIds((items) =>
                        items.filter((item) => item !== member.user_id),
                      );
                    }
                  }}
                />
              ))}
            </div>
            <button
              type="button"
              onClick={() => ownershipMutation.mutate()}
              disabled={ownershipMutation.isPending}
              className="mt-4 inline-flex items-center gap-2 rounded-md bg-raven-violet px-3 py-2 text-sm text-white disabled:opacity-50"
            >
              <Save className="h-4 w-4" aria-hidden="true" />
              Save ownership
            </button>
          </article>

          <article className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-5">
            <div className="flex items-center gap-2">
              <ArrowRightLeft
                className="h-5 w-5 text-raven-cyan"
                aria-hidden="true"
              />
              <h2 className="text-lg font-semibold">Case handoff</h2>
            </div>
            <select
              value={handoffOwner}
              onChange={(event) => setHandoffOwner(event.target.value)}
              className="mt-4 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text"
            >
              <option value="">Select new owner</option>
              {nonOwnerMembers.map((member) => (
                <option key={member.id} value={member.user_id}>
                  {member.username}
                </option>
              ))}
            </select>
            <textarea
              value={handoffReason}
              onChange={(event) => setHandoffReason(event.target.value)}
              placeholder="Reason and context for the handoff"
              rows={3}
              className="mt-3 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
            />
            <textarea
              value={pendingWork}
              onChange={(event) => setPendingWork(event.target.value)}
              placeholder="Pending work summary"
              rows={3}
              className="mt-3 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
            />
            <button
              type="button"
              onClick={() => handoffMutation.mutate()}
              disabled={
                !handoffOwner ||
                !handoffReason.trim() ||
                handoffMutation.isPending
              }
              className="mt-3 rounded-md border border-raven-violet px-3 py-2 text-sm text-raven-text disabled:opacity-50"
            >
              Confirm handoff
            </button>
          </article>
        </div>
      ) : null}
    </section>
  );
}

function ChipList({
  icon,
  label,
  values,
}: {
  icon: JSX.Element;
  label: string;
  values: string[];
}): JSX.Element {
  return (
    <div className="mt-4">
      <p className="text-xs uppercase tracking-wide text-raven-muted">{label}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {values.length ? (
          values.map((value) => (
            <span
              key={value}
              className="inline-flex min-w-0 items-center gap-1 rounded border border-raven-border px-2 py-1 text-xs text-raven-muted"
            >
              {icon}
              <span className="break-words">{value}</span>
            </span>
          ))
        ) : (
          <span className="text-xs text-raven-muted">None assigned</span>
        )}
      </div>
    </div>
  );
}

function RosterRow({
  member,
  role,
  onChange,
}: {
  member: InvestigationMember;
  role: "analyst" | "watcher";
  onChange: (role: "analyst" | "watcher") => void;
}): JSX.Element {
  return (
    <div className="flex min-w-0 flex-col gap-2 rounded-md border border-raven-border bg-raven-panelSoft p-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="break-words text-sm font-medium">{member.username}</p>
        <p className="break-all text-xs text-raven-muted">{member.email}</p>
      </div>
      <select
        value={role}
        onChange={(event) =>
          onChange(event.target.value as "analyst" | "watcher")
        }
        className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
      >
        <option value="analyst">Assigned analyst</option>
        <option value="watcher">Watcher</option>
      </select>
    </div>
  );
}

async function invalidateCoordination(
  queryClient: ReturnType<typeof useQueryClient>,
  investigationId: string,
): Promise<void> {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["ownership", investigationId] }),
    queryClient.invalidateQueries({ queryKey: ["members", investigationId] }),
    queryClient.invalidateQueries({ queryKey: ["escalations", investigationId] }),
    queryClient.invalidateQueries({
      queryKey: ["investigation", investigationId],
    }),
    queryClient.invalidateQueries({ queryKey: ["timeline", investigationId] }),
    queryClient.invalidateQueries({ queryKey: ["collaboration-dashboard"] }),
  ]);
}
