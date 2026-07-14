import type { Dispatch, ReactNode, SetStateAction } from "react"

import { CharacterEvidencePanel } from "@/components/reader/CharacterEvidencePanel"
import type { ConnectedRelationship } from "@/components/reader/CharacterProfileRightRail"
import type { CharacterProfileTab } from "@/components/reader/CharacterProfileTabs"
import type { Character, RelationshipGraph as RelationshipGraphData } from "@/types/character"
import type { SearchResult } from "@/types/reader"
import { CharacterArcTab } from "./charactersPage.arc"
import type { MenuAction } from "./charactersPage.components"
import { CharacterContinuityTab } from "./charactersPage.continuity"
import { CharacterMentionsTab } from "./charactersPage.mentions"
import { CharacterNotesTab } from "./charactersPage.notes"
import { CharacterOverviewIdentityCards } from "./charactersPage.overview"
import { CharacterEditProfileForm, CharacterGraphVisibilityCard, CharacterReviewControlsCard } from "./charactersPage.profileControls"
import { CharacterProfileHeader } from "./charactersPage.profileHeader"
import { CharacterRelationshipsTab } from "./charactersPage.relationships"
import { CharacterTimelineTab } from "./charactersPage.timeline"
import {
  buildDraft,
  formatRelationshipType,
  sentimentLabel,
  type EditDraft,
  type RelationshipComposerDraft,
} from "./charactersPage.helpers"

type HiddenGraphNode = NonNullable<RelationshipGraphData["hidden_nodes"]>[number]
type TraitEntry = [string, { value: string } | null | undefined]

type CharacterProfileWorkspaceProps = {
  actionError: string | null
  activeTab: CharacterProfileTab
  arcTracker: Character["arc_tracker"] | null
  bookId: string
  bookTotalChapters?: number | null
  character: Character
  characterMenuActions: MenuAction[]
  characterMenuOpen: boolean
  chapterAppearanceText: (chapter: number | null | undefined) => string
  connections: ConnectedRelationship[]
  counterpartOptions: Character[]
  createRelationshipBusy: boolean
  draft: EditDraft
  editing: boolean
  evidence: SearchResult[]
  evidenceError: string | null
  evidenceLoading: boolean
  flags: string[]
  graphOverrideBusy: boolean
  growthEvents: NonNullable<Character["growth_events"]>
  hiddenGraphNodes: HiddenGraphNode[]
  hiddenGraphRecord: NonNullable<RelationshipGraphData["hidden_nodes"]>[number] | null
  isAuthorMode: boolean
  isDark: boolean
  knownFacts: string[]
  noteToast: string | null
  openQuestions: string[]
  relationshipDraft: RelationshipComposerDraft
  relationshipGraph: ReactNode
  reviewNoteBusy: boolean
  reviewNoteDraft: string
  reviewStatus: string
  saving: boolean
  selectedHealthIssues: string[]
  shareState: "idle" | "copied" | "error"
  summary: string
  traitEntries: TraitEntry[]
  onApproveCharacter: () => void
  onCreateRelationship: () => void
  onDemoteSelectedCharacter: () => void
  onDraftChange: Dispatch<SetStateAction<EditDraft>>
  onGraphVisibilityOverride: (value: "include" | "exclude" | null) => void
  onOpenEvidence: () => void
  onRejectCharacter: () => void
  onReviewHiddenNode: (nodeId: string) => void
  onReviewNoteChange: Dispatch<SetStateAction<string>>
  onSaveCharacter: () => void
  onSaveCharacterNote: () => void
  onSaveReviewNote: () => void
  onSetActiveTab: (tab: CharacterProfileTab) => void
  onSetEditing: Dispatch<SetStateAction<boolean>>
  onSetRelationshipDraft: Dispatch<SetStateAction<RelationshipComposerDraft>>
  onShareCharacter: () => void
  onToggleCharacterMenu: () => void
  onToggleProtectedFromRepair: () => void
}

export function CharacterProfileWorkspace({
  actionError,
  activeTab,
  arcTracker,
  bookId,
  bookTotalChapters,
  character,
  characterMenuActions,
  characterMenuOpen,
  chapterAppearanceText,
  connections,
  counterpartOptions,
  createRelationshipBusy,
  draft,
  editing,
  evidence,
  evidenceError,
  evidenceLoading,
  flags,
  graphOverrideBusy,
  growthEvents,
  hiddenGraphNodes,
  hiddenGraphRecord,
  isAuthorMode,
  isDark,
  knownFacts,
  noteToast,
  openQuestions,
  relationshipDraft,
  relationshipGraph,
  reviewNoteBusy,
  reviewNoteDraft,
  reviewStatus,
  saving,
  selectedHealthIssues,
  shareState,
  summary,
  traitEntries,
  onApproveCharacter,
  onCreateRelationship,
  onDemoteSelectedCharacter,
  onDraftChange,
  onGraphVisibilityOverride,
  onOpenEvidence,
  onRejectCharacter,
  onReviewHiddenNode,
  onReviewNoteChange,
  onSaveCharacter,
  onSaveCharacterNote,
  onSaveReviewNote,
  onSetActiveTab,
  onSetEditing,
  onSetRelationshipDraft,
  onShareCharacter,
  onToggleCharacterMenu,
  onToggleProtectedFromRepair,
}: CharacterProfileWorkspaceProps) {
  return (
    <div className="p-5">
      <CharacterProfileHeader
        activeTab={activeTab}
        character={character}
        characterMenuActions={characterMenuActions}
        characterMenuOpen={characterMenuOpen}
        flags={flags}
        isDark={isDark}
        relationshipCount={connections.length}
        shareState={shareState}
        onShareCharacter={onShareCharacter}
        onTabSelect={onSetActiveTab}
        onToggleCharacterMenu={onToggleCharacterMenu}
      />

      {activeTab === "overview" ? (
        <div className="mt-5 grid gap-4 xl:grid-cols-2">
          <CharacterOverviewIdentityCards
            character={character}
            chapterAppearanceText={chapterAppearanceText}
            evidenceCount={evidence.length}
            growthEventCount={growthEvents.length}
            isDark={isDark}
            knownFacts={knownFacts}
            reviewStatus={reviewStatus}
            summary={summary}
            totalChapters={bookTotalChapters}
            onOpenEvidence={onOpenEvidence}
          />

          <CharacterGraphVisibilityCard
            character={character}
            graphOverrideBusy={graphOverrideBusy}
            hiddenGraphRecord={hiddenGraphRecord}
            isAuthorMode={isAuthorMode}
            isDark={isDark}
            onGraphVisibilityOverride={onGraphVisibilityOverride}
          />

          {isAuthorMode ? (
            <CharacterReviewControlsCard
              character={character}
              isDark={isDark}
              reviewNoteBusy={reviewNoteBusy}
              reviewNoteDraft={reviewNoteDraft}
              saving={saving}
              onApproveCharacter={onApproveCharacter}
              onDemoteSelectedCharacter={onDemoteSelectedCharacter}
              onRejectCharacter={onRejectCharacter}
              onReviewNoteChange={onReviewNoteChange}
              onSaveReviewNote={onSaveReviewNote}
              onToggleProtectedFromRepair={onToggleProtectedFromRepair}
            />
          ) : null}

          {isAuthorMode && editing ? (
            <CharacterEditProfileForm
              actionError={actionError}
              draft={draft}
              isDark={isDark}
              saving={saving}
              onCancel={() => {
                onSetEditing(false)
                onDraftChange(buildDraft(character))
              }}
              onDraftChange={onDraftChange}
              onSave={onSaveCharacter}
            />
          ) : null}
        </div>
      ) : null}

      {activeTab === "relationships" ? (
        <CharacterRelationshipsTab
          connections={connections}
          counterpartOptions={counterpartOptions}
          createRelationshipBusy={createRelationshipBusy}
          hiddenGraphNodes={hiddenGraphNodes}
          isAuthorMode={isAuthorMode}
          isDark={isDark}
          relationshipDraft={relationshipDraft}
          onCreateRelationship={onCreateRelationship}
          onDraftChange={onSetRelationshipDraft}
          onReviewHiddenNode={onReviewHiddenNode}
        >
          {relationshipGraph}
        </CharacterRelationshipsTab>
      ) : null}

      {activeTab === "mentions" ? (
        <CharacterMentionsTab
          character={character}
          chapterAppearanceText={chapterAppearanceText}
          evidence={evidence}
          isDark={isDark}
          openQuestions={openQuestions}
          totalChapters={bookTotalChapters}
          onOpenEvidence={onOpenEvidence}
        />
      ) : null}

      {activeTab === "timeline" ? (
        <CharacterTimelineTab
          arcTracker={arcTracker}
          character={character}
          chapterAppearanceText={chapterAppearanceText}
          growthEvents={growthEvents}
          isDark={isDark}
          totalChapters={bookTotalChapters}
        />
      ) : null}

      {activeTab === "arc" ? (
        <CharacterArcTab
          arcTracker={arcTracker}
          character={character}
          growthEvents={growthEvents}
          isDark={isDark}
        />
      ) : null}

      {activeTab === "evidence" ? (
        <CharacterEvidencePanel
          characterId={character.id}
          characterName={character.name}
          error={evidenceError}
          evidence={evidence}
          formatRelationshipType={formatRelationshipType}
          isDark={isDark}
          loading={evidenceLoading}
          relationships={connections}
          sentimentLabel={sentimentLabel}
        />
      ) : null}

      {activeTab === "continuity" ? (
        <CharacterContinuityTab
          contradictions={arcTracker?.contradictions ?? []}
          diagnostics={arcTracker?.diagnostics ?? []}
          healthIssues={selectedHealthIssues}
          isDark={isDark}
          traitEntries={traitEntries}
        />
      ) : null}

      {activeTab === "notes" ? (
        <CharacterNotesTab
          bookId={bookId}
          character={character}
          isDark={isDark}
          noteToast={noteToast}
          onSaveCharacterNote={onSaveCharacterNote}
        />
      ) : null}

      {actionError && !editing ? <p className="mt-4 text-sm text-rose-400">{actionError}</p> : null}
    </div>
  )
}
