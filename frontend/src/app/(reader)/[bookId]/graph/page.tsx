"use client"

import dynamic from "next/dynamic"
import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useParams } from "next/navigation"

import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { readerApi } from "@/lib/api/reader"
import { capture } from "@/lib/analytics/posthog"
import { useBookDetail } from "@/lib/hooks/useBookDetail"
import { asQueryKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { cn } from "@/lib/utils/text"

const RelationshipGraph = dynamic(
  () => import("@/components/intelligence/RelationshipGraph"),
  {
    ssr: false,
    loading: () => (
      <div className="app-panel flex min-h-[36rem] items-center justify-center text-sm text-[rgb(var(--muted-foreground))]">
        Loading relationship graph...
      </div>
    ),
  }
)

export default function GraphPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [chapter, setChapter] = useState(1)
  const [maxChapter, setMaxChapter] = useState(1)
  const { data: book = null } = useBookDetail(bookId)
  const { data: progress = null } = useQuery({
    queryKey: asQueryKey(readerCacheKey(bookId, "progress")),
    queryFn: () => readerApi.getProgress(bookId),
  })
  const authorMode = book?.mode === "author"
  const chapterLabel = authorMode ? "Up to manuscript chapter" : "Up to read chapter"

  useEffect(() => {
    const readChapter = Math.max(1, progress?.current_chapter ?? 1)
    setChapter(readChapter)
    setMaxChapter(readChapter)
  }, [progress])

  useEffect(() => {
    capture("graph_opened", { book_id: bookId })
  }, [bookId])

  return (
    <div className="app-shell min-h-screen">
      <div className="mx-auto flex w-full max-w-[1680px] flex-col gap-6 px-4 py-5 sm:px-6 lg:px-8">
        <WorkspaceFamilyHeader
          active="relationships"
          bookId={bookId}
          family="story-bible"
          title="Relationship graph"
          description="Inspect the character network through the current reading or manuscript chapter, with relationship context grounded in the workspace."
          actions={
            <label className="flex w-full max-w-full items-center justify-between gap-3 rounded-md border border-[rgba(var(--border),0.85)] bg-[rgba(var(--surface),0.74)] px-4 py-3 text-sm text-[rgb(var(--muted-foreground))] lg:w-auto lg:min-w-[280px]">
            <span className="min-w-0 truncate">{chapterLabel}</span>
            <input
              type="number"
              inputMode="numeric"
              value={chapter}
              min={1}
              max={maxChapter}
              aria-label={chapterLabel}
              onChange={(event) => {
                const nextValue = Number(event.target.value)
                setChapter(Math.min(maxChapter, Math.max(1, nextValue)))
              }}
              className={cn(
                "w-20 rounded-md border border-[rgba(var(--border),0.85)] bg-[rgb(var(--surface))] px-3 py-2 text-right text-sm font-medium text-[rgb(var(--foreground))]",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(var(--primary),0.5)]"
              )}
            />
            </label>
          }
        />

        <RelationshipGraph bookId={bookId} upToChapter={chapter} theme={isDark ? "dark" : "light"} authorMode={authorMode} />
      </div>
    </div>
  )
}
