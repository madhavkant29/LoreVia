import { describe, expect, it } from "vitest"

import type { Character } from "@/types/character"
import {
  buildCharacterBibleExportFilename,
  buildCharacterCardExportFilename,
  buildCharacterCreatePayload,
  buildCharacterUpdatePayload,
  buildPartitionTargetSuggestion,
  buildRelationshipCreatePayload,
} from "./charactersPage.mutationPayloads"
import type { CreateDraft, EditDraft, RelationshipComposerDraft } from "./charactersPage.helpers"

const editDraft: EditDraft = {
  name: " Mira ",
  aliases: "Captain, The Pilot",
  description: "  Leads the crew. ",
  goal: " Find the gate ",
  lieTheyBelieve: " Alone is safer ",
  backstoryWound: "",
  arcType: " redemption ",
  arcSummary: " Learns trust ",
  personalityTags: "precise, guarded",
  motivations: "archive, crew",
  fears: "failure",
}

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

describe("characters page mutation payload helpers", () => {
  it("normalizes character update payloads", () => {
    expect(buildCharacterUpdatePayload(editDraft)).toEqual({
      name: "Mira",
      aliases: ["Captain", "The Pilot"],
      description: "Leads the crew.",
      goal: "Find the gate",
      lieTheyBelieve: "Alone is safer",
      backstoryWound: null,
      arcType: "redemption",
      arcSummary: "Learns trust",
      personalityTags: ["precise", "guarded"],
      motivations: ["archive", "crew"],
      fears: ["failure"],
    })
  })

  it("normalizes create payloads with role and fallback chapter", () => {
    const payload = buildCharacterCreatePayload({
      ...editDraft,
      role: "",
      firstChapter: "not a number",
    } satisfies CreateDraft, 9)

    expect(payload.firstChapter).toBe(9)
    expect(payload.role).toBeNull()
  })

  it("normalizes relationship payload chapter and sentiment values", () => {
    const draft: RelationshipComposerDraft = {
      counterpartId: "character-2",
      relType: "ally",
      sentiment: "",
      description: "  Trusts her. ",
      fromChapter: "",
      toChapter: "12",
    }

    expect(buildRelationshipCreatePayload("character-1", draft, 3)).toEqual({
      characterAId: "character-1",
      characterBId: "character-2",
      relType: "ally",
      description: "Trusts her.",
      sentiment: null,
      fromChapter: 3,
      toChapter: 12,
    })
  })

  it("builds stable export filenames and partition suggestions", () => {
    expect(buildCharacterCardExportFilename("The Long Road", "Mira Vale", "pdf")).toBe("the-long-road-mira-vale-character-card.pdf")
    expect(buildCharacterBibleExportFilename("", "md")).toBe("lorevia-character-bible.md")
    expect(buildPartitionTargetSuggestion(character({ aliases: ["Mira", "Captain", "Pilot", "Vale", "Extra"] }))).toBe("Mira\nCaptain\nPilot\nVale")
    expect(buildPartitionTargetSuggestion(character({ name: "Mira", aliases: ["Captain"] }))).toBe("Mira\nCaptain")
  })
})
