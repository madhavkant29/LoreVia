"use client"

import dynamic from "next/dynamic"
import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useParams, useRouter } from "next/navigation"

import { ChapterList } from "@/components/reader/ChapterList"
import { ChaptersPageHeader } from "@/components/reader/ChaptersPageHeader"
import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import { asQueryKey, bookCacheKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book } from "@/types/book"
import type { ChapterListResponse } from "@/types/reader"

const AuthorToolsNav = dynamic(
  () => import("@/components/layout/AuthorToolsNav").then((module) => module.AuthorToolsNav),
  {
    ssr: false,
    loading: () => <div className="rounded-lg border border-dashed p-8" />,
  }
)

function storyUnitLabel(workType?: Book["work_type"]) {
  return workType === "screenplay" ? "Scene" : "Chapter"
}

export default function ChapterListPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  const [readBusy, setReadBusy] = useState<string | null>(null)
  const bookQuery = useQuery<Book>({
    queryKey: asQueryKey(bookCacheKey(bookId, "detail")),
    queryFn: () => booksApi.get(bookId),
    staleTime: 20_000,
  })
  const chapterListQuery = useQuery<ChapterListResponse>({
    queryKey: asQueryKey(readerCacheKey(bookId, "chapters")),
    queryFn: () => readerApi.getChapterList(bookId),
    staleTime: 30_000,
  })
  const book = bookQuery.data ?? null
  const data = chapterListQuery.data ?? null
  const chapterListLoading = chapterListQuery.isLoading
  const chapterListError = chapterListQuery.isError ? "Could not load the full chapter list." : null

  async function setChapterRead(chapter: number, read: boolean) {
    setReadBusy(`chapter:${chapter}`)
    try {
      await readerApi.updateChapterReadStatus(bookId, chapter, read)
      await chapterListQuery.refetch()
    } finally {
      setReadBusy(null)
    }
  }

  async function markBookRead() {
    setReadBusy("book")
    try {
      await readerApi.markBookRead(bookId)
      await chapterListQuery.refetch()
    } finally {
      setReadBusy(null)
    }
  }

  const unitLabel = storyUnitLabel(book?.work_type)
  const processedCount = useMemo(() => (data?.chapters ?? []).filter((chapter) => chapter.processed).length, [data])
  const chapterCount = data?.chapters.length ?? 0
  const backLabel = book?.mode === "author" ? "Back to Manuscripts" : "Back to Book"
  const subtitle = book?.mode === "author"
    ? `Showing all processed and queued ${unitLabel.toLowerCase()}s across the manuscript.`
    : `Showing the full ${unitLabel.toLowerCase()} list with your current read status.`

  return (
    <div className={`min-h-screen transition-colors ${isDark ? "bg-[radial-gradient(circle_at_top,#0d1a22_0%,#081019_28%,#05080f_62%,#030508_100%)] text-slate-100" : "bg-[linear-gradient(180deg,#fcf7ef_0%,#f8f3ec_46%,#f5f0ea_100%)] text-stone-950"}`}>
      <div className="mx-auto max-w-[100rem] px-4 pb-14 pt-5 sm:px-6 lg:px-8">
        <div className="grid gap-6 xl:grid-cols-[17rem_minmax(0,1fr)]">
          <AuthorToolsNav
            bookId={bookId}
            active="chapters"
            isDark={isDark}
            bookData={book}
            title="Chapter navigator"
            description="Move through the manuscript, open any chapter directly, and keep the rest of the workspace one click away."
            variant="rail"
            railSize="compact"
          />

          <main className="min-w-0 space-y-5">
            <ChaptersPageHeader
              title={book?.title || `${unitLabel} list`}
              subtitle={subtitle}
              processedCount={chapterListLoading ? null : processedCount}
              totalCount={chapterListLoading ? null : chapterCount}
              isDark={isDark}
              backLabel={backLabel}
              primaryActionLabel="Mark book as read"
              primaryActionBusyLabel="Marking..."
              primaryActionBusy={readBusy === "book"}
              primaryActionDisabled={chapterListLoading || Boolean(chapterListError)}
              onBack={() => router.back()}
              onPrimaryAction={() => void markBookRead()}
            />

            {chapterListError ? (
              <div className={`rounded-lg border px-5 py-4 text-sm ${isDark ? "border-red-500/25 bg-red-500/10 text-red-300" : "border-red-200 bg-red-50 text-red-700"}`}>
                {chapterListError}
              </div>
            ) : null}

            {chapterListLoading ? (
              <LoadingChapterList unitLabel={unitLabel} isDark={isDark} />
            ) : null}

            {!chapterListLoading && !chapterListError && chapterCount === 0 ? (
              <section className={`rounded-lg border border-dashed px-6 py-14 text-center ${isDark ? "border-white/10 bg-white/[0.03] text-slate-400" : "border-stone-300 bg-white/80 text-stone-500"}`}>
                <p className={`text-3xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>Chapters</p>
                <h2 className={`mt-3 text-xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>No chapters processed yet</h2>
                <p className="mt-2 text-sm">This manuscript will show processed and queued chapters here as they become available.</p>
              </section>
            ) : null}

            {!chapterListLoading && !chapterListError && chapterCount > 0 ? (
              <ChapterList
                chapters={data?.chapters ?? []}
                unitLabel={unitLabel}
                isDark={isDark}
                readBusyKey={readBusy}
                onOpenChapter={(chapterNumber) => router.push(`/${bookId}/chapter/${chapterNumber}`)}
                onToggleChapterRead={(chapterNumber, nextRead) => void setChapterRead(chapterNumber, nextRead)}
              />
            ) : null}
          </main>
        </div>
      </div>
    </div>
  )
}

function LoadingChapterList({ unitLabel, isDark }: { unitLabel: string; isDark: boolean }) {
  return (
    <section aria-label={`Loading ${unitLabel.toLowerCase()} list`} className="space-y-4">
      <div className={`text-3xs font-semibold uppercase tracking-[0.3em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>Chapters</div>
      <div className={`space-y-3 rounded-lg border p-3 sm:p-4 ${isDark ? "border-white/10 bg-[#091018]/58" : "border-stone-200 bg-white/78"}`}>
        {Array.from({ length: 3 }, (_, index) => (
          <div
            key={index}
            className={`animate-pulse rounded-lg border px-5 py-5 ${isDark ? "border-white/10 bg-[#0b1118]/78" : "border-stone-200 bg-white/85"}`}
          >
            <div className="flex flex-col gap-5 xl:grid xl:grid-cols-[minmax(0,1.15fr)_minmax(16rem,0.8fr)_auto] xl:items-center">
              <div className="flex items-start gap-4">
                <div className={`h-12 w-12 rounded-md ${isDark ? "bg-white/[0.08]" : "bg-stone-200"}`} />
                <div className="min-w-0 flex-1 space-y-3">
                  <div className={`h-3 w-24 rounded-full ${isDark ? "bg-white/[0.08]" : "bg-stone-200"}`} />
                  <div className={`h-7 w-44 rounded-full ${isDark ? "bg-white/[0.08]" : "bg-stone-200"}`} />
                </div>
              </div>
              <div className={`space-y-3 xl:border-l xl:pl-5 ${isDark ? "xl:border-white/10" : "xl:border-stone-200"}`}>
                <div className={`h-3 w-40 rounded-full ${isDark ? "bg-white/[0.08]" : "bg-stone-200"}`} />
                <div className={`h-3 w-32 rounded-full ${isDark ? "bg-white/[0.08]" : "bg-stone-200"}`} />
                <div className={`h-3 w-36 rounded-full ${isDark ? "bg-white/[0.08]" : "bg-stone-200"}`} />
              </div>
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2 xl:justify-end">
                  <div className={`h-7 w-24 rounded-full ${isDark ? "bg-white/[0.08]" : "bg-stone-200"}`} />
                  <div className={`h-7 w-20 rounded-full ${isDark ? "bg-white/[0.08]" : "bg-stone-200"}`} />
                  <div className={`h-7 w-24 rounded-full ${isDark ? "bg-white/[0.08]" : "bg-stone-200"}`} />
                </div>
                <div className="flex flex-wrap gap-2 xl:justify-end">
                  <div className={`h-10 w-24 rounded-md ${isDark ? "bg-white/[0.08]" : "bg-stone-200"}`} />
                  <div className={`h-10 w-32 rounded-md ${isDark ? "bg-white/[0.08]" : "bg-stone-200"}`} />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
