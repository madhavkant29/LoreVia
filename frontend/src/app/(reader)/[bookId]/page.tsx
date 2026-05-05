"use client"

import { useEffect, useState } from "react"
import type { Route } from "next"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"

import { AuthorToolsNav } from "@/components/layout/AuthorToolsNav"
import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import { useRecall } from "@/lib/hooks/useRecall"
import { useBookModeStore } from "@/lib/stores/bookModeStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book } from "@/types/book"
import type { ChapterListResponse, ReadingProgress } from "@/types/reader"

function storyUnitName(workType?: Book["work_type"], plural = false) {
  if (workType === "screenplay") return plural ? "scenes" : "scene"
  return plural ? "chapters" : "chapter"
}

function storyUnitTitle(workType?: Book["work_type"]) {
  return workType === "screenplay" ? "Scene" : "Chapter"
}

function storyUnitPrefix(workType?: Book["work_type"]) {
  return workType === "screenplay" ? "Sc." : "Ch."
}

function coverSrc(coverUrl: string | null | undefined) {
  if (!coverUrl) return null
  if (/^https?:\/\//i.test(coverUrl)) return coverUrl
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL
    if (apiUrl) {
      return new URL(coverUrl, apiUrl).toString()
    }
    if (typeof window !== "undefined") {
      return new URL(coverUrl, window.location.origin).toString()
    }
    return coverUrl
  } catch {
    return coverUrl
  }
}

function resolveCoverAtmosphere(book: Book | null, isDark: boolean) {
  if (!isDark) {
    return {
      background: "linear-gradient(180deg,#f7f5f0 0%,#eef2f0 52%,#f6f4ef 100%)",
      color: "#0c0a09",
    }
  }

  const dominant = book?.cover_edge_colors?.dominant || "#1f2937"
  const top = book?.cover_edge_colors?.top || dominant

  return {
    background: `linear-gradient(180deg,#0a0a0b 0%,${top}2b 34%,#101011 100%)`,
    color: "#f8fafc",
  }
}

function formatEtaLabel(seconds?: number | null) {
  if (typeof seconds !== "number" || Number.isNaN(seconds)) return null
  if (seconds <= 0) return "almost done"

  const minutes = Math.max(1, Math.round(seconds / 60))
  if (minutes < 60) return `${minutes} min left`

  const hours = Math.max(1, Math.round(minutes / 60))
  return `${hours} hr left`
}

function getProcessingSummary(book: Book | null) {
  const processing = book?.processing
  if (!processing) return null

  const stage = (processing.stage ?? processing.status ?? "").toString().trim()
  const completed = typeof processing.chapters_completed === "number" ? processing.chapters_completed : null
  const total = typeof processing.chapters_total === "number" ? processing.chapters_total : book?.total_chapters
  const progress = typeof processing.progress_pct === "number" ? processing.progress_pct : book?.progress_pct
  const eta = formatEtaLabel(processing.eta_seconds)
  const chapterLabel =
    processing.last_chapter_number
      ? `${storyUnitPrefix(book?.work_type)} ${processing.last_chapter_number}${processing.last_chapter_title ? ` - ${processing.last_chapter_title}` : ""}`
      : null

  const parts = [
    stage ? stage.replace(/_/g, " ") : null,
    completed !== null && total ? `${completed}/${total} ${storyUnitName(book?.work_type, true)}` : null,
    typeof progress === "number" ? `${Math.round(progress)}%` : null,
    eta,
    chapterLabel,
  ].filter(Boolean)

  return parts.length > 0 ? parts.join(" / ") : null
}

export default function BookOverviewPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const [book, setBook] = useState<Book | null>(null)
  const [progress, setProgress] = useState<ReadingProgress | null>(null)
  const [chapterList, setChapterList] = useState<ChapterListResponse | null>(null)
  const [modeSaving, setModeSaving] = useState(false)
  const [coverProcessing, setCoverProcessing] = useState(false)
  const router = useRouter()
  const { recall, lastChapter, show, dismiss } = useRecall(bookId)
  const { theme, toggleTheme } = usePreferencesStore()
  const bookMode = useBookModeStore((state) => state.getMode(bookId))
  const setBookMode = useBookModeStore((state) => state.setMode)
  const isDark = theme === "dark"
  const overviewScrollKey = `reader-overview-scroll:${bookId}`

  useEffect(() => {
    booksApi.get(bookId).then(setBook)
    readerApi.getProgress(bookId).then(setProgress).catch(() => {})
    readerApi.getChapterList(bookId).then(setChapterList).catch(() => {})
  }, [bookId])

  useEffect(() => {
    if (book?.mode === "reader" || book?.mode === "author") {
      setBookMode(bookId, book.mode)
    }
  }, [book?.mode, bookId, setBookMode])

  useEffect(() => {
    if (!book || book.status === "ready") return

    const interval = window.setInterval(async () => {
      const updated = await booksApi.get(bookId)
      if (updated.status === "ready") {
        setBook(updated)
        window.clearInterval(interval)
      } else {
        setBook(updated)
      }
    }, 3000)

    return () => window.clearInterval(interval)
  }, [book, bookId])

  useEffect(() => {
    if (typeof window === "undefined") return

    const saved = window.sessionStorage.getItem(overviewScrollKey)
    if (saved) {
      const nextY = Number(saved)
      if (!Number.isNaN(nextY)) {
        window.setTimeout(() => window.scrollTo({ top: nextY, behavior: "auto" }), 40)
      }
    }

    const saveScroll = () => {
      window.sessionStorage.setItem(overviewScrollKey, String(window.scrollY))
    }

    saveScroll()
    window.addEventListener("scroll", saveScroll, { passive: true })
    return () => window.removeEventListener("scroll", saveScroll)
  }, [overviewScrollKey])

  const continueChapter = progress?.current_chapter ?? 1
  const percentComplete = Math.round(progress?.percent_complete ?? book?.progress_pct ?? 0)
  const chaptersLeft = progress?.chapters_left ?? book?.chapters_left ?? 0
  const chaptersReadCount = progress?.chapters_read_count ?? book?.chapters_read_count ?? 0
  const activeBookMode = book?.mode ?? bookMode
  const processingSummary = getProcessingSummary(book)
  const unitTitle = storyUnitTitle(book?.work_type)
  const unitPrefix = storyUnitPrefix(book?.work_type)
  const unitPlural = storyUnitName(book?.work_type, true)
  const topChapterItems = (chapterList?.chapters ?? []).slice(0, 6)
  const pageAtmosphere = resolveCoverAtmosphere(book, isDark)

  const navigateWithMemory = (href: string) => {
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem(overviewScrollKey, String(window.scrollY))
    }
    router.push(href as Route)
  }

  useEffect(() => {
    const routes: Route[] = [
      `/${bookId}` as Route,
      `/${bookId}/summaries` as Route,
      `/${bookId}/analysis` as Route,
      `/${bookId}/ask` as Route,
      `/${bookId}/search` as Route,
      `/${bookId}/timeline` as Route,
      `/${bookId}/chapters` as Route,
      `/${bookId}/chapter/${continueChapter}` as Route,
    ]

    if (activeBookMode === "author") {
      routes.push(
        `/${bookId}/manuscript` as Route,
        `/${bookId}/notes` as Route,
        `/${bookId}/export` as Route,
        `/${bookId}/characters` as Route,
        `/${bookId}/advisor` as Route,
        `/${bookId}/graph` as Route,
        `/${bookId}/plot-threads` as Route,
        `/${bookId}/world-gap` as Route
      )
    }

    for (const route of routes) {
      router.prefetch(route)
    }
  }, [activeBookMode, bookId, continueChapter, router])

  const continueReading = () => {
    navigateWithMemory(`/${bookId}/chapter/${continueChapter}`)
  }

  const openAddSceneFlow = () => {
    navigateWithMemory(`/${bookId}/manuscript?newScene=1`)
  }

  const openRelationships = () => {
    navigateWithMemory(`/${bookId}/graph`)
  }

  const processCover = async () => {
    setCoverProcessing(true)
    try {
      const updated = await booksApi.processCover(bookId)
      setBook(updated)
    } finally {
      setCoverProcessing(false)
    }
  }

  const updateMode = async (nextMode: "reader" | "author") => {
    setBookMode(bookId, nextMode)
    setModeSaving(true)
    try {
      const updated = await booksApi.setMode(bookId, nextMode)
      setBook(updated)
    } catch {
      setBookMode(bookId, book?.mode ?? "reader")
    } finally {
      setModeSaving(false)
    }
  }

  if (!book) {
    return <div className={`flex justify-center py-20 ${isDark ? "text-slate-400" : "text-stone-400"}`}>Loading...</div>
  }

  const recapText = recall || book.public_description || `Start from ${book.title} with a quieter workspace: the book stays central, and deeper tools wait in the sidebar until you need them.`
  const recapChapter = lastChapter ?? Math.max(continueChapter - 1, 1)

  return (
    <div className="min-h-screen text-slate-100" style={pageAtmosphere}>
      <div className={`sticky top-0 z-30 flex items-center justify-between gap-3 px-4 py-4 backdrop-blur-2xl sm:px-6 lg:px-8 ${isDark ? "bg-black/55" : "bg-white/75"}`}>
        <div className="mx-auto flex w-full max-w-[94rem] items-center justify-between gap-3">
          <Link href="/library" className="transition hover:opacity-80">
            <img src="/image.png" alt="LoreVia" className="h-9 w-9 rounded-xl object-cover" />
          </Link>
          <div className="flex items-center gap-2">
            <Link href="/notifications" className={`flex h-10 w-10 items-center justify-center rounded-xl border ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white/80 text-stone-600"}`}>
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17H9.143m5.714 0H18l-1.286-1.286A2 2 0 0116 14.286V11a4 4 0 10-8 0v3.286a2 2 0 01-.714 1.428L6 17h3.143m5.714 0a3 3 0 11-5.714 0" />
              </svg>
            </Link>
            <div className={`inline-flex overflow-hidden rounded-xl border ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white/80"}`}>
              <button
                onClick={() => updateMode("reader")}
                disabled={modeSaving}
                className={`px-4 py-2 text-sm font-medium transition ${
                  activeBookMode === "reader"
                    ? isDark ? "bg-white text-slate-950" : "bg-stone-950 text-white shadow-sm"
                    : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-white"
                }`}
              >
                Reader
              </button>
              <button
                onClick={() => updateMode("author")}
                disabled={modeSaving}
                className={`px-4 py-2 text-sm font-medium transition ${
                  activeBookMode === "author"
                    ? isDark ? "bg-white text-slate-950" : "bg-stone-950 text-white shadow-sm"
                    : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-white"
                }`}
              >
                Author
              </button>
            </div>
            <button
              onClick={toggleTheme}
              aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
              className={`flex items-center gap-3 rounded-xl border px-3 py-2 text-sm transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white/90 text-stone-700 hover:bg-white"}`}
            >
              <span className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-300" : "text-stone-500"}`}>
                {isDark ? "Light" : "Dark"}
              </span>
              <span className={`relative flex h-6 w-11 items-center rounded-full transition ${isDark ? "bg-indigo-500/80" : "bg-stone-300"}`}>
                <span
                  className={`absolute flex h-5 w-5 items-center justify-center rounded-full bg-white text-[9px] font-semibold shadow-sm transition ${
                    isDark ? "translate-x-5 text-amber-500" : "translate-x-0.5 text-slate-700"
                  }`}
                >
                  {isDark ? "Day" : "Night"}
                </span>
              </span>
            </button>
            <Link href="/settings" className={`rounded-xl border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-300" : "border-stone-200 bg-white/80 text-stone-600"}`}>
              Settings
            </Link>
          </div>
        </div>
      </div>

      <div className="mx-auto grid max-w-[94rem] gap-6 px-4 pb-28 pt-6 sm:px-6 lg:grid-cols-[18rem_minmax(0,1fr)_22rem] lg:px-8">
        <div className="hidden lg:block lg:sticky lg:top-24 lg:self-start">
          <AuthorToolsNav
            bookId={bookId}
            active="overview"
            isDark={isDark}
            title={activeBookMode === "author" ? "Author workspace" : "Reader workspace"}
            description={activeBookMode === "author" ? "Drafting and intelligence stay nearby without crowding the book." : "Reading, chapters, and quiet tools stay one hover away."}
            currentChapter={continueChapter}
            mode={activeBookMode}
            variant="rail"
          />
        </div>

        <main className="space-y-6">
          <StoryRecapHero
            book={book}
            isDark={isDark}
            recap={recapText}
            recapChapter={recapChapter}
            unitTitle={unitTitle}
            continueChapter={continueChapter}
            showDismiss={show && Boolean(recall)}
            onDismiss={dismiss}
            onContinue={continueReading}
          />

          <BookPreview
            book={book}
            isDark={isDark}
            coverProcessing={coverProcessing}
            onRefreshCover={processCover}
          />
        </main>

        <aside className="space-y-5 lg:sticky lg:top-24 lg:self-start">
          <ReadingProgressPanel
            book={book}
            isDark={isDark}
            percentComplete={percentComplete}
            chaptersReadCount={chaptersReadCount}
            chaptersLeft={chaptersLeft}
            continueChapter={continueChapter}
            processingSummary={processingSummary}
            unitTitle={unitTitle}
            unitPrefix={unitPrefix}
            unitPlural={unitPlural}
            chapterCount={chapterList?.chapters.length ?? book.total_chapters}
          />

          <ChapterQuickSwitch
            bookId={bookId}
            isDark={isDark}
            chapters={topChapterItems}
            continueChapter={continueChapter}
            unitTitle={unitTitle}
            unitPlural={unitPlural}
            workType={book.work_type}
            onNavigate={navigateWithMemory}
          />

          <ContextPanel
            isDark={isDark}
            activeBookMode={activeBookMode}
            recap={recapText}
            unitTitle={unitTitle}
            continueChapter={continueChapter}
          />
        </aside>
      </div>

      {activeBookMode === "author" ? (
        <CreateFab
          bookId={bookId}
          isDark={isDark}
          onAddScene={openAddSceneFlow}
          onNavigate={navigateWithMemory}
        />
      ) : null}

      <nav className={`fixed inset-x-0 bottom-0 z-30 border-t px-4 py-3 backdrop-blur lg:hidden ${isDark ? "border-white/10 bg-black/92" : "border-stone-200 bg-white/92"}`}>
        <div className={`mx-auto grid max-w-xl grid-cols-6 gap-2 text-center text-[11px] font-medium ${isDark ? "text-slate-400" : "text-stone-500"}`}>
          <Link href={`/${bookId}`} className={`rounded-xl px-2 py-2 ${isDark ? "text-indigo-300" : "text-violet-700"}`}>Overview</Link>
          <button onClick={continueReading} className="rounded-xl px-2 py-2">Read</button>
          <Link href={`/${bookId}/chapters`} className="rounded-xl px-2 py-2">Chapters</Link>
          <Link href={`/${bookId}/summaries`} className="rounded-xl px-2 py-2">Summary</Link>
          <button onClick={openRelationships} className="rounded-xl px-2 py-2">Graph</button>
          <Link href="/library" className="rounded-xl px-2 py-2">Library</Link>
        </div>
      </nav>
    </div>
  )
}

function StoryRecapHero({
  book,
  isDark,
  recap,
  recapChapter,
  unitTitle,
  continueChapter,
  showDismiss,
  onDismiss,
  onContinue,
}: {
  book: Book
  isDark: boolean
  recap: string
  recapChapter: number
  unitTitle: string
  continueChapter: number
  showDismiss: boolean
  onDismiss: () => void
  onContinue: () => void
}) {
  return (
    <section className={`rounded-3xl border p-6 shadow-[0_24px_90px_-58px_rgba(0,0,0,0.75)] ${isDark ? "border-white/10 bg-[#111214]/92 text-white" : "border-stone-200 bg-white/90 text-stone-950"}`}>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_18rem] xl:items-center">
        <div>
          <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-indigo-200" : "text-indigo-700"}`}>Story recap</p>
          <h1 className="mt-3 font-serif text-3xl tracking-tight sm:text-4xl">{book.title}</h1>
          <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
            Resume with a grounded recap through {unitTitle.toLowerCase()} {recapChapter}.
          </p>
          <p className={`mt-5 max-w-3xl text-sm leading-8 ${isDark ? "text-slate-100" : "text-stone-700"}`}>{recap}</p>
        </div>

        <div className="flex flex-col gap-3 xl:items-stretch">
          <button
            onClick={onContinue}
            className={`rounded-full px-5 py-3 text-sm font-semibold transition ${isDark ? "bg-amber-300 text-stone-950 hover:bg-amber-200" : "bg-stone-950 text-white hover:bg-stone-800"}`}
          >
            {continueChapter > 1 ? `Continue Reading - ${unitTitle} ${continueChapter}` : "Continue Reading"}
          </button>
          <div className={`rounded-full px-4 py-3 text-center text-xs font-medium ${isDark ? "bg-white/8 text-slate-200" : "bg-stone-100 text-stone-600"}`}>
            Last active {unitTitle.toLowerCase()}: {recapChapter || "syncing"}
          </div>
          {showDismiss ? (
            <button
              onClick={onDismiss}
              className={`rounded-full px-3 py-2 text-sm transition ${isDark ? "text-slate-400 hover:bg-white/8 hover:text-white" : "text-stone-500 hover:bg-stone-100 hover:text-stone-800"}`}
            >
              Dismiss
            </button>
          ) : null}
        </div>
      </div>
    </section>
  )
}

function BookPreview({
  book,
  isDark,
  coverProcessing,
  onRefreshCover,
}: {
  book: Book
  isDark: boolean
  coverProcessing: boolean
  onRefreshCover: () => void
}) {
  return (
    <section className={`relative overflow-hidden rounded-3xl border shadow-[0_18px_70px_-42px_rgba(0,0,0,0.8)] ${isDark ? "border-white/10 bg-[#0f1012]" : "border-stone-200 bg-stone-50"}`}>
      <div className="absolute left-5 top-5 z-20 flex items-center gap-3">
        <p className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "bg-black/45 text-slate-300" : "bg-white/80 text-stone-500"}`}>Book preview</p>
      </div>
      <button
        type="button"
        onClick={onRefreshCover}
        disabled={coverProcessing}
        className={`absolute right-5 top-5 z-20 rounded-full border px-4 py-2 text-xs font-medium backdrop-blur transition ${isDark ? "border-white/10 bg-black/35 text-slate-200 hover:bg-black/55" : "border-stone-200 bg-white/80 text-stone-700 hover:bg-white"} disabled:opacity-50`}
      >
        {coverProcessing ? "Refreshing..." : "Refresh cover"}
      </button>

      <div className="relative h-[70vh] sm:h-[80vh] lg:h-[90vh]">
        <BookCoverCard book={book} isDark={isDark} />
        <div className="pointer-events-none absolute inset-0">
          {isDark ? (
            <>
              <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-black/45 to-transparent" />
              <div className="absolute inset-x-0 bottom-0 h-36 bg-gradient-to-t from-black/82 via-black/42 to-transparent" />
              <div className="absolute inset-y-0 left-0 w-16 bg-gradient-to-r from-black/22 to-transparent" />
              <div className="absolute inset-y-0 right-0 w-16 bg-gradient-to-l from-black/22 to-transparent" />
            </>
          ) : (
            <>
              <div className="absolute inset-x-0 top-0 h-20 bg-gradient-to-b from-white/40 to-transparent" />
              <div className="absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-white/55 to-transparent" />
            </>
          )}
        </div>

        <div className="absolute inset-x-0 bottom-0 z-10 p-6 text-center lg:p-8">
          <h2 className={`font-serif text-3xl uppercase tracking-tight drop-shadow-lg sm:text-5xl ${
              isDark ? "text-white" : "text-stone-900"
            }`}>
            {book.title}
          </h2>
          {book.author ? (
            <p className={`mt-2 text-sm sm:text-base ${isDark ? "text-white/80" : "text-stone-700"}`}>
              {book.author}
            </p>
          ) : null}
        </div>
      </div>
    </section>
  )
}

function ReadingProgressPanel({
  book,
  isDark,
  percentComplete,
  chaptersReadCount,
  chaptersLeft,
  continueChapter,
  processingSummary,
  unitTitle,
  unitPrefix,
  unitPlural,
  chapterCount,
}: {
  book: Book
  isDark: boolean
  percentComplete: number
  chaptersReadCount: number
  chaptersLeft: number
  continueChapter: number
  processingSummary: string | null
  unitTitle: string
  unitPrefix: string
  unitPlural: string
  chapterCount: number | null | undefined
}) {
  return (
    <section className={`rounded-3xl border p-6 ${isDark ? "border-white/10 bg-[#111214]/88" : "border-stone-200 bg-white/88"}`}>
      <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Reading progress</p>
      <div className="mt-5 flex items-end justify-between gap-3">
        <div>
          <p className={`text-4xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{percentComplete}%</p>
          <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{chaptersReadCount} {unitPlural} read</p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] ${book.status === "ready" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>
          {book.status}
        </span>
      </div>
      {processingSummary ? (
        <p className={`mt-3 text-sm ${isDark ? "text-amber-300" : "text-amber-700"}`}>{processingSummary}</p>
      ) : null}
      <div className={`mt-6 h-2 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-stone-200"}`}>
        <div
          className="h-full rounded-full bg-[linear-gradient(90deg,#5b4cf0,#10b981)] transition-all duration-1000 ease-out"
          style={{ width: `${Math.max(0, Math.min(percentComplete, 100))}%` }}
        />
      </div>
      <div className={`mt-6 grid grid-cols-2 gap-5 border-t pt-6 ${isDark ? "border-white/10" : "border-stone-200"}`}>
        <Metric label={`Current ${storyUnitName(book.work_type)}`} value={`${unitPrefix} ${continueChapter}`} isDark={isDark} />
        <Metric label={`${unitTitle}s left`} value={String(chaptersLeft)} isDark={isDark} />
        <Metric label="Format" value={book.format.toUpperCase()} isDark={isDark} />
        <Metric label={`Total ${unitPlural}`} value={String(chapterCount ?? "Syncing")} isDark={isDark} />
      </div>
    </section>
  )
}

function ChapterQuickSwitch({
  bookId,
  isDark,
  chapters,
  continueChapter,
  unitTitle,
  unitPlural,
  workType,
  onNavigate,
}: {
  bookId: string
  isDark: boolean
  chapters: ChapterListResponse["chapters"]
  continueChapter: number
  unitTitle: string
  unitPlural: string
  workType: Book["work_type"]
  onNavigate: (href: string) => void
}) {
  return (
    <section className={`rounded-3xl border p-5 ${isDark ? "border-white/10 bg-[#111214]/74" : "border-stone-200 bg-white/82"}`}>
      <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>{unitPlural}</p>
      <div className="mt-3 space-y-1.5">
        {chapters.length > 0 ? (
          chapters.map((chapter) => (
            <button
              key={chapter.number}
              onClick={() => onNavigate(`/${bookId}/chapter/${chapter.number}`)}
              className={`flex h-12 w-full items-center justify-between rounded-xl px-4 text-left transition ${
                chapter.number === continueChapter
                  ? isDark ? "bg-white text-stone-950" : "bg-stone-950 text-white"
                  : isDark ? "bg-white/[0.04] text-slate-200 hover:bg-white/[0.08]" : "bg-stone-50 text-stone-700 hover:bg-stone-100"
              }`}
            >
              <span className="truncate text-sm font-semibold">{unitTitle} {chapter.number}</span>
              <span className={`ml-3 shrink-0 text-[10px] uppercase tracking-[0.16em] ${chapter.number === continueChapter ? (isDark ? "text-stone-600" : "text-white/65") : (isDark ? "text-slate-500" : "text-stone-400")}`}>
                {chapter.read ? "Read" : "Unread"}
              </span>
            </button>
          ))
        ) : (
          <p className={`text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{unitTitle} indexing is still syncing.</p>
        )}
      </div>
      <button
        onClick={() => onNavigate(`/${bookId}/chapters`)}
        className={`mt-3 w-full rounded-xl border px-3 py-2.5 text-xs font-medium transition ${isDark ? "border-white/[0.08] bg-white/[0.03] text-white hover:bg-white/[0.06]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
      >
        Open full {storyUnitName(workType)} list
      </button>
    </section>
  )
}

function ContextPanel({
  isDark,
  activeBookMode,
  recap,
  unitTitle,
  continueChapter,
}: {
  isDark: boolean
  activeBookMode: "reader" | "author"
  recap: string
  unitTitle: string
  continueChapter: number
}) {
  const summary = recap.length > 220 ? `${recap.slice(0, 220).trim()}...` : recap
  const suggestion = activeBookMode === "author"
    ? "Use the sidebar for drafting and intelligence. The next useful action is still to read or review the current chapter before opening tools."
    : "Continue reading from the current chapter, then use Summary or Search from the sidebar when you need context."

  return (
    <section className={`rounded-3xl border p-5 ${isDark ? "border-white/10 bg-[#111214]/62" : "border-stone-200 bg-white/78"}`}>
      <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Context</p>
      <div className={`mt-4 rounded-2xl px-4 py-4 ${isDark ? "bg-white/[0.04]" : "bg-stone-50"}`}>
        <p className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>Suggested next action</p>
        <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{suggestion}</p>
      </div>
      <div className={`mt-3 rounded-2xl px-4 py-4 ${isDark ? "bg-white/[0.04]" : "bg-stone-50"}`}>
        <p className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-indigo-300" : "text-indigo-700"}`}>Current {unitTitle.toLowerCase()} context</p>
        <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{unitTitle} {continueChapter} is ready. {summary}</p>
      </div>
    </section>
  )
}

function CreateFab({
  bookId,
  isDark,
  onAddScene,
  onNavigate,
}: {
  bookId: string
  isDark: boolean
  onAddScene: () => void
  onNavigate: (href: string) => void
}) {
  const itemClass = `rounded-full border px-4 py-2 text-sm font-semibold shadow-[0_18px_44px_-28px_rgba(0,0,0,0.8)] transition ${
    isDark ? "border-white/10 bg-[#17191d] text-slate-100 hover:bg-[#202329]" : "border-stone-200 bg-white text-stone-800 hover:bg-stone-50"
  }`

  return (
    <div className="group/create fixed bottom-24 right-5 z-40 flex flex-col items-end gap-3 lg:bottom-8 lg:right-8">
      <div className="pointer-events-none flex translate-y-2 flex-col items-end gap-2 opacity-0 transition group-hover/create:pointer-events-auto group-hover/create:translate-y-0 group-hover/create:opacity-100 group-focus-within/create:pointer-events-auto group-focus-within/create:translate-y-0 group-focus-within/create:opacity-100">
        <button onClick={onAddScene} className={itemClass}>Add Scene</button>
        <button onClick={() => onNavigate(`/${bookId}/notes`)} className={itemClass}>Add Note</button>
        <button onClick={() => onNavigate(`/${bookId}/characters`)} className={itemClass}>Add Character</button>
      </div>
      <button
        className={`rounded-full px-5 py-3 text-sm font-semibold shadow-[0_18px_55px_-28px_rgba(0,0,0,0.9)] transition ${isDark ? "bg-amber-300 text-stone-950 hover:bg-amber-200" : "bg-stone-950 text-white hover:bg-stone-800"}`}
      >
        + Create
      </button>
    </div>
  )
}

function BookCoverCard({ book, isDark }: { book: Book; isDark: boolean }) {
  const [failed, setFailed] = useState(false)
  const src = !failed ? coverSrc(book.cover_processed_url ?? book.cover_url) : null

  if (!src) {
    return (
      <div className={`absolute inset-0 flex items-center justify-center ${isDark ? "bg-[#17191d]" : "bg-stone-100"}`}>
        <span className={`font-serif text-8xl font-bold lg:text-[12rem] ${isDark ? "text-white/20" : "text-stone-400/40"}`}>
          {titleInitials(book.title)}
        </span>
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={`${book.title} cover`}
      onError={() => setFailed(true)}
      className="absolute inset-0 h-full w-full object-cover object-center"
    />
  )
}

function Metric({ label, value, isDark }: { label: string; value: string; isDark: boolean }) {
  return (
    <div>
      <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{label}</p>
      <p className={`mt-1 text-base font-medium ${isDark ? "text-white" : "text-stone-900"}`}>{value}</p>
    </div>
  )
}

function titleInitials(title: string) {
  return title
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("")
}
