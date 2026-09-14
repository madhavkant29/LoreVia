"use client"
import { memo, useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { readerApi } from "@/lib/api/reader"
import { asQueryKey, readerCacheKey } from "@/lib/query/cacheKeys"
import type { ChapterSummary, SummaryMode } from "@/types/reader"
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
  })

  useEffect(() => {
    if (!summaryQuery.data) return
    capture("summary_viewed", { book_id: bookId, chapter: chapterNum, mode })
  }, [bookId, chapterNum, mode, summaryQuery.data])

  const shellClass = theme === "dark" ? "bg-black text-white border border-white/10" : "bg-white text-black"
  const tabActiveClass = theme === "dark" ? "bg-white text-black font-medium" : "bg-black text-white font-medium"
  const tabIdleClass = theme === "dark" ? "text-gray-300 hover:bg-white/10" : "text-gray-500 hover:bg-gray-100"
  const normalized = summaryQuery.data ? normalizeSummary(summaryQuery.data) : null

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4">
      <div className={`flex max-h-[86dvh] w-full flex-col rounded-t-lg transition-colors sm:max-h-[80vh] sm:max-w-lg ${shellClass}`}>
        <div className={theme === "dark" ? "flex items-center justify-between border-b border-white/10 px-5 py-4" : "flex items-center justify-between border-b border-gray-100 px-5 py-4"}>
          <h2 className="font-semibold">Chapter {chapterNum} Summary</h2>
          <button type="button" onClick={onClose} aria-label="Close summary" className={theme === "dark" ? "text-xl text-gray-500 hover:text-white" : "text-xl text-gray-400 hover:text-gray-600"}>x</button>
        </div>
        <div className="app-scroll flex gap-1 overflow-x-auto px-5 pt-4" role="tablist" aria-label="Summary length">
          {(Object.entries(SUMMARY_MODE_LABELS) as [SummaryMode, string][]).map(([m, label]) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={mode === m}
              onClick={() => setMode(m)}
              className={`shrink-0 rounded-full px-3 py-1.5 text-xs transition-colors ${
                mode === m ? tabActiveClass : tabIdleClass
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="app-scroll flex-1 overflow-y-auto px-5 py-4">
          {summaryQuery.isLoading || summaryQuery.isFetching ? (
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
    </div>
  )
})

function normalizeSummary(summary: ChapterSummary): ChapterSummary {
  const trimmed = summary.content.trim()
  if (!trimmed.startsWith("{") && !trimmed.startsWith("```")) {
    return {
      ...summary,
      key_events: summary.key_events ?? [],
      char_changes: summary.char_changes ?? [],
      clues: summary.clues ?? [],
    }
  }

  try {
    const stripped = trimmed
      .replace(/^```json\s*/i, "")
      .replace(/^```\s*/i, "")
      .replace(/\s*```$/, "")
    const parsed = JSON.parse(stripped)
    if (parsed && typeof parsed === "object") {
      return {
        content: parsed.summary ?? summary.content,
        key_events: parsed.key_events ?? summary.key_events ?? [],
        char_changes: parsed.char_changes ?? summary.char_changes ?? [],
        clues: parsed.clues ?? summary.clues ?? [],
      }
    }
  } catch {}

  return {
    ...summary,
    key_events: summary.key_events ?? [],
    char_changes: summary.char_changes ?? [],
    clues: summary.clues ?? [],
  }
}
