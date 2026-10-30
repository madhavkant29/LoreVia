import { describe, expect, it } from "vitest"
import type { Character } from "@/types/character"
import { characterMentionCountKind, characterMentionCountLabel } from "./charactersPage.mentionLabels"

const character = {
  id: "mara",
  book_id: "book",
  name: "Mara Vale",
  aliases: [],
  role: null,
  first_chapter: 1,
  trait_state: {},
  description: null,
  personality_tags: [],
  motivations: [],
  fears: [],
  archetype: null,
  arc_summary: null,
} as Character

describe("character mention labels", () => {
  it("labels verified source positions as named mentions", () => {
    const verified = {
      ...character,
      mention_count: 2,
      analysis_metadata: { mention_count_basis: "source_positions" as const },
    }
    expect(characterMentionCountLabel(verified)).toBe("2 named mentions")
    expect(characterMentionCountKind(verified)).toBe("Named mentions")
  })

  it("labels legacy or missing counts as estimates", () => {
    expect(characterMentionCountLabel({ ...character, mention_count: 1 })).toBe("1 estimated mention")
    expect(characterMentionCountLabel(character)).toBe("0 estimated mentions")
    expect(characterMentionCountKind(character)).toBe("Mention estimate")
  })
})
