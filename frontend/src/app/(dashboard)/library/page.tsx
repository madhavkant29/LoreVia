"use client"

import { useEffect, useState } from "react"
import type { Route } from "next"
import Link from "next/link"

import { UploadModal } from "@/components/modals/UploadModal"
import { booksApi } from "@/lib/api/books"
import { API_BASE } from "@/lib/constants"
import { SUPPORT_EMAIL } from "@/lib/constants/contact"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book } from "@/types/book"

const FREE_TOKEN_BUDGET = 250000

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-stone-200 text-stone-700",
  processing: "bg-amber-100 text-amber-800",
  ready: "bg-emerald-100 text-emerald-800",
  failed: "bg-rose-100 text-rose-700",
}

function titleInitials(title: string) {
  return title
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("")
}

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

export default function LibraryPage() {
  const [books, setBooks] = useState<Book[]>([])
  const [loading, setLoading] = useState(true)
  const [showUpload, setShowUpload] = useState(false)
  const [busyBookId, setBusyBookId] = useState<string | null>(null)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  const load = () => booksApi.list(true).then(setBooks).finally(() => setLoading(false))

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    if (loading) return
    const hasProcessingBook = books.some((book) => book.status === "processing" || (!book.cover_url && book.format === "pdf"))
    if (!hasProcessingBook) return

    const interval = window.setInterval(() => {
      load()
    }, 5000)

    return () => window.clearInterval(interval)
  }, [books, loading])

  const visibleBooks = books.filter((book) => !book.hidden_at)
  const activeBooks = visibleBooks.filter((book) => !book.archived_at)
  const archivedBooks = visibleBooks.filter((book) => !!book.archived_at)
  const consumedTokens = books.reduce((sum, book) => sum + (book.total_tokens ?? 0), 0)
  const tokenBudgetUsedPct = Math.min(100, Math.round((consumedTokens / FREE_TOKEN_BUDGET) * 100))

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
    <div
      className={`min-h-screen transition-colors ${
        isDark
          ? "bg-[linear-gradient(180deg,#000000_0%,#060606_44%,#0d0d0d_100%)] text-slate-100"
          : "bg-[linear-gradient(180deg,#fcf7ef_0%,#f8f3eb_42%,#f4f0ea_100%)] text-stone-950"
      }`}
    >
      <div className="mx-auto max-w-7xl px-4 pb-16 pt-6 sm:px-6 lg:px-8">
        <section
          className={`overflow-hidden rounded-[2rem] border shadow-[0_28px_100px_-60px_rgba(79,70,229,0.24)] ${
            isDark
              ? "border-white/10 bg-[radial-gradient(circle_at_top,rgba(99,102,241,0.16),transparent_34%),linear-gradient(180deg,rgba(11,24,48,0.92),rgba(10,20,38,0.88))]"
              : "border-white/70 bg-[radial-gradient(circle_at_top,#f8f4ff,transparent_34%),linear-gradient(180deg,rgba(255,255,255,0.92),rgba(255,255,255,0.76))]"
          }`}
        >
          <div className="flex flex-col gap-8 px-6 py-7 sm:px-8 lg:flex-row lg:items-end lg:justify-between lg:px-10 lg:py-10">
            <div className="max-w-3xl">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.34em] ${isDark ? "text-indigo-300" : "text-violet-500"}`}>Library</p>
              <h1 className={`mt-3 font-serif text-4xl tracking-tight sm:text-5xl ${isDark ? "text-white" : "text-stone-950"}`}>My Library</h1>
              <p className={`mt-3 max-w-2xl text-base leading-8 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                Covers stay visible, reading progress stays grounded, and your books remain organized without noisy side panels competing with the shelf.
              </p>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <Link
                href="/notes"
                className={`inline-flex items-center justify-center rounded-[1.1rem] border px-6 py-3.5 text-sm font-semibold transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white/85 text-stone-700 hover:bg-white"}`}
              >
                Notes
              </Link>
              <button
                onClick={() => setShowUpload(true)}
                className="inline-flex items-center justify-center rounded-[1.1rem] bg-[linear-gradient(135deg,#4f46e5,#4338ca)] px-6 py-3.5 text-sm font-semibold text-white shadow-[0_18px_40px_-24px_rgba(79,70,229,0.7)] transition hover:translate-y-[-1px]"
              >
                Upload Book
              </button>
              <div className={`rounded-[1.1rem] border px-5 py-3 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-300" : "border-stone-200 bg-white/80 text-stone-500"}`}>
                {visibleBooks.length} visible books
              </div>
            </div>
          </div>

          <div className={`grid gap-3 border-t px-6 py-5 sm:grid-cols-3 sm:px-8 lg:px-10 ${isDark ? "border-white/10" : "border-stone-200/70"}`}>
            <OverviewMetric label="Active shelf" value={String(activeBooks.length)} note="Ready to open" isDark={isDark} />
            <OverviewMetric label="Archived shelf" value={String(archivedBooks.length)} note="Quiet but preserved" isDark={isDark} />
            <OverviewMetric label="AI budget used" value={`${tokenBudgetUsedPct}%`} note={`${consumedTokens.toLocaleString()} tracked tokens`} isDark={isDark} />
          </div>
        </section>

        <div className="mt-8 space-y-10">
          {loading ? (
            <div className={`rounded-[1.75rem] border border-dashed py-20 text-center ${isDark ? "border-white/15 bg-white/5 text-slate-400" : "border-stone-300 bg-white/60 text-stone-400"}`}>
              Loading your shelves...
            </div>
          ) : (
            <>
              <ShelfSection
                title="Current shelf"
                subtitle="Books still in your main reading workspace."
                emptyTitle="No active books yet"
                emptyBody="Upload a PDF or EPUB and LoreVia will turn it into a progress-aware reading space."
                books={activeBooks}
                busyBookId={busyBookId}
                onArchive={(id) => handleArchive(id, true)}
                onRestore={(id) => handleArchive(id, false)}
                onRemove={handleRemove}
                isDark={isDark}
              />

              <ShelfSection
                title="Archive"
                subtitle="Books you want to retain without keeping them in the primary shelf."
                emptyTitle="Nothing archived"
                emptyBody="Archived books stay counted for quotas while moving out of the main shelf."
                books={archivedBooks}
                busyBookId={busyBookId}
                onArchive={(id) => handleArchive(id, true)}
                onRestore={(id) => handleArchive(id, false)}
                onRemove={handleRemove}
                archived
                isDark={isDark}
              />

              <div className={`rounded-[1.6rem] border p-5 text-sm leading-7 ${isDark ? "border-white/10 bg-white/5 text-slate-300" : "border-stone-200/80 bg-white/72 text-stone-600"}`}>
                <p className={`text-[11px] font-semibold uppercase tracking-[0.3em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Support</p>
                <p className="mt-3">
                  If a cover or extraction looks off, email{" "}
                  <a
                    href={`mailto:${SUPPORT_EMAIL}`}
                    className={`font-medium underline underline-offset-4 ${isDark ? "text-white decoration-white/20" : "text-stone-900 decoration-stone-300"}`}
                  >
                    {SUPPORT_EMAIL}
                  </a>.
                </p>
              </div>
            </>
          )}
        </div>
      </div>

      {showUpload && <UploadModal onClose={() => { setShowUpload(false); load() }} />}
    </div>
  )
}

function OverviewMetric({ label, value, note, isDark }: { label: string; value: string; note: string; isDark: boolean }) {
  return (
    <div className={`rounded-[1.35rem] border p-4 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200/80 bg-white/85"}`}>
      <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>{label}</p>
      <p className={`mt-2 text-3xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{value}</p>
      <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{note}</p>
    </div>
  )
}

function ShelfSection({
  title,
  subtitle,
  emptyTitle,
  emptyBody,
  books,
  busyBookId,
  onArchive,
  onRestore,
  onRemove,
  archived = false,
  isDark,
}: {
  title: string
  subtitle: string
  emptyTitle: string
  emptyBody: string
  books: Book[]
  busyBookId: string | null
  onArchive: (id: string) => void
  onRestore: (id: string) => void
  onRemove: (id: string) => void
  archived?: boolean
  isDark: boolean
}) {
  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className={`font-serif text-3xl ${isDark ? "text-white" : "text-stone-950"}`}>{title}</h2>
          <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{subtitle}</p>
        </div>
        <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{books.length} books</p>
      </div>

      {books.length === 0 ? (
        <div className={`rounded-[1.75rem] border border-dashed py-14 text-center ${isDark ? "border-white/15 bg-white/5" : "border-stone-300 bg-white/60"}`}>
          <p className={`text-lg font-medium ${isDark ? "text-white" : "text-stone-700"}`}>{emptyTitle}</p>
          <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{emptyBody}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 xl:grid-cols-3">
          {books.map((book) => (
            <article
              key={book.id}
              className={`overflow-hidden rounded-[1.75rem] border shadow-[0_24px_80px_-60px_rgba(120,53,15,0.28)] transition hover:-translate-y-0.5 ${
                isDark ? "border-white/10 bg-[#0e1730]" : "border-stone-200/80 bg-white/88"
              }`}
            >
              <div className="hidden p-5 sm:block">
                <div className={`rounded-[1.3rem] border p-4 ${isDark ? "border-white/10 bg-[#13203d]" : "border-stone-200 bg-stone-50"}`}>
                  <div className={`aspect-[1.45/1] overflow-hidden rounded-[1rem] ${isDark ? "bg-[#081120]" : "bg-white"}`}>
                    <BookCover book={book} isDark={isDark} />
                  </div>
                </div>

                <div className="flex items-start justify-between gap-4 px-1 pb-1 pt-4">
                  <div className="min-w-0">
                    <h3 className={`line-clamp-2 font-serif text-[2rem] leading-[1.05] ${isDark ? "text-white" : "text-stone-950"}`}>{book.title}</h3>
                    {book.author ? <p className={`mt-2 text-lg italic ${isDark ? "text-slate-400" : "text-stone-500"}`}>{book.author}</p> : null}
                    {book.series_name ? (
                      <p className={`mt-2 text-sm font-medium ${isDark ? "text-indigo-200" : "text-violet-600"}`}>
                        {book.series_order ? `${book.series_name} · Vol. ${book.series_order}` : book.series_name}
                      </p>
                    ) : null}
                  </div>
                  <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] ${STATUS_COLORS[book.status] ?? STATUS_COLORS.pending}`}>
                    {book.status}
                  </span>
                </div>

                <div className={`mt-4 border-t px-1 pt-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <MetaCell label="Genre" value={book.genre ? capitalize(book.genre) : "Unknown"} isDark={isDark} />
                    <MetaCell label="Chapters" value={book.total_chapters ? String(book.total_chapters) : "Syncing"} align="right" isDark={isDark} />
                  </div>

                  <div className="mt-4">
                    <div className={`mb-2 flex items-center justify-between text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                      <span>Reading progress</span>
                      <span className={isDark ? "font-medium text-white" : "font-medium text-stone-900"}>{Math.round(book.progress_pct ?? 0)}%</span>
                    </div>
                    <div className={`h-2 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-stone-200"}`}>
                      <div
                        className="h-full rounded-full bg-[linear-gradient(90deg,#5b4cf0,#7c6cff)]"
                        style={{ width: `${Math.max(0, Math.min(book.progress_pct ?? 0, 100))}%` }}
                      />
                    </div>
                  </div>

                  <div className="mt-5 flex flex-wrap gap-2">
                    <Link
                      href={`/${book.id}`}
                      className="rounded-full bg-[linear-gradient(135deg,#4f46e5,#4338ca)] px-5 py-2.5 text-sm font-semibold text-white shadow-[0_16px_36px_-22px_rgba(79,70,229,0.75)] transition hover:translate-y-[-1px]"
                    >
                      Open
                    </Link>
                    {book.mode === "author" ? (
                      <>
                        <Link
                          href={`/${book.id}/manuscript` as Route}
                          className={`rounded-full border px-5 py-2.5 text-sm font-medium transition ${isDark ? "border-emerald-400/30 text-emerald-200 hover:bg-emerald-400/10" : "border-emerald-200 text-emerald-700 hover:bg-emerald-50"}`}
                        >
                          Manage chapters
                        </Link>
                        <Link
                          href="/notes"
                          className={`rounded-full border px-5 py-2.5 text-sm font-medium transition ${isDark ? "border-white/15 text-slate-200 hover:bg-white/5" : "border-stone-300 text-stone-700 hover:bg-stone-50"}`}
                        >
                          Notes
                        </Link>
                      </>
                    ) : null}
                    {archived ? (
                      <button
                        onClick={() => onRestore(book.id)}
                        disabled={busyBookId === book.id}
                        className={`rounded-full border px-5 py-2.5 text-sm font-medium transition disabled:opacity-60 ${isDark ? "border-white/15 text-slate-200 hover:bg-white/5" : "border-stone-300 text-stone-700 hover:bg-stone-50"}`}
                      >
                        Restore
                      </button>
                    ) : (
                      <button
                        onClick={() => onArchive(book.id)}
                        disabled={busyBookId === book.id}
                        className={`rounded-full border px-5 py-2.5 text-sm font-medium transition disabled:opacity-60 ${isDark ? "border-white/15 text-slate-200 hover:bg-white/5" : "border-stone-300 text-stone-700 hover:bg-stone-50"}`}
                      >
                        Archive
                      </button>
                    )}
                    <button
                      onClick={() => onRemove(book.id)}
                      disabled={busyBookId === book.id}
                      className="rounded-full border border-rose-200 px-5 py-2.5 text-sm font-medium text-rose-700 transition hover:bg-rose-50 disabled:opacity-60"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              </div>

              <div className="block p-5 sm:hidden">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className={`line-clamp-2 font-serif text-[2.1rem] leading-[0.98] ${isDark ? "text-white" : "text-stone-950"}`}>{book.title}</h3>
                    {book.author ? <p className={`mt-2 text-base ${isDark ? "text-slate-400" : "text-stone-500"}`}>{book.author}</p> : null}
                    {book.series_name ? (
                      <p className={`mt-2 text-sm font-medium ${isDark ? "text-indigo-200" : "text-violet-600"}`}>
                        {book.series_order ? `${book.series_name} · Vol. ${book.series_order}` : book.series_name}
                      </p>
                    ) : null}
                  </div>
                  <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em] ${STATUS_COLORS[book.status] ?? STATUS_COLORS.pending}`}>
                    {book.status}
                  </span>
                </div>

                <div className={`mt-5 border-t pt-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
                  <div className="grid grid-cols-[1fr_1fr_auto] items-end gap-4">
                    <MetaCell label="Genre" value={book.genre ? capitalize(book.genre) : "Unknown"} isDark={isDark} />
                    <MetaCell label="Chapters" value={book.total_chapters ? `${book.total_chapters} chapters` : "Syncing"} isDark={isDark} />
                    <Link href={`/${book.id}`} className={`rounded-full px-3 py-2 text-xs font-semibold ${isDark ? "bg-white/10 text-white" : "bg-stone-100 text-stone-700"}`}>
                      Open
                    </Link>
                  </div>
                </div>

                <div className="mt-4 flex items-center gap-2">
                  {book.mode === "author" ? (
                    <>
                      <Link href={`/${book.id}/manuscript` as Route} className={`rounded-full border px-4 py-2 text-sm ${isDark ? "border-emerald-400/30 text-emerald-200" : "border-emerald-200 text-emerald-700"}`}>
                        Chapters
                      </Link>
                      <Link href="/notes" className={`rounded-full border px-4 py-2 text-sm ${isDark ? "border-white/15 text-slate-200" : "border-stone-300 text-stone-700"}`}>
                        Notes
                      </Link>
                    </>
                  ) : null}
                  {archived ? (
                    <button
                      onClick={() => onRestore(book.id)}
                      disabled={busyBookId === book.id}
                      className={`rounded-full border px-4 py-2 text-sm disabled:opacity-60 ${isDark ? "border-white/15 text-slate-200" : "border-stone-300 text-stone-700"}`}
                    >
                      Restore
                    </button>
                  ) : (
                    <button
                      onClick={() => onArchive(book.id)}
                      disabled={busyBookId === book.id}
                      className={`rounded-full border px-4 py-2 text-sm disabled:opacity-60 ${isDark ? "border-white/15 text-slate-200" : "border-stone-300 text-stone-700"}`}
                    >
                      Archive
                    </button>
                  )}
                  <button
                    onClick={() => onRemove(book.id)}
                    disabled={busyBookId === book.id}
                    className="rounded-full border border-rose-200 px-4 py-2 text-sm text-rose-700 disabled:opacity-60"
                  >
                    Remove
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

function BookCover({ book, isDark }: { book: Book; isDark: boolean }) {
  const [failed, setFailed] = useState(false)
  const src = !failed ? coverSrc(book.cover_url) ?? book.cover_url ?? null : null

  if (src) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt={`${book.title} cover`}
        className={`h-full w-full ${book.format === "pdf" ? "object-contain p-2" : "object-cover object-top"}`}
        onError={() => setFailed(true)}
      />
    )
  }

  return (
    <div className={`flex h-full w-full flex-col justify-between p-5 ${isDark ? "bg-[linear-gradient(150deg,#18294f,#0b1222_60%,#101b34)] text-white" : "bg-[linear-gradient(150deg,#f4ecda,#ffffff_60%,#ecebff)] text-stone-900"}`}>
      <span className={`text-[0.65rem] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-indigo-200" : "text-violet-600"}`}>LoreVia</span>
      <div>
        <p className="text-3xl font-semibold leading-none">{titleInitials(book.title)}</p>
        <p className={`mt-3 line-clamp-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{book.title}</p>
      </div>
    </div>
  )
}

function MetaCell({ label, value, align = "left", isDark }: { label: string; value: string; align?: "left" | "right"; isDark: boolean }) {
  return (
    <div className={align === "right" ? "text-right" : ""}>
      <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{label}</p>
      <p className={`mt-1 text-base font-medium ${isDark ? "text-white" : "text-stone-900"}`}>{value}</p>
    </div>
  )
}

function capitalize(value: string) {
  return value.replace(/(^|\s)\S/g, (char) => char.toUpperCase())
}
