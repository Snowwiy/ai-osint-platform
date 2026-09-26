import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  approveActionProposal,
  executeBackendActionProposal,
  getActionGatewayCapabilities,
  getAccessToken,
  listActionProposals,
  rejectActionProposal,
  setActionGatewayEnabled,
  type ActionProposal,
} from "../lib/api";
import { useI18n } from "../lib/i18n";

type Core = { invoke: (command: string, args?: Record<string, unknown>) => Promise<unknown> };
type NativeResult = { success: boolean; previousState: string; resultingState: string; message: string };

function nativeCore(): Core | null {
  try {
    return (window as Window & { __TAURI__?: { core?: Core } }).__TAURI__?.core ?? null;
  } catch { return null; }
}

export function ActionGatewayPanel(): JSX.Element {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [review, setReview] = useState<ActionProposal | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const proposals = useQuery({ queryKey: ["action-proposals"], queryFn: () => listActionProposals(), refetchInterval: 10000, retry: 1 });
  const capabilities = useQuery({ queryKey: ["action-capabilities"], queryFn: getActionGatewayCapabilities, refetchInterval: 30000, retry: 1 });
  const refresh = () => {
    void proposals.refetch();
    void capabilities.refetch();
    void queryClient.invalidateQueries({ queryKey: ["target-service-check"] });
    void queryClient.invalidateQueries({ queryKey: ["lan-services"] });
  };
  const policy = useMutation({ mutationFn: setActionGatewayEnabled, onSuccess: refresh });
  const submit = useMutation({
    mutationFn: async ({ item, decision }: { item: ActionProposal; decision: "approve" | "execute" | "reject" }) => {
      if (decision === "reject") return rejectActionProposal(item.id);
      const definition = capabilities.data?.actions.find((action) => action.action_id === item.action_id);
      if (decision === "approve") {
        let currentSnapshot: Record<string, unknown> | undefined;
        if (item.target_type === "local_service" || item.target_type === "local_process") {
          const core = nativeCore();
          const token = getAccessToken();
          if (!core || !token) throw new Error("Refresh this action from the local RavenTech desktop.");
          const value = await core.invoke("get_local_host_inventory", { token }) as { available?: boolean; services?: Array<{ name: string; displayName: string; state: string; pid: number | null; startType: string | null; actionAvailable: boolean }>; processes?: Array<{ pid: number; name: string; startedAtUnix: number; creationTicks: string | null; actionAvailable: boolean }> };
          if (!value.available) throw new Error("Local host inventory is unavailable.");
          if (item.target_type === "local_service") {
            const name = String(item.target_snapshot.name ?? "");
            const target = value.services?.find((service) => service.name === name);
            if (target) currentSnapshot = { name: target.name, display_name: target.displayName, state: target.state, pid: target.pid, start_type: target.startType, action_available: target.actionAvailable };
          } else {
            const pid = Number(item.target_snapshot.pid ?? -1);
            const target = value.processes?.find((process) => process.pid === pid);
            if (target) currentSnapshot = { pid: target.pid, name: target.name, started_at_unix: target.startedAtUnix, creation_ticks: target.creationTicks, action_available: target.actionAvailable };
          }
          if (!currentSnapshot) throw new Error("Local target changed. Create a fresh proposal.");
        }
        await approveActionProposal(item.id, confirmation || undefined, currentSnapshot);
      }
      if (definition?.executor === "desktop_native") {
        const core = nativeCore();
        const token = getAccessToken();
        if (!core || !token) throw new Error("Local desktop executor is unavailable.");
        return await core.invoke("execute_action_proposal", { token, proposalId: item.id }) as NativeResult;
      }
      return executeBackendActionProposal(item.id);
    },
    onSuccess: () => { setReview(null); setConfirmation(""); refresh(); },
  });

  const enabled = capabilities.data?.enabled ?? true;
  return <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4" aria-labelledby="action-gateway-title">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 id="action-gateway-title" className="text-lg font-semibold">{t("Action Gateway")}</h2><p className="mt-1 text-xs text-raven-muted">{t("Every write action needs a fresh human approval.")} {t("Read tools")}: {capabilities.data?.read_tools ?? 0} · {t("Action proposal tools")}: {capabilities.data?.action_proposal_tools ?? 0} · {t("Execution tools exposed to model")}: 0</p></div>
      {capabilities.data?.can_manage_policy ? <button type="button" disabled={policy.isPending} onClick={() => policy.mutate(!enabled)} className="rounded border border-raven-border px-3 py-2 text-sm">{enabled ? t("Disable Action Gateway") : t("Enable Action Gateway")}</button> : null}
    </div>
    {capabilities.isError || proposals.isError ? <p role="status" className="mt-3 text-sm text-amber-200">{t("Action Gateway status is unavailable.")}</p> : null}
    {!enabled ? <p role="status" className="mt-3 rounded border border-amber-400/50 p-3 text-sm">{t("Action Gateway is disabled. Pending proposals and approvals were invalidated.")}</p> : null}
    <div className="mt-4 grid gap-2 sm:grid-cols-4">
      <Count label={t("Pending approval")} value={proposals.data?.items.filter((item) => item.status === "awaiting_approval").length ?? 0} />
      <Count label={t("Approved") } value={proposals.data?.items.filter((item) => item.status === "approved").length ?? 0} />
      <Count label={t("Completed") } value={proposals.data?.items.filter((item) => item.status === "completed").length ?? 0} />
      <Count label={t("Failed or unverified") } value={proposals.data?.items.filter((item) => ["failed", "verification_failed", "completed_with_warnings"].includes(item.status)).length ?? 0} />
    </div>
    <div className="mt-4"><h3 className="text-sm font-semibold">{t("Action History")}</h3></div>
    <div className="mt-3 space-y-3">
      {proposals.data?.items.length ? proposals.data.items.map((item) => <article key={item.id} className="rounded border border-raven-border p-3">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-medium">{t(item.action_id)} · {item.target_display_name}</h3><p className="mt-1 text-xs text-raven-muted">{t("Origin")}: {t(item.origin)} · {t("Risk")}: {t(item.risk_level)} · {t("Status")}: {t(item.status)}</p></div><span className={`rounded border px-2 py-1 text-xs ${item.risk_level === "high" ? "border-rose-400/50 text-rose-200" : item.risk_level === "medium" ? "border-amber-400/50 text-amber-100" : "border-raven-border text-raven-muted"}`}>{t(item.risk_level)}</span></div>
        <p className="mt-1 text-xs text-raven-muted">{t("Requested by")}: {item.requested_by_user_id?.slice(0, 8) ?? t("Unknown")} · {t("Approved by")}: {item.approved_by_user_id?.slice(0, 8) ?? t("Not approved")}</p>
        <p className="mt-1 text-xs text-raven-muted">{t("Created")}: {new Date(item.created_at).toLocaleString()} · {t("Completed")}: {item.completed_at ? new Date(item.completed_at).toLocaleString() : t("Not completed")}</p>
        <p className="mt-2 text-sm">{item.reason}</p><p className="mt-2 text-xs text-raven-muted">{t("Expected effect")}: {item.expected_effect}</p><p className="mt-1 text-xs text-raven-muted">{t("Possible impact")}: {item.possible_impact}</p>
        {item.status === "awaiting_approval" && enabled ? <div className="mt-3 flex gap-2"><button type="button" onClick={() => { setReview(item); setConfirmation(""); }} className="rounded bg-raven-violet px-3 py-2 text-sm">{t("Review action")}</button><button type="button" disabled={submit.isPending} onClick={() => submit.mutate({ item, decision: "reject" })} className="rounded border border-raven-border px-3 py-2 text-sm">{t("Reject")}</button></div> : null}
        {item.status === "approved" && enabled ? <button type="button" disabled={submit.isPending} onClick={() => submit.mutate({ item, decision: "execute" })} className="mt-3 rounded border border-raven-border px-3 py-2 text-sm">{t("Execute approved action")}</button> : null}
        {item.result_summary ? <p role="status" className="mt-2 text-sm"><strong>{t("Verification")}:</strong> {item.result_summary}</p> : null}{item.safe_error_code ? <p className="mt-1 text-xs text-amber-200">{t("Safe error")}: {t(item.safe_error_code)}</p> : null}
        <p className="mt-2 break-all text-[11px] text-raven-muted">SHA-256: {item.proposal_hash}</p>
      </article>) : <p className="rounded border border-dashed border-raven-border p-4 text-sm text-raven-muted">{t("No action proposals recorded.")}</p>}
    </div>
    {review ? <div role="dialog" aria-modal="true" aria-labelledby="gateway-review-title" className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4">
      <section className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-lg border border-raven-border bg-raven-panel p-5 shadow-xl">
        <h2 id="gateway-review-title" className="text-lg font-semibold">{t("Human approval required")}</h2>
        <p className="mt-2">{t(review.action_id)} · {review.target_display_name}</p>
        <p className="mt-2 text-sm">{review.reason}</p><p className="mt-3 text-sm"><strong>{t("Risk")}:</strong> {t(review.risk_level)}</p>
        <p className="mt-2 text-xs text-raven-muted"><strong>{t("Approved target snapshot")}:</strong> {Object.entries(review.target_snapshot).map(([key, value]) => `${key}=${String(value)}`).join(" · ") || t("No target snapshot")}</p>
        <p className="mt-2 text-xs text-raven-muted"><strong>{t("Preconditions")}:</strong> {Object.entries(review.preconditions ?? {}).map(([key, value]) => `${key}=${String(value)}`).join(" · ") || t("None")}</p>
        <p className="mt-2 text-xs text-raven-muted"><strong>{t("Supporting evidence")}:</strong> {review.supporting_evidence_ids?.length ? review.supporting_evidence_ids.join(", ") : t("None supplied")}</p>
        <p className="mt-2 text-xs text-raven-muted"><strong>{t("Proposal expires")}:</strong> {new Date(review.expires_at).toLocaleString()}</p>
        <p className="mt-2 text-sm"><strong>{t("Expected effect")}:</strong> {review.expected_effect}</p><p className="mt-2 text-sm"><strong>{t("Possible impact")}:</strong> {review.possible_impact}</p><p className="mt-2 text-sm"><strong>{t("Recovery guidance")}:</strong> {review.rollback_guidance}</p>
        {review.risk_level === "high" ? <label className="mt-4 block text-sm">{t("Type the exact confirmation to approve")}: <strong className="select-all">{review.approval_confirmation}</strong><input autoComplete="off" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} className="mt-2 block w-full rounded border border-raven-border bg-raven-panelSoft px-3 py-2" /></label> : null}
        <div className="mt-5 flex flex-wrap gap-2"><button type="button" disabled={submit.isPending || !enabled || (review.risk_level === "high" && confirmation !== review.approval_confirmation)} onClick={() => submit.mutate({ item: review, decision: "approve" })} className="rounded bg-raven-violet px-3 py-2 text-sm disabled:opacity-50">{submit.isPending ? t("Processing") : t("Approve and execute")}</button><button type="button" disabled={submit.isPending} onClick={() => submit.mutate({ item: review, decision: "reject" })} className="rounded border border-raven-border px-3 py-2 text-sm">{t("Reject proposal")}</button><button type="button" disabled={submit.isPending} onClick={() => setReview(null)} className="rounded border border-raven-border px-3 py-2 text-sm">{t("Close")}</button></div>
        {submit.error ? <p role="alert" className="mt-3 text-sm text-rose-200">{submit.error instanceof Error ? submit.error.message : t("Action could not be completed.")}</p> : null}
      </section>
    </div> : null}
  </section>;
}

function Count({ label, value }: { label: string; value: number }): JSX.Element {
  return <div className="rounded border border-raven-border p-3"><p className="text-xs text-raven-muted">{label}</p><p className="mt-1 text-lg font-semibold">{value}</p></div>;
}
