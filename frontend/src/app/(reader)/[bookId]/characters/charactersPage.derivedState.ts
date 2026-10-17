import { useDeferredValue, useMemo } from "react"

import type { Character, CharacterRepairPreview, CharacterReviewResponse, RelationshipGraph as RelationshipGraphData } from "@/types/character"
import type { SearchResult } from "@/types/reader"
import {
  buildCharacterFlagsById,
  buildCharacterHealthById,
  buildCharacterLookup,
  buildConnectionsByCharacter,
  buildDashboardStats,
  buildMergeSuggestionIds,
  buildMergeSuggestions,
  buildRelationshipCounts,
  buildSelectedCharacterSummary,
  buildShadowCharacters,
  characterLabelForId,
  filterCharacters,
  filterMergeSuggestions,
  filterPendingCharacterCandidates,
  filterPendingRelationshipCandidates,
  getPendingCharacterCandidates,
  getPendingRelationshipCandidates,
  knownFacts,
  openQuestionsForCharacter,
  reviewStatusLabel,
  sortedMergeableCharacters,
  sortedRelationshipCounterpartOptions,
  sortGrowthEvents,
  visibleTraitEntries,
  type MergeSuggestion,
} from "./charactersPage.helpers"

type EvidenceCacheEntry = {
  chapter: number
  results: SearchResult[]
}

type UseCharacterPageDerivedStateArgs = {
  castFilter: "all" | "main" | "minor" | "needs-review" | "duplicates"
  chars: Character[]
  dismissedMergeKeys: string[]
  evidenceCache: Record<string, EvidenceCacheEntry>
  graphData: RelationshipGraphData | null
  manualMergePrimaryId: string
  manualMergeSecondaryId: string
  repairPreview: CharacterRepairPreview
  reviewData: CharacterReviewResponse
  roleFilter: string
  search: string
  selectedId: string
  selectedMergeKey: string
  showAllCast: boolean
  statusFilter: string
}

export function useCharacterPageDerivedState({
  castFilter,
  chars,
  dismissedMergeKeys,
  evidenceCache,
  graphData,
  manualMergePrimaryId,
  manualMergeSecondaryId,
  repairPreview,
  reviewData,
  roleFilter,
  search,
  selectedId,
  selectedMergeKey,
  showAllCast,
  statusFilter,
}: UseCharacterPageDerivedStateArgs) {
  const deferredSearch = useDeferredValue(search.trim().toLowerCase())

  const pendingCandidates = useMemo(
    () => getPendingCharacterCandidates(reviewData),
    [reviewData],
  )
  const pendingRelationshipCandidates = useMemo(
    () => getPendingRelationshipCandidates(reviewData),
    [reviewData],
  )
  const pendingReviewItemCount = pendingCandidates.length + pendingRelationshipCandidates.length
  const hasPendingReviewItems = pendingReviewItemCount > 0

  const mergeSuggestions = useMemo(
    () => buildMergeSuggestions(reviewData, dismissedMergeKeys),
    [dismissedMergeKeys, reviewData],
  )

  const mergeSuggestionIds = useMemo(
    () => buildMergeSuggestionIds(mergeSuggestions),
    [mergeSuggestions],
  )

  const connectionsByCharacter = useMemo(
    () => buildConnectionsByCharacter(graphData),
    [graphData],
  )

  const relationshipCounts = useMemo(
    () => buildRelationshipCounts(graphData),
    [graphData],
  )

  const shadowChars = useMemo(
    () => buildShadowCharacters(reviewData),
    [reviewData],
  )
  const charById = useMemo(
    () => buildCharacterLookup(chars, shadowChars),
    [chars, shadowChars],
  )
  const characterLabel = (characterId: string) => characterLabelForId(characterId, charById, repairPreview.character_labels)

  const flagsByCharacter = useMemo(
    () => buildCharacterFlagsById(chars, mergeSuggestionIds, connectionsByCharacter),
    [chars, connectionsByCharacter, mergeSuggestionIds],
  )

  const healthByCharacter = useMemo(
    () => buildCharacterHealthById(chars, mergeSuggestionIds, connectionsByCharacter),
    [chars, connectionsByCharacter, mergeSuggestionIds],
  )

  const filteredChars = useMemo(
    () => filterCharacters(chars, {
      deferredSearch,
      statusFilter,
      roleFilter,
      castFilter,
      flagsByCharacter,
      mergeSuggestionIds,
    }),
    [castFilter, chars, deferredSearch, flagsByCharacter, mergeSuggestionIds, roleFilter, statusFilter],
  )

  const selectedCharacter = useMemo(
    () => filteredChars.find((char) => char.id === selectedId)
      ?? charById.get(selectedId)
      ?? filteredChars[0]
      ?? chars[0]
      ?? null,
    [charById, chars, filteredChars, selectedId],
  )

  const filteredMergeSuggestions = useMemo(
    () => filterMergeSuggestions(mergeSuggestions, charById, deferredSearch),
    [charById, deferredSearch, mergeSuggestions],
  )

  const filteredPendingCandidates = useMemo(
    () => filterPendingCharacterCandidates(pendingCandidates, deferredSearch),
    [deferredSearch, pendingCandidates],
  )
  const filteredRelationshipCandidates = useMemo(
    () => filterPendingRelationshipCandidates(pendingRelationshipCandidates, deferredSearch),
    [deferredSearch, pendingRelationshipCandidates],
  )
  const selectedReviewCandidate = filteredPendingCandidates[0] ?? null

  const selectedMergeSuggestion = filteredMergeSuggestions.find((suggestion) => suggestion.key === selectedMergeKey)
    ?? filteredMergeSuggestions[0]
    ?? null

  const visibleCastChars = showAllCast ? filteredChars : filteredChars.slice(0, 8)

  const selectedConnections = useMemo(
    () => selectedCharacter ? connectionsByCharacter.get(selectedCharacter.id) ?? [] : [],
    [connectionsByCharacter, selectedCharacter],
  )
  const selectedKnownFacts = useMemo(
    () => selectedCharacter ? knownFacts(selectedCharacter, selectedConnections) : [],
    [selectedCharacter, selectedConnections],
  )
  const selectedTraitEntries = useMemo(
    () => visibleTraitEntries(selectedCharacter),
    [selectedCharacter],
  )
  const selectedOpenQuestions = useMemo(
    () => selectedCharacter ? openQuestionsForCharacter(selectedCharacter, selectedConnections) : [],
    [selectedCharacter, selectedConnections],
  )
  const hiddenGraphNodes = useMemo(() => graphData?.hidden_nodes ?? [], [graphData?.hidden_nodes])
  const selectedHiddenGraphRecord = useMemo(
    () => selectedCharacter ? hiddenGraphNodes.find((node) => node.id === selectedCharacter.id) ?? null : null,
    [hiddenGraphNodes, selectedCharacter],
  )
  const selectedFlags = useMemo(
    () => selectedCharacter ? flagsByCharacter.get(selectedCharacter.id) ?? [] : [],
    [flagsByCharacter, selectedCharacter],
  )
  const selectedReviewStatus = selectedCharacter ? reviewStatusLabel(selectedCharacter, selectedFlags) : "Unresolved"
  const selectedHealth = useMemo(
    () => selectedCharacter ? healthByCharacter.get(selectedCharacter.id) ?? null : null,
    [healthByCharacter, selectedCharacter],
  )
  const selectedCharacterSummary = useMemo(
    () => buildSelectedCharacterSummary(selectedCharacter, selectedConnections),
    [selectedCharacter, selectedConnections],
  )
  const selectedEvidence = useMemo(
    () => selectedCharacter ? evidenceCache[selectedCharacter.id]?.results ?? [] : [],
    [evidenceCache, selectedCharacter],
  )
  const selectedArcTracker = selectedCharacter?.arc_tracker ?? null
  const selectedGrowthEvents = useMemo(
    () => sortGrowthEvents(selectedCharacter),
    [selectedCharacter],
  )
  const relationshipCounterpartOptions = useMemo(
    () => sortedRelationshipCounterpartOptions(chars, selectedCharacter?.id),
    [chars, selectedCharacter?.id],
  )

  const mergeableCharacters = useMemo(
    () => sortedMergeableCharacters(chars),
    [chars],
  )
  const manualMergePrimary = manualMergePrimaryId ? charById.get(manualMergePrimaryId) ?? null : null
  const manualMergeSecondary = manualMergeSecondaryId ? charById.get(manualMergeSecondaryId) ?? null : null
  const isManualMerge = Boolean(manualMergePrimary && manualMergeSecondary)
  const selectedMergePrimary = isManualMerge
    ? manualMergePrimary
    : selectedMergeSuggestion ? charById.get(selectedMergeSuggestion.primaryId) ?? null : null
  const selectedMergeSecondary = isManualMerge
    ? manualMergeSecondary
    : selectedMergeSuggestion ? charById.get(selectedMergeSuggestion.secondaryId) ?? null : null
  const selectedMergePrimaryEvidence = selectedMergePrimary ? evidenceCache[selectedMergePrimary.id]?.results ?? [] : []
  const selectedMergeSecondaryEvidence = selectedMergeSecondary ? evidenceCache[selectedMergeSecondary.id]?.results ?? [] : []

  const dashboardStats = useMemo(
    () => buildDashboardStats(chars, flagsByCharacter, mergeSuggestions.length, pendingReviewItemCount),
    [chars, flagsByCharacter, mergeSuggestions.length, pendingReviewItemCount],
  )

  return {
    charById,
    characterLabel,
    connectionsByCharacter,
    dashboardStats,
    filteredChars,
    filteredMergeSuggestions,
    filteredPendingCandidates,
    filteredRelationshipCandidates,
    flagsByCharacter,
    hasPendingReviewItems,
    hiddenGraphNodes,
    isManualMerge,
    mergeSuggestionIds,
    mergeSuggestions: mergeSuggestions as MergeSuggestion[],
    mergeableCharacters,
    pendingReviewItemCount,
    relationshipCounterpartOptions,
    relationshipCounts,
    selectedArcTracker,
    selectedCharacter,
    selectedCharacterSummary,
    selectedConnections,
    selectedEvidence,
    selectedFlags,
    selectedGrowthEvents,
    selectedHealth,
    selectedHiddenGraphRecord,
    selectedKnownFacts,
    selectedMergePrimary,
    selectedMergePrimaryEvidence,
    selectedMergeSecondary,
    selectedMergeSecondaryEvidence,
    selectedMergeSuggestion,
    selectedOpenQuestions,
    selectedReviewCandidate,
    selectedReviewStatus,
    selectedTraitEntries,
    visibleCastChars,
  }
}
