import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { FolderIcon } from "./LibraryClient.icons"
import { LibraryProjectSection } from "./LibraryClient.sections"
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

describe("LibraryClient sections", () => {
  it("renders project collections with create actions", () => {
    const markup = renderToStaticMarkup(
      <LibraryProjectSection
        isDark={false}
        loading={false}
        viewMode="grid"
        title="All projects"
        icon={<FolderIcon />}
        books={[book()]}
        busyBookId={null}
        pinnedIds={{ "book-1": true }}
        menuBookId={null}
        skeletonLabel="Loading all projects"
        showCreateProject
        onCreateProject={vi.fn()}
        handlers={handlers}
      />
    )

    expect(markup).toContain("All projects")
    expect(markup).toContain("The Glass Archive")
    expect(markup).toContain("Create New Project")
  })

  it("renders configured empty states", () => {
    const markup = renderToStaticMarkup(
      <LibraryProjectSection
        isDark
        loading={false}
        viewMode="list"
        title="Pinned projects"
        icon={<FolderIcon />}
        books={[]}
        busyBookId={null}
        pinnedIds={{}}
        menuBookId={null}
        skeletonLabel="Loading pinned projects"
        emptyState={{
          show: true,
          title: "Nothing pinned yet",
          body: "Use a project menu.",
          actionLabel: "New Project",
          onAction: vi.fn(),
        }}
        handlers={handlers}
      />
    )

    expect(markup).toContain("Pinned projects")
    expect(markup).toContain("Nothing pinned yet")
    expect(markup).toContain("New Project")
  })
})
