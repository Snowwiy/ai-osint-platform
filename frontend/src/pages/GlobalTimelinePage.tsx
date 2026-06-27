import { Clock3, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { LongValue } from "../components/LongValue";
import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import {
  getAnalystWorkload,
  getDashboardTimeline,
  getInvestigationQueue,
} from "../lib/api";

const eventTypes = [
  "recon.executed",
  "findings.generated",
  "finding.remediation_updated",
  "finding.verified",
  "playbook.started",
  "playbook.completed",
  "note.created",
  "bookmark.created",
  "report.downloaded",
  "investigation.bulk_update",
  "investigation.pinned",
];

export function GlobalTimelinePage(): JSX.Element {
  const [actorId, setActorId] = useState("");
  const [investigationId, setInvestigationId] = useState("");
  const [eventType, setEventType] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const timeline = useQuery({
    queryKey: [
      "dashboard-timeline",
      actorId,
      investigationId,
      eventType,
      startDate,
      endDate,
    ],
    queryFn: () =>
      getDashboardTimeline({
        actor_id: actorId || undefined,
        investigation_id: investigationId || undefined,
        event_type: eventType || undefined,
        start_date: startDate ? new Date(startDate).toISOString() : undefined,
        end_date: endDate ? new Date(endDate).toISOString() : undefined,
        limit: 200,
      }),
  });
  const analysts = useQuery({
    queryKey: ["analyst-workload"],
    queryFn: getAnalystWorkload,
  });
  const investigations = useQuery({
    queryKey: ["investigation-queue", "timeline-filter"],
    queryFn: () => getInvestigationQueue({ limit: 100, sort: "newest" }),
  });

  if (timeline.isLoading) {
    return <LoadingBlock label="Loading global timeline" />;
  }
  if (timeline.isError) {
    return <ErrorBlock message={timeline.error} />;
  }
  const timelineItems = timeline.data?.items ?? [];
  const analystItems = analysts.data?.items ?? [];
  const investigationItems = investigations.data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Global Timeline"
        eyebrow="Cross-investigation activity"
        actions={
          <button
            type="button"
            onClick={() => void timeline.refetch()}
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </button>
        }
      />
      <section className="mb-5 grid gap-3 rounded-lg border border-raven-border bg-raven-panel/85 p-4 md:grid-cols-2 xl:grid-cols-5">
        <SelectFilter
          label="Analyst"
          value={actorId}
          onChange={setActorId}
          options={analystItems.map((item) => ({
            value: item.user_id,
            label: item.username,
          }))}
        />
        <SelectFilter
          label="Investigation"
          value={investigationId}
          onChange={setInvestigationId}
          options={investigationItems.map((item) => ({
            value: item.id,
            label: item.title,
          }))}
        />
        <SelectFilter
          label="Event type"
          value={eventType}
          onChange={setEventType}
          options={eventTypes.map((item) => ({ value: item, label: item }))}
        />
        <DateFilter label="Start" value={startDate} onChange={setStartDate} />
        <DateFilter label="End" value={endDate} onChange={setEndDate} />
      </section>

      {timelineItems.length ? (
        <div className="space-y-3">
          {timelineItems.map((event) => (
            <article
              key={event.id}
              className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-3">
                  <Clock3 className="mt-1 h-4 w-4 shrink-0 text-raven-cyan" />
                  <div className="min-w-0">
                    <p className="break-words font-medium">
                      {event.event_type.replace(/_/g, " ")}
                    </p>
                    <p className="mt-1 text-sm text-raven-muted">
                      {event.actor_name ?? "System"} |{" "}
                      {event.resource_type ?? "resource"}
                    </p>
                  </div>
                </div>
                <time className="text-xs text-raven-muted">
                  {new Date(event.timestamp).toLocaleString()}
                </time>
              </div>
              {event.investigation_id ? (
                <Link
                  to={`/investigations/${event.investigation_id}`}
                  className="mt-3 block text-sm text-raven-cyan"
                >
                  {event.investigation_title ?? event.investigation_id}
                </Link>
              ) : null}
              {event.resource_id ? (
                <div className="mt-3">
                  <LongValue value={event.resource_id} label="Resource ID" />
                </div>
              ) : null}
              {Object.keys(event.metadata).length ? (
                <details className="mt-3 rounded-md border border-raven-border bg-raven-panelSoft p-3">
                  <summary className="cursor-pointer text-sm text-raven-muted">
                    Metadata
                  </summary>
                  <pre className="mt-3 overflow-x-auto whitespace-pre-wrap break-all text-xs text-raven-muted">
                    {JSON.stringify(event.metadata, null, 2)}
                  </pre>
                </details>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <EmptyBlock message="No activity matches the selected timeline filters." />
      )}
    </>
  );
}

function SelectFilter({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}): JSX.Element {
  return (
    <label className="text-xs text-raven-muted">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
      >
        <option value="">All</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function DateFilter({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}): JSX.Element {
  return (
    <label className="text-xs text-raven-muted">
      {label}
      <input
        type="datetime-local"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
      />
    </label>
  );
}
