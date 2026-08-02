"use client"

import dynamic from "next/dynamic"
import type { ComponentProps, Dispatch, SetStateAction } from "react"

import { CharacterProfileRightRail, type SidebarTab } from "@/components/reader/CharacterProfileRightRail"
import type { CharacterProfileTab } from "@/components/reader/CharacterProfileTabs"
import { CharacterWorkspaceHeader } from "@/components/reader/CharacterWorkspaceHeader"
import { CharacterWorkspaceSidebarHeader } from "@/components/reader/CharacterWorkspaceSidebarHeader"
import type { Book } from "@/types/book"
import type {
  Character,
  CharacterCandidate,
  CharacterIdentityDiagnostics,
  CharacterRepairPreview,
  CharacterRelationshipCandidate,
  RelationshipGraph as RelationshipGraphData,
} from "@/types/character"
import type { CreateDraft, EditDraft, MergeSuggestion, RelationshipComposerDraft } from "./charactersPage.helpers"
import {
  CharacterBibleHeaderActions,
  CharacterBibleHeaderStats,
  CharacterBibleSkeleton,
  RelationshipGraphLoading,
} from "./charactersPage.components"
import { CharacterCreateForm } from "./charactersPage.createForm"
import type { useCharacterPageDerivedState } from "./charactersPage.derivedState"
import { CharacterDuplicateSideRail, CharacterDuplicateWorkspace } from "./charactersPage.duplicates"
import { CharacterProfileWorkspace } from "./charactersPage.profileWorkspace"
import { CharacterRepairTab } from "./charactersPage.repair"
import { CharacterReviewTab } from "./charactersPage.review"
import { CharacterCreateSidePanel, CharacterRepairSidePanel, CharacterReviewSidePanel } from "./charactersPage.sidePanels"
import { CharactersSidebarBody } from "./charactersPage.sidebar"
import { buildSidebarSummary, CharacterWorkspaceEmptyState } from "./charactersPage.workspaceState"

const RelationshipGraph = dynamic(
  () => import("@/components/intelligence/RelationshipGraph"),
  {
    ssr: false,
    loading: () => <RelationshipGraphLoading />,
  }
)

type CastFilter = "all" | "main" | "minor" | "needs-review" | "duplicates"
type WorkspaceMode = "profile" | "review" | "duplicates" | "repair"
type DerivedState = ReturnType<typeof useCharacterPageDerivedState>
type SidebarSummary = ReturnType<typeof buildSidebarSummary>
type PageMenuActions = ComponentProps<typeof CharacterBibleHeaderActions>["pageMenuActions"]
type CharacterMenuActions = ComponentProps<typeof CharacterProfileWorkspace>["characterMenuActions"]
type ShareState = ComponentProps<typeof CharacterProfileWorkspace>["shareState"]

export type CharactersPageLayoutProps = {
  actionError: string | null
  activeTab: CharacterProfileTab
  atmosphere: string
  book: Book | null
  bookId: string
  candidateActionId: string | null
  castFilter: CastFilter
  characterMenuActions: CharacterMenuActions
  characterMenuOpen: boolean
  chapterAppearanceText: (chapter: number | null | undefined) => string
  chars: Character[]
  createBusy: boolean
  createDraft: CreateDraft
  createRelationshipBusy: boolean
  creating: boolean
  derived: DerivedState
  draft: EditDraft
  editing: boolean
  error: string | null
  evidenceCache: ComponentProps<typeof CharacterReviewTab>["evidenceCache"]
  evidenceError: string | null
  evidenceLoadingId: string | null
  graphOverrideBusy: boolean
  identityDiagnostics: CharacterIdentityDiagnostics
  identityUndoActionId: string | null
  isAuthorMode: boolean
  isDark: boolean
  loading: boolean
  mergeBusy: boolean
  mergeError: string | null
  noteToast: string | null
  pageMenuActions: PageMenuActions
  pageMenuOpen: boolean
  partitioning: boolean
  relationshipCandidateActionId: string | null
  relationshipChapter: number
  relationshipDraft: RelationshipComposerDraft
  repairPreview: CharacterRepairPreview
  repairPreviewFetching: boolean
  reprocessAllowDemote: boolean
  reprocessAllowMerge: boolean
  reprocessBusy: boolean
  reviewNoteBusy: boolean
  reviewNoteDraft: string
  roleFilter: string
  saving: boolean
  search: string
  shareState: ShareState
  showAllCast: boolean
  sidebarSummary: SidebarSummary
  sidebarTab: SidebarTab
  statusFilter: string
  theme: string
  workspaceMode: WorkspaceMode
  onAcceptRelationshipCandidate: (candidate: CharacterRelationshipCandidate) => void
  onApplyRepairPlan: () => void
  onApproveCharacter: () => void
  onAttachCandidate: (candidate: CharacterCandidate) => void
  onAttachRelationshipCandidate: (candidate: CharacterRelationshipCandidate, side: "a" | "b") => void
  onBack: () => void
  onCancelCreate: () => void
  onClearManualMerge: () => void
  onCompareEvidence: (characterId: string) => void
  onCreateCharacter: () => void
  onCreateRelationship: () => void
  onDemoteSelectedCharacter: () => void
  onDismissDuplicateSuggestion: (suggestion: MergeSuggestion) => void
  onDuplicateReview: (characterId?: string) => void
  onFindCandidateEvidence: (candidate: CharacterCandidate) => void
  onGraphDataChange: Dispatch<SetStateAction<RelationshipGraphData | null>>
  onGraphVisibilityOverride: (value: "include" | "exclude" | null) => void
  onManualMerge: (primaryId?: string, secondaryId?: string) => void
  onMarkCandidatePlace: (candidate: CharacterCandidate) => void
  onMergeCharacters: (primaryId: string, secondaryId: string, suggestionId?: string) => void
  onOpenCreateCharacter: () => void
  onOpenEvidence: () => void
  onOpenRelationships: () => void
  onOpenRepairWorkspace: () => void
  onOpenReviewQueue: () => void
  onPartitionCharacter: () => void
  onPromoteCandidate: (candidate: CharacterCandidate) => void
  onRefreshEvidence: (character: Character, force?: boolean) => void
  onRefreshRepairPreview: () => void
  onRejectCandidate: (candidate: CharacterCandidate) => void
  onRejectCharacter: () => void
  onRejectRelationshipCandidate: (candidate: CharacterRelationshipCandidate) => void
  onRepairRelationships: () => void
  onResetCreate: () => void
  onResolveRelationshipCandidate: (candidate: CharacterRelationshipCandidate) => void
  onReviewDataIntent: () => void
  onSaveCharacter: () => void
  onSaveCharacterNote: () => void
  onSaveReviewNote: () => void
  onSelectCharacter: (characterId: string) => void
  onShareCharacter: () => void
  onStartManualMerge: (primaryId?: string, secondaryId?: string) => void
  onToggleCharacterMenu: () => void
  onTogglePageMenu: () => void
  onToggleProtectedFromRepair: () => void
  onUndoIdentityAction: (actionId: string) => void
  setActiveTab: Dispatch<SetStateAction<CharacterProfileTab>>
  setCastFilter: Dispatch<SetStateAction<CastFilter>>
  setCreateDraft: Dispatch<SetStateAction<CreateDraft>>
  setDraft: Dispatch<SetStateAction<EditDraft>>
  setEditing: Dispatch<SetStateAction<boolean>>
  setManualMergePrimaryId: Dispatch<SetStateAction<string>>
  setManualMergeSecondaryId: Dispatch<SetStateAction<string>>
  setRelationshipDraft: Dispatch<SetStateAction<RelationshipComposerDraft>>
  setReprocessAllowDemote: Dispatch<SetStateAction<boolean>>
  setReprocessAllowMerge: Dispatch<SetStateAction<boolean>>
  setReviewNoteDraft: Dispatch<SetStateAction<string>>
  setRoleFilter: Dispatch<SetStateAction<string>>
  setSearch: Dispatch<SetStateAction<string>>
  setSelectedId: Dispatch<SetStateAction<string>>
  setSelectedMergeKey: Dispatch<SetStateAction<string>>
  setSidebarTab: Dispatch<SetStateAction<SidebarTab>>
  setShowAllCast: Dispatch<SetStateAction<boolean>>
  setStatusFilter: Dispatch<SetStateAction<string>>
  setWorkspaceMode: Dispatch<SetStateAction<WorkspaceMode>>
}

export function CharactersPageLayout({
  actionError,
  activeTab,
  atmosphere,
  book,
  bookId,
  candidateActionId,
  castFilter,
  characterMenuActions,
  characterMenuOpen,
  chapterAppearanceText,
  chars,
  createBusy,
  createDraft,
  createRelationshipBusy,
  creating,
  derived,
  draft,
  editing,
  error,
  evidenceCache,
  evidenceError,
  evidenceLoadingId,
  graphOverrideBusy,
  identityDiagnostics,
  identityUndoActionId,
  isAuthorMode,
  isDark,
  loading,
  mergeBusy,
  mergeError,
  noteToast,
  pageMenuActions,
  pageMenuOpen,
  partitioning,
  relationshipCandidateActionId,
  relationshipChapter,
  relationshipDraft,
  repairPreview,
  repairPreviewFetching,
  reprocessAllowDemote,
  reprocessAllowMerge,
  reprocessBusy,
  reviewNoteBusy,
  reviewNoteDraft,
  roleFilter,
  saving,
  search,
  shareState,
  showAllCast,
  sidebarSummary,
  sidebarTab,
  statusFilter,
  theme,
  workspaceMode,
  onAcceptRelationshipCandidate,
  onApplyRepairPlan,
  onApproveCharacter,
  onAttachCandidate,
  onAttachRelationshipCandidate,
  onBack,
  onCancelCreate,
  onClearManualMerge,
  onCompareEvidence,
  onCreateCharacter,
  onCreateRelationship,
  onDemoteSelectedCharacter,
  onDismissDuplicateSuggestion,
  onDuplicateReview,
  onFindCandidateEvidence,
  onGraphDataChange,
  onGraphVisibilityOverride,
  onManualMerge,
  onMarkCandidatePlace,
  onMergeCharacters,
  onOpenCreateCharacter,
  onOpenEvidence,
  onOpenRelationships,
  onOpenRepairWorkspace,
  onOpenReviewQueue,
  onPartitionCharacter,
  onPromoteCandidate,
  onRefreshEvidence,
  onRefreshRepairPreview,
  onRejectCandidate,
  onRejectCharacter,
  onRejectRelationshipCandidate,
  onRepairRelationships,
  onResetCreate,
  onResolveRelationshipCandidate,
  onReviewDataIntent,
  onSaveCharacter,
  onSaveCharacterNote,
  onSaveReviewNote,
  onSelectCharacter,
  onShareCharacter,
  onStartManualMerge,
  onToggleCharacterMenu,
  onTogglePageMenu,
  onToggleProtectedFromRepair,
  onUndoIdentityAction,
  setActiveTab,
  setCastFilter,
  setCreateDraft,
  setDraft,
  setEditing,
  setManualMergePrimaryId,
  setManualMergeSecondaryId,
  setRelationshipDraft,
  setReprocessAllowDemote,
  setReprocessAllowMerge,
  setReviewNoteDraft,
  setRoleFilter,
  setSearch,
  setSelectedId,
  setSelectedMergeKey,
  setSidebarTab,
  setShowAllCast,
  setStatusFilter,
  setWorkspaceMode,
}: CharactersPageLayoutProps) {
  if (loading) {
    return <CharacterBibleSkeleton isDark={isDark} atmosphere={atmosphere} />
  }

  return (
    <div className={`min-h-screen transition-colors ${atmosphere}`}>
      <div className="mx-auto max-w-[1500px] px-4 pb-8 pt-5 sm:px-6 lg:px-8">
        <CharacterWorkspaceHeader
          title="Character Bible"
          description="Manage cast, aliases, relationships, continuity, and duplicate review."
          onBack={onBack}
          isDark={isDark}
          stats={<CharacterBibleHeaderStats isDark={isDark} stats={derived.dashboardStats} />}
          actions={(
            <CharacterBibleHeaderActions
              creating={creating}
              isAuthorMode={isAuthorMode}
              isDark={isDark}
              pageMenuActions={pageMenuActions}
              pageMenuOpen={pageMenuOpen}
              workspaceMode={workspaceMode}
              onCreateCharacter={onOpenCreateCharacter}
              onOpenDuplicateReview={() => onDuplicateReview()}
              onOpenRepairWorkspace={onOpenRepairWorkspace}
              onOpenReviewQueue={onOpenReviewQueue}
              onReviewDataIntent={onReviewDataIntent}
              onTogglePageMenu={onTogglePageMenu}
            />
          )}
        />

        {mergeError ? <p className="mt-3 text-sm text-amber-400">{mergeError}</p> : null}
        {error ? <p className="mt-3 text-sm text-rose-400">{error}</p> : null}

        {!error && (chars.length > 0 || creating || workspaceMode !== "profile") ? (
          <div className={`mt-5 overflow-hidden rounded-lg border ${isDark ? "border-[#202a38] bg-[#070c13]" : "border-stone-200 bg-white/94"}`}>
            <div className="grid xl:h-[calc(100vh-12rem)] xl:grid-cols-[340px_minmax(0,1fr)_320px] 2xl:grid-cols-[350px_minmax(0,1fr)_330px]">
              <aside className={`border-b xl:min-h-0 xl:overflow-y-auto xl:border-b-0 xl:border-r ${isDark ? "border-[#17202c]" : "border-stone-200"}`}>
                <CharacterWorkspaceSidebarHeader
                  castFilter={castFilter}
                  isDark={isDark}
                  mode={workspaceMode}
                  onCastFilterChange={setCastFilter}
                  onRoleFilterChange={setRoleFilter}
                  onSearchChange={setSearch}
                  onStatusFilterChange={setStatusFilter}
                  roleFilter={roleFilter}
                  search={search}
                  statusFilter={statusFilter}
                  summary={sidebarSummary}
                />

                <CharactersSidebarBody
                  candidateActionId={candidateActionId}
                  charById={derived.charById}
                  charsCount={chars.length}
                  filteredChars={derived.filteredChars}
                  filteredMergeSuggestions={derived.filteredMergeSuggestions}
                  filteredPendingCandidates={derived.filteredPendingCandidates}
                  filteredRelationshipCandidates={derived.filteredRelationshipCandidates}
                  flagsByCharacter={derived.flagsByCharacter}
                  isAuthorMode={isAuthorMode}
                  isDark={isDark}
                  relationshipCandidateActionId={relationshipCandidateActionId}
                  relationshipCounts={derived.relationshipCounts}
                  selectedCharacter={derived.selectedCharacter}
                  selectedMergeSuggestion={derived.selectedMergeSuggestion}
                  showAllCast={showAllCast}
                  visibleCastChars={derived.visibleCastChars}
                  workspaceMode={workspaceMode}
                  onAcceptRelationshipCandidate={onAcceptRelationshipCandidate}
                  onAttachCandidate={onAttachCandidate}
                  onAttachRelationshipCandidate={onAttachRelationshipCandidate}
                  onMarkCandidatePlace={onMarkCandidatePlace}
                  onOpenCreateCharacter={onOpenCreateCharacter}
                  onPromoteCandidate={onPromoteCandidate}
                  onRejectCandidate={onRejectCandidate}
                  onRejectRelationshipCandidate={onRejectRelationshipCandidate}
                  onResolveRelationshipCandidate={onResolveRelationshipCandidate}
                  onSelectCharacter={onSelectCharacter}
                  onSelectMergeSuggestion={setSelectedMergeKey}
                  onShowAllCastChange={setShowAllCast}
                />
              </aside>

              <section className={`border-b xl:min-h-0 xl:overflow-y-auto xl:border-b-0 xl:border-r ${isDark ? "border-[#17202c]" : "border-stone-200"}`}>
                {workspaceMode === "profile" && creating ? (
                  <CharacterCreateForm
                    actionError={actionError}
                    createBusy={createBusy}
                    createDraft={createDraft}
                    isDark={isDark}
                    onCancel={onCancelCreate}
                    onCreate={onCreateCharacter}
                    onDraftChange={setCreateDraft}
                    onReset={onResetCreate}
                  />
                ) : null}

                {workspaceMode === "profile" && derived.selectedCharacter && !creating ? (
                  <CharacterProfileWorkspace
                    actionError={actionError}
                    activeTab={activeTab}
                    arcTracker={derived.selectedArcTracker}
                    bookId={bookId}
                    bookTotalChapters={book?.total_chapters}
                    character={derived.selectedCharacter}
                    characterMenuActions={characterMenuActions}
                    characterMenuOpen={characterMenuOpen}
                    chapterAppearanceText={chapterAppearanceText}
                    connections={derived.selectedConnections}
                    counterpartOptions={derived.relationshipCounterpartOptions}
                    createRelationshipBusy={createRelationshipBusy}
                    draft={draft}
                    editing={editing}
                    evidence={derived.selectedEvidence}
                    evidenceError={evidenceError}
                    evidenceLoading={evidenceLoadingId === derived.selectedCharacter.id}
                    flags={derived.selectedFlags}
                    graphOverrideBusy={graphOverrideBusy}
                    growthEvents={derived.selectedGrowthEvents}
                    hiddenGraphNodes={derived.hiddenGraphNodes}
                    hiddenGraphRecord={derived.selectedHiddenGraphRecord}
                    isAuthorMode={isAuthorMode}
                    isDark={isDark}
                    knownFacts={derived.selectedKnownFacts}
                    noteToast={noteToast}
                    openQuestions={derived.selectedOpenQuestions}
                    relationshipDraft={relationshipDraft}
                    relationshipGraph={(
                      <RelationshipGraph
                        bookId={bookId}
                        upToChapter={relationshipChapter}
                        authorMode={isAuthorMode}
                        includeInactive={isAuthorMode}
                        theme={theme === "dark" ? "dark" : "light"}
                        focusCharacterId={derived.selectedCharacter.id}
                        onGraphDataChange={onGraphDataChange}
                        onSelectCharacterId={(characterId) => {
                          if (characterId) {
                            setSelectedId(characterId)
                            setActiveTab("relationships")
                          }
                        }}
                      />
                    )}
                    reviewNoteBusy={reviewNoteBusy}
                    reviewNoteDraft={reviewNoteDraft}
                    reviewStatus={derived.selectedReviewStatus}
                    saving={saving}
                    selectedHealthIssues={derived.selectedHealth?.issues ?? []}
                    shareState={shareState}
                    summary={derived.selectedCharacterSummary}
                    traitEntries={derived.selectedTraitEntries}
                    onApproveCharacter={onApproveCharacter}
                    onCreateRelationship={onCreateRelationship}
                    onDemoteSelectedCharacter={onDemoteSelectedCharacter}
                    onDraftChange={setDraft}
                    onGraphVisibilityOverride={onGraphVisibilityOverride}
                    onOpenEvidence={onOpenEvidence}
                    onRejectCharacter={onRejectCharacter}
                    onReviewHiddenNode={(nodeId) => {
                      setSelectedId(nodeId)
                      setActiveTab("overview")
                    }}
                    onReviewNoteChange={setReviewNoteDraft}
                    onSaveCharacter={onSaveCharacter}
                    onSaveCharacterNote={onSaveCharacterNote}
                    onSaveReviewNote={onSaveReviewNote}
                    onSetActiveTab={setActiveTab}
                    onSetEditing={setEditing}
                    onSetRelationshipDraft={setRelationshipDraft}
                    onShareCharacter={onShareCharacter}
                    onToggleCharacterMenu={onToggleCharacterMenu}
                    onToggleProtectedFromRepair={onToggleProtectedFromRepair}
                  />
                ) : null}

                {workspaceMode === "profile" && !derived.selectedCharacter && !creating ? (
                  <div className="p-5">
                    <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>
                      {chars.length === 0 ? "No character profiles are ready yet." : "No characters match the current filters."}
                    </p>
                    {chars.length === 0 && isAuthorMode ? (
                      <button
                        type="button"
                        onClick={onOpenCreateCharacter}
                        className="mt-4 rounded-md bg-violet-700 px-5 py-3 text-sm font-semibold text-white transition hover:bg-violet-600"
                      >
                        Add character
                      </button>
                    ) : null}
                  </div>
                ) : null}

                {workspaceMode === "review" ? (
                  <CharacterReviewTab
                    candidateActionId={candidateActionId}
                    evidenceCache={evidenceCache}
                    filteredPendingCandidatesCount={derived.filteredPendingCandidates.length}
                    relationshipCandidates={derived.filteredRelationshipCandidates}
                    selectedCandidate={derived.selectedReviewCandidate}
                    hasSelectedCharacter={Boolean(derived.selectedCharacter)}
                    isDark={isDark}
                    onAttachCandidate={onAttachCandidate}
                    onFindEvidence={onFindCandidateEvidence}
                    onMarkCandidatePlace={onMarkCandidatePlace}
                    onPromoteCandidate={onPromoteCandidate}
                    onRejectCandidate={onRejectCandidate}
                  />
                ) : null}

                {workspaceMode === "repair" ? (
                  <CharacterRepairTab
                    characterLabel={derived.characterLabel}
                    identityDiagnostics={identityDiagnostics}
                    identityUndoActionId={identityUndoActionId}
                    isDark={isDark}
                    repairPreview={repairPreview}
                    repairPreviewFetching={repairPreviewFetching}
                    reprocessAllowDemote={reprocessAllowDemote}
                    reprocessAllowMerge={reprocessAllowMerge}
                    reprocessBusy={reprocessBusy}
                    onApplyRepairPlan={onApplyRepairPlan}
                    onRefreshPreview={onRefreshRepairPreview}
                    onRepairRelationships={onRepairRelationships}
                    onSetReprocessAllowDemote={setReprocessAllowDemote}
                    onSetReprocessAllowMerge={setReprocessAllowMerge}
                    onUndoIdentityAction={onUndoIdentityAction}
                  />
                ) : null}

                {workspaceMode === "duplicates" ? (
                  <CharacterDuplicateWorkspace
                    connectionsByCharacter={derived.connectionsByCharacter}
                    isDark={isDark}
                    isManualMerge={derived.isManualMerge}
                    mergeBusy={mergeBusy}
                    mergeSuggestionIds={derived.mergeSuggestionIds}
                    mergeableCharacters={derived.mergeableCharacters}
                    primaryCharacter={derived.selectedMergePrimary}
                    primaryEvidence={derived.selectedMergePrimaryEvidence}
                    relationshipCounts={derived.relationshipCounts}
                    secondaryCharacter={derived.selectedMergeSecondary}
                    secondaryEvidence={derived.selectedMergeSecondaryEvidence}
                    selectedMergeSuggestion={derived.selectedMergeSuggestion}
                    onClearManualMerge={onClearManualMerge}
                    onCompareEvidence={onCompareEvidence}
                    onDismissSuggestion={onDismissDuplicateSuggestion}
                    onMergeCharacters={onMergeCharacters}
                    onSetManualPrimary={setManualMergePrimaryId}
                    onSetManualSecondary={setManualMergeSecondaryId}
                    onStartManualMerge={onStartManualMerge}
                  />
                ) : null}
              </section>

              <aside className="xl:min-h-0 xl:overflow-y-auto">
                {workspaceMode === "profile" && creating ? (
                  <CharacterCreateSidePanel isDark={isDark} />
                ) : null}

                {workspaceMode === "profile" && derived.selectedCharacter && derived.selectedHealth ? (
                  <CharacterProfileRightRail
                    character={derived.selectedCharacter}
                    connections={derived.selectedConnections}
                    evidence={derived.selectedEvidence}
                    evidenceError={evidenceError}
                    evidenceLoading={evidenceLoadingId === derived.selectedCharacter.id}
                    health={derived.selectedHealth}
                    isDark={isDark}
                    mergeSuggestionCount={derived.mergeSuggestions.length}
                    partitioning={partitioning}
                    selectedTab={sidebarTab}
                    onFindEvidence={onOpenEvidence}
                    onManualMerge={() => onManualMerge(derived.selectedCharacter?.id)}
                    onOpenNotes={() => setActiveTab("notes")}
                    onOpenRelationships={onOpenRelationships}
                    onPartition={onPartitionCharacter}
                    onRefreshEvidence={() => {
                      if (derived.selectedCharacter) onRefreshEvidence(derived.selectedCharacter, true)
                    }}
                    onReviewDuplicates={() => onDuplicateReview(derived.selectedCharacter?.id)}
                    onSelectTab={(tab) => {
                      setSidebarTab(tab)
                      if (tab === "evidence") onOpenEvidence()
                    }}
                  />

                ) : null}

                {workspaceMode === "review" ? (
                  <CharacterReviewSidePanel
                    candidateCount={derived.filteredPendingCandidates.length}
                    isDark={isDark}
                    mergeSuggestionCount={derived.mergeSuggestions.length}
                    relationshipCandidateCount={derived.filteredRelationshipCandidates.length}
                    selectedCandidate={derived.selectedReviewCandidate}
                  />
                ) : null}

                {workspaceMode === "repair" ? (
                  <CharacterRepairSidePanel
                    isDark={isDark}
                    repairPreview={repairPreview}
                    reprocessAllowDemote={reprocessAllowDemote}
                    reprocessAllowMerge={reprocessAllowMerge}
                  />
                ) : null}

                {workspaceMode === "duplicates" ? (
                  <CharacterDuplicateSideRail
                    characterCount={chars.length}
                    isDark={isDark}
                    isManualMerge={derived.isManualMerge}
                    mergeBusy={mergeBusy}
                    primaryCharacter={derived.selectedMergePrimary}
                    relationshipCandidates={derived.filteredRelationshipCandidates}
                    secondaryCharacter={derived.selectedMergeSecondary}
                    selectedMergeSuggestion={derived.selectedMergeSuggestion}
                    onClearManualMerge={onClearManualMerge}
                    onCompareEvidence={onCompareEvidence}
                    onDismissSuggestion={onDismissDuplicateSuggestion}
                    onMergeCharacters={onMergeCharacters}
                    onStartManualMerge={() => onStartManualMerge()}
                  />
                ) : null}
              </aside>
            </div>
          </div>
        ) : !error ? (
          <CharacterWorkspaceEmptyState
            bookStatus={book?.status}
            hasPendingReviewItems={derived.hasPendingReviewItems}
            isAuthorMode={isAuthorMode}
            isDark={isDark}
            pendingReviewItemCount={derived.pendingReviewItemCount}
            onOpenCreateCharacter={onOpenCreateCharacter}
            onOpenReviewQueue={onOpenReviewQueue}
          />
        ) : null}
      </div>
    </div>
  )
}
