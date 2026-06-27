import { ClipboardCheck, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { StatCard } from "../components/StatCard";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { getReviewBoard } from "../lib/api";
import { safeArray } from "../lib/safe";
import type { ReviewBoardItem } from "../types";

const statusOptions = [
  "",
  "pending_review",
  "changes_requested",
  "pending_approval",
  "validation_pending",
  "approved",
];
const priorityOptions = ["", "urgent", "high", "medium", "low"];
const riskOptions = ["", "critical", "high", "medium", "low", "info"];

export function ReviewBoardPage(): JSX.Element {
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [risk, setRisk] = useState("");
  const [dueDateBefore, setDueDateBefore] = useState("");
  const board = useQuery({
    queryKey: ["review-board", status, priority, risk, dueDateBefore],
    queryFn: () =>
      getReviewBoard({
        status: status || undefined,
        priority: priority || undefined,
        risk: risk || undefined,
        due_date_before: dueDateBefore || undefined,
      }),
    staleTime: 30_000,
  });

  if (board.isLoading) {
    return <LoadingBlock label="Loading review board" />;
  }
  if (board.isError) {
    return <ErrorBlock message={board.error} />;
  }
  const data = board.data;
  const items = safeArray(data?.items);

  return (
    <>
      <PageHeader
        title="Review Board"
        eyebrow="Case review and approval queue"
        actions={
          <button
            type="button"
            onClick={() => void board.refetch()}
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm hover:border-raven-violet"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </button>
        }
      />
      <section className="mb-5 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <p className="max-w-4xl text-sm leading-6 text-raven-muted">
          The review board centralizes case approvals, report approvals,
          remediation validation, change requests, and closure readiness. It is
          analyst-driven and uses only stored platform evidence.
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <FilterSelect
            label="Status"
            value={status}
            options={statusOptions}
            onChange={setStatus}
          />
          <FilterSelect
            label="Priority"
            value={priority}
            options={priorityOptions}
            onChange={setPriority}
          />
          <FilterSelect
            label="Risk"
            value={risk}
            options={riskOptions}
            onChange={setRisk}
          />
          <label className="block text-sm">
            <span className="text-raven-muted">Due before</span>
            <input
              type="date"
              value={dueDateBefore}
              onChange={(event) => setDueDateBefore(event.target.value)}
              className="input-base mt-1"
            />
          </label>
        </div>
      </section>
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard
          label="Case reviews"
          value={data?.pending_case_reviews ?? 0}
          detail="Pending review"
          icon={<ClipboardCheck className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Report approvals"
          value={data?.pending_report_approvals ?? 0}
          detail="Stakeholder-ready"
          icon={<ClipboardCheck className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Validation"
          value={data?.pending_remediation_validations ?? 0}
          detail="Pending remediation review"
          icon={<ClipboardCheck className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Changes requested"
          value={data?.changes_requested ?? 0}
          detail="Needs analyst update"
          icon={<ClipboardCheck className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Ready to close"
          value={data?.ready_for_closure ?? 0}
          detail="Approved cases"
          icon={<ClipboardCheck className="h-5 w-5" aria-hidden="true" />}
        />
      </section>
      <section className="mt-6">
        {items.length ? (
          <div className="grid gap-4 xl:grid-cols-2">
            {items.map((item) => (
              <ReviewBoardCard key={`${item.item_type}:${item.id}`} item={item} />
            ))}
          </div>
        ) : (
          <EmptyBlock
            title="No review work queued"
            message="Cases, reports, and remediation validation items appear here when they need reviewer action."
            nextStep="Submit a case or report for review when the evidence is ready."
          />
        )}
      </section>
    </>
  );
}

function ReviewBoardCard({ item }: { item: ReviewBoardItem }): JSX.Element {
  return (
    <article className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-raven-cyan">
            {formatLabel(item.item_type)}
          </p>
          <h2 className="mt-1 break-words text-lg font-semibold">{item.title}</h2>
        </div>
        <span className="rounded border border-raven-border bg-raven-panelSoft px-2 py-1 text-xs capitalize">
          {formatLabel(item.status)}
        </span>
      </div>
      <p className="mt-3 text-sm leading-6 text-raven-muted">{item.detail}</p>
      <div className="mt-3 flex flex-wrap gap-3 text-xs text-raven-muted">
        <span>Priority: {item.priority}</span>
        <span>Risk: {item.risk}</span>
        {item.due_date ? <span>Due {item.due_date}</span> : null}
        {item.created_at ? <span>Updated {formatDate(item.created_at)}</span> : null}
      </div>
      <Link
        to={`/investigations/${item.investigation_id}`}
        className="mt-4 inline-flex rounded-md border border-raven-border px-3 py-2 text-sm text-raven-cyan hover:border-raven-violet hover:text-white"
      >
        Open {item.investigation_title}
      </Link>
    </article>
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
    <label className="block text-sm">
      <span className="text-raven-muted">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="input-base mt-1"
      >
        {options.map((option) => (
          <option key={option || "all"} value={option}>
            {option ? formatLabel(option) : "All"}
          </option>
        ))}
      </select>
    </label>
  );
}

function formatLabel(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "recently" : date.toLocaleString();
}
