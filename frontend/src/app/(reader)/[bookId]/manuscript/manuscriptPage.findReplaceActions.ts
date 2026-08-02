import type { Dispatch, SetStateAction } from "react"

import type { EditorMode } from "./manuscriptPage.constants"
import { textToHtml, type BookDraftMap } from "./manuscriptPage.helpers"

type UseManuscriptFindReplaceActionsArgs = {
  activeChapterNumber: number
  chapterTitle: string
  editorMode: EditorMode
  replaceQuery: string
  replaceValue: string
  text: string
  markDraftDirty: (chapterNumber: number) => void
  setBookDrafts: Dispatch<SetStateAction<BookDraftMap>>
  setHtml: Dispatch<SetStateAction<string>>
  setText: Dispatch<SetStateAction<string>>
}

export function useManuscriptFindReplaceActions({
  activeChapterNumber,
  chapterTitle,
  editorMode,
  markDraftDirty,
  replaceQuery,
  replaceValue,
  setBookDrafts,
  setHtml,
  setText,
  text,
}: UseManuscriptFindReplaceActionsArgs) {
  function replaceInCurrentChapter() {
    if (!replaceQuery) return
    const nextText = text.replace(replaceQuery, replaceValue)
    const nextHtml = textToHtml(nextText)
    setText(nextText)
    setHtml(nextHtml)
    markDraftDirty(activeChapterNumber)
    setBookDrafts((current) => ({
      ...current,
      [activeChapterNumber]: { title: chapterTitle, text: nextText, html: nextHtml },
    }))
  }

  function replaceEverywhere() {
    if (!replaceQuery) return
    if (editorMode === "chapter") {
      const nextText = text.split(replaceQuery).join(replaceValue)
      const nextHtml = textToHtml(nextText)
      setText(nextText)
      setHtml(nextHtml)
      markDraftDirty(activeChapterNumber)
      setBookDrafts((current) => ({
        ...current,
        [activeChapterNumber]: { title: chapterTitle, text: nextText, html: nextHtml },
      }))
      return
    }
    setBookDrafts((current) => {
      const next: BookDraftMap = { ...current }
      for (const [chapterNumber, draft] of Object.entries(current)) {
        next[Number(chapterNumber)] = {
          ...draft,
          text: draft.text.split(replaceQuery).join(replaceValue),
          html: textToHtml(draft.text.split(replaceQuery).join(replaceValue)),
        }
      }
      return next
    })
  }

  return {
    replaceEverywhere,
    replaceInCurrentChapter,
  }
}
