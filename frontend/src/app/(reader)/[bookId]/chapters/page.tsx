"use client"

import { useEffect, useMemo, useState } from "react"
import { useParams, useRouter } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book } from "@/types/book"
import type { ChapterListResponse } from "@/types/reader"

function storyUnitLabel(workType?: Book["work_type"]) {
  return workType === "screenplay" ? "Scene" : "Chapter"
}

export default function ChapterListPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  const [book, setBook] = useState<Book | null>(null)
  const [data, setData] = useState<ChapterListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [readBusy, setReadBusy] = useState<string | null>(null)

  async function loadChapters() {
    setLoading(true)
    setError(null)
    await Promise.all([
      booksApi.get(bookId).then(setBook),
      readerApi.getChapterList(bookId).then(setData),
    ])
      .catch(() => setError("Could not load the full chapter list."))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadChapters().catch(() => {})
  }, [bookId])

  async function setChapterRead(chapter: number, read: boolean) {
    setReadBusy(`chapter:${chapter}`)
    try {
      await readerApi.updateChapterReadStatus(bookId, chapter, read)
      await readerApi.getChapterList(bookId).then(setData)
    } finally {
      setReadBusy(null)
    }
  }

  async function markBookRead() {
    setReadBusy("book")
    try {
      await readerApi.markBookRead(bookId)
      await readerApi.getChapterList(bookId).then(setData)
    } finally {
      setReadBusy(null)
    }
  }

  const unitLabel = storyUnitLabel(book?.work_type)
  const processedCount = useMemo(
    () => (data?.chapters ?? []).filter((chapter) => chapter.processed).length,
    [data]
  )

  return (
    <div className={`min-h-screen px-4 py-8 transition-colors ${isDark ? "bg-[linear-gradient(180deg,#000000_0%,#060606_44%,#0d0d0d_100%)] text-slate-100" : "bg-[linear-gradient(180deg,#fcf7ef_0%,#f8f3ec_46%,#f5f0ea_100%)] text-stone-950"}`}>
      <div className="mx-auto max-w-5xl">
        <button onClick={() => router.back()} className={`text-sm font-medium transition ${isDark ? "text-slate-400 hover:text-white" : "text-stone-500 hover:text-stone-900"}`}>{"<- Back"}</button>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-indigo-300" : "text-violet-500"}`}>Full Contents</p>
            <h1 className={`mt-2 font-serif text-5xl ${isDark ? "text-white" : "text-stone-950"}`}>{book?.title || "Chapter List"}</h1>
            <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>
              {book?.mode === "author"
                ? `Showing all processed and queued ${unitLabel.toLowerCase()}s across the manuscript.`
                : `Showing the full ${unitLabel.toLowerCase()} list with your current read status.`}
            </p>
          </div>
          <div className={`rounded-[1.1rem] border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-300" : "border-stone-200 bg-white/80 text-stone-600"}`}>
            {processedCount}/{data?.chapters.length ?? 0} processed
          </div>
        </div>

        {!loading && !error && data?.chapters.length ? (
          <div className="mt-5 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void markBookRead()}
              disabled={readBusy === "book"}
              className={`rounded-full border px-4 py-2 text-sm font-semibold ${isDark ? "border-emerald-300/20 bg-emerald-400/10 text-emerald-100" : "border-emerald-200 bg-emerald-50 text-emerald-800"} disabled:opacity-50`}
            >
              {readBusy === "book" ? "Marking..." : "Mark book read"}
            </button>
          </div>
        ) : null}

        {error ? (
          <div className={`mt-6 rounded-[1.3rem] border px-5 py-4 text-sm ${isDark ? "border-red-500/25 bg-red-500/10 text-red-300" : "border-red-200 bg-red-50 text-red-700"}`}>
            {error}
          </div>
        ) : null}

        {loading ? (
          <div className={`mt-6 rounded-[1.3rem] border px-5 py-4 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-300" : "border-stone-200 bg-white/80 text-stone-600"}`}>
            Loading {unitLabel.toLowerCase()}s...
          </div>
        ) : null}

        {!loading && !error ? (
          <div className="mt-8 space-y-4">
            {(data?.chapters ?? []).map((chapter) => (
              <article
                key={chapter.number}
                className={`w-full rounded-[1.4rem] border px-5 py-5 text-left ${
                  isDark
                    ? "border-white/10 bg-white/[0.04]"
                    : "border-stone-200 bg-white/90"
                }`}
              >
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                      {unitLabel} {chapter.number}
                    </p>
                    <h2 className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>
                      {chapter.title || `${unitLabel} ${chapter.number}`}
                    </h2>
                  </div>
                  <div className="flex flex-wrap gap-2 sm:justify-end">
                    <span className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${
                      chapter.processed
                        ? isDark ? "bg-emerald-500/15 text-emerald-300" : "bg-emerald-100 text-emerald-700"
                        : isDark ? "bg-amber-500/15 text-amber-300" : "bg-amber-100 text-amber-700"
                    }`}>
                      {chapter.processed ? "Processed" : "Queued"}
                    </span>
                    <span className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${
                      chapter.read
                        ? isDark ? "bg-indigo-500/15 text-indigo-300" : "bg-violet-100 text-violet-700"
                        : isDark ? "bg-white/8 text-slate-400" : "bg-stone-100 text-stone-500"
                    }`}>
                      {chapter.read ? "Read" : "Unread"}
                    </span>
                    <span className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${
                      chapter.intelligence_available !== false
                        ? isDark ? "bg-cyan-500/15 text-cyan-300" : "bg-cyan-100 text-cyan-700"
                        : isDark ? "bg-white/8 text-slate-500" : "bg-stone-100 text-stone-500"
                    }`}>
                      {chapter.intelligence_available !== false ? "Intel ready" : "Intel locked"}
                    </span>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => router.push(`/${bookId}/chapter/${chapter.number}`)}
                    className={`rounded-full border px-4 py-2 text-sm font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
                  >
                    Open
                  </button>
                  <button
                    type="button"
                    onClick={() => void setChapterRead(chapter.number, !chapter.read)}
                    disabled={readBusy === `chapter:${chapter.number}`}
                    className={`rounded-full border px-4 py-2 text-sm font-semibold ${chapter.read
                      ? isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-stone-200 bg-stone-50 text-stone-600"
                      : isDark ? "border-violet-300/20 bg-violet-400/10 text-violet-100" : "border-violet-200 bg-violet-50 text-violet-800"
                    } disabled:opacity-50`}
                  >
                    {readBusy === `chapter:${chapter.number}` ? "Saving..." : chapter.read ? "Mark unread" : "Mark read"}
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}
