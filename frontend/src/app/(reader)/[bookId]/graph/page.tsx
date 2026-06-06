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
import { Skeleton } from "@/components/ui/Skeleton"

const RelationshipGraph = dynamic(
  () => import("@/components/intelligence/RelationshipGraph"),
  {
    ssr: false,
    loading: () => (
      <RelationshipGraphSkeleton />
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

function RelationshipGraphSkeleton() {
  return (
    <div className="app-panel relative min-h-[36rem] overflow-hidden" role="status" aria-label="Loading relationship graph" aria-busy="true">
      <span className="sr-only">Loading relationship graph</span>
      <div className="absolute left-4 top-4 z-10 rounded-md border border-[rgba(var(--border),0.85)] bg-[rgb(var(--surface))] p-3">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="mt-2 h-4 w-36" />
        <Skeleton className="mt-2 h-3 w-48" />
      </div>
      <div className="absolute right-4 top-4 z-10 flex gap-2 rounded-md border border-[rgba(var(--border),0.85)] bg-[rgb(var(--surface))] p-2">
        <Skeleton className="h-8 w-8 rounded-md" />
        <Skeleton className="h-8 w-8 rounded-md" />
        <Skeleton className="h-8 w-14 rounded-md" />
        <Skeleton className="h-8 w-16 rounded-md" />
      </div>
      <div className="grid h-[36rem] place-items-center">
        <div className="relative h-72 w-full max-w-3xl">
          {[
            "left-[8%] top-[20%] h-14 w-14",
            "left-[28%] top-[8%] h-10 w-10",
            "left-[45%] top-[34%] h-16 w-16",
            "right-[26%] top-[18%] h-12 w-12",
            "right-[8%] top-[42%] h-10 w-10",
            "left-[18%] bottom-[18%] h-12 w-12",
            "right-[38%] bottom-[10%] h-14 w-14",
          ].map((className) => (
            <Skeleton key={className} variant="circle" className={`absolute ${className}`} />
          ))}
          <Skeleton className="absolute left-[14%] top-[35%] h-px w-48 rotate-12" />
          <Skeleton className="absolute left-[42%] top-[52%] h-px w-56 -rotate-12" />
          <Skeleton className="absolute right-[22%] top-[38%] h-px w-36 rotate-45" />
        </div>
      </div>
    </div>
  )
}
