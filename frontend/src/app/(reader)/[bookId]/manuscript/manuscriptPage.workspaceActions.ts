import type { Dispatch, SetStateAction } from "react"

import type { TemplateDestination } from "@/components/reader/ManuscriptPlanWorkspace"
import type { BookNote, CorkboardCard, WriterWorkspace, WritingTemplate } from "@/types/book"
import {
  buildTemplateNoteBody,
  buildTemplateOutlineBlock,
  textToHtml,
  type BookDraftMap,
} from "./manuscriptPage.helpers"

type SaveWorkspace = (patch: Partial<WriterWorkspace>, options?: { silent?: boolean }) => Promise<void>
type PersistNote = (payload?: {
  noteId?: string | null
  chapterNumber?: number | null
  title?: string | null
  body: string
}) => Promise<BookNote | null>

type UseManuscriptWorkspaceActionsArgs = {
  activeChapterNumber: number
  chapterTitle: string
  newCorkboardTitle: string
  text: string
  writerWorkspace: WriterWorkspace | null
  markDraftDirty: (chapterNumber: number) => void
  persistNote: PersistNote
  saveWorkspace: SaveWorkspace
  setBookDrafts: Dispatch<SetStateAction<BookDraftMap>>
  setHtml: Dispatch<SetStateAction<string>>
  setNewCorkboardTitle: Dispatch<SetStateAction<string>>
  setStatusMessage: Dispatch<SetStateAction<string | null>>
  setText: Dispatch<SetStateAction<string>>
}

export function useManuscriptWorkspaceActions({
  activeChapterNumber,
  chapterTitle,
  markDraftDirty,
  newCorkboardTitle,
  persistNote,
  saveWorkspace,
  setBookDrafts,
  setHtml,
  setNewCorkboardTitle,
  setStatusMessage,
  setText,
  text,
  writerWorkspace,
}: UseManuscriptWorkspaceActionsArgs) {
  async function addCorkboardCard() {
    if (!newCorkboardTitle.trim() || !writerWorkspace) return
    const card: CorkboardCard = {
      id: `card-${Date.now()}`,
      title: newCorkboardTitle.trim(),
      description: "",
      lane: "ideas",
      status: "planned",
      chapter_number: activeChapterNumber,
      template_id: null,
    }
    await saveWorkspace({
      corkboard_cards: [...writerWorkspace.corkboard_cards, card],
    })
    setNewCorkboardTitle("")
  }

  async function updateCardLane(cardId: string, lane: string) {
    if (!writerWorkspace) return
    await saveWorkspace({
      corkboard_cards: writerWorkspace.corkboard_cards.map((card) => card.id === cardId ? { ...card, lane } : card),
    }, { silent: true })
  }

  async function applyTemplateToChapter(template: WritingTemplate, destination: TemplateDestination) {
    if (destination === "chapter_note") {
      const saved = await persistNote({
        chapterNumber: activeChapterNumber,
        title: `Template: ${template.title}`,
        body: buildTemplateNoteBody(template),
      })
      if (!saved) return
      setStatusMessage(`Saved ${template.title} as a chapter note.`)
      return
    }

    if (destination === "corkboard") {
      if (!writerWorkspace) return
      const card: CorkboardCard = {
        id: `card-${Date.now()}`,
        title: template.title,
        description: buildTemplateNoteBody(template),
        lane: "ideas",
        status: "planned",
        chapter_number: activeChapterNumber,
        template_id: template.id,
      }
      await saveWorkspace({
        corkboard_cards: [...writerWorkspace.corkboard_cards, card],
      })
      setStatusMessage(`Added ${template.title} to the corkboard.`)
      return
    }

    const outlineBlock = buildTemplateOutlineBlock(template)
    const nextText = text.trim() ? `${text.trim()}\n\n${outlineBlock}` : outlineBlock
    const nextHtml = textToHtml(nextText)
    setText(nextText)
    setHtml(nextHtml)
    markDraftDirty(activeChapterNumber)
    setBookDrafts((current) => ({
      ...current,
      [activeChapterNumber]: { title: chapterTitle, text: nextText, html: nextHtml },
    }))
    setStatusMessage(`Added ${template.title} as a draft outline block in chapter ${activeChapterNumber}.`)
  }

  async function saveTemplates(templates: WritingTemplate[]) {
    if (!writerWorkspace) return
    await saveWorkspace({ templates })
    setStatusMessage("Template saved.")
  }

  return {
    addCorkboardCard,
    applyTemplateToChapter,
    saveTemplates,
    updateCardLane,
  }
}
