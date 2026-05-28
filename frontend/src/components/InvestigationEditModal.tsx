import { useState, type FormEvent } from "react";

import type { Investigation, InvestigationStatus } from "../types";

const statuses: InvestigationStatus[] = [
  "draft",
  "active",
  "completed",
  "archived",
];

export interface InvestigationEditValues {
  title: string;
  description: string | null;
  status: InvestigationStatus;
  scope_definition: string | null;
}

export function InvestigationEditModal({
  investigation,
  error,
  isSaving,
  onClose,
  onSubmit,
}: {
  investigation: Investigation;
  error?: string;
  isSaving: boolean;
  onClose: () => void;
  onSubmit: (values: InvestigationEditValues) => void;
}): JSX.Element {
  const [title, setTitle] = useState(investigation.title);
  const [description, setDescription] = useState(investigation.description ?? "");
  const [status, setStatus] = useState<InvestigationStatus>(investigation.status);
  const [validationError, setValidationError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const cleanTitle = title.trim();
    if (!cleanTitle) {
      setValidationError("Title is required.");
      return;
    }
    setValidationError(null);
    const cleanDescription = description.trim();
    onSubmit({
      title: cleanTitle,
      description: cleanDescription || null,
      status,
      scope_definition: cleanDescription || null,
    });
  }

  const formError = validationError ?? error;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-2xl rounded-lg border border-raven-border bg-raven-panel p-5 shadow-glow"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold">Edit Investigation</h2>
            <p className="mt-1 text-sm text-raven-muted">
              Update the case metadata shown across the workspace.
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

        <label className="mt-5 block text-sm text-raven-muted" htmlFor="edit-title">
          Title
        </label>
        <input
          id="edit-title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
        />

        <label
          className="mt-4 block text-sm text-raven-muted"
          htmlFor="edit-description"
        >
          Description
        </label>
        <textarea
          id="edit-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={4}
          className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
        />

        <label className="mt-4 block text-sm text-raven-muted" htmlFor="edit-status">
          Status
        </label>
        <select
          id="edit-status"
          value={status}
          onChange={(event) => setStatus(event.target.value as InvestigationStatus)}
          className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
        >
          {statuses.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>

        {formError ? (
          <div className="mt-4 rounded-md border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">
            {formError}
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
            {isSaving ? "Saving" : "Save changes"}
          </button>
        </div>
      </form>
    </div>
  );
}
