"use client"

import type { ReactNode } from "react"
import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import type { Route } from "next"
import { useRouter } from "next/navigation"

import { UpcomingBetaReadsCard } from "@/components/library/UpcomingBetaReadsCard"
import { UploadModal } from "@/components/modals/UploadModal"
import { booksApi } from "@/lib/api/books"
import { asQueryKey, booksListCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { getBookHref } from "@/lib/utils/bookRoutes"
import type { Book, BookStatus } from "@/types/book"

type SortOption = "recent" | "title" | "progress"
type ViewMode = "grid" | "list"
type ModeFilter = "all" | "author" | "reader"
type StatusFilter = "all" | BookStatus
type GlyphName = "moon" | "spark" | "leaf" | "crown" | "wave" | "diamond" | "orbit" | "star"

const PINNED_STORAGE_KEY = "library-pinned-projects:v1"
const NUMBER_FORMAT = new Intl.NumberFormat("en-US")
const GLYPHS: GlyphName[] = ["moon", "spark", "leaf", "crown", "wave", "diamond", "orbit", "star"]
const ACCENT_CLASSES = [
  "text-violet-300 border-violet-400/18 bg-violet-500/[0.06]",
  "text-blue-300 border-blue-400/18 bg-blue-500/[0.06]",
  "text-cyan-300 border-cyan-400/18 bg-cyan-500/[0.06]",
  "text-amber-200 border-amber-300/18 bg-amber-400/[0.06]",
  "text-emerald-300 border-emerald-400/18 bg-emerald-500/[0.06]",
]
const DOT_CLASSES: Record<BookStatus, string> = {
  pending: "bg-slate-500",
  processing: "bg-amber-400",
  ready: "bg-blue-400",
  failed: "bg-rose-400",
}

function storyUnitLabel(workType?: Book["work_type"], plural = false) {
  if (workType === "screenplay") return plural ? "scenes" : "scene"
  return plural ? "chapters" : "chapter"
}

function storyUnitPrefix(workType?: Book["work_type"]) {
  return workType === "screenplay" ? "Scene" : "Chapter"
}

function clampProgress(value?: number | null) {
  return Math.max(0, Math.min(100, Math.round(value ?? 0)))
}

function hashString(value: string) {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) | 0
  }
  return Math.abs(hash)
}

function getProjectGlyph(book: Book) {
  return GLYPHS[hashString(book.id + book.title) % GLYPHS.length]
}

function getAccentClass(book: Book) {
  return ACCENT_CLASSES[hashString(book.title + book.id) % ACCENT_CLASSES.length]
}

function getBookUpdatedAt(book: Book) {
  return book.processing?.updated_at ?? book.created_at
}

function formatRelativeTime(dateString?: string | null) {
  if (!dateString) return "Updated recently"

  const date = new Date(dateString)
  if (Number.isNaN(date.getTime())) return "Updated recently"

  const minutes = Math.max(1, Math.round((Date.now() - date.getTime()) / 60000))
  if (minutes < 60) return `Updated ${minutes}m ago`

  const hours = Math.round(minutes / 60)
  if (hours < 24) return `Updated ${hours}h ago`

  const days = Math.round(hours / 24)
  if (days < 7) return `Updated ${days}d ago`

  const weeks = Math.round(days / 7)
  if (weeks < 5) return `Updated ${weeks}w ago`

  const months = Math.round(days / 30)
  return `Updated ${months}mo ago`
}

function estimateWordCount(book: Book) {
  if (typeof book.total_tokens === "number" && book.total_tokens > 0) {
    return Math.round(book.total_tokens * 0.75)
  }

  const unitCount = Math.max(book.total_chapters ?? 0, book.chapters_read_count ?? 0, 1)
  return unitCount * (book.work_type === "screenplay" ? 900 : 3200)
}

function estimateTargetWordCount(book: Book, currentWords: number) {
  if (book.work_type === "screenplay") {
    return Math.max(18000, Math.ceil(currentWords / 3000) * 3000)
  }

  return Math.max(100000, Math.ceil(currentWords / 10000) * 10000)
}

function getActiveUnit(book: Book) {
  if (book.processing?.last_chapter_number) return book.processing.last_chapter_number

  const totalUnits = Math.max(book.total_chapters ?? 0, 1)
  if (!book.progress_pct) return 1
  return Math.min(totalUnits, Math.max(1, Math.round((book.progress_pct / 100) * totalUnits)))
}

function getProgressLine(book: Book) {
  const prefix = storyUnitPrefix(book.work_type)
  const unit = getActiveUnit(book)
  const title = book.processing?.last_chapter_title?.trim()

  if (title) return `${prefix} ${unit} - ${title}`

  if (book.status === "processing") return `${prefix} ${unit} - Processing`
  if (book.mode === "author") return `${prefix} ${unit} - Draft in motion`
  if (book.progress_pct && book.progress_pct > 0) return `${prefix} ${unit} - Continue reading`
  return `${prefix} 1 - Starting point`
}

function getGenreLabel(book: Book) {
  if (book.genre?.trim()) return book.genre
  if (book.work_type === "screenplay") return "Screenplay"
  if (book.mode === "author") return "Writing Project"
  return "Manuscript"
}

function matchesSearch(book: Book, search: string) {
  if (!search) return true

  const haystack = [
    book.title,
    book.author,
    book.genre,
    book.series_name,
    book.status,
    book.mode,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase()

  return haystack.includes(search)
}

function compareBooks(left: Book, right: Book, sortBy: SortOption) {
  if (sortBy === "title") return left.title.localeCompare(right.title)
  if (sortBy === "progress") return clampProgress(right.progress_pct) - clampProgress(left.progress_pct)

  return new Date(getBookUpdatedAt(right)).getTime() - new Date(getBookUpdatedAt(left)).getTime()
}

function countWarnings(book: Book) {
  let warnings = 0
  if (book.status === "failed") warnings += 1
  if (book.copyright_warning) warnings += 1
  return warnings
}

function getPublicSampleStatus(book: Book) {
  if (book.public_status === "published" && book.is_public) return "Public book live"
  if (book.public_status === "hidden") return "Public book hidden"
  if (book.public_status === "removed") return "Public book removed"
  if (book.public_status === "pending_review") return "Public review pending"
  return null
}

function formatNumber(value: number) {
  return NUMBER_FORMAT.format(value)
}

export default function LibraryPage() {
  const router = useRouter()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  const [showUpload, setShowUpload] = useState(false)
  const [publishBook, setPublishBook] = useState<Book | null>(null)
  const [publishSlug, setPublishSlug] = useState("")
  const [publishDescription, setPublishDescription] = useState("")
  const [publishConfirmed, setPublishConfirmed] = useState(false)
  const [uploadPreset, setUploadPreset] = useState<{ mode?: "reader" | "author"; existingBookId?: string }>({})
  const [busyBookId, setBusyBookId] = useState<string | null>(null)
  const [search, setSearch] = useState("")
  const [sortBy, setSortBy] = useState<SortOption>("recent")
  const [viewMode, setViewMode] = useState<ViewMode>("grid")
  const [modeFilter, setModeFilter] = useState<ModeFilter>("all")
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all")
  const [showArchived, setShowArchived] = useState(false)
  const [filterOpen, setFilterOpen] = useState(false)
  const [menuBookId, setMenuBookId] = useState<string | null>(null)
  const [pinnedIds, setPinnedIds] = useState<Record<string, boolean>>({})
  const [pinsReady, setPinsReady] = useState(false)

  const {
    data: books = [],
    isLoading: loading,
    refetch,
  } = useQuery<Book[]>({
    queryKey: asQueryKey(booksListCacheKey(true)),
    queryFn: () => booksApi.list(true),
    staleTime: 20_000,
    refetchInterval: (query) => {
      const items = (query.state.data as Book[] | undefined) ?? []
      const hasProcessingBook = items.some((book) => book.status === "processing" || (!book.cover_url && book.format === "pdf"))
      return hasProcessingBook ? 5_000 : false
    },
  })

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(PINNED_STORAGE_KEY)
      if (raw) {
        const parsed = JSON.parse(raw) as Record<string, boolean>
        setPinnedIds(parsed)
      }
    } catch {
      // ignore malformed local storage
    } finally {
      setPinsReady(true)
    }
  }, [])

  useEffect(() => {
    if (!pinsReady) return
    window.localStorage.setItem(PINNED_STORAGE_KEY, JSON.stringify(pinnedIds))
  }, [pinnedIds, pinsReady])

  const normalizedSearch = search.trim().toLowerCase()
  const visibleBooks = books.filter((book) => !book.hidden_at)
  const filteredBooks = visibleBooks
    .filter((book) => (showArchived ? true : !book.archived_at))
    .filter((book) => (modeFilter === "all" ? true : book.mode === modeFilter))
    .filter((book) => (statusFilter === "all" ? true : book.status === statusFilter))
    .filter((book) => matchesSearch(book, normalizedSearch))
    .sort((left, right) => compareBooks(left, right, sortBy))

  const explicitPinned = filteredBooks.filter((book) => pinnedIds[book.id] && !book.archived_at)
  const fallbackPinned = [...filteredBooks]
    .filter((book) => !book.archived_at)
    .sort((left, right) => {
      const leftScore = (left.mode === "author" ? 3 : 0) + (left.status === "ready" ? 2 : left.status === "processing" ? 1 : 0) + clampProgress(left.progress_pct)
      const rightScore = (right.mode === "author" ? 3 : 0) + (right.status === "ready" ? 2 : right.status === "processing" ? 1 : 0) + clampProgress(right.progress_pct)
      return rightScore - leftScore
    })
  const pinnedBooks = explicitPinned.length > 0 ? explicitPinned.slice(0, 3) : fallbackPinned.slice(0, 3)
  const pinnedBookIds = new Set(pinnedBooks.map((book) => book.id))
  const allProjectBooks = filteredBooks.filter((book) => !pinnedBookIds.has(book.id))
  const filterSummary =
    modeFilter === "all" && statusFilter === "all" && !showArchived ? "Filter" : "Filtered"

  async function handleArchive(bookId: string, archived: boolean) {
    setBusyBookId(bookId)
    try {
      await booksApi.archive(bookId, archived)
      await refetch()
      setMenuBookId(null)
    } finally {
      setBusyBookId(null)
    }
  }

  async function handleRemove(bookId: string) {
    const confirmed = window.confirm("Remove this project from your library view? It will stay counted for usage.")
    if (!confirmed) return

    setBusyBookId(bookId)
    try {
      await booksApi.hide(bookId, true)
      await refetch()
      setMenuBookId(null)
    } finally {
      setBusyBookId(null)
    }
  }

  function handleAddChapter(bookId?: string) {
    const href = bookId ? (`/library/add-chapter?book=${bookId}` as Route) : ("/library/add-chapter" as Route)
    router.push(href)
  }

  function openBook(book: Book) {
    router.push(getBookHref(book) as Route)
  }

  function togglePinned(bookId: string) {
    setPinnedIds((current) => ({ ...current, [bookId]: !current[bookId] }))
    setMenuBookId(null)
  }

  async function handlePublish(book: Book) {
    if (!publishConfirmed || !publishSlug.trim()) return
    setBusyBookId(book.id)
    try {
      await booksApi.publishPublicly(book.id, {
        publicSlug: publishSlug.trim(),
        rightsConfirmation: true,
        description: publishDescription.trim() || null,
      })
      setPublishBook(null)
      setPublishConfirmed(false)
      setPublishSlug("")
      setPublishDescription("")
      await refetch()
    } finally {
      setBusyBookId(null)
    }
  }

  async function handleUnpublish(bookId: string) {
    setBusyBookId(bookId)
    try {
      await booksApi.unpublishPublicly(bookId)
      await refetch()
      setMenuBookId(null)
    } finally {
      setBusyBookId(null)
    }
  }

  const pageBackground = isDark
    ? "bg-[radial-gradient(circle_at_top,rgba(122,92,255,0.1),transparent_24%),linear-gradient(180deg,#09090e_0%,#0c0c12_55%,#0a0a10_100%)] text-[#f4f1ea]"
    : "bg-[radial-gradient(circle_at_top,rgba(236,228,255,0.38),transparent_24%),linear-gradient(180deg,#faf7f1_0%,#f5f1ea_100%)] text-stone-950"
  const surfaceClass = isDark
    ? "border-white/[0.08] bg-[#111119]"
    : "border-stone-200/80 bg-white/80"
  const mutedText = isDark ? "text-[#9f9ca8]" : "text-stone-500"
  const headingText = isDark ? "text-[#f7f3ed]" : "text-stone-950"
  const controlClass = isDark
    ? "border-white/[0.08] bg-[#111118] text-[#ebe7df] shadow-[0_18px_40px_-34px_rgba(0,0,0,0.92)]"
    : "border-stone-200 bg-white text-stone-800"

  return (
    <div className={`relative left-1/2 min-h-screen w-screen -translate-x-1/2 transition-colors duration-300 ${pageBackground}`}>
      <div className="mx-auto w-full max-w-[1520px] px-4 pb-20 pt-8 sm:px-8 lg:px-16">
        <section className="space-y-10">
          <div className="flex flex-col gap-8 xl:flex-row xl:items-end xl:justify-between">
            <div className="space-y-3 pt-1">
              <h1 className={`font-serif text-[3.25rem] leading-[0.94] tracking-[-0.04em] sm:text-[3.5rem] ${headingText}`}>Library</h1>
              <p className={`max-w-xl text-lg leading-8 ${mutedText}`}>Understand, revise, and maintain continuity across every manuscript.</p>
            </div>

            <div className="flex w-full flex-col gap-3 xl:w-auto xl:flex-row xl:items-center xl:justify-end">
              <label className={`flex min-h-[3.35rem] flex-1 items-center gap-3 rounded-xl border px-4 xl:min-w-[18.5rem] ${controlClass}`}>
                <SearchIcon className={isDark ? "text-[#7c7a87]" : "text-stone-400"} />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search projects..."
                  className={`w-full bg-transparent text-[0.95rem] outline-none ${isDark ? "placeholder:text-[#66636f]" : "placeholder:text-stone-400"}`}
                />
              </label>

              <div className="relative">
                <button
                  type="button"
                  onClick={() => setFilterOpen((current) => !current)}
                  className={`inline-flex min-h-[3.35rem] items-center gap-3 rounded-xl border px-5 text-sm font-medium ${controlClass}`}
                >
                  <FilterIcon className={isDark ? "text-[#c8c4bd]" : "text-stone-600"} />
                  {filterSummary}
                </button>

                {filterOpen ? (
                  <div className={`absolute right-0 z-30 mt-3 w-[18rem] rounded-2xl border p-4 shadow-[0_24px_80px_-40px_rgba(0,0,0,0.75)] ${surfaceClass}`}>
                    <div className="space-y-4">
                      <div>
                        <p className={`text-[0.68rem] font-semibold uppercase tracking-[0.28em] ${mutedText}`}>Project mode</p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {[
                            ["all", "All"],
                            ["author", "Author Workspace"],
                            ["reader", "Collaborator Preview"],
                          ].map(([value, label]) => (
                            <button
                              key={value}
                              type="button"
                              onClick={() => setModeFilter(value as ModeFilter)}
                              className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                                modeFilter === value
                                  ? "border-violet-400/50 bg-violet-500/15 text-violet-200"
                                  : isDark
                                    ? "border-white/[0.08] bg-white/[0.03] text-[#b1afba]"
                                    : "border-stone-200 bg-stone-50 text-stone-600"
                              }`}
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div>
                        <p className={`text-[0.68rem] font-semibold uppercase tracking-[0.28em] ${mutedText}`}>Status</p>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {[
                            ["all", "Any"],
                            ["ready", "Ready"],
                            ["processing", "Processing"],
                            ["pending", "Queued"],
                            ["failed", "Needs review"],
                          ].map(([value, label]) => (
                            <button
                              key={value}
                              type="button"
                              onClick={() => setStatusFilter(value as StatusFilter)}
                              className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                                statusFilter === value
                                  ? "border-violet-400/50 bg-violet-500/15 text-violet-200"
                                  : isDark
                                    ? "border-white/[0.08] bg-white/[0.03] text-[#b1afba]"
                                    : "border-stone-200 bg-stone-50 text-stone-600"
                              }`}
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                      </div>

                      <label className="flex items-center justify-between gap-3">
                        <span className={`text-sm ${headingText}`}>Show archived projects</span>
                        <button
                          type="button"
                          onClick={() => setShowArchived((current) => !current)}
                          className={`relative h-7 w-12 rounded-full transition ${showArchived ? "bg-violet-500" : isDark ? "bg-white/[0.1]" : "bg-stone-200"}`}
                        >
                          <span className={`absolute top-1 h-5 w-5 rounded-full bg-white transition ${showArchived ? "left-6" : "left-1"}`} />
                        </button>
                      </label>
                    </div>
                  </div>
                ) : null}
              </div>

              <div className={`flex min-h-[3.35rem] items-center rounded-xl border px-4 ${controlClass}`}>
                <select
                  value={sortBy}
                  onChange={(event) => setSortBy(event.target.value as SortOption)}
                  className="min-w-[10.8rem] bg-transparent pr-6 text-sm outline-none [color-scheme:dark] cursor-pointer"
                >
                  <option value="recent" className="bg-[#121212] text-white">Recently Updated</option>
                  <option value="progress" className="bg-[#121212] text-white">Most Progress</option>
                  <option value="title" className="bg-[#121212] text-white">Title A-Z</option>
                </select>
              </div>

              <div className={`inline-flex min-h-[3.35rem] items-center overflow-hidden rounded-xl border ${controlClass}`}>
                <button
                  type="button"
                  onClick={() => setViewMode("grid")}
                  className={`inline-flex h-full items-center justify-center px-4 transition ${viewMode === "grid" ? "bg-violet-500/16 text-violet-200" : mutedText}`}
                  aria-label="Grid view"
                >
                  <GridIcon />
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode("list")}
                  className={`inline-flex h-full items-center justify-center px-4 transition ${viewMode === "list" ? "bg-violet-500/16 text-violet-200" : mutedText}`}
                  aria-label="List view"
                >
                  <ListIcon />
                </button>
              </div>

              <button
                type="button"
                onClick={() => router.push("/public/forum" as Route)}
                className={`inline-flex min-h-[3.35rem] items-center justify-center gap-3 rounded-xl border px-5 text-sm font-medium transition ${controlClass}`}
              >
                <ForumIcon className={isDark ? "text-[#c8c4bd]" : "text-stone-600"} />
                Beta Forum
              </button>

              <button
                type="button"
                onClick={() => {
                  setUploadPreset({})
                  setShowUpload(true)
                }}
                className="inline-flex min-h-[3.35rem] items-center justify-center gap-3 rounded-xl bg-[#33206f] px-6 text-sm font-semibold text-white shadow-[0_22px_44px_-28px_rgba(109,40,217,0.78)] transition hover:translate-y-[-1px] hover:bg-[#3d2782]"
              >
                <PlusIcon />
                New Project
              </button>
            </div>
          </div>

          <UpcomingBetaReadsCard isDark={isDark} />

          <section className="space-y-5">
            <SectionHeading
              icon={<PinIcon className={isDark ? "text-violet-300" : "text-violet-600"} />}
              title="Pinned Projects"
              actionLabel={pinnedBooks.length > 0 ? "View All" : undefined}
              actionHandler={() => setShowArchived(false)}
              isDark={isDark}
            />

            {loading ? (
              <LoadingPanel isDark={isDark} label="Loading your pinned projects..." />
            ) : pinnedBooks.length === 0 ? (
              <EmptyPanel
                isDark={isDark}
                title="Nothing pinned yet"
                body="Use the project menu to pin the stories you want on top."
              />
            ) : viewMode === "grid" ? (
              <div className="grid gap-4 xl:grid-cols-3">
                {pinnedBooks.map((book) => (
                  <ProjectCard
                    key={book.id}
                    book={book}
                    isDark={isDark}
                    busy={busyBookId === book.id}
                    isPinned={!!pinnedIds[book.id]}
                    menuOpen={menuBookId === book.id}
                    onMenuToggle={() => setMenuBookId((current) => (current === book.id ? null : book.id))}
                    onOpen={() => openBook(book)}
                    onTogglePinned={() => togglePinned(book.id)}
                    onArchive={() => handleArchive(book.id, true)}
                    onRestore={() => handleArchive(book.id, false)}
                    onRemove={() => handleRemove(book.id)}
                    onAddChapter={() => handleAddChapter(book.id)}
                    onPublish={() => {
                      setPublishBook(book)
                      setPublishSlug(book.public_slug ?? book.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""))
                      setPublishDescription(book.public_description ?? "")
                      setPublishConfirmed(false)
                    }}
                    onUnpublish={() => void handleUnpublish(book.id)}
                  />
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {pinnedBooks.map((book) => (
                  <ProjectRow
                    key={book.id}
                    book={book}
                    isDark={isDark}
                    busy={busyBookId === book.id}
                    isPinned={!!pinnedIds[book.id]}
                    menuOpen={menuBookId === book.id}
                    onMenuToggle={() => setMenuBookId((current) => (current === book.id ? null : book.id))}
                    onOpen={() => openBook(book)}
                    onTogglePinned={() => togglePinned(book.id)}
                    onArchive={() => handleArchive(book.id, true)}
                    onRestore={() => handleArchive(book.id, false)}
                    onRemove={() => handleRemove(book.id)}
                    onAddChapter={() => handleAddChapter(book.id)}
                    onPublish={() => {
                      setPublishBook(book)
                      setPublishSlug(book.public_slug ?? book.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""))
                      setPublishDescription(book.public_description ?? "")
                      setPublishConfirmed(false)
                    }}
                    onUnpublish={() => void handleUnpublish(book.id)}
                  />
                ))}
              </div>
            )}
          </section>

          <section className="space-y-5">
            <SectionHeading
              icon={<PinIcon className={isDark ? "text-violet-300" : "text-violet-600"} />}
              title="All Projects"
              actionLabel={filteredBooks.length > 0 ? "View All" : undefined}
              actionHandler={() => {
                setSearch("")
                setModeFilter("all")
                setStatusFilter("all")
                setShowArchived(false)
              }}
              isDark={isDark}
            />

            {loading ? (
              <LoadingPanel isDark={isDark} label="Loading your library..." />
            ) : allProjectBooks.length === 0 && filteredBooks.length === 0 ? (
              <EmptyPanel
                isDark={isDark}
                title="No projects match this view"
                body="Try a different filter, or start a new project from the button above."
              />
            ) : viewMode === "grid" ? (
              <div className="grid gap-4 xl:grid-cols-3">
                {allProjectBooks.map((book) => (
                  <ProjectCard
                    key={book.id}
                    book={book}
                    isDark={isDark}
                    busy={busyBookId === book.id}
                    isPinned={!!pinnedIds[book.id]}
                    menuOpen={menuBookId === book.id}
                    onMenuToggle={() => setMenuBookId((current) => (current === book.id ? null : book.id))}
                    onOpen={() => openBook(book)}
                    onTogglePinned={() => togglePinned(book.id)}
                    onArchive={() => handleArchive(book.id, true)}
                    onRestore={() => handleArchive(book.id, false)}
                    onRemove={() => handleRemove(book.id)}
                    onAddChapter={() => handleAddChapter(book.id)}
                    onPublish={() => {
                      setPublishBook(book)
                      setPublishSlug(book.public_slug ?? book.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""))
                      setPublishDescription(book.public_description ?? "")
                      setPublishConfirmed(false)
                    }}
                    onUnpublish={() => void handleUnpublish(book.id)}
                  />
                ))}

                <CreateProjectCard
                  isDark={isDark}
                  onCreate={() => {
                    setUploadPreset({})
                    setShowUpload(true)
                  }}
                />
              </div>
            ) : (
              <div className="space-y-3">
                {allProjectBooks.map((book) => (
                  <ProjectRow
                    key={book.id}
                    book={book}
                    isDark={isDark}
                    busy={busyBookId === book.id}
                    isPinned={!!pinnedIds[book.id]}
                    menuOpen={menuBookId === book.id}
                    onMenuToggle={() => setMenuBookId((current) => (current === book.id ? null : book.id))}
                    onOpen={() => openBook(book)}
                    onTogglePinned={() => togglePinned(book.id)}
                    onArchive={() => handleArchive(book.id, true)}
                    onRestore={() => handleArchive(book.id, false)}
                    onRemove={() => handleRemove(book.id)}
                    onAddChapter={() => handleAddChapter(book.id)}
                    onPublish={() => {
                      setPublishBook(book)
                      setPublishSlug(book.public_slug ?? book.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""))
                      setPublishDescription(book.public_description ?? "")
                      setPublishConfirmed(false)
                    }}
                    onUnpublish={() => void handleUnpublish(book.id)}
                  />
                ))}

                <CreateProjectRow
                  isDark={isDark}
                  onCreate={() => {
                    setUploadPreset({})
                    setShowUpload(true)
                  }}
                />
              </div>
            )}
          </section>
        </section>
      </div>

      {showUpload ? (
        <UploadModal
          initialMode={uploadPreset.mode}
          initialExistingBookId={uploadPreset.existingBookId}
          onClose={() => {
            setShowUpload(false)
            setUploadPreset({})
            void refetch()
          }}
        />
      ) : null}

      {publishBook ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 py-8">
          <div className={`w-full max-w-2xl rounded-[1.5rem] border p-6 ${surfaceClass}`}>
            <p className={`text-[0.68rem] font-semibold uppercase tracking-[0.28em] ${mutedText}`}>Public book</p>
            <h2 className={`mt-3 font-serif text-[2rem] tracking-[-0.03em] ${headingText}`}>Publish your own original work</h2>
            <p className={`mt-3 text-sm leading-7 ${mutedText}`}>
              Private Workspace and Public Book are different states. Do not publish books, chapters, EPUBs, web novels, paid content, or third-party works unless you own the rights or have explicit permission.
            </p>
            <div className="mt-6 grid gap-4">
              <label className="grid gap-2 text-sm">
                <span className={headingText}>Public URL slug</span>
                <input value={publishSlug} onChange={(event) => setPublishSlug(event.target.value)} className={`rounded-xl border px-4 py-3 ${controlClass}`} />
              </label>
              <label className="grid gap-2 text-sm">
                <span className={headingText}>Public description</span>
                <textarea value={publishDescription} onChange={(event) => setPublishDescription(event.target.value)} rows={4} className={`rounded-xl border px-4 py-3 ${controlClass}`} />
              </label>
              <label className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-sm leading-7 ${controlClass}`}>
                <input type="checkbox" checked={publishConfirmed} onChange={(event) => setPublishConfirmed(event.target.checked)} className="mt-1" />
                <span>I confirm that I own the rights to this content or have permission to upload and publish it on LoreVia.</span>
              </label>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button type="button" onClick={() => setPublishBook(null)} className={`rounded-full px-4 py-2 text-sm ${controlClass}`}>Cancel</button>
              <button type="button" disabled={!publishConfirmed || !publishSlug.trim() || busyBookId === publishBook.id} onClick={() => void handlePublish(publishBook)} className="rounded-full bg-[#33206f] px-5 py-2 text-sm font-semibold text-white disabled:opacity-50">
                Publish publicly
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function SectionHeading({
  icon,
  title,
  actionLabel,
  actionHandler,
  isDark,
}: {
  icon: ReactNode
  title: string
  actionLabel?: string
  actionHandler?: () => void
  isDark: boolean
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="flex items-center gap-2.5">
        {icon}
        <h2 className={`text-[1.05rem] font-medium tracking-[-0.01em] ${isDark ? "text-[#f5f0e8]" : "text-stone-900"}`}>{title}</h2>
      </div>

      {actionLabel && actionHandler ? (
        <button
          type="button"
          onClick={actionHandler}
          className={`inline-flex items-center gap-2 text-sm transition ${isDark ? "text-violet-300 hover:text-violet-200" : "text-violet-600 hover:text-violet-700"}`}
        >
          {actionLabel}
          <ChevronRightIcon />
        </button>
      ) : null}
    </div>
  )
}

function LoadingPanel({ isDark, label }: { isDark: boolean; label: string }) {
  return (
    <div className={`rounded-[1.35rem] border border-dashed px-6 py-16 text-center ${isDark ? "border-white/[0.08] bg-[#0d0d14] text-[#9f9da7]" : "border-stone-300 bg-white/60 text-stone-500"}`}>
      {label}
    </div>
  )
}

function EmptyPanel({ isDark, title, body }: { isDark: boolean; title: string; body: string }) {
  return (
    <div className={`rounded-[1.35rem] border border-dashed px-6 py-16 text-center ${isDark ? "border-white/[0.08] bg-[#0d0d14]" : "border-stone-300 bg-white/60"}`}>
      <p className={`text-xl font-medium ${isDark ? "text-[#f5f0e8]" : "text-stone-900"}`}>{title}</p>
      <p className={`mx-auto mt-3 max-w-lg text-sm ${isDark ? "text-[#9f9da7]" : "text-stone-500"}`}>{body}</p>
    </div>
  )
}

function ProjectCard({
  book,
  isDark,
  busy,
  isPinned,
  menuOpen,
  onMenuToggle,
  onOpen,
  onTogglePinned,
  onArchive,
  onRestore,
  onRemove,
  onAddChapter,
  onPublish,
  onUnpublish,
}: {
  book: Book
  isDark: boolean
  busy: boolean
  isPinned: boolean
  menuOpen: boolean
  onMenuToggle: () => void
  onOpen: () => void
  onTogglePinned: () => void
  onArchive: () => void
  onRestore: () => void
  onRemove: () => void
  onAddChapter: () => void
  onPublish: () => void
  onUnpublish: () => void
}) {
  const accentClass = getAccentClass(book)
  const progress = clampProgress(book.progress_pct)
  const currentWords = estimateWordCount(book)
  const targetWords = estimateTargetWordCount(book, currentWords)
  const warningCount = countWarnings(book)
  const isArchived = !!book.archived_at
  const publicSampleStatus = getPublicSampleStatus(book)

  return (
    <article
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault()
          onOpen()
        }
      }}
      className={`group relative cursor-pointer rounded-[1.35rem] border p-6 transition duration-300 hover:-translate-y-0.5 hover:border-violet-400/20 hover:shadow-[0_24px_60px_-44px_rgba(109,40,217,0.72)] focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/45 ${
        isDark ? "border-white/[0.06] bg-[#101018]" : "border-stone-200/80 bg-white/82"
      }`}
    >
      <div className="flex h-full flex-col">
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-4">
            <div className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-full border shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] ${accentClass}`}>
              <ProjectGlyph glyph={getProjectGlyph(book)} />
            </div>

            <div className="min-w-0">
              <div className="flex items-center gap-3">
                <h3 className={`truncate font-serif text-[2rem] leading-tight tracking-[-0.03em] ${isDark ? "text-[#f7f3ed]" : "text-stone-950"}`}>
                  {book.title}
                </h3>
                <span className={`h-2.5 w-2.5 rounded-full ${DOT_CLASSES[book.status]}`} />
              </div>
              <p className={`truncate text-[0.95rem] ${isDark ? "text-[#b7b4bd]" : "text-stone-600"}`}>{getGenreLabel(book)}</p>
              {publicSampleStatus ? (
                <p className={`mt-2 inline-flex rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${isDark ? "bg-cyan-400/12 text-cyan-200" : "bg-cyan-100 text-cyan-800"}`}>
                  {publicSampleStatus}
                </p>
              ) : null}
            </div>
          </div>

          <div className="relative">
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation()
                onMenuToggle()
              }}
              className={`relative z-20 rounded-full p-2 transition ${isDark ? "text-[#8c8994] hover:bg-white/[0.06] hover:text-white" : "text-stone-500 hover:bg-stone-100 hover:text-stone-900"}`}
              aria-label={`Open actions for ${book.title}`}
            >
              <DotsIcon />
            </button>

            {menuOpen ? (
              <ProjectMenu
                isDark={isDark}
                busy={busy}
                isPinned={isPinned}
                isArchived={isArchived}
                isAuthor={book.mode === "author"}
                isPublic={Boolean(book.is_public && book.public_status === "published")}
                workType={book.work_type}
                onTogglePinned={onTogglePinned}
                onArchive={onArchive}
                onRestore={onRestore}
                onRemove={onRemove}
                onAddChapter={onAddChapter}
                onPublish={onPublish}
                onUnpublish={onUnpublish}
              />
            ) : null}
          </div>
        </div>

        <p className={`mt-7 text-[1.05rem] ${isDark ? "text-[#d8d3cb]" : "text-stone-700"}`}>{getProgressLine(book)}</p>

        <div className="mt-5">
          <div className={`h-1.5 overflow-hidden rounded-full ${isDark ? "bg-white/[0.08]" : "bg-stone-200"}`}>
            <div className="h-full rounded-full bg-[linear-gradient(90deg,#8b5cf6,#a78bfa)]" style={{ width: `${progress}%` }} />
          </div>

          <div className={`mt-4 flex items-center justify-between gap-4 text-[0.95rem] ${isDark ? "text-[#c8c4bd]" : "text-stone-700"}`}>
            <span>{formatNumber(currentWords)} / {formatNumber(targetWords)} words</span>
            <span>{progress}%</span>
          </div>

          <p className={`mt-1.5 text-[0.95rem] ${isDark ? "text-[#8c8994]" : "text-stone-500"}`}>{formatRelativeTime(getBookUpdatedAt(book))}</p>
        </div>

        <div className={`mt-auto flex items-center gap-10 pt-8 text-[0.95rem] ${isDark ? "text-[#b7b4bd]" : "text-stone-600"}`}>
          <MetaBadge icon={<GroupIcon />} value={String(book.total_chapters ?? 0)} />
          <MetaBadge icon={<PageIcon />} value={String(Math.max(1, Math.round(currentWords / 1000)))} />
          <MetaBadge icon={<AlertIcon />} value={String(warningCount)} />
        </div>
      </div>
    </article>
  )
}

function ProjectRow({
  book,
  isDark,
  busy,
  isPinned,
  menuOpen,
  onMenuToggle,
  onOpen,
  onTogglePinned,
  onArchive,
  onRestore,
  onRemove,
  onAddChapter,
  onPublish,
  onUnpublish,
}: {
  book: Book
  isDark: boolean
  busy: boolean
  isPinned: boolean
  menuOpen: boolean
  onMenuToggle: () => void
  onOpen: () => void
  onTogglePinned: () => void
  onArchive: () => void
  onRestore: () => void
  onRemove: () => void
  onAddChapter: () => void
  onPublish: () => void
  onUnpublish: () => void
}) {
  const accentClass = getAccentClass(book)
  const progress = clampProgress(book.progress_pct)
  const currentWords = estimateWordCount(book)
  const targetWords = estimateTargetWordCount(book, currentWords)
  const isArchived = !!book.archived_at
  const publicSampleStatus = getPublicSampleStatus(book)

  return (
    <article
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault()
          onOpen()
        }
      }}
      className={`relative cursor-pointer rounded-[1.35rem] border px-6 py-5 transition hover:border-violet-400/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/45 ${isDark ? "border-white/[0.06] bg-[#101018]" : "border-stone-200/80 bg-white/82"}`}
    >
      <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex min-w-0 items-center gap-4">
          <div className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-full border shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] ${accentClass}`}>
            <ProjectGlyph glyph={getProjectGlyph(book)} />
          </div>

          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <h3 className={`truncate font-serif text-[2rem] tracking-[-0.03em] ${isDark ? "text-[#f7f3ed]" : "text-stone-950"}`}>{book.title}</h3>
              <span className={`h-2.5 w-2.5 rounded-full ${DOT_CLASSES[book.status]}`} />
            </div>
            <p className={`mt-1 truncate text-[0.95rem] ${isDark ? "text-[#b7b4bd]" : "text-stone-600"}`}>{getGenreLabel(book)}</p>
            {publicSampleStatus ? (
              <p className={`mt-2 inline-flex rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${isDark ? "bg-cyan-400/12 text-cyan-200" : "bg-cyan-100 text-cyan-800"}`}>
                {publicSampleStatus}
              </p>
            ) : null}
            <p className={`mt-1.5 text-[0.95rem] ${isDark ? "text-[#8c8994]" : "text-stone-500"}`}>{getProgressLine(book)}</p>
          </div>
        </div>

        <div className="flex flex-1 flex-col gap-3 xl:max-w-[34rem]">
          <div className={`h-1.5 overflow-hidden rounded-full ${isDark ? "bg-white/[0.08]" : "bg-stone-200"}`}>
            <div className="h-full rounded-full bg-[linear-gradient(90deg,#8b5cf6,#a78bfa)]" style={{ width: `${progress}%` }} />
          </div>
          <div className={`flex flex-wrap items-center gap-x-5 gap-y-2 text-[0.95rem] ${isDark ? "text-[#b7b4bd]" : "text-stone-600"}`}>
            <span>{formatNumber(currentWords)} / {formatNumber(targetWords)} words</span>
            <span>{progress}% complete</span>
            <span>{formatRelativeTime(getBookUpdatedAt(book))}</span>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 xl:justify-end">
          {book.mode === "author" ? (
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation()
                onAddChapter()
              }}
              className={`relative z-10 rounded-full px-4 py-2 text-sm font-medium transition ${
                isDark ? "bg-white/[0.04] text-[#f1ece4] hover:bg-white/[0.08]" : "bg-stone-100 text-stone-800 hover:bg-stone-200"
              }`}
            >
              Add {storyUnitLabel(book.work_type)}
            </button>
          ) : null}

          <div className="relative">
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation()
                onMenuToggle()
              }}
              className={`relative z-20 rounded-full p-2 transition ${isDark ? "text-[#8c8994] hover:bg-white/[0.06] hover:text-white" : "text-stone-500 hover:bg-stone-100 hover:text-stone-900"}`}
              aria-label={`Open actions for ${book.title}`}
            >
              <DotsIcon />
            </button>

            {menuOpen ? (
              <ProjectMenu
                isDark={isDark}
                busy={busy}
                isPinned={isPinned}
                isArchived={isArchived}
                isAuthor={book.mode === "author"}
                isPublic={Boolean(book.is_public && book.public_status === "published")}
                workType={book.work_type}
                onTogglePinned={onTogglePinned}
                onArchive={onArchive}
                onRestore={onRestore}
                onRemove={onRemove}
                onAddChapter={onAddChapter}
                onPublish={onPublish}
                onUnpublish={onUnpublish}
              />
            ) : null}
          </div>
        </div>
      </div>
    </article>
  )
}

function ProjectMenu({
  isDark,
  busy,
  isPinned,
  isArchived,
  isAuthor,
  isPublic,
  workType,
  onTogglePinned,
  onArchive,
  onRestore,
  onRemove,
  onAddChapter,
  onPublish,
  onUnpublish,
}: {
  isDark: boolean
  busy: boolean
  isPinned: boolean
  isArchived: boolean
  isAuthor: boolean
  isPublic: boolean
  workType: Book["work_type"]
  onTogglePinned: () => void
  onArchive: () => void
  onRestore: () => void
  onRemove: () => void
  onAddChapter: () => void
  onPublish: () => void
  onUnpublish: () => void
}) {
  return (
    <div
      onClick={(event) => event.stopPropagation()}
      className={`absolute right-0 top-full z-30 mt-2 w-48 overflow-hidden rounded-[1.15rem] border py-2 shadow-[0_30px_90px_-40px_rgba(0,0,0,0.85)] ${isDark ? "border-white/[0.08] bg-[#12121a]" : "border-stone-200 bg-white"}`}
    >
      <MenuButton isDark={isDark} onClick={onTogglePinned} label={isPinned ? "Unpin project" : "Pin project"} />
      {isAuthor ? <MenuButton isDark={isDark} onClick={onAddChapter} label={`Add ${storyUnitLabel(workType)}`} /> : null}
      {isAuthor ? <MenuButton isDark={isDark} onClick={isPublic ? onUnpublish : onPublish} label={isPublic ? "Unpublish public book" : "Publish publicly"} disabled={busy} /> : null}
      {isArchived ? (
        <MenuButton isDark={isDark} onClick={onRestore} label="Restore" disabled={busy} />
      ) : (
        <MenuButton isDark={isDark} onClick={onArchive} label="Archive" disabled={busy} />
      )}
      <MenuButton isDark={isDark} onClick={onRemove} label="Remove" disabled={busy} danger />
    </div>
  )
}

function MenuButton({
  isDark,
  onClick,
  label,
  disabled = false,
  danger = false,
}: {
  isDark: boolean
  onClick: () => void
  label: string
  disabled?: boolean
  danger?: boolean
}) {
  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation()
        onClick()
      }}
      disabled={disabled}
      className={`block w-full px-4 py-2.5 text-left text-sm transition disabled:opacity-50 ${
        danger
          ? isDark
            ? "text-rose-300 hover:bg-rose-500/10"
            : "text-rose-600 hover:bg-rose-50"
          : isDark
            ? "text-[#efe9df] hover:bg-white/[0.06]"
            : "text-stone-700 hover:bg-stone-50"
      }`}
    >
      {label}
    </button>
  )
}

function MetaBadge({ icon, value }: { icon: ReactNode; value: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <span>{icon}</span>
      <span>{value}</span>
    </div>
  )
}

function CreateProjectCard({ isDark, onCreate }: { isDark: boolean; onCreate: () => void }) {
  return (
    <button
      type="button"
      onClick={onCreate}
      className={`flex min-h-[18.25rem] flex-col items-center justify-center rounded-[1.35rem] border border-dashed p-8 text-center transition hover:-translate-y-0.5 ${
        isDark
          ? "border-white/[0.08] bg-[#0d0d14] hover:border-violet-400/30 hover:bg-[#11111a]"
          : "border-stone-300 bg-white/65 hover:border-violet-300 hover:bg-white"
      }`}
    >
      <div className={`flex h-20 w-20 items-center justify-center rounded-full border ${isDark ? "border-white/[0.1] text-[#b7b4bd]" : "border-stone-300 text-stone-500"}`}>
        <PlusLargeIcon />
      </div>
      <h3 className={`mt-8 font-serif text-[2rem] tracking-[-0.03em] ${isDark ? "text-[#f7f3ed]" : "text-stone-900"}`}>Create New Project</h3>
      <p className={`mt-3 text-lg ${isDark ? "text-[#9f9da7]" : "text-stone-500"}`}>Start a new story</p>
    </button>
  )
}

function CreateProjectRow({ isDark, onCreate }: { isDark: boolean; onCreate: () => void }) {
  return (
    <button
      type="button"
      onClick={onCreate}
      className={`flex items-center justify-between rounded-[1.35rem] border border-dashed px-5 py-5 text-left transition ${
        isDark
          ? "border-white/[0.08] bg-[#0d0d14] hover:border-violet-400/30 hover:bg-[#11111a]"
          : "border-stone-300 bg-white/65 hover:border-violet-300 hover:bg-white"
      }`}
    >
      <div>
        <h3 className={`font-serif text-[2rem] tracking-[-0.03em] ${isDark ? "text-[#f7f3ed]" : "text-stone-900"}`}>Create New Project</h3>
        <p className={`mt-2 ${isDark ? "text-[#9f9da7]" : "text-stone-500"}`}>Start a new story</p>
      </div>
      <div className={`flex h-14 w-14 items-center justify-center rounded-full border ${isDark ? "border-white/[0.08] text-[#b7b4bd]" : "border-stone-300 text-stone-500"}`}>
        <PlusLargeIcon />
      </div>
    </button>
  )
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg className={`h-5 w-5 ${className ?? ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M11 18a7 7 0 100-14 7 7 0 000 14zM20 20l-4-4" />
    </svg>
  )
}

function FilterIcon({ className }: { className?: string }) {
  return (
    <svg className={`h-5 w-5 ${className ?? ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16l-6 7v5l-4 2v-7L4 6z" />
    </svg>
  )
}

function ForumIcon({ className }: { className?: string }) {
  return (
    <svg className={`h-5 w-5 ${className ?? ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 10h10M7 14h6" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 5h14a2 2 0 012 2v8a2 2 0 01-2 2H9l-4 3v-3H5a2 2 0 01-2-2V7a2 2 0 012-2z" />
    </svg>
  )
}

function GridIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <rect x="4" y="4" width="6" height="6" rx="1.4" />
      <rect x="14" y="4" width="6" height="6" rx="1.4" />
      <rect x="4" y="14" width="6" height="6" rx="1.4" />
      <rect x="14" y="14" width="6" height="6" rx="1.4" />
    </svg>
  )
}

function ListIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01" />
    </svg>
  )
}

function PinIcon({ className }: { className?: string }) {
  return (
    <svg className={`h-4 w-4 ${className ?? ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M14 4l6 6-3 1-4 7-2-2 7-4 1-3-6-6 1-1zM8 14l-4 6" />
    </svg>
  )
}

function PlusIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" />
    </svg>
  )
}

function PlusLargeIcon() {
  return (
    <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" />
    </svg>
  )
}

function DotsIcon() {
  return (
    <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
      <path d="M4 10a1.4 1.4 0 112.8 0A1.4 1.4 0 014 10zm4.6 0a1.4 1.4 0 112.8 0 1.4 1.4 0 01-2.8 0zm4.6 0a1.4 1.4 0 112.8 0 1.4 1.4 0 01-2.8 0z" />
    </svg>
  )
}

function GroupIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 11a3 3 0 100-6 3 3 0 000 6zM4 19a5 5 0 0110 0M17 11a2.5 2.5 0 100-5M15.5 15.5A4.5 4.5 0 0120 20" />
    </svg>
  )
}

function PageIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 4h8l3 3v13H7V4z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 4v4h4M9 12h6M9 16h4" />
    </svg>
  )
}

function AlertIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4l8 14H4l8-14z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4M12 17h.01" />
    </svg>
  )
}

function ChevronRightIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 6l6 6-6 6" />
    </svg>
  )
}

function ProjectGlyph({ glyph }: { glyph: GlyphName }) {
  const className = "h-7 w-7"

  switch (glyph) {
    case "moon":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.5 3.5a8.5 8.5 0 108 12.2A8 8 0 0115.5 3.5z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 7.5l.7 1.6 1.6.7-1.6.7-.7 1.6-.7-1.6-1.6-.7 1.6-.7.7-1.6z" />
        </svg>
      )
    case "spark":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v18M3 12h18M6.5 6.5l11 11M17.5 6.5l-11 11" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6l1.3 4.7L18 12l-4.7 1.3L12 18l-1.3-4.7L6 12l4.7-1.3L12 6z" />
        </svg>
      )
    case "leaf":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M18.5 5.5C11 5.5 6 10.2 6 16.4c0 1 .1 1.9.4 2.6 7.1-.4 12.1-5.1 12.1-11.4z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M7 17c2.8-2.5 5.7-4.6 9.5-6.2" />
        </svg>
      )
    case "crown":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 18l1.8-9 5.7 4.2L17.7 9l1.8 9H4.5z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 18V7m8 11V7" />
        </svg>
      )
    case "wave":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 8c2 0 2-1 4-1s2 1 4 1 2-1 4-1 2 1 4 1" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 13c2 0 2-1 4-1s2 1 4 1 2-1 4-1 2 1 4 1" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 18c2 0 2-1 4-1s2 1 4 1 2-1 4-1 2 1 4 1" />
        </svg>
      )
    case "diamond":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 4l8 8-8 8-8-8 8-8z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 8l4 4-4 4-4-4 4-4z" />
        </svg>
      )
    case "orbit":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <circle cx="12" cy="12" r="2.2" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12c2.4-4.7 12.6-4.7 15 0-2.4 4.7-12.6 4.7-15 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 4.8c4.8-1.6 10.4 6.7 8.1 11.5-4.8 1.6-10.4-6.7-8.1-11.5z" />
        </svg>
      )
    case "star":
    default:
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 4l1.8 5.7L20 12l-6.2 2.3L12 20l-1.8-5.7L4 12l6.2-2.3L12 4z" />
        </svg>
      )
  }
}
