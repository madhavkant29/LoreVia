import type { Dispatch, SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import type { BookNote } from "@/types/book"

type PersistNote = (payload?: {
  noteId?: string | null
  chapterNumber?: number | null
  title?: string | null
  body: string
}) => Promise<BookNote | null>

type SaveWorkspaceVaultNote = (payload?: {
  title?: string | null
  body: string
  folderSegments?: string[]
}) => Promise<unknown>

type UseManuscriptNoteActionsArgs = {
  activeChapterNumber: number
  bookId: string
  editNoteBody: string
  editNoteTitle: string
  editingNoteId: string | null
  persistNote: PersistNote
  saveWorkspaceVaultNote: SaveWorkspaceVaultNote
  setEditNoteBody: Dispatch<SetStateAction<string>>
  setEditNoteTitle: Dispatch<SetStateAction<string>>
  setEditingNoteId: Dispatch<SetStateAction<string | null>>
  setEditingNoteSaving: Dispatch<SetStateAction<boolean>>
  setNoteBody: Dispatch<SetStateAction<string>>
  setNoteBodyText: Dispatch<SetStateAction<string>>
  setNoteTitle: Dispatch<SetStateAction<string>>
  setNotes: Dispatch<SetStateAction<BookNote[]>>
  setStatusMessage: Dispatch<SetStateAction<string | null>>
}

export function useManuscriptNoteActions({
  activeChapterNumber,
  bookId,
  editNoteBody,
  editNoteTitle,
  editingNoteId,
  persistNote,
  saveWorkspaceVaultNote,
  setEditNoteBody,
  setEditNoteTitle,
  setEditingNoteId,
  setEditingNoteSaving,
  setNoteBody,
  setNoteBodyText,
  setNoteTitle,
  setNotes,
  setStatusMessage,
}: UseManuscriptNoteActionsArgs) {
  async function saveNote() {
    const saved = await persistNote()
    if (!saved) return
    setNoteTitle("")
    setNoteBody("")
    setNoteBodyText("")
  }

  async function removeNote(noteId: string) {
    await booksApi.deleteBookNote(bookId, noteId)
    setNotes((current) => current.filter((note) => note.id !== noteId))
  }

  function startEditingNote(note: BookNote) {
    setEditingNoteId(note.id)
    setEditNoteTitle(note.title || "")
    setEditNoteBody(note.body)
  }

  function cancelEditingNote() {
    setEditingNoteId(null)
    setEditNoteTitle("")
    setEditNoteBody("")
  }

  async function saveEditedNote() {
    if (!editingNoteId) return
    setEditingNoteSaving(true)
    try {
      const updated = await persistNote({
        noteId: editingNoteId,
        title: editNoteTitle.trim() || null,
        body: editNoteBody,
      })
      if (!updated) return
      setNotes((current) => current.map((note) => note.id === updated.id ? updated : note))
      cancelEditingNote()
      setStatusMessage("Note updated.")
    } finally {
      setEditingNoteSaving(false)
    }
  }

  async function saveContinuityIssueAsNote(issue: { title: string; description: string; suggestion?: string }) {
    const noteBody = `**Continuity Issue: ${issue.title}**\n\n${issue.description}${issue.suggestion ? `\n\n**Suggestion:** ${issue.suggestion}` : ""}`
    const noteTitle = `Continuity: ${issue.title}`
    await saveWorkspaceVaultNote({
      title: noteTitle,
      body: noteBody,
      folderSegments: activeChapterNumber ? [`Chapter ${activeChapterNumber}`, "Continuity"] : ["Continuity"],
    })
  }

  return {
    cancelEditingNote,
    removeNote,
    saveContinuityIssueAsNote,
    saveEditedNote,
    saveNote,
    startEditingNote,
  }
}
