import type { Dispatch, SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import type {
  ChapterVersion,
  ChapterVersionDetail,
  NovelScene,
  SceneVersion,
  SceneVersionDetail,
} from "@/types/book"
import {
  buildSceneDraftStorageKey,
  textToHtml,
  type BookDraftMap,
} from "./manuscriptPage.helpers"

type UseManuscriptVersionActionsArgs = {
  bookId: string
  chapterVersionDetail: ChapterVersionDetail | null
  chapterVersionNameDraft: string
  editingScene: NovelScene | null
  sceneVersionDetail: SceneVersionDetail | null
  sceneVersionNameDraft: string
  selectedChapter: number | null
  clearDraftDirty: (chapterNumber: number) => void
  loadWorkspaceTree: () => Promise<void>
  runAutomaticChecks: (chapterNumber: number, content: string) => Promise<void>
  syncLocalChapterFromServer: (chapterNumber: number) => Promise<void>
  setBookDrafts: Dispatch<SetStateAction<BookDraftMap>>
  setChapterTitle: Dispatch<SetStateAction<string>>
  setChapterVersionDetail: Dispatch<SetStateAction<ChapterVersionDetail | null>>
  setChapterVersionNameDraft: Dispatch<SetStateAction<string>>
  setChapterVersions: Dispatch<SetStateAction<ChapterVersion[]>>
  setDraftChapterNumber: Dispatch<SetStateAction<number | null>>
  setEditingScene: Dispatch<SetStateAction<NovelScene | null>>
  setHtml: Dispatch<SetStateAction<string>>
  setRestoringSceneVersionId: Dispatch<SetStateAction<string | null>>
  setRestoringVersionId: Dispatch<SetStateAction<string | null>>
  setSceneBodyDraft: Dispatch<SetStateAction<string>>
  setSceneChapterDraft: Dispatch<SetStateAction<number | null>>
  setSceneDescriptionDraft: Dispatch<SetStateAction<string>>
  setSceneHtmlDraft: Dispatch<SetStateAction<string>>
  setSceneTitleDraft: Dispatch<SetStateAction<string>>
  setSceneVersionDetail: Dispatch<SetStateAction<SceneVersionDetail | null>>
  setSceneVersionNameDraft: Dispatch<SetStateAction<string>>
  setSceneVersions: Dispatch<SetStateAction<SceneVersion[]>>
  setSelectedChapter: Dispatch<SetStateAction<number | null>>
  setStatusMessage: Dispatch<SetStateAction<string | null>>
  setText: Dispatch<SetStateAction<string>>
}

export function useManuscriptVersionActions({
  bookId,
  chapterVersionDetail,
  chapterVersionNameDraft,
  clearDraftDirty,
  editingScene,
  loadWorkspaceTree,
  runAutomaticChecks,
  sceneVersionDetail,
  sceneVersionNameDraft,
  selectedChapter,
  setBookDrafts,
  setChapterTitle,
  setChapterVersionDetail,
  setChapterVersionNameDraft,
  setChapterVersions,
  setDraftChapterNumber,
  setEditingScene,
  setHtml,
  setRestoringSceneVersionId,
  setRestoringVersionId,
  setSceneBodyDraft,
  setSceneChapterDraft,
  setSceneDescriptionDraft,
  setSceneHtmlDraft,
  setSceneTitleDraft,
  setSceneVersionDetail,
  setSceneVersionNameDraft,
  setSceneVersions,
  setSelectedChapter,
  setStatusMessage,
  setText,
  syncLocalChapterFromServer,
}: UseManuscriptVersionActionsArgs) {
  async function createSnapshot() {
    if (selectedChapter === null) return
    try {
      const note = chapterVersionNameDraft.trim() || `Manual snapshot before edits to Chapter ${selectedChapter}`
      await booksApi.createChapterSnapshot(bookId, selectedChapter, note)
      setChapterVersions(await booksApi.getChapterVersions(bookId, selectedChapter))
      setChapterVersionNameDraft("")
      setStatusMessage(`Saved a snapshot for chapter ${selectedChapter}.`)
    } catch {
      setStatusMessage("Snapshot save failed. Please try again.")
    }
  }

  async function restoreSnapshot(versionId: string) {
    setRestoringVersionId(versionId)
    let pollTimer: ReturnType<typeof setInterval> | null = null
    try {
      const restored = await booksApi.restoreChapterVersion(bookId, versionId)
      setSelectedChapter(restored.chapter_number)
      setDraftChapterNumber(null)
      setChapterTitle(restored.title || `Chapter ${restored.chapter_number}`)
      setText(restored.text)
      setHtml(restored.html || textToHtml(restored.text))
      setChapterVersions(restored.versions)
      setBookDrafts((current) => ({
        ...current,
        [restored.chapter_number]: {
          title: restored.title || `Chapter ${restored.chapter_number}`,
          text: restored.text,
          html: restored.html || textToHtml(restored.text),
        },
      }))
      clearDraftDirty(restored.chapter_number)
      await runAutomaticChecks(restored.chapter_number, restored.text)
      await loadWorkspaceTree()
      setStatusMessage(`Restored chapter ${restored.chapter_number} from snapshot.`)
      pollTimer = setInterval(async () => {
        try {
          const status = await booksApi.getRestoreStatus(bookId, versionId)
          if (status.restore_status === "done" || status.restore_status === "failed") {
            if (pollTimer) clearInterval(pollTimer)
            setRestoringVersionId(null)
            if (status.restore_status === "failed") {
              setStatusMessage(status.restore_error ?? "Restore failed.")
            }
          }
        } catch {
          if (pollTimer) clearInterval(pollTimer)
          setRestoringVersionId(null)
        }
      }, 1500)
    } catch {
      setRestoringVersionId(null)
      if (pollTimer) clearInterval(pollTimer)
    }
  }

  async function previewSnapshot(versionId: string) {
    if (chapterVersionDetail?.id === versionId) {
      setChapterVersionDetail(null)
      return
    }

    try {
      const detail = await booksApi.getChapterVersionDetail(bookId, versionId)
      setChapterVersionDetail(detail)
    } catch {
      setStatusMessage("Could not load that snapshot preview.")
    }
  }

  async function createSceneSnapshot() {
    if (!editingScene?.id) return
    try {
      const note = sceneVersionNameDraft.trim() || `Manual snapshot for scene: ${editingScene.title}`
      const versions = await booksApi.createSceneSnapshot(bookId, editingScene.id, note)
      setSceneVersions(await booksApi.getSceneVersions(bookId, editingScene.id))
      setSceneVersionNameDraft("")
      setStatusMessage(`Saved a version for scene "${versions.scene_title}".`)
    } catch {
      setStatusMessage("Scene snapshot save failed. Please try again.")
    }
  }

  async function compareSceneVersion(versionId: string) {
    if (sceneVersionDetail?.id === versionId) {
      setSceneVersionDetail(null)
      return
    }

    try {
      const detail = await booksApi.getSceneVersionDetail(bookId, versionId)
      setSceneVersionDetail(detail)
    } catch {
      setStatusMessage("Could not load that scene version.")
    }
  }

  async function restoreSceneSnapshot(versionId: string) {
    setRestoringSceneVersionId(versionId)
    try {
      const previousChapterNumber = editingScene?.chapter_number ?? null
      const restored = await booksApi.restoreSceneVersion(bookId, versionId)
      setEditingScene(restored.scene)
      setSceneTitleDraft(restored.scene.title)
      setSceneDescriptionDraft(restored.scene.description ?? "")
      setSceneBodyDraft(restored.scene.body)
      setSceneHtmlDraft(restored.scene.html_body ?? textToHtml(restored.scene.body))
      setSceneChapterDraft(restored.scene.chapter_number ?? null)
      setSceneVersions(restored.versions)
      setSceneVersionDetail(null)
      await loadWorkspaceTree()
      const chaptersToRefresh = [...new Set([previousChapterNumber, restored.scene.chapter_number].filter((value): value is number => typeof value === "number" && value > 0))]
      await Promise.all(chaptersToRefresh.map(syncLocalChapterFromServer))
      if (typeof window !== "undefined") {
        window.localStorage.removeItem(buildSceneDraftStorageKey(bookId, restored.scene, restored.scene.chapter_number ?? previousChapterNumber))
      }
      setStatusMessage(`Restored scene "${restored.scene.title}" from version history.`)
    } finally {
      setRestoringSceneVersionId(null)
    }
  }

  return {
    compareSceneVersion,
    createSceneSnapshot,
    createSnapshot,
    previewSnapshot,
    restoreSceneSnapshot,
    restoreSnapshot,
  }
}
