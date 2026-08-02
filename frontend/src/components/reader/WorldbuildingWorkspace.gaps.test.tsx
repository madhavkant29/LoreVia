import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { GapAnalysisCard } from "./WorldbuildingWorkspace.gaps"
import type { WorldGapItem, WorldGapResult } from "@/types/world-building"

function gapItem(overrides: Partial<WorldGapItem> = {}): WorldGapItem {
  return {
    id: "gap-1",
    category: "canon_conflict",
    severity: "high",
    title: "Moon gate cost conflict",
    description: "The moon gate has two incompatible costs.",
    suggested_fix: "Choose one cost and apply it consistently.",
    world_evidence: "World bible says blood cost.",
    story_evidence: "Chapter says silver cost.",
    world_document_id: "doc-1",
    world_document_title: "Atlas Notes",
    story_chapter_number: 4,
    story_chapter_title: "Moon Road",
    character_name: null,
    priority: 8,
    entity_type: "magic",
    canonical_name: "Moon Gate",
    confidence: 0.91,
    provenance: {},
    ...overrides,
  }
}

function analysis(items: WorldGapItem[], flags: Record<string, unknown>[] = []): WorldGapResult {
  return {
    mode: "gap_detection",
    generated_at: "2026-06-01T00:00:00Z",
    gap_categories: { canon_conflict: items },
    gap_groups: [
      {
        key: "canon_conflict",
        label: "Canon conflicts",
        description: "Conflicts between world docs and story text.",
        items,
      },
    ],
    priority_gaps: items,
    consistency_flags: flags,
    world_elements: [],
    world_documents: [],
  }
}

describe("Worldbuilding gap analysis card", () => {
  it("renders gap groups, evidence, save state, and show-all controls", () => {
    const first = gapItem()
    const second = gapItem({ id: "gap-2", title: "River oath mismatch", story_chapter_number: null })
    const markup = renderToStaticMarkup(
      <GapAnalysisCard
        bookId="book-1"
        isDark={false}
        analysis={analysis([first, second])}
        analysisLoading={false}
        runButtonLoading={false}
        documentsAvailable
        expandedGapGroups={{}}
        openGapIds={new Set([first.id])}
        noteSavingId="gap-2"
        initialGapItemsPerGroup={1}
        onRunAnalysis={vi.fn()}
        onStartNewDocument={vi.fn()}
        onSaveGapAsNote={vi.fn()}
        onToggleGapGroup={vi.fn()}
      />
    )

    expect(markup).toContain("Grouped inconsistencies and cleanup notes")
    expect(markup).toContain("Canon conflicts")
    expect(markup).toContain("Moon gate cost conflict")
    expect(markup).toContain("Chapter 4")
    expect(markup).toContain("World bible says blood cost.")
    expect(markup).toContain("Chapter says silver cost.")
    expect(markup).toContain("Suggested fix")
    expect(markup).toContain("Saved to notes")
    expect(markup).toContain("Show all 2 items")
  })

  it("renders expanded groups and consistency flags", () => {
    const markup = renderToStaticMarkup(
      <GapAnalysisCard
        bookId="book-1"
        isDark
        analysis={analysis(
          [gapItem(), gapItem({ id: "gap-2", title: "River oath mismatch" })],
          [{ id: "flag-1", type: "name_conflict", title: "Name conflict", description: "Two city names conflict." }],
        )}
        analysisLoading={false}
        runButtonLoading={false}
        documentsAvailable
        expandedGapGroups={{ canon_conflict: true }}
        openGapIds={new Set()}
        noteSavingId={null}
        initialGapItemsPerGroup={1}
        onRunAnalysis={vi.fn()}
        onStartNewDocument={vi.fn()}
        onSaveGapAsNote={vi.fn()}
        onToggleGapGroup={vi.fn()}
      />
    )

    expect(markup).toContain("Consistency flags")
    expect(markup).toContain("name conflict")
    expect(markup).toContain("River oath mismatch")
    expect(markup).toContain("Show fewer items")
  })

  it("renders loading and no-analysis states", () => {
    const loadingMarkup = renderToStaticMarkup(
      <GapAnalysisCard
        bookId="book-1"
        isDark={false}
        analysis={null}
        analysisLoading
        runButtonLoading={false}
        documentsAvailable
        expandedGapGroups={{}}
        openGapIds={new Set()}
        noteSavingId={null}
        initialGapItemsPerGroup={4}
        onRunAnalysis={vi.fn()}
        onStartNewDocument={vi.fn()}
        onSaveGapAsNote={vi.fn()}
        onToggleGapGroup={vi.fn()}
      />
    )
    const noDocumentsMarkup = renderToStaticMarkup(
      <GapAnalysisCard
        bookId="book-1"
        isDark={false}
        analysis={null}
        analysisLoading={false}
        runButtonLoading={false}
        documentsAvailable={false}
        expandedGapGroups={{}}
        openGapIds={new Set()}
        noteSavingId={null}
        initialGapItemsPerGroup={4}
        onRunAnalysis={vi.fn()}
        onStartNewDocument={vi.fn()}
        onSaveGapAsNote={vi.fn()}
        onToggleGapGroup={vi.fn()}
      />
    )

    expect(loadingMarkup).toContain("Comparing the world corpus")
    expect(noDocumentsMarkup).toContain("Reference docs are missing")
    expect(noDocumentsMarkup).toContain("Start a reference doc")
  })

  it("renders empty completed analysis", () => {
    const emptyAnalysis: WorldGapResult = {
      ...analysis([]),
      gap_groups: [],
      consistency_flags: [],
    }
    const markup = renderToStaticMarkup(
      <GapAnalysisCard
        bookId="book-1"
        isDark={false}
        analysis={emptyAnalysis}
        analysisLoading={false}
        runButtonLoading
        documentsAvailable
        expandedGapGroups={{}}
        openGapIds={new Set()}
        noteSavingId={null}
        initialGapItemsPerGroup={4}
        onRunAnalysis={vi.fn()}
        onStartNewDocument={vi.fn()}
        onSaveGapAsNote={vi.fn()}
        onToggleGapGroup={vi.fn()}
      />
    )

    expect(markup).toContain("Gap results need reference documents")
    expect(markup).toContain("Running...")
  })
})
