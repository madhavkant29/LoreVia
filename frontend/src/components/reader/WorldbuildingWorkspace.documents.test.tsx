import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { WorldbuildingDocumentSidebar } from "./WorldbuildingWorkspace.documents"
import type { WorldBuildingDocument } from "@/types/world-building"

function document(overrides: Partial<WorldBuildingDocument> = {}): WorldBuildingDocument {
  return {
    id: "doc-1",
    book_id: "book-1",
    title: "Atlas Notes",
    source_name: null,
    word_count: 1234,
    is_active: true,
    archived_at: null,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-02T00:00:00Z",
    ...overrides,
  }
}

describe("Worldbuilding document sidebar", () => {
  it("renders visible documents and show-all controls", () => {
    const documents = [
      document(),
      document({ id: "doc-2", title: "City Laws", word_count: 500 }),
    ]
    const markup = renderToStaticMarkup(
      <WorldbuildingDocumentSidebar
        documentsLoading={false}
        documents={documents}
        visibleDocuments={[documents[0]]}
        selectedDocumentId="doc-1"
        showAllDocuments={false}
        isDark={false}
        onNewDocument={vi.fn()}
        onSelectDocument={vi.fn()}
        onToggleShowAllDocuments={vi.fn()}
      />
    )

    expect(markup).toContain("Documents")
    expect(markup).toContain("Reference docs stay separate")
    expect(markup).toContain("Atlas Notes")
    expect(markup).toContain("1,234 words")
    expect(markup).toContain("Show all 2 documents")
  })

  it("renders the empty and loading states", () => {
    const emptyMarkup = renderToStaticMarkup(
      <WorldbuildingDocumentSidebar
        documentsLoading={false}
        documents={[]}
        visibleDocuments={[]}
        selectedDocumentId={null}
        showAllDocuments={false}
        isDark
        onNewDocument={vi.fn()}
        onSelectDocument={vi.fn()}
        onToggleShowAllDocuments={vi.fn()}
      />
    )
    const loadingMarkup = renderToStaticMarkup(
      <WorldbuildingDocumentSidebar
        documentsLoading
        documents={[]}
        visibleDocuments={[]}
        selectedDocumentId={null}
        showAllDocuments={false}
        isDark={false}
        onNewDocument={vi.fn()}
        onSelectDocument={vi.fn()}
        onToggleShowAllDocuments={vi.fn()}
      />
    )

    expect(emptyMarkup).toContain("No world documents yet.")
    expect(emptyMarkup).toContain("Start a reference doc")
    expect(loadingMarkup).toContain("Loading world documents")
  })
})
