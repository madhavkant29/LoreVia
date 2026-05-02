"use client"

import { useEffect, useMemo, useState } from "react"
import type { Route } from "next"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"

import { RecallCard } from "@/components/intelligence/RecallCard"
import { AuthorToolsNav } from "@/components/layout/AuthorToolsNav"
import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { readerApi } from "@/lib/api/reader"
import { useRecall } from "@/lib/hooks/useRecall"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { useBookModeStore } from "@/lib/stores/bookModeStore"
import type { Book } from "@/types/book"
import type { CrossBookIntelligence } from "@/types/intelligence"
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
      background: "linear-gradient(180deg,#fcf7ef_0%,#f8f3ec_46%,#f5f0ea_100%)",
      color: "#0c0a09",
    }
  }

  const dominant = book?.cover_edge_colors?.dominant
    || book?.cover_edge_colors?.top
    || book?.cover_edge_colors?.left
    || "#5b6c9a"
  const top = book?.cover_edge_colors?.top || dominant
  const right = book?.cover_edge_colors?.right || dominant

  return {
    background: [
      `radial-gradient(circle at 14% 12%, ${top}33 0%, transparent 28%)`,
      `radial-gradient(circle at 86% 10%, ${right}22 0%, transparent 24%)`,
      `radial-gradient(circle at 50% 0%, ${dominant}18 0%, transparent 42%)`,
      "linear-gradient(180deg, #000000 0%, #050505 42%, #0a0a0a 100%)",
    ].join(", "),
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
  const [crossBook, setCrossBook] = useState<CrossBookIntelligence | null>(null)
  const [chapterList, setChapterList] = useState<ChapterListResponse | null>(null)
  const [modeSaving, setModeSaving] = useState(false)
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
    intelligenceApi.getCrossBookIntelligence(bookId).then(setCrossBook).catch(() => {})
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
      `/${bookId}/graph` as Route,
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
        `/${bookId}/timeline` as Route,
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

  const openRelationships = () => {
    navigateWithMemory(`/${bookId}/graph`)
  }

  const quickTools = useMemo(
    () => [
      { label: "Characters", href: `/${bookId}/characters` },
      { label: "Ask LoreVia", href: `/${bookId}/ask` },
      { label: "Search passages", href: `/${bookId}/search` },
      { label: "Major events", href: `/${bookId}/timeline` },
      { label: "Relationships", action: openRelationships },
      { label: "Summary", href: `/${bookId}/summaries` },
      ...(activeBookMode === "author"
        ? [
            { label: "Notes", href: `/${bookId}/notes` },
            { label: "World gaps", href: `/${bookId}/world-gap` },
          ]
        : []),
    ],
    [activeBookMode, bookId]
  )

  const featureTools = useMemo(
    () => [
      { label: "Analysis", meta: "All advanced tools", onClick: () => navigateWithMemory(`/${bookId}/analysis`) },
    ],
    [bookId]
  )

  const topChapterItems = (chapterList?.chapters ?? []).slice(0, 6)
  const worldNote = crossBook?.wiki_matches?.[0]
    ? `${crossBook.wiki_matches[0].left_name} mirrors ${crossBook.wiki_matches[0].right_name} across connected books, giving LoreVia a continuity anchor for the wider world.`
    : "LoreVia builds world notes as you move further into the manuscript."
  const theoryNote =
    crossBook?.character_matches?.[0]
      ? `${crossBook.character_matches[0].left_name} and ${crossBook.character_matches[0].right_name} echo each other across connected books.`
      : "Character and continuity theories begin to surface once more of the story world has been processed."
  const pageAtmosphere = resolveCoverAtmosphere(book, isDark)

  if (!book) {
    return <div className={`flex justify-center py-20 ${isDark ? "text-slate-400" : "text-stone-400"}`}>Loading...</div>
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

  return (
    <div className="min-h-screen text-slate-100" style={pageAtmosphere}>
      <div className="sticky top-0 z-30 flex items-center justify-between gap-3 px-4 py-5 backdrop-blur-2xl bg-black/45 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-7xl flex items-center justify-between gap-3 w-full">
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
                    ? isDark ? "bg-white text-slate-950" : "bg-white text-stone-950 shadow-sm"
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
                    ? isDark ? "bg-white text-slate-950" : "bg-white text-stone-950 shadow-sm"
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
      <div className="mx-auto max-w-7xl px-4 pb-28 pt-6 sm:px-6 lg:px-8">

        {show && recall ? (
          <div className="mt-6">
            <RecallCard recall={recall} lastChapter={lastChapter ?? Math.max(continueChapter - 1, 1)} onDismiss={dismiss} onContinue={continueReading} />
          </div>
        ) : null}

        <div className="mt-6 grid gap-10 lg:grid-cols-[minmax(0,1.05fr)_24rem]">
          <section
            className={`relative overflow-visible lg:overflow-hidden rounded-[26px] border min-h-[500px] sm:min-h-[600px] lg:min-h-[760px] transition-transform duration-[0.35s] ease hover:scale-[1.01] shadow-[0_10px_30px_rgba(0,0,0,.6)] ${
              isDark
                ? "border-white/10 bg-zinc-900/95"
                : "border-stone-200 bg-zinc-50/95"
            }`}
          >
            <BookCoverCard book={book} isDark={isDark} />

            <div className="absolute inset-0 pointer-events-none">
              <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-black/50 to-transparent" />
              <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/50 to-transparent" />
              <div className="absolute inset-y-0 left-0 w-16 bg-gradient-to-r from-black/30 to-transparent" />
              <div className="absolute inset-y-0 right-0 w-16 bg-gradient-to-l from-black/30 to-transparent" />
            </div>

            <div className="absolute inset-x-0 bottom-0 z-10 p-6 lg:p-8 bg-gradient-to-t from-black/90 via-black/60 to-transparent text-center">
              <h1 className="font-serif text-3xl lg:text-6xl tracking-tight text-white drop-shadow-lg uppercase">
                {book.title}
              </h1>

              {book.author ? (
                <p className="mt-2 text-sm lg:text-base text-white/80">
                  {book.author}
                </p>
              ) : null}
            </div>
          </section>

          <aside className="space-y-7">
            <div className={`rounded-[1.8rem] border p-10 ${isDark ? "border-white/10 bg-zinc-900/70" : "border-stone-200/80 bg-zinc-50/70"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>Reading progress</p>
              <div className="mt-6 flex items-end justify-between gap-3">
                <div>
                  <p className={`text-4xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{percentComplete}%</p>
                  <p className={`mt-2 text-base ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>{chaptersReadCount} {unitPlural} read</p>
                </div>
                <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] text-emerald-800">
                  {book.status}
                </span>
              </div>
              {processingSummary ? (
                <p className={`mt-3 text-sm ${isDark ? "text-amber-300" : "text-amber-700"}`}>{processingSummary}</p>
              ) : null}
              <div className={`mt-6 h-3 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-stone-200"}`}>
                <div
                  className="h-full rounded-full bg-[linear-gradient(90deg,#5b4cf0,#7c6cff)] transition-all duration-1000 ease-out"
                  style={{ width: `${Math.max(0, Math.min(percentComplete, 100))}%` }}
                />
              </div>
              <div className={`mt-6 grid grid-cols-2 gap-5 border-t pt-6 ${isDark ? "border-white/10" : "border-stone-200"}`}>
                <Metric label={`Current ${storyUnitName(book?.work_type)}`} value={`${unitPrefix} ${continueChapter}`} isDark={isDark} />
                <Metric label={`${unitTitle}s left`} value={String(chaptersLeft)} isDark={isDark} />
                <Metric label="Format" value={book.format.toUpperCase()} isDark={isDark} />
                <Metric label={`Total ${unitPlural}`} value={String(book.total_chapters ?? chapterList?.chapters.length ?? "Syncing")} isDark={isDark} />
              </div>
            </div>

            <div className={`rounded-[1.5rem] border p-6 transition-all duration-300 hover:bg-opacity-60 ${isDark ? "border-white/5 bg-zinc-900/45 hover:bg-zinc-900/60" : "border-stone-200/60 bg-zinc-50/45 hover:bg-zinc-50/60"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>{unitPlural}</p>
              <div className="mt-3 space-y-1.5">
                {topChapterItems.length > 0 ? (
                  topChapterItems.map((chapter) => (
                    <button
                      key={chapter.number}
                      onClick={() => navigateWithMemory(`/${bookId}/chapter/${chapter.number}`)}
                      className={`flex w-full items-center justify-between rounded-[1rem] px-4 py-3 text-left transition-all duration-300 relative overflow-hidden group ${
                        chapter.number === continueChapter
                          ? isDark ? "bg-indigo-500/15 text-indigo-100" : "bg-violet-50 text-violet-700"
                          : isDark ? "bg-white/5 text-slate-200 hover:bg-white/10" : "bg-stone-50 text-stone-700 hover:bg-stone-100"
                      }`}
                    >
                      <span className="font-medium text-base relative z-10">{unitTitle} {chapter.number}</span>
                      <span className={`text-xs uppercase tracking-[0.16em] relative z-10 ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                        {chapter.read ? "Read" : "Unread"}
                      </span>
                      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700 ease-in-out" />
                    </button>
                  ))
                ) : (
                  <p className={`text-sm leading-7 ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>{unitTitle} indexing is still syncing.</p>
                )}
              </div>
              <button
                onClick={() => navigateWithMemory(`/${bookId}/chapters`)}
                className={`mt-3 w-full rounded-[0.8rem] border px-3 py-2.5 text-xs font-medium transition hover:-translate-y-0.5 ${isDark ? "border-white/[0.08] bg-white/[0.03] text-white hover:bg-white/[0.06]" : "border-stone-200/60 bg-white/60 text-stone-600 hover:bg-white/70"}`}
              >
                Open full {storyUnitName(book?.work_type)} list
              </button>
            </div>

            <div className={`rounded-[1.5rem] border p-6 transition-all duration-300 hover:bg-opacity-60 ${isDark ? "border-white/5 bg-zinc-900/45 hover:bg-zinc-900/60" : "border-stone-200/60 bg-zinc-50/45 hover:bg-zinc-50/60"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-zinc-400" : "text-zinc-500"}`}>Workspace actions</p>
              <div className="mt-3 grid gap-2.5">
                <button
                  onClick={continueReading}
                  className="inline-flex items-center justify-center rounded-[1rem] bg-gradient-to-b from-violet-500 to-violet-700 px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_40px_rgba(99,102,241,.35)] transition hover:translate-y-[-1px]"
                >
                  {continueChapter > 1 ? `Continue - ${unitTitle} ${continueChapter}` : "Get started"}
                </button>
                <Link
                  href={`/${bookId}/summaries`}
                  className={`inline-flex items-center justify-center rounded-[1rem] border px-4 py-3 text-sm font-medium transition hover:-translate-y-0.5 ${isDark ? "border-white/[0.08] bg-white/[0.03] text-white hover:bg-white/[0.06]" : "border-stone-200/60 bg-white/60 text-stone-600 hover:bg-white/70"}`}
                >
                  Open summary
                </Link>
              </div>

              <div className="mt-3 grid grid-cols-2 gap-1.5">
                {quickTools.map((tool) =>
                  "href" in tool ? (
                    <Link
                      key={tool.label}
                      href={tool.href as Route}
                      className={`w-full text-center rounded-md border px-3 py-2 text-xs font-medium transition hover:-translate-y-0.5 ${isDark ? "border-white/[0.08] bg-white/[0.03] text-white hover:bg-white/[0.06]" : "border-stone-200/60 bg-white/60 text-stone-600 hover:bg-white/70"}`}
                    >
                      {tool.label}
                    </Link>
                  ) : (
                    <button
                      key={tool.label}
                      onClick={tool.action}
                      className={`w-full text-center rounded-md border px-3 py-2 text-xs font-medium transition hover:-translate-y-0.5 ${isDark ? "border-white/[0.08] bg-white/[0.03] text-white hover:bg-white/[0.06]" : "border-stone-200/60 bg-white/60 text-stone-600 hover:bg-white/70"}`}
                    >
                      {tool.label}
                    </button>
                  )
                )}
              </div>
            </div>
          </aside>
        </div>

        <div className="mt-8">
          <div className="space-y-6">
            {bookMode === "author" ? (
              <section className={`rounded-[1.8rem] border p-6 ${isDark ? "border-white/10 bg-white/5" : "border-white/70 bg-white/82"}`}>
                <div className="grid gap-5 xl:grid-cols-[17rem_minmax(0,1fr)]">
                  <AuthorToolsNav
                    bookId={bookId}
                    active="overview"
                    isDark={isDark}
                    title="Author tools"
                    description="A professional left-side workspace for drafting, notes, export, continuity, and story intelligence."
                  />

                  <div>
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                      <div>
                        <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-indigo-300" : "text-violet-500"}`}>Writing tools</p>
                        <h2 className={`mt-2 font-serif text-3xl ${isDark ? "text-white" : "text-stone-950"}`}>Write, organize, and export from one workspace</h2>
                      </div>
                      <p className={`max-w-xl text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                        The overview page now acts like a control center instead of a stack of unrelated cards.
                      </p>
                    </div>

                    <div className="mt-5 grid gap-3 md:grid-cols-2">
                      <div className={`rounded-[1.2rem] border p-5 ${isDark ? "border-white/10 bg-zinc-900/45" : "border-stone-200 bg-zinc-50/45"}`}>
                        <p className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-emerald-300" : "text-emerald-600"}`}>Writing</p>
                        <p className={`mt-2 text-lg font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Manuscript editor</p>
                        <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                          Draft chapters with continuity, character, and thread context already within reach.
                        </p>
                        <button
                          onClick={() => navigateWithMemory(`/${bookId}/manuscript`)}
                          className="mt-4 inline-flex items-center justify-center rounded-[1rem] bg-gradient-to-b from-emerald-500 to-emerald-700 px-5 py-3 text-sm font-semibold text-white shadow-[0_15px_40px_rgba(16,185,129,.35)] transition hover:translate-y-[-1px]"
                        >
                          Open manuscript editor
                        </button>
                      </div>

                      <div className={`rounded-[1.2rem] border p-5 ${isDark ? "border-white/10 bg-zinc-900/45" : "border-stone-200 bg-zinc-50/45"}`}>
                        <p className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-indigo-300" : "text-violet-500"}`}>Author Intelligence</p>
                        <p className={`mt-2 text-lg font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Story Advisor</p>
                        <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                          Ask about plotholes, threads, arcs, and pressure points with grounded manuscript answers.
                        </p>
                        <button
                          onClick={() => navigateWithMemory(`/${bookId}/advisor`)}
                          className="mt-4 inline-flex items-center justify-center rounded-[1rem] bg-gradient-to-b from-violet-500 to-violet-700 px-5 py-3 text-sm font-semibold text-white shadow-[0_15px_40px_rgba(99,102,241,.35)] transition hover:translate-y-[-1px]"
                        >
                          Open Story Advisor
                        </button>
                      </div>

                      <div className={`rounded-[1.2rem] border p-5 ${isDark ? "border-white/10 bg-zinc-900/45" : "border-stone-200 bg-zinc-50/45"}`}>
                        <p className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-sky-300" : "text-sky-700"}`}>Notes and files</p>
                        <p className={`mt-2 text-lg font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Import & Export studio</p>
                        <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                          Keep imports separate from exports, preview vault files, and ship manuscript, notes, or bible outputs from one page.
                        </p>
                        <div className="mt-4 flex flex-wrap gap-3">
                          <button
                            onClick={() => navigateWithMemory(`/${bookId}/export`)}
                            className="inline-flex items-center justify-center rounded-[1rem] bg-gradient-to-b from-sky-500 to-blue-700 px-5 py-3 text-sm font-semibold text-white shadow-[0_15px_40px_rgba(37,99,235,.35)] transition hover:translate-y-[-1px]"
                          >
                            Open import & export
                          </button>
                          <button
                            onClick={() => navigateWithMemory(`/${bookId}/notes`)}
                            className={`inline-flex items-center justify-center rounded-[1rem] border px-4 py-3 text-sm font-semibold transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
                          >
                            Open notes workspace
                          </button>
                        </div>
                      </div>

                      <div className={`rounded-[1.2rem] border p-5 ${isDark ? "border-white/10 bg-zinc-900/45" : "border-stone-200 bg-zinc-50/45"}`}>
                        <p className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>World building</p>
                        <p className={`mt-2 text-lg font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>World Gap Detection</p>
                        <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                          Compare separate lore documents against the manuscript and turn continuity gaps into actionable cleanup notes.
                        </p>
                        <button
                          onClick={() => navigateWithMemory(`/${bookId}/world-gap`)}
                          className="mt-4 inline-flex items-center justify-center rounded-[1rem] bg-gradient-to-b from-amber-500 to-amber-700 px-5 py-3 text-sm font-semibold text-white shadow-[0_15px_40px_rgba(245,158,11,.35)] transition hover:translate-y-[-1px]"
                        >
                          Open World Gap Detection
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </section>
            ) : null}

            <section className={`rounded-[1.8rem] border p-6 ${isDark ? "border-white/10 bg-zinc-900/70" : "border-stone-200 bg-zinc-50/70"}`}>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Explore</p>
                  <h2 className={`mt-2 font-serif text-3xl ${isDark ? "text-white" : "text-stone-900"}`}>Keep the current tools, but make them quieter.</h2>
                </div>
                <p className={`max-w-xl text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                  Analysis remains available, but the primary experience starts with the book itself and expands only as needed.
                </p>
              </div>
              <div className="mt-5">
                {featureTools.map((tool) => (
                  <button
                    key={tool.label}
                    onClick={tool.onClick}
                    className={`w-full rounded-[1.2rem] border px-6 py-5 text-center transition flex flex-col items-center justify-center ${isDark ? "border-white/10 bg-zinc-900/45 hover:bg-zinc-900/55" : "border-stone-200 bg-zinc-50/45 hover:bg-zinc-50/55"}`}
                  >
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>{tool.meta}</p>
                    <p className={`mt-2 text-2xl font-serif font-semibold uppercase tracking-widest ${isDark ? "text-white" : "text-stone-900"}`}>{tool.label}</p>
                  </button>
                ))}
              </div>
            </section>

          </div>
        </div>
      </div>

      <nav className={`fixed inset-x-0 bottom-0 z-30 border-t px-4 py-3 backdrop-blur lg:hidden ${isDark ? "border-white/10 bg-black/92" : "border-stone-200 bg-white/92"}`}>
        <div className={`mx-auto grid max-w-xl grid-cols-6 gap-2 text-center text-[11px] font-medium ${isDark ? "text-slate-400" : "text-stone-500"}`}>
          <Link href={`/${bookId}`} className={`rounded-xl px-2 py-2 ${isDark ? "text-indigo-300" : "text-violet-700"}`}>Overview</Link>
          <Link href={`/${bookId}/summaries`} className="rounded-xl px-2 py-2">Summary</Link>
          <Link href={`/${bookId}/ask`} className="rounded-xl px-2 py-2">Query</Link>
          <button onClick={openRelationships} className="rounded-xl px-2 py-2">Graph</button>
          <Link href="/notifications" className="rounded-xl px-2 py-2">Alerts</Link>
          <Link href="/library" className="rounded-xl px-2 py-2">Library</Link>
        </div>
      </nav>

    </div>
  )
}

function BookCoverCard({ book, isDark }: { book: Book; isDark: boolean }) {
  const [failed, setFailed] = useState(false)
  const src = !failed ? coverSrc(book.cover_url) ?? book.cover_url ?? null : null

  if (!src) {
    return (
      <div className={`absolute inset-0 flex items-center justify-center ${isDark ? "bg-gradient-to-br from-indigo-900 to-slate-800" : "bg-gradient-to-br from-violet-100 to-stone-200"}`}>
        <span className={`font-serif text-8xl lg:text-[12rem] font-bold ${isDark ? "text-white/20" : "text-stone-400/40"}`}>
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


