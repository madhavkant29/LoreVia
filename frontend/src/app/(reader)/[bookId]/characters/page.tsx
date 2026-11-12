"use client"

import { useEffect, useRef, useState } from "react"
import { useParams } from "next/navigation"

import type { SidebarTab } from "@/components/reader/CharacterProfileRightRail"
import type { CharacterProfileTab } from "@/components/reader/CharacterProfileTabs"
import { useConfirmDialog } from "@/components/ui/ConfirmDialog"
import { usePromptDialog } from "@/components/ui/PromptDialog"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book } from "@/types/book"
import type { Character, RelationshipGraph as RelationshipGraphData } from "@/types/character"
import type { ReadingProgress } from "@/types/reader"
import {
  buildCreateDraft,
  buildDraft,
  buildRelationshipDraft,
  type CreateDraft,
  type EditDraft,
  type RelationshipComposerDraft,
} from "./charactersPage.helpers"
import { useCharacterDraftProtection } from "./charactersPage.draftProtection"
import { useCharacterMutationActions } from "./charactersPage.characterActions"
import { useCharacterPageDerivedState } from "./charactersPage.derivedState"
import { useCharacterEvidence, useCharacterEvidenceAutoLoad } from "./charactersPage.evidence"
import { CharactersPageLayout, type CharactersPageLayoutProps } from "./charactersPage.layout"
import { useCharacterLayoutActions } from "./charactersPage.layoutActions"
import { useCharacterMergeActions } from "./charactersPage.mergeActions"
import { buildCharacterMenuActions, buildPageMenuActions } from "./charactersPage.menuActions"
import { useCharacterPageQueries } from "./charactersPage.queries"
import { useCharacterRefreshActions } from "./charactersPage.refreshActions"
import { useCharacterRepairActions } from "./charactersPage.repairActions"
import { useCharacterReviewActions } from "./charactersPage.reviewActions"
import { scheduleTrackedTimeout } from "./charactersPage.scheduling"
import { useCharacterShareExportActions } from "./charactersPage.shareExportActions"
import { useCharacterPageSyncEffects } from "./charactersPage.syncEffects"
import { useCharacterWorkspaceActions } from "./charactersPage.workspaceActions"
import { buildSidebarSummary } from "./charactersPage.workspaceState"

type CastFilter = "all" | "main" | "minor" | "needs-review" | "duplicates"
type WorkspaceMode = "profile" | "review" | "duplicates" | "repair"

export default function CharactersPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const confirm = useConfirmDialog()
  const prompt = usePromptDialog()

  const [reviewDataEnabled, setReviewDataEnabled] = useState(false)
  const [book, setBook] = useState<Book | null>(null)
  const [progress, setProgress] = useState<ReadingProgress | null>(null)
  const [chars, setChars] = useState<Character[]>([])
  const [graphData, setGraphData] = useState<RelationshipGraphData | null>(null)
  const [search, setSearch] = useState("")
  const [selectedId, setSelectedId] = useState("")
  const [selectedMergeKey, setSelectedMergeKey] = useState("")
  const [manualMergePrimaryId, setManualMergePrimaryId] = useState("")
  const [manualMergeSecondaryId, setManualMergeSecondaryId] = useState("")
  const [activeTab, setActiveTab] = useState<CharacterProfileTab>("overview")
  const [relationshipsEnabled, setRelationshipsEnabled] = useState(false)
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>("insights")
  const [castFilter, setCastFilter] = useState<CastFilter>("all")
  const [statusFilter, setStatusFilter] = useState("all")
  const [roleFilter, setRoleFilter] = useState("all")
  const [workspaceMode, setWorkspaceMode] = useState<WorkspaceMode>("profile")
  const [showAllCast, setShowAllCast] = useState(false)
  const [dismissedMergeKeys, setDismissedMergeKeys] = useState<string[]>([])
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [noteToast, setNoteToast] = useState<string | null>(null)
  const [draft, setDraft] = useState<EditDraft>(buildDraft(null))
  const [createDraft, setCreateDraft] = useState<CreateDraft>(buildCreateDraft(1))
  const [relationshipDraft, setRelationshipDraft] = useState<RelationshipComposerDraft>(buildRelationshipDraft(1))
  const [pageMenuOpen, setPageMenuOpen] = useState(false)
  const [characterMenuOpen, setCharacterMenuOpen] = useState(false)
  const [reviewNoteDraft, setReviewNoteDraft] = useState("")
  const [reprocessAllowMerge, setReprocessAllowMerge] = useState(true)
  const [reprocessAllowDemote, setReprocessAllowDemote] = useState(true)

  const theme = usePreferencesStore((state) => state.theme)
  const isDark = theme === "dark"
  const isAuthorMode = book?.mode === "author"
  const atmosphere = isDark ? "bg-[#11191a] text-slate-100" : "bg-[#f4f5f3] text-stone-950"

  const {
    bookData,
    error, queryIssues, repairUnavailable,
    charactersData,
    charactersLoading,
    chapterAppearanceText,
    identityDiagnostics,
    loading,
    progressData,
    refetchCharacterReview,
    refetchCharacters,
    refetchIdentityDiagnostics,
    refetchRelationshipGraph,
    refetchRepairPreview,
    relationshipChapter,
    relationshipGraphData,
    repairPreview,
    repairPreviewFetching,
    reviewData,
  } = useCharacterPageQueries({
    book,
    bookId,
    isAuthorMode,
    progress,
    relationshipsEnabled,
    reprocessAllowDemote,
    reprocessAllowMerge,
    reviewDataEnabled,
    workspaceMode,
  })
  const {
    evidenceCache,
    evidenceError,
    evidenceLoadingId,
    loadCandidateEvidence,
    loadCharacterEvidence,
  } = useCharacterEvidence({
    bookId,
    relationshipChapter,
  })

  const timeoutRef = useRef<Set<number>>(new Set())
  useEffect(() => {
    const timeoutIds = timeoutRef.current
    return () => {
      for (const id of timeoutIds) {
        window.clearTimeout(id)
      }
    }
  }, [])

  function scheduleTimeout(callback: () => void, delay: number) {
    scheduleTrackedTimeout(timeoutRef.current, callback, delay)
  }

  const derived = useCharacterPageDerivedState({
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
  })
  const {
    filteredChars,
    filteredMergeSuggestions,
    filteredPendingCandidates,
    filteredRelationshipCandidates,
    isManualMerge,
    selectedCharacter,
    selectedConnections,
    selectedMergePrimary,
    selectedMergeSecondary,
  } = derived

  useCharacterPageSyncEffects({
    activeTab,
    bookData,
    charactersData,
    charactersLoading,
    chars,
    charsLength: chars.length,
    editing,
    filteredChars,
    filteredMergeSuggestions,
    manualMergePrimaryId,
    manualMergeSecondaryId,
    progressData,
    relationshipChapter,
    relationshipGraphData,
    relationshipsEnabled,
    reviewDataEnabled,
    selectedCharacter,
    selectedId,
    selectedMergeKey,
    workspaceMode,
    setActionError,
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
    setReviewDataEnabled,
    setReviewNoteDraft,
    setSelectedId,
    setSelectedMergeKey,
  })

  const {
    refreshingGraph,
    refreshCharacters,
    refreshGraph,
  } = useCharacterRefreshActions({
    refetchCharacterReview,
    refetchCharacters,
    refetchRelationshipGraph,
    refetchRepairPreview,
    workspaceMode,
    setActionError,
    setChars,
    setGraphData,
  })

  const {
    exporting,
    handleExportCharacter,
    handleExportCharacterBible,
    handleShareCharacter,
    saveCharacterWorkspaceNote,
    shareState,
  } = useCharacterShareExportActions({
    bookId,
    bookTitle: book?.title,
    scheduleTimeout,
    selectedCharacter,
    selectedConnections,
    setActionError,
    setCharacterMenuOpen,
    setNoteToast,
    setPageMenuOpen,
  })

  const {
    dismissDuplicateSuggestion,
    handleMergeCharacters,
    mergeBusy,
    mergeError,
    setMergeError,
  } = useCharacterMergeActions({
    bookId,
    refreshCharacters,
    refreshGraph,
    refetchCharacterReview,
    setActiveTab,
    setDismissedMergeKeys,
    setSelectedId,
    setSidebarTab,
    setWorkspaceMode,
  })

  const {
    openCharacterEvidence,
    openCreateCharacter,
    openDuplicateReview,
    openManualMerge,
    openRelationships,
    openRepairWorkspace,
    openReviewQueue,
    resetFilters,
  } = useCharacterWorkspaceActions({
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
  })

  const {
    candidateActionId,
    handleAcceptRelationshipCandidate,
    handleAttachCandidate,
    handleAttachRelationshipCandidate,
    handleMarkCandidatePlace,
    handlePromoteCandidate,
    handleRejectCandidate,
    handleRejectRelationshipCandidate,
    handleResolveRelationshipCandidate,
    relationshipCandidateActionId,
  } = useCharacterReviewActions({
    bookId,
    refreshCharacters,
    refreshGraph,
    refetchCharacterReview,
    selectedCharacter,
    setActionError,
    setSelectedId,
    setWorkspaceMode,
  })

  const {
    handleApplyCharacterReprocess,
    handleRepairRelationships,
    handleUndoIdentityAction,
    identityUndoActionId,
    reprocessBusy,
  } = useCharacterRepairActions({
    bookId,
    refetchCharacterReview,
    refetchIdentityDiagnostics,
    refetchRepairPreview,
    refreshCharacters,
    refreshGraph,
    reprocessAllowDemote,
    reprocessAllowMerge,
    scheduleTimeout,
    setActionError,
    setNoteToast,
  })

  const {
    createBusy,
    createRelationshipBusy,
    deleting,
    graphOverrideBusy,
    handleApproveCharacter,
    handleCreateCharacter,
    handleCreateRelationship,
    handleDeleteCharacter,
    handleDemoteSelectedCharacter,
    handleGraphVisibilityOverride,
    handlePartitionCharacter,
    handleRejectCharacter,
    handleSaveCharacter,
    handleSaveReviewNote,
    handleToggleProtectedFromRepair,
    partitioning,
    reviewNoteBusy,
    saving,
  } = useCharacterMutationActions({
    bookId,
    chars,
    confirm,
    createDraft,
    draft,
    progressChapter: progress?.current_chapter ?? 1,
    prompt,
    refetchCharacterReview,
    refetchRepairPreview,
    refreshCharacters,
    refreshGraph,
    relationshipChapter,
    relationshipDraft,
    reviewNoteDraft,
    scheduleTimeout,
    selectedCharacter,
    workspaceMode,
    setActionError,
    setActiveTab,
    setCastFilter,
    setCharacterMenuOpen,
    setChars,
    setCreating,
    setEditing,
    setNoteToast,
    setRelationshipDraft,
    setSearch,
    setSelectedId,
    setWorkspaceMode,
  })

  useCharacterEvidenceAutoLoad({
    activeTab,
    loadCharacterEvidence,
    selectedCharacter,
    selectedMergePrimary,
    selectedMergeSecondary,
    sidebarTab,
    workspaceMode,
  })

  const changeWorkspace = useCharacterDraftProtection({ editing, creating, draft, createDraft, character: selectedCharacter,
    busy: saving || createBusy || deleting, initialChapter: progress?.current_chapter ?? 1, confirm, onDiscard: () => { setEditing(false); setCreating(false) } })

  const pageMenuActions = buildPageMenuActions({
    exporting,
    isAuthorMode,
    refreshingGraph,
    onClosePageMenu: () => setPageMenuOpen(false),
    onCreateCharacter: openCreateCharacter,
    onExportCharacterBible: (format) => void handleExportCharacterBible(format),
    onManualMerge: () => openManualMerge(),
    onOpenDuplicateReview: () => openDuplicateReview(),
    onOpenRepairWorkspace: openRepairWorkspace,
    onOpenReviewQueue: openReviewQueue,
    onRebuildGraph: () => void refreshGraph(),
    onResetFilters: () => { resetFilters(); setStatusFilter("all"); setRoleFilter("all") },
  })

  const characterMenuActions = buildCharacterMenuActions({
    character: selectedCharacter,
    deleting,
    editing,
    exporting,
    isAuthorMode,
    partitioning,
    saving,
    onCloseCharacterMenu: () => setCharacterMenuOpen(false),
    onDeleteCharacter: () => void handleDeleteCharacter(),
    onDemoteSelectedCharacter: () => void handleDemoteSelectedCharacter(),
    onExportCharacter: (format) => void handleExportCharacter(format),
    onFindEvidence: openCharacterEvidence,
    onManualMerge: (characterId) => openManualMerge(characterId),
    onOpenDuplicateReview: (characterId) => openDuplicateReview(characterId),
    onOpenReviewQueue: openReviewQueue,
    onPartitionCharacter: () => void handlePartitionCharacter(),
    onSetEditing: (value) => { setActiveTab("overview"); setEditing(typeof value === "function" ? value(editing) : value) },
    onToggleProtectedFromRepair: () => void handleToggleProtectedFromRepair(),
  })

  const sidebarSummary = buildSidebarSummary({
    filteredCharCount: filteredChars.length,
    filteredMergeSuggestionCount: filteredMergeSuggestions.length,
    filteredPendingCandidateCount: filteredPendingCandidates.length,
    filteredRelationshipCandidateCount: filteredRelationshipCandidates.length,
    isManualMerge,
    plannedDemotionCount: repairPreview.planned_demotions.length,
    plannedMergeCount: repairPreview.planned_merges.length,
    workspaceMode,
  })

  const layoutActions = useCharacterLayoutActions({
    dismissDuplicateSuggestion, handleAcceptRelationshipCandidate, handleApplyCharacterReprocess, handleApproveCharacter, handleAttachCandidate,
    handleAttachRelationshipCandidate, handleCreateCharacter, handleCreateRelationship, handleDemoteSelectedCharacter, handleGraphVisibilityOverride,
    handleMarkCandidatePlace, handleMergeCharacters, handlePartitionCharacter, handlePromoteCandidate, handleRejectCandidate, handleRejectCharacter,
    handleRejectRelationshipCandidate, handleRepairRelationships, handleResolveRelationshipCandidate, handleSaveCharacter, handleSaveReviewNote,
    handleShareCharacter, handleToggleProtectedFromRepair, handleUndoIdentityAction, loadCandidateEvidence, loadCharacterEvidence, openCharacterEvidence,
    openCreateCharacter, openDuplicateReview, openManualMerge, openRelationships, openRepairWorkspace, openReviewQueue, progressChapter: progress?.current_chapter ?? 1,
    refetchRepairPreview, saveCharacterWorkspaceNote, setActionError, setActiveTab, setCharacterMenuOpen, setCreateDraft,
    setCreating, setEditing, setManualMergePrimaryId, setManualMergeSecondaryId, setPageMenuOpen, setReviewDataEnabled, setSelectedId, setSidebarTab,
    setWorkspaceMode,
  })

  const layoutProps: CharactersPageLayoutProps = {
    queryIssues, repairUnavailable, actionError, activeTab, atmosphere, book, bookId, candidateActionId, castFilter, characterMenuActions, characterMenuOpen, chapterAppearanceText,
    chars, createBusy, createDraft, createRelationshipBusy, creating, derived, draft, editing, error, evidenceCache, evidenceError, evidenceLoadingId,
    graphOverrideBusy, identityDiagnostics, identityUndoActionId, isAuthorMode, isDark, loading, mergeBusy, mergeError, noteToast, pageMenuActions,
    pageMenuOpen, partitioning, relationshipCandidateActionId, relationshipChapter, relationshipDraft, repairPreview, repairPreviewFetching,
    reprocessAllowDemote, reprocessAllowMerge, reprocessBusy, reviewNoteBusy, reviewNoteDraft, roleFilter, saving, search, shareState, showAllCast,
    sidebarSummary, sidebarTab, statusFilter, theme, workspaceMode, onGraphDataChange: setGraphData, ...layoutActions,
    onCharacterUpdated: (updated: Character) => setChars((current) => current.map((item) => item.id === updated.id ? updated : item)),
    setActiveTab, setCastFilter,
    setCreateDraft, setDraft, setEditing, setManualMergePrimaryId, setManualMergeSecondaryId, setRelationshipDraft, setReprocessAllowDemote,
    setReprocessAllowMerge, setReviewNoteDraft, setRoleFilter, setSearch, setSelectedId, setSelectedMergeKey, setSidebarTab, setShowAllCast,
    setStatusFilter, setWorkspaceMode,
  }

  return <CharactersPageLayout {...layoutProps}
    onSelectCharacter={(id) => { if (id !== selectedId || creating || workspaceMode !== "profile") void changeWorkspace(() => layoutActions.onSelectCharacter(id)) }}
    onOpenCreateCharacter={() => { void changeWorkspace(openCreateCharacter) }}
    onOpenReviewQueue={() => { void changeWorkspace(openReviewQueue) }}
    onDuplicateReview={(id) => { void changeWorkspace(() => openDuplicateReview(id)) }}
    onOpenRepairWorkspace={() => { void changeWorkspace(openRepairWorkspace) }}
    pageMenuActions={pageMenuActions.map((action) => /^(Open |Review duplicate)/.test(action.label) ? { ...action, onClick: () => { void changeWorkspace(action.onClick) } } : action)}
    characterMenuActions={characterMenuActions.map((action) => /^(Open |Review duplicate|Merge |Close edit)/.test(action.label) ? { ...action, onClick: () => { void changeWorkspace(action.onClick) } } : action)}
  />
}
