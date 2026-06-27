import { Bookmark, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { InvestigationTabs } from "../components/InvestigationTabs";
import { LongValue } from "../components/LongValue";
import { PageHeader } from "../components/PageHeader";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlock";
import { ToastBanner, type ToastState } from "../components/ToastBanner";
import {
  deleteBookmark,
  listBookmarks,
  listInvestigationMembers,
} from "../lib/api";
import { useInvestigationId } from "../lib/hooks";
import { useAuth } from "../lib/useAuth";
import { useState } from "react";

export function BookmarksPage(): JSX.Element {
  const investigationId = useInvestigationId();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [toast, setToast] = useState<ToastState | null>(null);
  const bookmarks = useQuery({
    queryKey: ["bookmarks", investigationId],
    queryFn: () => listBookmarks(investigationId),
  });
  const members = useQuery({
    queryKey: ["members", investigationId],
    queryFn: () => listInvestigationMembers(investigationId),
  });
  const currentMember = members.data?.find((item) => item.user_id === user?.id);
  const canMutate =
    user?.role === "admin" ||
    currentMember?.role === "owner" ||
    currentMember?.role === "admin" ||
    currentMember?.role === "analyst";
  const remove = useMutation({
    mutationFn: deleteBookmark,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["bookmarks", investigationId] }),
        queryClient.invalidateQueries({ queryKey: ["timeline", investigationId] }),
      ]);
      setToast({ kind: "success", message: "Bookmark removed." });
    },
    onError: (error) => {
      setToast({ kind: "error", message: error.message });
    },
  });

  if (bookmarks.isLoading) {
    return <LoadingBlock label="Loading bookmarks" />;
  }
  if (bookmarks.isError) {
    return <ErrorBlock message={bookmarks.error} />;
  }
  const bookmarkItems = bookmarks.data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Bookmarks"
        eyebrow="Saved investigation evidence"
      />
      {toast ? <ToastBanner toast={toast} onDismiss={() => setToast(null)} /> : null}
      <InvestigationTabs />
      {bookmarkItems.length ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {bookmarkItems.map((item) => {
            const reference = item.entity_id ?? item.finding_id ?? item.report_id ?? "";
            return (
              <article
                key={item.id}
                className="rounded-lg border border-raven-border bg-raven-panel/85 p-4"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Bookmark className="h-4 w-4 text-raven-cyan" aria-hidden="true" />
                      <span className="rounded border border-raven-border px-2 py-1 text-xs capitalize text-raven-muted">
                        {item.bookmark_type}
                      </span>
                    </div>
                    <h2 className="mt-3 break-words font-semibold">{item.title}</h2>
                  </div>
                  {canMutate ? (
                    <button
                      type="button"
                      onClick={() => remove.mutate(item.id)}
                      disabled={remove.isPending}
                      className="rounded-md border border-rose-400/30 p-2 text-rose-100 hover:bg-rose-500/10 disabled:opacity-60"
                      aria-label="Delete bookmark"
                    >
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                    </button>
                  ) : null}
                </div>
                <LongValue
                  value={reference}
                  className="mt-4 text-sm text-raven-muted"
                  maxLength={48}
                />
                {item.note ? (
                  <p className="mt-3 whitespace-pre-wrap text-sm text-raven-muted">
                    {item.note}
                  </p>
                ) : null}
                <p className="mt-4 text-xs text-raven-muted">
                  Saved {new Date(item.created_at).toLocaleString()} by{" "}
                  {item.created_by ?? "unknown analyst"}
                </p>
              </article>
            );
          })}
        </div>
      ) : (
        <EmptyBlock
          title="No bookmarked evidence"
          message="Bookmarks preserve quick links to important findings, recon entities, reports, and correlations."
          nextStep="Use the bookmark action on an evidence-backed item in this investigation."
          permission="Contributors can manage bookmarks; viewers have read-only access."
        />
      )}
    </>
  );
}
