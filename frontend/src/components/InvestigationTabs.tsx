import { useEffect, useRef } from "react";
import { NavLink, useParams } from "react-router-dom";

const tabs = [
  { label: "Overview", path: "" },
  { label: "Members", path: "members" },
  { label: "Targets", path: "targets" },
  { label: "Notes", path: "notes" },
  { label: "Bookmarks", path: "bookmarks" },
  { label: "Tasks", path: "tasks" },
  { label: "Recon", path: "recon" },
  { label: "Findings", path: "findings" },
  { label: "Playbooks", path: "playbooks" },
  { label: "Timeline", path: "timeline" },
  { label: "Correlations", path: "correlations" },
  { label: "IOCs", path: "iocs" },
  { label: "Reports", path: "reports" },
  { label: "Closure", path: "closure" },
  { label: "AI Analysis", path: "analysis" },
];

export function InvestigationTabs(): JSX.Element {
  const { investigationId } = useParams();
  const navRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const active = navRef.current?.querySelector('[aria-current="page"]');
    active?.scrollIntoView({
      block: "nearest",
      inline: "center",
      behavior: "smooth",
    });
  }, [investigationId]);

  if (!investigationId) {
    return <></>;
  }

  return (
    <div className="relative mb-6 min-w-0 border-b border-raven-border">
      <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-5 bg-gradient-to-r from-raven-bg to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-5 bg-gradient-to-l from-raven-bg to-transparent" />
      <nav
        ref={navRef}
        className="themed-scrollbar flex max-w-full min-w-0 gap-2 overflow-x-auto overscroll-x-contain px-1 pb-3"
        aria-label="Investigation workspace sections"
      >
        {tabs.map((tab) => {
          const to = tab.path
            ? `/investigations/${investigationId}/${tab.path}`
            : `/investigations/${investigationId}`;
          return (
            <NavLink
              key={tab.label}
              to={to}
              end={!tab.path}
              className={({ isActive }) =>
                [
                  "flex-none whitespace-nowrap rounded-md px-3 py-2 text-sm transition",
                  isActive
                    ? "bg-raven-violet text-white shadow-glow"
                    : "border border-raven-border text-raven-muted hover:border-raven-violet hover:text-raven-text",
                ].join(" ")
              }
            >
              {tab.label}
            </NavLink>
          );
        })}
      </nav>
    </div>
  );
}
