import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { InvestigationTabs } from "../components/InvestigationTabs";
import { PageHeader } from "../components/PageHeader";
import { SeverityBadge } from "../components/SeverityBadge";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { getTimeline, listInvestigationMembers } from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import type { Severity, TimelineEvent } from "../types";

export function TimelinePage(): JSX.Element {
  const investigationId = useInvestigationId();
  const [source, setSource] = useState("all");
  const [eventType, setEventType] = useState("all");
  const [analystId, setAnalystId] = useState("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const timeline = useQuery({
    queryKey: [
      "timeline",
      investigationId,
      eventType,
      analystId,
      startDate,
      endDate,
    ],
    queryFn: () =>
      getTimeline(investigationId, {
        event_type: eventType === "all" ? undefined : eventType,
        analyst_id: analystId === "all" ? undefined : analystId,
        start_date: startDate
          ? new Date(`${startDate}T00:00:00Z`).toISOString()
          : undefined,
        end_date: endDate
          ? new Date(`${endDate}T23:59:59Z`).toISOString()
          : undefined,
      }),
  });
  const members = useQuery({
    queryKey: ["members", investigationId],
    queryFn: () => listInvestigationMembers(investigationId),
  });

  const sources = useMemo(() => {
    const unique = new Set((timeline.data?.events ?? []).map((event) => event.source));
    return ["all", ...Array.from(unique).sort()];
  }, [timeline.data?.events]);
  const eventTypes = useMemo(() => {
    const unique = new Set(
      (timeline.data?.events ?? []).map((event) => event.event_type),
    );
    return ["all", ...Array.from(unique).sort()];
  }, [timeline.data?.events]);
  const filtered = useMemo(() => {
    const events = timeline.data?.events ?? [];
    return source === "all"
      ? events
      : events.filter((event) => event.source === source);
  }, [source, timeline.data?.events]);
  const grouped = useMemo(() => groupTimelineEvents(filtered), [filtered]);

  if (timeline.isLoading) {
    return <LoadingBlock label="Loading timeline" />;
  }
  if (timeline.isError) {
    return <ErrorBlock message={timeline.error} />;
  }

  return (
    <>
      <PageHeader title="Timeline" eyebrow="Investigation activity" />
      <InvestigationTabs />

      <section className="mb-5 flex min-w-0 flex-wrap gap-2 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
        <select
          value={source}
          onChange={(event) => setSource(event.target.value)}
          className="min-w-0 rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
        >
          {sources.map((item) => (
            <option key={item} value={item}>
              {item === "all" ? "All sources" : item}
            </option>
          ))}
        </select>
        <select
          value={eventType}
          onChange={(event) => setEventType(event.target.value)}
          className="min-w-0 rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
        >
          {eventTypes.map((item) => (
            <option key={item} value={item}>
              {item === "all" ? "All event types" : item.replace(/_/g, " ")}
            </option>
          ))}
        </select>
        <select
          value={analystId}
          onChange={(event) => setAnalystId(event.target.value)}
          className="min-w-0 rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
        >
          <option value="all">All analysts</option>
          {(members.data ?? []).map((member) => (
            <option key={member.id} value={member.user_id}>
              {member.username}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={startDate}
          onChange={(event) => setStartDate(event.target.value)}
          aria-label="Timeline start date"
          className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
        />
        <input
          type="date"
          value={endDate}
          onChange={(event) => setEndDate(event.target.value)}
          aria-label="Timeline end date"
          className="rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-sm text-raven-text"
        />
      </section>

      {filtered.length ? (
        <div className="space-y-4">
          {grouped.map((group, index) => (
            <details
              key={group.key}
              open={index === 0}
              className="min-w-0 overflow-hidden rounded-lg border border-raven-border bg-raven-panel/70"
            >
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 bg-raven-panelSoft px-4 py-3">
                <span className="font-semibold">{group.label}</span>
                <span className="rounded border border-raven-border px-2 py-1 text-xs text-raven-muted">
                  {group.events.length} events
                </span>
              </summary>
              <div className="relative min-w-0 space-y-4 p-4 before:absolute before:left-7 before:top-6 before:h-[calc(100%-3rem)] before:w-px before:bg-raven-border">
                {group.events.map((event) => (
                  <article key={event.id} className="relative min-w-0 pl-10">
                    <div className="absolute left-0 top-1 h-6 w-6 rounded-full border border-raven-violet bg-raven-bg" />
                    <div className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
                      <div className="flex min-w-0 flex-col gap-3 md:flex-row md:items-start md:justify-between">
                        <div className="min-w-0">
                          <p className="break-words text-xs uppercase tracking-wide text-raven-muted">
                            {new Date(event.timestamp).toLocaleString()} |{" "}
                            {event.source}
                          </p>
                          <h2 className="mt-1 break-words font-semibold">
                            {event.title}
                          </h2>
                        </div>
                        <SeverityBadge severity={event.severity as Severity} />
                      </div>
                      <p className="mt-3 break-words text-sm leading-6 text-raven-muted">
                        {event.summary}
                      </p>
                      <p className="mt-3 break-words text-xs text-raven-muted">
                        Confidence {event.confidence}% | {event.event_type}
                      </p>
                    </div>
                  </article>
                ))}
              </div>
            </details>
          ))}
        </div>
      ) : (
        <EmptyBlock
          title="No timeline events"
          message="The immutable timeline summarizes investigation, evidence, workflow, and analyst activity."
          nextStep="Clear the filter or perform an authorized workflow action."
        />
      )}
    </>
  );
}

const timelineStages = [
  "intake",
  "scoping",
  "evidence_collection",
  "analysis",
  "remediation",
  "reporting",
] as const;

function groupTimelineEvents(
  events: TimelineEvent[],
): Array<{ key: string; label: string; events: TimelineEvent[] }> {
  const grouped = new Map<string, TimelineEvent[]>(
    timelineStages.map((stage) => [stage, []]),
  );
  events.forEach((event) => {
    const stage = timelineStageForEvent(event);
    grouped.get(stage)?.push(event);
  });
  return timelineStages
    .map((stage) => ({
      key: stage,
      label:
        stage === "evidence_collection"
          ? "Evidence Collection"
          : stage.replace(/_/g, " ").replace(/\b\w/g, (value) =>
              value.toUpperCase(),
            ),
      events: grouped.get(stage) ?? [],
    }))
    .filter((group) => group.events.length > 0);
}

function timelineStageForEvent(
  event: TimelineEvent,
): (typeof timelineStages)[number] {
  const value = `${event.event_type} ${event.source}`.toLowerCase();
  if (/report|export|summary/.test(value)) {
    return "reporting";
  }
  if (/reeedi|task|playbook|verified|validation|risk.accepted/.test(value)) {
    return "remediation";
  }
  if (/finding|analysis|knowledge|correlation|review/.test(value)) {
    return "analysis";
  }
  if (/recon|evidence|threat|entity|bookmark|certificate|dns/.test(value)) {
    return "evidence_collection";
  }
  if (/target|scope|authorization|member|assign|owner|handoff/.test(value)) {
    return "scoping";
  }
  return "intake";
}
