import { AddCharacterFromSelection } from "@/components/characters/AddCharacterFromSelection"
import type {
  ManuscriptFrontMatter,
  ManuscriptWorkspaceTree,
  NovelScene,
  SaveState,
  SceneVersion,
  SceneVersionDetail,
  WriterWorkspace,
} from "@/types/book"
import type { Character } from "@/types/character"

import { ManuscriptOverlayDialogs } from "./manuscriptPage.dynamic"
import { ManuscriptMobileFooter } from "./manuscriptPage.mobileFooter"
import { ManuscriptReprocessDialog } from "./manuscriptPage.reprocessDialog"

type CompileFormat = "pdf" | "docx" | "epub" | "vault"

type ManuscriptOverlayStackProps = {
  activeChapterNumber: number
  activeLastSavedAt?: string | Date | null
  activeSaveState: SaveState
  addCharacterOpen: boolean
  addCharacterText: string
  bookId: string
  characters: Character[]
  chapterTitle: string
  compileFormat: CompileFormat
  editingScene: NovelScene | null
  exporting: CompileFormat | null
  firstChapter?: number
  fullBookWordCount: number
  includeSceneMetadataOnExport: boolean
  includeTableOfContentsOnExport: boolean
  isDark: boolean
  manuscriptFrontMatter: ManuscriptFrontMatter | null
  reprocessing: boolean
  restoringSceneVersionId: string | null
  saving: boolean
  sceneBodyDraft: string
  sceneChapterDraft: number | null
  sceneDescriptionDraft: string
  sceneEditorOpen: boolean
  sceneHtmlDraft: string
  sceneSaving: boolean
  sceneTitleDraft: string
  sceneVersionDetail: SceneVersionDetail | null
  sceneVersionNameDraft: string
  sceneVersions: SceneVersion[]
  showCompileDialog: boolean
  showReprocessConfirm: boolean
  workspaceSaving: boolean
  workspaceTree: ManuscriptWorkspaceTree | null
  writerWorkspace: WriterWorkspace | null
  onAddCharacterClose: () => void
  onCharacterCreated: (character: Character) => void
  onCloseCompileDialog: () => void
  onCloseSceneEditor: () => void | Promise<void>
  onCompareSceneVersion: (versionId: string) => void
  onCompileManuscript: () => void
  onCreateSceneSnapshot: () => void
  onIncludeSceneMetadataOnExportChange: (checked: boolean) => void
  onIncludeTableOfContentsOnExportChange: (checked: boolean) => void
  onReprocessCancel: () => void
  onReprocessConfirm: () => void
  onRestoreSceneSnapshot: (versionId: string) => void
  onSave: () => void
  onSaveScene: () => void
  onSceneChapterDraftChange: (value: number | null) => void
  onSceneDescriptionDraftChange: (value: string) => void
  onSceneDraftChange: (nextHtml: string, nextText: string) => void
  onSceneTitleDraftChange: (value: string) => void
  onSceneVersionNameDraftChange: (value: string) => void
  onUpdateFrontMatter: (field: keyof ManuscriptFrontMatter, value: string | boolean) => void
}

export function ManuscriptOverlayStack({
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
  firstChapter,
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
  onAddCharacterClose,
  onCharacterCreated,
  onCloseCompileDialog,
  onCloseSceneEditor,
  onCompareSceneVersion,
  onCompileManuscript,
  onCreateSceneSnapshot,
  onIncludeSceneMetadataOnExportChange,
  onIncludeTableOfContentsOnExportChange,
  onReprocessCancel,
  onReprocessConfirm,
  onRestoreSceneSnapshot,
  onSave,
  onSaveScene,
  onSceneChapterDraftChange,
  onSceneDescriptionDraftChange,
  onSceneDraftChange,
  onSceneTitleDraftChange,
  onSceneVersionNameDraftChange,
  onUpdateFrontMatter,
}: ManuscriptOverlayStackProps) {
  return (
    <>
      <ManuscriptMobileFooter
        activeChapterNumber={activeChapterNumber}
        activeLastSavedAt={activeLastSavedAt}
        activeSaveState={activeSaveState}
        chapterTitle={chapterTitle}
        isDark={isDark}
        saving={saving}
        onSave={onSave}
      />

      {showReprocessConfirm ? (
        <ManuscriptReprocessDialog
          isDark={isDark}
          reprocessing={reprocessing}
          onCancel={onReprocessCancel}
          onConfirm={onReprocessConfirm}
        />
      ) : null}

      <ManuscriptOverlayDialogs
        isDark={isDark}
        sceneEditorOpen={sceneEditorOpen}
        editingScene={editingScene}
        onCloseSceneEditor={onCloseSceneEditor}
        sceneTitleDraft={sceneTitleDraft}
        onSceneTitleDraftChange={onSceneTitleDraftChange}
        sceneChapterDraft={sceneChapterDraft}
        onSceneChapterDraftChange={onSceneChapterDraftChange}
        workspaceTree={workspaceTree}
        sceneDescriptionDraft={sceneDescriptionDraft}
        onSceneDescriptionDraftChange={onSceneDescriptionDraftChange}
        characters={characters}
        sceneHtmlDraft={sceneHtmlDraft}
        onSceneDraftChange={onSceneDraftChange}
        sceneVersions={sceneVersions}
        sceneVersionNameDraft={sceneVersionNameDraft}
        onSceneVersionNameDraftChange={onSceneVersionNameDraftChange}
        sceneVersionDetail={sceneVersionDetail}
        restoringSceneVersionId={restoringSceneVersionId}
        sceneBodyDraft={sceneBodyDraft}
        onCreateSceneSnapshot={onCreateSceneSnapshot}
        onCompareSceneVersion={onCompareSceneVersion}
        onRestoreSceneSnapshot={onRestoreSceneSnapshot}
        sceneSaving={sceneSaving}
        onSaveScene={onSaveScene}
        showCompileDialog={showCompileDialog}
        writerWorkspace={writerWorkspace}
        manuscriptFrontMatter={manuscriptFrontMatter}
        onCloseCompileDialog={onCloseCompileDialog}
        compileFormat={compileFormat}
        fullBookWordCount={fullBookWordCount}
        includeSceneMetadataOnExport={includeSceneMetadataOnExport}
        onIncludeSceneMetadataOnExportChange={onIncludeSceneMetadataOnExportChange}
        includeTableOfContentsOnExport={includeTableOfContentsOnExport}
        onIncludeTableOfContentsOnExportChange={onIncludeTableOfContentsOnExportChange}
        onUpdateFrontMatter={onUpdateFrontMatter}
        exporting={exporting}
        workspaceSaving={workspaceSaving}
        onCompileManuscript={onCompileManuscript}
      />

      <AddCharacterFromSelection
        bookId={bookId}
        selectedText={addCharacterText}
        isDark={isDark}
        firstChapter={firstChapter}
        open={addCharacterOpen}
        onClose={onAddCharacterClose}
        onCreated={onCharacterCreated}
      />
    </>
  )
}
