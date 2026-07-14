"use client"

import type { Dispatch, SetStateAction } from "react"

import type { BookNote } from "@/types/book"

import type {
  ManuscriptAnalysisRailProps,
  ManuscriptWriteRailProps,
} from "./manuscriptPage.layout"

type BuildManuscriptRightRailPropsParams = {
  activeAnnotationId: ManuscriptAnalysisRailProps["activeAnnotationId"]
  activeChapterContextCharacters: ManuscriptWriteRailProps["activeChapterContextCharacters"]
  activeChapterNumber: number
  activeRightPane: ManuscriptWriteRailProps["activeRightPane"]
  activeThreadSummary: ManuscriptWriteRailProps["activeThreadSummary"]
  annotationActionId: ManuscriptAnalysisRailProps["annotationActionId"]
  annotationAnchor: ManuscriptAnalysisRailProps["annotationAnchor"]
  annotationCategory: ManuscriptAnalysisRailProps["annotationCategory"]
  annotationDraft: string
  annotationSave: ManuscriptAnalysisRailProps["annotationSave"]
  annotationVisibility: ManuscriptAnalysisRailProps["annotationVisibility"]
  annotations: ManuscriptAnalysisRailProps["annotations"]
  annotationsLoading: boolean
  arcSummaryCharacter: ManuscriptWriteRailProps["arcSummaryCharacter"]
  bookId: string
  characterCardDraft: ManuscriptAnalysisRailProps["characterCardDraft"]
  characterCardEditing: boolean
  characterCardSaving: boolean
  characters: ManuscriptWriteRailProps["characters"]
  chapterAnnotationsCount: number
  chapterManualNotes: BookNote[]
  draftSurfaceMode: ManuscriptAnalysisRailProps["draftSurfaceMode"]
  editNoteBody: string
  editNoteTitle: string
  editingNoteId: string | null
  editingNoteSaving: boolean
  editorMode: ManuscriptAnalysisRailProps["editorMode"]
  fullBookApproxPages: number
  fullBookPageMap: ManuscriptAnalysisRailProps["fullBookPageMap"]
  fullBookPageSummaryLabel: string
  fullBookReferenceItems: ManuscriptAnalysisRailProps["fullBookReferenceItems"]
  generalNotes: BookNote[]
  gotoPageInput: string
  inspectorClasses: ManuscriptAnalysisRailProps["inspectorClasses"]
  isDark: boolean
  jumpTarget: number | null
  noteBody: string
  noteBodyText: string
  noteScope: ManuscriptAnalysisRailProps["noteScope"]
  noteTitle: string
  notesLoading: boolean
  plotThreads: ManuscriptWriteRailProps["plotThreads"]
  recentEventSummary: ManuscriptWriteRailProps["recentEventSummary"]
  review: ManuscriptWriteRailProps["review"]
  reviewPassages: ManuscriptAnalysisRailProps["reviewPassages"]
  saveStateByTarget: ManuscriptAnalysisRailProps["saveStateByTarget"]
  savingNote: boolean
  selectedCharCard: ManuscriptWriteRailProps["selectedCharCard"]
  setActiveRightPane: Dispatch<SetStateAction<ManuscriptWriteRailProps["activeRightPane"]>>
  setAnnotationCategory: ManuscriptAnalysisRailProps["onAnnotationCategoryChange"]
  setAnnotationDraft: ManuscriptAnalysisRailProps["onAnnotationDraftChange"]
  setAnnotationVisibility: ManuscriptAnalysisRailProps["onAnnotationVisibilityChange"]
  setCharCardEditing: Dispatch<SetStateAction<boolean>>
  setEditNoteBody: ManuscriptAnalysisRailProps["onEditNoteBodyChange"]
  setEditNoteTitle: ManuscriptAnalysisRailProps["onEditNoteTitleChange"]
  setGotoPageInput: ManuscriptAnalysisRailProps["onGotoPageInputChange"]
  setNoteScope: ManuscriptAnalysisRailProps["onNoteScopeChange"]
  setNoteTitle: ManuscriptAnalysisRailProps["onNoteTitleChange"]
  setNotes: Dispatch<SetStateAction<BookNote[]>>
  setSelectedCharCard: Dispatch<SetStateAction<ManuscriptWriteRailProps["selectedCharCard"]>>
  suggestions: ManuscriptWriteRailProps["suggestions"]
  synopsis: ManuscriptAnalysisRailProps["synopsis"]
  totalChapters: number | null
  vaultNotes: ManuscriptWriteRailProps["vaultNotes"]
  warningSummary: ManuscriptWriteRailProps["warningSummary"]
  onBackToCharacters: ManuscriptAnalysisRailProps["onBackToCharacters"]
  onCancelAnnotation: ManuscriptAnalysisRailProps["onCancelAnnotation"]
  onCancelEditingNote: ManuscriptAnalysisRailProps["onCancelEditingNote"]
  onCharacterDraftFieldChange: ManuscriptAnalysisRailProps["onCharacterDraftFieldChange"]
  onCharacterNameClick: ManuscriptAnalysisRailProps["onCharacterNameClick"]
  onDownloadContinuityReport: ManuscriptAnalysisRailProps["onDownloadContinuityReport"]
  onEditNoteBodyChange: ManuscriptAnalysisRailProps["onNoteBodyChange"]
  onJumpToAnnotation: ManuscriptAnalysisRailProps["onJumpToAnnotation"]
  onJumpToChapter: ManuscriptAnalysisRailProps["onJumpToChapter"]
  onJumpToPage: ManuscriptAnalysisRailProps["onJumpToPage"]
  onOpenAnnotationComposer: ManuscriptAnalysisRailProps["onOpenAnnotationComposer"]
  onOpenCharacter: ManuscriptAnalysisRailProps["onOpenCharacter"]
  onOpenRightPane: ManuscriptWriteRailProps["onOpenRightPane"]
  onRefetchNotes: () => Promise<unknown> | unknown
  onRefetchVaultNotes: () => Promise<unknown> | unknown
  onRemoveAnnotation: (annotationId: string) => Promise<void> | void
  onRemoveNote: ManuscriptAnalysisRailProps["onRemoveNote"]
  onSaveAnnotation: () => Promise<void> | void
  onSaveCharacterCard: ManuscriptAnalysisRailProps["onSaveCharacterCard"]
  onSaveCharacterNote: ManuscriptAnalysisRailProps["onSaveCharacterNote"]
  onSaveContinuityIssueAsNote: ManuscriptAnalysisRailProps["onSaveContinuityIssueAsNote"]
  onSaveEditedNote: ManuscriptAnalysisRailProps["onSaveEditedNote"]
  onSaveNote: ManuscriptAnalysisRailProps["onSaveNote"]
  onSaveWorkspaceVaultNote: () => Promise<unknown> | unknown
  onStartEditingNote: ManuscriptAnalysisRailProps["onStartEditingNote"]
  onTightenSelectedText: () => Promise<void> | void
  onUpdateAnnotationStatus: (annotation: Parameters<ManuscriptAnalysisRailProps["onUpdateAnnotationStatus"]>[0], status: Parameters<ManuscriptAnalysisRailProps["onUpdateAnnotationStatus"]>[1]) => Promise<void> | void
}

export function buildManuscriptRightRailProps({
  activeAnnotationId,
  activeChapterContextCharacters,
  activeChapterNumber,
  activeRightPane,
  activeThreadSummary,
  annotationActionId,
  annotationAnchor,
  annotationCategory,
  annotationDraft,
  annotationSave,
  annotationVisibility,
  annotations,
  annotationsLoading,
  arcSummaryCharacter,
  bookId,
  characterCardDraft,
  characterCardEditing,
  characterCardSaving,
  characters,
  chapterAnnotationsCount,
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
  recentEventSummary,
  review,
  reviewPassages,
  saveStateByTarget,
  savingNote,
  selectedCharCard,
  setActiveRightPane,
  setAnnotationCategory,
  setAnnotationDraft,
  setAnnotationVisibility,
  setCharCardEditing,
  setEditNoteBody,
  setEditNoteTitle,
  setGotoPageInput,
  setNoteScope,
  setNoteTitle,
  setNotes,
  setSelectedCharCard,
  suggestions,
  synopsis,
  totalChapters,
  vaultNotes,
  warningSummary,
  onBackToCharacters,
  onCancelAnnotation,
  onCancelEditingNote,
  onCharacterDraftFieldChange,
  onCharacterNameClick,
  onDownloadContinuityReport,
  onEditNoteBodyChange,
  onJumpToAnnotation,
  onJumpToChapter,
  onJumpToPage,
  onOpenAnnotationComposer,
  onOpenCharacter,
  onOpenRightPane,
  onRefetchNotes,
  onRefetchVaultNotes,
  onRemoveAnnotation,
  onRemoveNote,
  onSaveAnnotation,
  onSaveCharacterCard,
  onSaveCharacterNote,
  onSaveContinuityIssueAsNote,
  onSaveEditedNote,
  onSaveNote,
  onSaveWorkspaceVaultNote,
  onStartEditingNote,
  onTightenSelectedText,
  onUpdateAnnotationStatus,
}: BuildManuscriptRightRailPropsParams) {
  const writeRailProps: ManuscriptWriteRailProps = {
    activeChapterContextCharacters,
    activeChapterNumber,
    activeRightPane,
    activeThreadSummary,
    arcSummaryCharacter,
    bookId,
    chapterAnnotationsCount,
    chapterManualNotes,
    characters,
    generalNotes,
    isDark,
    plotThreads,
    recentEventSummary,
    review,
    selectedCharCard,
    suggestions,
    totalChapters,
    vaultNotes,
    warningSummary,
    onBookNoteSaved: (note) => {
      setNotes((current) => [note, ...current.filter((item) => item.id !== note.id)])
      void onRefetchNotes()
    },
    onClearSelectedCharCard: () => {
      setSelectedCharCard(null)
      setActiveRightPane("context")
    },
    onOpenCharCard: onOpenCharacter,
    onOpenRightPane,
    onTightenSelectedText: () => void onTightenSelectedText(),
    onVaultNoteSaved: () => {
      void onRefetchVaultNotes()
    },
  }

  const analysisRailProps: ManuscriptAnalysisRailProps = {
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
    selectedCharacter: selectedCharCard,
    synopsis,
    onAnnotationCategoryChange: setAnnotationCategory,
    onAnnotationDraftChange: setAnnotationDraft,
    onAnnotationVisibilityChange: setAnnotationVisibility,
    onBackToCharacters,
    onCancelAnnotation,
    onCancelEditingNote,
    onCancelCharacterEdit: () => setCharCardEditing(false),
    onCharacterDraftFieldChange,
    onCharacterNameClick,
    onDownloadContinuityReport,
    onEditCharacterCard: () => setCharCardEditing(true),
    onEditNoteBodyChange: setEditNoteBody,
    onEditNoteTitleChange: setEditNoteTitle,
    onGotoPageInputChange: setGotoPageInput,
    onJumpToAnnotation,
    onJumpToChapter,
    onJumpToPage,
    onNoteBodyChange: onEditNoteBodyChange,
    onNoteScopeChange: setNoteScope,
    onNoteTitleChange: setNoteTitle,
    onOpenAnnotationComposer,
    onOpenCharacter,
    onRemoveAnnotation: (annotationId) => void onRemoveAnnotation(annotationId),
    onRemoveNote,
    onRightPaneChange: setActiveRightPane,
    onSaveAnnotation: () => void onSaveAnnotation(),
    onSaveCharacterCard,
    onSaveCharacterNote,
    onSaveContinuityIssueAsNote,
    onSaveEditedNote,
    onSaveNote,
    onSaveWorkspaceVaultNote: () => void onSaveWorkspaceVaultNote(),
    onStartEditingNote,
    onUpdateAnnotationStatus: (annotation, status) => void onUpdateAnnotationStatus(annotation, status),
  }

  return {
    analysisRailProps,
    writeRailProps,
  }
}
