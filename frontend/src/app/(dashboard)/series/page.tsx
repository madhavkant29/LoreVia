"use client"

import { useEffect, useMemo, useState } from "react"
import { booksApi } from "@/lib/api/books"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book } from "@/types/book"

export default function SeriesPage() {
  const user = useAuthStore((state) => state.user)
  const { theme } = usePreferencesStore()
  const [books, setBooks] = useState<Book[]>([])
  const [busyBookId, setBusyBookId] = useState<string | null>(null)
  const isDark = theme === "dark"

  const load = () => booksApi.list().then(setBooks).catch(() => {})

  useEffect(() => {
    if (user?.tier === "pro" || user?.tier === "power" || user?.tier === "admin") {
      load()
    }
  }, [user?.tier])

  const groupedSeries = useMemo(() => {
    const groups = new Map<string, Book[]>()
    for (const book of books) {
      if (!book.series_name) continue
      const key = book.series_name.trim()
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key)!.push(book)
    }
    return Array.from(groups.entries())
      .map(([name, items]) => ({
        name,
        items: [...items].sort((a, b) => (a.series_order ?? 9999) - (b.series_order ?? 9999) || a.title.localeCompare(b.title)),
      }))
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [books])

  async function saveSeries(book: Book, seriesName: string, seriesOrder: number | null) {
    setBusyBookId(book.id)
    try {
      await booksApi.setSeries(book.id, {
        series_name: seriesName.trim() || null,
        series_order: seriesName.trim() ? seriesOrder : null,
      })
      await load()
    } finally {
      setBusyBookId(null)
    }
  }

  if (!user || user.tier === "free") {
    return (
      <div className={`rounded-[2rem] border p-8 ${isDark ? "border-white/10 bg-white/5" : "border-amber-300 bg-amber-50"}`}>
        <h1 className={`text-3xl font-serif ${isDark ? "text-white" : "text-stone-900"}`}>Series Workspace</h1>
        <p className={`mt-3 text-sm leading-7 ${isDark ? "text-gray-300" : "text-stone-700"}`}>
          Series mode is reserved for paid plans. It is designed for readers moving through multiple books who want earlier volumes to inform the next one without losing continuity.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <section className={`rounded-[2rem] border p-6 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.32)] ${isDark ? "border-white/10 bg-[linear-gradient(145deg,rgba(30,41,59,0.75),rgba(15,23,42,0.94)_55%,rgba(56,189,248,0.12))]" : "border-white/70 bg-[linear-gradient(145deg,#ffffff,#f8fbff_55%,#eef4ff)]"}`}>
        <p className={`text-xs font-semibold uppercase tracking-[0.3em] ${isDark ? "text-sky-200" : "text-sky-700"}`}>Series workspace</p>
        <h1 className={`mt-3 font-serif text-4xl ${isDark ? "text-white" : "text-stone-900"}`}>Hold the bigger picture across volumes.</h1>
        <p className={`mt-3 max-w-3xl text-sm leading-7 ${isDark ? "text-gray-300" : "text-stone-600"}`}>
          Assign books to a named series and set their volume order. This gives LoreVia a clean structural layer for saga-level memory and future cross-book context instead of treating each volume like an isolated island.
        </p>
      </section>

      {groupedSeries.length > 0 ? (
        <section className="space-y-4">
          <div>
            <h2 className={`text-2xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Current series lanes</h2>
            <p className={`mt-1 text-sm ${isDark ? "text-gray-400" : "text-stone-500"}`}>Books grouped here will preserve volume order for future series-wide recall and analysis.</p>
          </div>
          <div className="grid gap-4">
            {groupedSeries.map((group) => (
              <div key={group.name} className={`rounded-[1.6rem] border p-5 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white"}`}>
                <div className="flex items-center justify-between gap-3">
                  <h3 className={`text-xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{group.name}</h3>
                  <span className={isDark ? "rounded-full bg-white/10 px-3 py-1 text-xs text-gray-300" : "rounded-full bg-stone-100 px-3 py-1 text-xs text-stone-600"}>
                    {group.items.length} volume{group.items.length === 1 ? "" : "s"}
                  </span>
                </div>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  {group.items.map((book) => (
                    <div key={book.id} className={`rounded-2xl border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
                      <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{book.series_order ? `Vol ${book.series_order} · ` : ""}{book.title}</p>
                      {book.author ? <p className={`mt-1 text-xs ${isDark ? "text-gray-400" : "text-stone-500"}`}>{book.author}</p> : null}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="space-y-4">
        <div>
          <h2 className={`text-2xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Assign books to a series</h2>
          <p className={`mt-1 text-sm ${isDark ? "text-gray-400" : "text-stone-500"}`}>Name the series once, set the volume number, and keep the order clean.</p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {books.map((book) => (
            <SeriesEditorCard
              key={book.id}
              book={book}
              isDark={isDark}
              busy={busyBookId === book.id}
              onSave={saveSeries}
            />
          ))}
        </div>
      </section>
    </div>
  )
}

function SeriesEditorCard({
  book,
  isDark,
  busy,
  onSave,
}: {
  book: Book
  isDark: boolean
  busy: boolean
  onSave: (book: Book, seriesName: string, seriesOrder: number | null) => Promise<void>
}) {
  const [seriesName, setSeriesName] = useState(book.series_name ?? "")
  const [seriesOrder, setSeriesOrder] = useState<string>(book.series_order ? String(book.series_order) : "")

  return (
    <div className={`rounded-[1.75rem] border p-5 shadow-[0_20px_70px_-52px_rgba(15,23,42,0.28)] ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white"}`}>
      <p className={`text-lg font-medium ${isDark ? "text-white" : "text-gray-900"}`}>{book.title}</p>
      {book.author ? <p className={`mt-1 text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>{book.author}</p> : null}
      <div className="mt-4 space-y-3">
        <input
          value={seriesName}
          onChange={(e) => setSeriesName(e.target.value)}
          placeholder="Series name, e.g. Stormlight Archive"
          className={`w-full rounded-2xl border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-white placeholder:text-gray-500" : "border-stone-200 bg-stone-50 text-stone-900 placeholder:text-stone-400"}`}
        />
        <input
          value={seriesOrder}
          onChange={(e) => setSeriesOrder(e.target.value.replace(/[^\d]/g, ""))}
          placeholder="Volume number"
          className={`w-full rounded-2xl border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-white placeholder:text-gray-500" : "border-stone-200 bg-stone-50 text-stone-900 placeholder:text-stone-400"}`}
        />
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          onClick={() => onSave(book, seriesName, seriesOrder ? Number(seriesOrder) : null)}
          disabled={busy}
          className={`rounded-full px-4 py-2 text-sm font-medium transition disabled:opacity-60 ${isDark ? "bg-amber-300 text-stone-950 hover:bg-amber-200" : "bg-stone-900 text-white hover:bg-stone-800"}`}
        >
          {busy ? "Saving..." : "Save series"}
        </button>
        {book.series_name ? (
          <button
            onClick={() => {
              setSeriesName("")
              setSeriesOrder("")
              onSave(book, "", null)
            }}
            disabled={busy}
            className={`rounded-full px-4 py-2 text-sm font-medium transition disabled:opacity-60 ${isDark ? "border border-white/15 text-gray-200 hover:bg-white/10" : "border border-stone-300 text-stone-700 hover:bg-stone-50"}`}
          >
            Remove from series
          </button>
        ) : null}
      </div>
    </div>
  )
}
