import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it, vi } from "vitest"

import { buildSidebarSummary, CharacterWorkspaceEmptyState } from "./charactersPage.workspaceState"

describe("characters page workspace state", () => {
  it("builds sidebar summaries for each workspace mode", () => {
    const base = {
      filteredCharCount: 7,
      filteredMergeSuggestionCount: 3,
      filteredPendingCandidateCount: 4,
      filteredRelationshipCandidateCount: 2,
      isManualMerge: false,
      plannedDemotionCount: 1,
      plannedMergeCount: 5,
    }

    expect(buildSidebarSummary({ ...base, workspaceMode: "profile" })).toBe("7 characters")
    expect(buildSidebarSummary({ ...base, workspaceMode: "review" })).toBe("4 candidate items / 2 relationship items")
    expect(buildSidebarSummary({ ...base, workspaceMode: "repair" })).toBe("5 planned merges / 1 planned demotions")
    expect(buildSidebarSummary({ ...base, workspaceMode: "duplicates", isManualMerge: true })).toBe("3 suggestions / manual pair selected")
  })

  it("renders pending-review empty-state actions for authors", () => {
    const markup = renderToStaticMarkup(
      <CharacterWorkspaceEmptyState
        hasPendingReviewItems
        isAuthorMode
        isDark={false}
        pendingReviewItemCount={1}
        onOpenCreateCharacter={vi.fn()}
        onOpenReviewQueue={vi.fn()}
      />
    )

    expect(markup).toContain("LoreVia held 1 extracted item")
    expect(markup).toContain("Review held candidates")
    expect(markup).toContain("Add character manually")
  })

  it("renders processing copy without author actions for readers", () => {
    const markup = renderToStaticMarkup(
      <CharacterWorkspaceEmptyState
        bookStatus="processing"
        hasPendingReviewItems={false}
        isAuthorMode={false}
        isDark
        pendingReviewItemCount={0}
        onOpenCreateCharacter={vi.fn()}
        onOpenReviewQueue={vi.fn()}
      />
    )

    expect(markup).toContain("Processing continues in the background")
    expect(markup).not.toContain("Add character manually")
  })
})
