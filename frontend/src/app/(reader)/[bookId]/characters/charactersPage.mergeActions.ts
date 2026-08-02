import { useState, type Dispatch, type SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import type { CharacterProfileTab } from "@/components/reader/CharacterProfileTabs"
import type { SidebarTab } from "@/components/reader/CharacterProfileRightRail"
import type { Character } from "@/types/character"
import type { MergeSuggestion } from "./charactersPage.helpers"

type WorkspaceMode = "profile" | "review" | "duplicates" | "repair"

type UseCharacterMergeActionsArgs = {
  bookId: string
  refreshCharacters: () => Promise<Character[]>
  refreshGraph: () => Promise<void>
  refetchCharacterReview: () => Promise<unknown>
  setActiveTab: Dispatch<SetStateAction<CharacterProfileTab>>
  setDismissedMergeKeys: Dispatch<SetStateAction<string[]>>
  setSelectedId: Dispatch<SetStateAction<string>>
  setSidebarTab: Dispatch<SetStateAction<SidebarTab>>
  setWorkspaceMode: Dispatch<SetStateAction<WorkspaceMode>>
}

export function useCharacterMergeActions({
  bookId,
  refreshCharacters,
  refreshGraph,
  refetchCharacterReview,
  setActiveTab,
  setDismissedMergeKeys,
  setSelectedId,
  setSidebarTab,
  setWorkspaceMode,
}: UseCharacterMergeActionsArgs) {
  const [mergeBusy, setMergeBusy] = useState(false)
  const [mergeError, setMergeError] = useState<string | null>(null)

  async function handleMergeCharacters(primaryId: string, secondaryId: string, suggestionId?: string) {
    if (!primaryId || !secondaryId || primaryId === secondaryId) {
      setMergeError("Choose two different characters to merge.")
      return
    }
    setMergeBusy(true)
    setMergeError(null)
    try {
      const response = suggestionId
        ? await booksApi.acceptDuplicateSuggestion(bookId, suggestionId)
        : await booksApi.mergeCharacters(bookId, { primaryId, secondaryId })
      const refreshed = await refreshCharacters()
      await refreshGraph()
      setWorkspaceMode("profile")
      setSelectedId(response.merged || refreshed[0]?.id || "")
      setActiveTab("overview")
      setSidebarTab("insights")
    } catch {
      setMergeError("Could not merge those characters.")
    } finally {
      setMergeBusy(false)
    }
  }

  async function dismissDuplicateSuggestion(suggestion: MergeSuggestion) {
    if (!suggestion.suggestionId) {
      setDismissedMergeKeys((current) => current.includes(suggestion.key) ? current : [...current, suggestion.key])
      setMergeError(null)
      return
    }
    setMergeBusy(true)
    setMergeError(null)
    try {
      await booksApi.dismissDuplicateSuggestion(bookId, suggestion.suggestionId)
      setDismissedMergeKeys((current) => current.includes(suggestion.key) ? current : [...current, suggestion.key])
      await refetchCharacterReview()
    } catch {
      setMergeError("Could not dismiss this duplicate suggestion.")
    } finally {
      setMergeBusy(false)
    }
  }

  return {
    dismissDuplicateSuggestion,
    handleMergeCharacters,
    mergeBusy,
    mergeError,
    setMergeError,
  }
}
