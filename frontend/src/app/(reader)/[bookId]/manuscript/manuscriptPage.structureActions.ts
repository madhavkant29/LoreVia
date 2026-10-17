import axios from "axios"
import type { Dispatch, SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import { buildManuscriptAutosaveKey } from "@/lib/utils/manuscriptEditor"
import { moveSceneIdToIndex, reorderWorkspaceSceneTree } from "@/lib/utils/sceneWorkspace"
import type { Book, ManuscriptWorkspaceTree, WorkspaceScene } from "@/types/book"
import type { EditorialReview, EditorialReviewPassage } from "@/types/intelligence"
import type { ChapterListResponse } from "@/types/reader"
import type { ConfirmDialogConfig } from "@/types/ux"
import { textToHtml, type BookDraftMap } from "./manuscriptPage.helpers"

type Confirm = (config: ConfirmDialogConfig) => Promise<boolean>
type DraggedSceneState = { chapterNumber: number; sceneId: string }
type SceneDropTarget = { chapterNumber: number; index: number }
type AutosaveStateByChapter = Record<number, { status: "pending" | "saved" | "error"; updatedAt?: string }>
type SceneOrderSaveStateByChapter = Record<number, "idle" | "saving" | "saved" | "failed">

type UseManuscriptStructureActionsArgs = {
  activeChapterNumber: number
  bookId: string
  chapterTitle: string
  confirm: Confirm
  draftChapterNumber: number | null
  includeSceneMetadataOnImport: boolean
  selectedChapter: number | null
  structureVersionByChapter: Record<number, number>
  text: string
  workspaceTree: ManuscriptWorkspaceTree | null
  loadWorkspaceTree: () => Promise<void>
  markDraftDirty: (chapterNumber: number) => void
  setAutosaveState: Dispatch<SetStateAction<AutosaveStateByChapter>>
  setBook: Dispatch<SetStateAction<Book | null>>
  setBookDrafts: Dispatch<SetStateAction<BookDraftMap>>
  setChapterList: Dispatch<SetStateAction<ChapterListResponse | null>>
  setChapterTitle: Dispatch<SetStateAction<string>>
  setCollapsedSceneGroups: Dispatch<SetStateAction<Record<string, boolean>>>
  setContentVersionByChapter: Dispatch<SetStateAction<Record<number, number>>>
  setDeletingChapterNumber: Dispatch<SetStateAction<number | null>>
  setDirtyDrafts: Dispatch<SetStateAction<number[]>>
  setDraftChapterNumber: Dispatch<SetStateAction<number | null>>
  setDraggedScene: Dispatch<SetStateAction<DraggedSceneState | null>>
  setHtml: Dispatch<SetStateAction<string>>
  setIncludeSceneMetadataOnExport: Dispatch<SetStateAction<boolean>>
  setIncludeSceneMetadataOnImport: Dispatch<SetStateAction<boolean>>
  setReplaceExisting: Dispatch<SetStateAction<boolean>>
  setReview: Dispatch<SetStateAction<EditorialReview | null>>
  setReviewPassages: Dispatch<SetStateAction<EditorialReviewPassage[]>>
  setSceneDropTarget: Dispatch<SetStateAction<SceneDropTarget | null>>
  setSceneOrderSaveState: Dispatch<SetStateAction<SceneOrderSaveStateByChapter>>
  setSelectedChapter: Dispatch<SetStateAction<number | null>>
  setStatusMessage: Dispatch<SetStateAction<string | null>>
  setText: Dispatch<SetStateAction<string>>
  setWorkspaceTree: Dispatch<SetStateAction<ManuscriptWorkspaceTree | null>>
}

export function useManuscriptStructureActions({
  activeChapterNumber,
  bookId,
  chapterTitle,
  confirm,
  draftChapterNumber,
  includeSceneMetadataOnImport,
  loadWorkspaceTree,
  markDraftDirty,
  selectedChapter,
  setAutosaveState,
  setBook,
  setBookDrafts,
  setChapterList,
  setChapterTitle,
  setCollapsedSceneGroups,
  setContentVersionByChapter,
  setDeletingChapterNumber,
  setDirtyDrafts,
  setDraftChapterNumber,
  setDraggedScene,
  setHtml,
  setIncludeSceneMetadataOnExport,
  setIncludeSceneMetadataOnImport,
  setReplaceExisting,
  setReview,
  setReviewPassages,
  setSceneDropTarget,
  setSceneOrderSaveState,
  setSelectedChapter,
  setStatusMessage,
  setText,
  setWorkspaceTree,
  structureVersionByChapter,
  text,
  workspaceTree,
}: UseManuscriptStructureActionsArgs) {
  function resetSceneDragState() {
    setDraggedScene(null)
    setSceneDropTarget(null)
  }

  async function reorderScenesInChapter(chapterNumber: number, sourceSceneId: string, destinationIndex: number) {
    if (!workspaceTree) return
    const chapterGroup = workspaceTree.scene_groups.find((group) => group.chapter_number === chapterNumber)
    if (!chapterGroup) return

    const currentSceneIds = chapterGroup.scenes.map((scene) => scene.id)
    const nextSceneIds = moveSceneIdToIndex(currentSceneIds, sourceSceneId, destinationIndex)
    if (nextSceneIds === currentSceneIds) return

    const previousTree = workspaceTree
    const expectedStructureVersion = chapterGroup.structure_version ?? structureVersionByChapter[chapterNumber] ?? 0

    setWorkspaceTree(reorderWorkspaceSceneTree(previousTree, chapterNumber, nextSceneIds))
    setSceneOrderSaveState((current) => ({ ...current, [chapterNumber]: "saving" }))

    try {
      const reordered = await booksApi.reorderChapterScenes(bookId, chapterNumber, {
        sceneIds: nextSceneIds,
        expectedStructureVersion,
      })
      setWorkspaceTree((current) =>
        current
          ? reorderWorkspaceSceneTree(
              current,
              chapterNumber,
              reordered.scenes.map((scene) => scene.id),
              reordered.structure_version
            )
          : current
      )
      setSceneOrderSaveState((current) => ({ ...current, [chapterNumber]: "saved" }))
    } catch (error) {
      setWorkspaceTree(previousTree)
      setSceneOrderSaveState((current) => ({ ...current, [chapterNumber]: "failed" }))
      if (axios.isAxiosError(error) && error.response?.status === 409) {
        setStatusMessage("Scene order changed in another session. Refreshed the chapter order.")
        void loadWorkspaceTree()
      } else {
        setStatusMessage("Could not save scene order. Reverted.")
      }
    } finally {
      resetSceneDragState()
    }
  }

  async function removeChapter(chapterNumber: number) {
    const confirmed = await confirm({
      title: `Remove Chapter ${chapterNumber}?`,
      body: `Remove Chapter ${chapterNumber}? This deletes its manuscript text, scenes, notes, comments, and chapter intelligence. This cannot be undone.`,
      confirmLabel: "Remove chapter",
      tone: "danger",
    })
    if (!confirmed) return

    setDeletingChapterNumber(chapterNumber)
    try {
      try {
        await booksApi.deleteChapter(bookId, chapterNumber)
      } catch (error) {
        const detail = axios.isAxiosError(error) ? (error.response?.data as { detail?: unknown } | undefined)?.detail : null
        setStatusMessage(
          typeof detail === "string" && detail.trim()
            ? `Could not remove Chapter ${chapterNumber}: ${detail}`
            : `Could not remove Chapter ${chapterNumber}.`
        )
        return
      }

      if (typeof window !== "undefined") {
        window.localStorage.removeItem(buildManuscriptAutosaveKey(bookId, chapterNumber))
      }

      let bookData: Book
      let chapters: ChapterListResponse
      let workspace: ManuscriptWorkspaceTree | null
      try {
        ;[bookData, chapters, workspace] = await Promise.all([
          booksApi.get(bookId),
          readerApi.getChapterList(bookId),
          booksApi.getWorkspaceTree(bookId).catch(() => null),
        ])
      } catch {
        setStatusMessage(`Chapter ${chapterNumber} removed. Reload the editor to refresh the chapter list.`)
        return
      }

      const nextChapterNumber =
        chapters.chapters.find((chapter) => chapter.number > chapterNumber)?.number ??
        chapters.chapters[chapters.chapters.length - 1]?.number ??
        null

      setBook(bookData)
      setChapterList(chapters)
      setWorkspaceTree(workspace)
      if (workspace) {
        setCollapsedSceneGroups((current) => {
          const next = { ...current }
          for (const group of workspace.scene_groups) {
            if (!(group.id in next)) next[group.id] = !!group.collapsed_by_default
          }
          return next
        })
      }
      setBookDrafts((current) => {
        const next = { ...current }
        delete next[chapterNumber]
        return next
      })
      setContentVersionByChapter((current) => {
        const next = { ...current }
        delete next[chapterNumber]
        return next
      })
      setAutosaveState((current) => {
        const next = { ...current }
        delete next[chapterNumber]
        return next
      })
      setDirtyDrafts((current) => current.filter((item) => item !== chapterNumber))

      if (selectedChapter === chapterNumber || draftChapterNumber === chapterNumber) {
        setSelectedChapter(nextChapterNumber)
        setDraftChapterNumber(null)
        setReplaceExisting(nextChapterNumber !== null)
        setReview(null)
        setReviewPassages([])
        if (nextChapterNumber === null) {
          setChapterTitle("")
          setText("")
          setHtml(textToHtml(""))
        }
      }

      setStatusMessage(`Chapter ${chapterNumber} removed.`)
    } finally {
      setDeletingChapterNumber(null)
    }
  }

  async function insertSceneIntoDraft(scene: WorkspaceScene) {
    const insertion = await booksApi.getSceneInsertion(bookId, scene.id, activeChapterNumber, "end", includeSceneMetadataOnImport)
    const separator = text.trim() ? "\n\n***\n\n" : ""
    const nextText = `${text}${separator}${insertion.body}`.trim()
    const nextHtml = insertion.html_body || textToHtml(nextText)
    setText(nextText)
    setHtml(nextHtml)
    setBookDrafts((current) => ({
      ...current,
      [activeChapterNumber]: { title: chapterTitle, text: nextText, html: nextHtml },
    }))
    markDraftDirty(activeChapterNumber)
    setStatusMessage(`Inserted scene "${insertion.title}" into chapter ${activeChapterNumber}.`)
  }

  async function handleSceneMetadataImportChange(checked: boolean) {
    if (!checked) {
      setIncludeSceneMetadataOnImport(false)
      return
    }

    const confirmed = await confirm({
      title: "Insert scene metadata?",
      body: "Scene metadata adds LoreVia planning labels to inserted scene text. Use it only when you want those scene notes in the manuscript draft.",
      confirmLabel: "Insert metadata",
    })
    if (confirmed) {
      setIncludeSceneMetadataOnImport(true)
      setStatusMessage("Scene metadata will be included when inserting scenes.")
    }
  }

  async function handleSceneMetadataExportChange(checked: boolean) {
    if (!checked) {
      setIncludeSceneMetadataOnExport(false)
      return
    }

    const confirmed = await confirm({
      title: "Include scene metadata?",
      body: "Scene metadata adds LoreVia planning labels to compiled exports. Keep it off for clean submission prose unless you really want those notes included.",
      confirmLabel: "Include metadata",
    })
    if (confirmed) {
      setIncludeSceneMetadataOnExport(true)
      setStatusMessage("Scene metadata will be included in compiled exports.")
    }
  }

  return {
    handleSceneMetadataExportChange,
    handleSceneMetadataImportChange,
    insertSceneIntoDraft,
    removeChapter,
    reorderScenesInChapter,
    resetSceneDragState,
  }
}
