import type { Dispatch, SetStateAction } from "react"

import type { SidebarTab } from "@/components/reader/CharacterProfileRightRail"
import type { CharacterProfileTab } from "@/components/reader/CharacterProfileTabs"
import type { Character, CharacterCandidate, CharacterRelationshipCandidate } from "@/types/character"
import { buildCreateDraft, type MergeSuggestion } from "./charactersPage.helpers"
import type { CharactersPageLayoutProps } from "./charactersPage.layout"

type WorkspaceMode = "profile" | "review" | "duplicates" | "repair"
type MaybePromise = void | Promise<unknown>

type CharacterLayoutActions = Pick<
  CharactersPageLayoutProps,
  | "onAcceptRelationshipCandidate"
  | "onApplyRepairPlan"
  | "onApproveCharacter"
  | "onAttachCandidate"
  | "onAttachRelationshipCandidate"
  | "onBack"
  | "onCancelCreate"
  | "onClearManualMerge"
  | "onCompareEvidence"
  | "onCreateCharacter"
  | "onCreateRelationship"
  | "onDemoteSelectedCharacter"
  | "onDismissDuplicateSuggestion"
  | "onDuplicateReview"
  | "onFindCandidateEvidence"
  | "onGraphVisibilityOverride"
  | "onManualMerge"
  | "onMarkCandidatePlace"
  | "onMergeCharacters"
  | "onOpenCreateCharacter"
  | "onOpenEvidence"
  | "onOpenRelationships"
  | "onOpenRepairWorkspace"
  | "onOpenReviewQueue"
  | "onPartitionCharacter"
  | "onPromoteCandidate"
  | "onRefreshEvidence"
  | "onRefreshRepairPreview"
  | "onRejectCandidate"
  | "onRejectCharacter"
  | "onRejectRelationshipCandidate"
  | "onRepairRelationships"
  | "onResetCreate"
  | "onResolveRelationshipCandidate"
  | "onReviewDataIntent"
  | "onSaveCharacter"
  | "onSaveCharacterNote"
  | "onSaveReviewNote"
  | "onSelectCharacter"
  | "onShareCharacter"
  | "onStartManualMerge"
  | "onToggleCharacterMenu"
  | "onTogglePageMenu"
  | "onToggleProtectedFromRepair"
  | "onUndoIdentityAction"
>

type UseCharacterLayoutActionsOptions = {
  dismissDuplicateSuggestion: (suggestion: MergeSuggestion) => MaybePromise
  handleAcceptRelationshipCandidate: (candidate: CharacterRelationshipCandidate) => MaybePromise
  handleApplyCharacterReprocess: () => MaybePromise
  handleApproveCharacter: () => MaybePromise
  handleAttachCandidate: (candidate: CharacterCandidate) => MaybePromise
  handleAttachRelationshipCandidate: (candidate: CharacterRelationshipCandidate, side: "a" | "b") => MaybePromise
  handleCreateCharacter: () => MaybePromise
  handleCreateRelationship: () => MaybePromise
  handleDemoteSelectedCharacter: () => MaybePromise
  handleGraphVisibilityOverride: (value: "include" | "exclude" | null) => MaybePromise
  handleMarkCandidatePlace: (candidate: CharacterCandidate) => MaybePromise
  handleMergeCharacters: (primaryId: string, secondaryId: string, suggestionId?: string) => MaybePromise
  handlePartitionCharacter: () => MaybePromise
  handlePromoteCandidate: (candidate: CharacterCandidate) => MaybePromise
  handleRejectCandidate: (candidate: CharacterCandidate) => MaybePromise
  handleRejectCharacter: () => MaybePromise
  handleRejectRelationshipCandidate: (candidate: CharacterRelationshipCandidate) => MaybePromise
  handleRepairRelationships: () => MaybePromise
  handleResolveRelationshipCandidate: (candidate: CharacterRelationshipCandidate) => MaybePromise
  handleSaveCharacter: () => MaybePromise
  handleSaveReviewNote: () => MaybePromise
  handleShareCharacter: () => MaybePromise
  handleToggleProtectedFromRepair: () => MaybePromise
  handleUndoIdentityAction: (actionId: string) => MaybePromise
  loadCandidateEvidence: (candidate: CharacterCandidate) => MaybePromise
  loadCharacterEvidence: (character: Character, force?: boolean) => MaybePromise
  openCharacterEvidence: () => void
  openCreateCharacter: () => void
  openDuplicateReview: (characterId?: string) => void
  openManualMerge: (primaryId?: string, secondaryId?: string) => void
  openRelationships: () => void
  openRepairWorkspace: () => void
  openReviewQueue: () => void
  progressChapter: number
  refetchRepairPreview: () => MaybePromise
  onBack: () => void
  saveCharacterWorkspaceNote: () => MaybePromise
  setActionError: Dispatch<SetStateAction<string | null>>
  setActiveTab: Dispatch<SetStateAction<CharacterProfileTab>>
  setCharacterMenuOpen: Dispatch<SetStateAction<boolean>>
  setCreateDraft: Dispatch<SetStateAction<ReturnType<typeof buildCreateDraft>>>
  setCreating: Dispatch<SetStateAction<boolean>>
  setEditing: Dispatch<SetStateAction<boolean>>
  setManualMergePrimaryId: Dispatch<SetStateAction<string>>
  setManualMergeSecondaryId: Dispatch<SetStateAction<string>>
  setPageMenuOpen: Dispatch<SetStateAction<boolean>>
  setReviewDataEnabled: Dispatch<SetStateAction<boolean>>
  setSelectedId: Dispatch<SetStateAction<string>>
  setSidebarTab: Dispatch<SetStateAction<SidebarTab>>
  setWorkspaceMode: Dispatch<SetStateAction<WorkspaceMode>>
}

export function useCharacterLayoutActions({
  dismissDuplicateSuggestion,
  handleAcceptRelationshipCandidate,
  handleApplyCharacterReprocess,
  handleApproveCharacter,
  handleAttachCandidate,
  handleAttachRelationshipCandidate,
  handleCreateCharacter,
  handleCreateRelationship,
  handleDemoteSelectedCharacter,
  handleGraphVisibilityOverride,
  handleMarkCandidatePlace,
  handleMergeCharacters,
  handlePartitionCharacter,
  handlePromoteCandidate,
  handleRejectCandidate,
  handleRejectCharacter,
  handleRejectRelationshipCandidate,
  handleRepairRelationships,
  handleResolveRelationshipCandidate,
  handleSaveCharacter,
  handleSaveReviewNote,
  handleShareCharacter,
  handleToggleProtectedFromRepair,
  handleUndoIdentityAction,
  loadCandidateEvidence,
  loadCharacterEvidence,
  openCharacterEvidence,
  openCreateCharacter,
  openDuplicateReview,
  openManualMerge,
  openRelationships,
  openRepairWorkspace,
  openReviewQueue,
  progressChapter,
  refetchRepairPreview,
  onBack,
  saveCharacterWorkspaceNote,
  setActionError,
  setActiveTab,
  setCharacterMenuOpen,
  setCreateDraft,
  setCreating,
  setEditing,
  setManualMergePrimaryId,
  setManualMergeSecondaryId,
  setPageMenuOpen,
  setReviewDataEnabled,
  setSelectedId,
  setSidebarTab,
  setWorkspaceMode,
}: UseCharacterLayoutActionsOptions): CharacterLayoutActions {
  return {
    onAcceptRelationshipCandidate: (candidate) => void handleAcceptRelationshipCandidate(candidate),
    onApplyRepairPlan: () => void handleApplyCharacterReprocess(),
    onApproveCharacter: () => void handleApproveCharacter(),
    onAttachCandidate: (candidate) => void handleAttachCandidate(candidate),
    onAttachRelationshipCandidate: (candidate, side) => void handleAttachRelationshipCandidate(candidate, side),
    onBack,
    onCancelCreate: () => {
      setCreating(false)
      setCreateDraft(buildCreateDraft(progressChapter))
      setActionError(null)
    },
    onClearManualMerge: () => {
      setManualMergePrimaryId("")
      setManualMergeSecondaryId("")
    },
    onCompareEvidence: (characterId) => {
      setWorkspaceMode("profile")
      setSelectedId(characterId)
      setActiveTab("evidence")
      setSidebarTab("evidence")
    },
    onCreateCharacter: () => void handleCreateCharacter(),
    onCreateRelationship: () => void handleCreateRelationship(),
    onDemoteSelectedCharacter: () => void handleDemoteSelectedCharacter(),
    onDismissDuplicateSuggestion: (suggestion) => void dismissDuplicateSuggestion(suggestion),
    onDuplicateReview: (characterId) => openDuplicateReview(characterId),
    onFindCandidateEvidence: (candidate) => void loadCandidateEvidence(candidate),
    onGraphVisibilityOverride: (value) => void handleGraphVisibilityOverride(value),
    onManualMerge: (primaryId, secondaryId) => openManualMerge(primaryId, secondaryId),
    onMarkCandidatePlace: (candidate) => void handleMarkCandidatePlace(candidate),
    onMergeCharacters: (primaryId, secondaryId, suggestionId) => void handleMergeCharacters(primaryId, secondaryId, suggestionId),
    onOpenCreateCharacter: openCreateCharacter,
    onOpenEvidence: openCharacterEvidence,
    onOpenRelationships: openRelationships,
    onOpenRepairWorkspace: openRepairWorkspace,
    onOpenReviewQueue: openReviewQueue,
    onPartitionCharacter: () => void handlePartitionCharacter(),
    onPromoteCandidate: (candidate) => void handlePromoteCandidate(candidate),
    onRefreshEvidence: (character, force) => void loadCharacterEvidence(character, force),
    onRefreshRepairPreview: () => void refetchRepairPreview(),
    onRejectCandidate: (candidate) => void handleRejectCandidate(candidate),
    onRejectCharacter: () => void handleRejectCharacter(),
    onRejectRelationshipCandidate: (candidate) => void handleRejectRelationshipCandidate(candidate),
    onRepairRelationships: () => void handleRepairRelationships(),
    onResetCreate: () => {
      setCreateDraft(buildCreateDraft(progressChapter))
      setActionError(null)
    },
    onResolveRelationshipCandidate: (candidate) => void handleResolveRelationshipCandidate(candidate),
    onReviewDataIntent: () => setReviewDataEnabled(true),
    onSaveCharacter: () => void handleSaveCharacter(),
    onSaveCharacterNote: () => void saveCharacterWorkspaceNote(),
    onSaveReviewNote: () => void handleSaveReviewNote(),
    onSelectCharacter: (characterId) => {
      setSelectedId(characterId)
      setCreating(false)
      setEditing(false)
      setWorkspaceMode("profile")
    },
    onShareCharacter: () => void handleShareCharacter(),
    onStartManualMerge: (primaryId, secondaryId) => openManualMerge(primaryId, secondaryId),
    onToggleCharacterMenu: () => setCharacterMenuOpen((current) => !current),
    onTogglePageMenu: () => setPageMenuOpen((current) => !current),
    onToggleProtectedFromRepair: () => void handleToggleProtectedFromRepair(),
    onUndoIdentityAction: (actionId) => void handleUndoIdentityAction(actionId),
  }
}
