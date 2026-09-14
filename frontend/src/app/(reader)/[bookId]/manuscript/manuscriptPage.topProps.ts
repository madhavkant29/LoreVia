"use client"

import type { Dispatch, SetStateAction } from "react"

import type { WriterWorkspace } from "@/types/book"

import type {
  ManuscriptHeaderProps,
  ManuscriptPlanWorkspaceSectionProps,
  ManuscriptSelectionMenuProps,
} from "./manuscriptPage.layout"

type SaveWorkspace = (patch: Partial<WriterWorkspace>, options?: { silent?: boolean }) => Promise<void>

type BuildManuscriptTopPropsParams = {
  activeLastSavedAt: ManuscriptHeaderProps["activeLastSavedAt"]
  activePreset: ManuscriptHeaderProps["activePreset"]
  activeSaveState: ManuscriptHeaderProps["activeSaveState"]
  autoReprocessEnabled: boolean
  bookGoalProgress: number | null
  bookId: string
  bookTitle?: string | null
  chapterApproxPages: number
  chapterGoalProgress: number | null
  chapterVersionsCount: number
  chapterWordCount: number
  compileFormatSetter: ManuscriptHeaderProps["compileFormatSetter"]
  draftSurfaceMode: ManuscriptHeaderProps["draftSurfaceMode"]
  editorMode: ManuscriptHeaderProps["editorMode"]
  emotionalArc: ManuscriptPlanWorkspaceSectionProps["emotionalArc"]
  exporting: ManuscriptHeaderProps["exporting"]
  failedSaveByTarget: ManuscriptHeaderProps["failedSaveByTarget"]
  focusMode: boolean
  fullBookApproxPages: number
  fullBookWordCount: number
  includeTableOfContentsOnExport: boolean
  isDark: boolean
  newCorkboardTitle: string
  normalizedProcessingStatus: ManuscriptHeaderProps["normalizedProcessingStatus"]
  processingRetrying: boolean
  readability: ManuscriptPlanWorkspaceSectionProps["readability"]
  readabilityLoading: boolean
  reprocessCta: ManuscriptHeaderProps["reprocessCta"]
  reprocessing: boolean
  saveStateByTarget: ManuscriptHeaderProps["saveStateByTarget"]
  saveWorkspace: SaveWorkspace
  selectionMenu: ManuscriptSelectionMenuProps["selectionMenu"]
  setDraftSurfaceMode: ManuscriptHeaderProps["onDraftSurfaceModeChange"]
  setEditorMode: ManuscriptHeaderProps["onEditorModeChange"]
  setFocusMode: ManuscriptHeaderProps["onFocusModeChange"]
  setIncludeTableOfContentsOnExport: ManuscriptHeaderProps["onIncludeTableOfContentsChange"]
  setNewCorkboardTitle: Dispatch<SetStateAction<string>>
  setShowCompileDialog: ManuscriptHeaderProps["onCompileDialogOpenChange"]
  setShowEditorSettings: ManuscriptHeaderProps["onShowEditorSettingsChange"]
  setShowExportMenu: ManuscriptHeaderProps["onExportMenuOpenChange"]
  setShowReprocessConfirm: ManuscriptHeaderProps["onShowReprocessConfirmChange"]
  setWorkspaceTab: ManuscriptHeaderProps["onWorkspaceTabChange"]
  setWriterWorkspace: Dispatch<SetStateAction<WriterWorkspace | null>>
  showExportMenu: boolean
  tighteningSelection: boolean
  workspaceSaving: boolean
  workspaceTab: ManuscriptHeaderProps["workspaceTab"]
  writerWorkspace: WriterWorkspace | null
  onAddCharacterFromSelection: ManuscriptSelectionMenuProps["onAddCharacterFromSelection"]
  onAddCorkboardCard: ManuscriptPlanWorkspaceSectionProps["onAddCorkboardCard"]
  onAnnotate: ManuscriptSelectionMenuProps["onAnnotate"]
  onApplyTemplate: ManuscriptPlanWorkspaceSectionProps["onApplyTemplate"]
  onCheckConsistency: ManuscriptSelectionMenuProps["onCheckConsistency"]
  onOpenProject: ManuscriptHeaderProps["onOpenProject"]
  onPrint: ManuscriptHeaderProps["onPrint"]
  onRetryProcessing: ManuscriptHeaderProps["onRetryProcessing"]
  onSaveTemplates: ManuscriptPlanWorkspaceSectionProps["onSaveTemplates"]
  onTightenSelectedText: ManuscriptSelectionMenuProps["onTightenSelectedText"]
  onToggleAutoReprocess: (enabled: boolean) => Promise<void> | void
  onUpdateCardLane: ManuscriptPlanWorkspaceSectionProps["onUpdateCardLane"]
}

export function buildManuscriptTopProps({
  activeLastSavedAt,
  activePreset,
  activeSaveState,
  autoReprocessEnabled,
  bookGoalProgress,
  bookId,
  bookTitle,
  chapterApproxPages,
  chapterGoalProgress,
  chapterVersionsCount,
  chapterWordCount,
  compileFormatSetter,
  draftSurfaceMode,
  editorMode,
  emotionalArc,
  exporting,
  failedSaveByTarget,
  focusMode,
  fullBookApproxPages,
  fullBookWordCount,
  includeTableOfContentsOnExport,
  isDark,
  newCorkboardTitle,
  normalizedProcessingStatus,
  processingRetrying,
  readability,
  readabilityLoading,
  reprocessCta,
  reprocessing,
  saveStateByTarget,
  saveWorkspace,
  selectionMenu,
  setDraftSurfaceMode,
  setEditorMode,
  setFocusMode,
  setIncludeTableOfContentsOnExport,
  setNewCorkboardTitle,
  setShowCompileDialog,
  setShowEditorSettings,
  setShowExportMenu,
  setShowReprocessConfirm,
  setWorkspaceTab,
  setWriterWorkspace,
  showExportMenu,
  tighteningSelection,
  workspaceSaving,
  workspaceTab,
  writerWorkspace,
  onAddCharacterFromSelection,
  onAddCorkboardCard,
  onAnnotate,
  onApplyTemplate,
  onCheckConsistency,
  onOpenProject,
  onPrint,
  onRetryProcessing,
  onSaveTemplates,
  onTightenSelectedText,
  onToggleAutoReprocess,
  onUpdateCardLane,
}: BuildManuscriptTopPropsParams) {
  const selectionMenuProps: ManuscriptSelectionMenuProps = {
    bookId,
    draftSurfaceMode,
    editorMode,
    isDark,
    selectionMenu,
    tighteningSelection,
    workspaceTab,
    onAddCharacterFromSelection,
    onAnnotate,
    onCheckConsistency,
    onTightenSelectedText,
  }

  const headerProps: ManuscriptHeaderProps = {
    activeLastSavedAt,
    activePreset,
    activeSaveState,
    autoReprocessEnabled,
    bookTitle,
    compileFormatSetter,
    draftSurfaceMode,
    editorMode,
    exporting,
    failedSaveByTarget,
    focusMode,
    homeHref: `/${bookId}`,
    includeTableOfContentsOnExport,
    isDark,
    normalizedProcessingStatus,
    processingRetrying,
    reprocessCta,
    reprocessing,
    saveStateByTarget,
    showExportMenu,
    workspaceSaving,
    workspaceTab,
    onAutoReprocessChange: (enabled) => void onToggleAutoReprocess(enabled),
    onCompileDialogOpenChange: setShowCompileDialog,
    onDraftSurfaceModeChange: setDraftSurfaceMode,
    onEditorModeChange: setEditorMode,
    onExportMenuOpenChange: setShowExportMenu,
    onFocusModeChange: setFocusMode,
    onIncludeTableOfContentsChange: setIncludeTableOfContentsOnExport,
    onOpenProject,
    onPresetChange: (nextPreset) => {
      void saveWorkspace({
        publishing: {
          ...(writerWorkspace?.publishing ?? { trim_size: "6x9", include_title_page: true, mirror_margins: true }),
          active_preset: nextPreset,
        },
      }, { silent: true })
    },
    onPrint,
    onRetryProcessing,
    onShowEditorSettingsChange: setShowEditorSettings,
    onShowReprocessConfirmChange: setShowReprocessConfirm,
    onWorkspaceTabChange: setWorkspaceTab,
  }

  const planWorkspaceProps: ManuscriptPlanWorkspaceSectionProps = {
    bookGoalProgress,
    chapterApproxPages,
    chapterGoalProgress,
    chapterVersionsCount,
    chapterWordCount,
    editorMode,
    emotionalArc,
    fullBookApproxPages,
    fullBookWordCount,
    isDark,
    newCorkboardTitle,
    readability,
    readabilityLoading,
    tighteningSelection,
    workspaceSaving,
    writerWorkspace,
    onAddCorkboardCard,
    onApplyTemplate,
    onNewCorkboardTitleChange: setNewCorkboardTitle,
    onSaveGoals: () => {
      if (writerWorkspace) void saveWorkspace({ word_count_goals: writerWorkspace.word_count_goals })
    },
    onSaveTemplates,
    onTightenSelectedText,
    onUpdateCardLane,
    onWordCountGoalChange: (field, value) => {
      setWriterWorkspace((current) => current ? { ...current, word_count_goals: { ...current.word_count_goals, [field]: value } } : current)
    },
  }

  return {
    headerProps,
    planWorkspaceProps,
    selectionMenuProps,
  }
}
