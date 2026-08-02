import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { AutoWikiCard } from "./WorldbuildingWorkspace.wiki"
import type { WikiEntry, WorldQueryResponse } from "@/types/world-building"

function wikiEntry(overrides: Partial<WikiEntry> = {}): WikiEntry {
  return {
    id: "wiki-1",
    book_id: "book-1",
    entry_type: "location",
    name: "Moon Gate",
    description: "A gate that opens during a lunar rite.",
    first_mention: 4,
    related_char_ids: [],
    created_at: "2026-06-01T00:00:00Z",
    ...overrides,
  }
}

const logicResult: WorldQueryResponse = {
  mode: "gap_detection",
  answer: "The canon can support the moon-gate climax if ritual costs are clarified.",
  citations: [{ title: "Atlas Notes", excerpt: "Moon gates need a lunar key." }],
  suggestions: [{ title: "Clarify ritual cost" }],
  logic_alerts: [{ title: "Cost conflict" }],
  simulation_steps: ["Check canon", "Compare story use"],
}

describe("Worldbuilding Auto Wiki card", () => {
  it("renders logic query output and wiki entries", () => {
    const entries = [wikiEntry(), wikiEntry({ id: "wiki-2", name: "Sun Road", entry_type: "place" })]
    const markup = renderToStaticMarkup(
      <AutoWikiCard
        isDark={false}
        logicQuery="Can the gates open?"
        logicLoading={false}
        logicResult={logicResult}
        wikiEntries={entries}
        wikiEntriesLoading={false}
        wikiGenerating={false}
        visibleWikiEntries={[entries[0]]}
        wikiTypeSummary={{ location: 1, place: 1 }}
        showAllWikiEntries={false}
        initialWikiCount={1}
        onLogicQueryChange={vi.fn()}
        onRunLogicQuery={vi.fn()}
        onRefreshWiki={vi.fn()}
        onGenerateWiki={vi.fn()}
        onToggleShowAllWikiEntries={vi.fn()}
      />
    )

    expect(markup).toContain("Generate wiki entries from manuscript text")
    expect(markup).toContain("Canon stress test")
    expect(markup).toContain("1 alerts")
    expect(markup).toContain("1 citations")
    expect(markup).toContain("The canon can support")
    expect(markup).toContain("Simulation steps")
    expect(markup).toContain("Clarify ritual cost")
    expect(markup).toContain("Moon Gate")
    expect(markup).toContain("First mention: chapter 4")
    expect(markup).toContain("Show all 2 entries")
  })

  it("renders loading, empty, and generating states", () => {
    const markup = renderToStaticMarkup(
      <AutoWikiCard
        isDark
        logicQuery=""
        logicLoading
        logicResult={null}
        wikiEntries={[]}
        wikiEntriesLoading
        wikiGenerating
        visibleWikiEntries={[]}
        wikiTypeSummary={{}}
        showAllWikiEntries={false}
        initialWikiCount={6}
        onLogicQueryChange={vi.fn()}
        onRunLogicQuery={vi.fn()}
        onRefreshWiki={vi.fn()}
        onGenerateWiki={vi.fn()}
        onToggleShowAllWikiEntries={vi.fn()}
      />
    )

    expect(markup).toContain("Thinking...")
    expect(markup).toContain("Generating...")
    expect(markup).toContain("Loading wiki entries")
  })

  it("renders empty wiki entries when not loading", () => {
    const markup = renderToStaticMarkup(
      <AutoWikiCard
        isDark={false}
        logicQuery=""
        logicLoading={false}
        logicResult={null}
        wikiEntries={[]}
        wikiEntriesLoading={false}
        wikiGenerating={false}
        visibleWikiEntries={[]}
        wikiTypeSummary={{}}
        showAllWikiEntries={false}
        initialWikiCount={6}
        onLogicQueryChange={vi.fn()}
        onRunLogicQuery={vi.fn()}
        onRefreshWiki={vi.fn()}
        onGenerateWiki={vi.fn()}
        onToggleShowAllWikiEntries={vi.fn()}
      />
    )

    expect(markup).toContain("No wiki entries yet.")
    expect(markup).toContain("Generate wiki")
  })
})
