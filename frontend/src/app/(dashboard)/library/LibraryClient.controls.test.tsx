import { createRef } from "react"
import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { LibraryProjectControls } from "./LibraryClient.controls"

describe("LibraryClient controls", () => {
  it("renders search, filter, sort, and view controls", () => {
    const markup = renderToStaticMarkup(
      <LibraryProjectControls
        isDark={false}
        searchInputRef={createRef<HTMLInputElement>()}
        search="glass"
        filterSummary="Filtered"
        filterOpen
        modeFilter="author"
        statusFilter="ready"
        showArchived={false}
        sortBy="recent"
        viewMode="grid"
        surfaceClass="surface"
        controlClass="control"
        mutedText="muted"
        headingText="heading"
        onSearchChange={vi.fn()}
        onFilterToggle={vi.fn()}
        onModeFilterChange={vi.fn()}
        onStatusFilterChange={vi.fn()}
        onShowArchivedToggle={vi.fn()}
        onSortChange={vi.fn()}
        onViewModeChange={vi.fn()}
      />
    )

    expect(markup).toContain("Search projects")
    expect(markup).toContain("Filtered")
    expect(markup).toContain("Project mode")
    expect(markup).toContain("Ready")
    expect(markup).toContain("Recently updated")
    expect(markup).toContain("Grid")
    expect(markup).toContain("List")
  })
})
