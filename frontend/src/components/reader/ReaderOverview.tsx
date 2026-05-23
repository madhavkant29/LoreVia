"use client"

import React from "react"
import { useState } from "react"

import { RecallCard } from "@/components/intelligence/RecallCard"
import { SmartBookCover } from "@/components/ui/SmartBookCover"
import { useRecall } from "@/lib/hooks/useRecall"
import { cn } from "@/lib/utils/text"
import {
  buildReaderChapterPreview,
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
  bookmark: ReaderBookmarkSnapshot | null
  isDark: boolean
  modeSaving: boolean
  canUseAuthorMode: boolean
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
  const { recall, lastChapter, show: showRecall, dismiss: dismissRecall } = useRecall(bookId)
  const chapters = chapterList?.chapters ?? []
  const continueChapter = progress?.current_chapter ?? bookmark?.chapter ?? 1
  const recallChapter = typeof lastChapter === "number" ? lastChapter : progress?.current_chapter ?? bookmark?.chapter ?? null
  const percentComplete = Math.max(0, Math.min(100, Math.round(progress?.percent_complete ?? book.progress_pct ?? 0)))
  const currentChapter = chapters.find((chapter) => chapter.number === continueChapter) ?? null
  const previewChapters = buildReaderChapterPreview(chapters, continueChapter)
  const remainingMinutes = estimateRemainingReadingMinutes(book, progress)
  const chapterScroll = Math.max(0, Math.min(100, Math.round((bookmark?.scrollPct ?? 0) * 100)))
  const chapterMinutesLeft = chapterScroll > 0 ? Math.max(3, Math.round((100 - chapterScroll) / 100 * 14)) : null
  const summaryReadyCount = (summaryCollection?.summaries ?? []).filter((summary) => summary.available).length
  const recentNote = [...bookNotes].sort((left, right) => (
    new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime()
  ))[0] ?? null
  const recentNotePreview = recentNote ? stripMarkup(recentNote.body) : ""
  const aboutCopy = book.public_description?.trim() || buildAboutFallback(book)
  const bookmarkCount = bookmark ? 1 : 0
  const startedLabel = formatDateLabel(book.created_at)
  const lastOpenedLabel = bookmark?.savedAt ? formatRecentDateLabel(bookmark.savedAt) : "Today"
  const formatLabel = formatBookFormatLabel(book.format)
  const chapterCount = chapters.length || book.total_chapters || 0
  const chapterUnit = book.work_type === "screenplay" ? "Scene" : "Chapter"
  const currentChapterLabel = currentChapter?.title?.trim()
    ? `${chapterUnit} ${continueChapter} - ${currentChapter.title}`
    : `${chapterUnit} ${continueChapter}`
  const nextChapter = chapters.find((chapter) => chapter.number > continueChapter) ?? null
  const noteCountLabel = `${bookNotes.length} note${bookNotes.length === 1 ? "" : "s"}`
  const highlightCountLabel = `${savedQuotes.length} highlight${savedQuotes.length === 1 ? "" : "s"}`
  const summaryCountLabel = summaryReadyCount > 0 ? `${summaryReadyCount} ready` : "Syncing"

  const submitSearch = () => {
    const trimmed = searchQuery.trim()
    const href = trimmed
      ? `/${bookId}/search?q=${encodeURIComponent(trimmed)}`
      : `/${bookId}/search`
    onNavigate(href)
  }

  return (
    <div className="relative isolate space-y-5">
      <div className={cn("pointer-events-none absolute inset-x-0 top-0 -z-10 h-64 blur-3xl", isDark ? "bg-[radial-gradient(circle_at_20%_0%,rgba(13,148,136,0.2),transparent_48%),radial-gradient(circle_at_80%_0%,rgba(148,163,184,0.12),transparent_42%)]" : "bg-[radial-gradient(circle_at_20%_0%,rgba(13,148,136,0.12),transparent_48%),radial-gradient(circle_at_80%_0%,rgba(120,113,108,0.08),transparent_42%)]")} />

      <section className={cn("relative overflow-hidden rounded-[1.9rem] border p-4 sm:p-5", isDark ? "border-white/[0.07] bg-[#0b1018]" : "border-slate-200 bg-white")}>
        <div className={cn("pointer-events-none absolute right-0 top-0 h-40 w-40 rounded-full blur-3xl", isDark ? "bg-teal-500/12" : "bg-teal-100/70")} />
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <button type="button" onClick={() => onNavigate("/library")} className={cn("transition", isDark ? "text-teal-300 hover:text-teal-200" : "text-teal-800 hover:text-teal-900")}>
                My Books
              </button>
              <span className={isDark ? "text-slate-600" : "text-slate-300"}>/</span>
              <span className={isDark ? "text-slate-300" : "text-slate-600"}>{book.title}</span>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className={cn("inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em]", isDark ? "border-emerald-400/18 bg-emerald-500/10 text-emerald-300" : "border-emerald-200 bg-emerald-50 text-emerald-700")}>
                <span className="h-2 w-2 rounded-full bg-current" />
                Reader mode active
              </span>
              {bookmark ? (
                <span className={cn("inline-flex rounded-full border px-3 py-1 text-[11px] font-semibold", isDark ? "border-white/10 bg-white/[0.04] text-slate-300" : "border-slate-200 bg-slate-50 text-slate-600")}>
                  Bookmark saved in {chapterUnit.toLowerCase()} {bookmark.chapter}
                </span>
              ) : null}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {canUseAuthorMode ? (
              <div className={cn("inline-flex h-11 overflow-hidden rounded-full border", isDark ? "border-white/10 bg-white/[0.04]" : "border-slate-200 bg-slate-50")}>
                {(["reader", "author"] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => onModeChange(mode)}
                    disabled={modeSaving}
                    className={cn(
                      "px-4 text-xs font-semibold uppercase tracking-[0.18em] transition",
                      mode === "reader" ? "rounded-l-full" : "rounded-r-full",
                      activeBookMode === mode
                        ? isDark ? "bg-teal-800 text-white" : "bg-teal-800 text-white"
                        : isDark ? "text-slate-300 hover:bg-white/[0.06]" : "text-slate-600 hover:bg-white",
                    )}
                  >
                    {mode}
                  </button>
                ))}
              </div>
            ) : null}

            <button
              type="button"
              onClick={onToggleTheme}
              className={cn("flex h-11 w-11 items-center justify-center rounded-full border transition", isDark ? "border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/[0.08]" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50")}
              aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
            >
              <ReaderIcon name={isDark ? "sun" : "moon"} />
            </button>

            <button
              type="button"
              onClick={onContinueReading}
              className={cn("inline-flex h-11 items-center gap-2 rounded-full px-5 text-sm font-semibold shadow-[0_18px_40px_-24px_rgba(15,118,110,0.48)] transition", isDark ? "bg-teal-800 text-white hover:bg-teal-700" : "bg-teal-800 text-white hover:bg-teal-700")}
            >
              <ReaderIcon name="book" className="h-4 w-4" />
              Open Reader
            </button>
          </div>
        </div>

        <div className="mt-5 grid gap-3 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-center">
          <label className={cn("flex min-h-[3.35rem] items-center gap-3 rounded-2xl border px-4", isDark ? "border-white/[0.08] bg-[#090c14] text-slate-200" : "border-slate-200 bg-slate-50 text-slate-800")}>
            <ReaderIcon name="search" className={isDark ? "h-5 w-5 text-slate-500" : "h-5 w-5 text-slate-400"} />
            <input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && submitSearch()}
              placeholder="Search books, authors, or notes..."
              className={cn("w-full bg-transparent text-sm outline-none", isDark ? "placeholder:text-slate-600" : "placeholder:text-slate-400")}
            />
            <button
              type="button"
              onClick={submitSearch}
              className={cn("rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] transition", isDark ? "bg-white/[0.05] text-slate-400 hover:bg-white/[0.08]" : "bg-white text-slate-500 hover:bg-slate-100")}
            >
              Search
            </button>
          </label>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onNavigate(`/${bookId}/summaries`)}
              className={softButtonClass(isDark)}
            >
              <ReaderIcon name="summary" />
              Summaries
            </button>
            <button
              type="button"
              onClick={() => onNavigate(`/${bookId}/notes`)}
              className={softButtonClass(isDark)}
            >
              <ReaderIcon name="note" />
              Notes
            </button>
          </div>
        </div>
      </section>

      {showRecall && recall ? (
        <RecallCard
          recall={recall}
          lastChapter={recallChapter}
          onDismiss={dismissRecall}
          onContinue={onContinueReading}
        />
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.58fr)_minmax(20rem,0.72fr)]">
        <article className={cn("relative overflow-hidden rounded-[1.9rem] border p-5 sm:p-6", isDark ? "border-white/[0.07] bg-[#0d121b]" : "border-slate-200 bg-white")}>
          <div className={cn("pointer-events-none absolute -left-8 top-6 h-32 w-32 rounded-full blur-3xl", isDark ? "bg-teal-500/10" : "bg-teal-100/70")} />
          <div className="grid gap-6 lg:grid-cols-[12rem_minmax(0,1fr)]">
            <SmartBookCover
              src={book.cover_url}
              title={book.title}
              isDark={isDark}
              className={cn("aspect-[0.72] overflow-hidden rounded-[1.5rem] border shadow-[0_28px_70px_-38px_rgba(15,23,42,0.82)]", isDark ? "border-white/10 bg-[#0a0d13]" : "border-slate-200 bg-slate-50")}
            />

            <div className="min-w-0">
              <h1 className={cn("font-serif text-4xl leading-none sm:text-5xl", isDark ? "text-white" : "text-slate-950")}>{book.title}</h1>
              <p className={cn("mt-3 text-xl", isDark ? "text-teal-300" : "text-teal-800")}>{book.author || "Unknown author"}</p>

              <div className="mt-4 flex flex-wrap items-center gap-3">
                <span className={cn("rounded-full px-3 py-1 text-sm font-medium", isDark ? "bg-white/[0.05] text-slate-200" : "bg-slate-100 text-slate-700")}>
                  {book.genre || (book.work_type === "screenplay" ? "Screenplay" : "Fiction")}
                </span>
                <span className={cn("text-sm", isDark ? "text-slate-400" : "text-slate-500")}>
                  {percentComplete}% complete
                </span>
                <span className={cn("text-sm", isDark ? "text-slate-500" : "text-slate-400")}>
                  {currentChapterLabel}
                </span>
              </div>

              <div className="mt-5">
                <div className={cn("h-2 overflow-hidden rounded-full", isDark ? "bg-white/[0.08]" : "bg-slate-100")}>
                  <div
                    className="h-full rounded-full bg-[linear-gradient(90deg,#7c3aed,#a855f7)]"
                    style={{ width: `${percentComplete}%` }}
                  />
                </div>
              </div>

              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={onContinueReading}
                  className={cn("inline-flex h-12 items-center gap-2 rounded-2xl px-5 text-sm font-semibold transition", isDark ? "bg-teal-800 text-white hover:bg-teal-700" : "bg-teal-800 text-white hover:bg-teal-700")}
                >
                  <ReaderIcon name="book" />
                  Continue Reading
                </button>
                <button
                  type="button"
                  onClick={() => onNavigate(`/${bookId}/summaries`)}
                  className={cn("inline-flex h-12 items-center gap-2 rounded-2xl border px-5 text-sm font-semibold transition", isDark ? "border-white/10 bg-white/[0.03] text-slate-100 hover:bg-white/[0.06]" : "border-slate-200 bg-white text-slate-800 hover:bg-slate-50")}
                >
                  <ReaderIcon name="summary" />
                  Open Chapter Summaries
                </button>
                <button
                  type="button"
                  onClick={() => onNavigate("/quotes")}
                  className={cn("flex h-12 w-12 items-center justify-center rounded-2xl border transition", isDark ? "border-white/10 bg-white/[0.03] text-slate-300 hover:bg-white/[0.06]" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50")}
                  aria-label="Open saved highlights"
                >
                  <ReaderIcon name="bookmark" />
                </button>
              </div>

              <div className="mt-6 grid gap-3 sm:grid-cols-3">
                <HeroMetric isDark={isDark} label="Current chapter" value={String(continueChapter)} note={currentChapter?.title || "Resume point"} />
                <HeroMetric isDark={isDark} label="Summaries" value={summaryCountLabel} note="chapter recaps" />
                <HeroMetric isDark={isDark} label="Saved items" value={String(savedQuotes.length + bookNotes.length + bookmarkCount)} note={`${highlightCountLabel} + ${noteCountLabel}`} />
              </div>
            </div>
          </div>
        </article>

        <article className={cn("rounded-[1.9rem] border p-5 sm:p-6", isDark ? "border-white/[0.07] bg-[#0d121b]" : "border-slate-200 bg-white")}>
          <div className="flex items-center justify-between gap-3">
            <span className={cn("inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em]", isDark ? "border-emerald-400/15 bg-emerald-500/10 text-emerald-300" : "border-emerald-200 bg-emerald-50 text-emerald-700")}>
              <span className="h-2 w-2 rounded-full bg-current" />
              Reading details
            </span>
            <span className={cn("text-xs", isDark ? "text-slate-500" : "text-slate-400")}>
              {bookmark ? `Synced ${lastOpenedLabel}` : "Ready"}
            </span>
          </div>

          <div className="mt-6 space-y-3">
            <DetailRow isDark={isDark} label="Total Chapters" value={chapterCount ? String(chapterCount) : "Syncing"} />
            <DetailRow isDark={isDark} label="Estimated Time to Finish" value={formatReadingDuration(remainingMinutes)} />
            <DetailRow isDark={isDark} label="Last Opened" value={lastOpenedLabel} />
            <DetailRow isDark={isDark} label="Started Reading" value={startedLabel} />
            <DetailRow isDark={isDark} label="Format" value={formatLabel} />
            <DetailRow isDark={isDark} label="Progress" value={`${percentComplete}%`} />
          </div>
        </article>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(16rem,0.92fr)_minmax(0,1.08fr)_minmax(18rem,0.95fr)]">
        <article className={readerPanelClass(isDark)}>
          <SectionTitle isDark={isDark} icon="progress">Reading Progress</SectionTitle>
          <div className="mt-5 space-y-4 text-sm">
            <div>
              <p className={mutedClass(isDark)}>Current {chapterUnit}</p>
              <p className={cn("mt-2 text-lg font-semibold", isDark ? "text-white" : "text-slate-900")}>{currentChapterLabel}</p>
            </div>
            <div>
              <div className="flex items-center justify-between gap-3">
                <p className={mutedClass(isDark)}>Story progress</p>
                <p className={cn("font-semibold", isDark ? "text-slate-200" : "text-slate-800")}>{percentComplete}%</p>
              </div>
              <div className={cn("mt-3 h-2 overflow-hidden rounded-full", isDark ? "bg-white/[0.08]" : "bg-slate-100")}>
                <div className="h-full rounded-full bg-[linear-gradient(90deg,#7c3aed,#a855f7)]" style={{ width: `${percentComplete}%` }} />
              </div>
            </div>
            <div className={cn("flex items-center justify-between border-t pt-4", isDark ? "border-white/[0.07]" : "border-slate-100")}>
              <span className={mutedClass(isDark)}>Saved chapter position</span>
              <span className={cn("font-medium", isDark ? "text-slate-200" : "text-slate-800")}>{bookmark ? `${chapterScroll}%` : "Not saved yet"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className={mutedClass(isDark)}>Time left in chapter</span>
              <span className={cn("font-medium", isDark ? "text-slate-200" : "text-slate-800")}>{chapterMinutesLeft ? formatReadingDuration(chapterMinutesLeft) : "Open reader"}</span>
            </div>
          </div>
        </article>

        <article className={readerPanelClass(isDark)}>
          <SectionTitle isDark={isDark} icon="spark">About This Book</SectionTitle>
          <div className={cn("mt-5 text-sm leading-8", isDark ? "text-slate-300" : "text-slate-600")}>
            <p>{aboutCopy}</p>
          </div>
        </article>

        <article className={readerPanelClass(isDark)}>
          <SectionTitle isDark={isDark} icon="list">Chapter List</SectionTitle>
          <div className="mt-5 space-y-2">
            {previewChapters.length > 0 ? previewChapters.map((chapter) => {
              const isCurrent = chapter.number === continueChapter
              const isNext = nextChapter?.number === chapter.number
              return (
                <button
                  key={chapter.number}
                  type="button"
                  onClick={() => onNavigate(`/${bookId}/chapter/${chapter.number}`)}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 rounded-2xl px-3 py-3 text-left transition",
                    isCurrent
                      ? isDark ? "bg-teal-800/30 text-white" : "bg-teal-50 text-slate-900"
                      : isDark ? "text-slate-300 hover:bg-white/[0.05]" : "text-slate-700 hover:bg-slate-50",
                  )}
                >
                  <div className="min-w-0">
                    <p className={cn("flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em]", isCurrent ? (isDark ? "text-teal-200" : "text-teal-800") : isDark ? "text-slate-500" : "text-slate-400")}>
                      <span className={cn("h-1.5 w-1.5 rounded-full", isCurrent ? "bg-teal-400" : chapter.read ? "bg-emerald-400" : isDark ? "bg-slate-600" : "bg-slate-300")} />
                      {chapterUnit} {chapter.number}
                    </p>
                    <p className="mt-1 truncate text-sm font-medium">{chapter.title || `${chapterUnit} ${chapter.number}`}</p>
                  </div>
                  <div className="shrink-0 text-right text-xs">
                    {isCurrent ? (
                      <span className={cn("rounded-full px-2 py-1 font-semibold", isDark ? "bg-white/10 text-white" : "bg-white text-teal-800")}>Current</span>
                    ) : isNext ? (
                      <span className={cn("font-semibold", isDark ? "text-teal-300" : "text-teal-700")}>Up Next</span>
                    ) : chapter.read ? (
                      <span className={isDark ? "text-slate-500" : "text-slate-400"}>Read</span>
                    ) : (
                      <span className={isDark ? "text-slate-500" : "text-slate-400"}>Unread</span>
                    )}
                  </div>
                </button>
              )
            }) : (
              <p className={cn("text-sm leading-7", isDark ? "text-slate-500" : "text-slate-500")}>LoreVia is still syncing the chapter list for this book.</p>
            )}
          </div>

          <button
            type="button"
            onClick={() => onNavigate(`/${bookId}/chapters`)}
            className={cn("mt-4 inline-flex items-center gap-2 text-sm font-semibold transition", isDark ? "text-teal-300 hover:text-teal-200" : "text-teal-800 hover:text-teal-900")}
          >
            View all chapters
            <ReaderIcon name="arrow" className="h-4 w-4" />
          </button>
        </article>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(15rem,0.78fr)_minmax(15rem,0.82fr)_minmax(17rem,1fr)]">
        <article className={readerPanelClass(isDark)}>
          <SectionTitle isDark={isDark} icon="summary">Chapter Summaries</SectionTitle>
          <p className={cn("mt-4 text-sm leading-7", isDark ? "text-slate-400" : "text-slate-600")}>
            Short recaps for every processed chapter so you can jump back in without rereading everything.
          </p>
          <div className={cn("mt-5 rounded-2xl border px-4 py-3 text-sm", isDark ? "border-white/[0.07] bg-white/[0.03] text-slate-300" : "border-slate-200 bg-slate-50 text-slate-700")}>
            {summaryReadyCount > 0 ? `${summaryReadyCount} chapter summaries ready` : "Summaries are syncing now"}
          </div>
          <button
            type="button"
            onClick={() => onNavigate(`/${bookId}/summaries`)}
            className={cn("mt-5 inline-flex h-11 items-center justify-center rounded-2xl px-4 text-sm font-semibold transition", isDark ? "bg-white/[0.05] text-slate-100 hover:bg-white/[0.08]" : "bg-slate-100 text-slate-800 hover:bg-slate-200")}
          >
            Open Summaries
          </button>
        </article>

        <article className={readerPanelClass(isDark)}>
          <SectionTitle isDark={isDark} icon="bookmark">Saved Items</SectionTitle>
          <div className="mt-5 grid grid-cols-3 gap-3">
            <SavedMetric isDark={isDark} value={bookmarkCount} label="Bookmarks" />
            <SavedMetric isDark={isDark} value={savedQuotes.length} label="Highlights" />
            <SavedMetric isDark={isDark} value={bookNotes.length} label="Notes" />
          </div>
          <div className="mt-5 flex flex-wrap gap-3">
            <button type="button" onClick={() => onNavigate("/quotes")} className={softButtonClass(isDark)}>
              <ReaderIcon name="bookmark" />
              Open Highlights
            </button>
            <button type="button" onClick={() => onNavigate(`/${bookId}/notes`)} className={softButtonClass(isDark)}>
              <ReaderIcon name="note" />
              Open Notes
            </button>
          </div>
        </article>

        <article className={readerPanelClass(isDark)}>
          <SectionTitle isDark={isDark} icon="quote">Recent Note</SectionTitle>
          {recentNote ? (
            <>
              <blockquote className={cn("mt-5 text-lg italic leading-8", isDark ? "text-slate-200" : "text-slate-700")}>
                "{truncatePreview(recentNotePreview)}"
              </blockquote>
              <div className={cn("mt-5 flex flex-wrap items-center justify-between gap-3 text-sm", isDark ? "text-slate-500" : "text-slate-500")}>
                <span>
                  {recentNote.chapter_number ? `${chapterUnit} ${recentNote.chapter_number}${recentNote.chapter_title ? ` - ${recentNote.chapter_title}` : ""}` : "Whole-book note"}
                </span>
                <span>{formatRecentDateLabel(recentNote.updated_at)}</span>
              </div>
              <button
                type="button"
                onClick={() => onNavigate(`/${bookId}/notes`)}
                className={cn("mt-5 inline-flex items-center gap-2 text-sm font-semibold transition", isDark ? "text-teal-300 hover:text-teal-200" : "text-teal-800 hover:text-teal-900")}
              >
                Open note workspace
                <ReaderIcon name="arrow" className="h-4 w-4" />
              </button>
            </>
          ) : (
            <div className={cn("mt-5 rounded-2xl border border-dashed px-4 py-5 text-sm", isDark ? "border-white/[0.08] text-slate-500" : "border-slate-200 text-slate-500")}>
              Save a note while reading and it will appear here for quick recall.
            </div>
          )}
        </article>
      </section>
    </div>
  )
}

function SavedMetric({ isDark, value, label }: { isDark: boolean; value: number; label: string }) {
  return (
    <div className={cn("rounded-2xl border px-3 py-4 text-center", isDark ? "border-white/[0.07] bg-white/[0.03]" : "border-slate-200 bg-slate-50")}>
      <p className={cn("text-2xl font-semibold", isDark ? "text-white" : "text-slate-900")}>{value}</p>
      <p className={cn("mt-1 text-xs uppercase tracking-[0.18em]", isDark ? "text-slate-500" : "text-slate-400")}>{label}</p>
    </div>
  )
}

function DetailRow({ isDark, label, value }: { isDark: boolean; label: string; value: string }) {
  return (
    <div className={cn("flex items-center justify-between gap-4 rounded-2xl border px-4 py-3 text-sm", isDark ? "border-white/[0.06] bg-white/[0.025]" : "border-slate-200/80 bg-slate-50/70")}>
      <span className={mutedClass(isDark)}>{label}</span>
      <span className={cn("text-right font-medium", isDark ? "text-slate-200" : "text-slate-800")}>{value}</span>
    </div>
  )
}

function HeroMetric({ isDark, label, value, note }: { isDark: boolean; label: string; value: string; note: string }) {
  return (
    <div className={cn("rounded-2xl border px-4 py-3", isDark ? "border-white/[0.06] bg-white/[0.025]" : "border-slate-200/80 bg-slate-50/70")}>
      <p className={cn("text-[11px] font-semibold uppercase tracking-[0.18em]", isDark ? "text-slate-500" : "text-slate-400")}>{label}</p>
      <p className={cn("mt-2 text-lg font-semibold", isDark ? "text-white" : "text-slate-900")}>{value}</p>
      <p className={cn("mt-1 text-xs", isDark ? "text-slate-400" : "text-slate-500")}>{note}</p>
    </div>
  )
}

function SectionTitle({ isDark, icon, children }: { isDark: boolean; icon: IconName; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <span className={cn("flex h-8 w-8 items-center justify-center rounded-full", isDark ? "bg-teal-500/10 text-teal-300" : "bg-teal-50 text-teal-800")}>
        <ReaderIcon name={icon} className="h-4 w-4" />
      </span>
      <h2 className={cn("text-lg font-semibold", isDark ? "text-white" : "text-slate-900")}>{children}</h2>
    </div>
  )
}

function readerPanelClass(isDark: boolean) {
  return cn("rounded-[1.75rem] border p-5 sm:p-6", isDark ? "border-white/[0.07] bg-[#0d121b]" : "border-slate-200 bg-white")
}

function softButtonClass(isDark: boolean) {
  return cn("inline-flex h-11 items-center gap-2 rounded-2xl border px-4 text-sm font-semibold transition", isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.06]" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50")
}

function mutedClass(isDark: boolean) {
  return isDark ? "text-slate-500" : "text-slate-500"
}

function stripMarkup(value: string) {
  return value.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim()
}

function truncatePreview(value: string, max = 160) {
  if (!value) return ""
  return value.length <= max ? value : `${value.slice(0, max - 3)}...`
}

function buildAboutFallback(book: Book) {
  const authorLabel = book.author?.trim() || "its author"
  const genreLabel = book.genre?.trim() || (book.work_type === "screenplay" ? "screenplay" : "story")
  return `${book.title} is loaded in reader mode for a cleaner reading pass. Use this space to move between chapters, summaries, highlights, and notes while staying oriented inside ${authorLabel}'s ${genreLabel.toLowerCase()}.`
}

function formatDateLabel(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Today"
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}

function formatRecentDateLabel(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Today"

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
