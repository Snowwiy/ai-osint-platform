import { Search } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { searchKnowledge } from "../lib/api";
import type { KnowledgeSearchResponse } from "../types";

export function KnowledgeSearchPage(): JSX.Element {
  const [query, setQuery] = useState("");
  const search = useMutation<KnowledgeSearchResponse, Error, string>({
    mutationFn: searchKnowledge,
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const clean = query.trim();
    if (clean) {
      search.mutate(clean);
    }
  }

  return (
    <>
      <PageHeader title="Knowledge Search" eyebrow="Local defensive knowledge" />
      <form
        onSubmit={handleSubmit}
        className="mb-6 flex flex-col gap-3 rounded-lg border border-raven-border bg-raven-panel/85 p-4 md:flex-row"
      >
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="exposed RDP"
          className="min-w-0 flex-1 rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
        />
        <button
          type="submit"
          className="inline-flex items-center justify-center gap-2 rounded-md bg-raven-violet px-4 py-2 font-medium text-white hover:bg-violet-500"
        >
          <Search className="h-4 w-4" aria-hidden="true" />
          Search
        </button>
      </form>

      {search.isPending ? <LoadingBlock label="Searching knowledge" /> : null}
      {search.isError ? <ErrorBlock message={search.error.message} /> : null}
      {search.data ? (
        search.data.items.length ? (
          <div className="space-y-4">
            {search.data.items.map((item) => (
              <article
                key={`${item.document_id}-${item.chunk.slice(0, 20)}`}
                className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"
              >
                <h2 className="font-semibold">{item.title}</h2>
                <p className="mt-1 text-xs text-raven-muted">
                  {item.source_type} · score {item.score.toFixed(2)}
                </p>
                <p className="mt-3 line-clamp-4 text-sm leading-6 text-raven-muted">
                  {item.chunk}
                </p>
                {item.tags.length ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {item.tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded border border-raven-border px-2 py-0.5 text-xs text-raven-muted"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        ) : (
          <EmptyBlock message="No knowledge results matched your query." />
        )
      ) : null}
    </>
  );
}
