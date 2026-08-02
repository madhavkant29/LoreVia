import type {
  BookNote,
  ManuscriptAnnotation,
  ManuscriptAnnotationCategory,
  SaveState,
} from "@/types/book"
import type { Character } from "@/types/character"
import type {
  EditorialContinuityIssue,
  EditorialReview,
  EditorialReviewPassage,
  ManuscriptSynopsis,
} from "@/types/intelligence"
import type { PlotThread } from "@/types/reader"
import type { ManuscriptSelectionAnchor } from "@/lib/utils/manuscriptAnnotations"

import { ManuscriptAnnotationComposer } from "./manuscriptPage.annotationComposer"
import { ManuscriptAnnotationList } from "./manuscriptPage.annotationList"
import { ManuscriptCharacterPane } from "./manuscriptPage.characterPane"
import { ManuscriptContinuityPanel } from "./manuscriptPage.continuity"
import type { DraftSurfaceMode, EditorMode, RightPane, SaveTarget } from "./manuscriptPage.constants"
import type {
  buildManuscriptInspectorClasses,
  FullBookPageMapItem,
  ManuscriptCharacterCardDraft,
  ManuscriptReferenceItem,
} from "./manuscriptPage.helpers"
import { ManuscriptInsightsSummaryPanels } from "./manuscriptPage.insightsSummary"
import { ManuscriptNoteComposer } from "./manuscriptPage.noteComposer"
import { ManuscriptNoteLists } from "./manuscriptPage.noteLists"
import { ManuscriptPageNavigator } from "./manuscriptPage.pageNavigator"
import { ManuscriptReferences } from "./manuscriptPage.references"

type InspectorClasses = ReturnType<typeof buildManuscriptInspectorClasses>
type NoteScope = "chapter" | "book"
type AnnotationVisibility = "shared" | "private"
type AnnotationSaveState = {
  saveState: SaveState
  retry: () => void
}

type ManuscriptAnalysisRailProps = {
  activeAnnotationId: string | null
  activeChapterNumber: number
  activeRightPane: RightPane
  annotationActionId: string | null
  annotationAnchor: ManuscriptSelectionAnchor | null
  annotationCategory: ManuscriptAnnotationCategory
  annotationDraft: string
  annotationSave: AnnotationSaveState
  annotationVisibility: AnnotationVisibility
  annotations: ManuscriptAnnotation[]
  annotationsLoading: boolean
  bookId: string
  characterCardDraft: ManuscriptCharacterCardDraft
  characterCardEditing: boolean
  characterCardSaving: boolean
  characters: Character[]
  chapterManualNotes: BookNote[]
  draftSurfaceMode: DraftSurfaceMode
  editNoteBody: string
  editNoteTitle: string
  editingNoteId: string | null
  editingNoteSaving: boolean
  editorMode: EditorMode
  fullBookApproxPages: number
  fullBookPageMap: FullBookPageMapItem[]
  fullBookPageSummaryLabel: string
  fullBookReferenceItems: ManuscriptReferenceItem[]
  generalNotes: BookNote[]
  gotoPageInput: string
  inspectorClasses: InspectorClasses
  isDark: boolean
  jumpTarget: number | null
  noteBody: string
  noteBodyText: string
  noteScope: NoteScope
  noteTitle: string
  notesLoading: boolean
  plotThreads: PlotThread[]
  review: EditorialReview | null
  reviewPassages: EditorialReviewPassage[]
  saveStateByTarget: Partial<Record<SaveTarget, SaveState>>
  savingNote: boolean
  selectedCharacter: Character | null
  synopsis: ManuscriptSynopsis | null
  onAnnotationCategoryChange: (category: ManuscriptAnnotationCategory) => void
  onAnnotationDraftChange: (value: string) => void
  onAnnotationVisibilityChange: (visibility: AnnotationVisibility) => void
  onBackToCharacters: () => void
  onCancelAnnotation: () => void
  onCancelEditingNote: () => void
  onCancelCharacterEdit: () => void
  onCharacterDraftFieldChange: (field: keyof ManuscriptCharacterCardDraft, value: string) => void
  onCharacterNameClick: (characterName: string) => void
  onDownloadContinuityReport: () => void
  onEditCharacterCard: () => void
  onEditNoteBodyChange: (value: string) => void
  onEditNoteTitleChange: (value: string) => void
  onGotoPageInputChange: (value: string) => void
  onJumpToAnnotation: (annotation: ManuscriptAnnotation) => void
  onJumpToChapter: (chapterNumber: number) => void
  onJumpToPage: (page: number) => void
  onNoteBodyChange: (html: string, text: string) => void
  onNoteScopeChange: (scope: NoteScope) => void
  onNoteTitleChange: (value: string) => void
  onOpenAnnotationComposer: () => void
  onOpenCharacter: (character: Character) => void
  onRemoveAnnotation: (annotationId: string) => void
  onRemoveNote: (noteId: string) => void
  onRightPaneChange: (pane: RightPane) => void
  onSaveAnnotation: () => void
  onSaveCharacterCard: () => void
  onSaveCharacterNote: (character: Character) => void
  onSaveContinuityIssueAsNote: (issue: EditorialContinuityIssue) => void
  onSaveEditedNote: () => void
  onSaveNote: () => void
  onSaveWorkspaceVaultNote: () => void
  onStartEditingNote: (note: BookNote) => void
  onUpdateAnnotationStatus: (annotation: ManuscriptAnnotation, status: "open" | "resolved") => void
}

export function ManuscriptAnalysisRail({
  activeAnnotationId,
  activeChapterNumber,
  activeRightPane,
  annotationActionId,
  annotationAnchor,
  annotationCategory,
  annotationDraft,
  annotationSave,
  annotationVisibility,
  annotations,
  annotationsLoading,
  bookId,
  characterCardDraft,
  characterCardEditing,
  characterCardSaving,
  characters,
  chapterManualNotes,
  draftSurfaceMode,
  editNoteBody,
  editNoteTitle,
  editingNoteId,
  editingNoteSaving,
  editorMode,
  fullBookApproxPages,
  fullBookPageMap,
  fullBookPageSummaryLabel,
  fullBookReferenceItems,
  generalNotes,
  gotoPageInput,
  inspectorClasses,
  isDark,
  jumpTarget,
  noteBody,
  noteBodyText,
  noteScope,
  noteTitle,
  notesLoading,
  plotThreads,
  review,
  reviewPassages,
  saveStateByTarget,
  savingNote,
  selectedCharacter,
  synopsis,
  onAnnotationCategoryChange,
  onAnnotationDraftChange,
  onAnnotationVisibilityChange,
  onBackToCharacters,
  onCancelAnnotation,
  onCancelEditingNote,
  onCancelCharacterEdit,
  onCharacterDraftFieldChange,
  onCharacterNameClick,
  onDownloadContinuityReport,
  onEditCharacterCard,
  onEditNoteBodyChange,
  onEditNoteTitleChange,
  onGotoPageInputChange,
  onJumpToAnnotation,
  onJumpToChapter,
  onJumpToPage,
  onNoteBodyChange,
  onNoteScopeChange,
  onNoteTitleChange,
  onOpenAnnotationComposer,
  onOpenCharacter,
  onRemoveAnnotation,
  onRemoveNote,
  onRightPaneChange,
  onSaveAnnotation,
  onSaveCharacterCard,
  onSaveCharacterNote,
  onSaveContinuityIssueAsNote,
  onSaveEditedNote,
  onSaveNote,
  onSaveWorkspaceVaultNote,
  onStartEditingNote,
  onUpdateAnnotationStatus,
}: ManuscriptAnalysisRailProps) {
  return (
    <aside className={inspectorClasses.rail}>
      <div className={`border-b p-2 ${isDark ? "border-white/[0.08]" : "border-stone-200"}`}>
        <div className="grid grid-cols-2 gap-1" role="tablist" aria-label="Analysis workspace panels">
          {([
            ["insights", "Insights"],
            ["character", "Characters"],
          ] as const).map(([pane, label]) => (
            <button
              key={pane}
              type="button"
              role="tab"
              aria-selected={activeRightPane === pane}
              onClick={() => onRightPaneChange(pane)}
              className={`rounded-sm border-b-2 px-3 py-2.5 text-sm font-semibold transition ${
                activeRightPane === pane
                  ? isDark
                    ? "border-teal-300 bg-white/[0.04] text-white"
                    : "border-teal-600 bg-stone-100 text-stone-950"
                  : isDark
                    ? "border-transparent text-slate-300 hover:bg-white/[0.04]"
                    : "border-transparent text-stone-600 hover:bg-stone-50"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {activeRightPane === "character" ? (
        <ManuscriptCharacterPane
          characterCardDraft={characterCardDraft}
          characterCardEditing={characterCardEditing}
          characterCardSaving={characterCardSaving}
          characters={characters}
          inspectorClasses={inspectorClasses}
          isDark={isDark}
          selectedCharacter={selectedCharacter}
          onBackToCharacters={onBackToCharacters}
          onCancelEdit={onCancelCharacterEdit}
          onDraftFieldChange={onCharacterDraftFieldChange}
          onEditCard={onEditCharacterCard}
          onOpenCharacter={onOpenCharacter}
          onSaveCard={onSaveCharacterCard}
          onSaveCharacterNote={onSaveCharacterNote}
        />
      ) : null}

      {activeRightPane === "insights" ? (
        <>
          {editorMode === "book" ? (
            <>
              <ManuscriptPageNavigator
                draftSurfaceMode={draftSurfaceMode}
                fullBookApproxPages={fullBookApproxPages}
                fullBookPageMap={fullBookPageMap}
                fullBookPageSummaryLabel={fullBookPageSummaryLabel}
                gotoPageInput={gotoPageInput}
                inspectorClasses={inspectorClasses}
                isDark={isDark}
                jumpTarget={jumpTarget}
                onGotoPageInputChange={onGotoPageInputChange}
                onJumpToPage={onJumpToPage}
              />

              <ManuscriptReferences
                fullBookPageMap={fullBookPageMap}
                fullBookReferenceItems={fullBookReferenceItems}
                inspectorClasses={inspectorClasses}
                isDark={isDark}
                onJumpToChapter={onJumpToChapter}
              />
            </>
          ) : null}

          <ManuscriptInsightsSummaryPanels
            bookId={bookId}
            inspectorClasses={inspectorClasses}
            isDark={isDark}
            plotThreads={plotThreads}
            reviewPassages={reviewPassages}
            synopsis={synopsis}
            onJumpToChapter={onJumpToChapter}
          />

          <ManuscriptContinuityPanel
            bookId={bookId}
            inspectorClasses={inspectorClasses}
            isDark={isDark}
            review={review}
            onDownloadContinuityReport={onDownloadContinuityReport}
            onJumpToChapter={onJumpToChapter}
            onSaveContinuityIssueAsNote={onSaveContinuityIssueAsNote}
          />
        </>
      ) : (
        <>
          <ManuscriptNoteComposer
            activeChapterNumber={activeChapterNumber}
            bookId={bookId}
            characters={characters}
            inspectorClasses={inspectorClasses}
            isDark={isDark}
            noteBody={noteBody}
            noteBodyText={noteBodyText}
            noteScope={noteScope}
            noteTitle={noteTitle}
            saveStateByTarget={saveStateByTarget}
            savingNote={savingNote}
            onCharacterClick={onCharacterNameClick}
            onNoteBodyChange={onNoteBodyChange}
            onNoteScopeChange={onNoteScopeChange}
            onNoteTitleChange={onNoteTitleChange}
            onSaveNote={onSaveNote}
            onSaveWorkspaceVaultNote={onSaveWorkspaceVaultNote}
          />

          <ManuscriptAnnotationComposer
            annotationActionId={annotationActionId}
            annotationAnchor={annotationAnchor}
            annotationCategory={annotationCategory}
            annotationDraft={annotationDraft}
            annotationSave={annotationSave}
            annotationVisibility={annotationVisibility}
            inspectorClasses={inspectorClasses}
            isDark={isDark}
            onAnnotationCategoryChange={onAnnotationCategoryChange}
            onAnnotationDraftChange={onAnnotationDraftChange}
            onAnnotationVisibilityChange={onAnnotationVisibilityChange}
            onCancelAnnotation={onCancelAnnotation}
            onOpenAnnotationComposer={onOpenAnnotationComposer}
            onSaveAnnotation={onSaveAnnotation}
          />

          <ManuscriptAnnotationList
            activeAnnotationId={activeAnnotationId}
            annotationActionId={annotationActionId}
            annotations={annotations}
            annotationsLoading={annotationsLoading}
            inspectorClasses={inspectorClasses}
            isDark={isDark}
            onJumpToAnnotation={onJumpToAnnotation}
            onRemoveAnnotation={onRemoveAnnotation}
            onUpdateAnnotationStatus={onUpdateAnnotationStatus}
          />

          <ManuscriptNoteLists
            chapterNotes={chapterManualNotes}
            editNoteBody={editNoteBody}
            editNoteTitle={editNoteTitle}
            editingNoteId={editingNoteId}
            editingNoteSaving={editingNoteSaving}
            generalNotes={generalNotes}
            inspectorClasses={inspectorClasses}
            isDark={isDark}
            notesLoading={notesLoading}
            onCancelEditingNote={onCancelEditingNote}
            onEditNoteBodyChange={onEditNoteBodyChange}
            onEditNoteTitleChange={onEditNoteTitleChange}
            onRemoveNote={onRemoveNote}
            onSaveEditedNote={onSaveEditedNote}
            onStartEditingNote={onStartEditingNote}
          />
        </>
      )}
    </aside>
  )
}
