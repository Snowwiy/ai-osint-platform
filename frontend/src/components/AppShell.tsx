import {
  Activity,
  BarChart3,
  Bookmark,
  BrainCircuit,
  BriefcaseBusiness,
  BookOpenCheck,
  Clock3,
  Handshake,
  ClipboardCheck,
  ClipboardList,
  DatabaseZap,
  FileText,
  GitGraph,
  Home,
  ListChecks,
  LogOut,
  Network,
  Radar,
  Search,
  Settings,
  ShieldAlert,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet, useParams } from "react-router-dom";

import { getBackendHealth, getFeatureAvailability } from "../lib/api";
import { useAuth } from "../lib/useAuth";
import type { FeatureFlagSettings, HealthResponse } from "../types";

interface NavigationItem {
  label: string;
  to: string;
  icon: typeof Home;
  feature?: keyof FeatureFlagSettings;
}

interface InvestigationNavigationItem {
  label: string;
  path: string;
  icon: typeof Home;
  feature?: keyof FeatureFlagSettings;
}

const topNav: NavigationItem[] = [
  { label: "Home", to: "/", icon: Home },
  {
    label: "Executive",
    to: "/executive",
    icon: BarChart3,
    feature: "enable_advanced_dashboard",
  },
  {
    label: "Queue",
    to: "/operations/queue",
    icon: ListChecks,
    feature: "enable_advanced_dashboard",
  },
  {
    label: "Workload",
    to: "/operations/analysts",
    icon: UsersRound,
    feature: "enable_advanced_dashboard",
  },
  {
    label: "Activity",
    to: "/operations/timeline",
    icon: Activity,
    feature: "enable_advanced_dashboard",
  },
  {
    label: "Collaboration",
    to: "/operations/collaboration",
    icon: Handshake,
    feature: "enable_collaboration",
  },
  { label: "Investigations", to: "/investigations", icon: ShieldCheck },
  { label: "Engagements", to: "/engagements", icon: BriefcaseBusiness },
  {
    label: "Evidence Intelligence",
    to: "/evidence-intelligence",
    icon: DatabaseZap,
  },
  { label: "Threat Intelligence", to: "/threat-intelligence", icon: Radar },
  { label: "Review Board", to: "/review-board", icon: ClipboardCheck },
  {
    label: "Reports",
    to: "/reports",
    icon: FileText,
    feature: "enable_report_exports",
  },
  { label: "Knowledge", to: "/knowledge", icon: Search },
];

const investigationNav: InvestigationNavigationItem[] = [
  { label: "Detail", path: "", icon: BarChart3 },
  { label: "Members", path: "members", icon: UsersRound },
  { label: "Targets", path: "targets", icon: ShieldCheck },
  { label: "Bookmarks", path: "bookmarks", icon: Bookmark },
  { label: "Recon", path: "recon", icon: Network },
  { label: "Findings", path: "findings", icon: ShieldAlert },
  {
    label: "Playbooks",
    path: "playbooks",
    icon: BookOpenCheck,
    feature: "enable_playbooks",
  },
  { label: "Timeline", path: "timeline", icon: Clock3 },
  { label: "Correlations", path: "correlations", icon: GitGraph },
  { label: "IOCs", path: "iocs", icon: Radar },
  {
    label: "Reports",
    path: "reports",
    icon: FileText,
    feature: "enable_report_exports",
  },
  {
    label: "Analysis",
    path: "analysis",
    icon: BrainCircuit,
    feature: "enable_ai_analysis",
  },
];

export function AppShell(): JSX.Element {
  const { user, logout } = useAuth();
  const params = useParams();
  const investigationId = params.investigationId;
  const health = useQuery({
    queryKey: ["backend-health"],
    queryFn: getBackendHealth,
    refetchInterval: 60_000,
    retry: 1,
  });
  const features = useQuery({
    queryKey: ["feature-availability"],
    queryFn: getFeatureAvailability,
    retry: 1,
    staleTime: 30_000,
  });
  const featureFlags = features.data?.feature_flags;
  const enabledTopNav = topNav.filter(
    (item) => !item.feature || featureFlags?.[item.feature] !== false,
  );
  const enabledInvestigationNav = investigationNav.filter(
    (item) => !item.feature || featureFlags?.[item.feature] !== false,
  );
  const visibleTopNav =
    user?.role === "admin"
      ? [
          ...enabledTopNav,
          { label: "Audit", to: "/admin/audit", icon: ClipboardList },
          { label: "Users", to: "/admin/users", icon: UsersRound },
          { label: "Operations", to: "/admin/operations", icon: Activity },
          { label: "Settings", to: "/admin/settings", icon: Settings },
          {
            label: "Demo QA",
            to: "/admin/demo-checklist",
            icon: ClipboardCheck,
          },
        ]
      : enabledTopNav;

  return (
    <div className="min-h-screen text-raven-text">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-72 flex-col overflow-hidden border-r border-raven-border bg-raven-bg/95 px-4 py-5 backdrop-blur lg:flex">
        <div className="flex flex-none items-center gap-3 px-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-raven-violet text-white">
            RT
          </div>
          <div>
            <p className="font-semibold">RavenTech</p>
            <p className="text-xs text-raven-muted">
              Defensive Intelligence & Threat Investigation Workspace
            </p>
          </div>
        </div>

        <div className="themed-scrollbar mt-6 min-h-0 flex-1 overflow-y-auto overscroll-contain pr-1 scroll-smooth">
          <nav className="space-y-1">
            {visibleTopNav.map((item) => (
              <ShellLink
                key={item.to}
                to={item.to}
                label={item.label}
                icon={item.icon}
              />
            ))}
          </nav>

          {investigationId ? (
            <div className="mt-8 pb-4">
              <p className="px-2 text-xs uppercase tracking-wide text-raven-muted">
                Investigation
              </p>
              <nav className="mt-3 space-y-1">
                {enabledInvestigationNav.map((item) => {
                  const to = item.path
                    ? `/investigations/${investigationId}/${item.path}`
                    : `/investigations/${investigationId}`;
                  return (
                    <ShellLink
                      key={item.label}
                      to={to}
                      label={item.label}
                      icon={item.icon}
                      end={!item.path}
                    />
                  );
                })}
              </nav>
            </div>
          ) : null}
        </div>

        <div className="mt-3 flex-none rounded-lg border border-raven-border bg-raven-panel p-3">
          <HealthIndicator
            health={health.data}
            isError={health.isError}
            exportEnabled={
              featureFlags?.enable_report_exports !== false &&
              (features.data?.allowed_export_formats ?? []).length > 0
            }
            onRetry={() => void health.refetch()}
          />
          <p className="truncate text-sm font-medium">{user?.username}</p>
          <p className="text-xs text-raven-muted">{user?.role}</p>
          <button
            type="button"
            onClick={() => void logout()}
            className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-sm text-raven-text hover:border-raven-violet"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            Sign out
          </button>
        </div>
      </aside>

      <div className="lg:pl-72">
        <header className="sticky top-0 z-10 border-b border-raven-border bg-raven-bg/90 px-4 py-3 backdrop-blur lg:hidden">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold">RavenTech</p>
              <p className="text-xs text-raven-muted">
                Defensive Intelligence & Threat Investigation Workspace
              </p>
            </div>
            <button
              type="button"
              onClick={() => void logout()}
              className="rounded-md border border-raven-border p-2 text-raven-muted"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
          <nav className="mt-3 flex gap-2 overflow-x-auto pb-1">
            {visibleTopNav.map((item) => (
              <MobileLink key={item.to} to={item.to} label={item.label} />
            ))}
            {investigationId
              ? enabledInvestigationNav.map((item) => {
                  const to = item.path
                    ? `/investigations/${investigationId}/${item.path}`
                    : `/investigations/${investigationId}`;
                  return <MobileLink key={item.label} to={to} label={item.label} />;
                })
              : null}
          </nav>
        </header>

        {featureFlags?.enable_demo_mode ? (
          <div className="border-b border-cyan-400/20 bg-cyan-500/10 px-4 py-2 text-center text-xs font-medium text-cyan-100 lg:px-8">
            Demo mode is active. Synthetic defensive data is clearly labeled.
          </div>
        ) : null}
        <main className="workspace-content mx-auto min-h-screen min-w-0 max-w-7xl overflow-x-hidden px-4 py-6 md:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function HealthIndicator({
  health,
  isError,
  exportEnabled,
  onRetry,
}: {
  health: HealthResponse | undefined;
  isError: boolean;
  exportEnabled: boolean;
  onRetry: () => void;
}): JSX.Element {
  const status = isError ? "error" : health?.status ?? "checking";
  const tone =
    status === "ok"
      ? "bg-emerald-400"
      : status === "degraded" || status === "checking"
        ? "bg-amber-300"
        : "bg-rose-400";
  const checks = health?.checks ?? {};
  const explanation =
    status === "ok"
      ? "Core services are available."
      : status === "degraded"
        ? "Core workflows remain available; optional capabilities need attention."
        : status === "checking"
          ? "Checking platform dependencies."
          : "The backend or a required dependency is unavailable.";
  return (
    <details className="mb-3 rounded-md border border-raven-border bg-raven-panelSoft text-xs text-raven-muted">
      <summary className="flex cursor-pointer list-none items-center justify-between px-3 py-2 hover:text-raven-text">
        <span className="inline-flex items-center gap-2">
          <span className={["h-2 w-2 rounded-full", tone].join(" ")} />
          Platform health
        </span>
        <span className="capitalize">{status}</span>
      </summary>
      <div className="border-t border-raven-border px-3 py-2">
        <p className="leading-5">{explanation}</p>
        <div className="mt-2 space-y-1.5">
          {Object.entries(checks).map(([name, check]) => (
            <div key={name} className="flex items-start justify-between gap-2">
              <span className="capitalize">{name.replace(/_/g, " ")}</span>
              <span className="text-right text-raven-text">
                {healthCheckLabel(name, check)}
              </span>
            </div>
          ))}
          <div className="flex items-start justify-between gap-2">
            <span>Report exports</span>
            <span className="text-right text-raven-text">
              {exportEnabled ? "available" : "disabled"}
            </span>
          </div>
        </div>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 w-full rounded border border-raven-border px-2 py-1.5 hover:border-raven-violet hover:text-raven-text"
        >
          Refresh health
        </button>
      </div>
    </details>
  );
}

function healthCheckLabel(
  name: string,
  check: HealthResponse["checks"][string],
): string {
  if (name === "migrations" && check.current && check.head) {
    return `${check.status}: ${check.current} / ${check.head}`;
  }
  if (name === "ai_provider" && typeof check.available === "boolean") {
    return check.available ? `${check.status}: configured` : `${check.status}: missing`;
  }
  return check.status;
}

function ShellLink({
  to,
  label,
  icon: Icon,
  end,
}: {
  to: string;
  label: string;
  icon: typeof Home;
  end?: boolean;
}): JSX.Element {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        [
          "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition",
          isActive
            ? "bg-raven-violet text-white"
            : "text-raven-muted hover:bg-raven-panel hover:text-raven-text",
        ].join(" ")
      }
    >
      <Icon className="h-4 w-4" aria-hidden="true" />
      {label}
    </NavLink>
  );
}

function MobileLink({ to, label }: { to: string; label: string }): JSX.Element {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        [
          "whitespace-nowrap rounded-md px-3 py-1.5 text-xs",
          isActive
            ? "bg-raven-violet text-white"
            : "border border-raven-border text-raven-muted",
        ].join(" ")
      }
    >
      {label}
    </NavLink>
  );
}
