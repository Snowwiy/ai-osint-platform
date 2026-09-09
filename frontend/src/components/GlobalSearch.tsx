import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Command, Loader2, Search, X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { globalSearch } from "../lib/api";
import { safeArray, safeInternalRoute } from "../lib/safe";
import type { GlobalSearchResult, GlobalSearchType } from "../types";

const RECENT_SEARCHES_KEY = "raventech.recentSearches";
const RESULT_TYPES: Array<{ value: GlobalSearchType | ""; label: string }> = [
  { value: "", label: "All" },
  { value: "investigation", label: "Investigations" },
  { value: "engagement", label: "Engagements" },
  { value: "finding", label: "Findings" },
  { value: "report", label: "Reports" },
  { value: "deliverable", label: "Deliverables" },
  { value: "notification", label: "Notifications" },
  { value: "scope_item", label: "Scope" },
  { value: "closure", label: "Closure" },
  { value: "ioc", label: "IOCs" },
  { value: "threat_object", label: "Threat Intel" },
  { value: "evidence_summary", label: "Evidence" },
  { value: "user", label: "Users" },
];

export function GlobalSearch(): JSX.Element {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [type, setType] = useState<GlobalSearchType | "">("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [recentSearches, setRecentSearches] = useState<string[]>(() =>
    readRecentSearches(),
  );
  const navigate = useNavigate();

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent): void => {
      const isSearchShortcut = (event.ctrlKey || event.metaKey) && event.key === "k";
      if (isSearchShortcut) {
        event.preventDefault();
        setOpen(true);
      }
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query), 220);
    return () => window.clearTimeout(timer);
  }, [query]);

  const search = useQuery({
    queryKey: ["global-search", debouncedQuery, type],
    queryFn: () =>
      globalSearch({
        q: debouncedQuery,
        type,
        limit: 20,
      }),
    enabled: open,
    retry: 1,
    staleTime: 15_000,
  });
  const results = useMemo(() => safeArray(search.data?.items), [search.data?.items]);
  const grouped = useMemo(() => groupResults(results), [results]);
  const hasQuery = debouncedQuery.trim().length > 0;

  const openResult = (result: GlobalSearchResult): void => {
    const route = safeInternalRoute(result.route);
    if (query.trim()) {
      const next = [
        query.trim(),
        ...recentSearches.filter((item) => item !== query.trim()),
      ].slice(0, 6);
      setRecentSearches(next);
      writeRecentSearches(next);
    }
    setOpen(false);
    navigate(route);
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex w-full items-center justify-between gap-3 rounded-lg border border-raven-border bg-raven-panelSoft px-3 py-2 text-left text-sm text-raven-muted transition hover:border-raven-violet hover:text-raven-text"
        title="Open global search (Ctrl+K)"
      >
        <span className="inline-flex min-w-0 items-center gap-2">
          <Search className="h-4 w-4 flex-none" aria-hidden="true" />
          <span className="truncate">Search investigations, reports, IOCs...</span>
        </span>
        <span className="hidden rounded border border-raven-border px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-raven-muted sm:inline-flex">
          Ctrl K
        </span>
      </button>

      {open ? (
        <div
          className="fixed inset-0 z-50 overflow-y-auto bg-black/70 px-3 py-4 backdrop-blur-sm sm:px-4 sm:py-8"
          role="dialog"
          aria-modal="true"
          aria-label="Global search"
        >
          <div className="mx-auto flex max-h-[calc(100vh-2rem)] max-w-3xl flex-col overflow-hidden rounded-lg border border-raven-border bg-raven-panel shadow-2xl sm:max-h-[calc(100vh-4rem)]">
            <div className="flex flex-wrap items-center gap-3 border-b border-raven-border p-4">
              <Search className="h-5 w-5 flex-none text-raven-muted" aria-hidden="true" />
              <input
                autoFocus
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search internal investigations, reports, findings, IOCs..."
                className="min-w-0 flex-1 basis-48 bg-transparent text-sm text-raven-text outline-none placeholder:text-raven-muted"
              />
              <select
                value={type}
                onChange={(event) =>
                  setType(event.target.value as GlobalSearchType | "")
                }
                className="order-3 w-full rounded border border-raven-border bg-raven-panelSoft px-2 py-1.5 text-xs text-raven-text outline-none sm:order-none sm:w-auto sm:max-w-[11rem]"
                aria-label="Search result type"
              >
                {RESULT_TYPES.map((item) => (
                  <option key={item.value || "all"} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-md border border-raven-border p-2 text-raven-muted hover:border-raven-violet hover:text-raven-text"
                aria-label="Close search"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>

            <div className="themed-scrollbar min-h-0 flex-1 overflow-y-auto p-4">
              {!hasQuery && recentSearches.length > 0 ? (
                <div className="mb-4">
                  <p className="mb-2 text-xs uppercase tracking-wide text-raven-muted">
                    Recent searches
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {recentSearches.map((item) => (
                      <button
                        key={item}
                        type="button"
                        onClick={() => setQuery(item)}
                        className="rounded-full border border-raven-border px-3 py-1 text-xs text-raven-muted hover:border-raven-violet hover:text-raven-text"
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              {search.isFetching ? (
                <div className="flex min-h-32 items-center justify-center text-sm text-raven-muted">
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                  Searching internal workspace
                </div>
              ) : null}

              {search.isError ? (
                <div className="rounded-lg border border-rose-400/30 bg-rose-500/10 p-4 text-sm text-rose-100">
                  Search is temporarily unavailable. Try again or refresh the page.
                </div>
              ) : null}

              {!search.isFetching && !search.isError && results.length === 0 ? (
                <div className="rounded-lg border border-dashed border-raven-border bg-raven-panelSoft p-6 text-center text-sm text-raven-muted">
                  <p className="font-medium text-raven-text">
                    {hasQuery ? "No matching results" : "Start typing to search"}
                  </p>
                  <p className="mx-auto mt-2 max-w-lg leading-6">
                    Search is internal-only and respects your workspace permissions.
                    It does not browse the internet or query external providers.
                  </p>
                </div>
              ) : null}

              {!search.isFetching && !search.isError
                ? grouped.map(([group, items]) => (
                    <div key={group} className="mb-5 last:mb-0">
                      <p className="mb-2 text-xs uppercase tracking-wide text-raven-muted">
                        {formatType(group)}
                      </p>
                      <div className="space-y-2">
                        {items.map((item) => (
                          <button
                            key={`${item.type}:${item.id}`}
                            type="button"
                            onClick={() => openResult(item)}
                            className="flex w-full items-start justify-between gap-3 rounded-lg border border-raven-border bg-raven-panelSoft p-3 text-left transition hover:border-raven-violet"
                          >
                            <span className="min-w-0">
                              <span className="block break-words text-sm font-medium text-raven-text">
                                {item.title || "Untitled result"}
                              </span>
                              {item.subtitle ? (
                                <span className="mt-1 block break-words text-xs text-raven-muted">
                                  {item.subtitle}
                                </span>
                              ) : null}
                              {item.snippet ? (
                                <span className="mt-2 block break-words text-xs leading-5 text-raven-muted">
                                  {item.snippet}
                                </span>
                              ) : null}
                              <span className="mt-2 flex flex-wrap gap-2 text-[11px] text-raven-muted">
                                {item.status ? <Badge>{item.status}</Badge> : null}
                                {item.severity ? <Badge>{item.severity}</Badge> : null}
                                {safeArray(item.matched_fields).length ? (
                                  <Badge>
                                    {safeArray(item.matched_fields).join(", ")}
                                  </Badge>
                                ) : null}
                              </span>
                            </span>
                            <ArrowRight
                              className="mt-0.5 h-4 w-4 flex-none text-raven-muted"
                              aria-hidden="true"
                            />
                          </button>
                        ))}
                      </div>
                    </div>
                  ))
                : null}
            </div>

            <div className="flex items-center justify-between border-t border-raven-border px-4 py-3 text-xs text-raven-muted">
              <span className="inline-flex items-center gap-1.5">
                <Command className="h-3.5 w-3.5" aria-hidden="true" />
                Ctrl/Command K opens search
              </span>
              <span>{search.data?.total ?? 0} results</span>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

function groupResults(
  results: GlobalSearchResult[],
): Array<[string, GlobalSearchResult[]]> {
  const groups = new Map<string, GlobalSearchResult[]>();
  for (const result of results) {
    const key = String(result.type || "other");
    groups.set(key, [...(groups.get(key) ?? []), result]);
  }
  return Array.from(groups.entries());
}

function formatType(value: string): string {
  return value.replace(/_/g, " ");
}

function Badge({ children }: { children: string }): JSX.Element {
  return (
    <span className="rounded-full border border-raven-border px-2 py-0.5 capitalize">
      {children.replace(/_/g, " ")}
    </span>
  );
}

function readRecentSearches(): string[] {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(RECENT_SEARCHES_KEY) ?? "[]");
    return Array.isArray(parsed)
      ? parsed.filter((item): item is string => typeof item === "string").slice(0, 6)
      : [];
  } catch {
    return [];
  }
}

function writeRecentSearches(items: string[]): void {
  window.localStorage.setItem(RECENT_SEARCHES_KEY, JSON.stringify(items.slice(0, 6)));
}
