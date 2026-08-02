import type { Dispatch, SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import type { Character } from "@/types/character"
import {
  buildManuscriptCharacterCardDraft,
  type ManuscriptCharacterCardDraft,
} from "./manuscriptPage.helpers"

type RightPane = "context" | "advisor" | "notes" | "arcs" | "insights" | "character"

type UseManuscriptCharacterCardActionsArgs = {
  bookId: string
  charCardDraft: ManuscriptCharacterCardDraft
  selectedCharCard: Character | null
  openRightPane: (pane: RightPane) => void
  setCharCardDraft: Dispatch<SetStateAction<ManuscriptCharacterCardDraft>>
  setCharCardEditing: Dispatch<SetStateAction<boolean>>
  setCharCardSaving: Dispatch<SetStateAction<boolean>>
  setCharacters: Dispatch<SetStateAction<Character[]>>
  setSelectedCharCard: Dispatch<SetStateAction<Character | null>>
  setStatusMessage: Dispatch<SetStateAction<string | null>>
}

export function useManuscriptCharacterCardActions({
  bookId,
  charCardDraft,
  openRightPane,
  selectedCharCard,
  setCharCardDraft,
  setCharCardEditing,
  setCharCardSaving,
  setCharacters,
  setSelectedCharCard,
  setStatusMessage,
}: UseManuscriptCharacterCardActionsArgs) {
  function openCharCard(char: Character) {
    setSelectedCharCard(char)
    setCharCardEditing(false)
    setCharCardDraft(buildManuscriptCharacterCardDraft(char))
    openRightPane("character")
  }

  async function saveCharCard() {
    if (!selectedCharCard) return
    setCharCardSaving(true)
    try {
      const updated = await booksApi.updateCharacter(bookId, selectedCharCard.id, {
        arcSummary: charCardDraft.arcSummary.trim() || null,
        description: charCardDraft.description.trim() || null,
        personalityTags: charCardDraft.personalityTags.split(",").map((tag) => tag.trim()).filter(Boolean),
        motivations: charCardDraft.motivations.split(",").map((motivation) => motivation.trim()).filter(Boolean),
        fears: charCardDraft.fears.split(",").map((fear) => fear.trim()).filter(Boolean),
      })
      setSelectedCharCard(updated)
      setCharacters((current) => current.map((character) => character.id === updated.id ? updated : character))
      setCharCardEditing(false)
      setStatusMessage(`Character card for ${updated.name} saved.`)
    } finally {
      setCharCardSaving(false)
    }
  }

  return {
    openCharCard,
    saveCharCard,
  }
}
