import { useRef, useState, type Dispatch, type SetStateAction } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { worldBuildingApi } from "@/lib/api/worldBuilding"
import { getApiErrorDetail } from "@/lib/utils/apiErrors"
import type { WorldGapItem, WorldIntegrationResult, WorldNote } from "@/types/world-building"

type Refetch = () => Promise<unknown>

interface UseWorldbuildingNoteActionsArgs {
  bookId: string
  chapterFilter: string
  refetchNotes: Refetch
  setChapterFilter: (value: string) => void
  setChapterNotes: Dispatch<SetStateAction<WorldNote[] | null>>
  setLoadingChapterNotes: (value: boolean) => void
  setNoteSavingId: (value: string | null) => void
  setNoteStatusId: (value: string | null) => void
}

export function useWorldbuildingNoteActions({ bookId, chapterFilter, refetchNotes, setChapterFilter, setChapterNotes, setLoadingChapterNotes, setNoteSavingId, setNoteStatusId }: UseWorldbuildingNoteActionsArgs) {
  const client = useQueryClient()
  const key = [`worldbuilding:${bookId}:notes`]
  const lock = useRef(false)
  const generation = useRef(0)
  const applied = useRef<number | null>(null)
  const [appliedChapter, setAppliedChapter] = useState<number | null>(null)
  const [notesMessage, setNotesMessage] = useState<string | null>(null)

  async function handleFetchNotesByChapter(chapter = Number(chapterFilter)) {
    if (lock.current) return
    if (!Number.isSafeInteger(chapter) || chapter < 1) { setNotesMessage("Enter a whole chapter number of 1 or higher."); return }
    const token = ++generation.current
    setLoadingChapterNotes(true); setNotesMessage(null)
    try {
      const result = await worldBuildingApi.getNotesByChapter(bookId, chapter)
      if (token !== generation.current) return
      applied.current = chapter; setAppliedChapter(chapter); setChapterNotes(result)
    } catch (error) {
      if (token === generation.current) setNotesMessage(`${getApiErrorDetail(error) ?? "Could not load notes for that chapter."} The previous results are retained. Try the filter again.`)
    } finally { if (token === generation.current) setLoadingChapterNotes(false) }
  }

  function handleClearChapterFilter() {
    generation.current++; applied.current = null; setAppliedChapter(null)
    setLoadingChapterNotes(false); setChapterFilter(""); setChapterNotes(null); setNotesMessage(null)
  }

  async function refreshNotes() {
    if (lock.current) return
    if (applied.current !== null) return handleFetchNotesByChapter(applied.current)
    const result = await refetchNotes() as { error?: unknown }
    setNotesMessage(result?.error ? "Could not refresh cleanup notes. Previous results are retained." : "Cleanup notes refreshed.")
  }

  function updateNotes(update: (notes: WorldNote[]) => WorldNote[]) {
    generation.current++; setLoadingChapterNotes(false)
    client.setQueryData<WorldNote[]>(key, (current = []) => update(current))
    setChapterNotes((current) => current === null ? null : update(current).filter((note) => note.chapter_number === applied.current))
  }

  async function createNote(id: string, payload: Parameters<typeof worldBuildingApi.createNote>[1]) {
    if (lock.current) return
    const existing = client.getQueryData<WorldNote[]>(key) ?? []
    if (existing.some((note) => (payload.linked_gap_id && note.linked_gap_id === payload.linked_gap_id) || (payload.linked_integration_id && note.linked_integration_id === payload.linked_integration_id))) {
      setNotesMessage("This finding is already saved in cleanup history. Reopen its note if it needs another pass."); return
    }
    lock.current = true; setNoteSavingId(id); setNotesMessage(null)
    try {
      const saved = await worldBuildingApi.createNote(bookId, payload)
      updateNotes((notes) => [saved, ...notes.filter((note) => note.id !== saved.id)])
      setNotesMessage("Saved to cleanup. Resolve it after making the manuscript or canon change.")
    } catch (error) { setNotesMessage(`${getApiErrorDetail(error) ?? "Could not confirm the note save."} The finding is retained. Refresh cleanup notes before retrying to avoid a duplicate.`) }
    finally { lock.current = false; setNoteSavingId(null) }
  }

  const saveGapAsNote = (item: WorldGapItem) => createNote(item.id, {
    world_document_id: item.world_document_id, note_type: "world_gap", chapter_number: item.story_chapter_number ?? null,
    title: item.title, body: item.description, priority: item.priority >= 8 ? "critical" : item.priority >= 6 ? "high" : "medium",
    status: "open", linked_gap_id: item.id, context_label: item.world_document_title ?? item.character_name ?? null, suggested_fix: item.suggested_fix,
  })

  const saveIntegrationAsNote = (item: WorldIntegrationResult["integration_opportunities"][number]) => createNote(item.id, {
    world_document_id: item.world_document_id, note_type: "world_integration", chapter_number: item.target_chapter ?? null,
    title: item.element_name, body: item.description, priority: item.priority >= 8 ? "critical" : item.priority >= 6 ? "high" : "medium",
    status: "open", linked_integration_id: item.id, context_label: item.world_document_title ?? item.element_type, suggested_fix: item.suggestions.join(" "),
  })

  async function setNoteStatus(noteId: string, status: string) {
    if (lock.current) return
    lock.current = true; setNoteStatusId(noteId); setNotesMessage(null)
    try {
      const saved = await worldBuildingApi.updateNoteStatus(bookId, noteId, status)
      updateNotes((notes) => notes.map((note) => note.id === noteId ? saved : note))
      setNotesMessage(status === "addressed" ? "Marked resolved. This records your decision; it does not edit the manuscript." : "Reopened the cleanup note.")
    } catch (error) { setNotesMessage(`${getApiErrorDetail(error) ?? "Could not update the note."} Its previous status is retained. Try again.`) }
    finally { lock.current = false; setNoteStatusId(null) }
  }

  async function deleteNote(noteId: string) {
    if (lock.current || !window.confirm("Delete this cleanup note? This cannot be undone and does not change your manuscript or canon sources.")) return
    lock.current = true; setNoteStatusId(noteId); setNotesMessage(null)
    try { await worldBuildingApi.deleteNote(bookId, noteId); updateNotes((notes) => notes.filter((note) => note.id !== noteId)); setNotesMessage("Deleted the cleanup note.") }
    catch (error) { setNotesMessage(`${getApiErrorDetail(error) ?? "Could not delete the note."} Refresh notes to check its current state before retrying.`) }
    finally { lock.current = false; setNoteStatusId(null) }
  }

  return { deleteNote, handleClearChapterFilter, handleFetchNotesByChapter, saveGapAsNote, saveIntegrationAsNote, setNoteStatus, refreshNotes, notesMessage, appliedChapter }
}
