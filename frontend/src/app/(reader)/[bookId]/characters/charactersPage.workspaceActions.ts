import type { Dispatch, SetStateAction } from "react"

import type { SidebarTab } from "@/components/reader/CharacterProfileRightRail"
import type { CharacterProfileTab } from "@/components/reader/CharacterProfileTabs"
import type { Character } from "@/types/character"
import type { ReadingProgress } from "@/types/reader"
import { buildCreateDraft, type CreateDraft, type MergeSuggestion } from "./charactersPage.helpers"
import { chooseDuplicateReviewSelection, chooseManualMergePair } from "./charactersPage.navigation"

type WorkspaceMode = "profile" | "review" | "duplicates" | "repair"

type UseCharacterWorkspaceActionsArgs = {
  chars: Character[]
  filteredMergeSuggestions: MergeSuggestion[]
  loadCharacterEvidence: (character: Character, force?: boolean) => Promise<unknown>
  progress: ReadingProgress | null
  selectedCharacter: Character | null
  setActionError: Dispatch<SetStateAction<string | null>>
  setActiveTab: Dispatch<SetStateAction<CharacterProfileTab>>
  setCastFilter: Dispatch<SetStateAction<"all" | "main" | "minor" | "needs-review" | "duplicates">>
  setCharacterMenuOpen: Dispatch<SetStateAction<boolean>>
  setCreateDraft: Dispatch<SetStateAction<CreateDraft>>
  setCreating: Dispatch<SetStateAction<boolean>>
  setDismissedMergeKeys: Dispatch<SetStateAction<string[]>>
  setEditing: Dispatch<SetStateAction<boolean>>
  setManualMergePrimaryId: Dispatch<SetStateAction<string>>
  setManualMergeSecondaryId: Dispatch<SetStateAction<string>>
  setMergeError: Dispatch<SetStateAction<string | null>>
  setPageMenuOpen: Dispatch<SetStateAction<boolean>>
  setReviewDataEnabled: Dispatch<SetStateAction<boolean>>
  setSearch: Dispatch<SetStateAction<string>>
  setSelectedMergeKey: Dispatch<SetStateAction<string>>
  setSidebarTab: Dispatch<SetStateAction<SidebarTab>>
  setWorkspaceMode: Dispatch<SetStateAction<WorkspaceMode>>
}

export function useCharacterWorkspaceActions({
  chars,
  filteredMergeSuggestions,
  loadCharacterEvidence,
  progress,
  selectedCharacter,
  setActionError,
  setActiveTab,
  setCastFilter,
  setCharacterMenuOpen,
  setCreateDraft,
  setCreating,
  setDismissedMergeKeys,
  setEditing,
  setManualMergePrimaryId,
  setManualMergeSecondaryId,
  setMergeError,
  setPageMenuOpen,
  setReviewDataEnabled,
  setSearch,
  setSelectedMergeKey,
  setSidebarTab,
  setWorkspaceMode,
}: UseCharacterWorkspaceActionsArgs) {
  function openCreateCharacter() {
    setWorkspaceMode("profile")
    setCreating(true)
    setEditing(false)
    setActiveTab("overview")
    setSidebarTab("insights")
    setCharacterMenuOpen(false)
    setPageMenuOpen(false)
    setActionError(null)
    setCreateDraft(buildCreateDraft(progress?.current_chapter ?? 1))
  }

  function openCharacterEvidence() {
    if (!selectedCharacter) return
    setWorkspaceMode("profile")
    setActiveTab("evidence")
    setSidebarTab("evidence")
    void loadCharacterEvidence(selectedCharacter)
  }

  function openRelationships() {
    setWorkspaceMode("profile")
    setActiveTab("relationships")
  }

  function openReviewQueue() {
    setCreating(false)
    setReviewDataEnabled(true)
    setWorkspaceMode("review")
    setPageMenuOpen(false)
  }

  function openDuplicateReview(targetCharacterId?: string) {
    setCreating(false)
    setReviewDataEnabled(true)
    setWorkspaceMode("duplicates")
    setManualMergePrimaryId("")
    setManualMergeSecondaryId("")
    if (targetCharacterId) {
      const selection = chooseDuplicateReviewSelection(targetCharacterId, filteredMergeSuggestions, chars)
      if (selection.selectedMergeKey) {
        setSelectedMergeKey(selection.selectedMergeKey)
        return
      }
      setManualMergePrimaryId(selection.manualMergePrimaryId)
      setManualMergeSecondaryId(selection.manualMergeSecondaryId)
    }
  }

  function openManualMerge(primaryId?: string, secondaryId?: string) {
    setCreating(false)
    const selection = chooseManualMergePair({
      chars,
      primaryId,
      secondaryId,
      selectedCharacterId: selectedCharacter?.id,
    })
    setWorkspaceMode("duplicates")
    setManualMergePrimaryId(selection.manualMergePrimaryId)
    setManualMergeSecondaryId(selection.manualMergeSecondaryId)
    setSelectedMergeKey("")
  }

  function openRepairWorkspace() {
    setCreating(false)
    setWorkspaceMode("repair")
    setPageMenuOpen(false)
  }

  function resetFilters() {
    setSearch("")
    setCastFilter("all")
    setWorkspaceMode("profile")
    setPageMenuOpen(false)
  }

  function dismissMergeSuggestion(key: string) {
    setDismissedMergeKeys((current) => current.includes(key) ? current : [...current, key])
    setMergeError(null)
  }

  return {
    dismissMergeSuggestion,
    openCharacterEvidence,
    openCreateCharacter,
    openDuplicateReview,
    openManualMerge,
    openRelationships,
    openRepairWorkspace,
    openReviewQueue,
    resetFilters,
  }
}
