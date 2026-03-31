"use client"
import { useEffect, useMemo, useState } from "react"
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
      { label: "Chapter List", onClick: () => router.push(`/${bookId}/chapters`) },
      { label: "Summaries", onClick: () => router.push(`/${bookId}/summaries`) },
      { label: "Foreshadowing", onClick: () => router.push(`/${bookId}/foreshadowing`) },
      { label: "Timeline", onClick: () => router.push(`/${bookId}/timeline`) },
      { label: "Themes", onClick: () => router.push(`/${bookId}/themes`) },
      { label: "Ask the Book", onClick: () => router.push(`/${bookId}/ask`) },
      { label: "Characters", onClick: () => router.push(`/${bookId}/characters`) },
      { label: "Relationship Evolution", onClick: () => router.push(`/${bookId}/relationship-evolution`) },
      { label: "Relationships", onClick: openRelationships },
      { label: "Quotes", onClick: () => router.push(`/quotes`) },
    ],
    [router, bookId]
  )

  if (!book) {
    return <div className={`flex justify-center py-20 ${isDark ? "text-slate-500" : "text-slate-400"}`}>Loading...</div>
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="space-y-8">
        {show && recall && (
          <RecallCard recall={recall} lastChapter={lastChapter!} onDismiss={dismiss} onContinue={continueReading} />
        )}

        <section className={`rounded-[1.75rem] border shadow-[0_20px_70px_-48px_rgba(15,23,42,0.16)] ${
          isDark ? "border-white/10 bg-slate-950" : "border-slate-200 bg-white"
        }`}>
          <div className="grid gap-8 px-6 py-8 lg:grid-cols-[1.15fr_0.85fr] lg:px-8">
            <div>
              <div className="mb-4">
                <button
                  onClick={() => router.push("/library")}
                  className={`rounded-full border px-4 py-2 text-sm font-medium transition ${
                    isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100"
                  }`}
                >
                  Back to Library
                </button>
              </div>
              <p className={`text-xs font-semibold uppercase tracking-[0.32em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                Book Overview
              </p>
              <h1 className={`mt-4 font-serif text-5xl leading-tight ${isDark ? "text-white" : "text-slate-950"}`}>{book.title}</h1>
              {book.author ? <p className={`mt-3 text-lg ${isDark ? "text-slate-300" : "text-slate-500"}`}>by {book.author}</p> : null}
              <p className={`mt-5 max-w-2xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                Return to the book, revisit what matters, and move through summaries, characters, themes, and relationship changes from one structured workspace.
              </p>

              <div className="mt-8 flex flex-wrap gap-3">
                <button
                  onClick={continueReading}
                  className={`rounded-full px-6 py-3 text-sm font-semibold transition ${
                    isDark ? "bg-white text-slate-950 hover:bg-slate-200" : "bg-slate-950 text-white hover:bg-slate-800"
                  }`}
                >
                  {continueChapter > 1 ? `Continue - Chapter ${continueChapter}` : "Start Reading"}
                </button>
                <div className={`rounded-full border px-4 py-3 text-sm ${
                  isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-slate-200 bg-slate-50 text-slate-700"
                }`}>
                  {book.total_chapters ? `${book.total_chapters} chapters available` : "Chapter count syncing"}
                </div>
                {book.genre ? (
                  <div className={`rounded-full border px-4 py-3 text-sm capitalize ${
                    isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-slate-200 bg-slate-50 text-slate-700"
                  }`}>
                    {book.genre}
                  </div>
                ) : null}
              </div>
            </div>

            <div className={`rounded-[1.4rem] border p-6 ${
              isDark ? "border-white/10 bg-slate-900" : "border-slate-200 bg-slate-50"
            }`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                Reading Status
              </p>
              <div className="mt-5 space-y-4">
                <OverviewStat label="Current chapter" value={`Chapter ${continueChapter}`} isDark={isDark} />
                <OverviewStat label="Format" value={book.format.toUpperCase()} isDark={isDark} />
                <OverviewStat label="Status" value={book.status} isDark={isDark} />
                {book.total_tokens ? <OverviewStat label="Book tokens" value={book.total_tokens.toLocaleString()} isDark={isDark} /> : null}
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-5">
          <div>
            <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Explore</p>
            <h2 className={`mt-2 font-serif text-3xl ${isDark ? "text-white" : "text-slate-950"}`}>Everything around the book</h2>
            <p className={`mt-2 max-w-2xl text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
              Move between memory, structure, people, and themes from one organized reading workspace.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {quickActions.map((action, index) => (
              <button
                key={action.label}
                onClick={action.onClick}
                className={`rounded-[1.35rem] border p-5 text-left transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_18px_54px_-40px_rgba(15,23,42,0.18)] ${
                  isDark ? "border-white/10 bg-slate-950" : "border-slate-200 bg-white"
                }`}
              >
                <div className="flex h-full flex-col">
                  <div className="flex items-start justify-between gap-3">
                    <div className={`flex h-11 w-11 items-center justify-center rounded-2xl text-sm font-semibold ${
                      isDark ? "bg-white/10 text-white" : "bg-slate-100 text-slate-700"
                    }`}>
                      {String(index + 1).padStart(2, "0")}
                    </div>
                    <span className={`rounded-full px-3 py-1 text-xs font-medium ${
                      isDark ? "bg-white/10 text-slate-200" : "bg-slate-100 text-slate-600"
                    }`}>
                      Open
                    </span>
                  </div>

                  <div className="mt-5 flex items-center gap-2">
                    <p className={`text-xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{action.label}</p>
                    <span
                      title={getActionDescription(action.label)}
                      className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-semibold ${
                        isDark ? "bg-white/10 text-slate-100" : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      i
                    </span>
                  </div>

                  <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-700"}`}>
                    {getActionDescription(action.label)}
                  </p>

                  <div className="mt-5">
                    <span className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>
                      {getActionMeta(action.label)}
                    </span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}

function OverviewStat({ label, value, isDark }: { label: string; value: string; isDark: boolean }) {
  return (
    <div className={`rounded-[1.1rem] border px-4 py-4 ${
      isDark ? "border-white/10 bg-white/5" : "border-slate-200 bg-white"
    }`}>
      <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>{label}</p>
      <p className={`mt-2 text-lg font-semibold capitalize ${isDark ? "text-white" : "text-slate-950"}`}>{value}</p>
    </div>
  )
}

function getActionDescription(label: string) {
  const descriptions: Record<string, string> = {
    "Chapter List": "See reading progress chapter by chapter and reopen any section instantly.",
    Summaries: "Review the story so far without stepping beyond your read progress.",
    Foreshadowing: "Surface the early hints and signals that matter as the narrative develops.",
    Timeline: "Follow the unfolding sequence of major events, entrances, and turning points.",
    Themes: "Trace recurring motifs, tensions, and narrative patterns across read chapters.",
    "Ask the Book": "Get grounded answers based only on what the text has already revealed.",
    Characters: "Browse merged character profiles with evolving details and relationships.",
    "Relationship Evolution": "Watch alliances and tensions shift through specific events.",
    Relationships: "Open the graph view for a broader map of character connections.",
    Quotes: "Return to your saved lines, passages, and annotations across the library.",
  }
  return descriptions[label] ?? "Open this reader tool."
}

function getActionMeta(label: string) {
  const meta: Record<string, string> = {
    "Chapter List": "Progress + navigation",
    Summaries: "Memory layer",
    Foreshadowing: "Signal tracking",
    Timeline: "Story structure",
    Themes: "Pattern analysis",
    "Ask the Book": "Grounded Q&A",
    Characters: "People + roles",
    "Relationship Evolution": "Change over time",
    Relationships: "Connection graph",
    Quotes: "Saved passages",
  }
  return meta[label] ?? "Reader tool"
}
