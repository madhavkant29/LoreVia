import { ManuscriptWorkspaceSidebarHeader } from "@/components/reader/ManuscriptWorkspaceSidebarHeader"
import type { SceneOrderSaveState } from "@/components/reader/ManuscriptSceneOrderStatus"
import type {
  ChapterVersion,
  ChapterVersionDetail,
  NovelScene,
  WorkspaceSceneGroup,
} from "@/types/book"

import { ManuscriptChapterRailSection } from "./manuscriptPage.chapterRail"
import { ManuscriptLeftRailTail } from "./manuscriptPage.leftRailTail"
import { ManuscriptSceneRailSection } from "./manuscriptPage.sceneRail"
import type {
  ManuscriptChapterListItem,
  ManuscriptIndexFormat,
} from "./manuscriptPage.helpers"

type DraggedSceneState = { chapterNumber: number; sceneId: string }
type SceneDropTarget = { chapterNumber: number; index: number }
type ChapterRailItem = ManuscriptChapterListItem & {
  processed?: boolean | null
}
type ChapterRailStats = Record<number, { wordCount: number; sceneCount: number; readingTime: string }>

type ManuscriptLeftRailProps = {
  bookGoalProgress: number | null
  bookId: string
  bookTargetWordCount: number
  bookTitle?: string | null
  chapterIndexFormat: ManuscriptIndexFormat
  chapterRowStats: ChapterRailStats
  chapterSearch: string
  chapterVersionDetail: ChapterVersionDetail | null
  chapterVersionNameDraft: string
  chapterVersions: ChapterVersion[]
  collapsedSceneGroups: Record<string, boolean>
  currentText: string
  deletingChapterNumber: number | null
  dirtyDrafts: number[]
  draftChapterNumber: number | null
  draggedScene: DraggedSceneState | null
  filteredChapterItems: ChapterRailItem[]
  filteredSceneGroups: WorkspaceSceneGroup[]
  fullBookReadingTime: string
  fullBookWordCount: number
  includeSceneMetadataOnImport: boolean
  isDark: boolean
  pendingReprocessChapters: ReadonlySet<number>
  reprocessingChapterNumber: number | null
  restoringVersionId: string | null
  sceneDropTarget: SceneDropTarget | null
  sceneOrderSaveState: Record<number, SceneOrderSaveState>
  selectedChapter: number | null
  onChapterSearchChange: (value: string) => void
  onCreateChapter: () => void
  onCreateChapterSnapshot: () => void
  onCreateScene: () => void
  onDragSceneStart: (chapterNumber: number, sceneId: string, index: number) => void
  onInsertSceneIntoDraft: (scene: NovelScene) => void
  onOpenSceneEditor: (scene: NovelScene | null) => void
  onPrefetchChapter: (chapterNumber: number) => void
  onPreviewChapterSnapshot: (versionId: string) => void
  onRemoveChapter: (chapterNumber: number) => void
  onRemoveScene: (scene: NovelScene) => void
  onReorderScenesInChapter: (chapterNumber: number, sceneId: string, targetIndex: number) => void
  onReprocessChapter: (chapterNumber: number) => void
  onResetSceneDragState: () => void
  onRestoreChapterSnapshot: (versionId: string) => void
  onSceneDropTargetChange: (target: SceneDropTarget) => void
  onSceneMetadataImportChange: (checked: boolean) => void
  onSelectChapter: (chapterNumber: number) => void
  onToggleSceneGroup: (groupId: string, collapsed: boolean) => void
  onVersionNameChange: (value: string) => void
}

export function ManuscriptLeftRail({
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
  onChapterSearchChange,
  onCreateChapter,
  onCreateChapterSnapshot,
  onCreateScene,
  onDragSceneStart,
  onInsertSceneIntoDraft,
  onOpenSceneEditor,
  onPrefetchChapter,
  onPreviewChapterSnapshot,
  onRemoveChapter,
  onRemoveScene,
  onReorderScenesInChapter,
  onReprocessChapter,
  onResetSceneDragState,
  onRestoreChapterSnapshot,
  onSceneDropTargetChange,
  onSceneMetadataImportChange,
  onSelectChapter,
  onToggleSceneGroup,
  onVersionNameChange,
}: ManuscriptLeftRailProps) {
  return (
    <aside className={`min-w-0 border-r p-5 xl:sticky xl:top-[8.25rem] xl:max-h-[calc(100vh-8.25rem)] xl:self-start xl:overflow-y-auto ${isDark ? "border-white/10 bg-[#11171a]" : "border-stone-200 bg-white/90"}`}>
      <ManuscriptWorkspaceSidebarHeader
        bookTitle={bookTitle}
        fullBookReadingTime={fullBookReadingTime}
        fullBookWordCount={fullBookWordCount}
        isDark={isDark}
        onCreateChapter={onCreateChapter}
        onCreateScene={onCreateScene}
      />
      <ManuscriptChapterRailSection
        chapterIndexFormat={chapterIndexFormat}
        chapterRowStats={chapterRowStats}
        chapterSearch={chapterSearch}
        deletingChapterNumber={deletingChapterNumber}
        dirtyDrafts={dirtyDrafts}
        draftChapterNumber={draftChapterNumber}
        filteredChapterItems={filteredChapterItems}
        isDark={isDark}
        pendingReprocessChapters={pendingReprocessChapters}
        reprocessingChapterNumber={reprocessingChapterNumber}
        selectedChapter={selectedChapter}
        onChapterSearchChange={onChapterSearchChange}
        onPrefetchChapter={onPrefetchChapter}
        onRemoveChapter={onRemoveChapter}
        onReprocessChapter={onReprocessChapter}
        onSelectChapter={onSelectChapter}
      />
      <ManuscriptSceneRailSection
        bookId={bookId}
        collapsedSceneGroups={collapsedSceneGroups}
        draggedScene={draggedScene}
        filteredSceneGroups={filteredSceneGroups}
        includeSceneMetadataOnImport={includeSceneMetadataOnImport}
        isDark={isDark}
        sceneDropTarget={sceneDropTarget}
        sceneOrderSaveState={sceneOrderSaveState}
        onDragSceneStart={onDragSceneStart}
        onInsertSceneIntoDraft={onInsertSceneIntoDraft}
        onOpenSceneEditor={onOpenSceneEditor}
        onRemoveScene={onRemoveScene}
        onReorderScenesInChapter={onReorderScenesInChapter}
        onResetSceneDragState={onResetSceneDragState}
        onSceneDropTargetChange={onSceneDropTargetChange}
        onSceneMetadataImportChange={onSceneMetadataImportChange}
        onToggleSceneGroup={onToggleSceneGroup}
      />
      <ManuscriptLeftRailTail
        bookGoalProgress={bookGoalProgress}
        bookTargetWordCount={bookTargetWordCount}
        chapterVersionDetail={chapterVersionDetail}
        chapterVersionNameDraft={chapterVersionNameDraft}
        chapterVersions={chapterVersions}
        currentText={currentText}
        fullBookWordCount={fullBookWordCount}
        isDark={isDark}
        restoringVersionId={restoringVersionId}
        selectedChapter={selectedChapter}
        onCreateSnapshot={onCreateChapterSnapshot}
        onPreviewSnapshot={onPreviewChapterSnapshot}
        onRestoreSnapshot={onRestoreChapterSnapshot}
        onVersionNameChange={onVersionNameChange}
      />
    </aside>
  )
}
