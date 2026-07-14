"use client"

import type { Dispatch, SetStateAction } from "react"

import type {
  ManuscriptEditorPanelProps,
  ManuscriptEditorStatusFooterProps,
  ManuscriptNonWriteWorkspaceSectionProps,
} from "./manuscriptPage.layout"

type BuildManuscriptEditorWorkspacePropsParams = {
  activeChapterNeedsReprocess: boolean
  activeChapterNumber: number
  activeFindIndex: number
  autosaveMetaLabel: (chapterNumber: number) => string | null
  bookDrafts: ManuscriptEditorPanelProps["bookDrafts"]
  bookTitle?: string | null
  bookId: string
  chapterApproxPages: number
  chapterHeading: string
  chapterIndexFormat: ManuscriptEditorPanelProps["chapterIndexFormat"]
  chapterListItems: ManuscriptEditorPanelProps["chapterListItems"]
  chapterPageSummaryLabel: string
  chapterPreviewSections: ManuscriptEditorPanelProps["chapterPreviewSections"]
  chapterReadingTime: string
  chapterRefs: ManuscriptEditorPanelProps["chapterRefs"]
  chapterSceneCount: number
  chapterTitle: string
  chapterWordCount: number
  characters: ManuscriptEditorPanelProps["characters"]
  continuityLoading: boolean
  draftSurfaceMode: ManuscriptEditorPanelProps["draftSurfaceMode"]
  draftSurfaceSummaryLabel: string
  editorMode: ManuscriptEditorPanelProps["editorMode"]
  firstLineIndent: boolean
  fontFamily: ManuscriptNonWriteWorkspaceSectionProps["fontFamily"]
  fontSize: number
  fullBookLoading: boolean
  fullBookPageSummaryLabel: string
  fullBookPreviewSections: ManuscriptEditorPanelProps["fullBookPreviewSections"]
  fullBookWordCount: number
  html: string
  indexFormat: string
  inlineContinuity: ManuscriptNonWriteWorkspaceSectionProps["inlineContinuity"]
  isDark: boolean
  jumpTarget: number | null
  leftRailVisible: boolean
  lineHeight: number
  logicSelectionText: string
  pagedPreviewPreset: ManuscriptEditorPanelProps["pagedPreviewPreset"]
  preWritingCheck: ManuscriptNonWriteWorkspaceSectionProps["preWritingCheck"]
  recallCharacter: ManuscriptNonWriteWorkspaceSectionProps["recallCharacter"]
  recallLoading: boolean
  recallQuery: string
  recallResults: ManuscriptNonWriteWorkspaceSectionProps["recallResults"]
  replaceExisting: boolean
  replaceQuery: string
  replaceValue: string
  reprocessingChapterNumber: number | null
  saveDisabled: boolean
  saveStateLabel: ManuscriptEditorPanelProps["saveStateLabel"]
  saveStateTone: ManuscriptEditorPanelProps["saveStateTone"]
  saving: boolean
  searchInputRef: ManuscriptNonWriteWorkspaceSectionProps["searchInputRef"]
  sheetStyle: ManuscriptEditorPanelProps["sheetStyle"]
  showEditorSettings: boolean
  showPageGuides: boolean
  showPageSetup: boolean
  showSearchTools: boolean
  text: string
  formatChapterHeading: ManuscriptEditorPanelProps["formatChapterHeading"]
  onChapterEditorBlur: ManuscriptEditorPanelProps["onChapterEditorBlur"]
  onChapterEditorFocus: ManuscriptEditorPanelProps["onChapterEditorFocus"]
  onChapterHeadingBlur: (value: string, chapterNumber: number, chapterTitle: string) => Promise<void> | void
  onChapterPageCountChange: ManuscriptEditorPanelProps["onChapterPageCountChange"]
  onChapterTextChange: ManuscriptEditorPanelProps["onChapterTextChange"]
  onCharacterClick: ManuscriptEditorPanelProps["onCharacterClick"]
  onDraftSurfaceModeChange: ManuscriptNonWriteWorkspaceSectionProps["onDraftSurfaceModeChange"]
  onEditorModeChange: ManuscriptNonWriteWorkspaceSectionProps["onEditorModeChange"]
  onEditorSettingsToggle: ManuscriptEditorPanelProps["onEditorSettingsToggle"]
  onFontFamilyChange: ManuscriptNonWriteWorkspaceSectionProps["onFontFamilyChange"]
  onFullBookDraftChange: ManuscriptEditorPanelProps["onFullBookDraftChange"]
  onFullBookEditorBlur: ManuscriptEditorPanelProps["onFullBookEditorBlur"]
  onFullBookEditorFocus: ManuscriptEditorPanelProps["onFullBookEditorFocus"]
  onFullBookHeadingBlur: ManuscriptEditorPanelProps["onFullBookHeadingBlur"]
  onFullBookPageCountChange: ManuscriptEditorPanelProps["onFullBookPageCountChange"]
  onIndexFormatChange: ManuscriptEditorPanelProps["onIndexFormatChange"]
  onJumpToChapter: ManuscriptNonWriteWorkspaceSectionProps["onJumpToChapter"]
  onLineHeightChange: ManuscriptNonWriteWorkspaceSectionProps["onLineHeightChange"]
  onRecallQueryChange: ManuscriptNonWriteWorkspaceSectionProps["onRecallQueryChange"]
  onReplaceEverywhere: ManuscriptNonWriteWorkspaceSectionProps["onReplaceEverywhere"]
  onReplaceExistingToggle: ManuscriptEditorPanelProps["onReplaceExistingToggle"]
  onReplaceInCurrentChapter: ManuscriptNonWriteWorkspaceSectionProps["onReplaceInCurrentChapter"]
  onReplaceQueryChange: ManuscriptNonWriteWorkspaceSectionProps["onReplaceQueryChange"]
  onReplaceValueChange: ManuscriptNonWriteWorkspaceSectionProps["onReplaceValueChange"]
  onSaveChapter: () => Promise<void> | void
  onSaveChapterDraft: ManuscriptEditorPanelProps["onSaveChapterDraft"]
  onSaveFullBook: ManuscriptEditorStatusFooterProps["onSaveFullBook"]
  onShowLeftRailChange: Dispatch<SetStateAction<boolean>>
  setFirstLineIndent: Dispatch<SetStateAction<boolean>>
  setFontSize: Dispatch<SetStateAction<number>>
  setFontSizeLocked: Dispatch<SetStateAction<boolean>>
  setShowPageGuides: Dispatch<SetStateAction<boolean>>
  setShowPageSetup: Dispatch<SetStateAction<boolean>>
  setShowSearchTools: Dispatch<SetStateAction<boolean>>
  onAddComment: ManuscriptEditorPanelProps["onAddComment"]
  onNotesShortcut: ManuscriptEditorPanelProps["onNotesShortcut"]
  onReprocessChapter: () => Promise<void> | void
}

export function buildManuscriptEditorWorkspaceProps({
  activeChapterNeedsReprocess,
  activeChapterNumber,
  activeFindIndex,
  autosaveMetaLabel,
  bookDrafts,
  bookId,
  bookTitle,
  chapterApproxPages,
  chapterHeading,
  chapterIndexFormat,
  chapterListItems,
  chapterPageSummaryLabel,
  chapterPreviewSections,
  chapterReadingTime,
  chapterRefs,
  chapterSceneCount,
  chapterTitle,
  chapterWordCount,
  characters,
  continuityLoading,
  draftSurfaceMode,
  draftSurfaceSummaryLabel,
  editorMode,
  firstLineIndent,
  fontFamily,
  fontSize,
  fullBookLoading,
  fullBookPageSummaryLabel,
  fullBookPreviewSections,
  fullBookWordCount,
  html,
  indexFormat,
  inlineContinuity,
  isDark,
  jumpTarget,
  leftRailVisible,
  lineHeight,
  logicSelectionText,
  pagedPreviewPreset,
  preWritingCheck,
  recallCharacter,
  recallLoading,
  recallQuery,
  recallResults,
  replaceExisting,
  replaceQuery,
  replaceValue,
  reprocessingChapterNumber,
  saveDisabled,
  saveStateLabel,
  saveStateTone,
  saving,
  searchInputRef,
  sheetStyle,
  showEditorSettings,
  showPageGuides,
  showPageSetup,
  showSearchTools,
  text,
  formatChapterHeading,
  onAddComment,
  onChapterEditorBlur,
  onChapterEditorFocus,
  onChapterHeadingBlur,
  onChapterPageCountChange,
  onChapterTextChange,
  onCharacterClick,
  onDraftSurfaceModeChange,
  onEditorModeChange,
  onEditorSettingsToggle,
  onFontFamilyChange,
  onFullBookDraftChange,
  onFullBookEditorBlur,
  onFullBookEditorFocus,
  onFullBookHeadingBlur,
  onFullBookPageCountChange,
  onIndexFormatChange,
  onJumpToChapter,
  onLineHeightChange,
  onNotesShortcut,
  onRecallQueryChange,
  onReplaceEverywhere,
  onReplaceExistingToggle,
  onReplaceInCurrentChapter,
  onReplaceQueryChange,
  onReplaceValueChange,
  onReprocessChapter,
  onSaveChapter,
  onSaveChapterDraft,
  onSaveFullBook,
  onShowLeftRailChange,
  setFirstLineIndent,
  setFontSize,
  setFontSizeLocked,
  setShowPageGuides,
  setShowPageSetup,
  setShowSearchTools,
}: BuildManuscriptEditorWorkspacePropsParams) {
  const editorPanelProps: ManuscriptEditorPanelProps = {
    activeChapterNeedsReprocess,
    activeChapterNumber,
    autosaveMetaLabel: autosaveMetaLabel(activeChapterNumber),
    bookDrafts,
    bookTitle,
    chapterApproxPages,
    chapterHeading,
    chapterIndexFormat,
    chapterListItems,
    chapterPreviewSections,
    chapterReadingTime,
    chapterRefs,
    chapterSceneCount,
    chapterWordCount,
    characters,
    draftSurfaceMode,
    editorMode,
    firstLineIndent,
    fullBookLoading,
    fullBookPreviewSections,
    html,
    indexFormat,
    isDark,
    jumpTarget,
    lineHeight,
    pagedPreviewPreset,
    replaceExisting,
    reprocessingChapterNumber,
    saveDisabled,
    saveStateLabel,
    saveStateTone,
    saving,
    sheetStyle,
    showEditorSettings,
    showPageGuides,
    text,
    formatChapterHeading,
    onAddComment,
    onChapterEditorBlur,
    onChapterEditorFocus,
    onChapterHeadingBlur: (value) => void onChapterHeadingBlur(value, activeChapterNumber, chapterTitle),
    onChapterPageCountChange,
    onChapterTextChange,
    onCharacterClick,
    onEditorSettingsToggle,
    onFullBookDraftChange,
    onFullBookEditorBlur,
    onFullBookEditorFocus,
    onFullBookHeadingBlur,
    onFullBookPageCountChange,
    onIndexFormatChange,
    onNotesShortcut,
    onReprocessChapter: () => void onReprocessChapter(),
    onReplaceExistingToggle,
    onSaveChapter: () => void onSaveChapter(),
    onSaveChapterDraft,
  }

  const editorStatusFooterProps: ManuscriptEditorStatusFooterProps = {
    bookDrafts,
    draftSurfaceMode,
    editorMode,
    isDark,
    saving,
    onSaveFullBook,
  }

  const nonWriteWorkspaceProps: ManuscriptNonWriteWorkspaceSectionProps = {
    activeChapterNumber,
    activeFindIndex,
    bookId,
    chapterPageSummaryLabel,
    chapterWordCount,
    continuityLoading,
    draftSurfaceMode,
    draftSurfaceSummaryLabel,
    editorMode,
    firstLineIndent,
    fontFamily,
    fontSize,
    fullBookPageSummaryLabel,
    fullBookWordCount,
    inlineContinuity,
    isDark,
    leftRailVisible,
    lineHeight,
    logicSelectionText,
    preWritingCheck,
    recallCharacter,
    recallLoading,
    recallQuery,
    recallResults,
    replaceQuery,
    replaceValue,
    searchInputRef,
    showPageGuides,
    showPageSetup,
    showSearchTools,
    onDraftSurfaceModeChange,
    onEditorModeChange,
    onFontFamilyChange,
    onFontSizeChange: (value) => {
      setFontSize(value)
      setFontSizeLocked(true)
    },
    onJumpToChapter,
    onLineHeightChange,
    onRecallQueryChange,
    onReplaceEverywhere,
    onReplaceInCurrentChapter,
    onReplaceQueryChange,
    onReplaceValueChange,
    onToggleFirstLineIndent: () => setFirstLineIndent((value) => !value),
    onToggleLeftRail: () => onShowLeftRailChange((value) => !value),
    onTogglePageSetup: () => setShowPageSetup((value) => !value),
    onToggleSearchTools: () => setShowSearchTools((value) => !value),
    onToggleShowPageGuides: () => setShowPageGuides((value) => !value),
  }

  return {
    editorPanelProps,
    editorStatusFooterProps,
    nonWriteWorkspaceProps,
  }
}
