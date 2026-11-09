import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import { CharacterProfileRightRail } from "./CharacterProfileRightRail"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("CharacterProfileRightRail", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  afterEach(() => {
    act(() => root?.unmount())
    container?.remove()
    container = null
    root = null
  })

  it("renders author-facing review context and delegates quick actions", () => {
    const onOpenRelationships = vi.fn()
    const view = renderRail({ onOpenRelationships })

    expect(view.textContent).toContain("Continuity alerts")
    expect(view.textContent).toContain("Profile coverage")
    expect(view.textContent).toContain("Open questions")
    expect(view.textContent).toContain("Grounded profile")
    expect(view.textContent).toContain("1 connected ties")
    clickButton(view, "Open")
    expect(onOpenRelationships).toHaveBeenCalledOnce()
  })

  it("renders evidence state and delegates evidence refresh", () => {
    const onRefreshEvidence = vi.fn()
    const view = renderRail({ onRefreshEvidence, selectedTab: "evidence" })

    expect(view.textContent).toContain("Grounded clue")
    expect(view.textContent).toContain("Mira studies the map.")
    clickButton(view, "Refresh")
    expect(onRefreshEvidence).toHaveBeenCalledOnce()
  })

  it("uses stored extraction confidence rather than optional profile completeness for the confidence bar", () => {
    const view = renderRail({ storedConfidence: 0.92, healthScore: 13 })

    expect(view.textContent).toContain("Extraction confidence")
    expect(view.textContent).toContain("High confidence")
    expect(view.textContent).toContain("92%")
    expect(view.querySelector('[style="width: 92%;"]')?.classList.contains("bg-emerald-600")).toBe(true)
  })

  it("labels grounding coverage separately when no extraction confidence is stored", () => {
    const view = renderRail({ groundingCoverage: 0.64, healthScore: 13 })

    expect(view.textContent).toContain("Grounding coverage")
    expect(view.textContent).toContain("64% source-backed")
    expect(view.textContent).not.toContain("Low confidence")
  })
})

function renderRail({
  onOpenRelationships = vi.fn(),
  onRefreshEvidence = vi.fn(),
  selectedTab = "insights",
  storedConfidence,
  groundingCoverage,
  healthScore = 84,
}: {
  onOpenRelationships?: () => void
  onRefreshEvidence?: () => void
  selectedTab?: "insights" | "evidence"
  storedConfidence?: number
  groundingCoverage?: number
  healthScore?: number
} = {}) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => {
    root?.render(
      <CharacterProfileRightRail
        character={{
          id: "character-1",
          book_id: "book-1",
          name: "Mira",
          aliases: [],
          role: "mc",
          first_chapter: 1,
          trait_state: {},
          description: "A careful strategist.",
          personality_tags: [],
          motivations: [],
          fears: [],
          archetype: null,
          arc_summary: null,
          relationship_summaries: ["Kael alliance"],
          analysis_metadata: storedConfidence === undefined && groundingCoverage === undefined
            ? undefined
            : { canonical_confidence: storedConfidence, grounding_coverage: groundingCoverage },
        }}
        connections={[{
          source: "character-1",
          target: "character-2",
          type: "ally",
          sentiment: 0.8,
          description: "They coordinate the search.",
          counterpartId: "character-2",
          counterpartName: "Kael",
        }]}
        evidence={[{ chapter_num: 3, chapter_title: "Map room", relevance: 0.9, summary: "Grounded clue", text: "Mira studies the map." }]}
        evidenceError={null}
        evidenceLoading={false}
        health={{ score: healthScore, tone: "strong", summary: "Grounded profile", issues: ["Review one open relationship"] }}
        isDark={false}
        mergeSuggestionCount={1}
        partitioning={false}
        selectedTab={selectedTab}
        onFindEvidence={vi.fn()}
        onManualMerge={vi.fn()}
        onOpenNotes={vi.fn()}
        onOpenRelationships={onOpenRelationships}
        onPartition={vi.fn()}
        onRefreshEvidence={onRefreshEvidence}
        onReviewDuplicates={vi.fn()}
        onSelectTab={vi.fn()}
      />
    )
  })
  return container
}

function clickButton(view: HTMLDivElement, label: string) {
  const button = Array.from(view.querySelectorAll("button")).find((candidate) => candidate.textContent?.trim() === label)
  if (!button) throw new Error(`Could not find ${label} button`)
  act(() => {
    button.click()
  })
}
