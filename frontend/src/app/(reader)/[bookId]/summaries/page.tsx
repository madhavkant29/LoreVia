"use client"

import { useQuery } from "@tanstack/react-query"
import { useParams } from "next/navigation"

import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { WorkspaceEmptyState, WorkspacePanel } from "@/components/ui/Workspace"
import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import { asQueryKey, bookCacheKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book } from "@/types/book"
import type { SummaryCollectionResponse } from "@/types/reader"

export default function SummariesPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const { data: book = null, isLoading: bookLoading } = useQuery<Book>({
    queryKey: asQueryKey(bookCacheKey(bookId, "detail")),
    queryFn: () => booksApi.get(bookId),
    staleTime: 20_000,
  })
  const { data = null, isLoading: dataLoading } = useQuery<SummaryCollectionResponse>({
    queryKey: asQueryKey(readerCacheKey(bookId, "summary-collection")),
    queryFn: () => readerApi.getSummaryCollection(bookId),
    staleTime: 45_000,
  })
  const summaries = data?.summaries ?? []

  return (
    <div className="app-shell min-h-screen">
      <div className="mx-auto max-w-5xl space-y-6 px-4 pb-16 pt-6 sm:px-6 lg:px-8">
        <WorkspaceFamilyHeader
          active="summaries"
          bookId={bookId}
          family="review-center"
          title="Chapter summaries"
          description={book?.mode === "author"
            ? `Review generated summaries for processed chapters through chapter ${data?.read_upto ?? 0}.`
            : `Review available summaries through your current reading position at chapter ${data?.read_upto ?? 0}.`}
        />

        {bookLoading || dataLoading ? (
          <WorkspacePanel tone="subtle" className="p-5 text-sm text-[rgb(var(--muted-foreground))]">
            Loading summaries...
          </WorkspacePanel>
        ) : summaries.length === 0 ? (
          <WorkspaceEmptyState
            title="No chapter summaries yet"
            body="Summaries will appear here after the manuscript chapters have been processed."
          />
        ) : (
          <div className="space-y-4">
            {summaries.map((summary) => (
              <WorkspacePanel key={summary.chapter_number} className="p-5 sm:p-6">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="app-eyebrow">Chapter {summary.chapter_number}</p>
                    <h2 className="mt-2 text-xl font-semibold text-[rgb(var(--foreground))]">
                      {summary.chapter_title || "Untitled chapter"}
                    </h2>
                  </div>
                  <span className={`shrink-0 rounded-md border px-2.5 py-1 text-xs font-semibold ${
                    summary.available
                      ? isDark ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-200" : "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : isDark ? "border-amber-400/20 bg-amber-400/10 text-amber-200" : "border-amber-200 bg-amber-50 text-amber-700"
                  }`}>
                    {summary.available ? "Available" : "Pending"}
                  </span>
                </div>
                <p className="mt-4 text-sm leading-7 text-[rgb(var(--muted-foreground))]">
                  {summary.content || (book?.mode === "author"
                    ? "Summary not available yet for this processed chapter."
                    : "Summary not available yet for this read chapter.")}
                </p>
              </WorkspacePanel>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
