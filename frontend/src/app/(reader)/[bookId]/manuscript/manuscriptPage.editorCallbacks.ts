import type { Dispatch, SetStateAction } from "react"

import type { Character } from "@/types/character"
import type { WriterWorkspace } from "@/types/book"
import type { BookDraftMap } from "./manuscriptPage.helpers"

type BookDraft = { title: string; text: string; html: string }
type ParseChapterHeading = (rawValue: string, fallbackNumber: number, fallbackTitle: string) => {
  chapterNumber: number
  title: string
}
type SaveChapterDraft = (chapterNumber: number, draft?: BookDraft) => Promise<void>
type SaveWorkspace = (patch: Partial<WriterWorkspace>, options?: { silent?: boolean }) => Promise<void>

type UseManuscriptEditorCallbacksOptions = {
  activeChapterNumber: number
  chapterTitle: string
  characters: Character[]
  markDraftDirty: (chapterNumber: number) => void
  openCharCard: (character: Character) => void
  parseChapterHeading: ParseChapterHeading
  refetchWorkspaceTree: () => Promise<unknown>
  saveChapterDraft: SaveChapterDraft
  saveWorkspace: SaveWorkspace
  setActiveEditorKey: Dispatch<SetStateAction<string | null>>
  setBookDrafts: Dispatch<SetStateAction<BookDraftMap>>
  setHtml: Dispatch<SetStateAction<string>>
  setReplaceExisting: Dispatch<SetStateAction<boolean>>
  setSaving: Dispatch<SetStateAction<boolean>>
  setShowEditorSettings: Dispatch<SetStateAction<boolean>>
  setText: Dispatch<SetStateAction<string>>
  setWriterWorkspace: Dispatch<SetStateAction<WriterWorkspace | null>>
}

export function useManuscriptEditorCallbacks({
  activeChapterNumber,
  chapterTitle,
  characters,
  markDraftDirty,
  openCharCard,
  parseChapterHeading,
  refetchWorkspaceTree,
  saveChapterDraft,
  saveWorkspace,
  setActiveEditorKey,
  setBookDrafts,
  setHtml,
  setReplaceExisting,
  setSaving,
  setShowEditorSettings,
  setText,
  setWriterWorkspace,
}: UseManuscriptEditorCallbacksOptions) {
  const blurChapterEditor = () => {
    setActiveEditorKey((current) => current === `chapter-${activeChapterNumber}` ? null : current)
  }

  const focusChapterEditor = () => {
    setActiveEditorKey(`chapter-${activeChapterNumber}`)
  }

  const changeChapterText = (nextHtml: string, nextText: string) => {
    setHtml(nextHtml)
    setText(nextText)
    markDraftDirty(activeChapterNumber)
    setBookDrafts((current) => ({
      ...current,
      [activeChapterNumber]: { title: chapterTitle, text: nextText, html: nextHtml },
    }))
  }

  const openCharacterByName = (characterName: string) => {
    const character = characters.find((candidate) => candidate.name === characterName || candidate.aliases?.includes(characterName))
    if (character) openCharCard(character)
  }

  const changeFullBookDraft = ({ chapterNumber, draft }: { chapterNumber: number; draft: BookDraft }) => {
    markDraftDirty(chapterNumber)
    setBookDrafts((current) => ({
      ...current,
      [chapterNumber]: {
        title: current[chapterNumber]?.title ?? draft.title,
        text: draft.text,
        html: draft.html,
      },
    }))
  }

  const blurFullBookEditor = (chapterNumber: number) => {
    setActiveEditorKey((current) => current === `book-${chapterNumber}` ? null : current)
  }

  const focusFullBookEditor = (chapterNumber: number) => {
    setActiveEditorKey(`book-${chapterNumber}`)
  }

  const blurFullBookHeading = async (chapterNumber: number, draft: BookDraft, value: string) => {
    const parsed = parseChapterHeading(value, chapterNumber, draft.title)
    setBookDrafts((current) => ({
      ...current,
      [chapterNumber]: {
        title: parsed.title,
        text: current[chapterNumber]?.text ?? draft.text,
        html: current[chapterNumber]?.html ?? draft.html,
      },
    }))
    markDraftDirty(chapterNumber)
    if (draft.text.trim()) {
      setSaving(true)
      try {
        await saveChapterDraft(chapterNumber, { ...draft, title: parsed.title })
      } finally {
        setSaving(false)
      }
    }
  }

  const changeIndexFormat = (format: WriterWorkspace["index_format"]) => {
    setWriterWorkspace((current) => current ? { ...current, index_format: format } : current)
    void saveWorkspace({ index_format: format })
    refetchWorkspaceTree()
  }

  const toggleEditorSettings = () => {
    setShowEditorSettings((value) => !value)
  }

  const toggleReplaceExisting = () => {
    setReplaceExisting((value) => !value)
  }

  return {
    blurChapterEditor,
    blurFullBookEditor,
    blurFullBookHeading,
    changeChapterText,
    changeFullBookDraft,
    changeIndexFormat,
    focusChapterEditor,
    focusFullBookEditor,
    openCharacterByName,
    toggleEditorSettings,
    toggleReplaceExisting,
  }
}
