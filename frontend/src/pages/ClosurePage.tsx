import {
  Archive,
  CheckCircle2,
  ClipboardCheck,
  FileArchive,
  Loader2,
  PackageCheck,
  Plus,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";
import { type FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { InvestigationTabs } from "../components/InvestigationTabs";
import { LongValue } from "../components/LongValue";
import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import {
  approveCaseClosure,
  archiveCaseDeliverable,
  closeCaseClosure,
  createCaseDeliverable,
  createCasePackageManifest,
  generateClosureChecklist,
  getCaseClosure,
  getInvestigation,
  listCaseDeliverables,
  listInvestigationMembers,
  listReports,
  reopenCaseClosure,
  submitCaseClosureReview,
  updateCaseClosure,
  updateCaseDeliverable,
  updateClosureChecklistItem,
} from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import { useAuth } from "../lib/useAuth";
import type {
  CaseClosureChecklistItem,
  CaseClosureChecklistStatus,
  CaseDeliverable,
  CaseDeliverableStatus,
  CaseDeliverableType,
  CaseFinalRiskRating,
  CasePackageManifestResponse,
  ReportFormat,
} from "../types";

const riskRatings: CaseFinalRiskRating[] = [
  "not_assessed",
  "low",
  "moderate",
  "elevated",
  "high",
  "critical",
];
const checklistStatuses: CaseClosureChecklistStatus[] = [
  "pending",
  "completed",
  "blocked",
  "not_applicable",
];
const deliverableTypes: CaseDeliverableType[] = [
  "executive_report",
  "technical_report",
  "evidence_appendix",
  "remediation_plan",
  "scope_summary",
  "audit_summary",
  "final_package",
];
const deliverableStatuses: CaseDeliverableStatus[] = [
  "draft",
  "ready",
  "approved",
  "delivered",
  "archived",
];
const formats: Array<ReportFormat | ""> = ["", "pdf", "docx", "html", "md"];

export function ClosurePage(): JSX.Element {
  const investigationId = useInvestigationId();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [toast, setToast] = useState<ToastState | null>(null);
  const [summary, setSummary] = useState("");
  const [riskRating, setRiskRating] =
    useState<CaseFinalRiskRating>("not_assessed");
  const [deliverableForm, setDeliverableForm] = useState({
    title: "",
    deliverable_type: "executive_report" as CaseDeliverableType,
    status: "draft" as CaseDeliverableStatus,
    report_id: "",
    export_format: "" as ReportFormat | "",
  });
  const [packageManifest, setPackageManifest] =
    useState<CasePackageManifestResponse | null>(null);

  const investigation = useQuery({
    queryKey: ["investigation", investigationId],
    queryFn: () => getInvestigation(investigationId),
  });
  const closure = useQuery({
    queryKey: ["case-closure", investigationId],
    queryFn: () => getCaseClosure(investigationId),
  });
  const deliverables = useQuery({
    queryKey: ["case-deliverables", investigationId],
    queryFn: () => listCaseDeliverables(investigationId),
  });
  const reports = useQuery({
    queryKey: ["reports", investigationId],
    queryFn: () => listReports(investigationId),
  });
  const members = useQuery({
    queryKey: ["members", investigationId],
    queryFn: () => listInvestigationMembers(investigationId),
  });

  const item = closure.data;
  const memberRole =
    members.data?.find((member) => member.user_id === user?.id)?.role ?? null;
  const canPrepare =
    user?.role === "admin" ||
    memberRole === "owner" ||
    memberRole === "admin" ||
    memberRole === "analyst";
  const canAdmin =
    user?.role === "admin" ||
    investigation.data?.owner_id === user?.id ||
    memberRole === "owner" ||
    memberRole === "admin";

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["case-closure", investigationId] }),
      queryClient.invalidateQueries({
        queryKey: ["case-deliverables", investigationId],
      }),
      queryClient.invalidateQueries({ queryKey: ["timeline", investigationId] }),
      queryClient.invalidateQueries({ queryKey: ["review-board"] }),
      queryClient.invalidateQueries({ queryKey: ["investigation", investigationId] }),
    ]);
  };

  const simpleMutation = useMutation({
    mutationFn: async (action: string) => {
      if (action === "generate") return generateClosureChecklist(investigationId);
      if (action === "submit") {
        return submitCaseClosureReview(investigationId, {
          closure_summary: summary || item?.closure_summary,
        });
      }
      if (action === "approve") return approveCaseClosure(investigationId);
      if (action === "reopen") return reopenCaseClosure(investigationId);
      if (action === "close") {
        const closureSummary =
          summary || item?.closure_summary || "Case closure approved.";
        const needsOverride =
          item?.status !== "approved" || (item?.blockers ?? []).length > 0;
        const overrideReason = needsOverride
          ? window.prompt("Override reason required for remaining blockers") ?? ""
          : null;
        return closeCaseClosure(investigationId, {
          closure_summary: closureSummary,
          override_reason: overrideReason || null,
        });
      }
      return updateCaseClosure(investigationId, {
        closure_summary: summary,
        final_risk_rating: riskRating,
      });
    },
    onSuccess: async () => {
      setToast({ kind: "success", message: "Case closure workflow updated." });
      await invalidate();
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message:
          error instanceof Error
            ? error.message
            : "Unable to update case closure workflow.",
      });
    },
  });

  const checklistMutation = useMutation({
    mutationFn: (input: {
      item: CaseClosureChecklistItem;
      status: CaseClosureChecklistStatus;
    }) =>
      updateClosureChecklistItem(investigationId, input.item.id, {
        status: input.status,
        description: input.item.description,
      }),
    onSuccess: invalidate,
    onError: (error) =>
      setToast({
        kind: "error",
        message:
          error instanceof Error ? error.message : "Unable to update checklist item.",
      }),
  });

  const deliverableMutation = useMutation({
    mutationFn: (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      return createCaseDeliverable(investigationId, {
        title: deliverableForm.title,
        deliverable_type: deliverableForm.deliverable_type,
        status: deliverableForm.status,
        report_id: deliverableForm.report_id || null,
        export_format: deliverableForm.export_format || null,
      });
    },
    onSuccess: async () => {
      setDeliverableForm({
        title: "",
        deliverable_type: "executive_report",
        status: "draft",
        report_id: "",
        export_format: "",
      });
      setToast({ kind: "success", message: "Deliverable record created." });
      await invalidate();
    },
    onError: (error) =>
      setToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Unable to create deliverable.",
      }),
  });

  const deliverableAction = useMutation({
    mutationFn: async (input: {
      deliverable: CaseDeliverable;
      status?: CaseDeliverableStatus;
      archive?: boolean;
    }) => {
      if (input.archive) {
        await archiveCaseDeliverable(investigationId, input.deliverable.id);
        return null;
      }
      return updateCaseDeliverable(investigationId, input.deliverable.id, {
        status: input.status,
      });
    },
    onSuccess: async () => {
      setToast({ kind: "success", message: "Deliverable updated." });
      await invalidate();
    },
    onError: (error) =>
      setToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Unable to update deliverable.",
      }),
  });

  const packageMutation = useMutation({
    mutationFn: () => createCasePackageManifest(investigationId),
    onSuccess: async (manifest) => {
      setPackageManifest(manifest);
      setToast({ kind: "success", message: "Package manifest generated." });
      await invalidate();
    },
    onError: (error) =>
      setToast({
        kind: "error",
        message:
          error instanceof Error ? error.message : "Unable to generate package manifest.",
      }),
  });

  if (investigation.isLoading || closure.isLoading) {
    return <LoadingBlock label="Loading case closure" />;
  }
  if (investigation.isError) {
    return <ErrorBlock message={investigation.error} />;
  }
  if (closure.isError) {
    return <ErrorBlock message={closure.error} />;
  }

  const reportItems = reports.data?.items ?? [];
  const deliverableItems = deliverables.data?.items ?? item?.deliverables ?? [];

  return (
    <div className="space-y-6">
      {toast ? (
        <ToastBanner toast={toast} onDismiss={() => setToast(null)} />
      ) : null}
      <PageHeader
        eyebrow="Client deliverables"
        title="Case Closure"
        actions={
          <button
            type="button"
            onClick={() => void closure.refetch()}
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-muted hover:border-raven-violet hover:text-raven-text"
          >
            <Loader2 className="h-4 w-4" aria-hidden="true" />
            Refresh
          </button>
        }
      />
      <p className="-mt-4 max-w-3xl text-sm leading-6 text-raven-muted">
        Prepare final review, deliverables, and evidence package manifests for
        analyst-approved defensive handoff.
      </p>
      <InvestigationTabs />

      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-raven-cyan">
              Closure status
            </p>
            <h2 className="mt-1 text-xl font-semibold">
              {formatLabel(item?.status ?? "draft")}
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-raven-muted">
              Closure is a governance checkpoint. It records final risk,
              unresolved warnings, and deliverables without deleting evidence or
              blocking report exports.
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-3 lg:text-right">
            <MiniMetric label="Risk" value={formatLabel(item?.final_risk_rating ?? "not_assessed")} />
            <MiniMetric label="Blockers" value={String(item?.blockers.length ?? 0)} />
            <MiniMetric
              label="Evidence"
              value={String(item?.evidence_package.evidence_count ?? 0)}
            />
          </div>
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_220px]">
          <label className="block">
            <span className="text-sm text-raven-muted">Closure summary</span>
            <textarea
              value={summary || item?.closure_summary || ""}
              onChange={(event) => setSummary(event.target.value)}
              rows={4}
              className="mt-1 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm outline-none focus:border-raven-violet"
              placeholder="Summarize final scope, residual risk, client handoff, and defensive next steps."
            />
          </label>
          <label className="block">
            <span className="text-sm text-raven-muted">Final risk rating</span>
            <select
              value={riskRating === "not_assessed" ? item?.final_risk_rating ?? riskRating : riskRating}
              onChange={(event) =>
                setRiskRating(event.target.value as CaseFinalRiskRating)
              }
              className="mt-1 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm outline-none focus:border-raven-violet"
            >
              {riskRatings.map((rating) => (
                <option key={rating} value={rating}>
                  {formatLabel(rating)}
                </option>
              ))}
            </select>
          </label>
        </div>

        {item?.warnings.length ? (
          <div className="mt-4 rounded-md border border-amber-400/30 bg-amber-500/10 p-3 text-sm text-amber-100">
            <p className="font-medium">Closure warnings</p>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {item.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="mt-5 flex flex-wrap gap-2">
          <ActionButton
            label="Save summary"
            icon={<ShieldCheck className="h-4 w-4" />}
            disabled={!canPrepare || simpleMutation.isPending}
            onClick={() => simpleMutation.mutate("save")}
          />
          <ActionButton
            label="Generate checklist"
            icon={<ClipboardCheck className="h-4 w-4" />}
            disabled={!canPrepare || simpleMutation.isPending}
            onClick={() => simpleMutation.mutate("generate")}
          />
          <ActionButton
            label="Submit for review"
            icon={<CheckCircle2 className="h-4 w-4" />}
            disabled={!canPrepare || simpleMutation.isPending || item?.status === "closed"}
            onClick={() => simpleMutation.mutate("submit")}
          />
          <ActionButton
            label="Approve"
            icon={<ShieldCheck className="h-4 w-4" />}
            disabled={!canAdmin || simpleMutation.isPending || item?.status !== "in_review"}
            onClick={() => simpleMutation.mutate("approve")}
          />
          <ActionButton
            label="Close case"
            icon={<PackageCheck className="h-4 w-4" />}
            disabled={!canAdmin || simpleMutation.isPending || item?.status === "closed"}
            onClick={() => simpleMutation.mutate("close")}
          />
          <ActionButton
            label="Reopen"
            icon={<RotateCcw className="h-4 w-4" />}
            disabled={!canAdmin || simpleMutation.isPending || item?.status !== "closed"}
            onClick={() => simpleMutation.mutate("reopen")}
          />
        </div>
        {!canPrepare ? (
          <p className="mt-3 text-xs text-raven-muted">
            Your role can review closure status but cannot mutate closure workflow.
          </p>
        ) : null}
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
          <h2 className="text-lg font-semibold">Closure checklist</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {(item?.checklist ?? []).length ? (
              (item?.checklist ?? []).map((check) => (
                <div
                  key={check.id}
                  className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Badge value={check.status} />
                    <span className="text-xs text-raven-muted">
                      {check.required ? "Required" : "Optional"}
                    </span>
                  </div>
                  <p className="mt-3 text-sm font-medium">{check.label}</p>
                  <p className="mt-2 text-xs leading-5 text-raven-muted">
                    {check.description}
                  </p>
                  <select
                    value={check.status}
                    disabled={!canPrepare || checklistMutation.isPending}
                    onChange={(event) =>
                      checklistMutation.mutate({
                        item: check,
                        status: event.target.value as CaseClosureChecklistStatus,
                      })
                    }
                    className="mt-3 w-full rounded-md border border-raven-border bg-raven-bg px-2 py-2 text-xs outline-none focus:border-raven-violet disabled:opacity-60"
                  >
                    {checklistStatuses.map((status) => (
                      <option key={status} value={status}>
                        {formatLabel(status)}
                      </option>
                    ))}
                  </select>
                </div>
              ))
            ) : (
              <EmptyBlock
                title="No checklist generated"
                message="Generate the deterministic closure checklist when the case is ready for final review."
                nextStep="Analysts can generate the checklist after evidence and reports exist."
              />
            )}
          </div>
        </div>

        <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
          <h2 className="text-lg font-semibold">Evidence package readiness</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <MiniMetric
              label="Evidence records"
              value={String(item?.evidence_package.evidence_count ?? 0)}
            />
            <MiniMetric
              label="Findings without evidence"
              value={String(item?.evidence_package.findings_without_evidence ?? 0)}
            />
          </div>
          <p className="mt-4 text-sm leading-6 text-raven-muted">
            {item?.evidence_package.evidence_chain_status ??
              "Evidence package summary is not available yet."}
          </p>
          <p className="mt-2 text-sm leading-6 text-raven-muted">
            {item?.evidence_package.scope_relation}
          </p>
          <div className="mt-4 rounded-md border border-raven-border bg-raven-panelSoft p-3">
            <p className="text-sm font-medium">Source summary</p>
            {Object.entries(item?.evidence_package.source_summary ?? {}).length ? (
              <ul className="mt-2 space-y-1 text-xs text-raven-muted">
                {Object.entries(item?.evidence_package.source_summary ?? {}).map(
                  ([source, count]) => (
                    <li key={source} className="flex justify-between gap-3">
                      <span className="break-all">{source}</span>
                      <span>{count}</span>
                    </li>
                  ),
                )}
              </ul>
            ) : (
              <p className="mt-2 text-xs text-raven-muted">
                No evidence sources are ready for packaging yet.
              </p>
            )}
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-lg font-semibold">Deliverables</h2>
            <p className="mt-2 text-sm text-raven-muted">
              Track client-ready records for reports, evidence appendix,
              remediation plan, scope summary, audit summary, and final package.
            </p>
          </div>
          <button
            type="button"
            onClick={() => packageMutation.mutate()}
            disabled={!canPrepare || packageMutation.isPending}
            className="inline-flex items-center gap-2 rounded-md bg-raven-violet px-3 py-2 text-sm text-white hover:bg-violet-500 disabled:opacity-60"
          >
            <FileArchive className="h-4 w-4" aria-hidden="true" />
            Create package manifest
          </button>
        </div>

        <form
          onSubmit={(event) => deliverableMutation.mutate(event)}
          className="mt-4 grid gap-3 lg:grid-cols-[1fr_180px_150px_220px_120px_auto]"
        >
          <input
            value={deliverableForm.title}
            onChange={(event) =>
              setDeliverableForm((current) => ({
                ...current,
                title: event.target.value,
              }))
            }
            placeholder="Deliverable title"
            className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm outline-none focus:border-raven-violet"
          />
          <select
            value={deliverableForm.deliverable_type}
            onChange={(event) =>
              setDeliverableForm((current) => ({
                ...current,
                deliverable_type: event.target.value as CaseDeliverableType,
              }))
            }
            className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm outline-none focus:border-raven-violet"
          >
            {deliverableTypes.map((type) => (
              <option key={type} value={type}>
                {formatLabel(type)}
              </option>
            ))}
          </select>
          <select
            value={deliverableForm.status}
            onChange={(event) =>
              setDeliverableForm((current) => ({
                ...current,
                status: event.target.value as CaseDeliverableStatus,
              }))
            }
            className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm outline-none focus:border-raven-violet"
          >
            {deliverableStatuses.map((status) => (
              <option key={status} value={status}>
                {formatLabel(status)}
              </option>
            ))}
          </select>
          <select
            value={deliverableForm.report_id}
            onChange={(event) =>
              setDeliverableForm((current) => ({
                ...current,
                report_id: event.target.value,
              }))
            }
            className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm outline-none focus:border-raven-violet"
          >
            <option value="">No linked report</option>
            {reportItems.map((report) => (
              <option key={report.id} value={report.id}>
                {report.title || `${formatLabel(report.report_type)} report`}
              </option>
            ))}
          </select>
          <select
            value={deliverableForm.export_format}
            onChange={(event) =>
              setDeliverableForm((current) => ({
                ...current,
                export_format: event.target.value as ReportFormat | "",
              }))
            }
            className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm outline-none focus:border-raven-violet"
          >
            {formats.map((format) => (
              <option key={format || "none"} value={format}>
                {format ? format.toUpperCase() : "Format"}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={!canPrepare || !deliverableForm.title.trim()}
            className="inline-flex items-center justify-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm hover:border-raven-violet disabled:opacity-60"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Add
          </button>
        </form>

        <div className="mt-4 overflow-x-auto">
          {deliverableItems.length ? (
            <table className="min-w-full divide-y divide-raven-border text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-raven-muted">
                <tr>
                  <th className="px-3 py-2">Title</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Report</th>
                  <th className="px-3 py-2">Format</th>
                  <th className="px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-raven-border">
                {deliverableItems.map((deliverable) => (
                  <tr key={deliverable.id}>
                    <td className="px-3 py-3">
                      <div className="max-w-[260px]">
                        <LongValue value={deliverable.title} />
                      </div>
                    </td>
                    <td className="px-3 py-3">{formatLabel(deliverable.deliverable_type)}</td>
                    <td className="px-3 py-3">
                      <Badge value={deliverable.status} />
                    </td>
                    <td className="px-3 py-3">
                      {deliverable.report_id ? (
                        <LongValue value={deliverable.report_id} />
                      ) : (
                        <span className="text-raven-muted">None</span>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      {deliverable.export_format?.toUpperCase() ?? "Any"}
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap gap-2">
                        <SmallButton
                          label="Ready"
                          disabled={!canPrepare}
                          onClick={() =>
                            deliverableAction.mutate({
                              deliverable,
                              status: "ready",
                            })
                          }
                        />
                        <SmallButton
                          label="Approve"
                          disabled={!canAdmin}
                          onClick={() =>
                            deliverableAction.mutate({
                              deliverable,
                              status: "approved",
                            })
                          }
                        />
                        <SmallButton
                          label="Archive"
                          disabled={!canPrepare}
                          icon={<Archive className="h-3.5 w-3.5" />}
                          onClick={() =>
                            deliverableAction.mutate({
                              deliverable,
                              archive: true,
                            })
                          }
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyBlock
              title="No deliverables tracked"
              message="Create deliverable records for client-ready reports, appendix material, remediation plans, or final package manifests."
              nextStep="Start with an executive or technical report deliverable after reports are generated."
            />
          )}
        </div>

        {packageManifest ? (
          <div className="mt-5 rounded-md border border-raven-violet bg-raven-violet/10 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-medium">Package manifest</p>
              <Badge value={packageManifest.readiness_status} />
            </div>
            <p className="mt-2 text-sm text-raven-muted">
              Included deliverables: {packageManifest.included_deliverables.length}.
              Missing: {packageManifest.missing_deliverables.length}.
            </p>
            {packageManifest.warnings.length ? (
              <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-amber-100">
                {packageManifest.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <p className="text-xs uppercase tracking-wide text-raven-muted">{label}</p>
      <p className="mt-1 break-words text-lg font-semibold">{value}</p>
    </div>
  );
}

function ActionButton({
  label,
  icon,
  disabled,
  onClick,
}: {
  label: string;
  icon: JSX.Element;
  disabled: boolean;
  onClick: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm hover:border-raven-violet disabled:cursor-not-allowed disabled:opacity-60"
    >
      {icon}
      {label}
    </button>
  );
}

function SmallButton({
  label,
  icon,
  disabled,
  onClick,
}: {
  label: string;
  icon?: JSX.Element;
  disabled: boolean;
  onClick: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center gap-1 rounded border border-raven-border px-2 py-1 text-xs text-raven-muted hover:border-raven-violet hover:text-raven-text disabled:cursor-not-allowed disabled:opacity-60"
    >
      {icon}
      {label}
    </button>
  );
}

function Badge({ value }: { value: string }): JSX.Element {
  return (
    <span
      className={[
        "inline-flex rounded border px-2 py-1 text-xs capitalize",
        badgeTone(value),
      ].join(" ")}
    >
      {formatLabel(value)}
    </span>
  );
}

function badgeTone(value: string): string {
  if (["completed", "ready", "approved", "delivered", "closed", "ready_with_warnings"].includes(value)) {
    return "border-emerald-400/40 bg-emerald-500/10 text-emerald-100";
  }
  if (["blocked", "critical", "high", "missing_required_deliverables"].includes(value)) {
    return "border-rose-400/40 bg-rose-500/10 text-rose-100";
  }
  if (["pending", "draft", "in_review", "reopened", "elevated"].includes(value)) {
    return "border-amber-400/40 bg-amber-500/10 text-amber-100";
  }
  return "border-raven-border bg-raven-panel text-raven-muted";
}

function formatLabel(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
