"use client"

import dynamic from "next/dynamic"
import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useParams, useRouter } from "next/navigation"

import { readerApi } from "@/lib/api/reader"
import { capture } from "@/lib/analytics/posthog"
import { useBookDetail } from "@/lib/hooks/useBookDetail"
import { asQueryKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { cn } from "@/lib/utils/text"

const RelationshipGraph = dynamic(
  () => import("@/components/intelligence/RelationshipGraph"),
  {
    ssr: false,
    loading: () => (
      <div className="flex min-h-[36rem] items-center justify-center rounded-lg border border-white/10 bg-[#070912] text-sm text-slate-300 shadow-[0_24px_80px_rgba(0,0,0,0.35)]">
        Loading relationship graph...
      </div>
    ),
  }
)

function ArrowLeftIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7M8 12h11" />
    </svg>
  )
}

export default function GraphPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
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
    <div className="min-h-screen bg-[#03050b] text-slate-100">
      <div className="mx-auto flex w-full max-w-[1680px] flex-col gap-6 px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex min-w-0 items-start gap-4">
            <button
              type="button"
              onClick={() => router.back()}
              className="mt-1 inline-flex shrink-0 items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3.5 py-2 text-sm text-slate-300 transition hover:border-violet-400/40 hover:bg-white/[0.06] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70"
            >
              <ArrowLeftIcon />
              <span>Back</span>
            </button>

            <div className="min-w-0">
              <p className="text-3xs font-semibold uppercase tracking-[0.28em] text-violet-300/80">Character Network</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white sm:text-[2rem]">Relationship Graph</h1>
            </div>
          </div>

          <label className="flex w-full max-w-full items-center justify-between gap-3 rounded-md border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-slate-300 shadow-[0_18px_48px_rgba(0,0,0,0.24)] lg:w-auto lg:min-w-[280px]">
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
                "w-20 rounded-xl border border-white/10 bg-[#0b1020] px-3 py-2 text-right text-sm font-medium text-white",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/70"
              )}
            />
          </label>
        </header>

        <RelationshipGraph bookId={bookId} upToChapter={chapter} theme="dark" authorMode={authorMode} />
      </div>
    </div>
  )
}
