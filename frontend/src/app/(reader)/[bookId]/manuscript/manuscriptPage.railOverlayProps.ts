"use client"

import type { Dispatch, SetStateAction } from "react"

import type { ManuscriptOverlayStackProps, ManuscriptLeftRailProps } from "./manuscriptPage.layout"

type BuildManuscriptRailOverlayPropsParams = {
  activeChapterNumber: number
  activeLastSavedAt: ManuscriptOverlayStackProps["activeLastSavedAt"]
  activeSaveState: ManuscriptOverlayStackProps["activeSaveState"]
  addCharacterOpen: boolean
  addCharacterText: string
  bookGoalProgress: number | null
  bookId: string
  bookTargetWordCount: number
  bookTitle?: string | null
  chapterIndexFormat: ManuscriptLeftRailProps["chapterIndexFormat"]
  chapterRowStats: ManuscriptLeftRailProps["chapterRowStats"]
  chapterSearch: string
  chapterTitle: string
  chapterVersionDetail: ManuscriptLeftRailProps["chapterVersionDetail"]
  chapterVersionNameDraft: string
  chapterVersions: ManuscriptLeftRailProps["chapterVersions"]
  characters: ManuscriptOverlayStackProps["characters"]
  collapsedSceneGroups: ManuscriptLeftRailProps["collapsedSceneGroups"]
  compileFormat: ManuscriptOverlayStackProps["compileFormat"]
  currentText: string
  deletingChapterNumber: number | null
  dirtyDrafts: number[]
  draftChapterNumber: number | null
  draggedScene: ManuscriptLeftRailProps["draggedScene"]
  editingScene: ManuscriptOverlayStackProps["editingScene"]
  exporting: ManuscriptOverlayStackProps["exporting"]
  filteredChapterItems: ManuscriptLeftRailProps["filteredChapterItems"]
  filteredSceneGroups: ManuscriptLeftRailProps["filteredSceneGroups"]
  fullBookReadingTime: string
  fullBookWordCount: number
  includeSceneMetadataOnExport: boolean
  includeSceneMetadataOnImport: boolean
  includeTableOfContentsOnExport: boolean
  isDark: boolean
  manuscriptFrontMatter: ManuscriptOverlayStackProps["manuscriptFrontMatter"]
  pendingReprocessChapters: ManuscriptLeftRailProps["pendingReprocessChapters"]
  reprocessing: boolean
  reprocessingChapterNumber: number | null
  restoringSceneVersionId: string | null
  restoringVersionId: string | null
  saving: boolean
  sceneBodyDraft: string
  sceneChapterDraft: number | null
  sceneDescriptionDraft: string
  sceneDropTarget: ManuscriptLeftRailProps["sceneDropTarget"]
  sceneEditorOpen: boolean
  sceneHtmlDraft: string
  sceneOrderSaveState: ManuscriptLeftRailProps["sceneOrderSaveState"]
  sceneSaving: boolean
  sceneTitleDraft: string
  sceneVersionDetail: ManuscriptOverlayStackProps["sceneVersionDetail"]
  sceneVersionNameDraft: string
  sceneVersions: ManuscriptOverlayStackProps["sceneVersions"]
  selectedChapter: number | null
  setAddCharacterOpen: Dispatch<SetStateAction<boolean>>
  setChapterSearch: Dispatch<SetStateAction<string>>
  setSceneBodyDraft: Dispatch<SetStateAction<string>>
  setSceneChapterDraft: Dispatch<SetStateAction<number | null>>
  setSceneDescriptionDraft: Dispatch<SetStateAction<string>>
  setSceneDropTarget: Dispatch<SetStateAction<ManuscriptLeftRailProps["sceneDropTarget"]>>
  setSceneHtmlDraft: Dispatch<SetStateAction<string>>
  setSceneTitleDraft: Dispatch<SetStateAction<string>>
  setSceneVersionNameDraft: Dispatch<SetStateAction<string>>
  setShowCompileDialog: Dispatch<SetStateAction<boolean>>
  setShowReprocessConfirm: Dispatch<SetStateAction<boolean>>
  setChapterVersionNameDraft: Dispatch<SetStateAction<string>>
  setIncludeTableOfContentsOnExport: Dispatch<SetStateAction<boolean>>
  showCompileDialog: boolean
  showReprocessConfirm: boolean
  workspaceSaving: boolean
  workspaceTree: ManuscriptOverlayStackProps["workspaceTree"]
  writerWorkspace: ManuscriptOverlayStackProps["writerWorkspace"]
  onCharacterCreated: ManuscriptOverlayStackProps["onCharacterCreated"]
  onCloseSceneEditor: ManuscriptOverlayStackProps["onCloseSceneEditor"]
  onCompareSceneVersion: ManuscriptOverlayStackProps["onCompareSceneVersion"]
  onCompileManuscript: () => Promise<void> | void
  onCreateChapter: ManuscriptLeftRailProps["onCreateChapter"]
  onCreateChapterSnapshot: () => Promise<void> | void
  onCreateSceneSnapshot: () => Promise<void> | void
  onDragSceneStart: ManuscriptLeftRailProps["onDragSceneStart"]
  onIncludeSceneMetadataOnExportChange: ManuscriptOverlayStackProps["onIncludeSceneMetadataOnExportChange"]
  onIncludeSceneMetadataOnImportChange: (checked: boolean) => Promise<void> | void
  onInsertSceneIntoDraft: (scene: Parameters<ManuscriptLeftRailProps["onInsertSceneIntoDraft"]>[0]) => Promise<void> | void
  onOpenSceneEditor: ManuscriptLeftRailProps["onOpenSceneEditor"]
  onPrefetchChapter: ManuscriptLeftRailProps["onPrefetchChapter"]
  onPreviewChapterSnapshot: (versionId: string) => Promise<void> | void
  onRemoveChapter: (chapterNumber: number) => Promise<void> | void
  onRemoveScene: (scene: Parameters<ManuscriptLeftRailProps["onRemoveScene"]>[0]) => Promise<void> | void
  onReorderScenesInChapter: (chapterNumber: number, sceneId: string, targetIndex: number) => Promise<void> | void
  onReprocessChapter: (chapterNumber: number) => Promise<void> | void
  onReprocessConfirm: (previewFingerprint: string) => Promise<void> | void
  onResetSceneDragState: ManuscriptLeftRailProps["onResetSceneDragState"]
  onRestoreChapterSnapshot: (versionId: string) => Promise<void> | void
  onRestoreSceneSnapshot: (versionId: string) => Promise<void> | void
  onSave: () => Promise<void> | void
  onSaveScene: () => Promise<void> | void
  onSelectChapter: ManuscriptLeftRailProps["onSelectChapter"]
  onToggleSceneGroup: ManuscriptLeftRailProps["onToggleSceneGroup"]
  onUpdateFrontMatter: ManuscriptOverlayStackProps["onUpdateFrontMatter"]
}

export function buildManuscriptRailOverlayProps({
  activeChapterNumber,
  activeLastSavedAt,
  activeSaveState,
  addCharacterOpen,
  addCharacterText,
  bookGoalProgress,
  bookId,
  bookTargetWordCount,
  bookTitle,
  chapterIndexFormat,
  chapterRowStats,
  chapterSearch,
  chapterTitle,
  chapterVersionDetail,
  chapterVersionNameDraft,
  chapterVersions,
  characters,
  collapsedSceneGroups,
  compileFormat,
  currentText,
  deletingChapterNumber,
  dirtyDrafts,
  draftChapterNumber,
  draggedScene,
  editingScene,
  exporting,
  filteredChapterItems,
  filteredSceneGroups,
  fullBookReadingTime,
  fullBookWordCount,
  includeSceneMetadataOnExport,
  includeSceneMetadataOnImport,
  includeTableOfContentsOnExport,
  isDark,
  manuscriptFrontMatter,
  pendingReprocessChapters,
  reprocessing,
  reprocessingChapterNumber,
  restoringSceneVersionId,
  restoringVersionId,
  saving,
  sceneBodyDraft,
  sceneChapterDraft,
  sceneDescriptionDraft,
  sceneDropTarget,
  sceneEditorOpen,
  sceneHtmlDraft,
  sceneOrderSaveState,
  sceneSaving,
  sceneTitleDraft,
  sceneVersionDetail,
  sceneVersionNameDraft,
  sceneVersions,
  selectedChapter,
  setAddCharacterOpen,
  setChapterSearch,
  setChapterVersionNameDraft,
  setIncludeTableOfContentsOnExport,
  setSceneBodyDraft,
  setSceneChapterDraft,
  setSceneDescriptionDraft,
  setSceneDropTarget,
  setSceneHtmlDraft,
  setSceneTitleDraft,
  setSceneVersionNameDraft,
  setShowCompileDialog,
  setShowReprocessConfirm,
  showCompileDialog,
  showReprocessConfirm,
  workspaceSaving,
  workspaceTree,
  writerWorkspace,
  onCharacterCreated,
  onCloseSceneEditor,
  onCompareSceneVersion,
  onCompileManuscript,
  onCreateChapter,
  onCreateChapterSnapshot,
  onCreateSceneSnapshot,
  onDragSceneStart,
  onIncludeSceneMetadataOnExportChange,
  onIncludeSceneMetadataOnImportChange,
  onInsertSceneIntoDraft,
  onOpenSceneEditor,
  onPrefetchChapter,
  onPreviewChapterSnapshot,
  onRemoveChapter,
  onRemoveScene,
  onReorderScenesInChapter,
  onReprocessChapter,
  onReprocessConfirm,
  onResetSceneDragState,
  onRestoreChapterSnapshot,
  onRestoreSceneSnapshot,
  onSave,
  onSaveScene,
  onSelectChapter,
  onToggleSceneGroup,
  onUpdateFrontMatter,
}: BuildManuscriptRailOverlayPropsParams) {
  const overlayStackProps: ManuscriptOverlayStackProps = {
    activeChapterNumber,
    activeLastSavedAt,
    activeSaveState,
    addCharacterOpen,
    addCharacterText,
    bookId,
    characters,
    chapterTitle,
    compileFormat,
    editingScene,
    exporting,
    firstChapter: activeChapterNumber ?? undefined,
    fullBookWordCount,
    includeSceneMetadataOnExport,
    includeTableOfContentsOnExport,
    isDark,
    manuscriptFrontMatter,
    reprocessing,
    restoringSceneVersionId,
    saving,
    sceneBodyDraft,
    sceneChapterDraft,
    sceneDescriptionDraft,
    sceneEditorOpen,
    sceneHtmlDraft,
    sceneSaving,
    sceneTitleDraft,
    sceneVersionDetail,
    sceneVersionNameDraft,
    sceneVersions,
    showCompileDialog,
    showReprocessConfirm,
    workspaceSaving,
    workspaceTree,
    writerWorkspace,
    onAddCharacterClose: () => setAddCharacterOpen(false),
    onCharacterCreated,
    onCloseCompileDialog: () => setShowCompileDialog(false),
    onCloseSceneEditor,
    onCompareSceneVersion: (versionId) => void onCompareSceneVersion(versionId),
    onCompileManuscript: () => void onCompileManuscript(),
    onCreateSceneSnapshot: () => void onCreateSceneSnapshot(),
    onIncludeSceneMetadataOnExportChange,
    onIncludeTableOfContentsOnExportChange: setIncludeTableOfContentsOnExport,
    onReprocessCancel: () => setShowReprocessConfirm(false),
    onReprocessConfirm: (previewFingerprint) => void onReprocessConfirm(previewFingerprint),
    onRestoreSceneSnapshot: (versionId) => void onRestoreSceneSnapshot(versionId),
    onSave: () => void onSave(),
    onSaveScene: () => void onSaveScene(),
    onSceneChapterDraftChange: setSceneChapterDraft,
    onSceneDescriptionDraftChange: setSceneDescriptionDraft,
    onSceneDraftChange: (nextHtml, nextText) => {
      setSceneHtmlDraft(nextHtml)
      setSceneBodyDraft(nextText)
    },
    onSceneTitleDraftChange: setSceneTitleDraft,
    onSceneVersionNameDraftChange: setSceneVersionNameDraft,
    onUpdateFrontMatter,
  }

  const leftRailProps: ManuscriptLeftRailProps = {
    bookGoalProgress,
    bookId,
    bookTargetWordCount,
    bookTitle,
    chapterIndexFormat,
    chapterRowStats,
    chapterSearch,
    chapterVersionDetail,
    chapterVersionNameDraft,
    chapterVersions,
    collapsedSceneGroups,
    currentText,
    deletingChapterNumber,
    dirtyDrafts,
    draftChapterNumber,
    draggedScene,
    filteredChapterItems,
    filteredSceneGroups,
    fullBookReadingTime,
    fullBookWordCount,
    includeSceneMetadataOnImport,
    isDark,
    pendingReprocessChapters,
    reprocessingChapterNumber,
    restoringVersionId,
    sceneDropTarget,
    sceneOrderSaveState,
    selectedChapter,
    onChapterSearchChange: setChapterSearch,
    onCreateChapter,
    onCreateChapterSnapshot: () => void onCreateChapterSnapshot(),
    onCreateScene: () => onOpenSceneEditor(null),
    onDragSceneStart,
    onInsertSceneIntoDraft: (scene) => void onInsertSceneIntoDraft(scene),
    onOpenSceneEditor,
    onPrefetchChapter,
    onPreviewChapterSnapshot: (versionId) => void onPreviewChapterSnapshot(versionId),
    onRemoveChapter: (chapterNumber) => void onRemoveChapter(chapterNumber),
    onRemoveScene: (scene) => void onRemoveScene(scene),
    onReorderScenesInChapter: (chapterNumber, sceneId, targetIndex) => void onReorderScenesInChapter(chapterNumber, sceneId, targetIndex),
    onReprocessChapter: (chapterNumber) => void onReprocessChapter(chapterNumber),
    onResetSceneDragState,
    onRestoreChapterSnapshot: (versionId) => void onRestoreChapterSnapshot(versionId),
    onSceneDropTargetChange: setSceneDropTarget,
    onSceneMetadataImportChange: (checked) => void onIncludeSceneMetadataOnImportChange(checked),
    onSelectChapter,
    onToggleSceneGroup,
    onVersionNameChange: setChapterVersionNameDraft,
  }

  return {
    leftRailProps,
    overlayStackProps,
  }
}
