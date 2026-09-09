import {
  ArchiveRestore,
  CalendarDays,
  Pencil,
  ShieldAlert,
  Tags,
  Target,
  Trash2,
} from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { DeleteInvestigationModal } from "../components/DeleteInvestigationModal";
import {
  InvestigationEditModal,
  type InvestigationEditValues,
} from "../components/InvestigationEditModal";
import { PageHeader } from "../components/PageHeader";
import { PurgeInvestigationModal } from "../components/PurgeInvestigationModal";
import { SavedViewsPanel } from "../components/SavedViewsPanel";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { StatusBadge } from "../components/StatusBadge";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import {
  createInvestigation,
  deleteInvestigation,
  getInvestigationTags,
  listFindings,
  listEngagements,
  listInvestigationsWithScope,
  listTags,
  listTargets,
  purgeInvestigation,
  restoreInvestigation,
  updateInvestigation,
} from "../lib/api";
import { useAuth } from "../lib/useAuth";
import type { Engagement, Investigation } from "../types";

export function InvestigationsPage(): JSX.Element {
  const [isCreating, setIsCreating] = useState(false);
  const [editing, setEditing] = useState<Investigation | null>(null);
  const [deleting, setDeleting] = useState<Investigation | null>(null);
  const [purging, setPurging] = useState<Investigation | null>(null);
  const [scope, setScope] = useState("all");
  const [selectedTag, setSelectedTag] = useState("all");
  const [toast, setToast] = useState<ToastState | null>(null);
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const investigations = useQuery({
    queryKey: ["investigations", scope],
    queryFn: () => listInvestigationsWithScope(scope),
  });
  const availableTags = useQuery({
    queryKey: ["tags"],
    queryFn: listTags,
  });
  const engagements = useQuery({
    queryKey: ["engagements", false],
    queryFn: () => listEngagements(false),
  });
  const investigationItems = investigations.data?.items ?? [];
  const availableTagItems = availableTags.data?.items ?? [];
  const scopedInvestigations =
    investigationItems.filter(
      (item) => scope === "archived" || item.status !== "archived",
    );
  const investigationTags = useQueries({
    queries: scopedInvestigations.map((item) => ({
      queryKey: ["investigation-tags", item.id],
      queryFn: () => getInvestigationTags(item.id),
    })),
  });
  const tagIdsByInvestigation = new Map(
    scopedInvestigations.map((item, index) => [
      item.id,
      (investigationTags[index]?.data?.items ?? []).map((tag) => tag.id),
    ]),
  );
  const visibleInvestigations = scopedInvestigations.filter(
    (item) =>
      selectedTag === "all" ||
      tagIdsByInvestigation.get(item.id)?.includes(selectedTag),
  );
  const targetCounts = useQueries({
    queries: visibleInvestigations.map((item) => ({
      queryKey: ["targets", item.id],
      queryFn: () => listTargets(item.id),
    })),
  });
  const findingCounts = useQueries({
    queries: visibleInvestigations.map((item) => ({
      queryKey: ["findings", item.id],
      queryFn: () => listFindings(item.id),
    })),
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      values,
    }: {
      id: string;
      values: InvestigationEditValues;
    }) => updateInvestigation(id, values),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["investigations"] });
      setEditing(null);
      setToast({ kind: "success", message: "Investigation updated." });
    },
  });

  useEffect(() => {
    const state = location.state as { toast?: ToastState } | null;
    if (state?.toast) {
      setToast(state.toast);
      navigate(location.pathname, { replace: true, state: null });
    }
  }, [location.pathname, location.state, navigate]);

  const deleteMutation = useMutation({
    mutationFn: deleteInvestigation,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["investigations"] });
      setDeleting(null);
      setToast({ kind: "success", message: "Investigation archived." });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message:
          error instanceof Error
            ? error.message
            : "Unable to archive investigation.",
      });
    },
  });
  const restoreMutation = useMutation({
    mutationFn: restoreInvestigation,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["investigations"] });
      setToast({ kind: "success", message: "Investigation restored." });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message:
          error instanceof Error
            ? error.message
            : "Unable to restore investigation.",
      });
    },
  });
  const purgeMutation = useMutation({
    mutationFn: purgeInvestigation,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["investigations"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard-executive"] });
      setPurging(null);
      setToast({
        kind: "success",
        message: "Archived investigation permanently deleted.",
      });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message:
          error instanceof Error
            ? error.message
            : "Unable to permanently delete investigation.",
      });
    },
  });

  if (investigations.isLoading) {
    return <LoadingBlock label="Loading investigations" />;
  }
  if (investigations.isError) {
    return <ErrorBlock message={investigations.error} />;
  }

  return (
    <>
      <PageHeader
        title="Investigations"
        eyebrow="Casework"
        actions={
          <button
            type="button"
            onClick={() => setIsCreating(true)}
            className="rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500"
          >
            New Investigation
          </button>
        }
      />
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}
      <div className="mb-5">
        <SavedViewsPanel
          viewType="investigation_list"
          route="/investigations"
          filters={{ scope, selectedTag }}
          onApply={(view) => {
            const nextScope = view.filters.scope;
            const nextTag = view.filters.selectedTag;
            if (typeof nextScope === "string") {
              setScope(nextScope);
            }
            if (typeof nextTag === "string") {
              setSelectedTag(nextTag);
            }
            setToast({ kind: "success", message: `Loaded ${view.name}.` });
          }}
        />
      </div>
      <div className="mb-5 flex flex-wrap gap-2">
        {[
          ["all", "All accessible"],
          ["owned_by_me", "Owned by me"],
          ["assigned_to_me", "Assigned to me"],
          ["member_of", "Member of"],
          ["viewer_only", "Viewer only"],
          ["active", "Active"],
          ["archived", "Archived"],
          ["needs_review", "Needs review"],
        ].map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setScope(value)}
            className={[
              "rounded-md border px-3 py-2 text-sm",
              scope === value
                ? "border-raven-violet bg-raven-violet text-white"
                : "border-raven-border text-raven-muted hover:border-raven-violet hover:text-raven-text",
            ].join(" ")}
          >
            {label}
          </button>
        ))}
        <label className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-muted">
          <Tags className="h-4 w-4" aria-hidden="true" />
          <span className="sr-only">Filter by tag</span>
          <select
            value={selectedTag}
            onChange={(event) => setSelectedTag(event.target.value)}
            className="bg-transparent text-raven-text outline-none"
          >
            <option value="all">All tags</option>
            {availableTagItems.map((tag) => (
              <option key={tag.id} value={tag.id}>
                {tag.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {visibleInvestigations.length ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {visibleInvestigations.map((item, index) => {
            const targetTotal = targetCounts[index]?.data?.total;
            const findingTotal = findingCounts[index]?.data?.length;
            const canManage = canManageInvestigation(
              item.owner_id,
              user?.id,
              user?.role,
            );
            const itemTags =
              investigationTags[
                scopedInvestigations.findIndex(
                  (investigation) => investigation.id === item.id,
                )
              ]?.data?.items ?? [];
            return (
              <article
                key={item.id}
                className="rounded-lg border border-raven-border bg-raven-panel/85 p-4 transition hover:border-raven-violet"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        to={`/investigations/${item.id}`}
                        className="font-semibold text-raven-text hover:text-raven-cyan"
                      >
                        {item.title}
                      </Link>
                      {item.title.startsWith("[DEMO]") ? (
                        <span className="rounded border border-cyan-400/30 bg-cyan-500/10 px-2 py-0.5 text-xs text-cyan-100">
                          Synthetic demo
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-2 line-clamp-2 text-sm text-raven-muted">
                      {item.description ??
                        item.scope_definition ??
                        "No description stored."}
                    </p>
                  </div>
                  <StatusBadge status={item.status} />
                </div>

                <div className="mt-4 grid gap-3 text-sm text-raven-muted sm:grid-cols-2">
                  <Metric
                    icon={<CalendarDays className="h-4 w-4" aria-hidden="true" />}
                    label={`Created ${new Date(item.created_at).toLocaleDateString()}`}
                  />
                  <Metric
                    icon={<Target className="h-4 w-4" aria-hidden="true" />}
                    label={`${targetTotal ?? "—"} targets`}
                  />
                  <Metric
                    icon={<ShieldAlert className="h-4 w-4" aria-hidden="true" />}
                    label={`${findingTotal ?? "—"} findings`}
                  />
                  <Metric label={ownerContext(item, user?.id, user?.role)} />
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <span
                    className={[
                      "rounded border px-2 py-1 text-xs capitalize",
                      item.priority === "urgent"
                        ? "border-rose-400/40 text-rose-100"
                        : item.priority === "high"
                          ? "border-orange-400/40 text-orange-100"
                          : "border-raven-border text-raven-muted",
                    ].join(" ")}
                  >
                    {item.priority} priority
                  </span>
                  {itemTags.map((tag) => (
                    <span
                      key={tag.id}
                      className="rounded border border-raven-border px-2 py-1 text-xs text-raven-cyan"
                    >
                      {tag.name}
                    </span>
                  ))}
                </div>

                <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                  <p className="text-xs text-raven-muted">
                    Updated {new Date(item.updated_at).toLocaleString()}
                  </p>
                  {canManage ? (
                    <div className="flex gap-2">
                      {item.status === "archived" ? (
                        <>
                          <button
                            type="button"
                            onClick={() => restoreMutation.mutate(item.id)}
                            disabled={
                              restoreMutation.isPending || purgeMutation.isPending
                            }
                            className="inline-flex items-center gap-2 rounded-md border border-emerald-400/30 px-3 py-1.5 text-sm text-emerald-100 hover:bg-emerald-500/10 disabled:opacity-60"
                          >
                            <ArchiveRestore
                              className="h-4 w-4"
                              aria-hidden="true"
                            />
                            Restore
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              purgeMutation.reset();
                              setPurging(item);
                            }}
                            disabled={
                              restoreMutation.isPending || purgeMutation.isPending
                            }
                            className="inline-flex items-center gap-2 rounded-md border border-rose-400/30 px-3 py-1.5 text-sm text-rose-100 hover:bg-rose-500/10 disabled:opacity-60"
                          >
                            <Trash2 className="h-4 w-4" aria-hidden="true" />
                            Delete permanently
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            type="button"
                            onClick={() => {
                              updateMutation.reset();
                              setEditing(item);
                            }}
                            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-1.5 text-sm text-raven-text hover:border-raven-violet"
                          >
                            <Pencil className="h-4 w-4" aria-hidden="true" />
                            Edit
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              deleteMutation.reset();
                              setDeleting(item);
                            }}
                            className="inline-flex items-center gap-2 rounded-md border border-rose-400/30 px-3 py-1.5 text-sm text-rose-100 hover:bg-rose-500/10"
                          >
                            <Trash2 className="h-4 w-4" aria-hidden="true" />
                            Archive
                          </button>
                        </>
                      )}
                    </div>
                  ) : null}
                </div>
                {item.status === "archived" ? (
                  <p className="mt-3 text-xs leading-5 text-raven-muted">
                    Preserved by data governance. Restore to resume work, or use
                    permanent deletion only when allowed by governance policy.
                  </p>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : (
        <EmptyBlock
          title="No investigations yet"
          message="Investigations define an authorized defensive assessment scope and preserve its evidence, findings, and analyst workflow."
          nextStep="Create an investigation to define scope and authorization."
          permission="Analysts and administrators can create investigations."
        />
      )}
      {isCreating ? (
        <NewInvestigationModal
          engagementOptions={engagements.data?.items ?? []}
          onClose={() => setIsCreating(false)}
        />
      ) : null}
      {editing ? (
        <InvestigationEditModal
          investigation={editing}
          engagementOptions={engagements.data?.items ?? []}
          error={updateMutation.error?.message}
          isSaving={updateMutation.isPending}
          onClose={() => {
            updateMutation.reset();
            setEditing(null);
          }}
          onSubmit={(values) =>
            updateMutation.mutate({ id: editing.id, values })
          }
        />
      ) : null}
      {deleting ? (
        <DeleteInvestigationModal
          investigation={deleting}
          error={deleteMutation.error?.message}
          isDeleting={deleteMutation.isPending}
          onClose={() => {
            deleteMutation.reset();
            setDeleting(null);
          }}
          onConfirm={() => deleteMutation.mutate(deleting.id)}
        />
      ) : null}
      {purging ? (
        <PurgeInvestigationModal
          investigation={purging}
          error={purgeMutation.error?.message}
          isPurging={purgeMutation.isPending}
          onClose={() => {
            purgeMutation.reset();
            setPurging(null);
          }}
          onConfirm={() => purgeMutation.mutate(purging.id)}
        />
      ) : null}
    </>
  );
}

function NewInvestigationModal({
  engagementOptions,
  onClose,
}: {
  engagementOptions: Engagement[];
  onClose: () => void;
}): JSX.Element {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [authorizationStatement, setAuthorizationStatement] = useState("");
  const [engagementId, setEngagementId] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const createMutation = useMutation({
    mutationFn: createInvestigation,
    onSuccess: async (investigation) => {
      await queryClient.invalidateQueries({ queryKey: ["investigations"] });
      onClose();
      navigate(`/investigations/${investigation.id}`);
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const cleanTitle = title.trim();
    const cleanAuthorization = authorizationStatement.trim();
    if (!cleanTitle) {
      setValidationError("Title is required.");
      return;
    }
    if (cleanAuthorization.length < 100) {
      setValidationError("Authorization statement must be at least 100 characters.");
      return;
    }
    setValidationError(null);
    createMutation.mutate({
      title: cleanTitle,
      description: description.trim() || null,
      authorization_statement: cleanAuthorization,
      scope_definition: description.trim() || null,
      engagement_id: engagementId || null,
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-2xl rounded-lg border border-raven-border bg-raven-panel p-5 shadow-glow"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold">New Investigation</h2>
            <p className="mt-1 text-sm text-raven-muted">
              Create an authorized defensive investigation workspace.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-raven-border px-3 py-1.5 text-sm text-raven-muted hover:text-raven-text"
          >
            Close
          </button>
        </div>

        <label className="mt-5 block text-sm text-raven-muted" htmlFor="title">
          Title
        </label>
        <input
          id="title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
        />

        <label className="mt-4 block text-sm text-raven-muted" htmlFor="description">
          Description
        </label>
        <textarea
          id="description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={3}
          className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
        />

        <label className="mt-4 block text-sm text-raven-muted" htmlFor="authorization">
          Authorization statement
        </label>
        <textarea
          id="authorization"
          value={authorizationStatement}
          onChange={(event) => setAuthorizationStatement(event.target.value)}
          rows={5}
          className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
        />

        <label
          className="mt-4 block text-sm text-raven-muted"
          htmlFor="engagement"
        >
          Engagement
        </label>
        <select
          id="engagement"
          value={engagementId}
          onChange={(event) => setEngagementId(event.target.value)}
          className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
        >
          <option value="">No linked engagement</option>
          {engagementOptions.map((engagement) => (
            <option key={engagement.id} value={engagement.id}>
              {engagement.title} - {engagement.client_name}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs leading-5 text-raven-muted">
          Linking an engagement surfaces authorization and scope governance across
          this investigation.
        </p>

        {validationError ?? createMutation.error?.message ? (
          <div className="mt-4 rounded-md border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">
            {validationError ?? createMutation.error?.message}
          </div>
        ) : null}

        <div className="mt-5 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-raven-border px-4 py-2 text-sm text-raven-muted hover:text-raven-text"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-60"
          >
            {createMutation.isPending ? "Creating" : "Create"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Metric({
  label,
  icon,
}: {
  label: string;
  icon?: JSX.Element;
}): JSX.Element {
  return (
    <div className="flex items-center gap-2">
      {icon ? <span className="text-raven-cyan">{icon}</span> : null}
      <span>{label}</span>
    </div>
  );
}

function ownerContext(
  investigation: Investigation,
  userId: string | undefined,
  role: string | undefined,
): string {
  if (investigation.owner_id === userId) {
    return "Owner: you";
  }
  if (role === "admin") {
    return "Admin access";
  }
  return "Member access";
}

function canManageInvestigation(
  ownerId: string,
  userId: string | undefined,
  role: string | undefined,
): boolean {
  return ownerId === userId || role === "admin";
}
