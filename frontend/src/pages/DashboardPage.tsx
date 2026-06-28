import {
  Activity,
  AlertTriangle,
  Bell,
  CheckCircle2,
  Clock3,
  FileText,
  FolderKanban,
  ListChecks,
  Pin,
  RefreshCw,
  Search,
  ShieldAlert,
  StickyNote,
  UserPlus,
  UsersRound,
  Wrench,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { StatCard } from "../components/StatCard";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import {
  getDashboardOverview,
  getDashboardHighlights,
  getDashboardTriage,
  getExecutiveDashboard,
  getNotificationUnreadCount,
  setInvestigationPinned,
} from "../lib/api";
import {
  readRecentInvestigations,
  type RecentInvestigation,
} from "../lib/recentInvestigations";
import type {
  DashboardHighlightItem,
  DashboardOverviewResponse,
  DashboardOperationsInvestigation,
  ExecutiveDashboardResponse,
  OperationsSignal,
  Severity,
} from "../types";

const severityOrder: Severity[] = ["critical", "high", "medium", "low", "info"];

function safeArray<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

function safeNumber(value: number | null | undefined): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function severityCounts(
  value: Partial<Record<Severity, number>> | null | undefined,
): Record<Severity, number> {
  return severityOrder.reduce(
    (current, severity) => ({
      ...current,
      [severity]: safeNumber(value?.[severity]),
    }),
    {} as Record<Severity, number>,
  );
}

function normalizeDashboardOverview(
  data: DashboardOverviewResponse,
): DashboardOverviewResponse {
  const investigations = data.investigations ?? {
    total: 0,
    active: 0,
    archived: 0,
    urgent: 0,
    overdue: 0,
  };
  const findings = data.findings ?? {
    total: 0,
    unresolved: 0,
    by_severity: severityCounts(null),
  };
  const remediation = data.remediation ?? {
    open_tasks: 0,
    overdue_tasks: 0,
    blocked_tasks: 0,
    completed_tasks: 0,
    completion_percent: 0,
  };
  const analystActivity = data.analyst_activity ?? {
    recent_actions: 0,
    investigations_touched: 0,
    notes_created: 0,
    remediation_completed: 0,
  };
  const infrastructureSignals = data.infrastructure_signals ?? {
    recurring_technologies: [],
    repeated_findings: [],
    recurring_domains: [],
    recurring_ips: [],
  };
  return {
    generated_at: data.generated_at ?? new Date().toISOString(),
    investigations: {
      total: safeNumber(investigations.total),
      active: safeNumber(investigations.active),
      archived: safeNumber(investigations.archived),
      urgent: safeNumber(investigations.urgent),
      overdue: safeNumber(investigations.overdue),
    },
    findings: {
      total: safeNumber(findings.total),
      unresolved: safeNumber(findings.unresolved),
      by_severity: severityCounts(findings.by_severity),
    },
    remediation: {
      open_tasks: safeNumber(remediation.open_tasks),
      overdue_tasks: safeNumber(remediation.overdue_tasks),
      blocked_tasks: safeNumber(remediation.blocked_tasks),
      completed_tasks: safeNumber(remediation.completed_tasks),
      completion_percent: safeNumber(remediation.completion_percent),
    },
    analyst_activity: {
      recent_actions: safeNumber(analystActivity.recent_actions),
      investigations_touched: safeNumber(analystActivity.investigations_touched),
      notes_created: safeNumber(analystActivity.notes_created),
      remediation_completed: safeNumber(analystActivity.remediation_completed),
    },
    infrastructure_signals: {
      recurring_technologies: safeArray(
        infrastructureSignals.recurring_technologies,
      ),
      repeated_findings: safeArray(infrastructureSignals.repeated_findings),
      recurring_domains: safeArray(infrastructureSignals.recurring_domains),
      recurring_ips: safeArray(infrastructureSignals.recurring_ips),
    },
    pinned_investigations: safeArray(data.pinned_investigations),
    recent_investigations: safeArray(data.recent_investigations),
  };
}

export function DashboardPage(): JSX.Element {
  const queryClient = useQueryClient();
  const overview = useQuery({
    queryKey: ["dashboard-overview"],
    queryFn: getDashboardOverview,
    staleTime: 30_000,
  });
  const triage = useQuery({
    queryKey: ["dashboard-triage"],
    queryFn: getDashboardTriage,
    staleTime: 30_000,
  });
  const highlights = useQuery({
    queryKey: ["dashboard-highlights"],
    queryFn: getDashboardHighlights,
    staleTime: 30_000,
  });
  const executive = useQuery({
    queryKey: ["dashboard-executive"],
    queryFn: getExecutiveDashboard,
    staleTime: 30_000,
  });
  const notifications = useQuery({
    queryKey: ["dashboard-notifications"],
    queryFn: getNotificationUnreadCount,
    staleTime: 30_000,
    retry: 1,
  });
  const pinMutation = useMutation({
    mutationFn: ({
      investigationId,
      pinned,
    }: {
      investigationId: string;
      pinned: boolean;
    }) => setInvestigationPinned(investigationId, pinned),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] });
      await queryClient.invalidateQueries({ queryKey: ["investigation-queue"] });
    },
  });

  if (overview.isLoading) {
    return <LoadingBlock label="Loading operations dashboard" />;
  }
  if (overview.isError) {
    return <ErrorBlock message={overview.error} />;
  }
  if (!overview.data) {
    return (
      <EmptyBlock
        title="No dashboard activity"
        message="The dashboard summarizes accessible investigations, findings, targets, reports, and recent analyst activity."
        nextStep="Create an investigation to define scope and authorization."
      />
    );
  }

  const data = normalizeDashboardOverview(overview.data);
  const highCritical =
    data.findings.by_severity.critical + data.findings.by_severity.high;
  const focusInvestigation =
    data.pinned_investigations[0] ?? data.recent_investigations[0];

  return (
    <>
      <PageHeader
        title="Operations Dashboard"
        eyebrow="Multi-investigation posture"
        actions={
          <button
            type="button"
            onClick={() => {
              void overview.refetch();
              void triage.refetch();
              void highlights.refetch();
              void executive.refetch();
              void notifications.refetch();
            }}
            disabled={overview.isFetching || triage.isFetching}
            className="inline-flex items-center gap-2 rounded-md border border-raven-border px-3 py-2 text-sm text-raven-text hover:border-raven-violet disabled:opacity-60"
          >
            <RefreshCw
              className={[
                "h-4 w-4",
                overview.isFetching || triage.isFetching ? "animate-spin" : "",
              ].join(" ")}
              aria-hidden="true"
            />
            Refresh
          </button>
        }
      />

      <div className="-mt-3 mb-5 flex flex-wrap items-center justify-between gap-3 text-sm text-raven-muted">
        <span>Last updated {formatDateTime(data.generated_at)}</span>
        <nav className="flex flex-wrap gap-2">
          <QuickLink to="/operations/queue" label="Investigation queue" />
          <QuickLink to="/operations/analysts" label="Analyst workload" />
          <QuickLink to="/operations/timeline" label="Global timeline" />
          <QuickLink to="/notifications" label="Activity inbox" />
        </nav>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-7">
        <StatCard
          label="Active investigations"
          value={data.investigations.active}
          detail={`${data.investigations.total} accessible`}
          icon={<FolderKanban className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Urgent"
          value={data.investigations.urgent}
          detail={`${data.investigations.overdue} overdue cases`}
          icon={<AlertTriangle className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Findings"
          value={data.findings.total}
          detail={`${data.findings.unresolved} unresolved`}
          icon={<ShieldAlert className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="High/Critical"
          value={highCritical}
          detail="Priority defensive review"
          icon={<Activity className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Open tasks"
          value={data.remediation.open_tasks}
          detail={`${data.remediation.overdue_tasks} overdue`}
          icon={<ListChecks className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Remediation"
          value={`${data.remediation.completion_percent}%`}
          detail={`${data.remediation.blocked_tasks} blocked`}
          icon={<CheckCircle2 className="h-5 w-5" aria-hidden="true" />}
        />
        <StatCard
          label="Inbox"
          value={notifications.data?.unread ?? 0}
          detail="Workflow alerts"
          icon={<Bell className="h-5 w-5" aria-hidden="true" />}
        />
      </div>

      <ExecutivePosture
        data={executive.data}
        isLoading={executive.isLoading}
        error={executive.error}
      />

      <QuickActions investigation={focusInvestigation} />

      <OperationalHighlights data={highlights.data} />

      <ContinueWorking items={readRecentInvestigations()} />

      {data.investigations.total === 0 ? (
        <section className="mt-8">
          <EmptyBlock
            title="No accessible investigations"
            message="Recent authorized investigations will appear here when you own or join a case."
            nextStep="Create an investigation or ask a case owner to add you."
          />
        </section>
      ) : (
        <>
          <section className="mt-8 grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
            <InvestigationList
              title="Pinned investigations"
              items={data.pinned_investigations}
              empty="Pin priority cases from the queue for quick access."
              onPin={(item) =>
                pinMutation.mutate({
                  investigationId: item.id,
                  pinned: !item.pinned,
                })
              }
            />
            <TriagePanel
              items={triage.data?.items?.slice(0, 6) ?? []}
              isLoading={triage.isLoading}
            />
          </section>

          <section className="mt-6 grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
            <InvestigationList
              title="Recent investigations"
              items={data.recent_investigations}
              empty="No recent investigation activity is stored."
              onPin={(item) =>
                pinMutation.mutate({
                  investigationId: item.id,
                  pinned: !item.pinned,
                })
              }
            />
            <AnalystActivity data={data.analyst_activity} />
          </section>

          <section className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <SignalPanel
              title="Recurring technologies"
              items={data.infrastructure_signals.recurring_technologies}
            />
            <SignalPanel
              title="Repeated findings"
              items={data.infrastructure_signals.repeated_findings}
            />
            <SignalPanel
              title="Recurring domains"
              items={data.infrastructure_signals.recurring_domains}
            />
            <SignalPanel
              title="Recurring IPs"
              items={data.infrastructure_signals.recurring_ips}
            />
          </section>

          <section className="mt-6 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
            <h2 className="text-lg font-semibold">Findings distribution</h2>
            <div className="mt-4 grid gap-3 sm:grid-cols-5">
              {severityOrder.map((severity) => (
                <div
                  key={severity}
                  className="rounded-md border border-raven-border bg-raven-panelSoft p-3"
                >
                  <p className="text-xs capitalize text-raven-muted">{severity}</p>
                  <p className="mt-1 text-2xl font-semibold">
                    {data.findings.by_severity[severity]}
                  </p>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </>
  );
}

function ExecutivePosture({
  data,
  isLoading,
  error,
}: {
  data: ExecutiveDashboardResponse | undefined;
  isLoading: boolean;
  error: Error | null;
}): JSX.Element {
  if (isLoading) {
    return (
      <section className="mt-6">
        <LoadingBlock label="Loading executive posture" />
      </section>
    );
  }
  if (error || !data) {
    return (
      <section className="mt-6 rounded-lg border border-amber-400/30 bg-amber-500/10 p-4">
        <p className="text-sm text-amber-100">
          Executive posture is temporarily unavailable. Operational dashboard
          data remains available.
        </p>
      </section>
    );
  }
  const repeatedTechnologies = safeArray(data.repeated_technologies);
  const repeatedFindings = safeArray(data.repeated_findings);
  const analystWorkload = safeArray(data.analyst_workload);
  const detection = data.detection_visibility ?? {
    mapped_findings: 0,
    missing_coverage: 0,
    coverage_percent: 0,
    recurring_defensive_gaps: [],
  };
  const knowledge = data.knowledge_usage ?? {
    most_referenced_frameworks: [],
    common_defensive_concerns: [],
  };
  const threat = data.threat_intelligence ?? {
    recurring_infrastructure: 0,
    recurring_indicators: 0,
    repeated_iocs: 0,
    active_campaigns: 0,
    attack_coverage: 0,
    investigations_sharing_entities: 0,
    high_confidence_iocs: 0,
    high_confidence_observations: 0,
    unresolved_correlated_findings: 0,
    recent_intelligence_activity: [],
  };
  const recentIntelligence = safeArray(threat.recent_intelligence_activity);
  return (
    <section className="mt-6 min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-raven-cyan">
            Executive posture
          </p>
          <h2 className="mt-1 text-lg font-semibold">
            Defensive portfolio intelligence
          </h2>
        </div>
        <span className="text-xs text-raven-muted">
          Updated {data.generated_at ? formatDateTime(data.generated_at) : "recently"}
        </span>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        <MiniMetric
          label="Active cases"
          value={safeNumber(data.active_investigations)}
        />
        <MiniMetric
          label="High risk"
          value={safeNumber(data.high_risk_investigations)}
        />
        <MiniMetric
          label="Overdue"
          value={safeNumber(data.overdue_remediation)}
        />
        <MiniMetric
          label="Reporting ready"
          value={safeNumber(data.reporting_ready_investigations)}
        />
        <MiniMetric
          label="No remediation"
          value={safeNumber(data.investigations_without_remediation)}
        />
        <MiniMetric
          label="Missing reports"
          value={safeNumber(data.investigations_missing_reports)}
        />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <ExecutiveSignalList
          title="Repeated technologies"
          items={repeatedTechnologies}
        />
        <ExecutiveSignalList
          title="Repeated findings"
          items={repeatedFindings}
        />
        <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
          <p className="text-sm font-semibold">Analyst workload</p>
          {analystWorkload.length ? (
            <div className="mt-3 space-y-3">
              {analystWorkload.slice(0, 4).map((item) => (
                <div key={item.user_id} className="min-w-0">
                  <p className="break-words text-sm">{item.analyst_name}</p>
                  <p className="mt-1 text-xs text-raven-muted">
                    {item.investigations} cases | {item.unresolved_findings}{" "}
                    unresolved | {item.overdue_ownership} overdue
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-sm text-raven-muted">
              No analyst assignments are available.
            </p>
          )}
        </div>
      </div>
      <div className="mt-4">
        <p className="text-xs uppercase tracking-wide text-raven-cyan">
          Detection intelligence and knowledge maturity
        </p>
        <div className="mt-3 grid gap-4 lg:grid-cols-4">
          <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
            <p className="text-sm font-semibold">Detection visibility</p>
            <p className="mt-3 text-3xl font-semibold">
              {safeNumber(detection.coverage_percent)}%
            </p>
            <p className="mt-2 text-xs leading-5 text-raven-muted">
              {safeNumber(detection.mapped_findings)} mapped findings |{" "}
              {safeNumber(detection.missing_coverage)} missing coverage
            </p>
          </div>
          <ExecutiveSignalList
            title="Recurring defensive gaps"
            items={safeArray(detection.recurring_defensive_gaps)}
          />
          <ExecutiveSignalList
            title="Referenced frameworks"
            items={safeArray(knowledge.most_referenced_frameworks)}
          />
          <ExecutiveSignalList
            title="Common defensive concerns"
            items={safeArray(knowledge.common_defensive_concerns)}
          />
        </div>
      </div>
      <div className="mt-4">
        <p className="text-xs uppercase tracking-wide text-raven-cyan">
          Threat intelligence and IOC correlation
        </p>
        <div className="mt-3 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <MiniMetric
            label="Recurring infrastructure"
            value={safeNumber(threat.recurring_infrastructure)}
          />
          <MiniMetric
            label="Recurring indicators"
            value={safeNumber(threat.recurring_indicators)}
          />
          <MiniMetric
            label="Repeated IOCs"
            value={safeNumber(threat.repeated_iocs)}
          />
          <MiniMetric
            label="Active campaigns"
            value={safeNumber(threat.active_campaigns)}
          />
          <MiniMetric
            label="ATT&CK coverage"
            value={safeNumber(threat.attack_coverage)}
          />
          <MiniMetric
            label="Cases sharing entities"
            value={safeNumber(threat.investigations_sharing_entities)}
          />
          <MiniMetric
            label="High confidence IOCs"
            value={safeNumber(threat.high_confidence_iocs)}
          />
          <MiniMetric
            label="High confidence observations"
            value={safeNumber(threat.high_confidence_observations)}
          />
          <MiniMetric
            label="Unresolved correlations"
            value={safeNumber(threat.unresolved_correlated_findings)}
          />
          <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
            <p className="text-sm font-semibold">Recent intelligence</p>
            {recentIntelligence[0] ? (
              <>
                <p className="mt-2 break-all text-sm text-raven-muted">
                  {recentIntelligence[0].label}
                </p>
                <p className="mt-1 text-xs text-raven-muted">
                  {safeNumber(recentIntelligence[0].count)} observations
                </p>
              </>
            ) : (
              <p className="mt-2 text-sm text-raven-muted">
                No IOC activity stored.
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function ExecutiveSignalList({
  title,
  items,
}: {
  title: string;
  items: Array<{ label: string; count: number }>;
}): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <p className="text-sm font-semibold">{title}</p>
      {items.length ? (
        <div className="mt-3 space-y-3">
          {items.slice(0, 4).map((item) => (
            <div key={item.label} className="flex min-w-0 justify-between gap-3">
              <span className="min-w-0 break-all text-sm text-raven-muted">
                {item.label}
              </span>
              <span className="flex-none text-sm font-medium">{item.count}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-raven-muted">
          No cross-investigation recurrence detected.
        </p>
      )}
    </div>
  );
}

function OperationalHighlights({
  data,
}: {
  data:
    | {
        needs_attention: DashboardHighlightItem[];
        overdue_remediation: DashboardHighlightItem[];
        without_findings: DashboardHighlightItem[];
        recently_archived: DashboardHighlightItem[];
        recent_activity: DashboardHighlightItem[];
      }
    | undefined;
}): JSX.Element {
  const cards = [
    {
      label: "Needs attention",
      items: data?.needs_attention ?? [],
      empty: "No investigations currently need elevated attention.",
    },
    {
      label: "Overdue remediation",
      items: data?.overdue_remediation ?? [],
      empty: "No overdue remediation work is visible.",
    },
    {
      label: "Without findings",
      items: data?.without_findings ?? [],
      empty: "All active investigations have stored findings.",
    },
    {
      label: "Recently archived",
      items: data?.recently_archived ?? [],
      empty: "No investigations were archived recently.",
    },
  ];
  return (
    <section className="mt-6">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Operational highlights</h2>
        <span className="text-xs text-raven-muted">
          Deterministic workspace signals
        </span>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <article
            key={card.label}
            className="min-w-0 rounded-lg border border-raven-border bg-raven-panel/85 p-4"
          >
            <p className="text-sm font-semibold">{card.label}</p>
            {card.items[0] ? (
              <>
                <Link
                  to={`/investigations/${card.items[0].investigation_id}`}
                  className="mt-3 block break-words text-sm text-raven-cyan hover:text-white"
                >
                  {card.items[0].title}
                </Link>
                <p className="mt-2 break-words text-xs leading-5 text-raven-muted">
                  {card.items[0].detail}
                </p>
                {card.items.length > 1 ? (
                  <p className="mt-2 text-xs text-raven-muted">
                    +{card.items.length - 1} more
                  </p>
                ) : null}
              </>
            ) : (
              <p className="mt-3 text-sm text-raven-muted">{card.empty}</p>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

function ContinueWorking({
  items,
}: {
  items: RecentInvestigation[];
}): JSX.Element {
  return (
    <section className="mt-6 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex items-center gap-2">
        <Clock3 className="h-5 w-5 text-raven-cyan" aria-hidden="true" />
        <h2 className="text-lg font-semibold">Continue working</h2>
      </div>
      {items.length ? (
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {items.slice(0, 4).map((item) => (
            <Link
              key={item.id}
              to={`/investigations/${item.id}`}
              className="min-w-0 rounded-md border border-raven-border bg-raven-panelSoft p-3 hover:border-raven-violet"
            >
              <p className="break-words text-sm font-medium">{item.title}</p>
              <p className="mt-2 text-xs capitalize text-raven-muted">
                {item.stage} stage | {item.status}
              </p>
              <p className="mt-1 text-xs text-raven-muted">
                Viewed {formatDateTime(item.viewed_at)}
              </p>
            </Link>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-raven-muted">
          Open an investigation and it will appear here for quick navigation.
        </p>
      )}
    </section>
  );
}

function InvestigationList({
  title,
  items,
  empty,
  onPin,
}: {
  title: string;
  items: DashboardOperationsInvestigation[];
  empty: string;
  onPin: (item: DashboardOperationsInvestigation) => void;
}): JSX.Element {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{title}</h2>
        <Link
          to="/operations/queue"
          className="text-sm text-raven-cyan hover:text-white"
        >
          Open queue
        </Link>
      </div>
      {items.length ? (
        <div className="space-y-3">
          {items.map((item) => (
            <article
              key={item.id}
              className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <Link
                    to={`/investigations/${item.id}`}
                    className="break-words font-semibold hover:text-raven-cyan"
                  >
                    {item.title}
                  </Link>
                  <p className="mt-2 text-sm text-raven-muted">
                    Risk {item.risk_score}/100 | Triage {item.triage_score}/100 |{" "}
                    {item.findings_count} findings
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => onPin(item)}
                  className={[
                    "rounded-md border p-2",
                    item.pinned
                      ? "border-raven-violet bg-raven-violet/20 text-violet-100"
                      : "border-raven-border text-raven-muted hover:text-raven-text",
                  ].join(" ")}
                  title={item.pinned ? "Unpin investigation" : "Pin investigation"}
                >
                  <Pin className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <Badge value={item.status} />
                <Badge value={`${item.priority} priority`} />
                <Badge value={item.triage_category.replace(/_/g, " ")} />
                {item.overdue_tasks ? (
                  <Badge value={`${item.overdue_tasks} overdue tasks`} danger />
                ) : null}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyBlock message={empty} />
      )}
    </section>
  );
}

function QuickActions({
  investigation,
}: {
  investigation: DashboardOperationsInvestigation | undefined;
}): JSX.Element {
  const actions = investigation
    ? [
        {
          label: "Run recon",
          to: `/investigations/${investigation.id}/targets`,
          icon: Search,
        },
        {
          label: "Generate findings",
          to: `/investigations/${investigation.id}/findings`,
          icon: ShieldAlert,
        },
        {
          label: "Generate report",
          to: `/investigations/${investigation.id}/reports`,
          icon: FileText,
        },
        {
          label: "Create note",
          to: `/investigations/${investigation.id}/notes`,
          icon: StickyNote,
        },
        {
          label: "Create remediation",
          to: `/investigations/${investigation.id}/tasks`,
          icon: Wrench,
        },
        {
          label: "Assign analyst",
          to: `/investigations/${investigation.id}/members`,
          icon: UserPlus,
        },
      ]
    : [];

  return (
    <section className="mt-6 rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Quick actions</h2>
          <p className="mt-1 text-sm text-raven-muted">
            {investigation
              ? `Focused on ${investigation.title}`
              : "Pin or open an investigation to enable case actions."}
          </p>
        </div>
        {investigation ? (
          <Link
            to={`/investigations/${investigation.id}`}
            className="text-sm text-raven-cyan hover:text-white"
          >
            Open investigation
          </Link>
        ) : null}
      </div>
      {actions.length ? (
        <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {actions.map(({ label, to, icon: Icon }) => (
            <Link
              key={label}
              to={to}
              className="flex min-h-20 items-center gap-3 rounded-md border border-raven-border bg-raven-panelSoft p-3 text-sm hover:border-raven-violet"
            >
              <Icon
                className="h-4 w-4 shrink-0 text-raven-cyan"
                aria-hidden="true"
              />
              <span>{label}</span>
            </Link>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function TriagePanel({
  items,
  isLoading,
}: {
  items: Array<{
    investigation_id: string;
    title: string;
    score: number;
    category: string;
    reasons: string[];
  }>;
  isLoading: boolean;
}): JSX.Element {
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Quick triage</h2>
        <Link to="/operations/queue" className="text-sm text-raven-cyan">
          Review all
        </Link>
      </div>
      {isLoading ? (
        <p className="mt-4 text-sm text-raven-muted">Calculating deterministic scores.</p>
      ) : items.length ? (
        <div className="mt-4 space-y-3">
          {items.map((item) => (
            <Link
              key={item.investigation_id}
              to={`/investigations/${item.investigation_id}`}
              className="block rounded-md border border-raven-border bg-raven-panelSoft p-3 hover:border-raven-violet"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium">{item.title}</span>
                <span className="text-lg font-semibold">{item.score}</span>
              </div>
              <p className="mt-1 text-xs capitalize text-raven-cyan">
                {item.category.replace(/_/g, " ")}
              </p>
              <p className="mt-2 line-clamp-2 text-sm text-raven-muted">
                {item.reasons.join(" ")}
              </p>
            </Link>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-raven-muted">
          No cases are available for triage.
        </p>
      )}
    </section>
  );
}

function AnalystActivity({
  data,
}: {
  data: DashboardOverviewResponse["analyst_activity"];
}): JSX.Element {
  return (
    <section className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <h2 className="text-lg font-semibold">Analyst activity | 30 days</h2>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <MiniMetric label="Recent actions" value={data.recent_actions} />
        <MiniMetric
          label="Cases touched"
          value={data.investigations_touched}
        />
        <MiniMetric label="Notes created" value={data.notes_created} />
        <MiniMetric
          label="Remediation completed"
          value={data.remediation_completed}
        />
      </div>
      <Link
        to="/operations/analysts"
        className="mt-4 inline-flex items-center gap-2 text-sm text-raven-cyan"
      >
        <UsersRound className="h-4 w-4" aria-hidden="true" />
        View workload
      </Link>
    </section>
  );
}

function SignalPanel({
  title,
  items,
}: {
  title: string;
  items: OperationsSignal[];
}): JSX.Element {
  return (
    <article className="rounded-lg border border-raven-border bg-raven-panel/85 p-4">
      <h2 className="text-sm font-semibold">{title}</h2>
      {items.length ? (
        <div className="mt-4 space-y-3">
          {items.slice(0, 6).map((item) => (
            <div key={item.value} className="min-w-0">
              <p className="break-all text-sm">{item.value}</p>
              <p className="mt-1 text-xs text-raven-muted">
                {item.count} observations | {item.investigation_count} cases
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-raven-muted">
          No cross-investigation recurrence detected.
        </p>
      )}
    </article>
  );
}

function MiniMetric({ label, value }: { label: string; value: number }): JSX.Element {
  return (
    <div className="rounded-md border border-raven-border bg-raven-panelSoft p-3">
      <p className="text-xs text-raven-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function Badge({ value, danger }: { value: string; danger?: boolean }): JSX.Element {
  return (
    <span
      className={[
        "rounded border px-2 py-1 capitalize",
        danger
          ? "border-rose-400/40 bg-rose-500/10 text-rose-100"
          : "border-raven-border text-raven-muted",
      ].join(" ")}
    >
      {value}
    </span>
  );
}

function QuickLink({ to, label }: { to: string; label: string }): JSX.Element {
  return (
    <Link
      to={to}
      className="rounded-md border border-raven-border px-3 py-1.5 text-xs text-raven-muted hover:border-raven-violet hover:text-raven-text"
    >
      {label}
    </Link>
  );
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString();
}
