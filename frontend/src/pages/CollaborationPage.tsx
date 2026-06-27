import {
  AlertTriangle,
  ArrowRightLeft,
  Eye,
  RefreshCw,
  ShieldCheck,
  UserRoundCheck,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { getCollaborationDashboard } from "../lib/api";
import { safeArray, safeDate, safeString } from "../lib/safe";
import type {
  CollaborationDashboardInvestigation,
  CollaborationDashboardResponse,
} from "../types";

export function CollaborationPage(): JSX.Element {
  const dashboard = useQuery({
    queryKey: ["collaboration-dashboard"],
    queryFn: getCollaborationDashboard,
  });

  if (dashboard.isLoading) {
    return <LoadingBlock label="Loading collaboration workspace" />;
  }
  if (dashboard.isError) {
    return <ErrorBlock message={dashboard.error} />;
  }
  if (!dashboard.data) {
    return (
      <EmptyBlock
        title="No collaboration activity"
        message="Ownership changes, assignments, handoffs, escalations, and coordination events appear here."
        nextStep="Open an investigation to assign an analyst or record an operational update."
      />
    );
  }

  const data = dashboard.data;
  const owned = safeArray(data.owned);
  const assigned = safeArray(data.assigned);
  const watching = safeArray(data.watching);
  const needsAttention = safeArray(data.needs_attention);
  return (
    <>
      <PageHeader
        title="Collaboration"
        eyebrow="Operational coordination"
        actions={
          <button
            type="button"
            onClick={() => void dashboard.refetch()}
            disabled={dashboard.isFetching}
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-text hover:border-raven-violet disabled:opacity-60"
          >
            <RefreshCw
              className={[
                "h-4 w-4",
                dashboard.isFetching ? "animate-spin" : "",
              ].join(" ")}
              aria-hidden="true"
            />
            Refresh
          </button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="Owned"
          value={owned.length}
          icon={<ShieldCheck className="h-5 w-5" aria-hidden="true" />}
        />
        <Metric
          label="Assigned"
          value={assigned.length}
          icon={<UserRoundCheck className="h-5 w-5" aria-hidden="true" />}
        />
        <Metric
          label="Watching"
          value={watching.length}
          icon={<Eye className="h-5 w-5" aria-hidden="true" />}
        />
        <Metric
          label="Needs attention"
          value={needsAttention.length}
          icon={<AlertTriangle className="h-5 w-5" aria-hidden="true" />}
        />
      </div>

      <section className="mt-6 grid min-w-0 gap-5 xl:grid-cols-2">
        <InvestigationGroup
          title="Needs Attention"
          items={needsAttention}
          empty="No assigned cases currently require operational attention."
        />
        <RecentCoordination data={data} />
      </section>

      <section className="mt-6 grid min-w-0 gap-5 xl:grid-cols-3">
        <InvestigationGroup
          title="My Investigations"
          items={owned}
          empty="You do not currently own an investigation."
        />
        <InvestigationGroup
          title="Assigned"
          items={assigned}
          empty="No investigations are assigned to you."
        />
        <InvestigationGroup
          title="Watching"
          items={watching}
          empty="You are not watching any investigations."
        />
      </section>
    </>
  );
}

function Metric({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
  icon: JSX.Element;
}): JSX.Element {
  return (
    <article className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex items-center justify-between text-raven-cyan">
        <span className="text-xs uppercase tracking-wide text-raven-muted">
          {label}
        </span>
        {icon}
      </div>
      <p className="mt-3 text-3xl font-semibold">{value}</p>
    </article>
  );
}

function InvestigationGroup({
  title,
  items,
  empty,
}: {
  title: string;
  items: CollaborationDashboardInvestigation[];
  empty: string;
}): JSX.Element {
  const safeItems = safeArray(items);
  return (
    <section className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <h2 className="text-lg font-semibold">{title}</h2>
      {safeItems.length ? (
        <div className="mt-4 space-y-3">
          {safeItems.slice(0, 10).map((item) => (
            <Link
              key={item.id}
              to={`/investigations/${item.id}`}
              className="block min-w-0 rounded-md border border-raven-border bg-raven-panelSoft p-3 hover:border-raven-violet"
            >
              <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
                <span className="min-w-0 break-words font-medium">
                  {item.title}
                </span>
                <span className="rounded border border-raven-border px-2 py-1 text-xs capitalize text-raven-muted">
                  {item.state}
                </span>
              </div>
              <p className="mt-2 text-xs text-raven-muted">
                {item.open_tasks} open tasks | {item.blocked_tasks} blocked |{" "}
                {item.urgent_findings} urgent findings | {item.escalation_count}{" "}
                escalations
              </p>
            </Link>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-raven-muted">{empty}</p>
      )}
    </section>
  );
}

function RecentCoordination({
  data,
}: {
  data: CollaborationDashboardResponse;
}): JSX.Element {
  const events = safeArray(data.recent_coordination);
  return (
    <section className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex items-center gap-2">
        <ArrowRightLeft className="h-5 w-5 text-raven-cyan" aria-hidden="true" />
        <h2 className="text-lg font-semibold">Recent Coordination</h2>
      </div>
      {events.length ? (
        <div className="mt-4 space-y-3">
          {events.slice(0, 12).map((event) => {
            const timestamp = safeDate(event.timestamp);
            const title = safeString(event.investigation_title, "Investigation");
            const action = safeString(event.action, "coordination event");
            return (
              <article
                key={event.id}
                className="min-w-0 border-b border-raven-border pb-3 last:border-0"
              >
                <Link
                  to={`/investigations/${event.investigation_id}`}
                  className="break-words text-sm font-medium hover:text-raven-cyan"
                >
                  {title}
                </Link>
                <p className="mt-1 break-words text-sm capitalize text-raven-muted">
                  {action.replace(/[._]/g, " ")}
                </p>
                <p className="mt-1 text-xs text-raven-muted">
                  {timestamp ? timestamp.toLocaleString() : "Time unavailable"}
                </p>
              </article>
            );
          })}
        </div>
      ) : (
        <p className="mt-4 text-sm text-raven-muted">
          No coordination activity is stored yet.
        </p>
      )}
    </section>
  );
}
