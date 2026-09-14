import type { RightPane } from "./manuscriptPage.constants"
import { useManuscriptCharacterCardActions } from "./manuscriptPage.characterCardActions"
import { useManuscriptChapterLoading } from "./manuscriptPage.chapterLoading"
import { useManuscriptFrontMatterActions } from "./manuscriptPage.frontMatterActions"
import { useManuscriptIntelligenceActions } from "./manuscriptPage.intelligenceActions"
import { useManuscriptSceneActions } from "./manuscriptPage.sceneActions"
import { useManuscriptStructureActions } from "./manuscriptPage.structureActions"
import { useManuscriptWorkspacePersistence } from "./manuscriptPage.workspacePersistence"
import { parseChapterHeadingInput } from "./manuscriptPage.helpers"

type ManuscriptDocumentBindingsArgs = ReturnType<
  (typeof import("./manuscriptPage.setup"))["useManuscriptPageSetup"]
>

export function useManuscriptDocumentBindings(args: ManuscriptDocumentBindingsArgs) {
  const {
    activeChapterNumber,
    authHydrated,
    bookDrafts,
    bookId,
    chapterList,
    chapterTitle,
    charCardDraft,
    confirm,
    deferredChecksSeedRef,
    draftChapterNumber,
    editingScene,
    editorMode,
    firstChapterLoadedCapturedRef,
    handledSceneIntentRef,
    html,
    includeSceneMetadataOnImport,
    initialChapterLoadedRef,
    lastAutoChecksRef,
    manuscriptLoadStartedAtRef,
    nextChapterNumber,
    queryClient,
    refetchWorkspaceTree,
    router,
    sceneBodyDraft,
    sceneChapterDraft,
    sceneDescriptionDraft,
    sceneDraftDirty,
    sceneHtmlDraft,
    sceneTitleDraft,
    searchParams,
    selectedCharCard,
    selectedChapter,
    structureVersionByChapter,
    text,
    userTier,
    workspaceTree,
  } = args

  const openRightPane = (pane: RightPane) => {
    args.setActiveRightPane(pane)
    args.setShowRightRail(true)
  }

  const {
    openCharCard,
    saveCharCard,
  } = useManuscriptCharacterCardActions({
    bookId,
    charCardDraft,
    selectedCharCard,
    openRightPane,
    setCharCardDraft: args.setCharCardDraft,
    setCharCardEditing: args.setCharCardEditing,
    setCharCardSaving: args.setCharCardSaving,
    setCharacters: args.setCharacters,
    setSelectedCharCard: args.setSelectedCharCard,
    setStatusMessage: args.setStatusMessage,
  })

  const { saveWorkspace } = useManuscriptWorkspacePersistence({
    bookId,
    setStatusMessage: args.setStatusMessage,
    setTargetRetry: args.setTargetRetry,
    setTargetSaveState: args.setTargetSaveState,
    setWorkspaceSaving: args.setWorkspaceSaving,
    setWriterWorkspace: args.setWriterWorkspace,
  })

  const chapterLoading = useManuscriptChapterLoading({
    authHydrated,
    bookDrafts,
    bookId,
    chapterList,
    deferredChecksSeedRef,
    editorMode,
    firstChapterLoadedCapturedRef,
    initialChapterLoadedRef,
    manuscriptLoadStartedAtRef,
    nextChapterNumber,
    queryClient,
    refetchWorkspaceTree,
    router,
    selectedChapter,
    setAutosaveState: args.setAutosaveState,
    setBook: args.setBook,
    setBookDrafts: args.setBookDrafts,
    setChapterList: args.setChapterList,
    setChapterTitle: args.setChapterTitle,
    setCharacters: args.setCharacters,
    setCollapsedSceneGroups: args.setCollapsedSceneGroups,
    setContentVersionByChapter: args.setContentVersionByChapter,
    setDirtyDrafts: args.setDirtyDrafts,
    setDraftChapterNumber: args.setDraftChapterNumber,
    setFullBookLoading: args.setFullBookLoading,
    setHtml: args.setHtml,
    setLoading: args.setLoading,
    setReview: args.setReview,
    setReviewPassages: args.setReviewPassages,
    setSelectedChapter: args.setSelectedChapter,
    setStatusMessage: args.setStatusMessage,
    setText: args.setText,
    setWorkspaceTree: args.setWorkspaceTree,
    setWriterWorkspace: args.setWriterWorkspace,
    userTier,
  })

  const sceneActions = useManuscriptSceneActions({
    bookId,
    confirm,
    editingScene,
    handledSceneIntentRef,
    loadWorkspaceTree: chapterLoading.loadWorkspaceTree,
    router,
    sceneBodyDraft,
    sceneChapterDraft,
    sceneDescriptionDraft,
    sceneDraftDirty,
    sceneHtmlDraft,
    sceneTitleDraft,
    searchParams,
    selectedChapter,
    setEditingScene: args.setEditingScene,
    setSceneBodyDraft: args.setSceneBodyDraft,
    setSceneChapterDraft: args.setSceneChapterDraft,
    setSceneDescriptionDraft: args.setSceneDescriptionDraft,
    setSceneEditorOpen: args.setSceneEditorOpen,
    setSceneHtmlDraft: args.setSceneHtmlDraft,
    setSceneSaving: args.setSceneSaving,
    setSceneTitleDraft: args.setSceneTitleDraft,
    setSceneVersionDetail: args.setSceneVersionDetail,
    setSceneVersionNameDraft: args.setSceneVersionNameDraft,
    setSceneVersions: args.setSceneVersions,
    setStatusMessage: args.setStatusMessage,
    syncLocalChapterFromServer: chapterLoading.syncLocalChapterFromServer,
  })

  const intelligenceActions = useManuscriptIntelligenceActions({
    activeChapterNumber,
    bookId,
    chapterTitle,
    editorMode,
    html,
    lastAutoChecksRef,
    markDraftDirty: chapterLoading.markDraftDirty,
    router,
    searchParams,
    setBookDrafts: args.setBookDrafts,
    setEmotionalArc: args.setEmotionalArc,
    setHtml: args.setHtml,
    setLogicSelectionText: args.setLogicSelectionText,
    setPlotThreads: args.setPlotThreads,
    setReview: args.setReview,
    setReviewPassages: args.setReviewPassages,
    setStatusMessage: args.setStatusMessage,
    setSuggestions: args.setSuggestions,
    setSynopsis: args.setSynopsis,
    setText: args.setText,
    setTighteningSelection: args.setTighteningSelection,
  })

  const structureActions = useManuscriptStructureActions({
    activeChapterNumber,
    bookId,
    chapterTitle,
    confirm,
    draftChapterNumber,
    includeSceneMetadataOnImport,
    selectedChapter,
    structureVersionByChapter,
    text,
    workspaceTree,
    loadWorkspaceTree: chapterLoading.loadWorkspaceTree,
    markDraftDirty: chapterLoading.markDraftDirty,
    setAutosaveState: args.setAutosaveState,
    setBook: args.setBook,
    setBookDrafts: args.setBookDrafts,
    setChapterList: args.setChapterList,
    setChapterTitle: args.setChapterTitle,
    setCollapsedSceneGroups: args.setCollapsedSceneGroups,
    setContentVersionByChapter: args.setContentVersionByChapter,
    setDeletingChapterNumber: args.setDeletingChapterNumber,
    setDirtyDrafts: args.setDirtyDrafts,
    setDraftChapterNumber: args.setDraftChapterNumber,
    setDraggedScene: args.setDraggedScene,
    setHtml: args.setHtml,
    setIncludeSceneMetadataOnExport: args.setIncludeSceneMetadataOnExport,
    setIncludeSceneMetadataOnImport: args.setIncludeSceneMetadataOnImport,
    setReplaceExisting: args.setReplaceExisting,
    setReview: args.setReview,
    setReviewPassages: args.setReviewPassages,
    setSceneDropTarget: args.setSceneDropTarget,
    setSceneOrderSaveState: args.setSceneOrderSaveState,
    setSelectedChapter: args.setSelectedChapter,
    setStatusMessage: args.setStatusMessage,
    setText: args.setText,
    setWorkspaceTree: args.setWorkspaceTree,
  })

  const { updateFrontMatter } = useManuscriptFrontMatterActions({
    setWriterWorkspace: args.setWriterWorkspace,
  })

  return {
    ...chapterLoading,
    ...sceneActions,
    ...intelligenceActions,
    ...structureActions,
    openCharCard,
    openRightPane,
    saveCharCard,
    saveWorkspace,
    parseChapterHeading: parseChapterHeadingInput,
    updateFrontMatter,
  }
}
