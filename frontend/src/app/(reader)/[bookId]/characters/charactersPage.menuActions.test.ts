import { describe, expect, it, vi } from "vitest"

import type { Character } from "@/types/character"
import { buildCharacterMenuActions, buildPageMenuActions } from "./charactersPage.menuActions"

function character(overrides: Partial<Character> = {}): Character {
  return {
    id: "character-1",
    book_id: "book-1",
    name: "Mira",
    aliases: [],
    role: "mc",
    first_chapter: 1,
    last_seen_chapter: 3,
    mention_count: 12,
    status: "alive",
    trait_state: {},
    description: null,
    personality_tags: [],
    motivations: [],
    fears: [],
    archetype: null,
    arc_summary: null,
    analysis_metadata: {},
    ...overrides,
  }
}

describe("charactersPage menu action builders", () => {
  it("builds page actions with author-only entries and export busy state", () => {
    const onClosePageMenu = vi.fn()
    const onCreateCharacter = vi.fn()
    const onExportCharacterBible = vi.fn()
    const actions = buildPageMenuActions({
      exporting: "bible",
      isAuthorMode: true,
      refreshingGraph: false,
      onClosePageMenu,
      onCreateCharacter,
      onExportCharacterBible,
      onManualMerge: vi.fn(),
      onOpenDuplicateReview: vi.fn(),
      onOpenRepairWorkspace: vi.fn(),
      onOpenReviewQueue: vi.fn(),
      onRebuildGraph: vi.fn(),
      onResetFilters: vi.fn(),
    })

    expect(actions.map((action) => action.label)).toEqual([
      "Open add character",
      "Open review queue",
      "Exporting bible...",
      "Exporting PDF...",
      "Review duplicate suggestions",
      "Open repair workspace",
      "Open manual merge",
      "Rebuild relationship graph",
      "Reset filters",
    ])
    expect(actions[2]?.disabled).toBe(true)
    expect(actions[3]?.disabled).toBe(true)

    actions[0]?.onClick()
    expect(onCreateCharacter).toHaveBeenCalledTimes(1)
    expect(onClosePageMenu).toHaveBeenCalledTimes(1)
  })

  it("builds character actions with protected and busy labels", () => {
    const onCloseCharacterMenu = vi.fn()
    const onToggleProtectedFromRepair = vi.fn()
    const onDemoteSelectedCharacter = vi.fn()
    const actions = buildCharacterMenuActions({
      character: character({ analysis_metadata: { protected_from_repair: true } }),
      deleting: true,
      editing: false,
      exporting: "character",
      isAuthorMode: true,
      partitioning: true,
      saving: true,
      onCloseCharacterMenu,
      onDeleteCharacter: vi.fn(),
      onDemoteSelectedCharacter,
      onExportCharacter: vi.fn(),
      onFindEvidence: vi.fn(),
      onManualMerge: vi.fn(),
      onOpenDuplicateReview: vi.fn(),
      onOpenReviewQueue: vi.fn(),
      onPartitionCharacter: vi.fn(),
      onSetEditing: vi.fn(),
      onToggleProtectedFromRepair,
    })

    expect(actions.map((action) => action.label)).toContain("Remove repair protection")
    expect(actions.map((action) => action.label)).toContain("Moving to review...")
    expect(actions.map((action) => action.label)).toContain("Splitting character...")
    expect(actions.map((action) => action.label)).toContain("Exporting character...")
    expect(actions.map((action) => action.label)).toContain("Deleting...")
    expect(actions.find((action) => action.label === "Moving to review...")?.disabled).toBe(true)
    expect(actions.find((action) => action.label === "Splitting character...")?.disabled).toBe(true)
    expect(actions.find((action) => action.label === "Exporting character...")?.disabled).toBe(true)
    expect(actions.find((action) => action.label === "Deleting...")?.disabled).toBe(true)

    actions.find((action) => action.label === "Remove repair protection")?.onClick()
    expect(onToggleProtectedFromRepair).toHaveBeenCalledTimes(1)
    expect(onCloseCharacterMenu).toHaveBeenCalledTimes(1)
  })

  it("returns no character menu actions when no character is selected", () => {
    expect(buildCharacterMenuActions({
      character: null,
      deleting: false,
      editing: false,
      exporting: null,
      isAuthorMode: true,
      partitioning: false,
      saving: false,
      onCloseCharacterMenu: vi.fn(),
      onDeleteCharacter: vi.fn(),
      onDemoteSelectedCharacter: vi.fn(),
      onExportCharacter: vi.fn(),
      onFindEvidence: vi.fn(),
      onManualMerge: vi.fn(),
      onOpenDuplicateReview: vi.fn(),
      onOpenReviewQueue: vi.fn(),
      onPartitionCharacter: vi.fn(),
      onSetEditing: vi.fn(),
      onToggleProtectedFromRepair: vi.fn(),
    })).toEqual([])
  })

  it("does not offer a removable repair-protection action for reviewed characters", () => {
    const onToggleProtectedFromRepair = vi.fn()
    const actions = buildCharacterMenuActions({
      character: character({ analysis_metadata: { user_reviewed: true } }),
      deleting: false,
      editing: false,
      exporting: null,
      isAuthorMode: true,
      partitioning: false,
      saving: false,
      onCloseCharacterMenu: vi.fn(),
      onDeleteCharacter: vi.fn(),
      onDemoteSelectedCharacter: vi.fn(),
      onExportCharacter: vi.fn(),
      onFindEvidence: vi.fn(),
      onManualMerge: vi.fn(),
      onOpenDuplicateReview: vi.fn(),
      onOpenReviewQueue: vi.fn(),
      onPartitionCharacter: vi.fn(),
      onSetEditing: vi.fn(),
      onToggleProtectedFromRepair,
    })

    const action = actions.find((item) => item.label === "Protected by review or manual edits")
    expect(action?.disabled).toBe(true)
    expect(onToggleProtectedFromRepair).not.toHaveBeenCalled()
  })
})
