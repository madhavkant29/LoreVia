import { useCallback, useEffect, type Dispatch, type MutableRefObject, type SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import {
  parseSceneAutosaveDraft,
} from "@/lib/utils/manuscriptEditor"
import type { ConfirmDialogConfig } from "@/types/ux"
import type { NovelScene, SceneVersion, SceneVersionDetail } from "@/types/book"
import {
  buildSceneDraftStorageKey,
  textToHtml,
} from "./manuscriptPage.helpers"

type Confirm = (config: ConfirmDialogConfig) => Promise<boolean>

type ManuscriptSceneRouter = {
  replace: (href: string) => void
}

type ManuscriptSceneSearchParams = {
  get: (name: string) => string | null
}

type UseManuscriptSceneActionsArgs = {
  bookId: string
  confirm: Confirm
  editingScene: NovelScene | null
  handledSceneIntentRef: MutableRefObject<boolean>
  router: ManuscriptSceneRouter
  sceneBodyDraft: string
  sceneChapterDraft: number | null
  sceneDescriptionDraft: string
  sceneDraftDirty: boolean
  sceneHtmlDraft: string
  sceneTitleDraft: string
  searchParams: ManuscriptSceneSearchParams
  selectedChapter: number | null
  loadWorkspaceTree: () => Promise<void>
  syncLocalChapterFromServer: (chapterNumber: number) => Promise<void>
  setEditingScene: Dispatch<SetStateAction<NovelScene | null>>
  setSceneBodyDraft: Dispatch<SetStateAction<string>>
  setSceneChapterDraft: Dispatch<SetStateAction<number | null>>
  setSceneDescriptionDraft: Dispatch<SetStateAction<string>>
  setSceneEditorOpen: Dispatch<SetStateAction<boolean>>
  setSceneHtmlDraft: Dispatch<SetStateAction<string>>
  setSceneSaving: Dispatch<SetStateAction<boolean>>
  setSceneTitleDraft: Dispatch<SetStateAction<string>>
  setSceneVersionDetail: Dispatch<SetStateAction<SceneVersionDetail | null>>
  setSceneVersionNameDraft: Dispatch<SetStateAction<string>>
  setSceneVersions: Dispatch<SetStateAction<SceneVersion[]>>
  setStatusMessage: Dispatch<SetStateAction<string | null>>
}

export function useManuscriptSceneActions({
  bookId,
  confirm,
  editingScene,
  handledSceneIntentRef,
  loadWorkspaceTree,
  router,
  sceneBodyDraft,
  sceneChapterDraft,
  sceneDescriptionDraft,
  sceneDraftDirty,
  sceneHtmlDraft,
  sceneTitleDraft,
  searchParams,
  selectedChapter,
  setEditingScene,
  setSceneBodyDraft,
  setSceneChapterDraft,
  setSceneDescriptionDraft,
  setSceneEditorOpen,
  setSceneHtmlDraft,
  setSceneSaving,
  setSceneTitleDraft,
  setSceneVersionDetail,
  setSceneVersionNameDraft,
  setSceneVersions,
  setStatusMessage,
  syncLocalChapterFromServer,
}: UseManuscriptSceneActionsArgs) {
  const loadSceneVersions = useCallback(async (sceneId: string) => {
    try {
      setSceneVersions(await booksApi.getSceneVersions(bookId, sceneId))
    } catch {
      setSceneVersions([])
    }
  }, [bookId, setSceneVersions])

  const openSceneEditor = useCallback((scene?: NovelScene | null) => {
    const nextScene = scene ?? null
    const fallbackChapterNumber = nextScene?.chapter_number ?? (selectedChapter ?? null)
    const storageKey = buildSceneDraftStorageKey(bookId, nextScene, fallbackChapterNumber)
    const recoveredDraft = typeof window === "undefined" ? null : parseSceneAutosaveDraft(window.localStorage.getItem(storageKey))

    setEditingScene(nextScene)
    setSceneTitleDraft(recoveredDraft?.title ?? nextScene?.title ?? "")
    setSceneDescriptionDraft(recoveredDraft?.description ?? nextScene?.description ?? "")
    setSceneBodyDraft(recoveredDraft?.body ?? nextScene?.body ?? "")
    setSceneHtmlDraft(nextScene?.html_body ?? textToHtml(recoveredDraft?.body ?? nextScene?.body ?? ""))
    setSceneChapterDraft(recoveredDraft?.chapterNumber ?? fallbackChapterNumber)
    setSceneVersionDetail(null)
    setSceneVersionNameDraft("")
    setSceneEditorOpen(true)

    if (nextScene?.id) {
      void loadSceneVersions(nextScene.id)
    } else {
      setSceneVersions([])
    }
    if (recoveredDraft?.updatedAt) {
      setStatusMessage(`Recovered a local autosave for scene "${recoveredDraft.title || nextScene?.title || "draft"}".`)
    }
  }, [
    bookId,
    loadSceneVersions,
    selectedChapter,
    setEditingScene,
    setSceneBodyDraft,
    setSceneChapterDraft,
    setSceneDescriptionDraft,
    setSceneEditorOpen,
    setSceneHtmlDraft,
    setSceneTitleDraft,
    setSceneVersionDetail,
    setSceneVersionNameDraft,
    setSceneVersions,
    setStatusMessage,
  ])

  const closeSceneEditor = useCallback(async () => {
    if (sceneDraftDirty) {
      const confirmed = await confirm({
        title: "Close scene editor?",
        body: "You have unsaved scene changes. Close the editor anyway?",
        confirmLabel: "Close editor",
        tone: "danger",
      })
      if (!confirmed) return
    }
    setSceneEditorOpen(false)
    setEditingScene(null)
    setSceneTitleDraft("")
    setSceneDescriptionDraft("")
    setSceneBodyDraft("")
    setSceneHtmlDraft("<p></p>")
    setSceneChapterDraft(selectedChapter ?? null)
    setSceneVersions([])
    setSceneVersionDetail(null)
    setSceneVersionNameDraft("")
  }, [
    confirm,
    sceneDraftDirty,
    selectedChapter,
    setEditingScene,
    setSceneBodyDraft,
    setSceneChapterDraft,
    setSceneDescriptionDraft,
    setSceneEditorOpen,
    setSceneHtmlDraft,
    setSceneTitleDraft,
    setSceneVersionDetail,
    setSceneVersionNameDraft,
    setSceneVersions,
  ])

  useEffect(() => {
    const shouldOpenNewScene = searchParams.get("newScene") === "1"
    if (!shouldOpenNewScene || handledSceneIntentRef.current) return

    handledSceneIntentRef.current = true
    openSceneEditor(null)
    router.replace(`/${bookId}/manuscript`)
  }, [bookId, handledSceneIntentRef, openSceneEditor, router, searchParams])

  const saveScene = useCallback(async () => {
    if (!sceneTitleDraft.trim() || !sceneBodyDraft.trim()) return
    setSceneSaving(true)
    try {
      const previousChapterNumber = editingScene?.chapter_number ?? null
      const savedScene = await booksApi.saveScene(bookId, {
        id: editingScene?.id,
        title: sceneTitleDraft.trim(),
        description: sceneDescriptionDraft.trim() || null,
        body: sceneBodyDraft,
        html_body: sceneHtmlDraft,
        chapter_number: sceneChapterDraft,
        status: sceneChapterDraft ? "assigned" : "unassigned",
        sort_order: editingScene?.sort_order,
      })
      if (typeof window !== "undefined") {
        window.localStorage.removeItem(buildSceneDraftStorageKey(bookId, editingScene, previousChapterNumber))
        window.localStorage.removeItem(buildSceneDraftStorageKey(bookId, savedScene, savedScene.chapter_number ?? previousChapterNumber))
      }
      await loadWorkspaceTree()
      const chaptersToRefresh = [...new Set([previousChapterNumber, sceneChapterDraft].filter((value): value is number => typeof value === "number" && value > 0))]
      await Promise.all(chaptersToRefresh.map(syncLocalChapterFromServer))
      await closeSceneEditor()
      setStatusMessage(editingScene ? "Scene updated." : "Scene saved.")
    } finally {
      setSceneSaving(false)
    }
  }, [
    bookId,
    closeSceneEditor,
    editingScene,
    loadWorkspaceTree,
    sceneBodyDraft,
    sceneChapterDraft,
    sceneDescriptionDraft,
    sceneHtmlDraft,
    sceneTitleDraft,
    setSceneSaving,
    setStatusMessage,
    syncLocalChapterFromServer,
  ])

  const removeScene = useCallback(async (scene: NovelScene) => {
    await booksApi.deleteScene(bookId, scene.id)
    await loadWorkspaceTree()
    if (typeof scene.chapter_number === "number" && scene.chapter_number > 0) {
      await syncLocalChapterFromServer(scene.chapter_number)
    }
    setStatusMessage(`Deleted scene "${scene.title}".`)
  }, [bookId, loadWorkspaceTree, setStatusMessage, syncLocalChapterFromServer])

  return {
    closeSceneEditor,
    openSceneEditor,
    removeScene,
    saveScene,
  }
}
