import { useDeferredValue, useMemo } from "react"

import type { ManuscriptDraftFontFamily } from "@/components/reader/ManuscriptNonWriteWorkspace"
import { deriveReprocessCta, isBookActivelyProcessing } from "@/lib/utils/editorProjectCta"
import { buildSceneOutline } from "@/lib/utils/manuscriptEditor"
import { normalizeProcessingStatus } from "@/lib/utils/processingStatus"
import type {
  Book,
  BookNote,
  EmotionalArcOverview,
  ManuscriptAnnotation,
  ManuscriptWorkspaceTree,
  NovelScene,
  PreWritingCheck,
  SaveState,
  WriterWorkspace,
} from "@/types/book"
import type { EditorialReview, EditorialReviewPassage } from "@/types/intelligence"
import type { ChapterListResponse, PlotThread, SearchResult, TimelineResponse } from "@/types/reader"
import type { DraftSurfaceMode, EditorMode, SaveTarget, WorkspaceTab } from "./manuscriptPage.constants"
import {
  activeManuscriptSaveState,
  buildActiveChapterDisplayTitle,
  buildActiveChapterHeading,
  buildChapterPreviewSections,
  buildChapterRowStats,
  buildDraftSurfaceSummaryLabel,
  buildFullBookPageMap,
  buildFullBookPreviewSections,
  buildManuscriptReferenceItems,
  buildRecentEventSummary,
  buildStructureVersionByChapter,
  countBookDraftWords,
  filterChapterListItems,
  filterWorkspaceSceneGroups,
  formatManuscriptChapterHeading,
  getActiveChapterContextCharacters,
  getActiveThreadSummary,
  getChapterAnnotations,
  getChapterLinkedNotes,
  getGeneralManuscriptNotes,
  getOpenManuscriptAnnotations,
  getResolvedManuscriptAnnotations,
  getRightRailThreadItems,
  getWarningSummary,
  manuscriptApproxPages,
  manuscriptAutosaveMetaLabel,
  manuscriptGoalProgress,
  manuscriptPageSummaryLabel,
  manuscriptReadingTime,
  manuscriptSaveStateLabel,
  manuscriptSaveStateTone,
  resolveManuscriptDraftFontStack,
  type BookDraftMap,
  type ManuscriptChapterAutosaveState,
} from "./manuscriptPage.helpers"

type UseManuscriptDerivedStateArgs = {
  activeChapterNumber: number
  annotationLastSavedAt?: string | null
  annotations: ManuscriptAnnotation[]
  autosaveState: ManuscriptChapterAutosaveState
  book: Book | null
  bookDrafts: BookDraftMap
  chapterList: ChapterListResponse | null
  chapterPreviewPageCount: number
  chapterSearch: string
  chapterTitle: string
  dirtyDrafts: number[]
  draftSurfaceMode: DraftSurfaceMode
  editingScene: NovelScene | null
  editorMode: EditorMode
  emotionalArc: EmotionalArcOverview | null
  focusMode: boolean
  fontFamily: ManuscriptDraftFontFamily
  fontSize: number
  fullBookPreviewPageCount: number
  html: string
  isDark: boolean
  lineHeight: number
  notes: BookNote[]
  plotThreads: PlotThread[]
  preWritingCheck: PreWritingCheck | null
  recallResults: SearchResult[]
  review: EditorialReview | null
  reviewPassages: EditorialReviewPassage[]
  rightRailPlotThreads: PlotThread[]
  rightRailTimelineData: TimelineResponse | null
  saveStateByTarget: Partial<Record<SaveTarget, SaveState>>
  sceneBodyDraft: string
  sceneChapterDraft: number | null
  sceneDescriptionDraft: string
  sceneEditorOpen: boolean
  sceneSearch: string
  sceneTitleDraft: string
  selectedChapter: number | null
  showLeftRail: boolean
  showRightRail: boolean
  saving: boolean
  text: string
  workspaceTab: WorkspaceTab
  workspaceTree: ManuscriptWorkspaceTree | null
  writerWorkspace: WriterWorkspace | null
}

export function useManuscriptDerivedState({
  activeChapterNumber,
  annotationLastSavedAt,
  annotations,
  autosaveState,
  book,
  bookDrafts,
  chapterList,
  chapterPreviewPageCount,
  chapterSearch,
  chapterTitle,
  dirtyDrafts,
  draftSurfaceMode,
  editingScene,
  editorMode,
  emotionalArc,
  focusMode,
  fontFamily,
  fontSize,
  fullBookPreviewPageCount,
  html,
  isDark,
  lineHeight,
  notes,
  plotThreads,
  preWritingCheck,
  recallResults,
  review,
  reviewPassages,
  rightRailPlotThreads,
  rightRailTimelineData,
  saveStateByTarget,
  sceneBodyDraft,
  sceneChapterDraft,
  sceneDescriptionDraft,
  sceneEditorOpen,
  sceneSearch,
  sceneTitleDraft,
  selectedChapter,
  showLeftRail,
  showRightRail,
  saving,
  text,
  workspaceTab,
  workspaceTree,
  writerWorkspace,
}: UseManuscriptDerivedStateArgs) {
  const sceneDraftDirty = useMemo(() => {
    if (!sceneEditorOpen) return false
    const baseTitle = editingScene?.title ?? ""
    const baseDescription = editingScene?.description ?? ""
    const baseBody = editingScene?.body ?? ""
    const baseChapterNumber = editingScene?.chapter_number ?? (selectedChapter ?? null)
    return (
      sceneTitleDraft !== baseTitle
      || sceneDescriptionDraft !== baseDescription
      || sceneBodyDraft !== baseBody
      || sceneChapterDraft !== baseChapterNumber
    )
  }, [editingScene, sceneBodyDraft, sceneChapterDraft, sceneDescriptionDraft, sceneEditorOpen, sceneTitleDraft, selectedChapter])

  const hasPendingEdits = dirtyDrafts.length > 0 || sceneDraftDirty
  const reprocessCta = useMemo(
    () => deriveReprocessCta(book, hasPendingEdits),
    [book, hasPendingEdits],
  )
  const isBookProcessing = isBookActivelyProcessing(book)
  const reprocessMetadata = writerWorkspace?.reprocess
  const autoReprocessEnabled = reprocessMetadata?.auto_reprocess_enabled !== false
  const pendingReprocessChapters = useMemo(
    () => new Set((reprocessMetadata?.pending_chapters ?? []).filter((chapterNumber) => Number.isFinite(chapterNumber) && chapterNumber > 0)),
    [reprocessMetadata?.pending_chapters],
  )
  const activeChapterNeedsReprocess = pendingReprocessChapters.has(activeChapterNumber)

  const sheetStyle = {
    fontSize: `${fontSize}pt`,
    lineHeight: String(lineHeight),
    fontFamily: resolveManuscriptDraftFontStack(fontFamily),
  } as const

  const chapterWordCount = useMemo(() => countBookDraftWords({ 1: { title: chapterTitle, text, html } }), [chapterTitle, html, text])
  const chapterApproxPages = useMemo(() => manuscriptApproxPages(chapterWordCount), [chapterWordCount])
  const chapterReadingTime = useMemo(() => manuscriptReadingTime(chapterWordCount), [chapterWordCount])
  const chapterSceneOutline = useMemo(() => buildSceneOutline(text), [text])
  const fullBookWordCount = useMemo(() => countBookDraftWords(bookDrafts), [bookDrafts])
  const fullBookApproxPages = useMemo(() => manuscriptApproxPages(fullBookWordCount), [fullBookWordCount])
  const fullBookReadingTime = useMemo(() => manuscriptReadingTime(fullBookWordCount), [fullBookWordCount])
  const chapterGoalProgress = useMemo(
    () => manuscriptGoalProgress(chapterWordCount, writerWorkspace?.word_count_goals.chapter_target),
    [chapterWordCount, writerWorkspace]
  )
  const bookGoalProgress = useMemo(
    () => manuscriptGoalProgress(fullBookWordCount, writerWorkspace?.word_count_goals.book_target),
    [fullBookWordCount, writerWorkspace]
  )
  const deferredChapterSearch = useDeferredValue(chapterSearch)
  const deferredSceneSearch = useDeferredValue(sceneSearch)
  const leftRailVisible = workspaceTab === "write" && !focusMode && showLeftRail
  const rightRailVisible = workspaceTab !== "plan" && !focusMode && showRightRail
  const desktopLayoutClass = leftRailVisible && rightRailVisible
    ? "xl:grid-cols-[22rem_minmax(0,1fr)_23.5rem]"
    : leftRailVisible
      ? "xl:grid-cols-[22rem_minmax(0,1fr)]"
      : rightRailVisible
        ? "xl:grid-cols-[minmax(0,1fr)_23.5rem]"
        : "xl:grid-cols-1"
  const chapterListItems = useMemo(() => chapterList?.chapters ?? [], [chapterList])
  const fullBookPageMap = useMemo(
    () => buildFullBookPageMap(chapterList?.chapters ?? [], bookDrafts),
    [bookDrafts, chapterList]
  )
  const fullBookReferenceItems = useMemo(() => buildManuscriptReferenceItems({
    recallResults,
    review,
    reviewPassages,
  }), [recallResults, review, reviewPassages])
  const pagedPreviewPreset = writerWorkspace?.publishing.active_preset ?? "standard_manuscript"
  const chapterLinkedNotes = useMemo(
    () => getChapterLinkedNotes(notes, activeChapterNumber),
    [activeChapterNumber, notes]
  )
  const chapterManualNotes = chapterLinkedNotes
  const chapterAnnotations = useMemo(
    () => getChapterAnnotations(annotations, activeChapterNumber),
    [activeChapterNumber, annotations]
  )
  const openChapterAnnotations = useMemo(
    () => getOpenManuscriptAnnotations(chapterAnnotations),
    [chapterAnnotations]
  )
  const resolvedChapterAnnotations = useMemo(
    () => getResolvedManuscriptAnnotations(chapterAnnotations),
    [chapterAnnotations]
  )
  const generalNotes = useMemo(
    () => getGeneralManuscriptNotes(notes),
    [notes]
  )
  const filteredChapterItems = useMemo(
    () => filterChapterListItems(chapterListItems, deferredChapterSearch),
    [chapterListItems, deferredChapterSearch]
  )
  const chapterRowStats = useMemo(() => buildChapterRowStats(chapterListItems, bookDrafts), [bookDrafts, chapterListItems])
  const chapterIndexFormat = writerWorkspace?.index_format ?? "arabic"
  const formatChapterHeading = (chapterNumber: number, title: string) => formatManuscriptChapterHeading(chapterNumber, title, chapterIndexFormat)
  const activeChapterDisplayTitle = buildActiveChapterDisplayTitle({
    chapterTitle,
    chapterListItems,
    activeChapterNumber,
  })
  const activeChapterHeading = buildActiveChapterHeading(activeChapterNumber, activeChapterDisplayTitle)
  const chapterPreviewSections = useMemo(
    () => buildChapterPreviewSections(activeChapterNumber, activeChapterDisplayTitle, html, chapterIndexFormat),
    [activeChapterDisplayTitle, activeChapterNumber, html, chapterIndexFormat]
  )
  const fullBookPreviewSections = useMemo(
    () => buildFullBookPreviewSections({
      editorMode,
      draftSurfaceMode,
      chapterListItems: chapterList?.chapters ?? [],
      bookDrafts,
      chapterIndexFormat,
    }),
    [bookDrafts, chapterList, draftSurfaceMode, editorMode, chapterIndexFormat]
  )
  const chapterPageSummaryLabel = manuscriptPageSummaryLabel({
    draftSurfaceMode,
    previewPageCount: chapterPreviewPageCount,
    approxPages: chapterApproxPages,
  })
  const fullBookPageSummaryLabel = manuscriptPageSummaryLabel({
    draftSurfaceMode,
    previewPageCount: fullBookPreviewPageCount,
    approxPages: fullBookApproxPages,
  })
  const draftSurfaceSummaryLabel = buildDraftSurfaceSummaryLabel({
    draftSurfaceMode,
    editorMode,
  })
  const activeChapterWordTarget = writerWorkspace?.word_count_goals.chapter_target ?? 0
  const activeChapterContextCharacters = getActiveChapterContextCharacters(preWritingCheck)
  const activeThreadSummary = getActiveThreadSummary(preWritingCheck)
  const rightRailThreadItems = getRightRailThreadItems(plotThreads, rightRailPlotThreads)
  const recentEventSummary = buildRecentEventSummary({
    preWritingCheck,
    rightRailTimelineData,
    activeChapterNumber,
  })
  const warningSummary = getWarningSummary(preWritingCheck)
  const arcSummaryCharacter = emotionalArc?.characters[0] ?? null
  const filteredSceneGroups = useMemo(
    () => filterWorkspaceSceneGroups(workspaceTree, deferredSceneSearch),
    [deferredSceneSearch, workspaceTree]
  )
  const structureVersionByChapter = useMemo(
    () => buildStructureVersionByChapter(workspaceTree),
    [workspaceTree]
  )
  const manuscriptFrontMatter = writerWorkspace?.manuscript_front_matter
  const saveStateLabel = (chapterNumber: number) => {
    return manuscriptSaveStateLabel({
      chapterNumber,
      saving,
      dirtyDrafts,
      autosaveState,
    })
  }
  const saveStateTone = (chapterNumber: number) => {
    return manuscriptSaveStateTone(saveStateLabel(chapterNumber), isDark)
  }
  const autosaveMetaLabel = (chapterNumber: number) => {
    return manuscriptAutosaveMetaLabel({
      chapterNumber,
      dirtyDrafts,
      autosaveState,
    })
  }
  const activeSaveState = activeManuscriptSaveState({
    saving,
    chapterTitleSaveState: saveStateByTarget.chapter_title,
    activeChapterAutosaveStatus: autosaveState[activeChapterNumber]?.status,
    dirtyDrafts,
    activeChapterNumber,
  })
  const activeLastSavedAt = autosaveState[activeChapterNumber]?.updatedAt ?? annotationLastSavedAt
  const normalizedProcessingStatus = normalizeProcessingStatus(book?.processing, book)

  return {
    activeChapterContextCharacters,
    activeChapterDisplayTitle,
    activeChapterHeading,
    activeChapterNeedsReprocess,
    activeChapterWordTarget,
    activeLastSavedAt,
    activeSaveState,
    activeThreadSummary,
    arcSummaryCharacter,
    autoReprocessEnabled,
    autosaveMetaLabel,
    bookGoalProgress,
    chapterAnnotations,
    chapterApproxPages,
    chapterGoalProgress,
    chapterIndexFormat,
    chapterLinkedNotes,
    chapterListItems,
    chapterManualNotes,
    chapterPageSummaryLabel,
    chapterPreviewSections,
    chapterReadingTime,
    chapterRowStats,
    chapterSceneOutline,
    chapterWordCount,
    desktopLayoutClass,
    draftSurfaceSummaryLabel,
    filteredChapterItems,
    filteredSceneGroups,
    formatChapterHeading,
    fullBookApproxPages,
    fullBookPageMap,
    fullBookPageSummaryLabel,
    fullBookPreviewSections,
    fullBookReadingTime,
    fullBookReferenceItems,
    fullBookWordCount,
    generalNotes,
    hasPendingEdits,
    isBookProcessing,
    leftRailVisible,
    manuscriptFrontMatter,
    normalizedProcessingStatus,
    openChapterAnnotations,
    pagedPreviewPreset,
    pendingReprocessChapters,
    recentEventSummary,
    reprocessCta,
    reprocessMetadata,
    resolvedChapterAnnotations,
    rightRailThreadItems,
    rightRailVisible,
    saveStateLabel,
    saveStateTone,
    sceneDraftDirty,
    sheetStyle,
    structureVersionByChapter,
    warningSummary,
  }
}
