import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { SeverityBadge } from "../components/SeverityBadge";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { getTimeline } from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import type { Severity } from "../types";

export function TimelinePage(): JSX.Element {
  const investigationId = useInvestigationId();
  const [source, setSource] = useState("all");
  const timeline = useQuery({
    queryKey: ["timeline", investigationId],
    queryFn: () => getTimeline(investigationId),
  });

  const sources = useMemo(() => {
    const unique = new Set(timeline.data?.events.map((event) => event.source) ?? []);
    return ["all", ...Array.from(unique).sort()];
  }, [timeline.data?.events]);

  const filtered = useMemo(() => {
    const events = timeline.data?.events ?? [];
    return source === "all"
      ? events
      : events.filter((event) => event.source === source);
  }, [source, timeline.data?.events]);

  if (timeline.isLoading) {
    return <LoadingBlock label="Loading timeline" />;
  }
  if (timeline.isError) {
    return <ErrorBlock message={timeline.error.message} />;
  }

  return (
    <>
      <PageHeader
        title="Timeline"
        eyebrow="Investigation activity"
        actions={
          <select
            value={source}
            onChange={(event) => setSource(event.target.value)}
            className="rounded-md border border-raven-border bg-raven-panel px-3 py-2 text-sm text-raven-text"
          >
            {sources.map((item) => (
              <option key={item} value={item}>
                {item === "all" ? "All sources" : item}
              </option>
            ))}
          </select>
        }
      />

      {filtered.length ? (
        <div className="relative space-y-4 before:absolute before:left-3 before:top-2 before:h-full before:w-px before:bg-raven-border">
          {filtered.map((event) => (
            <article key={event.id} className="relative pl-10">
              <div className="absolute left-0 top-1 h-6 w-6 rounded-full border border-raven-violet bg-raven-bg" />
              <div className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-raven-muted">
                      {new Date(event.timestamp).toLocaleString()} · {event.source}
                    </p>
                    <h2 className="mt-1 font-semibold">{event.title}</h2>
                  </div>
                  <SeverityBadge severity={event.severity as Severity} />
                </div>
                <p className="mt-3 text-sm leading-6 text-raven-muted">{event.summary}</p>
                <p className="mt-3 text-xs text-raven-muted">
                  Confidence {event.confidence}% · {event.event_type}
                </p>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyBlock message="No timeline events match the current filter." />
      )}
    </>
  );
}

