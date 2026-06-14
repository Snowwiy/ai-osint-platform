import {
  BarChart3,
  Bookmark,
  BrainCircuit,
  BookOpenCheck,
  Clock3,
  ClipboardList,
  FileText,
  GitGraph,
  Home,
  LogOut,
  Network,
  Search,
  ShieldAlert,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet, useParams } from "react-router-dom";

import { getBackendHealth } from "../lib/api";
import { useAuth } from "../lib/useAuth";
import type { HealthResponse } from "../types";

const topNav = [
  { label: "Home", to: "/", icon: Home },
  { label: "Investigations", to: "/investigations", icon: ShieldCheck },
  { label: "Knowledge", to: "/knowledge", icon: Search },
];

const investigationNav = [
  { label: "Detail", path: "", icon: BarChart3 },
  { label: "Members", path: "members", icon: UsersRound },
  { label: "Targets", path: "targets", icon: ShieldCheck },
  { label: "Bookmarks", path: "bookmarks", icon: Bookmark },
  { label: "Recon", path: "recon", icon: Network },
  { label: "Findings", path: "findings", icon: ShieldAlert },
  { label: "Playbooks", path: "playbooks", icon: BookOpenCheck },
  { label: "Timeline", path: "timeline", icon: Clock3 },
  { label: "Correlations", path: "correlations", icon: GitGraph },
  { label: "Reports", path: "reports", icon: FileText },
  { label: "Analysis", path: "analysis", icon: BrainCircuit },
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
  const visibleTopNav =
    user?.role === "admin"
      ? [...topNav, { label: "Audit", to: "/admin/audit", icon: ClipboardList }]
      : topNav;

  return (
    <div className="min-h-screen text-raven-text">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-72 border-r border-raven-border bg-raven-bg/95 px-4 py-5 backdrop-blur lg:block">
        <div className="flex items-center gap-3 px-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-raven-violet text-white">
            RT
          </div>
          <div>
            <p className="font-semibold">RavenTech</p>
            <p className="text-xs text-raven-muted">OSINT Platform</p>
          </div>
        </div>

        <nav className="mt-8 space-y-1">
          {visibleTopNav.map((item) => (
            <ShellLink key={item.to} to={item.to} label={item.label} icon={item.icon} />
          ))}
        </nav>

        {investigationId ? (
          <div className="mt-8">
            <p className="px-2 text-xs uppercase tracking-wide text-raven-muted">
              Investigation
            </p>
            <nav className="mt-3 space-y-1">
              {investigationNav.map((item) => {
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

        <div className="absolute bottom-5 left-4 right-4 rounded-lg border border-raven-border bg-raven-panel p-3">
          <HealthIndicator
            health={health.data}
            isError={health.isError}
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
              <p className="text-xs text-raven-muted">OSINT Platform</p>
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
              ? investigationNav.map((item) => {
                  const to = item.path
                    ? `/investigations/${investigationId}/${item.path}`
                    : `/investigations/${investigationId}`;
                  return <MobileLink key={item.label} to={to} label={item.label} />;
                })
              : null}
          </nav>
        </header>

        <main className="mx-auto min-h-screen max-w-7xl px-4 py-6 md:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function HealthIndicator({
  health,
  isError,
  onRetry,
}: {
  health: HealthResponse | undefined;
  isError: boolean;
  onRetry: () => void;
}): JSX.Element {
  const status = isError ? "error" : health?.status ?? "checking";
  const tone =
    status === "ok"
      ? "bg-emerald-400"
      : status === "degraded" || status === "checking"
        ? "bg-amber-300"
        : "bg-rose-400";
  return (
    <button
      type="button"
      onClick={onRetry}
      className="mb-3 flex w-full items-center justify-between rounded-md border border-raven-border bg-raven-panelSoft px-3 py-2 text-left text-xs text-raven-muted hover:text-raven-text"
      title="Backend health status. Click to refresh."
    >
      <span className="inline-flex items-center gap-2">
        <span className={["h-2 w-2 rounded-full", tone].join(" ")} />
        Backend
      </span>
      <span className="capitalize">{status}</span>
    </button>
  );
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
