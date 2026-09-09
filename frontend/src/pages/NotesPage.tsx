import { Archive, Edit3, Pin, PinOff, PlusCircle, Search } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { InvestigationTabs } from "../components/InvestigationTabs";
import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import {
  createNote,
  deleteNote,
  listInvestigationMembers,
  listNotes,
  updateNote,
} from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import { safeArray } from "../lib/safe";
import { useAuth } from "../lib/useAuth";
import type { InvestigationNote, NoteType } from "../types";

const noteTypes: NoteType[] = [
  "analyst_note",
  "triage_note",
  "remediation_note",
  "escalation_note",
  "validation_note",
  "closure_note",
  "evidence_note",
  "executive_note",
  "timeline_note",
];

export function NotesPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<InvestigationNote | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [search, setSearch] = useState("");
  const [noteType, setNoteType] = useState<NoteType | "all">("all");
  const [includeArchived, setIncludeArchived] = useState(false);
  const notes = useQuery({
    queryKey: ["notes", investigationId, includeArchived, noteType, search],
    queryFn: () =>
      listNotes(investigationId, {
        includeArchived,
        noteType: noteType === "all" ? undefined : noteType,
        search,
      }),
  });
  const members = useQuery({
    queryKey: ["members", investigationId],
    queryFn: () => listInvestigationMembers(investigationId),
  });
  const currentMember = members.data?.find((member) => member.user_id === user?.id);
  const canMutate =
    user?.role === "admin" ||
    currentMember?.role === "owner" ||
    currentMember?.role === "admin" ||
    currentMember?.role === "analyst";
  const createMutation = useMutation({
    mutationFn: (values: NoteFormValues) => createNote(investigationId, values),
    onSuccess: async () => {
      await invalidateCaseData(queryClient, investigationId);
      setIsCreating(false);
      setToast({ kind: "success", message: "Note added." });
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, values }: { id: string; values: NoteFormValues }) =>
      updateNote(investigationId, id, values),
    onSuccess: async () => {
      await invalidateCaseData(queryClient, investigationId);
      setEditing(null);
      setToast({ kind: "success", message: "Note updated." });
    },
  });
  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteNote(investigationId, id),
    onSuccess: async () => {
      await invalidateCaseData(queryClient, investigationId);
      setToast({ kind: "success", message: "Note archived." });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Unable to delete note.",
      });
    },
  });
  const pinMutation = useMutation({
    mutationFn: ({ id, pinned }: { id: string; pinned: boolean }) =>
      updateNote(investigationId, id, { pinned }),
    onSuccess: async () => {
      await invalidateCaseData(queryClient, investigationId);
      setToast({ kind: "success", message: "Note pin updated." });
    },
    onError: (error) => {
      setToast({ kind: "error", message: error.message });
    },
  });

  if (notes.isLoading) {
    return <LoadingBlock label="Loading notes" />;
  }
  if (notes.isError) {
    return <ErrorBlock message={notes.error} />;
  }
  const noteItems = notes.data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Notes"
        eyebrow="Analyst case notes"
        actions={
          canMutate ? (
            <button
              type="button"
              onClick={() => setIsCreating(true)}
              className="inline-flex items-center gap-2 rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500"
            >
              <PlusCircle className="h-4 w-4" aria-hidden="true" />
              Add note
            </button>
          ) : null
        }
      />
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}
      <InvestigationTabs />
      <section className="mb-5 grid gap-3 rounded-lg border border-raven-border bg-raven-panel/85 p-4 md:grid-cols-[1fr_220px_auto]">
        <label className="relative">
          <span className="sr-only">Search notes</span>
          <Search
            className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-raven-muted"
            aria-hidden="true"
          />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search titles and note content"
            className="w-full rounded-md border border-raven-border bg-raven-bg py-2 pl-10 pr-3 text-sm text-raven-text outline-none focus:border-raven-violet"
          />
        </label>
        <select
          value={noteType}
          onChange={(event) => setNoteType(event.target.value as NoteType | "all")}
          className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text outline-none focus:border-raven-violet"
        >
          <option value="all">All note types</option>
          {noteTypes.map((item) => (
            <option key={item} value={item}>
              {noteTypeLabel(item)}
            </option>
          ))}
        </select>
        <label className="inline-flex items-center gap-2 text-sm text-raven-muted">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(event) => setIncludeArchived(event.target.checked)}
            className="h-4 w-4 accent-violet-500"
          />
          Show archived
        </label>
      </section>

      {noteItems.length ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {noteItems.map((note) => (
            <article
              key={note.id}
              className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <span className="rounded border border-raven-border px-2 py-1 text-xs capitalize text-raven-cyan">
                    {noteTypeLabel(note.note_type)}
                  </span>
                  {note.pinned ? (
                    <span className="ml-2 rounded border border-amber-400/30 px-2 py-1 text-xs text-amber-100">
                      Pinned
                    </span>
                  ) : null}
                  {note.archived ? (
                    <span className="ml-2 rounded border border-raven-border px-2 py-1 text-xs text-raven-muted">
                      Archived
                    </span>
                  ) : null}
                  <span className="ml-2 rounded border border-raven-border px-2 py-1 text-xs capitalize text-raven-muted">
                    {note.visibility}
                  </span>
                  <h2 className="mt-3 font-semibold">{note.title}</h2>
                  <p className="mt-1 text-xs text-raven-muted">
                    Updated {new Date(note.updated_at).toLocaleString()}
                  </p>
                </div>
                {canMutate && !note.archived ? (
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      pinMutation.mutate({ id: note.id, pinned: !note.pinned })
                    }
                    disabled={pinMutation.isPending}
                    className="rounded-md border border-raven-border p-2 text-raven-muted hover:border-raven-violet hover:text-raven-text"
                    aria-label={note.pinned ? "Unpin note" : "Pin note"}
                  >
                    {note.pinned ? (
                      <PinOff className="h-4 w-4" aria-hidden="true" />
                    ) : (
                      <Pin className="h-4 w-4" aria-hidden="true" />
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditing(note)}
                    className="rounded-md border border-raven-border p-2 text-raven-muted hover:border-raven-violet hover:text-raven-text"
                    aria-label="Edit note"
                  >
                    <Edit3 className="h-4 w-4" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    onClick={() => deleteMutation.mutate(note.id)}
                    disabled={deleteMutation.isPending}
                    className="rounded-md border border-rose-400/30 p-2 text-rose-100 hover:bg-rose-500/10 disabled:opacity-60"
                    aria-label="Archive note"
                  >
                    <Archive className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
                ) : null}
              </div>
              <MarkdownPreview value={note.content} />
              {safeArray(note.references).length ? (
                <div className="mt-4 border-t border-raven-border pt-3">
                  <p className="text-xs uppercase tracking-wide text-raven-muted">
                    References
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {safeArray(note.references).map((reference) => (
                      <span
                        key={reference}
                        className="max-w-full break-all rounded border border-raven-border px-2 py-1 text-xs text-raven-cyan"
                      >
                        {reference}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <EmptyBlock
          title="No analyst notes"
          message="Notes preserve evidence context, recommendations, executive observations, and remediation decisions."
          nextStep="Create a note to document the next analyst action or important context."
          permission="Contributors can create notes; viewers have read-only access."
        />
      )}

      {isCreating ? (
        <NoteModal
          title="Add note"
          isSaving={createMutation.isPending}
          error={createMutation.error?.message}
          onClose={() => {
            createMutation.reset();
            setIsCreating(false);
          }}
          onSubmit={(values) => createMutation.mutate(values)}
        />
      ) : null}
      {editing ? (
        <NoteModal
          title="Edit note"
          note={editing}
          isSaving={updateMutation.isPending}
          error={updateMutation.error?.message}
          onClose={() => {
            updateMutation.reset();
            setEditing(null);
          }}
          onSubmit={(values) => updateMutation.mutate({ id: editing.id, values })}
        />
      ) : null}
    </>
  );
}

interface NoteFormValues {
  title: string;
  content: string;
  note_type: NoteType;
  pinned?: boolean;
  visibility?: "investigation" | "owners";
  references?: string[];
}

function NoteModal({
  title,
  note,
  error,
  isSaving,
  onClose,
  onSubmit,
}: {
  title: string;
  note?: InvestigationNote;
  error?: string;
  isSaving: boolean;
  onClose: () => void;
  onSubmit: (values: NoteFormValues) => void;
}): JSX.Element {
  const [noteTitle, setNoteTitle] = useState(note?.title ?? "");
  const [body, setBody] = useState(note?.content ?? "");
  const [noteType, setNoteType] = useState<NoteType>(
    note?.note_type ?? "analyst_note",
  );
  const [pinned, setPinned] = useState(note?.pinned ?? false);
  const [visibility, setVisibility] = useState<"investigation" | "owners">(
    note?.visibility ?? "investigation",
  );
  const [references, setReferences] = useState(
    safeArray(note?.references).join("\n"),
  );
  const [validationError, setValidationError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (!noteTitle.trim() || !body.trim()) {
      setValidationError("Title and note are required.");
      return;
    }
    setValidationError(null);
    onSubmit({
      title: noteTitle.trim(),
      content: body.trim(),
      note_type: noteType,
      pinned,
      visibility,
      references: references
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean),
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-2xl rounded-lg border border-raven-border bg-raven-panel p-5 shadow-glow"
      >
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-xl font-semibold">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            className="rounded-md border border-raven-border px-3 py-1.5 text-sm text-raven-muted hover:text-raven-text disabled:opacity-60"
          >
            Close
          </button>
        </div>

        <label className="mt-5 block text-sm text-raven-muted" htmlFor="note-title">
          Title
        </label>
        <input
          id="note-title"
          value={noteTitle}
          onChange={(event) => setNoteTitle(event.target.value)}
          className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
        />

        <label className="mt-4 block text-sm text-raven-muted" htmlFor="note-type">
          Note type
        </label>
        <select
          id="note-type"
          value={noteType}
          onChange={(event) => setNoteType(event.target.value as NoteType)}
          className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
        >
          {noteTypes.map((item) => (
            <option key={item} value={item}>
              {noteTypeLabel(item)}
            </option>
          ))}
        </select>

        <label className="mt-4 block text-sm text-raven-muted" htmlFor="note-body">
          Markdown note
        </label>
        <textarea
          id="note-body"
          value={body}
          onChange={(event) => setBody(event.target.value)}
          rows={9}
          className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
        />
        <label className="mt-4 inline-flex items-center gap-2 text-sm text-raven-muted">
          <input
            type="checkbox"
            checked={pinned}
            onChange={(event) => setPinned(event.target.checked)}
            className="h-4 w-4 accent-violet-500"
          />
          Pin this note
        </label>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="block text-sm text-raven-muted">
            Visibility
            <select
              value={visibility}
              onChange={(event) =>
                setVisibility(
                  event.target.value as "investigation" | "owners",
                )
              }
              className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text"
            >
              <option value="investigation">Investigation members</option>
              <option value="owners">Owners and admins</option>
            </select>
          </label>
          <label className="block text-sm text-raven-muted">
            References
            <textarea
              value={references}
              onChange={(event) => setReferences(event.target.value)}
              rows={4}
              placeholder="One evidence, finding, task, or report reference per line"
              className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text"
            />
          </label>
        </div>

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
            {isSaving ? "Saving" : "Save note"}
          </button>
        </div>
      </form>
    </div>
  );
}

function noteTypeLabel(value: NoteType): string {
  return value.replace(/_/g, " ");
}

function MarkdownPreview({ value }: { value: string }): JSX.Element {
  const lines = value.split("\n");
  return (
    <div className="mt-4 space-y-2 text-sm leading-6 text-raven-muted">
      {lines.map((line, index) => {
        const key = `${index}:${line}`;
        if (line.startsWith("### ")) {
          return (
            <h4 key={key} className="pt-2 text-sm font-semibold text-raven-text">
              {line.slice(4)}
            </h4>
          );
        }
        if (line.startsWith("## ")) {
          return (
            <h3 key={key} className="pt-2 font-semibold text-raven-text">
              {line.slice(3)}
            </h3>
          );
        }
        if (line.startsWith("# ")) {
          return (
            <h2 key={key} className="pt-2 text-lg font-semibold text-raven-text">
              {line.slice(2)}
            </h2>
          );
        }
        if (line.startsWith("- ")) {
          return (
            <p key={key} className="pl-4">
              - {line.slice(2)}
            </p>
          );
        }
        return line.trim() ? <p key={key}>{line}</p> : <br key={key} />;
      })}
    </div>
  );
}

async function invalidateCaseData(
  queryClient: ReturnType<typeof useQueryClient>,
  investigationId: string,
): Promise<void> {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["notes", investigationId] }),
    queryClient.invalidateQueries({ queryKey: ["timeline", investigationId] }),
    queryClient.invalidateQueries({
      queryKey: ["investigation-analytics", investigationId],
    }),
  ]);
}
