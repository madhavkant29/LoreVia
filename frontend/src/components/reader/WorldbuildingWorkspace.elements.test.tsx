import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { ElementSuggestionsCard, ExtractedElementsCard } from "./WorldbuildingWorkspace.elements"
import type { WorldElement } from "@/types/world-building"

function element(overrides: Partial<WorldElement> = {}): WorldElement {
  return {
    id: "element-1",
    book_id: "book-1",
    series_id: null,
    world_document_id: "doc-1",
    source_scope: "worldbuilding",
    element_type: "magic_system",
    name: "Moon Gates",
    description: "Ancient gates opened by lunar rites.",
    parent_element_id: null,
    dependencies: [],
    usage_count: 12,
    gap_score: null,
    integration_score: null,
    suggestions: [{ title: "Use in chapter climax", reason: "Raises stakes" }],
    edited_by_author: false,
    is_series_canonical: false,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-02T00:00:00Z",
    chapter_number: null,
    chapter_title: null,
    world_document_title: "Atlas Notes",
    canonical_name: null,
    aliases: [],
    confidence: 0.82,
    provenance: [],
    claims: [],
    chapter_numbers: [1, 4],
    chapter_count: 2,
    summary_mentions: 3,
    presence_score: null,
    narrative_modes: [],
    source_excerpt: null,
    character_id: null,
    author_override: false,
    ...overrides,
  }
}

describe("Worldbuilding element cards", () => {
  it("renders element suggestions and show-all controls", () => {
    const suggestionElement = element()
    const markup = renderToStaticMarkup(
      <ElementSuggestionsCard
        isDark={false}
        suggestionElements={[suggestionElement, element({ id: "element-2", name: "River Oath" })]}
        visibleSuggestionElements={[suggestionElement]}
        showAllSuggestions={false}
        initialSuggestionCount={1}
        onAcceptElementSuggestion={vi.fn()}
        onToggleShowAllSuggestions={vi.fn()}
      />
    )

    expect(markup).toContain("Element Suggestions")
    expect(markup).toContain("2 items ready for review")
    expect(markup).toContain("Moon Gates")
    expect(markup).toContain("Use in chapter climax")
    expect(markup).toContain("Mark implemented")
    expect(markup).toContain("Show all 2 suggestion groups")
  })

  it("renders extracted element summaries and refresh state", () => {
    const extracted = element()
    const markup = renderToStaticMarkup(
      <ExtractedElementsCard
        isDark
        extractedElements={[extracted]}
        visibleElements={[extracted]}
        visibleElementCards={[extracted]}
        elementTypeSummary={{ magic_system: 1 }}
        elementsLoading
        showAllElements={false}
        initialElementCount={0}
        onRefreshElements={vi.fn()}
        onToggleShowAllElements={vi.fn()}
      />
    )

    expect(markup).toContain("Extracted Elements")
    expect(markup).toContain("Refreshing...")
    expect(markup).toContain("magic system 1")
    expect(markup).toContain("Moon Gates")
    expect(markup).toContain("82%")
    expect(markup).toContain("12 mentions")
    expect(markup).toContain("Show all 1 elements")
  })

  it("renders empty states", () => {
    const suggestionsMarkup = renderToStaticMarkup(
      <ElementSuggestionsCard
        isDark={false}
        suggestionElements={[]}
        visibleSuggestionElements={[]}
        showAllSuggestions={false}
        initialSuggestionCount={6}
        onAcceptElementSuggestion={vi.fn()}
        onToggleShowAllSuggestions={vi.fn()}
      />
    )
    const extractedMarkup = renderToStaticMarkup(
      <ExtractedElementsCard
        isDark={false}
        extractedElements={[]}
        visibleElements={[]}
        visibleElementCards={[]}
        elementTypeSummary={{}}
        elementsLoading={false}
        showAllElements={false}
        initialElementCount={6}
        onRefreshElements={vi.fn()}
        onToggleShowAllElements={vi.fn()}
      />
    )

    expect(suggestionsMarkup).toContain("No element suggestions yet.")
    expect(extractedMarkup).toContain("No extracted elements yet.")
  })
})
