import { Archive, FileCheck2, Plus, ShieldCheck, X } from "lucide-react";
import { useMemo, useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { LongValue } from "../components/LongValue";
import { PageHeader } from "../components/PageHeader";
import { SavedViewsPanel } from "../components/SavedViewsPanel";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import {
  archiveEngagement,
  createAuthorizationEvidence,
  createEngagement,
  createEngagementScopeItem,
  deleteAuthorizationEvidence,
  deleteEngagementScopeItem,
  listAuthorizationEvidence,
  listEngagementScopeItems,
  listEngagements,
  updateEngagement,
} from "../lib/api";
import type {
  AuthorizationEvidence,
  AuthorizationEvidenceType,
  AuthorizationStatus,
  Engagement,
  EngagementStatus,
  ScopeStatus,
  ScopeType,
} from "../types";
import { safeArray } from "../lib/safe";

const engagementStatuses: EngagementStatus[] = [
  "draft",
  "active",
  "completed",
  "archived",
];
const authorizationStatuses: AuthorizationStatus[] = [
  "not_provided",
  "pending_review",
  "approved",
  "expired",
  "revoked",
];
const scopeTypes: ScopeType[] = [
  "domain",
  "subdomain",
  "ip",
  "cidr",
  "email",
  "username",
  "organization",
  "other",
];
const scopeStatuses: ScopeStatus[] = ["in_scope", "pending_review", "out_of_scope"];
const evidenceTypes: AuthorizationEvidenceType[] = [
  "contract",
  "email_approval",
  "statement_of_work",
  "internal_authorization",
  "other",
];

export function EngagementsPage(): JSX.Element {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);

  const engagements = useQuery({
    queryKey: ["engagements", includeArchived],
    queryFn: () => listEngagements(includeArchived),
  });

  const requestedId = searchParams.get("engagement");
  const items = useMemo(
    () => safeArray(engagements.data?.items),
    [engagements.data?.items],
  );
  const selected = useMemo(
    () =>
      items.find((item) => item.id === selectedId) ??
      items.find((item) => item.id === requestedId) ??
      items[0] ??
      null,
    [items, requestedId, selectedId],
  );

  const archiveMutation = useMutation({
    mutationFn: archiveEngagement,
    onSuccess: async () => {
      setToast({ kind: "success", message: "Engagement archived." });
      await queryClient.invalidateQueries({ queryKey: ["engagements"] });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Unable to archive.",
      });
    },
  });

  if (engagements.isLoading) {
    return <LoadingBlock label="Loading engagements" />;
  }
  if (engagements.isError) {
    return <ErrorBlock message={engagements.error} />;
  }

  return (
    <>
      <PageHeader
        title="Engagements"
        eyebrow="Scope governance"
        actions={
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setIncludeArchived((value) => !value)}
              className="rounded-md border border-raven-border px-3 py-2 text-sm text-raven-muted hover:border-raven-violet hover:text-raven-text"
            >
              {includeArchived ? "Hide archived" : "Show archived"}
            </button>
            <button
              type="button"
              onClick={() => setShowCreate(true)}
              className="inline-flex items-center gap-2 rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500"
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              New Engagement
            </button>
          </div>
        }
      />
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}
      <div className="mb-5">
        <SavedViewsPanel
          viewType="engagements"
          route="/engagements"
          filters={{ includeArchived }}
          onApply={(view) => {
            setIncludeArchived(view.filters.includeArchived === true);
            setToast({ kind: "success", message: `Loaded ${view.name}.` });
          }}
        />
      </div>
      {items.length ? (
        <div className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
          <section className="space-y-3">
            {items.map((engagement) => (
              <button
                key={engagement.id}
                type="button"
                onClick={() => setSelectedId(engagement.id)}
                className={[
                  "w-full rounded-lg border bg-raven-panel/85 p-4 text-left transition",
                  selected?.id === engagement.id
                    ? "border-raven-violet"
                    : "border-raven-border hover:border-raven-violet",
                ].join(" ")}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="font-semibold text-raven-text">
                    {engagement.title}
                  </h2>
                  <StatusBadge value={engagement.status} />
                </div>
                <p className="mt-2 text-sm text-raven-muted">
                  {engagement.client_name}
                </p>
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  <StatusBadge value={engagement.authorization_status} />
                  <span className="rounded border border-raven-border px-2 py-1 text-raven-muted">
                    {engagement.linked_investigations_count} linked cases
                  </span>
                  <span className="rounded border border-raven-border px-2 py-1 text-raven-muted">
                    {engagement.scope_counts.in_scope ?? 0} approved scope
                  </span>
                </div>
              </button>
            ))}
          </section>
          {selected ? (
            <EngagementDetail
              engagement={selected}
              isArchiving={archiveMutation.isPending}
              onArchive={() => {
                if (window.confirm("Archive this engagement metadata?")) {
                  archiveMutation.mutate(selected.id);
                }
              }}
              onToast={setToast}
            />
          ) : null}
        </div>
      ) : (
        <EmptyBlock
          title="No engagements yet"
          message="Engagements capture client metadata, authorization status, and approved defensive scope."
          nextStep="Create an engagement before linking investigations when scope governance is required."
          permission="Analysts and administrators can create engagement metadata."
        />
      )}
      {showCreate ? (
        <CreateEngagementModal
          onClose={() => setShowCreate(false)}
          onCreated={(engagement) => {
            setSelectedId(engagement.id);
            setShowCreate(false);
            setToast({ kind: "success", message: "Engagement created." });
          }}
        />
      ) : null}
    </>
  );
}

function EngagementDetail({
  engagement,
  isArchiving,
  onArchive,
  onToast,
}: {
  engagement: Engagement;
  isArchiving: boolean;
  onArchive: () => void;
  onToast: (toast: ToastState | null) => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<EngagementStatus>(engagement.status);
  const [authorizationStatus, setAuthorizationStatus] =
    useState<AuthorizationStatus>(engagement.authorization_status);

  const scope = useQuery({
    queryKey: ["engagement-scope", engagement.id],
    queryFn: () => listEngagementScopeItems(engagement.id),
  });
  const evidence = useQuery({
    queryKey: ["engagement-authorization", engagement.id],
    queryFn: () => listAuthorizationEvidence(engagement.id),
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      updateEngagement(engagement.id, {
        status,
        authorization_status: authorizationStatus,
      }),
    onSuccess: async () => {
      onToast({ kind: "success", message: "Engagement status updated." });
      await queryClient.invalidateQueries({ queryKey: ["engagements"] });
    },
    onError: (error) =>
      onToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Unable to update.",
      }),
  });
  const deleteScopeMutation = useMutation({
    mutationFn: (scopeId: string) => deleteEngagementScopeItem(engagement.id, scopeId),
    onSuccess: async () => {
      onToast({ kind: "success", message: "Scope item removed." });
      await queryClient.invalidateQueries({
        queryKey: ["engagement-scope", engagement.id],
      });
      await queryClient.invalidateQueries({ queryKey: ["engagements"] });
    },
  });
  const deleteEvidenceMutation = useMutation({
    mutationFn: (evidenceId: string) =>
      deleteAuthorizationEvidence(engagement.id, evidenceId),
    onSuccess: async () => {
      onToast({ kind: "success", message: "Authorization metadata removed." });
      await queryClient.invalidateQueries({
        queryKey: ["engagement-authorization", engagement.id],
      });
    },
  });

  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-raven-cyan">
            Engagement detail
          </p>
          <h2 className="mt-1 text-xl font-semibold">{engagement.title}</h2>
          <p className="mt-2 text-sm text-raven-muted">
            {engagement.description ?? "No description stored."}
          </p>
        </div>
        {engagement.status !== "archived" ? (
          <button
            type="button"
            onClick={onArchive}
            disabled={isArchiving}
            className="inline-flex items-center gap-2 rounded-md border border-amber-400/30 px-3 py-2 text-sm text-amber-100 hover:bg-amber-500/10 disabled:opacity-60"
          >
            <Archive className="h-4 w-4" aria-hidden="true" />
            Archive
          </button>
        ) : null}
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <Info label="Client" value={engagement.client_name} />
        <Info label="Contact" value={engagement.client_contact ?? "Not provided"} />
        <Info label="Start" value={formatDate(engagement.start_date)} />
        <Info label="End" value={formatDate(engagement.end_date)} />
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-[1fr_1fr_auto]">
        <SelectField
          label="Engagement status"
          value={status}
          onChange={(value) => setStatus(value as EngagementStatus)}
          options={engagementStatuses}
        />
        <SelectField
          label="Authorization"
          value={authorizationStatus}
          onChange={(value) => setAuthorizationStatus(value as AuthorizationStatus)}
          options={authorizationStatuses}
        />
        <button
          type="button"
          onClick={() => updateMutation.mutate()}
          disabled={updateMutation.isPending}
          className="self-end rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-60"
        >
          Save
        </button>
      </div>

      <div className="mt-6 grid gap-5 xl:grid-cols-2">
        <Panel title="Scope Items" icon={<ShieldCheck className="h-5 w-5" />}>
          <ScopeForm engagementId={engagement.id} onToast={onToast} />
          <div className="mt-4 space-y-2">
            {(scope.data ?? []).length ? (
              (scope.data ?? []).map((item) => (
                <div
                  key={item.id}
                  className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <StatusBadge value={item.status} />
                      <p className="mt-2 text-sm text-raven-muted">
                        {item.scope_type}
                      </p>
                      <LongValue value={item.value} className="mt-1 font-medium" />
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        if (window.confirm("Remove this scope item?")) {
                          deleteScopeMutation.mutate(item.id);
                        }
                      }}
                      className="rounded border border-rose-400/30 p-2 text-rose-100 hover:bg-rose-500/10"
                    >
                      <X className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <p className="rounded-md border border-raven-border bg-raven-panelSoft p-3 text-sm text-raven-muted">
                No scope items stored. Add approved, pending, or out-of-scope
                values for analyst review.
              </p>
            )}
          </div>
        </Panel>

        <Panel title="Authorization Metadata" icon={<FileCheck2 className="h-5 w-5" />}>
          <AuthorizationForm engagementId={engagement.id} onToast={onToast} />
          <div className="mt-4 space-y-2">
            {(evidence.data ?? []).length ? (
              (evidence.data ?? []).map((item: AuthorizationEvidence) => (
                <div
                  key={item.id}
                  className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <StatusBadge value={item.status} />
                      <p className="mt-2 font-medium">{item.title}</p>
                      <p className="mt-1 text-sm text-raven-muted">
                        {item.evidence_type}
                      </p>
                      {item.reference ? (
                        <LongValue
                          value={item.reference}
                          className="mt-1 text-sm text-raven-muted"
                        />
                      ) : null}
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        if (window.confirm("Remove this authorization metadata?")) {
                          deleteEvidenceMutation.mutate(item.id);
                        }
                      }}
                      className="rounded border border-rose-400/30 p-2 text-rose-100 hover:bg-rose-500/10"
                    >
                      <X className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <p className="rounded-md border border-raven-border bg-raven-panelSoft p-3 text-sm text-raven-muted">
                No authorization metadata stored. Store references only unless a
                governed evidence repository is available.
              </p>
            )}
          </div>
        </Panel>
      </div>
    </section>
  );
}

function CreateEngagementModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (engagement: Engagement) => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [clientName, setClientName] = useState("");
  const [description, setDescription] = useState("");
  const [authorizationStatus, setAuthorizationStatus] =
    useState<AuthorizationStatus>("pending_review");
  const [validationError, setValidationError] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: createEngagement,
    onSuccess: async (engagement) => {
      await queryClient.invalidateQueries({ queryKey: ["engagements"] });
      onCreated(engagement);
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (!title.trim() || !clientName.trim()) {
      setValidationError("Title and client name are required.");
      return;
    }
    setValidationError(null);
    mutation.mutate({
      title: title.trim(),
      client_name: clientName.trim(),
      description: description.trim() || null,
      status: "draft",
      authorization_status: authorizationStatus,
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
            <h2 className="text-xl font-semibold">New Engagement</h2>
            <p className="mt-1 text-sm text-raven-muted">
              Store client metadata, authorization posture, and approved scope
              references.
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
        <TextInput label="Title" value={title} onChange={setTitle} />
        <TextInput label="Client name" value={clientName} onChange={setClientName} />
        <SelectField
          label="Authorization"
          value={authorizationStatus}
          onChange={(value) => setAuthorizationStatus(value as AuthorizationStatus)}
          options={authorizationStatuses}
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
        {validationError ?? mutation.error?.message ? (
          <div className="mt-4 rounded-md border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">
            {validationError ?? mutation.error?.message}
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
            disabled={mutation.isPending}
            className="rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-60"
          >
            {mutation.isPending ? "Creating" : "Create engagement"}
          </button>
        </div>
      </form>
    </div>
  );
}

function ScopeForm({
  engagementId,
  onToast,
}: {
  engagementId: string;
  onToast: (toast: ToastState | null) => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const [scopeType, setScopeType] = useState<ScopeType>("domain");
  const [value, setValue] = useState("");
  const [status, setStatus] = useState<ScopeStatus>("in_scope");
  const mutation = useMutation({
    mutationFn: () =>
      createEngagementScopeItem(engagementId, {
        scope_type: scopeType,
        value,
        status,
      }),
    onSuccess: async () => {
      setValue("");
      onToast({ kind: "success", message: "Scope item added." });
      await queryClient.invalidateQueries({
        queryKey: ["engagement-scope", engagementId],
      });
      await queryClient.invalidateQueries({ queryKey: ["engagements"] });
    },
    onError: (error) =>
      onToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Unable to add scope.",
      }),
  });
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (value.trim()) {
          mutation.mutate();
        }
      }}
      className="grid gap-2 md:grid-cols-[1fr_1fr_1fr_auto]"
    >
      <SelectField
        label="Type"
        value={scopeType}
        onChange={(next) => setScopeType(next as ScopeType)}
        options={scopeTypes}
      />
      <TextInput label="Value" value={value} onChange={setValue} compact />
      <SelectField
        label="Status"
        value={status}
        onChange={(next) => setStatus(next as ScopeStatus)}
        options={scopeStatuses}
      />
      <button
        type="submit"
        disabled={!value.trim() || mutation.isPending}
        className="self-end rounded-md border border-raven-border px-3 py-2 text-sm hover:border-raven-violet disabled:opacity-60"
      >
        Add
      </button>
    </form>
  );
}

function AuthorizationForm({
  engagementId,
  onToast,
}: {
  engagementId: string;
  onToast: (toast: ToastState | null) => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [evidenceType, setEvidenceType] =
    useState<AuthorizationEvidenceType>("internal_authorization");
  const [status, setStatus] = useState<AuthorizationStatus>("approved");
  const [reference, setReference] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      createAuthorizationEvidence(engagementId, {
        title,
        evidence_type: evidenceType,
        status,
        reference: reference.trim() || null,
      }),
    onSuccess: async () => {
      setTitle("");
      setReference("");
      onToast({ kind: "success", message: "Authorization metadata added." });
      await queryClient.invalidateQueries({
        queryKey: ["engagement-authorization", engagementId],
      });
    },
    onError: (error) =>
      onToast({
        kind: "error",
        message:
          error instanceof Error
            ? error.message
            : "Unable to add authorization metadata.",
      }),
  });
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (title.trim()) {
          mutation.mutate();
        }
      }}
      className="space-y-2"
    >
      <TextInput label="Title" value={title} onChange={setTitle} compact />
      <div className="grid gap-2 md:grid-cols-2">
        <SelectField
          label="Type"
          value={evidenceType}
          onChange={(next) => setEvidenceType(next as AuthorizationEvidenceType)}
          options={evidenceTypes}
        />
        <SelectField
          label="Status"
          value={status}
          onChange={(next) => setStatus(next as AuthorizationStatus)}
          options={authorizationStatuses}
        />
      </div>
      <TextInput label="Reference" value={reference} onChange={setReference} compact />
      <button
        type="submit"
        disabled={!title.trim() || mutation.isPending}
        className="w-full rounded-md border border-raven-border px-3 py-2 text-sm hover:border-raven-violet disabled:opacity-60"
      >
        Add authorization metadata
      </button>
    </form>
  );
}

function Panel({
  title,
  icon,
  children,
}: {
  title: string;
  icon: JSX.Element;
  children: ReactNode;
}): JSX.Element {
  return (
    <div className="rounded-lg border border-raven-border bg-raven-bg/40 p-4">
      <h3 className="flex items-center gap-2 font-semibold">
        {icon}
        {title}
      </h3>
      <div className="mt-4">{children}</div>
    </div>
  );
}

function TextInput({
  label,
  value,
  onChange,
  compact = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  compact?: boolean;
}): JSX.Element {
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <label
      className={
        compact
          ? "block text-sm text-raven-muted"
          : "mt-4 block text-sm text-raven-muted"
      }
      htmlFor={id}
    >
      {label}
      <input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
}): JSX.Element {
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <label className="block text-sm text-raven-muted" htmlFor={id}>
      {label}
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {labelText(option)}
          </option>
        ))}
      </select>
    </label>
  );
}

function StatusBadge({ value }: { value: string }): JSX.Element {
  const tone =
    value.includes("approved") || value === "active" || value === "in_scope"
      ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-100"
      : value.includes("revoked") ||
          value.includes("expired") ||
          value === "out_of_scope"
        ? "border-rose-400/30 bg-rose-500/10 text-rose-100"
        : "border-raven-border bg-raven-panelSoft text-raven-muted";
  return (
    <span className={["rounded border px-2 py-1 text-xs capitalize", tone].join(" ")}>
      {labelText(value)}
    </span>
  );
}

function Info({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <p className="text-xs uppercase tracking-wide text-raven-muted">{label}</p>
      <p className="mt-1 break-words text-sm text-raven-text">{value}</p>
    </div>
  );
}

function formatDate(value: string | null): string {
  if (!value) {
    return "Not set";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Invalid date" : date.toLocaleDateString();
}

function labelText(value: string): string {
  return value.replace(/_/g, " ");
}
