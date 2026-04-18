"use client"

import { useEffect, useMemo, useState } from "react"
import type { Route } from "next"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"

import { RecallCard } from "@/components/intelligence/RecallCard"
import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { readerApi } from "@/lib/api/reader"
import { API_BASE } from "@/lib/constants"
import { useRecall } from "@/lib/hooks/useRecall"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book } from "@/types/book"
import type { CrossBookIntelligence } from "@/types/intelligence"
import type { ChapterListResponse, ReadingProgress } from "@/types/reader"

function coverSrc(coverUrl: string | null | undefined) {
  if (!coverUrl) return null
  if (/^https?:\/\//i.test(coverUrl)) return coverUrl
  try {
    return new URL(coverUrl, API_BASE).toString()
  } catch {
    if (typeof window !== "undefined") {
      return new URL(coverUrl, window.location.origin).toString()
    }
    return coverUrl
  }
}

export default function BookOverviewPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const [book, setBook] = useState<Book | null>(null)
  const [progress, setProgress] = useState<ReadingProgress | null>(null)
  const [crossBook, setCrossBook] = useState<CrossBookIntelligence | null>(null)
  const [chapterList, setChapterList] = useState<ChapterListResponse | null>(null)
  const router = useRouter()
  const { recall, lastChapter, show, dismiss } = useRecall(bookId)
  const { theme, toggleTheme } = usePreferencesStore()
  const isDark = theme === "dark"
  const overviewScrollKey = `reader-overview-scroll:${bookId}`

  useEffect(() => {
    booksApi.get(bookId).then(setBook)
    readerApi.getProgress(bookId).then(setProgress).catch(() => {})
    readerApi.getChapterList(bookId).then(setChapterList).catch(() => {})
    intelligenceApi.getCrossBookIntelligence(bookId).then(setCrossBook).catch(() => {})
  }, [bookId])

  useEffect(() => {
    if (!book || book.status !== "processing") return

    const interval = window.setInterval(() => {
      booksApi.get(bookId).then(setBook).catch(() => {})
      readerApi.getProgress(bookId).then(setProgress).catch(() => {})
      readerApi.getChapterList(bookId).then(setChapterList).catch(() => {})
    }, 5000)

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

  const navigateWithMemory = (href: string) => {
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem(overviewScrollKey, String(window.scrollY))
    }
    router.push(href as Route)
  }

  const continueReading = () => {
    navigateWithMemory(`/${bookId}/chapter/${continueChapter}`)
  }

  const openRelationships = () => {
    const proceed = window.confirm("The relationship graph may contain spoilers for unread chapters. Continue?")
    if (proceed) navigateWithMemory(`/${bookId}/graph`)
  }

  const quickTools = useMemo(
    () => [
      { label: "Characters", href: `/${bookId}/characters` },
      { label: "Relationships", action: openRelationships },
      { label: "Summary", href: `/${bookId}/summaries` },
      { label: "Search", href: `/${bookId}/search` },
    ],
    [bookId]
  )

  const featureTools = useMemo(
    () => [
      { label: "Themes", meta: "Patterns and motifs", onClick: () => navigateWithMemory(`/${bookId}/themes`) },
      { label: "Foreshadowing", meta: "Signals and hints", onClick: () => navigateWithMemory(`/${bookId}/foreshadowing`) },
      { label: "Timeline", meta: "Story structure", onClick: () => navigateWithMemory(`/${bookId}/timeline`) },
      { label: "Cross-book wiki", meta: "Series echoes", onClick: () => navigateWithMemory(`/${bookId}/cross-book-wiki`) },
      { label: "Relationship evolution", meta: "Shifts over time", onClick: () => navigateWithMemory(`/${bookId}/relationship-evolution`) },
      { label: "Quotes", meta: "Saved lines", onClick: () => navigateWithMemory("/quotes") },
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

  if (!book) {
    return <div className={`flex justify-center py-20 ${isDark ? "text-slate-400" : "text-stone-400"}`}>Loading...</div>
  }

  return (
    <div className={`min-h-screen ${isDark ? "bg-[linear-gradient(180deg,#07111f_0%,#0b1830_44%,#0d1b35_100%)] text-slate-100" : "bg-[linear-gradient(180deg,#fcf7ef_0%,#f8f3ec_46%,#f5f0ea_100%)] text-stone-950"}`}>
      <div className="mx-auto max-w-7xl px-4 pb-28 pt-6 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between gap-3">
          <Link href="/library" className={`text-sm font-medium transition ${isDark ? "text-indigo-300 hover:text-indigo-200" : "text-violet-700 hover:text-violet-800"}`}>
            LoreVia
          </Link>
          <div className="flex items-center gap-2">
            <button
              onClick={toggleTheme}
              className={`rounded-xl border px-4 py-2 text-sm transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white/80 text-stone-600 hover:bg-white"}`}
            >
              {isDark ? "Light mode" : "Dark mode"}
            </button>
            <Link href="/settings" className={`rounded-xl border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-300" : "border-stone-200 bg-white/80 text-stone-600"}`}>
              Settings
            </Link>
          </div>
        </div>

        {show && recall ? (
          <div className="mt-6">
            <RecallCard recall={recall} lastChapter={lastChapter ?? Math.max(continueChapter - 1, 1)} onDismiss={dismiss} onContinue={continueReading} />
          </div>
        ) : null}

        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.05fr)_24rem]">
          <section className={`rounded-[2rem] border p-5 shadow-[0_28px_100px_-60px_rgba(79,70,229,0.25)] sm:p-8 ${isDark ? "border-white/10 bg-[radial-gradient(circle_at_top,rgba(99,102,241,0.14),transparent_35%),linear-gradient(180deg,rgba(10,20,38,0.92),rgba(10,20,38,0.86))]" : "border-white/70 bg-[radial-gradient(circle_at_top,#f7f2ff,transparent_35%),linear-gradient(180deg,rgba(255,255,255,0.9),rgba(255,255,255,0.78))]"}`}>
            <div className="grid gap-8 lg:grid-cols-[0.88fr_1fr] lg:items-start">
              <div className="order-2 lg:order-1">
                <p className={`text-[11px] font-semibold uppercase tracking-[0.34em] ${isDark ? "text-indigo-300" : "text-violet-500"}`}>Reading workspace</p>
                <h1 className={`mt-4 max-w-[11ch] font-serif text-5xl leading-[0.94] tracking-tight sm:text-6xl ${isDark ? "text-white" : "text-stone-950"}`}>
                  {book.title}
                </h1>
                {book.author ? <p className={`mt-3 text-2xl italic ${isDark ? "text-slate-400" : "text-stone-500"}`}>by {book.author}</p> : null}

                <div className={`mt-6 rounded-[1.5rem] border p-5 ${isDark ? "border-white/10 bg-white/5" : "border-violet-100 bg-[linear-gradient(180deg,#f5f4ff,#fbfbff)]"}`}>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.26em] ${isDark ? "text-indigo-300" : "text-violet-500"}`}>
                    {chaptersReadCount > 0 ? `Story so far • Ch. ${Math.max((lastChapter ?? continueChapter) - 1, 1)}` : "Start your reading"}
                  </p>
                  <p className={`mt-4 text-lg leading-8 ${isDark ? "text-slate-200" : "text-stone-600"}`}>
                    {show && recall
                      ? recall
                      : chaptersReadCount > 0
                        ? "LoreVia keeps prior chapters within reach so you can re-enter the book without losing the thread."
                        : "Open the first chapter and LoreVia will begin building summaries, character recall, and continuity signals around your progress."}
                  </p>
                  {show && recall ? (
                    <button
                      onClick={dismiss}
                      className={`mt-4 text-sm font-semibold transition ${isDark ? "text-indigo-300 hover:text-indigo-200" : "text-violet-700 hover:text-violet-800"}`}
                    >
                      Hide recap
                    </button>
                  ) : null}
                </div>

                <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                  <button
                    onClick={continueReading}
                    className="inline-flex items-center justify-center rounded-[1.2rem] bg-[linear-gradient(135deg,#4f46e5,#4338ca)] px-6 py-4 text-lg font-semibold text-white shadow-[0_22px_46px_-28px_rgba(79,70,229,0.78)] transition hover:translate-y-[-1px]"
                  >
                    {continueChapter > 1 ? `Continue - Chapter ${continueChapter}` : "Get started"}
                  </button>
                  <Link
                    href={`/${bookId}/summaries`}
                    className={`inline-flex items-center justify-center rounded-[1.2rem] border px-6 py-4 text-lg font-medium transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white/85 text-stone-700 hover:bg-white"}`}
                  >
                    Open summary
                  </Link>
                </div>

                <div className="mt-5 grid grid-cols-2 gap-3">
                  {quickTools.map((tool) =>
                    "href" in tool ? (
                      <Link
                        key={tool.label}
                        href={tool.href as Route}
                        className={`rounded-[1.05rem] border px-4 py-3 text-center text-sm font-medium transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white/72 text-stone-700 hover:bg-white"}`}
                      >
                        {tool.label}
                      </Link>
                    ) : (
                      <button
                        key={tool.label}
                        onClick={tool.action}
                        className={`rounded-[1.05rem] border px-4 py-3 text-center text-sm font-medium transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white/72 text-stone-700 hover:bg-white"}`}
                      >
                        {tool.label}
                      </button>
                    )
                  )}
                </div>
              </div>

              <div className="order-1 flex justify-center lg:order-2 lg:justify-end">
                <BookCoverCard book={book} isDark={isDark} />
              </div>
            </div>
          </section>

          <aside className="space-y-5">
            <div className={`rounded-[1.8rem] border p-5 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200/80 bg-white/78"}`}>
              <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Reading progress</p>
              <div className="mt-4 flex items-end justify-between gap-3">
                <div>
                  <p className={`text-4xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{percentComplete}%</p>
                  <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{chaptersReadCount} chapters read</p>
                </div>
                <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] text-emerald-800">
                  {book.status}
                </span>
              </div>
              <div className={`mt-4 h-2 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-stone-200"}`}>
                <div
                  className="h-full rounded-full bg-[linear-gradient(90deg,#5b4cf0,#7c6cff)]"
                  style={{ width: `${Math.max(0, Math.min(percentComplete, 100))}%` }}
                />
              </div>
              <div className={`mt-5 grid grid-cols-2 gap-4 border-t pt-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
                <Metric label="Current chapter" value={`Ch. ${continueChapter}`} isDark={isDark} />
                <Metric label="Chapters left" value={String(chaptersLeft)} isDark={isDark} />
                <Metric label="Format" value={book.format.toUpperCase()} isDark={isDark} />
                <Metric label="Total chapters" value={String(book.total_chapters ?? chapterList?.chapters.length ?? "Syncing")} isDark={isDark} />
              </div>
            </div>

            <div className={`rounded-[1.8rem] border p-5 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200/80 bg-white/78"}`}>
              <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-indigo-300" : "text-violet-500"}`}>Chapter rail</p>
              <div className="mt-4 space-y-2">
                {topChapterItems.length > 0 ? (
                  topChapterItems.map((chapter) => (
                    <button
                      key={chapter.number}
                      onClick={() => navigateWithMemory(`/${bookId}/chapter/${chapter.number}`)}
                      className={`flex w-full items-center justify-between rounded-[1rem] px-4 py-3 text-left transition ${
                        chapter.number === continueChapter
                          ? isDark ? "bg-indigo-500/15 text-indigo-100" : "bg-violet-50 text-violet-700"
                          : isDark ? "bg-white/5 text-slate-200 hover:bg-white/10" : "bg-stone-50 text-stone-700 hover:bg-stone-100"
                      }`}
                    >
                      <span className="font-medium">Chapter {chapter.number}</span>
                      <span className={`text-xs uppercase tracking-[0.16em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                        {chapter.read ? "Read" : "Unread"}
                      </span>
                    </button>
                  ))
                ) : (
                  <p className={`text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-500"}`}>Chapter indexing is still syncing.</p>
                )}
              </div>
              <button
                onClick={() => navigateWithMemory(`/${bookId}/chapters`)}
                className={`mt-4 w-full rounded-[1rem] border px-4 py-3 text-sm font-medium ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
              >
                Open full chapter list
              </button>
            </div>
          </aside>
        </div>

        <div className="mt-8">
          <div className="space-y-6">
            <section className={`rounded-[1.8rem] border p-6 ${isDark ? "border-white/10 bg-white/5" : "border-white/70 bg-white/82"}`}>
              <h2 className={`font-serif text-3xl ${isDark ? "text-white" : "text-stone-950"}`}>World Mechanics</h2>
              <p className={`mt-4 max-w-3xl text-lg leading-9 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{worldNote}</p>
            </section>

            <section className={`rounded-[1.8rem] border p-6 ${isDark ? "border-white/10 bg-white/5" : "border-white/70 bg-white/82"}`}>
              <h2 className={`font-serif text-3xl ${isDark ? "text-white" : "text-stone-950"}`}>Recent Theories</h2>
              <div className={`mt-4 rounded-[1.35rem] p-5 ${isDark ? "bg-white/5" : "bg-stone-50"}`}>
                <p className={`text-lg italic leading-9 ${isDark ? "text-slate-300" : "text-stone-600"}`}>“{theoryNote}”</p>
                <p className={`mt-4 text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>LoreVia story model</p>
              </div>
            </section>

            <section className={`rounded-[1.8rem] border p-6 ${isDark ? "border-white/10 bg-white/5" : "border-white/70 bg-white/82"}`}>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Explore</p>
                  <h2 className={`mt-2 font-serif text-3xl ${isDark ? "text-white" : "text-stone-950"}`}>Keep the current tools, but make them quieter.</h2>
                </div>
                <p className={`max-w-xl text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                  Analysis remains available, but the primary experience starts with the book itself and expands only as needed.
                </p>
              </div>
              <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {featureTools.map((tool) => (
                  <button
                    key={tool.label}
                    onClick={tool.onClick}
                    className={`rounded-[1.2rem] border px-4 py-4 text-left transition ${isDark ? "border-white/10 bg-white/5 hover:bg-white/10" : "border-stone-200 bg-stone-50 hover:bg-white"}`}
                  >
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{tool.meta}</p>
                    <p className={`mt-2 text-lg font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{tool.label}</p>
                  </button>
                ))}
              </div>
            </section>
          </div>
        </div>
      </div>

      <nav className={`fixed inset-x-0 bottom-0 z-30 border-t px-4 py-3 backdrop-blur lg:hidden ${isDark ? "border-white/10 bg-[#07111f]/92" : "border-stone-200 bg-white/92"}`}>
        <div className={`mx-auto grid max-w-xl grid-cols-5 gap-2 text-center text-[11px] font-medium ${isDark ? "text-slate-400" : "text-stone-500"}`}>
          <Link href={`/${bookId}`} className={`rounded-xl px-2 py-2 ${isDark ? "text-indigo-300" : "text-violet-700"}`}>Overview</Link>
          <Link href={`/${bookId}/summaries`} className="rounded-xl px-2 py-2">Summary</Link>
          <Link href={`/${bookId}/search`} className="rounded-xl px-2 py-2">Search</Link>
          <button onClick={openRelationships} className="rounded-xl px-2 py-2">Graph</button>
          <Link href="/library" className="rounded-xl px-2 py-2">Library</Link>
        </div>
      </nav>
    </div>
  )
}

function BookCoverCard({ book, isDark }: { book: Book; isDark: boolean }) {
  const [failed, setFailed] = useState(false)
  const src = !failed ? coverSrc(book.cover_url) ?? book.cover_url ?? null : null

  return (
    <div className={`w-full max-w-[24rem] rounded-[1.8rem] border p-4 shadow-[0_28px_90px_-56px_rgba(0,0,0,0.55)] ${isDark ? "border-white/10 bg-[linear-gradient(180deg,#101a31,#0a1222)]" : "border-stone-200 bg-[linear-gradient(180deg,#151515,#25211d)]"}`}>
      <div className={`overflow-hidden rounded-[1.25rem] ${isDark ? "bg-[#07101d]" : "bg-stone-950"}`}>
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={src}
            alt={`${book.title} cover`}
            className={`aspect-[3/4] w-full ${book.format === "pdf" ? "bg-white object-contain p-4" : "object-cover object-top"}`}
            onError={() => setFailed(true)}
          />
        ) : (
          <div className={`flex aspect-[3/4] flex-col justify-between p-8 ${isDark ? "bg-[linear-gradient(180deg,#12203b,#0a1221)] text-white" : "bg-[linear-gradient(180deg,#1b1b1a,#0f0f0f)] text-white"}`}>
            <div className="mx-auto h-full w-full border border-white/25 px-6 py-10 text-center">
              <p className="text-xs uppercase tracking-[0.38em] text-white/45">LoreVia Edition</p>
              <div className="mt-12">
                <p className="text-5xl font-semibold leading-none">{book.title.slice(0, 1).toUpperCase()}</p>
                <p className="mt-8 text-lg leading-8 text-white/70">{titleInitials(book.title)}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
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
