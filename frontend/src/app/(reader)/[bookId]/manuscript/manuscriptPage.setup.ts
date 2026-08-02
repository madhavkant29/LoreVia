import { useQueryClient } from "@tanstack/react-query"
import { useEffect, useMemo, useRef } from "react"
import { useParams, useRouter, useSearchParams } from "next/navigation"

import { useConfirmDialog } from "@/components/ui/ConfirmDialog"
import type { ManuscriptSelectionAnchor } from "@/lib/utils/manuscriptAnnotations"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { useAuthStore } from "@/lib/stores/authStore"
import { capture } from "@/lib/analytics/posthog"
import { useManuscriptAnalysisState } from "./manuscriptPage.analysisState"
import { useManuscriptAnnotationSave } from "./manuscriptPage.annotationSave"
import { useManuscriptCoreState } from "./manuscriptPage.coreState"
import { useManuscriptDerivedState } from "./manuscriptPage.derivedState"
import { useManuscriptNoteAnnotationState } from "./manuscriptPage.noteAnnotationState"
import { useManuscriptPageQueries } from "./manuscriptPage.queries"
import { useManuscriptSaveTargets } from "./manuscriptPage.saveTargets"
import { useManuscriptSceneUiState } from "./manuscriptPage.sceneUiState"
import { useManuscriptTelemetryRefs } from "./manuscriptPage.telemetry"
import { useManuscriptEditorUiState } from "./manuscriptPage.uiState"

export function useManuscriptPageSetup() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const searchParams = useSearchParams()
  const confirm = useConfirmDialog()
  const { theme } = usePreferencesStore()
  const userTier = useAuthStore((state) => state.user?.tier)
  const authHydrated = useAuthStore((state) => state.hydrated)
  const queryClient = useQueryClient()
  const isDark = theme === "dark"

  useEffect(() => {
    capture("author_manuscript_opened", { book_id: bookId })
  }, [bookId])

  const coreState = useManuscriptCoreState()
  const sceneUiState = useManuscriptSceneUiState()
  const analysisState = useManuscriptAnalysisState()
  const editorUiState = useManuscriptEditorUiState()
  const noteAnnotationState = useManuscriptNoteAnnotationState()
  const saveTargets = useManuscriptSaveTargets()

  const chapterRefs = useRef<Record<number, HTMLDivElement | null>>({})
  const searchInputRef = useRef<HTMLInputElement | null>(null)
  const manuscriptSectionRef = useRef<HTMLDivElement | null>(null)
  const initialChapterLoadedRef = useRef<number | null>(null)
  const handledSceneIntentRef = useRef(false)
  const annotationRangesRef = useRef<Map<string, Range>>(new Map())
  const pendingAnnotationJumpIdRef = useRef<string | null>(null)
  const selectionMenuAnchorRef = useRef<ManuscriptSelectionAnchor | null>(null)
  const telemetryRefs = useManuscriptTelemetryRefs({
    bookId,
    loading: coreState.loading,
  })
  const deferredChecksSeedRef = useRef<{ chapterNumber: number; text: string } | null>(null)
  const lastAutoChecksRef = useRef<Record<number, number>>({})

  const nextChapterNumber = useMemo(() => {
    const numbers = coreState.chapterList?.chapters.map((chapter) => chapter.number) ?? []
    return numbers.length ? Math.max(...numbers) + 1 : 1
  }, [coreState.chapterList])

  const activeChapterNumber =
    coreState.selectedChapter ?? coreState.draftChapterNumber ?? nextChapterNumber
  const annotationChapterNumber = coreState.selectedChapter ?? coreState.draftChapterNumber
  const pageQueries = useManuscriptPageQueries({
    activeRightPane: editorUiState.activeRightPane,
    activeChapterNumber,
    annotationChapterNumber,
    bookId,
    loading: coreState.loading,
    selectedChapter: coreState.selectedChapter,
    showLeftRail: editorUiState.showLeftRail,
    showRightRail: editorUiState.showRightRail,
    workspaceTab: editorUiState.workspaceTab,
  })

  const annotationSave = useManuscriptAnnotationSave({
    activeChapterNumber,
    bookId,
    pendingAnnotationJumpIdRef,
    setActiveAnnotationId: noteAnnotationState.setActiveAnnotationId,
    setAnnotationAnchor: noteAnnotationState.setAnnotationAnchor,
    setAnnotationDraft: noteAnnotationState.setAnnotationDraft,
    setAnnotations: coreState.setAnnotations,
    setStatusMessage: coreState.setStatusMessage,
  })
  const derivedState = useManuscriptDerivedState({
    activeChapterNumber,
    annotationLastSavedAt: annotationSave.lastSavedAt,
    annotations: coreState.annotations,
    autosaveState: coreState.autosaveState,
    book: coreState.book,
    bookDrafts: coreState.bookDrafts,
    chapterList: coreState.chapterList,
    chapterPreviewPageCount: editorUiState.chapterPreviewPageCount,
    chapterSearch: sceneUiState.chapterSearch,
    chapterTitle: coreState.chapterTitle,
    dirtyDrafts: coreState.dirtyDrafts,
    draftSurfaceMode: editorUiState.draftSurfaceMode,
    editingScene: sceneUiState.editingScene,
    editorMode: editorUiState.editorMode,
    emotionalArc: analysisState.emotionalArc,
    focusMode: editorUiState.focusMode,
    fontFamily: editorUiState.fontFamily,
    fontSize: editorUiState.fontSize,
    fullBookPreviewPageCount: editorUiState.fullBookPreviewPageCount,
    html: coreState.html,
    isDark,
    lineHeight: editorUiState.lineHeight,
    notes: coreState.notes,
    plotThreads: coreState.plotThreads,
    preWritingCheck: coreState.preWritingCheck,
    recallResults: analysisState.recallResults,
    review: coreState.review,
    reviewPassages: coreState.reviewPassages,
    rightRailPlotThreads: pageQueries.rightRailPlotThreads,
    rightRailTimelineData: pageQueries.rightRailTimelineData,
    saveStateByTarget: saveTargets.saveStateByTarget,
    saving: coreState.saving,
    sceneBodyDraft: sceneUiState.sceneBodyDraft,
    sceneChapterDraft: sceneUiState.sceneChapterDraft,
    sceneDescriptionDraft: sceneUiState.sceneDescriptionDraft,
    sceneEditorOpen: sceneUiState.sceneEditorOpen,
    sceneSearch: sceneUiState.sceneSearch,
    sceneTitleDraft: sceneUiState.sceneTitleDraft,
    selectedChapter: coreState.selectedChapter,
    showLeftRail: editorUiState.showLeftRail,
    showRightRail: editorUiState.showRightRail,
    text: coreState.text,
    workspaceTab: editorUiState.workspaceTab,
    workspaceTree: coreState.workspaceTree,
    writerWorkspace: coreState.writerWorkspace,
  })

  return {
    ...coreState,
    ...sceneUiState,
    ...analysisState,
    ...editorUiState,
    ...noteAnnotationState,
    ...saveTargets,
    ...telemetryRefs,
    ...pageQueries,
    ...derivedState,
    activeChapterNumber,
    annotationChapterNumber,
    annotationRangesRef,
    annotationSave,
    authHydrated,
    bookId,
    chapterRefs,
    confirm,
    deferredChecksSeedRef,
    handledSceneIntentRef,
    initialChapterLoadedRef,
    isDark,
    lastAutoChecksRef,
    manuscriptSectionRef,
    nextChapterNumber,
    pendingAnnotationJumpIdRef,
    queryClient,
    router,
    searchInputRef,
    searchParams,
    selectionMenuAnchorRef,
    userTier,
  }
}
