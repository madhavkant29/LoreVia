"use client"

import { useEffect, useState } from "react"
import type { Route } from "next"
import Link from "next/link"
import { useRouter } from "next/navigation"

import { UploadModal } from "@/components/modals/UploadModal"
import { authApi } from "@/lib/api/auth"
import { booksApi } from "@/lib/api/books"
import { SUPPORT_EMAIL } from "@/lib/constants/contact"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book } from "@/types/book"

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-stone-200 text-stone-700",
  processing: "bg-amber-100 text-amber-800",
  ready: "bg-emerald-100 text-emerald-800",
  failed: "bg-rose-100 text-rose-700",
}

const STATUS_COLORS_DARK: Record<string, string> = {
  pending: "border border-white/10 bg-white/5 text-[#E0E0E0]",
  processing: "border border-amber-400/30 bg-amber-400/10 text-amber-200",
  ready: "border border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  failed: "border border-rose-400/30 bg-rose-400/10 text-rose-200",
}

function statusPillClasses(status: string, isDark: boolean) {
  if (isDark) return STATUS_COLORS_DARK[status] ?? STATUS_COLORS_DARK.pending
  return STATUS_COLORS[status] ?? STATUS_COLORS.pending
}

function formatEtaLabel(seconds?: number | null) {
  if (typeof seconds !== "number" || Number.isNaN(seconds)) return null
  if (seconds <= 0) return "almost done"

  const minutes = Math.max(1, Math.round(seconds / 60))
  if (minutes < 60) return `${minutes} min left`

  const hours = Math.max(1, Math.round(minutes / 60))
  return `${hours} hr left`
}

function storyUnitLabel(workType?: Book["work_type"], plural = false) {
  if (workType === "screenplay") return plural ? "scenes" : "scene"
  return plural ? "chapters" : "chapter"
}

function storyUnitPrefix(workType?: Book["work_type"]) {
  return workType === "screenplay" ? "Sc." : "Ch."
}

function seriesOrderLabel(book: Book) {
  if (!book.series_name) return ""
  if (!book.series_order) return book.series_name
  const prefix = book.work_type === "screenplay" ? "Ep." : "Vol."
  return `${book.series_name} - ${prefix} ${book.series_order}`
}
function getProcessingSummary(book: Book) {
  const processing = book.processing
  if (!processing) return null

  const stage = (processing.stage ?? processing.status ?? "").toString().trim()
  const completed = typeof processing.chapters_completed === "number" ? processing.chapters_completed : null
  const total = typeof processing.chapters_total === "number" ? processing.chapters_total : book.total_chapters
  const progress = typeof processing.progress_pct === "number" ? processing.progress_pct : book.progress_pct
  const eta = formatEtaLabel(processing.eta_seconds)
  const chapterLabel =
    processing.last_chapter_number
      ? `${storyUnitPrefix(book.work_type)} ${processing.last_chapter_number}${processing.last_chapter_title ? ` - ${processing.last_chapter_title}` : ""}`
      : null

  const parts = [
    stage ? stage.replace(/_/g, " ") : null,
    completed !== null && total ? `${completed}/${total} ${storyUnitLabel(book.work_type, true)}` : null,
    typeof progress === "number" ? `${Math.round(progress)}%` : null,
    eta,
    chapterLabel,
  ].filter(Boolean)

  return parts.length > 0 ? parts.join(" · ") : null
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

function ProcessingLine({ book, isDark }: { book: Book; isDark: boolean }) {
  const summary = getProcessingSummary(book)
  if (!summary && book.status !== "processing") return null

  return <p className={`mt-2 text-xs ${isDark ? "text-amber-300/90" : "text-amber-700"}`}>{summary ?? "Processing in the background"}</p>
}

export default function LibraryPage() {
  const router = useRouter()
  const [books, setBooks] = useState<Book[]>([])
  const [loading, setLoading] = useState(true)
  const [showUpload, setShowUpload] = useState(false)
  const [uploadPreset, setUploadPreset] = useState<{ mode?: "reader" | "author"; existingBookId?: string }>({})
  const [busyBookId, setBusyBookId] = useState<string | null>(null)
  const [freeTokenBudget, setFreeTokenBudget] = useState<number>(250000)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  const load = () => booksApi.list(true).then(setBooks).finally(() => setLoading(false))

  useEffect(() => {
    authApi.getTierLimits().then(limits => setFreeTokenBudget(limits.free_total_token_budget))
  }, [])

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
  const authorBooks = visibleBooks.filter((book) => book.mode === "author")
  const consumedTokens = books.reduce((sum, book) => sum + (book.total_tokens ?? 0), 0)
  const tokenBudgetUsedPct = Math.min(100, Math.round((consumedTokens / freeTokenBudget) * 100))

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

  function handleAddChapter(bookId?: string) {
    const href = bookId ? (`/library/add-chapter?book=${bookId}` as Route) : ("/library/add-chapter" as Route)
    router.push(href)
  }

  return (
    <div
      className={`min-h-screen transition-colors ${
        isDark
          ? "bg-black text-[#E0E0E0]"
          : "bg-[linear-gradient(180deg,#fcf7ef_0%,#f8f3eb_42%,#f4f0ea_100%)] text-stone-950"
      }`}
    >
      <div className="mx-auto w-full px-3 pb-16 pt-6 sm:px-6 lg:px-8 xl:max-w-7xl">
        <section
          className={`overflow-hidden rounded-[2rem] border ${
            isDark
              ? "border-white/10 bg-[#0D0D0D]"
              : "border-white/70 bg-[radial-gradient(circle_at_top,#f8f4ff,transparent_34%),linear-gradient(180deg,rgba(255,255,255,0.92),rgba(255,255,255,0.76))]"
          }`}
        >
          <div className="flex flex-col gap-8 px-6 py-7 sm:px-8 lg:flex-row lg:items-end lg:justify-between lg:px-10 lg:py-10">
            <div className="max-w-3xl">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.34em] ${isDark ? "text-[#A0A0A0]" : "text-violet-500"}`}>Library</p>
              <h1 className={`mt-3 font-serif text-4xl tracking-tight sm:text-5xl ${isDark ? "text-[#E0E0E0]" : "text-stone-950"}`}>My Library</h1>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <button
                onClick={() => {
                  setUploadPreset({})
                  setShowUpload(true)
                }}
                className="inline-flex items-center justify-center rounded-[1.1rem] bg-[linear-gradient(135deg,#4f46e5,#4338ca)] px-6 py-3.5 text-sm font-semibold text-white shadow-[0_18px_40px_-24px_rgba(79,70,229,0.7)] transition hover:translate-y-[-1px]"
              >
                Upload Book
              </button>
              {authorBooks.length > 0 ? (
                <button
                  onClick={() => {
                    handleAddChapter(authorBooks[0]?.id)
                  }}
                  className={`inline-flex items-center justify-center rounded-[1.1rem] px-6 py-3.5 text-sm font-semibold transition ${
                    isDark
                      ? "border border-white/12 bg-[#111111] text-[#E0E0E0] hover:bg-[#171717]"
                      : "border border-stone-200 bg-white text-stone-800 hover:bg-stone-50"
                  }`}
                >
                  Add Scene
                </button>
              ) : null}
              <div
                className={`rounded-[1.1rem] border px-5 py-3 text-sm ${
                  isDark ? "border-white/12 bg-[#0B0B0B] text-[#A0A0A0]" : "border-stone-200 bg-white/80 text-stone-500"
                }`}
              >
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
            <div
              className={`rounded-[1.75rem] border border-dashed py-20 text-center ${
                isDark ? "border-white/15 bg-[#0B0B0B] text-[#A0A0A0]" : "border-stone-300 bg-white/60 text-stone-400"
              }`}
            >
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
                onOpenBook={(id) => router.push(`/${id}`)}
                onAddChapter={handleAddChapter}
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
                onOpenBook={(id) => router.push(`/${id}`)}
                onAddChapter={handleAddChapter}
              />

              <div
                className={`rounded-[1.6rem] border p-5 text-sm leading-7 ${
                  isDark ? "border-white/12 bg-[#0B0B0B] text-[#A0A0A0]" : "border-stone-200/80 bg-white/72 text-stone-600"
                }`}
              >
                <p className={`text-[11px] font-semibold uppercase tracking-[0.3em] ${isDark ? "text-[#A0A0A0]" : "text-stone-400"}`}>Support</p>
                <p className="mt-3">
                  If a cover or extraction looks off, email{" "}
                  <a
                    href={`mailto:${SUPPORT_EMAIL}`}
                    className={`font-medium underline underline-offset-4 ${isDark ? "text-[#E0E0E0] decoration-white/20" : "text-stone-900 decoration-stone-300"}`}
                  >
                    {SUPPORT_EMAIL}
                  </a>.
                </p>
              </div>
            </>
          )}
        </div>
      </div>

      {showUpload && (
        <UploadModal
          initialMode={uploadPreset.mode}
          initialExistingBookId={uploadPreset.existingBookId}
          onClose={() => {
            setShowUpload(false)
            setUploadPreset({})
            load()
          }}
        />
      )}
    </div>
  )
}

function OverviewMetric({ label, value, note, isDark }: { label: string; value: string; note: string; isDark: boolean }) {
  return (
    <div className={`rounded-[1.35rem] border p-4 ${isDark ? "border-white/12 bg-[#0B0B0B]" : "border-stone-200/80 bg-white/85"}`}>
      <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-[#A0A0A0]" : "text-stone-400"}`}>{label}</p>
      <p className={`mt-2 text-3xl font-semibold ${isDark ? "text-[#E0E0E0]" : "text-stone-950"}`}>{value}</p>
      <p className={`mt-2 text-sm ${isDark ? "text-[#A0A0A0]" : "text-stone-500"}`}>{note}</p>
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
  onOpenBook,
  onAddChapter,
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
  onOpenBook: (id: string) => void
  onAddChapter: (id?: string) => void
  archived?: boolean
  isDark: boolean
}) {
  const [menuOpen, setMenuOpen] = useState<string | null>(null)
  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className={`font-serif text-3xl ${isDark ? "text-[#E0E0E0]" : "text-stone-950"}`}>{title}</h2>
          <p className={`mt-1 text-sm ${isDark ? "text-[#A0A0A0]" : "text-stone-500"}`}>{subtitle}</p>
        </div>
        <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-[#808080]" : "text-stone-400"}`}>{books.length} books</p>
      </div>

      {books.length === 0 ? (
        <div className={`rounded-[1.75rem] border border-dashed py-14 text-center ${isDark ? "border-white/15 bg-[#0B0B0B]" : "border-stone-300 bg-white/60"}`}>
          <p className={`text-lg font-medium ${isDark ? "text-[#E0E0E0]" : "text-stone-700"}`}>{emptyTitle}</p>
          <p className={`mt-2 text-sm ${isDark ? "text-[#A0A0A0]" : "text-stone-500"}`}>{emptyBody}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 xl:grid-cols-3">
          {books.map((book) => (
            <article
              key={book.id}
              role="link"
              tabIndex={0}
              onClick={() => onOpenBook(book.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault()
                  onOpenBook(book.id)
                }
              }}
              className={`relative ${menuOpen === book.id ? "z-50" : "z-0"} rounded-[1.5rem] transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_8px_40px_-12px_rgba(99,102,241,0.25)] focus:outline-none focus-visible:ring-2 focus-visible:ring-white/40 ${
                isDark
                  ? "bg-[#0A0A0A] hover:bg-[#0D0D0D]"
                  : "bg-white hover:bg-stone-50"
              }`}
            >
              <div className="hidden p-6 sm:block">
                <div className={`aspect-[1.5/1] overflow-hidden rounded-[1.25rem] ${isDark ? "bg-black" : "bg-stone-100"}`}>
                  <BookCover book={book} isDark={isDark} />
                </div>

                <div className="mt-5 space-y-3">
                  <div className="min-w-0">
                    <h3 className={`line-clamp-2 font-serif text-[1.75rem] font-medium leading-tight ${isDark ? "text-[#E0E0E0]" : "text-stone-950"}`}>{book.title}</h3>
                    {book.author ? <p className={`mt-1 text-sm ${isDark ? "text-[#808080]" : "text-stone-500"}`}>{book.author}</p> : null}
                    {book.series_name ? (
                      <p className={`mt-1 text-xs font-medium uppercase tracking-wider ${isDark ? "text-violet-400" : "text-violet-600"}`}>
                        {book.series_order ? `${seriesOrderLabel(book)}` : book.series_name}
                      </p>
                    ) : null}
                    <p className={`mt-1 text-xs uppercase tracking-wider ${isDark ? "text-[#606060]" : "text-stone-400"}`}>{book.status}</p>
                    <ProcessingLine book={book} isDark={isDark} />
                  </div>

                  <div className={`pt-3 ${isDark ? "border-t border-white/8" : "border-t border-stone-200"}`}>
                    <div className={`flex items-center justify-between text-xs ${isDark ? "text-[#707070]" : "text-stone-500"}`}>
                      <span>{Math.round(book.progress_pct ?? 0)}% complete</span>
                      <span>{book.total_chapters ? `${book.total_chapters} ${storyUnitLabel(book.work_type, true)}` : "Syncing"}</span>
                    </div>

                    <div className="mt-2">
                      <div className={`h-1 overflow-hidden rounded-full ${isDark ? "bg-white/8" : "bg-stone-200"}`}>
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-violet-500 to-indigo-500"
                          style={{ width: `${Math.max(0, Math.min(book.progress_pct ?? 0, 100))}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 pt-2">
                    <button
                      onClick={(event) => {
                        event.stopPropagation()
                        if (book.mode === "author") {
                          window.location.href = `/${book.id}/manuscript`
                        } else {
                          onOpenBook(book.id)
                        }
                      }}
                      className={`min-w-0 flex-1 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                        isDark
                          ? "bg-white text-black hover:bg-white/90"
                          : "bg-stone-900 text-white hover:bg-stone-800"
                      }`}
                    >
                      {book.mode === "author" ? `Manage ${storyUnitLabel(book.work_type, true)}` : "Continue Reading"}
                    </button>

                    {book.mode === "author" ? (
                      <button
                        onClick={(event) => {
                          event.stopPropagation()
                          onAddChapter(book.id)
                        }}
                        className={`rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                          isDark
                            ? "border border-white/12 bg-white/5 text-[#E0E0E0] hover:bg-white/10"
                            : "border border-stone-200 bg-stone-50 text-stone-800 hover:bg-stone-100"
                        }`}
                      >
                        Add Scene
                      </button>
                    ) : null}

                    <div className="relative">
                      <button
                        onClick={(event) => {
                          event.stopPropagation()
                          setMenuOpen(menuOpen === book.id ? null : book.id)
                        }}
                        className={`rounded-lg p-2.5 transition ${isDark ? "hover:bg-white/10 text-[#A0A0A0]" : "hover:bg-stone-100 text-stone-500"}`}
                      >
                        <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
                        </svg>
                      </button>

                      {menuOpen === book.id && (
                        <div className={`absolute right-0 bottom-full mb-2 sm:bottom-auto sm:top-full sm:mt-2 sm:mb-0 z-50 w-44 overflow-hidden rounded-xl border py-1 shadow-2xl ${
                          isDark
                            ? "border-white/12 bg-[#0D0D0D]"
                            : "border-stone-200 bg-white"
                        }`}>
                          {book.mode === "author" && (
                            <button
                              onClick={(event) => {
                                event.stopPropagation()
                                onAddChapter(book.id)
                                setMenuOpen(null)
                              }}
                              className={`block w-full px-4 py-2 text-left text-sm transition ${isDark ? "text-[#E0E0E0] hover:bg-white/10" : "text-stone-700 hover:bg-stone-50"}`}
                            >
                              Add Scene
                            </button>
                          )}
                          {book.mode === "author" && (
                            <Link
                              href="/notes"
                              onClick={(event) => {
                                event.stopPropagation()
                                setMenuOpen(null)
                              }}
                              className={`block px-4 py-2 text-sm transition ${isDark ? "text-[#E0E0E0] hover:bg-white/10" : "text-stone-700 hover:bg-stone-50"}`}
                            >
                              Notes
                            </Link>
                          )}
                          {archived ? (
                            <button
                              onClick={(event) => {
                                event.stopPropagation()
                                onRestore(book.id)
                                setMenuOpen(null)
                              }}
                              disabled={busyBookId === book.id}
                              className={`w-full px-4 py-2 text-left text-sm transition disabled:opacity-60 ${isDark ? "text-[#E0E0E0] hover:bg-white/10" : "text-stone-700 hover:bg-stone-50"}`}
                            >
                              Restore
                            </button>
                          ) : (
                            <button
                              onClick={(event) => {
                                event.stopPropagation()
                                onArchive(book.id)
                                setMenuOpen(null)
                              }}
                              disabled={busyBookId === book.id}
                              className={`w-full px-4 py-2 text-left text-sm transition disabled:opacity-60 ${isDark ? "text-[#E0E0E0] hover:bg-white/10" : "text-stone-700 hover:bg-stone-50"}`}
                            >
                              Archive
                            </button>
                          )}
                          <button
                            onClick={(event) => {
                              event.stopPropagation()
                              onRemove(book.id)
                              setMenuOpen(null)
                            }}
                            disabled={busyBookId === book.id}
                            className={`w-full px-4 py-2 text-left text-sm transition disabled:opacity-60 ${
                              isDark ? "text-rose-300 hover:bg-rose-500/10" : "text-rose-600 hover:bg-rose-50"
                            }`}
                          >
                            Remove
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <div className="block px-3 pb-6 pt-5 sm:hidden">
                <div className={`aspect-[1.5/1] overflow-hidden rounded-[1.25rem] ${isDark ? "bg-black" : "bg-stone-100"}`}>
                  <BookCover book={book} isDark={isDark} />
                </div>

                <div className="mt-4 space-y-3">
                  <div className="w-full overflow-visible">
                    <h3 className={`w-full font-serif text-sm font-medium leading-snug break-words overflow-wrap-anywhere ${isDark ? "text-[#E0E0E0]" : "text-stone-950"}`}>{book.title}</h3>
                    {book.author ? <p className={`mt-1 text-sm text-center ${isDark ? "text-[#808080]" : "text-stone-500"}`}>{book.author}</p> : null}
                    {book.series_name ? (
                      <p className={`mt-1 text-xs font-medium uppercase tracking-wider text-center ${isDark ? "text-violet-400" : "text-violet-600"}`}>
                        {book.series_order ? `${seriesOrderLabel(book)}` : book.series_name}
                      </p>
                    ) : null}
                    <p className={`mt-1 text-xs uppercase tracking-wider text-center ${isDark ? "text-[#606060]" : "text-stone-400"}`}>{book.status}</p>
                    <ProcessingLine book={book} isDark={isDark} />
                  </div>

                  <div className={`pt-3 ${isDark ? "border-t border-white/8" : "border-t border-stone-200"}`}>
                    <div className={`flex items-center justify-between text-xs ${isDark ? "text-[#707070]" : "text-stone-500"}`}>
                      <span>{Math.round(book.progress_pct ?? 0)}% complete</span>
                      <span>{book.total_chapters ? `${book.total_chapters} ${storyUnitLabel(book.work_type, true)}` : "Syncing"}</span>
                    </div>

                    <div className="mt-2">
                      <div className={`h-1 overflow-hidden rounded-full ${isDark ? "bg-white/8" : "bg-stone-200"}`}>
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-violet-500 to-indigo-500"
                          style={{ width: `${Math.max(0, Math.min(book.progress_pct ?? 0, 100))}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 pt-2">
                    <button
                      onClick={(event) => {
                        event.stopPropagation()
                        if (book.mode === "author") {
                          window.location.href = `/${book.id}/manuscript`
                        } else {
                          onOpenBook(book.id)
                        }
                      }}
                      className={`min-w-0 flex-1 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                        isDark
                          ? "bg-white text-black hover:bg-white/90"
                          : "bg-stone-900 text-white hover:bg-stone-800"
                      }`}
                    >
                      {book.mode === "author" ? `Manage ${storyUnitLabel(book.work_type, true)}` : "Continue Reading"}
                    </button>

                    {book.mode === "author" ? (
                      <button
                        onClick={(event) => {
                          event.stopPropagation()
                          onAddChapter(book.id)
                        }}
                        className={`rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                          isDark
                            ? "border border-white/12 bg-white/5 text-[#E0E0E0] hover:bg-white/10"
                            : "border border-stone-200 bg-stone-50 text-stone-800 hover:bg-stone-100"
                        }`}
                      >
                        Add Scene
                      </button>
                    ) : null}

                    <div className="relative">
                      <button
                        onClick={(event) => {
                          event.stopPropagation()
                          setMenuOpen(menuOpen === book.id ? null : book.id)
                        }}
                        className={`rounded-lg p-2.5 transition ${isDark ? "hover:bg-white/10 text-[#A0A0A0]" : "hover:bg-stone-100 text-stone-500"}`}
                      >
                        <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
                        </svg>
                      </button>

                      {menuOpen === book.id && (
                        <div className={`absolute right-0 bottom-full mb-2 sm:bottom-auto sm:top-full sm:mt-2 sm:mb-0 z-50 w-44 overflow-hidden rounded-xl border py-1 shadow-2xl ${
                          isDark
                            ? "border-white/12 bg-[#0D0D0D]"
                            : "border-stone-200 bg-white"
                        }`}>
                          {book.mode === "author" && (
                            <button
                              onClick={(event) => {
                                event.stopPropagation()
                                onAddChapter(book.id)
                                setMenuOpen(null)
                              }}
                              className={`block w-full px-4 py-2 text-left text-sm transition ${isDark ? "text-[#E0E0E0] hover:bg-white/10" : "text-stone-700 hover:bg-stone-50"}`}
                            >
                              Add Scene
                            </button>
                          )}
                          {book.mode === "author" && (
                            <Link
                              href="/notes"
                              onClick={(event) => {
                                event.stopPropagation()
                                setMenuOpen(null)
                              }}
                              className={`block px-4 py-2 text-sm transition ${isDark ? "text-[#E0E0E0] hover:bg-white/10" : "text-stone-700 hover:bg-stone-50"}`}
                            >
                              Notes
                            </Link>
                          )}
                          {archived ? (
                            <button
                              onClick={(event) => {
                                event.stopPropagation()
                                onRestore(book.id)
                                setMenuOpen(null)
                              }}
                              disabled={busyBookId === book.id}
                              className={`w-full px-4 py-2 text-left text-sm transition disabled:opacity-60 ${isDark ? "text-[#E0E0E0] hover:bg-white/10" : "text-stone-700 hover:bg-stone-50"}`}
                            >
                              Restore
                            </button>
                          ) : (
                            <button
                              onClick={(event) => {
                                event.stopPropagation()
                                onArchive(book.id)
                                setMenuOpen(null)
                              }}
                              disabled={busyBookId === book.id}
                              className={`w-full px-4 py-2 text-left text-sm transition disabled:opacity-60 ${isDark ? "text-[#E0E0E0] hover:bg-white/10" : "text-stone-700 hover:bg-stone-50"}`}
                            >
                              Archive
                            </button>
                          )}
                          <button
                            onClick={(event) => {
                              event.stopPropagation()
                              onRemove(book.id)
                              setMenuOpen(null)
                            }}
                            disabled={busyBookId === book.id}
                            className={`w-full px-4 py-2 text-left text-sm transition disabled:opacity-60 ${
                              isDark ? "text-rose-300 hover:bg-rose-500/10" : "text-rose-600 hover:bg-rose-50"
                            }`}
                          >
                            Remove
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
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
      <img
        src={src}
        alt={`${book.title} cover`}
        className={`h-full w-full ${book.format === "pdf" ? "object-contain p-2" : "object-cover object-top"}`}
        onError={() => setFailed(true)}
      />
    )
  }

  return (
    <div className={`flex h-full w-full flex-col justify-between p-5 ${isDark ? "bg-[#0D0D0D] text-[#E0E0E0]" : "bg-[linear-gradient(150deg,#f4ecda,#ffffff_60%,#ecebff)] text-stone-900"}`}>
      <span className={`text-[0.65rem] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-[#808080]" : "text-violet-600"}`}>LoreVia</span>
      <div>
        <p className="text-3xl font-semibold leading-none">{titleInitials(book.title)}</p>
        <p className={`mt-3 line-clamp-3 text-sm leading-6 ${isDark ? "text-[#A0A0A0]" : "text-stone-600"}`}>{book.title}</p>
      </div>
    </div>
  )
}

function MetaCell({ label, value, align = "left", isDark }: { label: string; value: string; align?: "left" | "right"; isDark: boolean }) {
  return (
    <div className={align === "right" ? "text-right" : ""}>
      <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-[#808080]" : "text-stone-400"}`}>{label}</p>
      <p className={`mt-1 text-base font-medium ${isDark ? "text-[#E0E0E0]" : "text-stone-900"}`}>{value}</p>
    </div>
  )
}

function capitalize(value: string) {
  return value.replace(/(^|\s)\S/g, (char) => char.toUpperCase())
}


