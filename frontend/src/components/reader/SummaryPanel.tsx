"use client"
import { memo, useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { readerApi } from "@/lib/api/reader"
import { asQueryKey, readerCacheKey } from "@/lib/query/cacheKeys"
import type { SummaryMode } from "@/types/reader"
import { normalizeChapterSummary } from "@/lib/utils/summaries"
import { Dialog } from "@/components/ui/Dialog"
import { SUMMARY_MODE_LABELS } from "@/lib/constants"
import { capture } from "@/lib/analytics/posthog"
import { Skeleton } from "@/components/ui/Skeleton"

interface Props {
  bookId: string
  chapterNum: number
  onClose: () => void
  theme: "light" | "dark"
}

export const SummaryPanel = memo(function SummaryPanel({ bookId, chapterNum, onClose, theme }: Props) {
  const [mode, setMode] = useState<SummaryMode>("short")
  const summaryQuery = useQuery({
    queryKey: asQueryKey(readerCacheKey(bookId, `summary:${chapterNum}:${mode}`)),
    queryFn: () => readerApi.getSummary(bookId, chapterNum, mode),
    staleTime: 2 * 60 * 1000,
    retry: false,
  })

  useEffect(() => {
    if (!summaryQuery.data) return
    capture("summary_viewed", { book_id: bookId, chapter: chapterNum, mode })
  }, [bookId, chapterNum, mode, summaryQuery.data])

  const shellClass = theme === "dark" ? "bg-black text-white border border-white/10" : "bg-white text-black"
  const tabActiveClass = theme === "dark" ? "bg-white text-black font-medium" : "bg-black text-white font-medium"
  const tabIdleClass = theme === "dark" ? "text-gray-300 hover:bg-white/10" : "text-gray-500 hover:bg-gray-100"
  const normalized = summaryQuery.data ? normalizeChapterSummary(summaryQuery.data) : null

  return (
    <Dialog open onClose={onClose} title={`Chapter ${chapterNum} Summary`} description="Choose a recap length, then return to your place in the chapter." className={shellClass} contentClassName="p-5">
      <div className="flex flex-col">
        <div className={theme === "dark" ? "flex items-center justify-between border-b border-white/10 px-5 py-4" : "flex items-center justify-between border-b border-gray-100 px-5 py-4"}>
          <button type="button" onClick={onClose} aria-label="Close summary" className="min-h-11 rounded-sm border px-4 text-sm">Return to reading</button>
        </div>
        <div className="app-scroll flex flex-wrap gap-1 pt-4" role="group" aria-label="Summary length">
          {(Object.entries(SUMMARY_MODE_LABELS) as [SummaryMode, string][]).map(([m, label]) => (
            <button
              key={m}
              type="button"
              aria-pressed={mode === m}
              onClick={() => setMode(m)}
              className={`min-h-11 shrink-0 rounded-sm px-3 py-2 text-sm transition-colors ${
                mode === m ? tabActiveClass : tabIdleClass
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="app-scroll flex-1 overflow-y-auto px-5 py-4">
          {summaryQuery.isError ? <p role="alert" className="mb-4 text-sm">Could not load this recap. <button type="button" disabled={summaryQuery.isFetching} className="underline" onClick={() => void summaryQuery.refetch()}>Retry recap</button></p> : null}
          {summaryQuery.isLoading ? (
            <div className="space-y-3 py-2" role="status" aria-label="Loading summary" aria-busy="true">
              <span className="sr-only">Loading summary</span>
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-11/12" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="mt-6 h-3 w-24" />
              <Skeleton className="h-4 w-4/5" />
              <Skeleton className="h-4 w-3/4" />
            </div>
          ) : normalized ? (
            <div>
              <p className={theme === "dark" ? "whitespace-pre-wrap text-sm leading-relaxed text-gray-100" : "whitespace-pre-wrap text-sm leading-relaxed text-gray-700"}>
                {normalized.content}
              </p>

              {normalized.key_events && normalized.key_events.length > 0 && (
                <div className="mt-4">
                  <p className={theme === "dark" ? "mb-2 text-xs font-medium uppercase tracking-wide text-gray-400" : "mb-2 text-xs font-medium uppercase tracking-wide text-gray-500"}>
                    Key Events
                  </p>
                  {normalized.key_events.map((e, i) => (
                    <p key={i} className={theme === "dark" ? "mb-1 text-sm text-gray-300" : "mb-1 text-sm text-gray-600"}>
                      - {e.event}
                    </p>
                  ))}
                </div>
              )}

              {normalized.char_changes && normalized.char_changes.length > 0 && (
                <div className="mt-4">
                  <p className={theme === "dark" ? "mb-2 text-xs font-medium uppercase tracking-wide text-gray-400" : "mb-2 text-xs font-medium uppercase tracking-wide text-gray-500"}>
                    Character Changes
                  </p>
                  {normalized.char_changes.map((e, i) => (
                    <p key={i} className={theme === "dark" ? "mb-1 text-sm text-gray-300" : "mb-1 text-sm text-gray-600"}>
                      - {e.character}: {e.change}
                    </p>
                  ))}
                </div>
              )}

              {normalized.clues && normalized.clues.length > 0 && (
                <div className="mt-4">
                  <p className={theme === "dark" ? "mb-2 text-xs font-medium uppercase tracking-wide text-gray-400" : "mb-2 text-xs font-medium uppercase tracking-wide text-gray-500"}>
                    Clues
                  </p>
                  {normalized.clues.map((e, i) => (
                    <p key={i} className={theme === "dark" ? "mb-1 text-sm text-gray-300" : "mb-1 text-sm text-gray-600"}>
                      - {e.clue}
                    </p>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className={theme === "dark" ? "py-8 text-center text-sm text-gray-500" : "py-8 text-center text-sm text-gray-400"}>
              Summary not available yet
            </p>
          )}
        </div>
      </div>
    </Dialog>
  )
})
