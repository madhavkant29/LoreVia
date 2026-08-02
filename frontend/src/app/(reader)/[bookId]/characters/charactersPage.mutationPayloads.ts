import type { Character } from "@/types/character"
import {
  parsePositiveInteger,
  slugify,
  stringToList,
  type CreateDraft,
  type EditDraft,
  type RelationshipComposerDraft,
} from "./charactersPage.helpers"

export function buildCharacterUpdatePayload(draft: EditDraft) {
  return {
    name: draft.name.trim(),
    aliases: stringToList(draft.aliases),
    description: draft.description.trim() || null,
    goal: draft.goal.trim() || null,
    lieTheyBelieve: draft.lieTheyBelieve.trim() || null,
    backstoryWound: draft.backstoryWound.trim() || null,
    arcType: draft.arcType.trim() || null,
    arcSummary: draft.arcSummary.trim() || null,
    personalityTags: stringToList(draft.personalityTags),
    motivations: stringToList(draft.motivations),
    fears: stringToList(draft.fears),
  }
}

export function buildCharacterCreatePayload(draft: CreateDraft, fallbackChapter: number) {
  return {
    ...buildCharacterUpdatePayload(draft),
    firstChapter: parsePositiveInteger(draft.firstChapter, fallbackChapter),
    role: draft.role || null,
  }
}

export function buildRelationshipCreatePayload(
  selectedCharacterId: string,
  draft: RelationshipComposerDraft,
  fallbackChapter: number,
) {
  return {
    characterAId: selectedCharacterId,
    characterBId: draft.counterpartId,
    relType: draft.relType,
    description: draft.description.trim() || null,
    sentiment: draft.sentiment === "" ? null : Number(draft.sentiment),
    fromChapter: parsePositiveInteger(draft.fromChapter, fallbackChapter),
    toChapter: draft.toChapter === "" ? null : parsePositiveInteger(draft.toChapter, fallbackChapter),
  }
}

export function buildCharacterCardExportFilename(bookTitle: string | null | undefined, characterName: string, format: string) {
  const bookBase = slugify(bookTitle ?? "lorevia") || "lorevia"
  const characterBase = slugify(characterName) || "character"
  return `${bookBase}-${characterBase}-character-card.${format}`
}

export function buildCharacterBibleExportFilename(bookTitle: string | null | undefined, format: string) {
  return `${slugify(bookTitle ?? "lorevia") || "lorevia"}-character-bible.${format}`
}

export function buildPartitionTargetSuggestion(character: Character) {
  return character.aliases.length >= 2
    ? character.aliases.slice(0, 4).join("\n")
    : [character.name, ...character.aliases].filter(Boolean).join("\n")
}
