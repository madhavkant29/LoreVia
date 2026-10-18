import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { CreateProjectCard, EmptyPanel, ProjectCard, ProjectRow } from "./LibraryClient.projects"
import type { Book } from "@/types/book"

function book(overrides: Partial<Book> = {}): Book {
  return {
    id: "book-1",
    title: "The Glass Archive",
    author: "A. Writer",
    genre: "Fantasy",
    format: "pdf",
    work_type: "novel",
    status: "ready",
    mode: "author",
    workspace_shell: "author",
    access_class: "owner",
    can_switch_workspace_mode: true,
    total_chapters: 12,
    chapters_read_count: 4,
    progress_pct: 55,
    total_tokens: 40_000,
    created_at: "2026-06-01T00:00:00Z",
    processing: {
      status: "ready",
      stage: "ready",
      label: "Ready",
      progress_pct: 100,
      retryAvailable: false,
      updated_at: "2026-06-02T00:00:00Z",
    },
    ...overrides,
  } as Book
}

const handlers = {
  onMenuToggle: vi.fn(),
  onOpen: vi.fn(),
  onPrefetch: vi.fn(),
  onRetryProcessing: vi.fn(),
  onTogglePinned: vi.fn(),
  onArchive: vi.fn(),
  onRestore: vi.fn(),
  onRemove: vi.fn(),
  onPermanentDelete: vi.fn(),
  onAddChapter: vi.fn(),
  onPublish: vi.fn(),
  onUnpublish: vi.fn(),
}

describe("LibraryClient project presentation", () => {
  it("offers continuation for allowance-paused projects in cards and rows", () => {
    const pausedBook = book({
      status: "processing",
      processing: {
        status: "paused",
        stage: "paused",
        chapters_completed: 1,
        chapters_total: 3,
        pause_reason: "monthly_processed_words",
        resume_available: true,
        retry_available: true,
      },
    })
    const cardMarkup = renderToStaticMarkup(
      <ProjectCard book={pausedBook} isDark busy={false} isPinned={false} menuOpen={false} {...handlers} />
    )
    const rowMarkup = renderToStaticMarkup(
      <ProjectRow book={pausedBook} isDark={false} busy={false} isPinned={false} menuOpen={false} {...handlers} />
    )

    expect(cardMarkup).toContain("Continue processing")
    expect(rowMarkup).toContain("Continue processing")
  })

  it("renders project cards, rows, empty panels, and create cards", () => {
    const cardMarkup = renderToStaticMarkup(
      <ProjectCard
        book={book({ public_status: "published", is_public: true })}
        isDark
        busy={false}
        isPinned
        menuOpen
        {...handlers}
      />
    )
    const rowMarkup = renderToStaticMarkup(
      <ProjectRow
        book={book({ title: "Row Project", work_type: "screenplay" })}
        isDark={false}
        busy={false}
        isPinned={false}
        menuOpen={false}
        {...handlers}
      />
    )
    const emptyMarkup = renderToStaticMarkup(
      <EmptyPanel isDark={false} title="No projects yet" body="Start writing." actionLabel="New Project" actionHandler={vi.fn()} />
    )
    const createMarkup = renderToStaticMarkup(<CreateProjectCard isDark onCreate={vi.fn()} />)

    expect(cardMarkup).toContain("The Glass Archive")
    expect(cardMarkup).toContain("Public sample")
    expect(cardMarkup).toContain('href="/the-glass-archive--book-1"')
    expect(cardMarkup).not.toContain('role="button"')
    expect(cardMarkup).toContain("Pin")
    expect(rowMarkup).toContain("Row Project")
    expect(rowMarkup).toContain("Screenplay")
    expect(emptyMarkup).toContain("No projects yet")
    expect(createMarkup).toContain("Create New Project")
  })
})
