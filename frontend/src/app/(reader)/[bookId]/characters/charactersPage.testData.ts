import type { Character } from "@/types/character"

export function character(overrides: Partial<Character>): Character {
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
    growth_events: [],
    relationship_summaries: [],
    analysis_metadata: {},
    tags: [],
    graph_visibility_override: null,
    ...overrides,
  } as Character
}
