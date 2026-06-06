"use client"

import React, { useState } from "react"

import { RecallCard } from "@/components/intelligence/RecallCard"
import { CoverEditOverlay } from "@/components/ui/CoverEditOverlay"
import { SmartBookCover } from "@/components/ui/SmartBookCover"
import { useRecall } from "@/lib/hooks/useRecall"
import { cn } from "@/lib/utils/text"
import { chapterKindLabel } from "@/lib/utils/chapterLabels"
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
  bookmark,
  isDark,
  modeSaving,
  canUseAuthorMode,
  greetingName = "there",
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
  const spoilerSafePulseScore = Math.max(0, Math.min(100, Math.round(54 + percentComplete * 0.32 + summaryReadyCount * 2)))
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
    <div className="relative isolate space-y-5">

      <section className={cn("relative overflow-hidden rounded-lg border p-4 sm:p-5", isDark ? "border-white/[0.07] bg-[#0b1018]" : "border-slate-200 bg-white")}>
        <div className={cn("pointer-events-none absolute right-0 top-0 h-32 w-32 rounded-full blur-3xl", isDark ? "bg-teal-500/10" : "bg-teal-100/55")} />
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0">
            <p className={cn("text-3xs font-semibold uppercase tracking-[0.24em]", isDark ? "text-teal-300" : "text-teal-800")}>Reader workspace</p>
            <h1 className={cn("mt-2 font-serif text-3xl leading-none sm:text-4xl", isDark ? "text-white" : "text-slate-950")}>Welcome back, {greetingName}.</h1>
            <p className={cn("mt-3 max-w-3xl text-sm leading-6", isDark ? "text-slate-400" : "text-slate-600")}>
              Fall back into the story. Track your progress, keep your place, and stay spoiler-safe.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span className={cn("inline-flex items-center gap-2 rounded-full border px-3 py-1 text-3xs font-semibold uppercase tracking-[0.18em]", isDark ? "border-emerald-400/18 bg-emerald-500/10 text-emerald-300" : "border-emerald-200 bg-emerald-50 text-emerald-700")}>
                <span className="h-2 w-2 rounded-full bg-current" />
                Reader mode active
              </span>
              {bookmark ? (
                <span className={cn("inline-flex rounded-full border px-3 py-1 text-3xs font-semibold", isDark ? "border-white/10 bg-white/[0.04] text-slate-300" : "border-slate-200 bg-slate-50 text-slate-600")}>
                  Bookmark saved in {chapterUnit.toLowerCase()} {bookmark.chapter}
                </span>
              ) : null}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {canUseAuthorMode ? (
              <ModeToggle
                isDark={isDark}
                activeMode={activeBookMode}
                modeSaving={modeSaving}
                onModeChange={onModeChange}
              />
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
              className={cn("inline-flex h-11 items-center gap-2 rounded-md px-5 text-sm font-semibold transition-colors", isDark ? "bg-teal-800 text-white hover:bg-teal-700" : "bg-teal-800 text-white hover:bg-teal-700")}
            >
              <ReaderIcon name="book" className="h-4 w-4" />
              Open Reader
            </button>
          </div>
        </div>

        <div className="mt-5 grid gap-3 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-center">
          <label className={cn("flex min-h-[3.2rem] items-center gap-3 rounded-md border px-4", isDark ? "border-white/[0.08] bg-[#090c14] text-slate-200" : "border-slate-200 bg-slate-50 text-slate-800")}>
            <ReaderIcon name="search" className={isDark ? "h-5 w-5 text-slate-500" : "h-5 w-5 text-slate-400"} />
            <span className="sr-only">Search this book, notes, or summaries</span>
            <input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && submitSearch()}
              className="w-full bg-transparent text-sm outline-none"
            />
            <button
              type="button"
              onClick={submitSearch}
              className={cn("rounded-full px-2 py-1 text-3xs font-semibold uppercase tracking-[0.18em] transition", isDark ? "bg-white/[0.05] text-slate-400 hover:bg-white/[0.08]" : "bg-white text-slate-500 hover:bg-slate-100")}
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
        <article className={cn("relative overflow-hidden rounded-lg border p-5 sm:p-6", isDark ? "border-white/[0.07] bg-[#0d121b]" : "border-slate-200 bg-white")}>
          <div className={cn("pointer-events-none absolute -left-8 top-6 h-32 w-32 rounded-full blur-3xl", isDark ? "bg-teal-500/10" : "bg-teal-100/70")} />
          <div className="grid gap-6 lg:grid-cols-[12rem_minmax(0,1fr)]">
            <SmartBookCover
              src={coverUrlOverride !== null ? coverUrlOverride : book.cover_url}
              title={book.title}
              isDark={isDark}
              className={cn("aspect-[0.72] overflow-hidden rounded-lg border", isDark ? "border-white/10 bg-[#0a0d13]" : "border-slate-200 bg-slate-50")}
              overlay={
                <CoverEditOverlay
                  bookId={bookId}
                  isDark={isDark}
                  hasCover={Boolean(coverUrlOverride !== null ? coverUrlOverride : book.cover_url)}
                  onCoverUpdated={(updated) => setCoverUrlOverride(updated.cover_url ?? null)}
                />
              }
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
                    className="h-full rounded-full bg-teal-700"
                    style={{ width: `${percentComplete}%` }}
                  />
                </div>
              </div>

              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={onContinueReading}
                  className={cn("inline-flex h-12 items-center gap-2 rounded-md px-5 text-sm font-semibold transition", isDark ? "bg-teal-800 text-white hover:bg-teal-700" : "bg-teal-800 text-white hover:bg-teal-700")}
                >
                  <ReaderIcon name="book" />
                  Continue Reading
                </button>
                <button
                  type="button"
                  onClick={() => onNavigate(`/${bookId}/summaries`)}
                  className={cn("inline-flex h-12 items-center gap-2 rounded-md border px-5 text-sm font-semibold transition", isDark ? "border-white/10 bg-white/[0.03] text-slate-100 hover:bg-white/[0.06]" : "border-slate-200 bg-white text-slate-800 hover:bg-slate-50")}
                >
                  <ReaderIcon name="summary" />
                  Open Chapter Summaries
                </button>
                <button
                  type="button"
                  onClick={() => onNavigate("/quotes")}
                  className={cn("flex h-12 w-12 items-center justify-center rounded-md border transition", isDark ? "border-white/10 bg-white/[0.03] text-slate-300 hover:bg-white/[0.06]" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50")}
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

        <article className={cn("rounded-lg border p-5 sm:p-6", isDark ? "border-white/[0.07] bg-[#0d121b]" : "border-slate-200 bg-white")}>
          <div className="flex items-center justify-between gap-3">
            <span className={cn("inline-flex items-center gap-2 rounded-full border px-3 py-1 text-3xs font-semibold uppercase tracking-[0.18em]", isDark ? "border-emerald-400/15 bg-emerald-500/10 text-emerald-300" : "border-emerald-200 bg-emerald-50 text-emerald-700")}>
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

      <section className="grid gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(18rem,0.72fr)_minmax(17rem,0.7fr)]">
        <article className={readerPanelClass(isDark)}>
          <SectionTitle isDark={isDark} icon="list">Chapter Progress</SectionTitle>
          <div className="mt-5 space-y-2">
            {previewChapters.length > 0 ? previewChapters.map((chapter) => {
              const isCurrent = chapter.number === continueChapter
              return (
                <button
                  key={`progress-${chapter.number}`}
                  type="button"
                  onClick={() => onNavigate(`/${bookId}/chapter/${chapter.number}`)}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 rounded-md border px-4 py-3 text-left transition",
                    isCurrent
                      ? isDark ? "border-teal-500/45 bg-teal-500/10 text-white" : "border-teal-300 bg-teal-50 text-slate-950"
                      : isDark ? "border-white/[0.06] bg-white/[0.03] text-slate-300 hover:bg-white/[0.06]" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
                  )}
                >
                  <div className="min-w-0">
                    <p className={cn("text-xs font-semibold uppercase tracking-[0.18em]", isCurrent ? "text-teal-400" : isDark ? "text-slate-500" : "text-slate-400")}>{chapterKindLabel(chapter.chapter_kind, chapter.number, chapterUnit)}</p>
                    <p className="mt-1 break-words text-sm font-semibold leading-6">{chapter.title || chapterKindLabel(chapter.chapter_kind, chapter.number, chapterUnit)}</p>
                  </div>
                  <span className={cn("text-xs font-semibold", isCurrent ? "text-teal-400" : chapter.read ? "text-emerald-400" : isDark ? "text-slate-500" : "text-slate-400")}>
                    {isCurrent ? "Reading" : chapter.read ? "Complete" : "Unread"}
                  </span>
                </button>
              )
            }) : (
              <p className={cn("text-sm leading-7", isDark ? "text-slate-500" : "text-slate-500")}>LoreVia is still syncing the chapter list for this book.</p>
            )}
          </div>
          <button type="button" onClick={() => onNavigate(`/${bookId}/chapters`)} className={readerFooterLinkClass(isDark)}>
            View all chapters <ReaderIcon name="arrow" className="h-4 w-4" />
          </button>
        </article>

        <article className={readerPanelClass(isDark)}>
          <div className="flex items-start justify-between gap-3">
            <SectionTitle isDark={isDark} icon="spark">Story Pulse</SectionTitle>
            <span className={cn("rounded-full px-3 py-1 text-3xs font-semibold", isDark ? "bg-white/[0.06] text-slate-300" : "bg-slate-100 text-slate-600")}>Spoiler-safe</span>
          </div>
          <div className="mt-5 flex items-center gap-4">
            <div
              className="relative flex h-24 w-24 shrink-0 items-center justify-center rounded-full"
              style={{ background: `conic-gradient(#8b5cf6 0 ${spoilerSafePulseScore}%, ${isDark ? "#1b2430" : "#edf0f5"} ${spoilerSafePulseScore}% 100%)` }}
            >
              <div className={cn("flex h-[4.6rem] w-[4.6rem] flex-col items-center justify-center rounded-full", isDark ? "bg-[#0d121b]" : "bg-white")}>
                <span className={cn("text-2xl font-semibold", isDark ? "text-white" : "text-slate-950")}>{spoilerSafePulseScore}</span>
                <span className={cn("text-3xs", isDark ? "text-slate-500" : "text-slate-400")}>/100</span>
              </div>
            </div>
            <p className={cn("text-sm leading-6", isDark ? "text-slate-300" : "text-slate-600")}>
              The story is unfolding through content you have reached. LoreVia keeps this score bounded to your reading progress.
            </p>
          </div>
          <div className="mt-5 space-y-3">
            <ReaderMetricRow isDark={isDark} label="Continuity" value={Math.min(96, spoilerSafePulseScore + 14)} />
            <ReaderMetricRow isDark={isDark} label="World depth" value={Math.min(94, spoilerSafePulseScore + 10)} />
            <ReaderMetricRow isDark={isDark} label="Character consistency" value={Math.min(92, spoilerSafePulseScore + 8)} />
            <ReaderMetricRow isDark={isDark} label="Pacing" value={Math.max(58, spoilerSafePulseScore - 6)} />
          </div>
        </article>

        <article className={readerPanelClass(isDark)}>
          <SectionTitle isDark={isDark} icon="book">Current Chapter</SectionTitle>
          <div className="mt-5 space-y-3">
            <DetailRow isDark={isDark} label="Chapter" value={currentChapterLabel} />
            <DetailRow isDark={isDark} label="Position" value={bookmark ? `${chapterScroll}%` : `${Math.round(progress?.scroll_pct ?? 0)}%`} />
            <DetailRow isDark={isDark} label="Last read" value={lastOpenedLabel} />
          </div>
          <button type="button" onClick={onContinueReading} className={readerFooterLinkClass(isDark)}>
            Go to last read <ReaderIcon name="arrow" className="h-4 w-4" />
          </button>
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
                <div className="h-full rounded-full bg-teal-700" style={{ width: `${percentComplete}%` }} />
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
                    "flex w-full items-center justify-between gap-3 rounded-md px-3 py-3 text-left transition",
                    isCurrent
                      ? isDark ? "bg-teal-800/30 text-white" : "bg-teal-50 text-slate-900"
                      : isDark ? "text-slate-300 hover:bg-white/[0.05]" : "text-slate-700 hover:bg-slate-50",
                  )}
                >
                  <div className="min-w-0">
                    <p className={cn("flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em]", isCurrent ? (isDark ? "text-teal-200" : "text-teal-800") : isDark ? "text-slate-500" : "text-slate-400")}>
                      <span className={cn("h-1.5 w-1.5 rounded-full", isCurrent ? "bg-teal-400" : chapter.read ? "bg-emerald-400" : isDark ? "bg-slate-600" : "bg-slate-300")} />
                      {chapterKindLabel(chapter.chapter_kind, chapter.number, chapterUnit)}
                    </p>
                    <p className="mt-1 break-words text-sm font-medium leading-6">{chapter.title || chapterKindLabel(chapter.chapter_kind, chapter.number, chapterUnit)}</p>
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
          <div className={cn("mt-5 rounded-md border px-4 py-3 text-sm", isDark ? "border-white/[0.07] bg-white/[0.03] text-slate-300" : "border-slate-200 bg-slate-50 text-slate-700")}>
            {summaryReadyCount > 0 ? `${summaryReadyCount} chapter summaries ready` : "Summaries are syncing now"}
          </div>
          <button
            type="button"
            onClick={() => onNavigate(`/${bookId}/summaries`)}
            className={cn("mt-5 inline-flex h-11 items-center justify-center rounded-md px-4 text-sm font-semibold transition", isDark ? "bg-white/[0.05] text-slate-100 hover:bg-white/[0.08]" : "bg-slate-100 text-slate-800 hover:bg-slate-200")}
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
            <div className={cn("mt-5 rounded-md border border-dashed px-4 py-5 text-sm", isDark ? "border-white/[0.08] text-slate-500" : "border-slate-200 text-slate-500")}>
              Save a note while reading and it will appear here for quick recall.
            </div>
          )}
        </article>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(15rem,0.72fr)_minmax(0,1fr)_minmax(17rem,0.82fr)]">
        <article className={readerPanelClass(isDark)}>
          <SectionTitle isDark={isDark} icon="bookmark">Notes & Quotes</SectionTitle>
          <p className={cn("mt-4 text-sm leading-7", isDark ? "text-slate-400" : "text-slate-600")}>Your thoughts, highlights, and favorite lines.</p>
          <div className="mt-5 space-y-3">
            <DetailRow isDark={isDark} label="Bookmarks" value={String(bookmarkCount)} />
            <DetailRow isDark={isDark} label="Quotes saved" value={String(savedQuotes.length)} />
            <DetailRow isDark={isDark} label="Notes" value={String(bookNotes.length)} />
          </div>
          <button type="button" onClick={() => onNavigate(`/${bookId}/notes`)} className={readerFooterLinkClass(isDark)}>
            Open notes hub <ReaderIcon name="arrow" className="h-4 w-4" />
          </button>
        </article>

        <article className={readerPanelClass(isDark)}>
          <SectionTitle isDark={isDark} icon="spark">Ask LoreVia</SectionTitle>
          <p className={cn("mt-4 text-sm leading-7", isDark ? "text-slate-400" : "text-slate-600")}>
            Ask grounded, spoiler-safe questions about chapters you have already reached.
          </p>
          <button
            type="button"
            onClick={() => onNavigate(`/${bookId}/ask`)}
            className={cn("mt-5 flex w-full flex-col items-start rounded-md border px-4 py-4 text-left transition", isDark ? "border-white/[0.07] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-slate-50 hover:bg-white")}
          >
            <span className={cn("text-sm", isDark ? "text-slate-500" : "text-slate-400")}>Ask something about the story...</span>
            <span className="mt-3 inline-flex items-center gap-2 rounded-full bg-teal-800 px-4 py-2 text-sm font-semibold text-white">
              Ask LoreVia <ReaderIcon name="arrow" className="h-4 w-4" />
            </span>
          </button>
          <div className="mt-4 flex flex-wrap gap-2">
            {["Is the author foreshadowing something?", "What's the significance of this place?", "Who knows this secret?"].map((question) => (
              <button key={question} type="button" onClick={() => onNavigate(`/${bookId}/ask`)} className={cn("rounded-full px-3 py-1.5 text-xs font-semibold", isDark ? "bg-white/[0.05] text-slate-300" : "bg-slate-100 text-slate-600")}>{question}</button>
            ))}
          </div>
          <p className={cn("mt-4 text-center text-xs", isDark ? "text-slate-500" : "text-slate-400")}>LoreVia only uses content you have read.</p>
        </article>

        <article className={readerPanelClass(isDark)}>
          <SectionTitle isDark={isDark} icon="note">Recent Reading Activity</SectionTitle>
          <div className="mt-5 space-y-3">
            {recentActivities.length > 0 ? recentActivities.map((activity) => (
              <div key={`${activity.title}-${activity.time}`} className={cn("rounded-md border px-4 py-3", isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white")}>
                <div className="flex items-start justify-between gap-3">
                  <p className={cn("text-sm font-semibold", isDark ? "text-slate-100" : "text-slate-800")}>{activity.title}</p>
                  <span className={cn("text-xs", isDark ? "text-slate-500" : "text-slate-400")}>{activity.time}</span>
                </div>
                <p className={cn("mt-1 text-xs leading-5", isDark ? "text-slate-500" : "text-slate-500")}>{activity.body}</p>
              </div>
            )) : (
              <p className={cn("rounded-md border border-dashed px-4 py-5 text-sm", isDark ? "border-white/[0.08] text-slate-500" : "border-slate-200 text-slate-500")}>Reading activity will appear after you continue reading, save a quote, or add a note.</p>
            )}
          </div>
          <button type="button" onClick={() => onNavigate(`/${bookId}/chapters`)} className={readerFooterLinkClass(isDark)}>
            View full activity <ReaderIcon name="arrow" className="h-4 w-4" />
          </button>
        </article>
      </section>

      <section className={cn("rounded-lg border p-5 sm:p-6", isDark ? "border-white/[0.07] bg-[#0d121b]" : "border-slate-200 bg-white")}>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,0.65fr)_auto] lg:items-end">
          <div>
            <p className={cn("text-3xs font-semibold uppercase tracking-[0.24em]", isDark ? "text-slate-500" : "text-slate-400")}>Reader workspace</p>
            <h2 className={cn("mt-2 font-serif text-3xl leading-none", isDark ? "text-white" : "text-slate-950")}>Your reading command center.</h2>
            <p className={cn("mt-2 text-sm leading-6", isDark ? "text-slate-400" : "text-slate-600")}>Track your journey, set goals, and stay immersed.</p>
          </div>
          <div className="flex justify-start lg:justify-end">
            <span className={cn("inline-flex rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em]", isDark ? "border-teal-500/20 bg-teal-500/10 text-teal-200" : "border-teal-200 bg-teal-50 text-teal-800")}>
              Reader Overview
            </span>
          </div>
        </div>
        <ReaderWorkspaceContent
          isDark={isDark}
          percentComplete={percentComplete}
          progress={progress}
          chapterUnit={chapterUnit}
          continueChapter={continueChapter}
          chapterCount={chapterCount}
          bookmarkCount={bookmarkCount}
          savedQuotesCount={savedQuotes.length}
          notesCount={bookNotes.length}
          onNavigate={onNavigate}
          onContinueReading={onContinueReading}
          bookId={bookId}
        />
      </section>
    </div>
  )
}

function SavedMetric({ isDark, value, label }: { isDark: boolean; value: number; label: string }) {
  return (
    <div className={cn("rounded-md border px-3 py-4 text-center", isDark ? "border-white/[0.07] bg-white/[0.03]" : "border-slate-200 bg-slate-50")}>
      <p className={cn("text-2xl font-semibold", isDark ? "text-white" : "text-slate-900")}>{value}</p>
      <p className={cn("mt-1 text-xs uppercase tracking-[0.18em]", isDark ? "text-slate-500" : "text-slate-400")}>{label}</p>
    </div>
  )
}

function DetailRow({ isDark, label, value }: { isDark: boolean; label: string; value: string }) {
  return (
    <div className={cn("flex items-center justify-between gap-4 rounded-md border px-4 py-3 text-sm", isDark ? "border-white/[0.06] bg-white/[0.025]" : "border-slate-200/80 bg-slate-50/70")}>
      <span className={mutedClass(isDark)}>{label}</span>
      <span className={cn("text-right font-medium", isDark ? "text-slate-200" : "text-slate-800")}>{value}</span>
    </div>
  )
}

function HeroMetric({ isDark, label, value, note }: { isDark: boolean; label: string; value: string; note: string }) {
  return (
    <div className={cn("rounded-md border px-4 py-3", isDark ? "border-white/[0.06] bg-white/[0.025]" : "border-slate-200/80 bg-slate-50/70")}>
      <p className={cn("text-3xs font-semibold uppercase tracking-[0.18em]", isDark ? "text-slate-500" : "text-slate-400")}>{label}</p>
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

function ReaderMetricRow({ isDark, label, value }: { isDark: boolean; label: string; value: number }) {
  return (
    <div className={cn("rounded-md border px-4 py-3", isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white")}>
      <div className="flex items-center justify-between gap-3">
        <span className={cn("text-sm", isDark ? "text-slate-300" : "text-slate-600")}>{label}</span>
        <span className="text-sm font-semibold text-teal-500">{value}%</span>
      </div>
      <div className={cn("mt-3 h-1.5 overflow-hidden rounded-full", isDark ? "bg-white/[0.08]" : "bg-slate-100")}>
        <div className="h-full rounded-full bg-teal-500" style={{ width: `${value}%` }} />
      </div>
    </div>
  )
}

function ReaderWorkspaceContent({
  isDark,
  percentComplete,
  progress,
  chapterUnit,
  continueChapter,
  chapterCount,
  bookmarkCount,
  savedQuotesCount,
  notesCount,
  onNavigate,
  onContinueReading,
  bookId,
}: {
  isDark: boolean
  percentComplete: number
  progress: ReadingProgress | null
  chapterUnit: string
  continueChapter: number
  chapterCount: number
  bookmarkCount: number
  savedQuotesCount: number
  notesCount: number
  onNavigate: (href: string) => void
  onContinueReading: () => void
  bookId: string
}) {
  const chaptersRead = progress?.chapters_read_count ?? 0
  const sessionGoal = 45
  const sessionProgress = clamp(Math.round(progress?.scroll_pct ? progress.scroll_pct * 100 : percentComplete), 0, 100)
  const savedItems = bookmarkCount + savedQuotesCount + notesCount

  return (
    <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,0.96fr)_minmax(0,0.92fr)_minmax(0,1fr)] xl:auto-rows-fr">
      <div className={cn("rounded-md border p-5", isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-slate-50")}>
        <p className={cn("text-3xs font-semibold uppercase tracking-[0.22em]", isDark ? "text-slate-500" : "text-slate-400")}>Reading progress</p>
        <div className="mt-5 flex flex-col gap-5 sm:flex-row sm:items-center">
          <div
            className="flex h-28 w-28 shrink-0 items-center justify-center rounded-full"
            style={{ background: `conic-gradient(#2dd4bf 0 ${percentComplete}%, ${isDark ? "#1b2430" : "#edf0f5"} ${percentComplete}% 100%)` }}
          >
            <div className={cn("flex h-20 w-20 flex-col items-center justify-center rounded-full", isDark ? "bg-[#0d121b]" : "bg-white")}>
              <span className={cn("text-2xl font-semibold", isDark ? "text-white" : "text-slate-950")}>{percentComplete}%</span>
              <span className={cn("text-3xs", isDark ? "text-slate-500" : "text-slate-400")}>overall</span>
            </div>
          </div>
          <div className="min-w-0 space-y-2 text-sm">
            <p className={isDark ? "text-slate-300" : "text-slate-600"}>{chaptersRead} / {chapterCount} chapters completed</p>
            <p className={isDark ? "text-slate-500" : "text-slate-400"}>{progress?.chapters_left ?? 0} chapters left</p>
            <p className={isDark ? "text-slate-500" : "text-slate-400"}>Estimated time left updates from reading progress.</p>
            <button
              type="button"
              onClick={() => onNavigate(`/${bookId}/chapters`)}
              className={cn("inline-flex items-center gap-2 text-sm font-semibold transition", isDark ? "text-teal-300 hover:text-teal-200" : "text-teal-800 hover:text-teal-900")}
            >
              View all chapters
              <ReaderIcon name="arrow" className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
      <div className="grid gap-5">
        <div className={cn("rounded-md border p-5", isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-slate-50")}>
          <p className={cn("text-3xs font-semibold uppercase tracking-[0.22em]", isDark ? "text-slate-500" : "text-slate-400")}>Session goal</p>
          <p className={cn("mt-4 text-3xl font-semibold", isDark ? "text-white" : "text-slate-950")}>{sessionGoal} pages</p>
          <p className={cn("mt-1 text-sm", isDark ? "text-slate-400" : "text-slate-500")}>Daily reading goal</p>
          <ReaderMetricRow isDark={isDark} label="Session progress" value={sessionProgress} />
          <button
            type="button"
            onClick={onContinueReading}
            className={cn("mt-4 inline-flex w-full items-center justify-center gap-2 rounded-md px-4 py-3 text-sm font-semibold transition", isDark ? "bg-teal-800 text-white hover:bg-teal-700" : "bg-teal-800 text-white hover:bg-teal-700")}
          >
            Continue reading
            <ReaderIcon name="arrow" className="h-4 w-4" />
          </button>
        </div>
        <div className={cn("rounded-md border p-5", isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-slate-50")}>
          <p className={cn("text-3xs font-semibold uppercase tracking-[0.22em]", isDark ? "text-slate-500" : "text-slate-400")}>Saved items</p>
          <p className={cn("mt-3 text-3xl font-semibold", isDark ? "text-white" : "text-slate-950")}>{savedItems}</p>
          <div className="mt-4 space-y-3">
            <DetailRow isDark={isDark} label="Bookmarks" value={String(bookmarkCount)} />
            <DetailRow isDark={isDark} label="Quotes saved" value={String(savedQuotesCount)} />
            <DetailRow isDark={isDark} label="Notes" value={String(notesCount)} />
          </div>
        </div>
      </div>
      <div className="grid gap-5">
        <div className={cn("rounded-md border p-5", isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-slate-50")}>
          <p className={cn("text-3xs font-semibold uppercase tracking-[0.22em]", isDark ? "text-slate-500" : "text-slate-400")}>Up next</p>
          <div className="mt-4 space-y-3">
            <ReaderMiniCard isDark={isDark} label={`Continue ${chapterUnit.toLowerCase()} ${continueChapter}`} value={percentComplete} suffix="%" onClick={onContinueReading} />
            <ReaderMiniCard isDark={isDark} label="Open notes hub" value={notesCount} onClick={() => onNavigate(`/${bookId}/notes`)} />
            <ReaderMiniCard isDark={isDark} label="Review summaries" value={chapterCount} onClick={() => onNavigate(`/${bookId}/summaries`)} />
          </div>
        </div>
      </div>
    </div>
  )
}

function ReaderMiniCard({ isDark, label, value, onClick, suffix = "" }: { isDark: boolean; label: string; value: number; onClick: () => void; suffix?: string }) {
  return (
    <button type="button" onClick={onClick} className={cn("rounded-md border p-4 text-left transition", isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-slate-50 hover:bg-white")}>
      <p className={cn("text-2xl font-semibold", isDark ? "text-white" : "text-slate-950")}>{value}{suffix}</p>
      <p className={cn("mt-1 text-sm leading-6", isDark ? "text-slate-500" : "text-slate-500")}>{label}</p>
    </button>
  )
}

function ModeToggle({
  isDark,
  activeMode,
  modeSaving,
  onModeChange,
}: {
  isDark: boolean
  activeMode: "reader" | "author"
  modeSaving: boolean
  onModeChange: (nextMode: "reader" | "author") => void
}) {
  const thumbClass = activeMode === "author" ? "translate-x-full" : "translate-x-0"

  return (
    <div
      role="group"
      aria-label="Workspace mode"
      className={cn("relative inline-grid h-11 grid-cols-2 rounded-full border p-1", isDark ? "border-white/10 bg-white/[0.04]" : "border-slate-200 bg-slate-50")}
    >
      <span
        aria-hidden="true"
        className={cn("pointer-events-none absolute inset-y-1 left-1 w-[calc(50%-0.25rem)] rounded-full bg-teal-800 transition-transform duration-300 ease-out", thumbClass)}
      />
      {(["reader", "author"] as const).map((mode) => (
        <button
          key={mode}
          type="button"
          onClick={() => onModeChange(mode)}
          disabled={modeSaving}
          aria-pressed={activeMode === mode}
          className={cn(
            "relative z-10 min-w-[5.8rem] rounded-full px-4 text-xs font-semibold uppercase tracking-[0.18em] transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-teal-500/60",
            activeMode === mode ? "text-white" : isDark ? "text-slate-300 hover:text-white" : "text-slate-600 hover:text-slate-900",
          )}
        >
          {mode}
        </button>
      ))}
    </div>
  )
}

function readerPanelClass(isDark: boolean) {
  return cn("rounded-lg border p-5 sm:p-6", isDark ? "border-white/[0.07] bg-[#0d121b]" : "border-slate-200 bg-white")
}

function softButtonClass(isDark: boolean) {
  return cn("inline-flex h-11 items-center gap-2 rounded-md border px-4 text-sm font-semibold transition", isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.06]" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50")
}

function readerFooterLinkClass(isDark: boolean) {
  return cn("mt-5 inline-flex w-full items-center justify-center gap-2 rounded-md border px-4 py-3 text-sm font-semibold transition", isDark ? "border-white/10 bg-white/[0.03] text-teal-300 hover:bg-white/[0.06]" : "border-slate-200 bg-white text-teal-800 hover:bg-slate-50")
}

function mutedClass(isDark: boolean) {
  return isDark ? "text-slate-500" : "text-slate-500"
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
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
