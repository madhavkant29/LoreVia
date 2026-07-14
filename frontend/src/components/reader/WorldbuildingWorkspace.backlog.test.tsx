import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { SavedCleanupBacklogCard } from "./WorldbuildingWorkspace.backlog"
import type { WorldNote } from "@/types/world-building"

function note(overrides: Partial<WorldNote> = {}): WorldNote {
  return {
    id: "note-1",
    book_id: "book-1",
    world_element_id: null,
    world_document_id: "doc-1",
    note_type: "world_gap",
    chapter_number: 3,
    title: "Clarify moon gates",
    body: "Moon gate rules conflict between documents.",
    priority: "high",
    status: "open",
    linked_gap_id: "gap-1",
    linked_integration_id: null,
    context_label: "Atlas Notes",
    suggested_fix: "Align the ritual cost before the next chapter.",
    tags: [],
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-02T00:00:00Z",
    addressed_at: null,
    ...overrides,
  }
}

describe("Worldbuilding saved cleanup backlog card", () => {
  it("renders chapter filters and note columns", () => {
    const markup = renderToStaticMarkup(
      <SavedCleanupBacklogCard
        isDark={false}
        notesLoading={false}
        chapterFilter="3"
        loadingChapterNotes={false}
        isChapterFiltered
        openNotes={[note()]}
        addressedNotes={[note({ id: "note-2", status: "addressed", addressed_at: "2026-06-03T00:00:00Z" })]}
        noteStatusId={null}
        onChapterFilterChange={vi.fn()}
        onFetchNotesByChapter={vi.fn()}
        onClearChapterFilter={vi.fn()}
        onRefreshNotes={vi.fn()}
        onResolveNote={vi.fn()}
        onReopenNote={vi.fn()}
        onDeleteNote={vi.fn()}
      />
    )

    expect(markup).toContain("Saved cleanup backlog")
    expect(markup).toContain("Filter by chapter")
    expect(markup).toContain("Show all")
    expect(markup).toContain("Open Notes")
    expect(markup).toContain("Clarify moon gates")
    expect(markup).toContain("Suggested fix")
    expect(markup).toContain("Addressed Notes")
    expect(markup).toContain("Reopen")
  })

  it("renders loading and empty states", () => {
    const loadingMarkup = renderToStaticMarkup(
      <SavedCleanupBacklogCard
        isDark
        notesLoading
        chapterFilter=""
        loadingChapterNotes
        isChapterFiltered={false}
        openNotes={[]}
        addressedNotes={[]}
        noteStatusId={null}
        onChapterFilterChange={vi.fn()}
        onFetchNotesByChapter={vi.fn()}
        onClearChapterFilter={vi.fn()}
        onRefreshNotes={vi.fn()}
        onResolveNote={vi.fn()}
        onReopenNote={vi.fn()}
        onDeleteNote={vi.fn()}
      />
    )
    const emptyMarkup = renderToStaticMarkup(
      <SavedCleanupBacklogCard
        isDark={false}
        notesLoading={false}
        chapterFilter=""
        loadingChapterNotes={false}
        isChapterFiltered={false}
        openNotes={[]}
        addressedNotes={[]}
        noteStatusId={null}
        onChapterFilterChange={vi.fn()}
        onFetchNotesByChapter={vi.fn()}
        onClearChapterFilter={vi.fn()}
        onRefreshNotes={vi.fn()}
        onResolveNote={vi.fn()}
        onReopenNote={vi.fn()}
        onDeleteNote={vi.fn()}
      />
    )

    expect(loadingMarkup).toContain("Loading...")
    expect(loadingMarkup).toContain("Loading saved world-gap notes")
    expect(emptyMarkup).toContain("No open world gap notes right now.")
    expect(emptyMarkup).toContain("No resolved notes yet.")
  })
})
