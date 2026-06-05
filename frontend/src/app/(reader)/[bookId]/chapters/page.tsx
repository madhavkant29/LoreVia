"use client"

import dynamic from "next/dynamic"
import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useParams, useRouter } from "next/navigation"

import { ChapterList } from "@/components/reader/ChapterList"
import { ChaptersPageHeader } from "@/components/reader/ChaptersPageHeader"
import { Skeleton } from "@/components/ui/Skeleton"
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
  const [deleteBusy, setDeleteBusy] = useState<string | null>(null)
  const [actionStatus, setActionStatus] = useState<string | null>(null)
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

  async function removeChapter(chapterNumber: number) {
    const confirmed = window.confirm(
      `Remove ${unitLabel} ${chapterNumber}? This deletes its manuscript text, scenes, notes, comments, and chapter intelligence. This cannot be undone.`
    )
    if (!confirmed) return

    setDeleteBusy(`chapter:${chapterNumber}`)
    setActionStatus(null)
    try {
      await booksApi.deleteChapter(bookId, chapterNumber)
      await Promise.all([bookQuery.refetch(), chapterListQuery.refetch()])
      setActionStatus(`${unitLabel} ${chapterNumber} removed.`)
    } catch {
      setActionStatus(`Could not remove ${unitLabel.toLowerCase()} ${chapterNumber}.`)
    } finally {
      setDeleteBusy(null)
    }
  }

  const unitLabel = storyUnitLabel(book?.work_type)
  const canRemoveChapters = book?.mode === "author"
  const processedCount = useMemo(() => (data?.chapters ?? []).filter((chapter) => chapter.processed).length, [data])
  const chapterCount = data?.chapters.length ?? 0
  const backLabel = book?.mode === "author" ? "Back to Manuscripts" : "Back to Book"
  const subtitle = book?.mode === "author"
    ? `Showing all processed and queued ${unitLabel.toLowerCase()}s across the manuscript.`
    : `Showing the full ${unitLabel.toLowerCase()} list with your current read status.`

  return (
    <div className={`min-h-screen transition-colors ${isDark ? "bg-[#071211] text-slate-100" : "bg-stone-50 text-stone-950"}`}>
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

            {actionStatus ? (
              <div role="status" className={`rounded-lg border px-5 py-4 text-sm ${isDark ? "border-white/10 bg-white/[0.04] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                {actionStatus}
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
                deleteBusyKey={deleteBusy}
                onOpenChapter={(chapterNumber) => router.push(`/${bookId}/chapter/${chapterNumber}`)}
                onToggleChapterRead={(chapterNumber, nextRead) => void setChapterRead(chapterNumber, nextRead)}
                onDeleteChapter={canRemoveChapters ? (chapterNumber) => void removeChapter(chapterNumber) : undefined}
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
          <div key={index} className={`rounded-lg border px-5 py-5 ${isDark ? "border-white/10 bg-[#0b1118]/78" : "border-stone-200 bg-white/85"}`}>
            <div className="flex flex-col gap-5 xl:grid xl:grid-cols-[minmax(0,1.15fr)_minmax(16rem,0.8fr)_auto] xl:items-center">
              <div className="flex items-start gap-4">
                <Skeleton variant="circle" className="h-12 w-12 rounded-md" />
                <div className="min-w-0 flex-1 space-y-3">
                  <Skeleton className="h-3 w-24 rounded-full" />
                  <Skeleton className="h-7 w-44 rounded-full" />
                </div>
              </div>
              <div className={`space-y-3 xl:border-l xl:pl-5 ${isDark ? "xl:border-white/10" : "xl:border-stone-200"}`}>
                <Skeleton className="h-3 w-40 rounded-full" />
                <Skeleton className="h-3 w-32 rounded-full" />
                <Skeleton className="h-3 w-36 rounded-full" />
              </div>
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2 xl:justify-end">
                  <Skeleton className="h-7 w-24 rounded-full" />
                  <Skeleton className="h-7 w-20 rounded-full" />
                  <Skeleton className="h-7 w-24 rounded-full" />
                </div>
                <div className="flex flex-wrap gap-2 xl:justify-end">
                  <Skeleton className="h-10 w-24 rounded-md" />
                  <Skeleton className="h-10 w-32 rounded-md" />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
