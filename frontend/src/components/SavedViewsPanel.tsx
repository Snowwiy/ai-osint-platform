import { useState, type ReactNode } from "react";
import { Bookmark, Check, Pin, PinOff, Save, Star, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createSavedView,
  deleteSavedView,
  listSavedViews,
  pinSavedView,
  setDefaultSavedView,
  unpinSavedView,
} from "../lib/api";
import type { SavedView, SavedViewType } from "../types";

interface SavedViewsPanelProps {
  viewType: SavedViewType;
  route: string;
  filters: object;
  sort?: object | null;
  title?: string;
  onApply?: (view: SavedView) => void;
}

export function SavedViewsPanel({
  viewType,
  route,
  filters,
  sort = null,
  title = "Saved Views",
  onApply,
}: SavedViewsPanelProps): JSX.Element {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const savedViews = useQuery({
    queryKey: ["saved-views", viewType],
    queryFn: () => listSavedViews({ view_type: viewType }),
    retry: 1,
    staleTime: 30_000,
  });
  const items = savedViews.data?.items ?? [];

  const invalidate = async (): Promise<void> => {
    await queryClient.invalidateQueries({ queryKey: ["saved-views"] });
  };

  const createMutation = useMutation({
    mutationFn: () =>
      createSavedView({
        name: name.trim(),
        view_type: viewType,
        route,
        filters: sanitizeFilters(filters),
        sort: sort ? sanitizeFilters(sort) : null,
      }),
    onSuccess: async () => {
      setName("");
      setMessage("Saved view created.");
      await invalidate();
    },
    onError: () => setMessage("Unable to save this view. Check the name and try again."),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteSavedView,
    onSuccess: async () => {
      setMessage("Saved view deleted.");
      await invalidate();
    },
    onError: () => setMessage("Unable to delete this saved view."),
  });

  const pinMutation = useMutation({
    mutationFn: ({ id, pinned }: { id: string; pinned: boolean }) =>
      pinned ? unpinSavedView(id) : pinSavedView(id),
    onSuccess: async () => {
      setMessage("Saved view updated.");
      await invalidate();
    },
    onError: () => setMessage("Unable to update pinned state."),
  });

  const defaultMutation = useMutation({
    mutationFn: setDefaultSavedView,
    onSuccess: async () => {
      setMessage("Default view updated.");
      await invalidate();
    },
    onError: () => setMessage("Unable to set this view as default."),
  });

  const saveDisabled = !name.trim() || createMutation.isPending;

  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel p-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="flex items-center gap-2 text-sm font-semibold text-raven-text">
            <Bookmark className="h-4 w-4 text-raven-muted" aria-hidden="true" />
            {title}
          </p>
          <p className="mt-1 text-xs leading-5 text-raven-muted">
            Save the current filters for quick internal navigation. Views are
            private to your account unless governance changes that later.
          </p>
        </div>
        <div className="flex min-w-0 flex-col gap-2 sm:flex-row">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Name this view"
            className="min-w-0 rounded border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm text-raven-text outline-none placeholder:text-raven-muted"
          />
          <button
            type="button"
            disabled={saveDisabled}
            onClick={() => createMutation.mutate()}
            title={
              saveDisabled
                ? "Enter a saved view name before saving."
                : "Save current filters"
            }
            className="inline-flex items-center justify-center gap-2 rounded-md bg-raven-violet px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Save className="h-4 w-4" aria-hidden="true" />
            Save
          </button>
        </div>
      </div>

      {message ? (
        <button
          type="button"
          onClick={() => setMessage(null)}
          className="mt-3 rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-left text-xs text-raven-muted hover:border-raven-violet"
        >
          {message}
        </button>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        {savedViews.isLoading ? (
          <span className="text-xs text-raven-muted">Loading saved views...</span>
        ) : null}
        {savedViews.isError ? (
          <span className="text-xs text-rose-100">
            Saved views are temporarily unavailable.
          </span>
        ) : null}
        {!savedViews.isLoading && !savedViews.isError && items.length === 0 ? (
          <span className="text-xs text-raven-muted">
            No saved views yet. Save the current filters to make this page faster next time.
          </span>
        ) : null}
        {items.map((view) => (
          <div
            key={view.id}
            className="flex max-w-full items-center gap-1 rounded-full border border-raven-border bg-raven-panelSoft p-1"
          >
            <button
              type="button"
              onClick={() => onApply?.(view)}
              className="min-w-0 max-w-[18rem] truncate rounded-full px-2 py-1 text-xs text-raven-text hover:bg-raven-panel"
              title={`Load ${view.name}`}
            >
              {view.is_default ? "Default: " : ""}
              {view.name}
            </button>
            <IconButton
              label={view.is_pinned ? "Unpin saved view" : "Pin saved view"}
              onClick={() => pinMutation.mutate({ id: view.id, pinned: view.is_pinned })}
            >
              {view.is_pinned ? (
                <PinOff className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <Pin className="h-3.5 w-3.5" aria-hidden="true" />
              )}
            </IconButton>
            <IconButton
              label="Set as default"
              onClick={() => defaultMutation.mutate(view.id)}
            >
              {view.is_default ? (
                <Check className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <Star className="h-3.5 w-3.5" aria-hidden="true" />
              )}
            </IconButton>
            <IconButton
              label="Delete saved view"
              onClick={() => {
                if (window.confirm(`Delete saved view "${view.name}"?`)) {
                  deleteMutation.mutate(view.id);
                }
              }}
            >
              <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
            </IconButton>
          </div>
        ))}
      </div>
    </section>
  );
}

function IconButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-full p-1 text-raven-muted hover:bg-raven-panel hover:text-raven-text"
      aria-label={label}
      title={label}
    >
      {children}
    </button>
  );
}

function sanitizeFilters(value: object): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(value).filter(([, item]) => item !== undefined && item !== ""),
  );
}
