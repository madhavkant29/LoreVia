import { startTransition, useEffect, type Dispatch, type SetStateAction } from "react"

import type { Book } from "@/types/book"
import type { Character, RelationshipGraph as RelationshipGraphData } from "@/types/character"
import type { ReadingProgress } from "@/types/reader"
import type { CharacterProfileTab } from "@/components/reader/CharacterProfileTabs"
import { buildDraft, buildRelationshipDraft, type EditDraft, type RelationshipComposerDraft } from "./charactersPage.helpers"
import { scheduleIdleWork } from "./charactersPage.scheduling"

type WorkspaceMode = "profile" | "review" | "duplicates" | "repair"

type UseCharacterPageSyncEffectsArgs = {
  activeTab: CharacterProfileTab
  bookData: Book | null
  charactersData: Character[]
  charactersLoading: boolean
  charsLength: number
  chars: Character[]
  editing: boolean
  filteredChars: Character[]
  filteredMergeSuggestions: Array<{ key: string }>
  manualMergePrimaryId: string
  manualMergeSecondaryId: string
  progressData: ReadingProgress | null
  relationshipGraphData: RelationshipGraphData | null
  relationshipChapter: number
  relationshipsEnabled: boolean
  reviewDataEnabled: boolean
  selectedCharacter: Character | null
  selectedId: string
  selectedMergeKey: string
  workspaceMode: WorkspaceMode
  setActionError: Dispatch<SetStateAction<string | null>>
  setBook: Dispatch<SetStateAction<Book | null>>
  setCharacterMenuOpen: Dispatch<SetStateAction<boolean>>
  setChars: Dispatch<SetStateAction<Character[]>>
  setDraft: Dispatch<SetStateAction<EditDraft>>
  setGraphData: Dispatch<SetStateAction<RelationshipGraphData | null>>
  setManualMergePrimaryId: Dispatch<SetStateAction<string>>
  setManualMergeSecondaryId: Dispatch<SetStateAction<string>>
  setPageMenuOpen: Dispatch<SetStateAction<boolean>>
  setProgress: Dispatch<SetStateAction<ReadingProgress | null>>
  setRelationshipsEnabled: Dispatch<SetStateAction<boolean>>
  setRelationshipDraft: Dispatch<SetStateAction<RelationshipComposerDraft>>
  setReviewNoteDraft: Dispatch<SetStateAction<string>>
  setReviewDataEnabled: Dispatch<SetStateAction<boolean>>
  setSelectedId: Dispatch<SetStateAction<string>>
  setSelectedMergeKey: Dispatch<SetStateAction<string>>
}

export function useCharacterPageSyncEffects({
  activeTab,
  bookData,
  charactersData,
  charactersLoading,
  charsLength,
  chars,
  editing,
  filteredChars,
  filteredMergeSuggestions,
  manualMergePrimaryId,
  manualMergeSecondaryId,
  progressData,
  relationshipGraphData,
  relationshipChapter,
  relationshipsEnabled,
  reviewDataEnabled,
  selectedCharacter,
  selectedId,
  selectedMergeKey,
  workspaceMode,
  setBook,
  setCharacterMenuOpen,
  setChars,
  setDraft,
  setGraphData,
  setManualMergePrimaryId,
  setManualMergeSecondaryId,
  setPageMenuOpen,
  setProgress,
  setRelationshipsEnabled,
  setRelationshipDraft,
  setReviewNoteDraft,
  setReviewDataEnabled,
  setSelectedId,
  setSelectedMergeKey,
}: UseCharacterPageSyncEffectsArgs) {
  useEffect(() => {
    setBook(bookData)
  }, [bookData, setBook])

  useEffect(() => {
    setChars(charactersData)
    setSelectedId((current) => current || charactersData[0]?.id || "")
  }, [charactersData, setChars, setSelectedId])

  useEffect(() => {
    setProgress(progressData)
  }, [progressData, setProgress])

  useEffect(() => {
    if (reviewDataEnabled || (!charactersLoading && charsLength === 0) || workspaceMode === "review" || workspaceMode === "duplicates") {
      setReviewDataEnabled(true)
      return
    }

    return scheduleIdleWork(() => {
      startTransition(() => setReviewDataEnabled(true))
    }, 220)
  }, [charactersLoading, charsLength, reviewDataEnabled, setReviewDataEnabled, workspaceMode])

  useEffect(() => {
    if (relationshipsEnabled || activeTab === "relationships") {
      setRelationshipsEnabled(true)
      return
    }

    return scheduleIdleWork(() => {
      startTransition(() => setRelationshipsEnabled(true))
    }, 180)
  }, [activeTab, relationshipsEnabled, setRelationshipsEnabled])

  useEffect(() => {
    setGraphData(relationshipGraphData)
  }, [relationshipGraphData, setGraphData])

  useEffect(() => {
    if (chars.some((char) => char.id === selectedId)) return
    if (filteredChars.length === 0) {
      setSelectedId("")
      return
    }
    if (filteredChars.some((char) => char.id === selectedId)) return
    setSelectedId(filteredChars[0].id)
  }, [chars, filteredChars, selectedId, setSelectedId])

  useEffect(() => {
    if (filteredMergeSuggestions.length === 0) {
      setSelectedMergeKey("")
      return
    }
    if (filteredMergeSuggestions.some((suggestion) => suggestion.key === selectedMergeKey)) return
    setSelectedMergeKey(filteredMergeSuggestions[0].key)
  }, [filteredMergeSuggestions, selectedMergeKey, setSelectedMergeKey])

  useEffect(() => {
    if (!editing) {
      setDraft(buildDraft(selectedCharacter))
    }
  }, [editing, selectedCharacter, setDraft])

  useEffect(() => {
    setReviewNoteDraft(selectedCharacter?.analysis_metadata?.review_note ?? "")
  }, [selectedCharacter?.id, selectedCharacter?.analysis_metadata?.review_note, setReviewNoteDraft])

  useEffect(() => {
    const fallbackCounterpart = chars.find((char) => char.id !== selectedCharacter?.id)?.id ?? ""
    setRelationshipDraft(buildRelationshipDraft(relationshipChapter, fallbackCounterpart))
  }, [chars, relationshipChapter, selectedCharacter?.id, setRelationshipDraft])

  useEffect(() => {
    setCharacterMenuOpen(false)
    setPageMenuOpen(false)
  }, [selectedId, selectedMergeKey, workspaceMode, setCharacterMenuOpen, setPageMenuOpen])

  useEffect(() => {
    if (workspaceMode !== "duplicates" || !manualMergePrimaryId) return
    if (!chars.some((char) => char.id === manualMergePrimaryId)) {
      setManualMergePrimaryId("")
    }
  }, [chars, manualMergePrimaryId, setManualMergePrimaryId, workspaceMode])

  useEffect(() => {
    if (workspaceMode !== "duplicates" || !manualMergeSecondaryId) return
    if (!chars.some((char) => char.id === manualMergeSecondaryId)) {
      setManualMergeSecondaryId("")
    }
  }, [chars, manualMergeSecondaryId, setManualMergeSecondaryId, workspaceMode])
}
