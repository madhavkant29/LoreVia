import { describe, expect, it } from "vitest"

import type { ConnectedRelationship } from "@/components/reader/CharacterProfileRightRail"
import type { Character } from "@/types/character"
import type { MergeSuggestion } from "./charactersPage.helpers"
import { buildCharacterWorkspaceNoteContent, chooseDuplicateReviewSelection, chooseManualMergePair } from "./charactersPage.navigation"

function character(overrides: Partial<Character> = {}): Character {
  return {
    id: "character-1",
    book_id: "book-1",
    name: "Mira",
    aliases: [],
    role: "mc",
    first_chapter: 1,
    last_seen_chapter: 4,
    mention_count: 12,
    status: "alive",
    trait_state: {},
    description: "A careful pilot.",
    personality_tags: [],
    motivations: [],
    fears: [],
    archetype: null,
    arc_summary: null,
    analysis_metadata: {},
    ...overrides,
  }
}

function relationship(overrides: Partial<ConnectedRelationship> = {}): ConnectedRelationship {
  return {
    source: "character-1",
    target: "character-2",
    type: "ally",
    sentiment: 1,
    description: "Trusts her with the map.",
    counterpartId: "character-2",
    counterpartName: "Jon",
    ...overrides,
  }
}

function mergeSuggestion(overrides: Partial<MergeSuggestion> = {}): MergeSuggestion {
  return {
    key: "merge-1",
    primaryId: "character-1",
    secondaryId: "character-2",
    confidence: 92,
    reasons: [],
    sharedClusterKeys: [],
    sharedChapters: [],
    primaryIsProtected: false,
    secondaryIsProtected: false,
    primaryIsCurated: false,
    secondaryIsCurated: false,
    ...overrides,
  }
}

describe("charactersPage navigation helpers", () => {
  it("builds character workspace note content from profile fields and relationships", () => {
    const content = buildCharacterWorkspaceNoteContent(
      character({
        arc_summary: "Learns to trust the crew.",
        personality_tags: ["precise", "guarded"],
        motivations: ["protect the archive"],
      }),
      [relationship()],
    )

    expect(content).toContain("A careful pilot.")
    expect(content).toContain("## Arc summary\n\nLearns to trust the crew.")
    expect(content).toContain("## Personality tags\n\n- precise\n- guarded")
    expect(content).toContain("## Motivations\n\n- protect the archive")
    expect(content).toContain("- Jon: Ally - Trusts her with the map.")
  })

  it("prefers an existing duplicate suggestion for the target character", () => {
    expect(chooseDuplicateReviewSelection(
      "character-2",
      [mergeSuggestion()],
      [character({ id: "character-1" }), character({ id: "character-2" })],
    )).toEqual({
      manualMergePrimaryId: "",
      manualMergeSecondaryId: "",
      selectedMergeKey: "merge-1",
    })
  })

  it("falls back to a manual duplicate pair when no suggestion matches", () => {
    expect(chooseDuplicateReviewSelection(
      "character-3",
      [mergeSuggestion()],
      [character({ id: "character-1" }), character({ id: "character-3" })],
    )).toEqual({
      manualMergePrimaryId: "character-3",
      manualMergeSecondaryId: "character-1",
      selectedMergeKey: null,
    })
  })

  it("chooses a valid manual merge secondary distinct from the primary", () => {
    expect(chooseManualMergePair({
      chars: [character({ id: "character-1" }), character({ id: "character-2" })],
      primaryId: "character-1",
      secondaryId: "character-1",
      selectedCharacterId: null,
    })).toEqual({
      manualMergePrimaryId: "character-1",
      manualMergeSecondaryId: "character-2",
    })
  })
})
