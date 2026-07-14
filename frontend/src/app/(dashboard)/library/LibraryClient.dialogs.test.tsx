import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { PermanentDeleteBookDialog, PublishBookDialog } from "./LibraryClient.dialogs"
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

const themeProps = {
  surfaceClass: "surface",
  mutedText: "muted",
  headingText: "heading",
  controlClass: "control",
}

describe("LibraryClient dialogs", () => {
  it("renders the publish dialog with rights confirmation copy", () => {
    const markup = renderToStaticMarkup(
      <PublishBookDialog
        {...themeProps}
        publishSlug="glass-archive"
        publishDescription="A public sample."
        publishConfirmed={false}
        busy={false}
        onSlugChange={vi.fn()}
        onDescriptionChange={vi.fn()}
        onConfirmedChange={vi.fn()}
        onCancel={vi.fn()}
        onPublish={vi.fn()}
      />
    )

    expect(markup).toContain("Publish your own original work")
    expect(markup).toContain("Public URL slug")
    expect(markup).toContain("I confirm that I own the rights")
    expect(markup).toContain("Publish publicly")
  })

  it("renders the permanent delete dialog with validation state", () => {
    const markup = renderToStaticMarkup(
      <PermanentDeleteBookDialog
        {...themeProps}
        book={book()}
        deleteConfirmation="DELETE"
        deleteError="Type DELETE BOOK exactly to continue."
        busy={false}
        onConfirmationChange={vi.fn()}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />
    )

    expect(markup).toContain("Delete The Glass Archive permanently?")
    expect(markup).toContain("Type DELETE BOOK")
    expect(markup).toContain("Type DELETE BOOK exactly to continue.")
    expect(markup).toContain("Delete permanently")
  })
})
