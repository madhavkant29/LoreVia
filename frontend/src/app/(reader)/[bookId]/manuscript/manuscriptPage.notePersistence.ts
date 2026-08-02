import type { Dispatch, SetStateAction } from "react"

import { booksApi } from "@/lib/api/books"
import { capture, captureTiming } from "@/lib/analytics/posthog"
import { saveContextualVaultNote } from "@/lib/utils/notes"
import { htmlToPlainText } from "@/lib/utils/richText"
import type { Book, BookNote, SaveState } from "@/types/book"
import type { ChapterListResponse } from "@/types/reader"
import type { SaveTarget } from "./manuscriptPage.constants"

type PersistNotePayload = {
  noteId?: string | null
  chapterNumber?: number | null
  title?: string | null
  body: string
}

type SaveWorkspaceVaultNotePayload = {
  title?: string | null
  body: string
  folderSegments?: string[]
}

type SetTargetSaveState = (target: SaveTarget, state: SaveState) => void
type SetTargetRetry = (target: SaveTarget, retry: (() => Promise<void>) | null) => void

type UseManuscriptNotePersistenceArgs = {
  activeChapterNumber: number
  book: Book | null
  bookId: string
  chapterList: ChapterListResponse | null
  noteBody: string
  noteScope: "chapter" | "book"
  noteTitle: string
  setNotes: Dispatch<SetStateAction<BookNote[]>>
  setSavingNote: Dispatch<SetStateAction<boolean>>
  setStatusMessage: Dispatch<SetStateAction<string | null>>
  setTargetRetry: SetTargetRetry
  setTargetSaveState: SetTargetSaveState
}

export function useManuscriptNotePersistence({
  activeChapterNumber,
  book,
  bookId,
  chapterList,
  noteBody,
  noteScope,
  noteTitle,
  setNotes,
  setSavingNote,
  setStatusMessage,
  setTargetRetry,
  setTargetSaveState,
}: UseManuscriptNotePersistenceArgs) {
  async function persistNote(payload?: PersistNotePayload) {
    const nextBody = payload?.body ?? noteBody
    const nextText = htmlToPlainText(nextBody)
    if (!nextText.trim()) return null
    const startedAt = typeof performance !== "undefined" ? performance.now() : 0
    const chapterNumber = payload?.chapterNumber ?? (noteScope === "chapter" ? activeChapterNumber : null)
    const title = payload?.title ?? (noteTitle.trim() || null)
    const localId = payload?.noteId ?? `local-note-${Date.now()}`
    const optimisticNote: BookNote = {
      id: localId,
      book_id: bookId,
      book_title: book?.title ?? "",
      chapter_number: chapterNumber,
      chapter_title: chapterNumber ? chapterList?.chapters.find((chapter) => chapter.number === chapterNumber)?.title ?? null : null,
      title,
      body: nextBody,
      tags: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    setTargetSaveState("book_note", "saving")
    setTargetRetry("book_note", null)
    setNotes((current) => [optimisticNote, ...current.filter((note) => note.id !== localId)])
    setSavingNote(true)
    try {
      const saved = await booksApi.saveBookNote(bookId, {
        noteId: payload?.noteId ?? null,
        chapterNumber,
        title,
        body: nextBody,
      })
      setNotes((current) => [saved, ...current.filter((note) => note.id !== saved.id && note.id !== localId)])
      setTargetSaveState("book_note", "saved")
      captureTiming("save_latency_ms", startedAt, { book_id: bookId, save_target: "book_note" })
      setStatusMessage(`Saved note${saved.chapter_number ? ` for chapter ${saved.chapter_number}` : ""}.`)
      return saved
    } catch {
      setTargetSaveState("book_note", "error")
      setTargetRetry("book_note", () => persistNote(payload).then(() => undefined))
      captureTiming("save_latency_ms", startedAt, { book_id: bookId, save_target: "book_note", save_state: "error" })
      capture("save_failure_count", { book_id: bookId, save_target: "book_note" })
      setStatusMessage("Could not save note. Your draft is still kept locally.")
      return null
    } finally {
      setSavingNote(false)
    }
  }

  async function saveWorkspaceVaultNote(payload?: SaveWorkspaceVaultNotePayload) {
    const nextBody = payload?.body ?? noteBody
    const nextText = htmlToPlainText(nextBody).trim()
    if (!nextText) return null
    const startedAt = typeof performance !== "undefined" ? performance.now() : 0
    const title = payload?.title?.trim() || noteTitle.trim() || `Chapter ${activeChapterNumber} note`
    const chapterFolder = noteScope === "chapter" && activeChapterNumber ? [`Chapter ${activeChapterNumber}`] : ["Whole Book"]

    setTargetSaveState("vault_note", "saving")
    setTargetRetry("vault_note", null)
    try {
      const saved = await saveContextualVaultNote({
        bookId,
        title,
        content: nextText,
        context: "manual_editor",
        folderSegments: payload?.folderSegments?.length ? payload.folderSegments : chapterFolder,
      })
      try {
        window.localStorage.removeItem(`lorevia:vault-note-draft:${bookId}`)
      } catch {
        // local draft cleanup is best-effort
      }
      setTargetSaveState("vault_note", "saved")
      captureTiming("save_latency_ms", startedAt, { book_id: bookId, save_target: "vault_note" })
      setStatusMessage(`Saved to notes workspace: ${saved.path}`)
      return saved
    } catch {
      try {
        window.localStorage.setItem(`lorevia:vault-note-draft:${bookId}`, JSON.stringify({ title, body: nextBody, folderSegments: payload?.folderSegments ?? chapterFolder }))
      } catch {
        // local draft persistence is best-effort
      }
      setTargetSaveState("vault_note", "error")
      setTargetRetry("vault_note", () => saveWorkspaceVaultNote(payload).then(() => undefined))
      captureTiming("save_latency_ms", startedAt, { book_id: bookId, save_target: "vault_note", save_state: "error" })
      capture("save_failure_count", { book_id: bookId, save_target: "vault_note" })
      setStatusMessage("Could not save to workspace notes. Your draft is still kept locally.")
      return null
    }
  }

  return {
    persistNote,
    saveWorkspaceVaultNote,
  }
}
