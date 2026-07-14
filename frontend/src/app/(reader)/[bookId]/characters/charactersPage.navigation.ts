import type { ConnectedRelationship } from "@/components/reader/CharacterProfileRightRail"
import type { Character } from "@/types/character"
import { buildSelectedCharacterSummary, formatRelationshipType, type MergeSuggestion } from "./charactersPage.helpers"

export function buildCharacterWorkspaceNoteContent(
  character: Character,
  connections: ConnectedRelationship[],
) {
  const summary = buildSelectedCharacterSummary(character, connections)
  const bodyParts = [
    summary,
    character.arc_summary ? `## Arc summary\n\n${character.arc_summary}` : "",
    character.personality_tags.length ? `## Personality tags\n\n- ${character.personality_tags.join("\n- ")}` : "",
    character.motivations.length ? `## Motivations\n\n- ${character.motivations.join("\n- ")}` : "",
    connections.length
      ? `## Key relationships\n\n${connections
          .slice(0, 4)
          .map((edge) => `- ${edge.counterpartName}: ${formatRelationshipType(edge.type)}${edge.description ? ` - ${edge.description}` : ""}`)
          .join("\n")}`
      : "",
  ].filter(Boolean)

  return bodyParts.join("\n\n")
}

export function chooseDuplicateReviewSelection(
  targetCharacterId: string | undefined,
  filteredMergeSuggestions: MergeSuggestion[],
  chars: Character[],
) {
  if (!targetCharacterId) {
    return {
      manualMergePrimaryId: "",
      manualMergeSecondaryId: "",
      selectedMergeKey: null,
    }
  }

  const preferred = filteredMergeSuggestions.find((suggestion) => (
    suggestion.primaryId === targetCharacterId || suggestion.secondaryId === targetCharacterId
  ))
  if (preferred) {
    return {
      manualMergePrimaryId: "",
      manualMergeSecondaryId: "",
      selectedMergeKey: preferred.key,
    }
  }

  return {
    manualMergePrimaryId: targetCharacterId,
    manualMergeSecondaryId: chars.find((char) => char.id !== targetCharacterId)?.id ?? "",
    selectedMergeKey: null,
  }
}

export function chooseManualMergePair({
  chars,
  primaryId,
  secondaryId,
  selectedCharacterId,
}: {
  chars: Character[]
  primaryId?: string
  secondaryId?: string
  selectedCharacterId?: string | null
}) {
  const primary = primaryId || selectedCharacterId || chars[0]?.id || ""
  const fallbackSecondary = chars.find((char) => char.id !== primary)?.id ?? ""
  return {
    manualMergePrimaryId: primary,
    manualMergeSecondaryId: secondaryId && secondaryId !== primary ? secondaryId : fallbackSecondary,
  }
}
