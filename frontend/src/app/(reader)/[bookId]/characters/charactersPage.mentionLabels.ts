import type { Character } from "@/types/character"

export function characterMentionCountLabel(character: Character): string {
  const count = character.mention_count ?? 0
  return character.analysis_metadata?.mention_count_basis === "source_positions"
    ? `${count} named ${count === 1 ? "mention" : "mentions"}`
    : `${count} estimated ${count === 1 ? "mention" : "mentions"}`
}

export function characterMentionCountKind(character: Character): string {
  return character.analysis_metadata?.mention_count_basis === "source_positions"
    ? "Named mentions"
    : "Mention estimate"
}
