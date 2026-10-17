import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { WorldbuildingDocumentEditorCard } from "./WorldbuildingWorkspace.editor"
import type { WorldBuildingDocument } from "@/types/world-building"

function document(overrides: Partial<WorldBuildingDocument> = {}): WorldBuildingDocument {
  return {
    id: "doc-1",
    book_id: "book-1",
    title: "Atlas Notes",
    source_name: null,
    word_count: 1200,
    is_active: true,
    archived_at: null,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-02T00:00:00Z",
    ...overrides,
  }
}

describe("Worldbuilding document editor card", () => {
  it("renders create-state document editing controls", () => {
    const markup = renderToStaticMarkup(
      <WorldbuildingDocumentEditorCard
        isDark={false}
        selectedDocument={null}
        draftTitle="New Atlas"
        draftText="World text"
        savingDocument={false}
        deletingDocument={false}
        analysisLoading={false}
        hasDocuments
        onDraftTitleChange={vi.fn()}
        onDraftTextChange={vi.fn()}
        onSaveDocument={vi.fn()}
        onNewDocument={vi.fn()}
        onDeleteDocument={vi.fn()}
        onRunAnalysis={vi.fn()}
      />
    )

    expect(markup).toContain("Worldbuilding Manuscript")
    expect(markup).toContain("Type directly or upload files")
    expect(markup).toContain("Document title")
    expect(markup).toContain("Worldbuilding manuscript")
    expect(markup).toContain("Create document")
    expect(markup).toContain("Refresh comparison")
  })

  it("renders edit, saving, deleting, and analysis states", () => {
    const markup = renderToStaticMarkup(
      <WorldbuildingDocumentEditorCard
        isDark
        selectedDocument={document()}
        draftTitle="Atlas Notes"
        draftText="World text"
        savingDocument
        deletingDocument
        analysisLoading
        hasDocuments={false}
        onDraftTitleChange={vi.fn()}
        onDraftTextChange={vi.fn()}
        onSaveDocument={vi.fn()}
        onNewDocument={vi.fn()}
        onDeleteDocument={vi.fn()}
        onRunAnalysis={vi.fn()}
      />
    )

    expect(markup).toContain("Editing Atlas Notes")
    expect(markup).toContain("Saving...")
    expect(markup).toContain("Removing...")
    expect(markup).toContain("Refreshing…")
  })
})
