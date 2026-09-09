import { BookmarkCheck, BookmarkPlus } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createBookmark,
  listBookmarks,
  listInvestigationMembers,
} from "../lib/api";
import { useAuth } from "../lib/useAuth";
import type { EvidenceBookmarkCreateRequest } from "../types";
import { safeArray } from "../lib/safe";

export function BookmarkButton({
  investigationId,
  title,
  entityId,
  findingId,
  reportId,
}: {
  investigationId: string;
  title: string;
  entityId?: string;
  findingId?: string;
  reportId?: string;
}): JSX.Element | null {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const bookmarks = useQuery({
    queryKey: ["bookmarks", investigationId],
    queryFn: () => listBookmarks(investigationId),
  });
  const members = useQuery({
    queryKey: ["members", investigationId],
    queryFn: () => listInvestigationMembers(investigationId),
  });
  const member = members.data?.find((item) => item.user_id === user?.id);
  const canMutate =
    user?.role === "admin" ||
    member?.role === "owner" ||
    member?.role === "admin" ||
    member?.role === "analyst";
  const existing = safeArray(bookmarks.data?.items).find(
    (item) =>
      item.entity_id === (entityId ?? null) &&
      item.finding_id === (findingId ?? null) &&
      item.report_id === (reportId ?? null),
  );
  const mutation = useMutation({
    mutationFn: (body: EvidenceBookmarkCreateRequest) =>
      createBookmark(investigationId, body),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["bookmarks", investigationId] }),
        queryClient.invalidateQueries({ queryKey: ["timeline", investigationId] }),
      ]);
    },
  });

  if (!canMutate && !existing) {
    return null;
  }

  return (
    <div className="inline-flex items-center gap-2">
      <button
        type="button"
        disabled={Boolean(existing) || mutation.isPending || !canMutate}
        onClick={() =>
          mutation.mutate({
            entity_id: entityId,
            finding_id: findingId,
            report_id: reportId,
            title,
          })
        }
        title={existing ? "Already bookmarked" : "Bookmark evidence"}
        className="inline-flex items-center gap-2 rounded-md border border-raven-border px-2.5 py-1.5 text-xs text-raven-muted hover:border-raven-violet hover:text-raven-text disabled:cursor-default disabled:opacity-70"
      >
        {existing ? (
          <BookmarkCheck className="h-4 w-4 text-raven-cyan" aria-hidden="true" />
        ) : (
          <BookmarkPlus className="h-4 w-4" aria-hidden="true" />
        )}
        {existing ? "Saved" : mutation.isPending ? "Saving" : "Bookmark"}
      </button>
      {mutation.isError ? (
        <span className="max-w-52 text-xs text-rose-200" title={mutation.error.message}>
          Unable to save
        </span>
      ) : null}
    </div>
  );
}
