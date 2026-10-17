"use client"

import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"

import { ChapterList } from "@/components/reader/ChapterList"
import { ChaptersPageHeader } from "@/components/reader/ChaptersPageHeader"
import { AuthorToolsNav } from "@/components/layout/AuthorToolsNav"
import { useConfirmDialog } from "@/components/ui/ConfirmDialog"
import { Skeleton } from "@/components/ui/Skeleton"
import { ErrorCard } from "@/components/ui/ErrorCard"
import { canRemoveChapter, filterChapterList, type ChapterStatusFilter } from "@/lib/utils/chapterNavigator"
import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import { asQueryKey, bookCacheKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book } from "@/types/book"
import type { ChapterListResponse, SummaryCollectionResponse } from "@/types/reader"

function storyUnitLabel(workType?: Book["work_type"]) {
  return workType === "screenplay" ? "Scene" : "Chapter"
}

export default function ChapterListPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const confirm = useConfirmDialog()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  const [readBusy, setReadBusy] = useState<string | null>(null)
  const [deleteBusy, setDeleteBusy] = useState<string | null>(null)
  const [actionStatus, setActionStatus] = useState<string | null>(null)
  const [actionError, setActionError] = useState<{ message: string; retry: () => void } | null>(null)
  const [search, setSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState<ChapterStatusFilter>("all")
  const [recapsVisible, setRecapsVisible] = useState(false)
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
  const summaryCollectionQuery = useQuery<SummaryCollectionResponse>({
    queryKey: asQueryKey(readerCacheKey(bookId, "summary-collection")),
    queryFn: () => readerApi.getSummaryCollection(bookId),
    staleTime: 45_000,
    enabled: false,
  })
  const book = bookQuery.data ?? null
  const data = chapterListQuery.data ?? null
  const chapterListLoading = chapterListQuery.isLoading
  const chapterListError = chapterListQuery.isError ? "Could not load the full chapter list." : null

  async function setChapterRead(chapter: number, read: boolean) {
    if (readBusy || deleteBusy) return
    setReadBusy(`chapter:${chapter}`)
    setActionStatus(null)
    setActionError(null)
    try {
      await readerApi.updateChapterReadStatus(bookId, chapter, read)
      await chapterListQuery.refetch()
      if (recapsVisible) await summaryCollectionQuery.refetch()
      setActionStatus(`${unitLabel} ${chapter} marked ${read ? "as read" : "unread"}.`)
    } catch {
      setActionError({ message: `Could not update ${unitLabel.toLowerCase()} ${chapter}. Your read status has not been saved.`, retry: () => void setChapterRead(chapter, read) })
    } finally {
      setReadBusy(null)
    }
  }

  async function markBookRead() {
    if (readBusy || deleteBusy) return
    setReadBusy("book")
    setActionStatus(null)
    setActionError(null)
    try {
      await readerApi.markBookRead(bookId)
      await chapterListQuery.refetch()
      if (recapsVisible) await summaryCollectionQuery.refetch()
      setActionStatus("Book marked as read.")
    } catch {
      setActionError({ message: "Could not mark the book as read. Your read status has not been saved.", retry: () => void markBookRead() })
    } finally {
      setReadBusy(null)
    }
  }

  async function removeChapter(chapterNumber: number) {
    if (readBusy || deleteBusy || !canRemoveChapter(book, chapterNumber)) return
    const confirmed = await confirm({
      title: `Remove ${unitLabel} ${chapterNumber}?`,
      body: `Remove ${unitLabel} ${chapterNumber}? This deletes its manuscript text, scenes, notes, comments, and chapter intelligence. This cannot be undone.`,
      confirmLabel: `Remove ${unitLabel.toLowerCase()}`,
      tone: "danger",
    })
    if (!confirmed) return

    setDeleteBusy(`chapter:${chapterNumber}`)
    setActionStatus(null)
    setActionError(null)
    try {
      await booksApi.deleteChapter(bookId, chapterNumber)
      await Promise.all([bookQuery.refetch(), chapterListQuery.refetch()])
      setActionStatus(`${unitLabel} ${chapterNumber} removed.`)
    } catch {
      setActionError({ message: `Could not remove ${unitLabel.toLowerCase()} ${chapterNumber}. Try again.`, retry: () => void removeChapter(chapterNumber) })
    } finally {
      setDeleteBusy(null)
    }
  }

  const unitLabel = storyUnitLabel(book?.work_type)
  const processedCount = useMemo(() => (data?.chapters ?? []).filter((chapter) => chapter.processed).length, [data])
  const chapterCount = data?.chapters.length ?? 0
  const visibleChapters = useMemo(() => filterChapterList(data?.chapters ?? [], search, statusFilter), [data, search, statusFilter])
  const allRead = chapterCount > 0 && data!.chapters.every((chapter) => chapter.read)
  const bookContext = book?.title ? `${book.title} · ` : ""
  const subtitle = book?.mode === "author"
    ? `${bookContext}Processed and queued ${unitLabel.toLowerCase()}s across the manuscript.`
    : `${bookContext}The full ${unitLabel.toLowerCase()} list with your current read status.`

  async function toggleRecaps() {
    if (recapsVisible) {
      setRecapsVisible(false)
      return
    }
    setRecapsVisible(true)
    await summaryCollectionQuery.refetch()
  }

  return (
    <div data-chapter-navigator className={`min-h-screen transition-colors ${isDark ? "bg-[#071211] text-slate-100" : "bg-stone-50 text-stone-950"}`}>
      <div className="mx-auto max-w-[100rem] px-4 pb-20 pt-5 sm:px-6 lg:px-8">
        <div className="space-y-6">
          <AuthorToolsNav
            bookId={bookId}
            active="chapters"
            isDark={isDark}
            bookData={book}
            title="Chapter navigator"
            variant="bar"
          />

          <main className="min-w-0 space-y-5">
            <ChaptersPageHeader
              title={`${unitLabel}s`}
              subtitle={subtitle}
              processedCount={!data ? null : processedCount}
              totalCount={!data ? null : chapterCount}
              isDark={isDark}
              backLabel="Home"
              homeHref={`/${bookId}`}
              primaryActionLabel={allRead ? "Book marked as read" : "Mark book as read"}
              primaryActionBusyLabel="Marking..."
              primaryActionBusy={readBusy === "book"}
              primaryActionDisabled={!chapterCount || allRead || readBusy !== null || deleteBusy !== null || Boolean(chapterListError)}
              onBack={() => router.back()}
              onPrimaryAction={() => void markBookRead()}
            />

            {bookQuery.isError ? <ErrorCard variant="compact" isDark={isDark} message="Book details could not be loaded. You can still open the available chapters." onRetry={() => void bookQuery.refetch()} /> : null}
            {chapterListError ? <ErrorCard variant="compact" isDark={isDark} message={data ? "Could not refresh the chapter list. Showing the last loaded version." : chapterListError} onRetry={() => void chapterListQuery.refetch()} /> : null}
            {actionError ? <div role="alert"><ErrorCard variant="compact" isDark={isDark} message={actionError.message} onRetry={actionError.retry} /></div> : null}

            {actionStatus ? (
              <div role="status" className={`border-l-2 px-4 py-3 text-sm ${isDark ? "border-teal-400 bg-teal-500/10 text-slate-200" : "border-teal-700 bg-teal-50 text-stone-700"}`}>
                {actionStatus}
              </div>
            ) : null}

            {chapterListLoading ? (
              <LoadingChapterList unitLabel={unitLabel} isDark={isDark} />
            ) : null}

            {!chapterListLoading && !chapterListError && chapterCount === 0 ? (
              <section className={`border-t px-1 py-10 ${isDark ? "border-white/[0.08] text-slate-400" : "border-stone-200 text-stone-500"}`}>
                <h2 className={`text-base font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>No {unitLabel.toLowerCase()}s yet</h2>
                <p className="mt-2 text-sm">Your processed and queued {unitLabel.toLowerCase()}s will appear here. Return to the book overview to check manuscript progress.</p>
                <Link href={`/${bookId}`} className={`mt-4 inline-flex min-h-10 items-center text-sm font-semibold underline underline-offset-4 ${isDark ? "text-teal-300" : "text-teal-800"}`}>Open book overview</Link>
              </section>
            ) : null}

            {chapterCount > 0 ? (
              <>
                <div className="flex flex-wrap items-end gap-3">
                  <label className="w-full min-w-0 text-sm font-medium sm:flex-1">
                    Find a {unitLabel.toLowerCase()}
                    <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Title, number or tag" className={`mt-1 block min-h-11 w-full min-w-0 rounded-sm border px-3 text-sm ${isDark ? "border-white/15 bg-white/5 text-slate-100 placeholder:text-slate-400" : "border-stone-300 bg-white text-stone-900 placeholder:text-stone-500"}`} />
                  </label>
                  <div className="text-sm font-medium">
                    <label htmlFor="chapter-status-filter">Status</label>
                    <select id="chapter-status-filter" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as ChapterStatusFilter)} className={`mt-1 block min-h-11 rounded-sm border px-3 text-sm ${isDark ? "border-white/15 bg-[#142321] text-slate-100" : "border-stone-300 bg-white text-stone-900"}`}>
                      <option value="all">All statuses</option><option value="unread">Unread</option><option value="read">Read</option><option value="queued">Queued</option>
                    </select>
                  </div>
                  <button type="button" aria-expanded={recapsVisible} aria-controls="chapter-results" onClick={() => void toggleRecaps()} className={`min-h-11 px-2 text-sm font-semibold ${isDark ? "text-teal-300" : "text-teal-800"}`}>
                    {recapsVisible ? `Hide ${unitLabel.toLowerCase()} recaps` : `Show ${unitLabel.toLowerCase()} recaps`}
                  </button>
                </div>
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  <p aria-live="polite">{visibleChapters.length} of {chapterCount} {unitLabel.toLowerCase()}{chapterCount === 1 ? "" : "s"}</p>
                  {search || statusFilter !== "all" ? <button type="button" onClick={() => { setSearch(""); setStatusFilter("all") }} className={`min-h-10 font-semibold underline underline-offset-4 ${isDark ? "text-teal-300" : "text-teal-800"}`}>Clear filters</button> : null}
                </div>
                {recapsVisible && summaryCollectionQuery.isFetching ? <p role="status" className="text-sm">Loading recaps…</p> : null}
                {recapsVisible && summaryCollectionQuery.isError ? <ErrorCard variant="compact" isDark={isDark} message="Could not load chapter recaps. Your chapter list is still available." onRetry={() => void summaryCollectionQuery.refetch()} /> : null}
                {recapsVisible && summaryCollectionQuery.isSuccess && !summaryCollectionQuery.isFetching && summaryCollectionQuery.data.summaries.length === 0 ? <p className="text-sm">No chapter recaps are available yet.</p> : null}
                <div id="chapter-results">
                {visibleChapters.length === 0 ? <p className="border-t border-current/20 py-8 text-sm">No {unitLabel.toLowerCase()}s match these filters. Try another title or clear the filters.</p> : null}
                {visibleChapters.length > 0 ? <ChapterList
                  chapters={visibleChapters}
                  summaries={recapsVisible ? summaryCollectionQuery.data?.summaries ?? [] : []}
                  unitLabel={unitLabel}
                  isDark={isDark}
                  readBusyKey={readBusy}
                  deleteBusyKey={deleteBusy}
                  onOpenChapter={(chapterNumber) => router.push(`/${bookId}/chapter/${chapterNumber}`)}
                  onToggleChapterRead={(chapterNumber, nextRead) => void setChapterRead(chapterNumber, nextRead)}
                  onDeleteChapter={(chapterNumber) => void removeChapter(chapterNumber)}
                  canDeleteChapter={(chapterNumber) => canRemoveChapter(book, chapterNumber)}
                /> : null}
                </div>
              </>
            ) : null}
          </main>
        </div>
      </div>
    </div>
  )
}

function LoadingChapterList({ unitLabel, isDark }: { unitLabel: string; isDark: boolean }) {
  return (
    <section role="status" aria-busy="true" aria-label={`Loading ${unitLabel.toLowerCase()} list`}>
      <div className={`text-sm font-semibold ${isDark ? "text-slate-200" : "text-stone-800"}`}>{unitLabel}s</div>
      <div className={`mt-3 divide-y border-y ${isDark ? "divide-white/[0.08] border-white/[0.08]" : "divide-stone-200 border-stone-200"}`}>
        {Array.from({ length: 3 }, (_, index) => (
          <div key={index} className="grid gap-3 px-1 py-4 xl:grid-cols-[4.5rem_minmax(0,1fr)_minmax(13rem,0.65fr)_14rem] xl:items-center xl:gap-5">
            <Skeleton className="h-4 w-10" />
            <div className="space-y-2">
              <Skeleton className="h-5 w-44" />
              <Skeleton className="h-3 w-24" />
            </div>
            <Skeleton className="h-3 w-48" />
            <div className="flex gap-2 md:justify-end">
              <Skeleton className="h-9 w-16 rounded-sm" />
              <Skeleton className="h-9 w-24 rounded-sm" />
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
