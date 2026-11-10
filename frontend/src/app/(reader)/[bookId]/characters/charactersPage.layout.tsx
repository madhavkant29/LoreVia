"use client"

import dynamic from "next/dynamic"
import { useState, useSyncExternalStore, type ComponentProps, type Dispatch, type SetStateAction } from "react"

import { CharacterProfileRightRail, type SidebarTab } from "@/components/reader/CharacterProfileRightRail"
import type { CharacterProfileTab } from "@/components/reader/CharacterProfileTabs"
import { CharacterWorkspaceHeader } from "@/components/reader/CharacterWorkspaceHeader"
import { AuthorToolsNav } from "@/components/layout/AuthorToolsNav"
import { ProfileEnrichmentNotice } from "@/components/reader/ProfileEnrichmentNotice"
import { CharacterWorkspaceSidebarHeader } from "@/components/reader/CharacterWorkspaceSidebarHeader"
import { WorkspaceSidePanel } from "@/components/ui/WorkspaceSidePanel"
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
  queryIssues: Array<{ label: string; retry: () => Promise<unknown>; busy: boolean }>
  repairUnavailable: boolean
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
  onCharacterUpdated: (character: Character) => void
  onAttachCandidate: (candidate: CharacterCandidate) => void
  onAttachRelationshipCandidate: (candidate: CharacterRelationshipCandidate, side: "a" | "b") => void
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
  queryIssues, repairUnavailable, actionError,
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
  onCharacterUpdated,
  onAttachCandidate,
  onAttachRelationshipCandidate,
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
  setSelectedMergeKey,
  setSidebarTab,
  setShowAllCast,
  setStatusFilter,
}: CharactersPageLayoutProps) {
  const [mobileRosterOpen, setMobileRosterOpen] = useState(false)
  const [inspectorOpen, setInspectorOpen] = useState(false)

  const desktop = useSyncExternalStore(subscribeDesktop, () => window.matchMedia("(min-width: 1280px)").matches, () => false)

  if (loading) {
    return <CharacterBibleSkeleton isDark={isDark} atmosphere={atmosphere} />
  }

  return (
    <main data-character-workspace className={`min-h-screen transition-colors ${atmosphere}`}>
      <div className="mx-auto max-w-[1500px] px-4 pb-8 pt-5 sm:px-6 lg:px-8">
        <div className="mb-5">
          <AuthorToolsNav
            active="characters"
            bookData={book}
            bookId={bookId}
            isDark={isDark}
            mode={book?.mode ?? "author"}
            title={book?.title || "Character Bible"}
            variant="bar"
          />
        </div>
        <CharacterWorkspaceHeader
          title="Character Bible"
          description="Manage cast, aliases, relationships, continuity, and duplicate review."
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

        <ProfileEnrichmentNotice processing={book?.processing} bookId={bookId} isDark={isDark} onReview={onOpenReviewQueue} />
        {mergeError ? <p className="mt-3 text-sm text-amber-400">{mergeError}</p> : null}
        {actionError && workspaceMode !== "profile" ? <p role="alert" className={`mt-3 text-sm ${isDark ? "text-rose-300" : "text-rose-700"}`}>{actionError}</p> : null}
        {queryIssues.map((issue) => <div key={issue.label} role="alert" className="mt-3 flex flex-wrap items-center gap-3 border border-amber-600/40 px-4 py-3 text-sm">
          <span>{issue.label} could not be loaded. Try again to load current data.</span>
          <button type="button" disabled={issue.busy} onClick={() => void issue.retry()} className="min-h-10 underline underline-offset-4 disabled:opacity-50">{issue.busy ? "Retrying…" : "Retry " + issue.label.toLowerCase()}</button>
        </div>)}
        {noteToast ? <p role="status" className="mt-3 text-sm">{noteToast}</p> : null}

        {!error && (chars.length > 0 || creating || workspaceMode !== "profile") ? (
          <>
            <div className="mt-4 flex items-center gap-2">
              <button
                type="button"
                aria-expanded={mobileRosterOpen}
                onClick={() => setMobileRosterOpen(true)}
                className={`rounded-sm border px-3 py-2 text-sm font-medium xl:hidden ${isDark ? "border-[#202a38] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
              >
                Cast
              </button>
              <button
                type="button"
                aria-expanded={inspectorOpen}
                onClick={() => setInspectorOpen((current) => !current)}
                className={`rounded-sm border px-3 py-2 text-sm font-medium ${isDark ? "border-[#202a38] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
              >
                Details
              </button>
            </div>
            <div className={`mt-4 rounded-sm border ${isDark ? "border-[#202a38] bg-[#070c13]" : "border-stone-200 bg-white/94"}`}>
            <div className={`grid min-w-0 xl:h-[calc(100vh-12rem)] ${inspectorOpen ? "xl:grid-cols-[310px_minmax(0,1fr)_320px]" : "xl:grid-cols-[310px_minmax(0,1fr)]"}`}>
              {desktop || mobileRosterOpen ? <WorkspaceSidePanel title="Character roster" side="left" onClose={() => setMobileRosterOpen(false)}>
              <aside className={`h-full min-h-0 overflow-y-auto xl:border-r ${isDark ? "border-[#17202c] bg-[#070c13]" : "border-stone-200 bg-white"}`}>
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
                  onSelectCharacter={(characterId) => {
                    onSelectCharacter(characterId)
                    setMobileRosterOpen(false)
                  }}
                  onSelectMergeSuggestion={setSelectedMergeKey}
                  onShowAllCastChange={setShowAllCast}
                />
              </aside>
              </WorkspaceSidePanel> : null}

              <section className={`min-w-0 border-b xl:min-h-0 xl:overflow-y-auto xl:border-b-0 xl:border-r ${isDark ? "border-[#17202c]" : "border-stone-200"}`}>
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
                        inspectorPlacement="inline"
                        bookId={bookId}
                        upToChapter={relationshipChapter}
                        authorMode={isAuthorMode}
                        includeInactive={isAuthorMode}
                        theme={theme === "dark" ? "dark" : "light"}
                        focusCharacterId={derived.selectedCharacter.id}
                        onGraphDataChange={onGraphDataChange}
                        onSelectCharacterId={(characterId) => {
                          if (characterId) {
                            onSelectCharacter(characterId)
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
                    onCharacterUpdated={onCharacterUpdated}
                    onCreateRelationship={onCreateRelationship}
                    onDemoteSelectedCharacter={onDemoteSelectedCharacter}
                    onDraftChange={setDraft}
                    onGraphVisibilityOverride={onGraphVisibilityOverride}
                    onOpenEvidence={onOpenEvidence}
                    onRejectCharacter={onRejectCharacter}
                    onReviewHiddenNode={(nodeId) => {
                      onSelectCharacter(nodeId)
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
                    pendingCandidates={derived.filteredPendingCandidates}
                    relationshipCandidates={derived.filteredRelationshipCandidates}
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
                    repairUnavailable={repairUnavailable}
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

              {inspectorOpen ? <WorkspaceSidePanel title="Character details" side="right" onClose={() => setInspectorOpen(false)}>
              <aside className={`h-full min-h-0 overflow-y-auto ${isDark ? "bg-[#070c13]" : "bg-white"}`}>
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
                    onFindEvidence={() => { onOpenEvidence(); setInspectorOpen(false) }}
                    onManualMerge={() => onManualMerge(derived.selectedCharacter?.id)}
                    onOpenNotes={() => { setActiveTab("notes"); setInspectorOpen(false) }}
                    onOpenContinuity={() => { setActiveTab("continuity"); setInspectorOpen(false) }}
                    onOpenRelationships={() => { onOpenRelationships(); setInspectorOpen(false) }}
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
              </WorkspaceSidePanel> : null}
            </div>
          </div>
          </>
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
    </main>
  )
}

function subscribeDesktop(callback: () => void) {
  const media = window.matchMedia("(min-width: 1280px)")
  media.addEventListener("change", callback)
  return () => media.removeEventListener("change", callback)
}
