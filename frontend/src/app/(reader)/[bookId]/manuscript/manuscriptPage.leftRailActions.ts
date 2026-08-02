import type { Dispatch, SetStateAction } from "react"

import type { EditorialReview, EditorialReviewPassage } from "@/types/intelligence"
import { textToHtml } from "./manuscriptPage.helpers"

type DraggedSceneState = { chapterNumber: number; sceneId: string }
type SceneDropTarget = { chapterNumber: number; index: number }

type UseManuscriptLeftRailActionsOptions = {
  nextChapterNumber: number
  prefetchManuscriptChapter: (chapterNumber: number) => void
  setChapterTitle: Dispatch<SetStateAction<string>>
  setCollapsedSceneGroups: Dispatch<SetStateAction<Record<string, boolean>>>
  setDraftChapterNumber: Dispatch<SetStateAction<number | null>>
  setDraggedScene: Dispatch<SetStateAction<DraggedSceneState | null>>
  setHtml: Dispatch<SetStateAction<string>>
  setReplaceExisting: Dispatch<SetStateAction<boolean>>
  setReview: Dispatch<SetStateAction<EditorialReview | null>>
  setReviewPassages: Dispatch<SetStateAction<EditorialReviewPassage[]>>
  setSceneDropTarget: Dispatch<SetStateAction<SceneDropTarget | null>>
  setSelectedChapter: Dispatch<SetStateAction<number | null>>
  setText: Dispatch<SetStateAction<string>>
}

export function useManuscriptLeftRailActions({
  nextChapterNumber,
  prefetchManuscriptChapter,
  setChapterTitle,
  setCollapsedSceneGroups,
  setDraftChapterNumber,
  setDraggedScene,
  setHtml,
  setReplaceExisting,
  setReview,
  setReviewPassages,
  setSceneDropTarget,
  setSelectedChapter,
  setText,
}: UseManuscriptLeftRailActionsOptions) {
  const createChapterDraft = () => {
    setSelectedChapter(null)
    setDraftChapterNumber(nextChapterNumber)
    setReplaceExisting(false)
    setChapterTitle(`Chapter ${nextChapterNumber}`)
    setText("")
    setHtml(textToHtml(""))
    setReview(null)
    setReviewPassages([])
  }

  const startSceneDrag = (chapterNumber: number, sceneId: string, index: number) => {
    setDraggedScene({ chapterNumber, sceneId })
    setSceneDropTarget({ chapterNumber, index })
  }

  const selectChapter = (chapterNumber: number) => {
    prefetchManuscriptChapter(chapterNumber - 1)
    prefetchManuscriptChapter(chapterNumber + 1)
    setSelectedChapter(chapterNumber)
    setDraftChapterNumber(null)
    setReplaceExisting(true)
  }

  const toggleSceneGroup = (groupId: string, collapsed: boolean) => {
    setCollapsedSceneGroups((current) => ({ ...current, [groupId]: !collapsed }))
  }

  return {
    createChapterDraft,
    selectChapter,
    startSceneDrag,
    toggleSceneGroup,
  }
}
