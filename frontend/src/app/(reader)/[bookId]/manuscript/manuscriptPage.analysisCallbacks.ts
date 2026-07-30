import type { Dispatch, SetStateAction } from "react"

import { intelligenceApi } from "@/lib/api/intelligence"
import { capture } from "@/lib/analytics/posthog"
import type { Character } from "@/types/character"
import type { Book } from "@/types/book"
import {
  buildManuscriptCharacterNotePayload,
  type BookDraftMap,
  type ManuscriptCharacterCardDraft,
} from "./manuscriptPage.helpers"

type SaveWorkspaceVaultNotePayload = {
  title?: string | null
  body: string
  folderSegments?: string[]
}

type UseManuscriptAnalysisCallbacksOptions = {
  activeChapterNumber: number
  book: Book | null
  bookDrafts: BookDraftMap
  bookId: string
  openCharacterByName: (characterName: string) => void
  saveWorkspaceVaultNote: (payload?: SaveWorkspaceVaultNotePayload) => Promise<unknown>
  setAnnotationAnchor: Dispatch<SetStateAction<null | {
    quote: string
    anchorContextBefore: string | null
    anchorContextAfter: string | null
    startOffset: number
    endOffset: number
  }>>
  setAnnotationDraft: Dispatch<SetStateAction<string>>
  setCharCardDraft: Dispatch<SetStateAction<ManuscriptCharacterCardDraft>>
  setNoteBody: Dispatch<SetStateAction<string>>
  setNoteBodyText: Dispatch<SetStateAction<string>>
  setSelectedCharCard: Dispatch<SetStateAction<Character | null>>
  setStatusMessage: Dispatch<SetStateAction<string | null>>
  text: string
}

export function useManuscriptAnalysisCallbacks({
  activeChapterNumber,
  book,
  bookDrafts,
  bookId,
  openCharacterByName,
  saveWorkspaceVaultNote,
  setAnnotationAnchor,
  setAnnotationDraft,
  setCharCardDraft,
  setNoteBody,
  setNoteBodyText,
  setSelectedCharCard,
  setStatusMessage,
  text,
}: UseManuscriptAnalysisCallbacksOptions) {
  const clearSelectedCharacter = () => {
    setSelectedCharCard(null)
  }

  const cancelAnnotation = () => {
    setAnnotationAnchor(null)
    setAnnotationDraft("")
  }

  const changeCharacterDraftField = (field: keyof ManuscriptCharacterCardDraft, value: string) => {
    setCharCardDraft((draft) => ({ ...draft, [field]: value }))
  }

  const downloadContinuityReport = async () => {
    const blob = await intelligenceApi.continuityReport(bookId, text || bookDrafts[activeChapterNumber]?.text || "", "pdf", activeChapterNumber)
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = `${(book?.title || "lorevia").replace(/\s+/g, "-").toLowerCase()}-continuity-report.pdf`
    link.click()
    URL.revokeObjectURL(url)
    capture("continuity_report_exported", {
      book_id: bookId,
      chapter_number: activeChapterNumber,
      format: "pdf",
    })
  }

  const changeNoteBody = (nextHtml: string, nextText: string) => {
    setNoteBody(nextHtml)
    setNoteBodyText(nextText)
  }

  const saveCharacterNote = (character: Character) => {
    void saveWorkspaceVaultNote(buildManuscriptCharacterNotePayload(character)).catch(() => setStatusMessage("Could not save note."))
  }

  return {
    cancelAnnotation,
    changeCharacterDraftField,
    changeNoteBody,
    clearSelectedCharacter,
    downloadContinuityReport,
    openCharacterByName,
    saveCharacterNote,
  }
}
