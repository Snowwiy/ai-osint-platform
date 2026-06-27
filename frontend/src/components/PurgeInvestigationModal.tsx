import { AlertTriangle, Loader2, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getInvestigationPurgeImpact } from "../lib/api";
import type { Investigation } from "../types";

export function PurgeInvestigationModal({
  investigation,
  error,
  isPurging,
  onClose,
  onConfirm,
}: {
  investigation: Investigation;
  error?: string;
  isPurging: boolean;
  onClose: () => void;
  onConfirm: () => void;
}): JSX.Element {
  const [confirmation, setConfirmation] = useState("");
  const impact = useQuery({
    queryKey: ["investigation-purge-impact", investigation.id],
    queryFn: () => getInvestigationPurgeImpact(investigation.id),
  });
  const canPurge =
    impact.data?.permanent_deletion_enabled !== false &&
    confirmation === investigation.title &&
    !impact.isLoading;

  useEffect(() => {
    setConfirmation("");
  }, [investigation.id]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-lg border border-rose-400/30 bg-raven-panel p-5 shadow-glow">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 flex-none items-center justify-center rounded-lg border border-rose-400/30 bg-rose-500/10 text-rose-100">
            <AlertTriangle className="h-5 w-5" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <h2 className="text-xl font-semibold">
              Permanently delete archived investigation?
            </h2>
            <p className="mt-2 text-sm leading-6 text-raven-muted">
              This action permanently removes the archived investigation and
              associated records according to governance policy.
            </p>
            <p className="mt-2 break-words text-sm text-rose-100">
              {investigation.title}
            </p>
          </div>
        </div>

        {impact.isLoading ? (
          <div className="mt-5 inline-flex items-center gap-2 text-sm text-raven-muted">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            Loading affected artifact counts.
          </div>
        ) : impact.isError ? (
          <div className="mt-5 rounded-md border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">
            {impact.error.message}
          </div>
        ) : impact.data?.permanent_deletion_enabled === false ? (
          <div className="mt-5 rounded-md border border-amber-300/30 bg-amber-400/10 p-3 text-sm text-amber-100">
            Governance settings currently prevent permanent deletion. Restore
            or retain this archived investigation.
          </div>
        ) : (
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <ImpactCount label="Findings" value={impact.data?.findings_count ?? 0} />
            <ImpactCount label="Notes" value={impact.data?.notes_count ?? 0} />
            <ImpactCount label="Reports" value={impact.data?.reports_count ?? 0} />
            <ImpactCount label="Tasks" value={impact.data?.tasks_count ?? 0} />
            <ImpactCount label="Evidence" value={impact.data?.evidence_count ?? 0} />
            <ImpactCount label="Members" value={impact.data?.members_count ?? 0} />
          </div>
        )}

        <label className="mt-5 block text-sm">
          <span className="text-raven-muted">
            Type the investigation name to confirm permanent deletion.
          </span>
          <input
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            disabled={isPurging || impact.data?.permanent_deletion_enabled === false}
            className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet disabled:opacity-60"
            placeholder={investigation.title}
          />
        </label>

        {error ? (
          <div className="mt-4 rounded-md border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">
            {error}
          </div>
        ) : null}

        <div className="mt-5 flex flex-wrap justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isPurging}
            className="rounded-md border border-raven-border px-4 py-2 text-sm text-raven-muted hover:text-raven-text disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={!canPurge || isPurging}
            className="inline-flex items-center gap-2 rounded-md bg-rose-500 px-4 py-2 text-sm font-medium text-white hover:bg-rose-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
            {isPurging ? "Deleting" : "Delete permanently"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ImpactCount({
  label,
  value,
}: {
  label: string;
  value: number;
}): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <p className="text-xs uppercase tracking-wide text-raven-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value.toLocaleString()}</p>
    </div>
  );
}
