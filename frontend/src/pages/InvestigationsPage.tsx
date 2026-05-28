import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { listInvestigations } from "../lib/api";

export function InvestigationsPage(): JSX.Element {
  const investigations = useQuery({
    queryKey: ["investigations"],
    queryFn: listInvestigations,
  });

  if (investigations.isLoading) {
    return <LoadingBlock label="Loading investigations" />;
  }
  if (investigations.isError) {
    return <ErrorBlock message={investigations.error.message} />;
  }

  return (
    <>
      <PageHeader title="Investigations" eyebrow="Casework" />
      {investigations.data?.items.length ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {investigations.data.items.map((item) => (
            <Link
              key={item.id}
              to={`/investigations/${item.id}`}
              className="rounded-lg border border-raven-border bg-raven-panel/85 p-4 transition hover:border-raven-violet"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="font-semibold text-raven-text">{item.title}</h2>
                  <p className="mt-2 line-clamp-2 text-sm text-raven-muted">
                    {item.description ?? item.scope_definition ?? "No description stored."}
                  </p>
                </div>
                <span className="rounded border border-raven-border px-2 py-1 text-xs capitalize text-raven-muted">
                  {item.status}
                </span>
              </div>
              <p className="mt-4 text-xs text-raven-muted">
                Updated {new Date(item.updated_at).toLocaleString()}
              </p>
            </Link>
          ))}
        </div>
      ) : (
        <EmptyBlock message="No investigations are available for this account." />
      )}
    </>
  );
}
