import { beforeEach, describe, expect, it, vi } from "vitest"

import {
  buildLibraryNextBestActions,
  buildRecentLibraryActivityItems,
  clampProgress,
  compareBooks,
  countWarnings,
  deriveLibraryCollections,
  deriveLibraryMetrics,
  getBookWordCount,
  formatNumber,
  formatRelativeTime,
  getActiveUnit,
  getBookUpdatedAt,
  getGenreLabel,
  getProgressLine,
  getPublicSampleStatus,
  getStatusBadgeClass,
  getStatusTooltip,
  getVisibleLibraryBooks,
  libraryFilterSummary,
  matchesSearch,
  storyUnitLabel,
  storyUnitPrefix,
} from "./LibraryClient.helpers"
import type { Book } from "@/types/book"

function buildBook(overrides: Partial<Book> & Pick<Book, "id" | "title">): Book {
  return {
    author: "A. Writer",
    genre: "Fantasy",
    format: "pdf",
    work_type: "novel",
    status: "ready",
    mode: "author",
    workspace_shell: "author",
    access_class: "owner",
    can_switch_workspace_mode: true,
    total_chapters: 10,
    chapters_read_count: 2,
    progress_pct: 30,
    total_tokens: 24_000,
    created_at: "2026-06-01T00:00:00Z",
    processing: {
      status: "ready",
      stage: "ready",
      label: "Ready",
      progress_pct: 100,
      retryAvailable: false,
      updated_at: "2026-06-05T00:00:00Z",
    },
    ...overrides,
  } as Book
}

beforeEach(() => {
  vi.useRealTimers()
})

describe("LibraryClient helpers", () => {
  it("shows every explicit pin in the selected sort order and excludes archived pins", () => {
    const visibleBooks = ["D", "B", "C", "A", "E"].map((id) => buildBook({ id, title: id }))
    visibleBooks[4].archived_at = "2026-09-29T12:00:00Z"
    const result = deriveLibraryCollections({ visibleBooks, showArchived: true, modeFilter: "all", statusFilter: "all", normalizedSearch: "", sortBy: "title", pinnedIds: { A: true, B: true, C: true, D: true, E: true } })
    expect(result.pinnedBooks.map((book) => book.id)).toEqual(["A", "B", "C", "D"])
    expect(result.allProjectBooks.map((book) => book.id)).toEqual(["E"])
  })
  it("formats story units, progress, numbers, and relative timestamps", () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-06-05T02:00:00Z"))

    expect(storyUnitLabel("screenplay")).toBe("scene")
    expect(storyUnitLabel("screenplay", true)).toBe("scenes")
    expect(storyUnitPrefix("screenplay")).toBe("Scene")
    expect(clampProgress(-10)).toBe(0)
    expect(clampProgress(101.4)).toBe(100)
    expect(formatNumber(12345)).toBe("12,345")
    expect(formatRelativeTime("2026-06-05T01:35:00Z")).toBe("Updated 25m ago")
    expect(formatRelativeTime("not-a-date")).toBe("Updated recently")
  })

  it("derives project progress and word-count summaries", () => {
    const processingBook = buildBook({
      id: "processing",
      title: "Processing",
      status: "processing",
      processing: {
        status: "processing",
        stage: "extracting",
        current_step_label: "Processing",
        progress_pct: 50,
        retry_available: false,
        last_chapter_number: 4,
        last_chapter_title: "The Ash Gate",
        updated_at: "2026-06-06T00:00:00Z",
      },
    })
    const screenplay = buildBook({
      id: "screenplay",
      title: "Screenplay",
      work_type: "screenplay",
      total_tokens: null,
      total_chapters: 4,
      chapters_read_count: 0,
    })

    expect(getBookUpdatedAt(processingBook)).toBe("2026-06-06T00:00:00Z")
    expect(getActiveUnit(processingBook)).toBe(4)
    expect(getProgressLine(processingBook)).toBe("Chapter 4 - The Ash Gate")
    expect(getBookWordCount(processingBook)).toBe(0)
    expect(getBookWordCount(screenplay)).toBe(0)
    expect(getBookWordCount(buildBook({ id: "measured", title: "Measured", total_words: 12_345 }))).toBe(12_345)
  })

  it("filters and sorts books consistently", () => {
    const alpha = buildBook({
      id: "alpha",
      title: "Alpha",
      progress_pct: 10,
      processing: { status: "ready", stage: "ready", current_step_label: "Ready", progress_pct: 100, retry_available: false, updated_at: "2026-06-01T00:00:00Z" },
    })
    const beta = buildBook({
      id: "beta",
      title: "Beta",
      progress_pct: 90,
      series_name: "Ash Cycle",
      processing: { status: "ready", stage: "ready", current_step_label: "Ready", progress_pct: 100, retry_available: false, updated_at: "2026-06-03T00:00:00Z" },
    })

    expect(matchesSearch(beta, "ash")).toBe(true)
    expect(matchesSearch(alpha, "ash")).toBe(false)
    expect([beta, alpha].sort((left, right) => compareBooks(left, right, "title"))).toEqual([alpha, beta])
    expect([alpha, beta].sort((left, right) => compareBooks(left, right, "progress"))).toEqual([beta, alpha])
    expect([alpha, beta].sort((left, right) => compareBooks(left, right, "recent"))).toEqual([beta, alpha])
  })

  it("derives visible collections, explicit pins, metrics, and recent activity", () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-06-10T00:00:00Z"))

    const ready = buildBook({
      id: "ready",
      title: "Ready Project",
      progress_pct: 80,
      processing: { status: "ready", stage: "ready", current_step_label: "Ready", progress_pct: 100, retry_available: false, updated_at: "2026-06-09T00:00:00Z" },
    })
    const processing = buildBook({
      id: "processing",
      title: "Processing Project",
      status: "processing",
      progress_pct: 40,
      processing: { status: "processing", stage: "extracting", current_step_label: "Extracting", progress_pct: 40, retry_available: false, updated_at: "2026-06-10T00:00:00Z" },
    })
    const archived = buildBook({
      id: "archived",
      title: "Archived Project",
      archived_at: "2026-06-01T00:00:00Z",
    })
    const hidden = buildBook({
      id: "hidden",
      title: "Hidden Project",
      hidden_at: "2026-06-01T00:00:00Z",
    })
    const collaborator = buildBook({
      id: "collaborator",
      title: "Collaborator Project",
      access_class: "reader_collaborator",
    })

    const visibleBooks = getVisibleLibraryBooks([ready, processing, archived, hidden, collaborator])
    expect(visibleBooks.map((book) => book.id)).toEqual(["ready", "processing", "archived"])

    const collections = deriveLibraryCollections({
      visibleBooks,
      showArchived: false,
      modeFilter: "all",
      statusFilter: "all",
      normalizedSearch: "",
      sortBy: "recent",
      pinnedIds: { ready: true },
    })
    expect(collections.filteredBooks.map((book) => book.id)).toEqual(["processing", "ready"])
    expect(collections.pinnedBooks.map((book) => book.id)).toEqual(["ready"])
    expect(collections.allProjectBooks.map((book) => book.id)).toEqual(["processing"])

    const fallbackCollections = deriveLibraryCollections({
      visibleBooks,
      showArchived: false,
      modeFilter: "all",
      statusFilter: "all",
      normalizedSearch: "",
      sortBy: "recent",
      pinnedIds: {},
    })
    expect(fallbackCollections.pinnedBooks).toEqual([])
    expect(fallbackCollections.allProjectBooks.map((book) => book.id)).toEqual(["processing", "ready"])

    expect(deriveLibraryMetrics(visibleBooks)).toEqual({
      totalProjects: 2,
      activeDrafts: 2,
      processing: 1,
    })
    expect(buildRecentLibraryActivityItems(visibleBooks)[0]).toMatchObject({
      id: "library-activity:processing",
      label: "Processing Project is still processing",
      tone: "warning",
    })
    expect(libraryFilterSummary({ modeFilter: "all", statusFilter: "all", showArchived: false })).toBe("Filter")
    expect(libraryFilterSummary({ modeFilter: "author", statusFilter: "all", showArchived: false })).toBe("Filtered")
  })

  it("derives next-best actions for empty, processing, and ready libraries", () => {
    const create = vi.fn()
    const ready = buildBook({ id: "ready", title: "Ready Project", status: "ready" })
    const processing = buildBook({ id: "processing", title: "Processing Project", status: "processing" })

    expect(buildLibraryNextBestActions({
      visibleBooks: [],
      hasAnyProjects: false,
      onCreateProject: create,
    })[0]).toMatchObject({ id: "new-project", label: "New Project" })
    expect(buildLibraryNextBestActions({
      visibleBooks: [processing, ready],
      hasAnyProjects: true,
      onCreateProject: create,
    })[0]).toMatchObject({ id: "processing:processing", label: "Check processing", tone: "secondary" })
    expect(buildLibraryNextBestActions({
      visibleBooks: [ready],
      hasAnyProjects: true,
      onCreateProject: create,
    })[0]).toMatchObject({ id: "continue:ready", label: "Continue project" })
  })

  it("derives status, genre, warning, and public sample labels", () => {
    const failedPublic = buildBook({
      id: "failed",
      title: "Failed",
      status: "failed",
      genre: "",
      copyright_warning: true,
      public_status: "published",
      is_public: true,
    })

    expect(getGenreLabel(failedPublic)).toBe("Writing Project")
    expect(countWarnings(failedPublic)).toBe(2)
    expect(getPublicSampleStatus(failedPublic)).toBe("Public book live")
    expect(getStatusTooltip("failed")).toBe("Needs review before continuing")
    expect(getStatusBadgeClass("ready", true)).toContain("text-teal")
    expect(getStatusBadgeClass("pending", false)).toContain("text-stone")
  })
})
