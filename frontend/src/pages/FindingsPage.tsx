import {
  BookOpenCheck,
  BrainCircuit,
  ChevronDown,
  ChevronRight,
  Loader2,
  SearchX,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { InvestigationTabs } from "../components/InvestigationTabs";
import { BookmarkButton } from "../components/BookmarkButton";
import { LongValue } from "../components/LongValue";
import { PageHeader } from "../components/PageHeader";
import { SeverityBadge } from "../components/SeverityBadge";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import {
  assignFinding,
  generateFindings,
  listFindingPlaybooks,
  listInvestigationMembers,
  listFindings,
  startFindingPlaybook,
  updateFindingRemediation,
  updateFindingStatus,
} from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import { useAuth } from "../lib/useAuth";
import type {
  Finding,
  FindingEvidence,
  FindingRemediationUpdate,
  FindingStatus,
  InvestigationMember,
  RemediationStatus,
  Severity,
} from "../types";

const severities: Array<Severity | "all"> = [
  "all",
  "critical",
  "high",
  "medium",
  "low",
  "info",
];
const severityRank: Record<Severity, number> = {
  critical: 5,
  high: 4,
  medium: 3,
  low: 2,
  info: 1,
};
const findingStatuses: FindingStatus[] = [
  "new",
  "under_review",
  "validated",
  "accepted_risk",
  "mitigated",
  "false_positive",
  "archived",
];
const remediationStatuses: RemediationStatus[] = [
  "not_started",
  "validating",
  "remediation_planned",
  "in_progress",
  "pending_verification",
  "remediated",
  "accepted_risk",
  "false_positive",
];
type SortMode = "newest" | "severity";

export function FindingsPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [source, setSource] = useState("all");
  const [target, setTarget] = useState("all");
  const [sortMode, setSortMode] = useState<SortMode>("newest");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<ToastState | null>(null);
  const findings = useQuery({
    queryKey: ["findings", investigationId],
    queryFn: () => listFindings(investigationId),
  });
  const members = useQuery({
    queryKey: ["members", investigationId],
    queryFn: () => listInvestigationMembers(investigationId),
  });
  const currentMember = members.data?.find(
    (member) => member.user_id === user?.id,
  );
  const canMutate =
    user?.role === "admin" ||
    currentMember?.role === "owner" ||
    currentMember?.role === "admin" ||
    currentMember?.role === "analyst";
  const generate = useMutation({
    mutationFn: () => generateFindings(investigationId),
    onSuccess: async (items) => {
      await queryClient.invalidateQueries({ queryKey: ["findings", investigationId] });
      setToast({
        kind: "success",
        message: `${items.length} deterministic findings are available.`,
      });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message:
          error instanceof Error
            ? error.message
            : "Unable to refresh findings intelligence.",
      });
    },
  });
  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: FindingStatus }) =>
      updateFindingStatus(id, { status }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["findings", investigationId] });
      await queryClient.invalidateQueries({ queryKey: ["timeline", investigationId] });
      setToast({ kind: "success", message: "Finding status updated." });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message: error instanceof Error ? error.message : "Unable to update finding.",
      });
    },
  });
  const assignMutation = useMutation({
    mutationFn: ({ id, userId }: { id: string; userId: string }) =>
      assignFinding(id, {
        assigned_to: userId.trim() || null,
        reviewed_by: null,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["findings", investigationId] });
      setToast({ kind: "success", message: "Finding ownership updated." });
    },
    onError: (error) => {
      setToast({
        kind: "error",
        message:
          error instanceof Error ? error.message : "Unable to update ownership.",
      });
    },
  });

  const sources = useMemo(() => {
    const unique = new Set((findings.data ?? []).map((item) => item.source));
    return ["all", ...Array.from(unique).sort()];
  }, [findings.data]);

  const targets = useMemo(() => {
    const unique = new Set((findings.data ?? []).flatMap(findingTargets));
    return ["all", ...Array.from(unique).sort()];
  }, [findings.data]);

  const filtered = useMemo(() => {
    const items = findings.data ?? [];
    return items
      .filter((item) => severity === "all" || item.severity === severity)
      .filter((item) => source === "all" || item.source === source)
      .filter((item) => target === "all" || findingTargets(item).includes(target))
      .sort((left, right) => {
        if (sortMode === "severity") {
          return (
            severityRank[right.severity] - severityRank[left.severity] ||
            right.risk_score - left.risk_score
          );
        }
        return (
          new Date(right.created_at).getTime() -
          new Date(left.created_at).getTime()
        );
      });
  }, [findings.data, severity, sortMode, source, target]);

  function toggleExpanded(id: string): void {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  if (findings.isLoading) {
    return <LoadingBlock label="Loading findings" />;
  }
  if (findings.isError) {
    return <ErrorBlock message={findings.error.message} />;
  }

  return (
    <>
      <PageHeader
        title="Findings"
        eyebrow="Correlation output"
        actions={
          <div className="flex flex-wrap gap-2">
            {canMutate ? (
              <button
                type="button"
                onClick={() => generate.mutate()}
                disabled={generate.isPending}
                className="inline-flex items-center gap-2 rounded-md bg-raven-violet px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-60"
              >
                {generate.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <BrainCircuit className="h-4 w-4" aria-hidden="true" />
                )}
                Refresh intelligence
              </button>
            ) : null}
            <FilterSelect
              label="Severity"
              value={severity}
              options={severities}
              onChange={(value) => setSeverity(value as Severity | "all")}
            />
            <FilterSelect
              label="Source"
              value={source}
              options={sources}
              onChange={setSource}
            />
            <FilterSelect
              label="Target"
              value={target}
              options={targets}
              onChange={setTarget}
            />
            <FilterSelect
              label="Sort"
              value={sortMode}
              options={["newest", "severity"]}
              onChange={(value) => setSortMode(value as SortMode)}
            />
          </div>
        }
      />
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}
      <InvestigationTabs />

      {filtered.length ? (
        <div className="space-y-4">
          {filtered.map((finding) => {
            const isExpanded = expanded.has(finding.id);
            return (
              <article
                key={finding.id}
                className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"
              >
                <button
                  type="button"
                  onClick={() => toggleExpanded(finding.id)}
                  className="flex w-full flex-col gap-3 text-left md:flex-row md:items-start md:justify-between"
                >
                  <div className="flex gap-3">
                    <span className="mt-1 text-raven-cyan">
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4" aria-hidden="true" />
                      ) : (
                        <ChevronRight className="h-4 w-4" aria-hidden="true" />
                      )}
                    </span>
                    <div>
                      <h2 className="font-semibold">{finding.title}</h2>
                      <p className="mt-2 line-clamp-2 text-sm leading-6 text-raven-muted">
                        {finding.summary || finding.description}
                      </p>
                    </div>
                  </div>
                  <SeverityBadge severity={finding.severity} />
                </button>

                <div className="mt-4 grid gap-3 text-sm text-raven-muted md:grid-cols-6">
                  <Metric label="Risk" value={`${finding.risk_score}/100`} />
                  <Metric
                    label="Confidence"
                    value={`${finding.confidence_score}%`}
                  />
                  <Metric label="Source" value={finding.source} />
                  <Metric label="Status" value={finding.status} />
                  <Metric label="Owner" value={finding.assigned_to ?? "Unassigned"} />
                  <Metric
                    label="Created"
                    value={new Date(finding.created_at).toLocaleString()}
                  />
                </div>
                <div className="mt-4">
                  <BookmarkButton
                    investigationId={investigationId}
                    findingId={finding.id}
                    title={`Finding: ${finding.title}`}
                  />
                </div>

                {isExpanded ? (
                  <FindingDetails
                    finding={finding}
                    members={members.data ?? []}
                    canMutate={canMutate}
                    onStatusChange={(status) =>
                      statusMutation.mutate({ id: finding.id, status })
                    }
                    onAssign={(userId) =>
                      assignMutation.mutate({ id: finding.id, userId })
                    }
                  />
                ) : null}
              </article>
            );
          })}
        </div>
      ) : findings.data?.length ? (
        <EmptyBlock message="No findings match the current filters. Clear a filter or change the sort to review stored findings." />
      ) : (
        <EmptyBlock message="No findings have been generated yet. Run passive recon and threat intelligence, then correlation can create evidence-backed findings." />
      )}
    </>
  );
}

function FindingDetails({
  finding,
  members,
  canMutate,
  onStatusChange,
  onAssign,
}: {
  finding: Finding;
  members: InvestigationMember[];
  canMutate: boolean;
  onStatusChange: (status: FindingStatus) => void;
  onAssign: (userId: string) => void;
}): JSX.Element {
  const targets = findingTargets(finding);
  const [assignee, setAssignee] = useState(finding.assigned_to ?? "");
  return (
    <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_0.8fr]">
      <section className="rounded-md border border-raven-border bg-raven-panelSoft p-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-raven-muted">
          Evidence Summary
        </h3>
        {finding.evidence.length ? (
          <div className="mt-3 space-y-3">
            {finding.evidence.map((item) => (
              <EvidenceCard key={item.id} evidence={item} />
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-raven-muted">
            No detailed evidence records are linked to this finding yet.
          </p>
        )}
      </section>

      <section className="rounded-md border border-raven-border bg-raven-panelSoft p-4">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-raven-muted">
          Citations and Context
        </h3>
        <div className="mt-3 space-y-3 text-sm text-raven-muted">
          <div>
            <p className="text-xs uppercase tracking-wide">Review workflow</p>
            <div className="mt-2 grid gap-2">
              <select
                value={finding.status}
                disabled={!canMutate}
                onChange={(event) =>
                  onStatusChange(event.target.value as FindingStatus)
                }
                className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
              >
                {findingStatuses.map((status) => (
                  <option key={status} value={status}>
                    {labelForOption(status)}
                  </option>
                ))}
              </select>
              {canMutate ? <div className="flex gap-2">
                <select
                  value={assignee}
                  onChange={(event) => setAssignee(event.target.value)}
                  className="min-w-0 flex-1 rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
                >
                  <option value="">Unassigned</option>
                  {members.map((member) => (
                    <option key={member.id} value={member.user_id}>
                      {member.username} ({member.role})
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => onAssign(assignee)}
                  className="rounded-md border border-raven-border px-3 py-2 text-raven-text hover:border-raven-violet"
                >
                  Assign
                </button>
              </div> : null}
            </div>
          </div>
          <RemediationPanel
            finding={finding}
            members={members}
            canMutate={canMutate}
          />
          <RecommendedPlaybooks finding={finding} canMutate={canMutate} />
          <div>
            <p className="text-xs uppercase tracking-wide">Targets</p>
            <ChipList
              values={finding.affected_targets.length ? finding.affected_targets : targets}
              empty="No target metadata found."
            />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide">Remediation guidance</p>
            <BulletList
              values={finding.remediation_guidance}
              empty="No remediation guidance stored."
            />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide">Analyst notes</p>
            <BulletList
              values={finding.analyst_notes}
              empty="No analyst notes stored."
            />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide">Review notes</p>
            <BulletList
              values={[
                finding.review_notes,
                finding.remediation_notes,
                finding.validation_notes,
              ].filter((item): item is string => Boolean(item))}
              empty="No review notes stored."
            />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide">Framework mappings</p>
            {finding.framework_mappings.length ? (
              <div className="mt-2 space-y-2">
                {finding.framework_mappings.map((mapping) => (
                  <div
                    key={`${mapping.framework}-${mapping.control}`}
                    className="rounded border border-raven-border p-2"
                  >
                    <p className="text-raven-text">
                      {mapping.framework}: {mapping.control}
                    </p>
                    <p className="mt-1 text-xs leading-5">{mapping.rationale}</p>
                  </div>
                ))}
              </div>
            ) : (
              <ChipList values={[]} empty="No framework mappings stored." />
            )}
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide">Tags</p>
            <ChipList values={finding.tags} empty="No tags stored." />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide">References</p>
            <ChipList values={finding.references} empty="No references stored." />
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide">Evidence IDs</p>
            <ChipList
              values={finding.evidence.map((item) => item.id)}
              empty="No evidence citations stored."
            />
          </div>
          <div className="grid gap-2 pt-1 text-xs">
            <p>Updated {new Date(finding.updated_at).toLocaleString()}</p>
            <LongValue label="Finding ID" value={finding.id} maxLength={42} />
          </div>
        </div>
      </section>
    </div>
  );
}

function RemediationPanel({
  finding,
  members,
  canMutate,
}: {
  finding: Finding;
  members: InvestigationMember[];
  canMutate: boolean;
}): JSX.Element {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<RemediationStatus>(
    finding.remediation_status,
  );
  const [owner, setOwner] = useState(finding.remediation_owner ?? "");
  const [dueDate, setDueDate] = useState(finding.remediation_due_date ?? "");
  const [notes, setNotes] = useState(finding.remediation_notes ?? "");
  const [verificationNotes, setVerificationNotes] = useState(
    finding.verification_notes ?? "",
  );
  const [verifier, setVerifier] = useState(finding.verified_by ?? "");
  const mutation = useMutation({
    mutationFn: (body: FindingRemediationUpdate) =>
      updateFindingRemediation(finding.id, body),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["findings", finding.investigation_id],
        }),
        queryClient.invalidateQueries({
          queryKey: ["timeline", finding.investigation_id],
        }),
        queryClient.invalidateQueries({
          queryKey: ["reports", finding.investigation_id],
        }),
      ]);
    },
  });

  return (
    <div className="rounded-md border border-raven-border bg-raven-bg/50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs uppercase tracking-wide">Remediation workflow</p>
        <span className="rounded border border-raven-border px-2 py-1 text-xs capitalize text-raven-text">
          {labelForOption(finding.remediation_status)}
        </span>
      </div>
      <div className="mt-2 grid gap-2 text-xs">
        <p>
          Owner:{" "}
          {memberLabel(members, finding.remediation_owner) ?? "Unassigned"}
        </p>
        <p>Due: {finding.remediation_due_date ?? "No due date"}</p>
        {finding.verified_at ? (
          <p>Verified {new Date(finding.verified_at).toLocaleString()}</p>
        ) : null}
      </div>
      {canMutate ? (
        <div className="mt-3 grid gap-2">
          <div className="grid gap-2 md:grid-cols-2">
            <select
              value={status}
              onChange={(event) =>
                setStatus(event.target.value as RemediationStatus)
              }
              className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
            >
              {remediationStatuses.map((value) => (
                <option key={value} value={value}>
                  {labelForOption(value)}
                </option>
              ))}
            </select>
            <select
              value={owner}
              onChange={(event) => setOwner(event.target.value)}
              className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
            >
              <option value="">Unassigned owner</option>
              {members
                .filter((member) => member.role !== "viewer")
                .map((member) => (
                  <option key={member.id} value={member.user_id}>
                    {member.username} ({member.role})
                  </option>
                ))}
            </select>
            <input
              type="date"
              value={dueDate}
              onChange={(event) => setDueDate(event.target.value)}
              className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
            />
            <select
              value={verifier}
              onChange={(event) => setVerifier(event.target.value)}
              className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
            >
              <option value="">No verifier</option>
              {members
                .filter((member) => member.role !== "viewer")
                .map((member) => (
                  <option key={member.id} value={member.user_id}>
                    {member.username} ({member.role})
                  </option>
                ))}
            </select>
          </div>
          <textarea
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            rows={2}
            placeholder="Remediation or accepted-risk notes"
            className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text outline-none focus:border-raven-violet"
          />
          <textarea
            value={verificationNotes}
            onChange={(event) => setVerificationNotes(event.target.value)}
            rows={2}
            placeholder="Verification notes"
            className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text outline-none focus:border-raven-violet"
          />
          <button
            type="button"
            disabled={mutation.isPending}
            onClick={() =>
              mutation.mutate({
                remediation_status: status,
                remediation_owner: owner || null,
                remediation_due_date: dueDate || null,
                remediation_notes: notes || null,
                verification_notes: verificationNotes || null,
                verified_by: verifier || null,
              })
            }
            className="inline-flex items-center justify-center gap-2 rounded-md bg-raven-violet px-3 py-2 text-sm text-white disabled:opacity-50"
          >
            {mutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : null}
            Update remediation
          </button>
          {mutation.isError ? (
            <p className="whitespace-pre-line text-xs text-rose-200">
              {mutation.error.message}
            </p>
          ) : null}
          {mutation.isSuccess ? (
            <p className="text-xs text-emerald-200">Remediation updated.</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function RecommendedPlaybooks({
  finding,
  canMutate,
}: {
  finding: Finding;
  canMutate: boolean;
}): JSX.Element {
  const queryClient = useQueryClient();
  const recommendations = useQuery({
    queryKey: ["finding-playbooks", finding.id],
    queryFn: () => listFindingPlaybooks(finding.id),
  });
  const start = useMutation({
    mutationFn: (playbookId: string) =>
      startFindingPlaybook(finding.id, playbookId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["playbook-runs", finding.investigation_id],
        }),
        queryClient.invalidateQueries({
          queryKey: ["timeline", finding.investigation_id],
        }),
      ]);
    },
  });

  return (
    <div className="rounded-md border border-raven-border bg-raven-bg/50 p-3">
      <div className="flex items-center gap-2">
        <BookOpenCheck className="h-4 w-4 text-raven-cyan" aria-hidden="true" />
        <p className="text-xs uppercase tracking-wide">
          Recommended defensive playbooks
        </p>
      </div>
      {recommendations.isLoading ? (
        <p className="mt-2 text-xs">Loading recommendations...</p>
      ) : recommendations.isError ? (
        <p className="mt-2 whitespace-pre-line text-xs text-rose-200">
          {recommendations.error.message}
        </p>
      ) : recommendations.data?.length ? (
        <div className="mt-3 space-y-2">
          {recommendations.data.map((item) => (
            <div
              key={item.playbook.id}
              className="rounded border border-raven-border p-3"
            >
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-sm font-medium text-raven-text">
                    {item.playbook.name}
                  </p>
                  <p className="mt-1 text-xs leading-5">{item.reason}</p>
                  <p className="mt-1 text-xs text-raven-cyan">
                    {item.playbook.framework ?? "Defensive workflow"} ·{" "}
                    {item.playbook.steps.length} steps
                  </p>
                </div>
                {canMutate ? (
                  <button
                    type="button"
                    disabled={start.isPending}
                    onClick={() => start.mutate(item.playbook.id)}
                    className="rounded-md border border-raven-violet px-3 py-2 text-xs text-raven-text hover:bg-raven-violet disabled:opacity-50"
                  >
                    Start playbook
                  </button>
                ) : null}
              </div>
            </div>
          ))}
          {start.isError ? (
            <p className="whitespace-pre-line text-xs text-rose-200">
              {start.error.message}
            </p>
          ) : null}
          {start.isSuccess ? (
            <p className="text-xs text-emerald-200">
              Playbook run is ready in the Playbooks tab.
            </p>
          ) : null}
        </div>
      ) : (
        <p className="mt-2 text-xs">
          No deterministic playbook mapping is available for this finding.
        </p>
      )}
    </div>
  );
}

function memberLabel(
  members: InvestigationMember[],
  userId: string | null,
): string | null {
  if (!userId) {
    return null;
  }
  const member = members.find((item) => item.user_id === userId);
  return member ? `${member.username} (${member.role})` : userId;
}

function BulletList({
  values,
  empty,
}: {
  values: string[];
  empty: string;
}): JSX.Element {
  if (!values.length) {
    return <p className="mt-2 text-xs text-raven-muted">{empty}</p>;
  }
  return (
    <ul className="mt-2 space-y-1 text-xs leading-5 text-raven-muted">
      {values.map((value) => (
        <li key={value}>- {value}</li>
      ))}
    </ul>
  );
}

function EvidenceCard({ evidence }: { evidence: FindingEvidence }): JSX.Element {
  const citations = [
    evidence.recon_entity_id ? `recon:${evidence.recon_entity_id}` : null,
    evidence.threat_finding_id ? `threat:${evidence.threat_finding_id}` : null,
  ].filter((item): item is string => item !== null);

  return (
    <div className="rounded-md border border-raven-border bg-raven-bg/60 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium">{evidence.evidence_type}</p>
        <span className="rounded border border-raven-border px-2 py-0.5 text-xs text-raven-cyan">
          {evidence.source}
        </span>
      </div>
      <p className="mt-2 text-sm leading-6 text-raven-muted">
        {evidence.description}
      </p>
      {citations.length ? (
        <div className="mt-3">
          <ChipList values={citations} empty="" />
        </div>
      ) : null}
    </div>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}): JSX.Element {
  return (
    <label className="flex items-center gap-2 rounded-md border border-raven-border bg-raven-panel px-3 py-2 text-sm text-raven-muted">
      <span>{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="bg-transparent text-raven-text outline-none"
      >
        {options.map((item) => (
          <option key={item} value={item}>
            {labelForOption(item)}
          </option>
        ))}
      </select>
    </label>
  );
}

function Metric({ label, value }: { label: string; value: string | number }): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2">
      <p className="text-xs uppercase tracking-wide">{label}</p>
      <LongValue value={String(value)} className="mt-1" maxLength={40} />
    </div>
  );
}

function ChipList({
  values,
  empty,
}: {
  values: string[];
  empty: string;
}): JSX.Element {
  if (!values.length) {
    return (
      <div className="mt-2 flex items-center gap-2 text-xs text-raven-muted">
        <SearchX className="h-3.5 w-3.5" aria-hidden="true" />
        {empty}
      </div>
    );
  }
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {values.map((value) => (
        <div
          key={value}
          className="max-w-full rounded border border-raven-border px-2 py-1 text-xs text-raven-muted"
          title={value}
        >
          <LongValue value={value} maxLength={42} />
        </div>
      ))}
    </div>
  );
}

function findingTargets(finding: Finding): string[] {
  const values = new Set<string>();
  for (const evidence of finding.evidence) {
    for (const key of [
      "target",
      "target_value",
      "value",
      "domain",
      "ip",
      "url",
      "host",
      "hostname",
    ]) {
      const raw = evidence.data[key];
      if (typeof raw === "string" && raw.trim()) {
        values.add(raw.trim());
      }
    }
  }
  return Array.from(values);
}

function labelForOption(value: string): string {
  if (value === "all") {
    return "All";
  }
  if (value === "severity") {
    return "Highest severity";
  }
  return value.replace(/_/g, " ");
}
