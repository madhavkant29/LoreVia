import type { Route } from "next"

import { getBookHref } from "@/lib/utils/bookRoutes"
import type { Book, BookStatus } from "@/types/book"
import type { NextBestAction, RecentActivityItem } from "@/types/ux"
import { resolveNextBestActions, type NextBestActionCandidate } from "@/lib/workspace/nextBestActionResolver"

export type SortOption = "recent" | "title" | "progress"
export type ViewMode = "grid" | "list"
export type ModeFilter = "all" | "author" | "reader"
export type StatusFilter = "all" | BookStatus
export type GlyphName = "moon" | "spark" | "leaf" | "crown" | "wave" | "diamond" | "orbit" | "star"
export type MetricTone = "slate" | "teal" | "violet" | "amber"

export const PINNED_STORAGE_KEY = "library-pinned-projects:v1"
const NUMBER_FORMAT = new Intl.NumberFormat("en-US")
const GLYPHS: GlyphName[] = ["moon", "spark", "leaf", "crown", "wave", "diamond", "orbit", "star"]
const ACCENT_CLASSES = [
  "text-teal-700 border-teal-800/18 bg-teal-800/[0.06]",
  "text-blue-300 border-blue-400/18 bg-blue-500/[0.06]",
  "text-cyan-300 border-cyan-400/18 bg-cyan-500/[0.06]",
  "text-amber-200 border-amber-300/18 bg-amber-400/[0.06]",
  "text-emerald-300 border-emerald-400/18 bg-emerald-500/[0.06]",
]
export const DOT_CLASSES: Record<BookStatus, string> = {
  pending: "bg-slate-500",
  processing: "bg-amber-400",
  ready: "bg-blue-400",
  failed: "bg-rose-400",
}
export const EMPTY_BOOKS: Book[] = []
export const MODE_FILTER_OPTIONS: Array<{ value: ModeFilter; label: string; tooltip: string }> = [
  { value: "all", label: "All", tooltip: "Show all project modes" },
  { value: "author", label: "Author Workspace", tooltip: "Show writing projects only" },
  { value: "reader", label: "Collaborator Preview", tooltip: "Show reader preview projects only" },
]
export const STATUS_FILTER_OPTIONS: Array<{ value: StatusFilter; label: string; tooltip: string }> = [
  { value: "all", label: "Any", tooltip: "Show every project status" },
  { value: "ready", label: "Ready", tooltip: "Show projects ready to open" },
  { value: "processing", label: "Processing", tooltip: "Show projects still being analyzed" },
  { value: "pending", label: "Queued", tooltip: "Show projects waiting to process" },
  { value: "failed", label: "Needs review", tooltip: "Show projects that need attention" },
]
export const STATUS_LABELS: Record<BookStatus, string> = {
  pending: "Queued",
  processing: "Processing",
  ready: "Ready",
  failed: "Needs review",
}

export function storyUnitLabel(workType?: Book["work_type"], plural = false) {
  if (workType === "screenplay") return plural ? "scenes" : "scene"
  return plural ? "chapters" : "chapter"
}

export function storyUnitPrefix(workType?: Book["work_type"]) {
  return workType === "screenplay" ? "Scene" : "Chapter"
}

export function clampProgress(value?: number | null) {
  return Math.max(0, Math.min(100, Math.round(value ?? 0)))
}

function hashString(value: string) {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) | 0
  }
  return Math.abs(hash)
}

export function getProjectGlyph(book: Book) {
  return GLYPHS[hashString(book.id + book.title) % GLYPHS.length]
}

export function getAccentClass(book: Book) {
  return ACCENT_CLASSES[hashString(book.title + book.id) % ACCENT_CLASSES.length]
}

export function getBookUpdatedAt(book: Book) {
  return book.processing?.updated_at ?? book.created_at
}

export function formatRelativeTime(dateString?: string | null) {
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

export function estimateWordCount(book: Book) {
  if (typeof book.total_tokens === "number" && book.total_tokens > 0) {
    return Math.round(book.total_tokens * 0.75)
  }

  const unitCount = Math.max(book.total_chapters ?? 0, book.chapters_read_count ?? 0, 1)
  return unitCount * (book.work_type === "screenplay" ? 900 : 3200)
}

export function estimateTargetWordCount(book: Book, currentWords: number) {
  if (book.work_type === "screenplay") {
    return Math.max(18000, Math.ceil(currentWords / 3000) * 3000)
  }

  return Math.max(100000, Math.ceil(currentWords / 10000) * 10000)
}

export function getActiveUnit(book: Book) {
  if (book.processing?.last_chapter_number) return book.processing.last_chapter_number

  const totalUnits = Math.max(book.total_chapters ?? 0, 1)
  if (!book.progress_pct) return 1
  return Math.min(totalUnits, Math.max(1, Math.round((book.progress_pct / 100) * totalUnits)))
}

export function getProgressLine(book: Book) {
  const prefix = storyUnitPrefix(book.work_type)
  const unit = getActiveUnit(book)
  const title = book.processing?.last_chapter_title?.trim()

  if (title) return `${prefix} ${unit} - ${title}`

  if (book.status === "processing") return `${prefix} ${unit} - Processing`
  if (book.mode === "author") return `${prefix} ${unit} - Draft in motion`
  if (book.progress_pct && book.progress_pct > 0) return `${prefix} ${unit} - Continue reading`
  return `${prefix} 1 - Starting point`
}

export function getGenreLabel(book: Book) {
  if (book.genre?.trim()) return book.genre
  if (book.work_type === "screenplay") return "Screenplay"
  if (book.mode === "author") return "Writing Project"
  return "Manuscript"
}

export function matchesSearch(book: Book, search: string) {
  if (!search) return true

  const haystack = [book.title, book.author, book.genre, book.series_name, book.status, book.mode]
    .filter(Boolean)
    .join(" ")
    .toLowerCase()

  return haystack.includes(search)
}

export function compareBooks(left: Book, right: Book, sortBy: SortOption) {
  if (sortBy === "title") return left.title.localeCompare(right.title)
  if (sortBy === "progress") return clampProgress(right.progress_pct) - clampProgress(left.progress_pct)

  return new Date(getBookUpdatedAt(right)).getTime() - new Date(getBookUpdatedAt(left)).getTime()
}

export function getVisibleLibraryBooks(books: Book[]) {
  return books.filter((book) => !book.hidden_at && book.access_class !== "reader_collaborator")
}

export function deriveLibraryCollections({
  visibleBooks,
  showArchived,
  modeFilter,
  statusFilter,
  normalizedSearch,
  sortBy,
  pinnedIds,
}: {
  visibleBooks: Book[]
  showArchived: boolean
  modeFilter: ModeFilter
  statusFilter: StatusFilter
  normalizedSearch: string
  sortBy: SortOption
  pinnedIds: Record<string, boolean>
}) {
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

  return {
    filteredBooks,
    explicitPinned,
    fallbackPinned,
    pinnedBooks,
    pinnedBookIds,
    allProjectBooks,
  }
}

export function deriveLibraryMetrics(visibleBooks: Book[]) {
  return {
    totalProjects: visibleBooks.filter((book) => !book.archived_at).length,
    activeDrafts: visibleBooks.filter((book) => !book.archived_at && book.mode === "author").length,
    processing: visibleBooks.filter((book) => !book.archived_at && book.status === "processing").length,
  }
}

export function buildRecentLibraryActivityItems(visibleBooks: Book[]): RecentActivityItem[] {
  return [...visibleBooks]
    .filter((book) => !book.archived_at && !book.hidden_at)
    .sort((left, right) => new Date(getBookUpdatedAt(right)).getTime() - new Date(getBookUpdatedAt(left)).getTime())
    .slice(0, 5)
    .map((book) => ({
      id: `library-activity:${book.id}`,
      label: book.status === "processing" ? `${book.title} is still processing` : `${book.title} was updated`,
      detail: `${getProgressLine(book)} / ${formatRelativeTime(getBookUpdatedAt(book))}`,
      href: getBookHref(book) as Route,
      timestamp: getBookUpdatedAt(book),
      tone: book.status === "failed" ? "danger" : book.status === "processing" ? "warning" : "default",
    }))
}

export function buildLibraryNextBestActions({
  visibleBooks,
  hasAnyProjects,
  onCreateProject,
  recommendationSnoozes = {},
}: {
  visibleBooks: Book[]
  hasAnyProjects: boolean
  onCreateProject: () => void
  recommendationSnoozes?: Record<string, unknown>
}): NextBestAction[] {
  const failedBook = visibleBooks.find((book) => !book.archived_at && book.status === "failed")
  const processingBook = visibleBooks.find((book) => !book.archived_at && book.status === "processing")
  const readyBook = visibleBooks.find((book) => !book.archived_at && book.status === "ready")
  const candidates: NextBestActionCandidate[] = []
  if (!hasAnyProjects) {
    candidates.push({
        id: "new-project",
        label: "New Project",
        description: "Create or import your first manuscript.",
        onSelect: onCreateProject,
        priority: "fallback",
        fingerprint: "library-empty",
      })
  }
  if (failedBook) {
    candidates.push({
      id: `failed:${failedBook.id}`,
      label: "Review processing failure",
      description: `${failedBook.title} needs attention before story tools can refresh.`,
      href: getBookHref(failedBook) as Route,
      tone: "danger",
      priority: "failed_processing",
      fingerprint: `${failedBook.id}:${failedBook.status}:${getBookUpdatedAt(failedBook)}`,
    })
  }
  if (processingBook) {
    candidates.push({
        id: `processing:${processingBook.id}`,
        label: "Check processing",
        description: `${processingBook.title} is refreshing extraction and story memory.`,
        href: getBookHref(processingBook) as Route,
        tone: "secondary",
        priority: "active_drafting",
        fingerprint: `${processingBook.id}:${processingBook.status}:${getBookUpdatedAt(processingBook)}`,
      })
  }
  if (readyBook) {
    candidates.push({
        id: `continue:${readyBook.id}`,
        label: "Continue project",
        description: getProgressLine(readyBook),
        href: getBookHref(readyBook) as Route,
        priority: "active_drafting",
        fingerprint: `${readyBook.id}:${getBookUpdatedAt(readyBook)}`,
      })
  }
  return resolveNextBestActions(candidates, recommendationSnoozes)
}

export function libraryFilterSummary({
  modeFilter,
  statusFilter,
  showArchived,
}: {
  modeFilter: ModeFilter
  statusFilter: StatusFilter
  showArchived: boolean
}) {
  return modeFilter === "all" && statusFilter === "all" && !showArchived ? "Filter" : "Filtered"
}

export function countWarnings(book: Book) {
  let warnings = 0
  if (book.status === "failed") warnings += 1
  if (book.copyright_warning) warnings += 1
  return warnings
}

export function getPublicSampleStatus(book: Book) {
  if (book.public_status === "published" && book.is_public) return "Public book live"
  if (book.public_status === "hidden") return "Public book hidden"
  if (book.public_status === "removed") return "Public book removed"
  if (book.public_status === "pending_review") return "Public review pending"
  return null
}

export function getStatusTooltip(status: BookStatus) {
  if (status === "ready") return "Ready to open"
  if (status === "processing") return "AI analysis is still running"
  if (status === "pending") return "Waiting to process"
  return "Needs review before continuing"
}

export function getStatusBadgeClass(status: BookStatus, isDark: boolean) {
  if (status === "ready") return isDark ? "bg-teal-400/12 text-teal-200" : "bg-teal-50 text-teal-700"
  if (status === "processing") return isDark ? "bg-violet-400/14 text-violet-200" : "bg-violet-50 text-violet-700"
  if (status === "failed") return isDark ? "bg-rose-400/14 text-rose-200" : "bg-rose-50 text-rose-700"
  return isDark ? "bg-white/[0.06] text-[#d7d0c6]" : "bg-stone-100 text-stone-700"
}

export function formatNumber(value: number) {
  return NUMBER_FORMAT.format(value)
}
