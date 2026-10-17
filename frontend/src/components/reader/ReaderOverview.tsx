"use client"

import React, { useState } from "react"

import { RecallCard } from "@/components/intelligence/RecallCard"
import { CoverEditOverlay } from "@/components/ui/CoverEditOverlay"
import { SmartBookCover } from "@/components/ui/SmartBookCover"
import { ErrorCard } from "@/components/ui/ErrorCard"
import { WorkspaceModeSwitcher } from "@/components/reader/WorkspaceModeSwitcher"
import { useRecall } from "@/lib/hooks/useRecall"
import { buildManuscriptRecap } from "@/lib/utils/summaries"
import { cn } from "@/lib/utils/text"
import { chapterKindLabel } from "@/lib/utils/chapterLabels"
import {
  buildReaderChapterPreview,
  estimateChapterRemainingReadingMinutes,
  estimateRemainingReadingMinutes,
  formatBookFormatLabel,
  formatReadingDuration,
} from "@/lib/utils/readerOverview"
import type { Book, BookNote, SavedQuote } from "@/types/book"
import type { ChapterListResponse, ReadingProgress, SummaryCollectionResponse } from "@/types/reader"

type ReaderBookmarkSnapshot = {
  chapter: number
  chapterTitle: string | null
  scrollPct: number
  savedAt: string
}

type ReaderOverviewProps = {
  bookId: string
  book: Book
  activeBookMode: "reader" | "author"
  progress: ReadingProgress | null
  chapterList: ChapterListResponse | null
  summaryCollection: SummaryCollectionResponse | null
  bookNotes: BookNote[]
  savedQuotes: SavedQuote[]
  savedItemsLoading?: boolean
  savedItemsError?: boolean
  onRetrySavedItems?: () => void
  bookmark: ReaderBookmarkSnapshot | null
  isDark: boolean
  modeSaving: boolean
  canUseAuthorMode: boolean
  greetingName?: string
  onModeChange: (nextMode: "reader" | "author") => void
  onToggleTheme: () => void
  onNavigate: (href: string) => void
  onContinueReading: () => void
}

export function ReaderOverview({
  bookId,
  book,
  activeBookMode,
  progress,
  chapterList,
  summaryCollection,
  bookNotes,
  savedQuotes,
  savedItemsLoading = false,
  savedItemsError = false,
  onRetrySavedItems,
  bookmark,
  isDark,
  modeSaving,
  canUseAuthorMode,
  onModeChange,
  onToggleTheme,
  onNavigate,
  onContinueReading,
}: ReaderOverviewProps) {
  const [searchQuery, setSearchQuery] = useState("")
  const [coverUrlOverride, setCoverUrlOverride] = useState<string | null>(null)
  const { recall, lastChapter, show: showRecall, dismiss: dismissRecall } = useRecall(bookId)
  const chapters = chapterList?.chapters ?? []
  const continueChapter = progress?.current_chapter ?? bookmark?.chapter ?? 1
  const recallChapter = typeof lastChapter === "number" ? lastChapter : progress?.current_chapter ?? bookmark?.chapter ?? null
  const percentComplete = Math.max(0, Math.min(100, Math.round(progress?.percent_complete ?? book.progress_pct ?? 0)))
  const currentChapter = chapters.find((chapter) => chapter.number === continueChapter) ?? null
  const previewChapters = buildReaderChapterPreview(chapters, continueChapter)
  const remainingMinutes = estimateRemainingReadingMinutes(book, progress)
  const chapterScroll = Math.max(0, Math.min(100, Math.round((bookmark?.scrollPct ?? progress?.scroll_pct ?? 0) * 100)))
  const chapterMinutesLeft = bookmark
    ? estimateChapterRemainingReadingMinutes(currentChapter?.word_count, bookmark.scrollPct)
    : null
  const summaryReadyCount = (summaryCollection?.summaries ?? []).filter((summary) => summary.available).length
  const manuscriptRecap = buildManuscriptRecap(summaryCollection)
  const recentNote = [...bookNotes].sort((left, right) => (
    new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime()
  ))[0] ?? null
  const recentNotePreview = recentNote ? stripMarkup(recentNote.body) : ""
  const aboutCopy = book.public_description?.trim() || buildAboutFallback(book)
  const bookmarkCount = bookmark ? 1 : 0
  const startedLabel = formatDateLabel(book.created_at)
  const lastOpenedLabel = bookmark?.savedAt ? formatRecentDateLabel(bookmark.savedAt) : "Not opened yet"
  const formatLabel = formatBookFormatLabel(book.format)
  const chapterCount = chapters.length || book.total_chapters || 0
  const chapterUnit = book.work_type === "screenplay" ? "Scene" : "Chapter"
  const currentChapterBaseLabel = currentChapter?.printed_label || chapterKindLabel(currentChapter?.chapter_kind, continueChapter, chapterUnit)
  const currentChapterLabel = currentChapter?.title?.trim() && currentChapter.title.trim() !== currentChapterBaseLabel
    ? `${currentChapterBaseLabel} - ${currentChapter.title}`
    : currentChapterBaseLabel
  const noteCountLabel = savedItemsLoading ? "Loading notes" : savedItemsError ? "Notes unavailable" : `${bookNotes.length} note${bookNotes.length === 1 ? "" : "s"}`
  const highlightCountLabel = savedItemsLoading ? "Loading highlights" : savedItemsError ? "Highlights unavailable" : `${savedQuotes.length} highlight${savedQuotes.length === 1 ? "" : "s"}`
  const summaryCountLabel = `${summaryReadyCount} ready`
  const processedChapterCount = chapters.filter((chapter) => chapter.processed).length
  const readChapterCount = chapters.filter((chapter) => chapter.read).length
  const storyMemoryCoverage = chapterCount > 0
    ? Math.min(100, Math.round((summaryReadyCount / chapterCount) * 100))
    : 0
  const recentActivities = [
    bookmark ? { title: `Read ${chapterUnit} ${bookmark.chapter}`, body: bookmark.chapterTitle || currentChapter?.title || "Saved reader position", time: lastOpenedLabel } : null,
    savedQuotes[0] ? { title: "Saved a quote", body: truncatePreview(savedQuotes[0].quote_text, 82), time: formatRecentDateLabel(savedQuotes[0].created_at) } : null,
    recentNote ? { title: "Added a note", body: truncatePreview(recentNotePreview, 82), time: formatRecentDateLabel(recentNote.updated_at) } : null,
  ].filter(Boolean) as Array<{ title: string; body: string; time: string }>

  const submitSearch = () => {
    const trimmed = searchQuery.trim()
    const href = trimmed
      ? `/${bookId}/search?q=${encodeURIComponent(trimmed)}`
      : `/${bookId}/search`
    onNavigate(href)
  }

  return (
    <div className="space-y-5" data-reader-overview>
      <header className={cn("flex flex-wrap items-end justify-between gap-4 border-b pb-4", isDark ? "border-white/10" : "border-slate-200")}>
        <div>
          <h1 className="font-serif text-2xl font-semibold tracking-tight sm:text-3xl">Book overview</h1>
          <p className={cn("mt-1 text-sm", mutedClass(isDark))}>Continue reading, revisit a chapter, or find your notes.</p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <WorkspaceModeSwitcher isDark={isDark} activeMode={activeBookMode} modeSaving={modeSaving} writingAvailable={canUseAuthorMode} onModeChange={onModeChange} />
          <button type="button" onClick={onToggleTheme} className={softButtonClass(isDark)} aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}><ReaderIcon name={isDark ? "sun" : "moon"} /></button>
        </div>
      </header>

      {showRecall && recall ? <RecallCard recall={recall} lastChapter={recallChapter} onDismiss={dismissRecall} onContinue={onContinueReading} /> : null}

      <section className={readerPanelClass(isDark)} aria-label="Current book">
        <div className="grid items-start gap-5 md:grid-cols-[minmax(10rem,15rem)_minmax(0,1fr)] md:gap-7 xl:grid-cols-[minmax(12rem,17rem)_minmax(0,1fr)] xl:gap-9">
          <SmartBookCover src={coverUrlOverride !== null ? coverUrlOverride : book.cover_url} title={book.title} isDark={isDark} className="aspect-[0.72] w-full max-w-[17rem] overflow-hidden rounded-sm shadow-xl shadow-black/20 md:row-span-2"
            overlay={<CoverEditOverlay bookId={bookId} isDark={isDark} hasCover={Boolean(coverUrlOverride !== null ? coverUrlOverride : book.cover_url)} onCoverUpdated={(updated) => setCoverUrlOverride(updated.cover_url ?? null)} />} />
          <div className="min-w-0 md:pt-1">
            <h2 className="break-words font-serif text-2xl leading-tight sm:text-3xl xl:text-4xl">{book.title}</h2>
            <p className={cn("mt-2 text-sm", mutedClass(isDark))}>{book.author || "Unknown author"}{book.genre ? ` · ${book.genre}` : ""}</p>
            <p className={cn("mt-3 hidden max-w-3xl text-sm leading-6 sm:block", mutedClass(isDark))}>{aboutCopy}</p>
          </div>
          <div className="space-y-4 md:col-start-2">
            <p className={cn("text-sm leading-6 sm:hidden", mutedClass(isDark))}>{aboutCopy}</p>
            <div className={cn("border-t pt-4", isDark ? "border-white/10" : "border-slate-200")}>
              <p className={cn("mb-2 text-xs font-medium uppercase tracking-[0.16em]", mutedClass(isDark))}>Continue reading</p>
              <div className="flex flex-wrap justify-between gap-2 text-sm">
                <span>{chapters.length ? currentChapterLabel : "No chapters available yet"}</span>
                <span className={mutedClass(isDark)}>{percentComplete}% read · {formatReadingDuration(remainingMinutes)} left</span>
              </div>
              <div className={cn("mt-3 h-1.5 overflow-hidden rounded-full", isDark ? "bg-white/10" : "bg-slate-200")}><div className="h-full rounded-full bg-teal-600" style={{ width: `${percentComplete}%` }} /></div>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <button type="button" disabled={!chapters.length} onClick={onContinueReading} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-sm bg-teal-800 px-4 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-50"><ReaderIcon name="book" />Continue Reading</button>
              <button type="button" onClick={() => onNavigate(`/${bookId}/chapters`)} className={softButtonClass(isDark)}>Browse chapter recaps</button>
            </div>
            <p className={cn("text-xs", mutedClass(isDark))}>{summaryCountLabel} chapter recaps · {highlightCountLabel} · {noteCountLabel}</p>
          </div>
        </div>
      </section>

      <form role="search" aria-label="Search this book" onSubmit={(event) => { event.preventDefault(); submitSearch() }} className={cn(readerPanelClass(isDark), "space-y-2")}>
        <label htmlFor="overview-book-search" className="block text-sm font-medium">Search this book, notes, or summaries</label>
        <div className="flex gap-2">
          <input id="overview-book-search" type="search" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search words, people, or places" className={cn("min-h-11 min-w-0 flex-1 rounded-sm border bg-transparent px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600", isDark ? "border-white/15 placeholder:text-slate-400" : "border-slate-300 placeholder:text-slate-500")} />
          <button type="submit" className={softButtonClass(isDark)}>Search</button>
        </div>
      </form>

      <div className="grid gap-5 lg:grid-cols-2">
        <section className={readerPanelClass(isDark)}>
          <h2 className="font-serif text-lg font-semibold">Chapters</h2>
          <div className={cn("mt-3 divide-y", isDark ? "divide-white/10" : "divide-slate-200")}>
            {previewChapters.length ? previewChapters.map((chapter) => (
              <button key={chapter.number} type="button" onClick={() => onNavigate(`/${bookId}/chapter/${chapter.number}`)} aria-current={chapter.number === continueChapter ? "location" : undefined}
                className={cn("flex min-h-14 w-full items-center justify-between gap-4 px-2 py-3 text-left focus-visible:ring-2 focus-visible:ring-teal-600", chapter.number === continueChapter ? isDark ? "bg-teal-900/30" : "bg-teal-50" : isDark ? "hover:bg-white/5" : "hover:bg-slate-50")}>
                <span className="min-w-0"><span className={cn("block text-xs", mutedClass(isDark))}>{chapter.parent_part_title ? `${chapter.parent_part_title} · ` : ""}{chapter.printed_label || chapterKindLabel(chapter.chapter_kind, chapter.number, chapterUnit)}</span><span className="mt-1 block break-words text-sm font-medium">{chapter.title || chapter.printed_label || chapterKindLabel(chapter.chapter_kind, chapter.number, chapterUnit)}</span></span>
                <span className={cn("shrink-0 text-xs", mutedClass(isDark))}>{chapter.number === continueChapter ? "Current" : chapter.read ? "Read" : "Unread"}</span>
              </button>
            )) : <p className={cn("py-4 text-sm leading-6", mutedClass(isDark))}>{book.status === "ready" ? "This book has no chapters yet. Browse chapters to see available content." : "Chapters will appear here as processing finishes."}</p>}
          </div>
          <button type="button" onClick={() => onNavigate(`/${bookId}/chapters`)} className={readerFooterLinkClass(isDark)}>View all chapters <ReaderIcon name="arrow" /></button>
        </section>
        <section className={readerPanelClass(isDark)}>
          <h2 className="font-serif text-lg font-semibold">Notes &amp; highlights</h2>
          {savedItemsError && onRetrySavedItems ? <div className="mt-3"><ErrorCard isDark={isDark} variant="compact" message="Saved items could not be refreshed. Retry or open your notes and highlights directly." onRetry={onRetrySavedItems} /></div> : null}
          <p className={cn("mt-2 text-sm", mutedClass(isDark))}>{noteCountLabel} · {highlightCountLabel} · {bookmarkCount} saved reading position</p>
          {recentNote ? <div className={cn("mt-4 border-l-2 pl-4", isDark ? "border-slate-600" : "border-slate-300")}>
            <p className={cn("text-xs", mutedClass(isDark))}>Recent note · {recentNote.chapter_number ? `${chapterUnit} ${recentNote.chapter_number}` : "Whole book"} · {formatRecentDateLabel(recentNote.updated_at)}</p>
            <blockquote className="mt-2 break-words text-sm leading-7">{truncatePreview(recentNotePreview)}</blockquote>
          </div> : <p className={cn("mt-4 text-sm leading-6", mutedClass(isDark))}>Save a note while reading and it will appear here for quick recall.</p>}
          <div className="mt-5 grid gap-2 sm:grid-cols-2">
            <button type="button" onClick={() => onNavigate(`/${bookId}/notes`)} className={softButtonClass(isDark)}>Open Notes</button>
            <button type="button" onClick={() => onNavigate("/quotes")} className={softButtonClass(isDark)}>Open Highlights</button>
          </div>
          <div className={cn("mt-5 border-t pt-4", isDark ? "border-white/10" : "border-slate-200")}>
            <h3 className="text-sm font-semibold">Ask LoreVia</h3>
            <p className={cn("mt-2 text-sm leading-6", mutedClass(isDark))}>Ask grounded, spoiler-safe questions about chapters you have already reached.</p>
            <button type="button" onClick={() => onNavigate(`/${bookId}/ask`)} className={readerFooterLinkClass(isDark)}>Ask about this book <ReaderIcon name="arrow" /></button>
          </div>
        </section>
      </div>

      <details className={readerPanelClass(isDark)} open>
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-serif text-lg font-semibold">
          <span>Reading details &amp; story memory</span>
          <span aria-hidden="true" className={cn("text-lg font-normal", mutedClass(isDark))}>⌄</span>
        </summary>
        <div className="mt-5 grid gap-6 lg:grid-cols-2">
          <section>
            <h2 className="text-sm font-semibold">Reading details</h2>
            <dl className="mt-3">
              <DetailRow isDark={isDark} label="Current chapter" value={chapters.length ? currentChapterLabel : "Not available"} />
              <DetailRow isDark={isDark} label="Chapter position" value={`${chapterScroll}%`} />
              <DetailRow isDark={isDark} label="Time left in chapter" value={formatReadingDuration(chapterMinutesLeft)} />
              <DetailRow isDark={isDark} label="Last opened" value={lastOpenedLabel} />
              <DetailRow isDark={isDark} label="Added to library" value={startedLabel} />
              <DetailRow isDark={isDark} label="Format" value={formatLabel} />
              <DetailRow isDark={isDark} label="Total chapters" value={String(chapterCount)} />
            </dl>
          </section>
          <section>
            <h2 className="text-sm font-semibold">Story Memory</h2>
            <p className={cn("mt-3 text-sm leading-6", mutedClass(isDark))}>{storyMemoryCoverage}% summary coverage, based on chapters with an available recap.</p>
            <dl className="mt-3">
              <DetailRow isDark={isDark} label="Summaries ready" value={String(summaryReadyCount)} />
              <DetailRow isDark={isDark} label="Chapters processed" value={String(processedChapterCount)} />
              <DetailRow isDark={isDark} label="Chapters read" value={String(readChapterCount)} />
            </dl>
            <h3 className="mt-5 text-sm font-semibold">Manuscript recap</h3>
            <p className={cn("mt-2 text-sm leading-7", mutedClass(isDark))}>{manuscriptRecap?.content ?? "A manuscript recap will appear here when chapter recaps are ready."}</p>
            {manuscriptRecap ? <p className={cn("mt-2 text-xs", mutedClass(isDark))}>Compiled from {manuscriptRecap.chapterCount} available chapter recaps.</p> : null}
          </section>
          <section className="lg:col-span-2">
            <h2 className="text-sm font-semibold">Recent reading activity</h2>
            {recentActivities.length ? <ul className="mt-3 grid gap-4 sm:grid-cols-3">{recentActivities.map((activity) => <li key={`${activity.title}-${activity.time}`}>
              <p className="text-sm font-medium">{activity.title} <span className={cn("text-xs font-normal", mutedClass(isDark))}>· {activity.time}</span></p>
              <p className={cn("mt-1 text-sm leading-6", mutedClass(isDark))}>{activity.body}</p>
            </li>)}</ul> : <p className={cn("mt-3 text-sm", mutedClass(isDark))}>Reading activity will appear after you read, save a quote, or add a note.</p>}
          </section>
        </div>
      </details>
    </div>
  )
}

function DetailRow({ isDark, label, value }: { isDark: boolean; label: string; value: string }) {
  return <div className={cn("flex items-start justify-between gap-4 border-b py-3 text-sm", isDark ? "border-white/10" : "border-slate-200")}><dt className={mutedClass(isDark)}>{label}</dt><dd className="min-w-0 break-words text-right font-medium">{value}</dd></div>
}

function readerPanelClass(isDark: boolean) {
  return cn("min-w-0 rounded-md border p-4 sm:p-5", isDark ? "border-white/10 bg-[#0d1720]" : "border-slate-200 bg-white")
}

function softButtonClass(isDark: boolean) {
  return cn("inline-flex min-h-11 items-center justify-center gap-2 rounded-sm border px-4 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-teal-600", isDark ? "border-white/15 text-slate-200 hover:bg-white/5" : "border-slate-300 text-slate-700 hover:bg-slate-50")
}

function readerFooterLinkClass(isDark: boolean) {
  return cn("mt-3 inline-flex min-h-11 items-center gap-2 text-sm font-semibold focus-visible:ring-2 focus-visible:ring-teal-600", isDark ? "text-teal-300 hover:text-teal-200" : "text-teal-800 hover:text-teal-700")
}

function mutedClass(isDark: boolean) {
  return isDark ? "text-slate-300" : "text-slate-600"
}

function stripMarkup(value: string) {
  return value.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim()
}

function truncatePreview(value: string, max = 160) {
  if (!value) return ""
  return value.length <= max ? value : `${value.slice(0, max - 3)}...`
}

function buildAboutFallback(book: Book) {
  const authorLabel = book.author?.trim()
  const genreLabel = book.genre?.trim()
  const details = [authorLabel ? `by ${authorLabel}` : null, genreLabel].filter(Boolean).join(". ")
  return details ? `${book.title}. ${details}.` : "No description has been added for this book."
}

function formatDateLabel(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Unavailable"
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}

function formatRecentDateLabel(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Unavailable"

  const now = new Date()
  const sameDay = now.toDateString() === date.toDateString()
  if (sameDay) return "Today"

  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

type IconName = "arrow" | "bookmark" | "book" | "list" | "moon" | "note" | "progress" | "quote" | "search" | "spark" | "summary" | "sun"

function ReaderIcon({ name, className = "h-4 w-4" }: { name: IconName; className?: string }) {
  const common = { className, fill: "none", viewBox: "0 0 24 24", stroke: "currentColor", strokeWidth: 1.8 }

  switch (name) {
    case "arrow":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M13 6l6 6-6 6" /></svg>
    case "bookmark":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M7 5h10v15l-5-3-5 3V5z" /></svg>
    case "book":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M6 4h9a3 3 0 013 3v13H8a2 2 0 01-2-2V4z" /><path strokeLinecap="round" strokeLinejoin="round" d="M8 18h10M9 8h5" /></svg>
    case "list":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01" /></svg>
    case "moon":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M20 15.5A8 8 0 018.5 4 8.5 8.5 0 1020 15.5z" /></svg>
    case "note":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M7 4h8l3 3v13H7V4z" /><path strokeLinecap="round" strokeLinejoin="round" d="M15 4v4h4M9 13h6M9 16h4" /></svg>
    case "progress":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M5 19V9M10 19V5M15 19v-7M20 19V8M4 19h17" /></svg>
    case "quote":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M9 9H6v4h3v5l-4-3V9a3 3 0 013-3h1v3zM18 9h-3v4h3v5l-4-3V9a3 3 0 013-3h1v3z" /></svg>
    case "search":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M11 18a7 7 0 100-14 7 7 0 000 14zM16 16l4 4" /></svg>
    case "spark":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3zM18 16l.8 2.2L21 19l-2.2.8L18 22l-.8-2.2L15 19l2.2-.8L18 16z" /></svg>
    case "summary":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M7 5h10M7 9h10M7 13h6M7 17h8" /></svg>
    case "sun":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M12 4V2M12 22v-2M4 12H2M22 12h-2M5 5l-1.4-1.4M20.4 20.4L19 19M19 5l1.4-1.4M3.6 20.4L5 19M12 16a4 4 0 100-8 4 4 0 000 8z" /></svg>
    default:
      return null
  }
}
