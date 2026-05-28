import { NavLink, useParams } from "react-router-dom";

const tabs = [
  { label: "Overview", path: "" },
  { label: "Targets", path: "targets" },
  { label: "Recon", path: "recon" },
  { label: "Findings", path: "findings" },
  { label: "Timeline", path: "timeline" },
  { label: "Correlations", path: "correlations" },
  { label: "Reports", path: "reports" },
  { label: "AI Analysis", path: "analysis" },
];

export function InvestigationTabs(): JSX.Element {
  const { investigationId } = useParams();
  if (!investigationId) {
    return <></>;
  }

  return (
    <nav className="mb-6 flex gap-2 overflow-x-auto border-b border-raven-border pb-3">
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
                "whitespace-nowrap rounded-md px-3 py-2 text-sm transition",
                isActive
                  ? "bg-raven-violet text-white"
                  : "border border-raven-border text-raven-muted hover:border-raven-violet hover:text-raven-text",
              ].join(" ")
            }
          >
            {tab.label}
          </NavLink>
        );
      })}
    </nav>
  );
}
