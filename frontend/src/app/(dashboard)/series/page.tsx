"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"

import { booksApi } from "@/lib/api/books"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book, BookSeries } from "@/types/book"

export default function SeriesPage() {
  const user = useAuthStore((state) => state.user)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [series, setSeries] = useState<BookSeries[]>([])
  const [books, setBooks] = useState<Book[]>([])
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")

  async function load() {
    const [seriesRows, bookRows] = await Promise.all([booksApi.listSeries(), booksApi.list()])
    setSeries(seriesRows)
    setBooks(bookRows)
  }

  useEffect(() => {
    if (user?.tier === "pro" || user?.tier === "power" || user?.tier === "admin") {
      load().catch(() => {})
    }
  }, [user?.tier])

  const unassignedBooks = useMemo(
    () => books.filter((book) => !book.primary_series_id && !book.series_name),
    [books]
  )

  async function createSeries() {
    if (!name.trim()) return
    setBusyKey("create")
    try {
      await booksApi.createSeries({ name: name.trim(), description: description.trim() || null })
      setName("")
      setDescription("")
      await load()
    } finally {
      setBusyKey(null)
    }
  }

  if (!user || user.tier === "free") {
    return (
      <div className={`rounded-[2rem] border p-8 ${isDark ? "border-white/10 bg-white/5" : "border-amber-300 bg-amber-50"}`}>
        <h1 className={`text-3xl font-serif ${isDark ? "text-white" : "text-stone-900"}`}>Series workspace</h1>
        <p className={`mt-3 text-sm leading-7 ${isDark ? "text-gray-300" : "text-stone-700"}`}>
          Series mode is reserved for paid plans. It is built for readers carrying continuity across multiple books without losing where each volume stands.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <section className={`rounded-[2rem] border p-6 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.32)] ${isDark ? "border-white/10 bg-[linear-gradient(145deg,rgba(30,41,59,0.75),rgba(15,23,42,0.94)_55%,rgba(56,189,248,0.12))]" : "border-white/70 bg-[linear-gradient(145deg,#ffffff,#f8fbff_55%,#eef4ff)]"}`}>
        <p className={`text-xs font-semibold uppercase tracking-[0.3em] ${isDark ? "text-sky-200" : "text-sky-700"}`}>Series workspace</p>
        <h1 className={`mt-3 font-serif text-4xl ${isDark ? "text-white" : "text-stone-900"}`}>Track sagas as connected reading lanes, not isolated uploads.</h1>
        <p className={`mt-3 max-w-3xl text-sm leading-7 ${isDark ? "text-gray-300" : "text-stone-600"}`}>
          Create named series, slot books into proper volume order, mark earlier volumes as already finished, and let the bigger picture stay visible while each book keeps its own chapter history.
        </p>
      </section>

      <section className={`rounded-[1.75rem] border p-5 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white"}`}>
        <div className="grid gap-3 md:grid-cols-[1.2fr_1.5fr_auto]">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Create a new series"
            className={`rounded-2xl border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-white placeholder:text-gray-500" : "border-stone-200 bg-stone-50 text-stone-900 placeholder:text-stone-400"}`}
          />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Short note about this series"
            className={`rounded-2xl border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-white placeholder:text-gray-500" : "border-stone-200 bg-stone-50 text-stone-900 placeholder:text-stone-400"}`}
          />
          <button
            onClick={createSeries}
            disabled={busyKey === "create"}
            className={`rounded-full px-5 py-3 text-sm font-semibold transition disabled:opacity-60 ${isDark ? "bg-amber-300 text-stone-950 hover:bg-amber-200" : "bg-stone-900 text-white hover:bg-stone-800"}`}
          >
            {busyKey === "create" ? "Creating..." : "Create series"}
          </button>
        </div>
      </section>

      {series.length === 0 ? (
        <div className={`rounded-3xl border border-dashed py-14 text-center ${isDark ? "border-white/15 bg-white/5 text-gray-400" : "border-stone-300 bg-stone-50 text-stone-500"}`}>
          No series yet. Create one above, then start assigning books.
        </div>
      ) : (
        <div className="space-y-6">
          {series.map((lane) => (
            <section key={lane.id} className={`rounded-[1.75rem] border p-5 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white"}`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className={`text-2xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{lane.name}</h2>
                  {lane.description ? <p className={`mt-1 text-sm ${isDark ? "text-gray-400" : "text-stone-500"}`}>{lane.description}</p> : null}
                </div>
                <span className={isDark ? "rounded-full bg-white/10 px-3 py-1 text-xs text-gray-300" : "rounded-full bg-stone-100 px-3 py-1 text-xs text-stone-600"}>
                  {lane.books.length} volume{lane.books.length === 1 ? "" : "s"}
                </span>
              </div>

              {lane.books.length > 0 ? (
                <div className="mt-5 grid gap-4 lg:grid-cols-2">
                  {lane.books.map((book) => (
                    <SeriesBookCard
                      key={book.id}
                      laneId={lane.id}
                      book={book}
                      isDark={isDark}
                      busy={busyKey === `${lane.id}:${book.id}`}
                      onRefresh={load}
                      onBusy={setBusyKey}
                    />
                  ))}
                </div>
              ) : (
                <div className={`mt-5 rounded-2xl border border-dashed p-5 text-sm ${isDark ? "border-white/10 text-gray-400" : "border-stone-300 text-stone-500"}`}>
                  No books in this series yet.
                </div>
              )}

              <div className="mt-5">
                <p className={`mb-3 text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-gray-400" : "text-stone-500"}`}>Add a book</p>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {books
                    .filter((book) => !lane.books.find((item) => item.id === book.id))
                    .map((book) => (
                      <AddBookCard
                        key={book.id}
                        laneId={lane.id}
                        book={book}
                        isDark={isDark}
                        onRefresh={load}
                        onBusy={setBusyKey}
                        busy={busyKey === `add:${lane.id}:${book.id}`}
                      />
                    ))}
                </div>
              </div>
            </section>
          ))}
        </div>
      )}

      {unassignedBooks.length > 0 ? (
        <section className={`rounded-[1.75rem] border p-5 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white/80"}`}>
          <h2 className={`text-2xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Unassigned books</h2>
          <p className={`mt-1 text-sm ${isDark ? "text-gray-400" : "text-stone-500"}`}>These books are not connected to any series yet.</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {unassignedBooks.map((book) => (
              <span key={book.id} className={isDark ? "rounded-full bg-white/10 px-3 py-1 text-sm text-gray-200" : "rounded-full bg-stone-100 px-3 py-1 text-sm text-stone-700"}>
                {book.title}
              </span>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  )
}

function SeriesBookCard({
  laneId,
  book,
  isDark,
  busy,
  onRefresh,
  onBusy,
}: {
  laneId: string
  book: Book
  isDark: boolean
  busy: boolean
  onRefresh: () => Promise<void>
  onBusy: (value: string | null) => void
}) {
  const progress = book.progress_pct ?? 0

  return (
    <div className={`rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>
            {book.series_order ? `Vol ${book.series_order} · ` : ""}
            {book.title}
          </p>
          {book.author ? <p className={`mt-1 text-xs ${isDark ? "text-gray-400" : "text-stone-500"}`}>{book.author}</p> : null}
        </div>
        <Link href={`/${book.id}`} className={`rounded-full px-3 py-1 text-xs font-semibold ${isDark ? "bg-white text-stone-950" : "bg-stone-900 text-white"}`}>
          Open
        </Link>
      </div>

      <div className="mt-4">
        <div className="mb-2 flex items-center justify-between text-xs">
          <span className={isDark ? "text-gray-400" : "text-stone-500"}>Completion</span>
          <span className={isDark ? "text-gray-200" : "text-stone-700"}>{progress}%</span>
        </div>
        <div className={`h-2 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-stone-200"}`}>
          <div className="h-full rounded-full bg-indigo-500" style={{ width: `${Math.max(0, Math.min(progress, 100))}%` }} />
        </div>
        <p className={`mt-2 text-xs ${isDark ? "text-gray-400" : "text-stone-500"}`}>
          {book.chapters_read_count ?? 0} read · {book.chapters_left ?? 0} left
        </p>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          onClick={async () => {
            onBusy(`${laneId}:${book.id}`)
            try {
              await booksApi.setSeriesBookStatus(laneId, book.id, true)
              await onRefresh()
            } finally {
              onBusy(null)
            }
          }}
          disabled={busy}
          className={`rounded-full px-4 py-2 text-sm font-medium transition disabled:opacity-60 ${isDark ? "bg-amber-300 text-stone-950 hover:bg-amber-200" : "bg-stone-900 text-white hover:bg-stone-800"}`}
        >
          {busy ? "Saving..." : "Mark book read"}
        </button>
        <button
          onClick={async () => {
            onBusy(`${laneId}:${book.id}`)
            try {
              await booksApi.removeBookFromSeries(laneId, book.id)
              await onRefresh()
            } finally {
              onBusy(null)
            }
          }}
          disabled={busy}
          className={`rounded-full px-4 py-2 text-sm font-medium transition disabled:opacity-60 ${isDark ? "border border-white/15 text-gray-200 hover:bg-white/10" : "border border-stone-300 text-stone-700 hover:bg-stone-50"}`}
        >
          Remove
        </button>
      </div>
    </div>
  )
}

function AddBookCard({
  laneId,
  book,
  isDark,
  onRefresh,
  onBusy,
  busy,
}: {
  laneId: string
  book: Book
  isDark: boolean
  onRefresh: () => Promise<void>
  onBusy: (value: string | null) => void
  busy: boolean
}) {
  const [position, setPosition] = useState(book.series_order ? String(book.series_order) : "")

  return (
    <div className={`rounded-2xl border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
      <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{book.title}</p>
      <div className="mt-3 flex gap-2">
        <input
          value={position}
          onChange={(e) => setPosition(e.target.value.replace(/[^\d]/g, ""))}
          placeholder="Vol"
          className={`w-20 rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-white placeholder:text-gray-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
        />
        <button
          onClick={async () => {
            onBusy(`add:${laneId}:${book.id}`)
            try {
              await booksApi.addBookToSeries(laneId, book.id, { position: position ? Number(position) : null })
              await onRefresh()
            } finally {
              onBusy(null)
            }
          }}
          disabled={busy}
          className={`flex-1 rounded-full px-4 py-2 text-sm font-medium transition disabled:opacity-60 ${isDark ? "bg-white text-stone-950 hover:bg-gray-200" : "bg-stone-900 text-white hover:bg-stone-800"}`}
        >
          {busy ? "Adding..." : "Add to series"}
        </button>
      </div>
    </div>
  )
}
