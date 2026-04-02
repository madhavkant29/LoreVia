"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { booksApi } from "@/lib/api/books"
import type { Book } from "@/types/book"
import { UploadModal } from "@/components/modals/UploadModal"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-stone-200 text-stone-700",
  processing: "bg-amber-100 text-amber-800",
  ready: "bg-emerald-100 text-emerald-800",
  failed: "bg-rose-100 text-rose-700",
}

export default function LibraryPage() {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [books, setBooks] = useState<Book[]>([])
  const [loading, setLoading] = useState(true)
  const [showUpload, setShowUpload] = useState(false)
  const [busyBookId, setBusyBookId] = useState<string | null>(null)

  const load = () => booksApi.list(true).then(setBooks).finally(() => setLoading(false))

  useEffect(() => {
    load()
  }, [])

  const visibleBooks = books.filter((book) => !book.hidden_at)
  const activeBooks = visibleBooks.filter((book) => !book.archived_at)
  const archivedBooks = visibleBooks.filter((book) => !!book.archived_at)
  const consumedBooks = books.length
  const consumedTokens = books.reduce((sum, book) => sum + (book.total_tokens ?? 0), 0)

  async function handleArchive(bookId: string, archived: boolean) {
    setBusyBookId(bookId)
    try {
      await booksApi.archive(bookId, archived)
      await load()
    } finally {
      setBusyBookId(null)
    }
  }

  async function handleRemove(bookId: string) {
    const confirmed = window.confirm(
      "Remove this book from your library view? It will still count toward your upload and token usage."
    )
    if (!confirmed) return

    setBusyBookId(bookId)
    try {
      await booksApi.hide(bookId, true)
      await load()
    } finally {
      setBusyBookId(null)
    }
  }

  return (
    <div className="space-y-8">
      <section className={`rounded-[2rem] border p-6 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.45)] ${
        isDark
          ? "border-white/10 bg-[linear-gradient(135deg,rgba(120,53,15,0.18),rgba(15,23,42,0.82)_55%,rgba(14,116,144,0.18))]"
          : "border-stone-200 bg-[linear-gradient(135deg,#fff9ef,white_55%,#eef6ff)]"
      }`}>
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-amber-200" : "text-amber-700"}`}>Library</p>
            <h1 className={`mt-2 font-serif text-4xl ${isDark ? "text-white" : "text-stone-900"}`}>Your reading room</h1>
            <p className={`mt-3 text-sm leading-6 ${isDark ? "text-gray-300" : "text-stone-600"}`}>
              Archive books you want to keep, remove books you do not want in the UI anymore, and keep your usage history intact so upload limits cannot be reset by hiding entries.
            </p>
          </div>
          <button
            onClick={() => setShowUpload(true)}
            className={`rounded-full px-5 py-3 text-sm font-semibold transition ${
              isDark ? "bg-amber-300 text-stone-950 hover:bg-amber-200" : "bg-stone-900 text-white hover:bg-stone-800"
            }`}
          >
            Upload a book
          </button>
          <Link
            href="/public-studio"
            className={`rounded-full px-5 py-3 text-sm font-semibold transition ${
              isDark ? "border border-white/10 text-white hover:bg-white/10" : "border border-stone-300 text-stone-800 hover:bg-white"
            }`}
          >
            Public studio
          </Link>
        </div>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <MetricCard label="Visible books" value={String(visibleBooks.length)} note="Active plus archived" isDark={isDark} />
          <MetricCard label="Consumed uploads" value={String(consumedBooks)} note="Hidden books still count" isDark={isDark} />
          <MetricCard label="Consumed tokens" value={consumedTokens.toLocaleString()} note="Prevents free-tier abuse" isDark={isDark} />
        </div>
      </section>

      {loading ? (
        <div className={`rounded-3xl border border-dashed py-20 text-center ${isDark ? "border-white/15 text-gray-500" : "border-stone-300 text-stone-400"}`}>Loading your shelves...</div>
      ) : (
        <div className="space-y-10">
          <ShelfSection
            title="Currently reading"
            subtitle="Books still in your main shelf."
            emptyTitle="No active books"
            emptyBody="Upload a PDF or EPUB to build your first spoiler-aware reading workspace."
            books={activeBooks}
            isDark={isDark}
            busyBookId={busyBookId}
            onArchive={(id) => handleArchive(id, true)}
            onRestore={(id) => handleArchive(id, false)}
            onRemove={handleRemove}
          />

          <ShelfSection
            title="Archived shelf"
            subtitle="Books you want to keep without cluttering the main library."
            emptyTitle="No archived books"
            emptyBody="Archived books stay counted for quotas, but move into a quieter shelf."
            books={archivedBooks}
            isDark={isDark}
            busyBookId={busyBookId}
            onArchive={(id) => handleArchive(id, true)}
            onRestore={(id) => handleArchive(id, false)}
            onRemove={handleRemove}
            archived
          />
        </div>
      )}

      {showUpload && <UploadModal onClose={() => { setShowUpload(false); load() }} />}
    </div>
  )
}

function MetricCard({ label, value, note, isDark }: { label: string; value: string; note: string; isDark: boolean }) {
  return (
    <div className={`rounded-3xl border p-4 ${isDark ? "border-white/10 bg-white/5" : "border-white/70 bg-white/90"}`}>
      <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-gray-400" : "text-stone-500"}`}>{label}</p>
      <p className={`mt-2 text-3xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{value}</p>
      <p className={`mt-2 text-sm ${isDark ? "text-gray-400" : "text-stone-500"}`}>{note}</p>
    </div>
  )
}

function ShelfSection({
  title,
  subtitle,
  emptyTitle,
  emptyBody,
  books,
  isDark,
  busyBookId,
  onArchive,
  onRestore,
  onRemove,
  archived = false,
}: {
  title: string
  subtitle: string
  emptyTitle: string
  emptyBody: string
  books: Book[]
  isDark: boolean
  busyBookId: string | null
  onArchive: (id: string) => void
  onRestore: (id: string) => void
  onRemove: (id: string) => void
  archived?: boolean
}) {
  return (
    <section className="space-y-4">
      <div>
        <h2 className={`text-2xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{title}</h2>
        <p className={`mt-1 text-sm ${isDark ? "text-gray-400" : "text-stone-500"}`}>{subtitle}</p>
      </div>

      {books.length === 0 ? (
        <div className={`rounded-3xl border border-dashed py-14 text-center ${isDark ? "border-white/15 bg-white/5" : "border-stone-300 bg-stone-50"}`}>
          <p className={`text-lg font-medium ${isDark ? "text-white" : "text-stone-700"}`}>{emptyTitle}</p>
          <p className={`mt-2 text-sm ${isDark ? "text-gray-400" : "text-stone-500"}`}>{emptyBody}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
          {books.map((book) => (
            <article
              key={book.id}
              className={`group rounded-[1.75rem] border p-5 shadow-[0_20px_60px_-45px_rgba(15,23,42,0.55)] transition hover:-translate-y-0.5 hover:shadow-[0_28px_70px_-40px_rgba(15,23,42,0.35)] ${
                isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className={`line-clamp-2 text-lg font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{book.title}</h3>
                  {book.author && <p className={`mt-1 text-sm ${isDark ? "text-gray-400" : "text-stone-500"}`}>{book.author}</p>}
                </div>
                <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_COLORS[book.status] ?? STATUS_COLORS.pending}`}>
                  {book.status}
                </span>
              </div>

              <div className={`mt-4 flex flex-wrap gap-2 text-xs ${isDark ? "text-gray-400" : "text-stone-500"}`}>
                {book.is_public ? <span className="rounded-full bg-sky-100 px-3 py-1 text-sky-800">Public</span> : null}
                {book.series_name ? (
                  <span className={isDark ? "rounded-full bg-indigo-400/15 px-3 py-1 text-indigo-100" : "rounded-full bg-indigo-100 px-3 py-1 text-indigo-800"}>
                    {book.series_name}{book.series_order ? ` · Vol ${book.series_order}` : ""}
                  </span>
                ) : null}
                {book.genre && <span className={isDark ? "rounded-full bg-white/10 px-3 py-1 capitalize" : "rounded-full bg-stone-100 px-3 py-1 capitalize"}>{book.genre}</span>}
                {book.total_chapters && <span className={isDark ? "rounded-full bg-white/10 px-3 py-1" : "rounded-full bg-stone-100 px-3 py-1"}>{book.total_chapters} chapters</span>}
                {book.total_tokens ? <span className={isDark ? "rounded-full bg-white/10 px-3 py-1" : "rounded-full bg-stone-100 px-3 py-1"}>{book.total_tokens.toLocaleString()} tokens</span> : null}
                {book.is_truncated ? <span className="rounded-full bg-amber-100 px-3 py-1 text-amber-800">Truncated</span> : null}
              </div>

              <div className="mt-6 flex flex-wrap gap-2">
                <Link
                  href={`/${book.id}`}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition ${isDark ? "bg-amber-300 text-stone-950 hover:bg-amber-200" : "bg-stone-900 text-white hover:bg-stone-800"}`}
                >
                  Open
                </Link>
                {archived ? (
                  <button
                    onClick={() => onRestore(book.id)}
                    disabled={busyBookId === book.id}
                    className={`rounded-full px-4 py-2 text-sm font-medium transition disabled:opacity-60 ${isDark ? "border border-white/15 text-gray-200 hover:bg-white/10" : "border border-stone-300 text-stone-700 hover:bg-stone-50"}`}
                  >
                    Restore
                  </button>
                ) : (
                  <button
                    onClick={() => onArchive(book.id)}
                    disabled={busyBookId === book.id}
                    className={`rounded-full px-4 py-2 text-sm font-medium transition disabled:opacity-60 ${isDark ? "border border-white/15 text-gray-200 hover:bg-white/10" : "border border-stone-300 text-stone-700 hover:bg-stone-50"}`}
                  >
                    Archive
                  </button>
                )}
                <button
                  onClick={() => onRemove(book.id)}
                  disabled={busyBookId === book.id}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition disabled:opacity-60 ${isDark ? "border border-rose-400/30 text-rose-300 hover:bg-rose-400/10" : "border border-rose-200 text-rose-700 hover:bg-rose-50"}`}
                >
                  Remove from UI
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
