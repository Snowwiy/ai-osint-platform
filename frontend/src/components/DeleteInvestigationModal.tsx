import { AlertTriangle, Archive } from "lucide-react";

import type { Investigation } from "../types";

export function DeleteInvestigationModal({
  investigation,
  error,
  isDeleting,
  onClose,
  onConfirm,
}: {
  investigation: Investigation;
  error?: string;
  isDeleting: boolean;
  onClose: () => void;
  onConfirm: () => void;
}): JSX.Element {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
      <div className="w-full max-w-xl rounded-lg border border-raven-border bg-raven-panel p-5 shadow-glow">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 flex-none items-center justify-center rounded-lg border border-rose-400/30 bg-rose-500/10 text-rose-100">
            <AlertTriangle className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-xl font-semibold">Archive investigation?</h2>
            <p className="mt-2 text-sm leading-6 text-raven-muted">
              This removes "{investigation.title}" from the active workspace while
              preserving its targets, evidence, findings, reports, timeline, and
              analysis under the configured retention policy.
            </p>
            <p className="mt-2 text-xs leading-5 text-raven-muted">
              Permanent deletion is disabled by data governance. An administrator or
              owner can restore the investigation later.
            </p>
          </div>
        </div>

        {error ? (
          <div className="mt-4 rounded-md border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">
            {error}
          </div>
        ) : null}

        <div className="mt-5 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isDeleting}
            className="rounded-md border border-raven-border px-4 py-2 text-sm text-raven-muted hover:text-raven-text disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isDeleting}
            className="inline-flex items-center gap-2 rounded-md bg-rose-500 px-4 py-2 text-sm font-medium text-white hover:bg-rose-400 disabled:opacity-60"
          >
            <Archive className="h-4 w-4" aria-hidden="true" />
            {isDeleting ? "Archiving" : "Archive"}
          </button>
        </div>
      </div>
    </div>
  );
}
