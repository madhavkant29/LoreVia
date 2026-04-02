"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import { RecallCard } from "@/components/intelligence/RecallCard"
import { useRecall } from "@/lib/hooks/useRecall"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book } from "@/types/book"

export default function BookOverviewPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const [book, setBook] = useState<Book | null>(null)
  const [progress, setProgress] = useState<{ current_chapter: number } | null>(null)
  const router = useRouter()
  const { recall, lastChapter, show, dismiss } = useRecall(bookId)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  useEffect(() => {
    booksApi.get(bookId).then(setBook)
    readerApi.getProgress(bookId).then(setProgress).catch(() => {})
  }, [bookId])

  const continueChapter = progress?.current_chapter ?? 1

  const continueReading = () => {
    router.push(`/${bookId}/chapter/${continueChapter}`)
  }

  const openRelationships = () => {
    const proceed = window.confirm("The relationship graph may contain spoilers for unread chapters. Continue?")
    if (proceed) router.push(`/${bookId}/graph`)
  }

  const quickActions = useMemo(
    () => [
      { label: "Continue reading", meta: continueChapter > 1 ? `Resume at chapter ${continueChapter}` : "Begin from chapter 1", accent: "primary", onClick: continueReading },
      { label: "Chapter list", meta: "Navigate every chapter", accent: "neutral", onClick: () => router.push(`/${bookId}/chapters`) },
      { label: "Summaries", meta: "Scene memory and recap", accent: "neutral", onClick: () => router.push(`/${bookId}/summaries`) },
      { label: "Themes", meta: "Patterns and motifs", accent: "cool", onClick: () => router.push(`/${bookId}/themes`) },
      { label: "Foreshadowing", meta: "Signals and early hints", accent: "warm", onClick: () => router.push(`/${bookId}/foreshadowing`) },
      { label: "Timeline", meta: "Story structure", accent: "neutral", onClick: () => router.push(`/${bookId}/timeline`) },
      { label: "Characters", meta: "People and roles", accent: "neutral", onClick: () => router.push(`/${bookId}/characters`) },
      { label: "Relationship evolution", meta: "Shifts over time", accent: "neutral", onClick: () => router.push(`/${bookId}/relationship-evolution`) },
      { label: "Relationship graph", meta: "Network overview", accent: "neutral", onClick: openRelationships },
      { label: "Quotes", meta: "Saved lines across books", accent: "neutral", onClick: () => router.push(`/quotes`) },
    ],
    [router, bookId, continueChapter]
  )

  if (!book) {
    return <div className={`flex justify-center py-20 ${isDark ? "text-stone-500" : "text-slate-400"}`}>Loading...</div>
  }

  return (
    <div className={`min-h-screen px-4 py-10 transition-colors ${isDark ? "bg-[radial-gradient(circle_at_top,#182135,#070a12_62%)] text-stone-100" : "bg-[linear-gradient(180deg,#fcfcfe,#eef3f8)] text-slate-950"}`}>
      <div className="mx-auto max-w-6xl space-y-8">
        <div className="flex flex-wrap items-center gap-3">
          <Link href="/" className={pillClass(isDark)}>
            Home
          </Link>
          <Link href="/library" className={pillClass(isDark)}>
            Library
          </Link>
          <button onClick={() => router.push("/library")} className={pillClass(isDark)}>
            Dashboard
          </button>
        </div>

        {show && recall && (
          <RecallCard recall={recall} lastChapter={lastChapter!} onDismiss={dismiss} onContinue={continueReading} />
        )}

        <section className={`overflow-hidden rounded-[2.2rem] border shadow-[0_32px_140px_-70px_rgba(15,23,42,0.38)] ${isDark ? "border-white/10 bg-[radial-gradient(circle_at_top_right,rgba(96,165,250,0.18),transparent_28%),linear-gradient(150deg,#0d1220,#0a0d16_58%,#111a2a)]" : "border-white/70 bg-[radial-gradient(circle_at_top_right,rgba(59,130,246,0.12),transparent_25%),linear-gradient(150deg,#ffffff,#f8fafc_60%,#eef4ff)]"}`}>
          <div className="grid gap-8 px-6 py-8 lg:grid-cols-[1.15fr_0.85fr] lg:px-8">
            <div>
              <p className={`text-xs font-semibold uppercase tracking-[0.34em] ${isDark ? "text-sky-200" : "text-sky-700"}`}>Reading cockpit</p>
              <h1 className={`mt-4 max-w-3xl font-serif text-5xl leading-tight ${isDark ? "text-white" : "text-slate-950"}`}>{book.title}</h1>
              {book.author ? <p className={`mt-3 text-lg ${isDark ? "text-stone-300" : "text-slate-500"}`}>by {book.author}</p> : null}
              <p className={`mt-5 max-w-2xl text-sm leading-7 ${isDark ? "text-stone-300" : "text-slate-600"}`}>
                Resume the narrative, inspect structure, trace signals, and move between memory, themes, people, and plot without losing your place.
              </p>

              <div className="mt-8 flex flex-wrap gap-3">
                <button
                  onClick={continueReading}
                  className={`rounded-full px-6 py-3 text-sm font-semibold transition ${isDark ? "bg-amber-300 text-slate-950 hover:bg-amber-200" : "bg-slate-950 text-white hover:bg-slate-800"}`}
                >
                  {continueChapter > 1 ? `Continue Chapter ${continueChapter}` : "Start Reading"}
                </button>
                <Link href={`/${bookId}/themes`} className={pillClass(isDark)}>
                  Open themes
                </Link>
                <Link href={`/${bookId}/foreshadowing`} className={pillClass(isDark)}>
                  Open foreshadowing
                </Link>
              </div>

              <div className="mt-6 flex flex-wrap gap-3">
                <InfoChip label={book.total_chapters ? `${book.total_chapters} chapters` : "Chapters syncing"} isDark={isDark} />
                {book.series_name ? <InfoChip label={`${book.series_name}${book.series_order ? ` · Vol ${book.series_order}` : ""}`} isDark={isDark} /> : null}
                {book.genre ? <InfoChip label={book.genre} isDark={isDark} /> : null}
                <InfoChip label={book.format.toUpperCase()} isDark={isDark} />
              </div>
            </div>

            <div className={`rounded-[1.6rem] border p-6 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-slate-200 bg-white/80"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-stone-400" : "text-slate-500"}`}>Session state</p>
              <div className="mt-5 grid gap-4">
                <OverviewStat label="Current chapter" value={`Chapter ${continueChapter}`} isDark={isDark} />
                <OverviewStat label="Status" value={book.status} isDark={isDark} />
                <OverviewStat label="Book tokens" value={book.total_tokens ? book.total_tokens.toLocaleString() : "Pending"} isDark={isDark} />
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className={`text-xs font-semibold uppercase tracking-[0.3em] ${isDark ? "text-stone-400" : "text-slate-500"}`}>Explore</p>
              <h2 className={`mt-2 font-serif text-3xl ${isDark ? "text-white" : "text-slate-950"}`}>Every reading tool, one level below the story.</h2>
            </div>
            <p className={`max-w-xl text-sm leading-6 ${isDark ? "text-stone-300" : "text-slate-600"}`}>
              Start with the continuation path, then fan out into summaries, people, motifs, and structural signals as needed.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {quickActions.map((action) => (
              <button
                key={action.label}
                onClick={action.onClick}
                className={`group rounded-[1.6rem] border p-5 text-left transition duration-200 hover:-translate-y-1 hover:shadow-[0_22px_60px_-48px_rgba(15,23,42,0.3)] ${cardClass(isDark, action.accent)}`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] ${badgeClass(isDark, action.accent)}`}>
                    {action.meta}
                  </span>
                  <span className={isDark ? "text-stone-500 transition group-hover:text-stone-300" : "text-slate-300 transition group-hover:text-slate-500"}>
                    {"->"}
                  </span>
                </div>
                <p className={`mt-5 text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{action.label}</p>
              </button>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}

function pillClass(isDark: boolean) {
  return isDark
    ? "rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-stone-300 hover:bg-white/10 hover:text-white"
    : "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-slate-950"
}

function cardClass(isDark: boolean, accent: string) {
  if (isDark) {
    if (accent === "primary") return "border-amber-300/20 bg-amber-300/10"
    if (accent === "cool") return "border-sky-300/20 bg-sky-300/10"
    if (accent === "warm") return "border-rose-300/20 bg-rose-300/10"
    return "border-white/10 bg-white/[0.03]"
  }
  if (accent === "primary") return "border-amber-200 bg-amber-50"
  if (accent === "cool") return "border-sky-200 bg-sky-50"
  if (accent === "warm") return "border-rose-200 bg-rose-50"
  return "border-slate-200 bg-white"
}

function badgeClass(isDark: boolean, accent: string) {
  if (isDark) {
    if (accent === "primary") return "bg-amber-300/15 text-amber-100"
    if (accent === "cool") return "bg-sky-300/15 text-sky-100"
    if (accent === "warm") return "bg-rose-300/15 text-rose-100"
    return "bg-white/10 text-stone-300"
  }
  if (accent === "primary") return "bg-amber-100 text-amber-800"
  if (accent === "cool") return "bg-sky-100 text-sky-800"
  if (accent === "warm") return "bg-rose-100 text-rose-800"
  return "bg-slate-100 text-slate-600"
}

function InfoChip({ label, isDark }: { label: string; isDark: boolean }) {
  return (
    <div className={`rounded-full border px-4 py-2 text-sm capitalize ${isDark ? "border-white/10 bg-white/5 text-stone-200" : "border-slate-200 bg-white text-slate-700"}`}>
      {label}
    </div>
  )
}

function OverviewStat({ label, value, isDark }: { label: string; value: string; isDark: boolean }) {
  return (
    <div className={`rounded-[1.2rem] border px-4 py-4 ${isDark ? "border-white/10 bg-black/20" : "border-slate-200 bg-white"}`}>
      <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-stone-400" : "text-slate-500"}`}>{label}</p>
      <p className={`mt-2 text-xl font-semibold capitalize ${isDark ? "text-white" : "text-slate-950"}`}>{value}</p>
    </div>
  )
}
