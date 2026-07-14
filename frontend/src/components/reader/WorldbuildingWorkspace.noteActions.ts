import { worldBuildingApi } from "@/lib/api/worldBuilding"
import type { WorldGapItem, WorldIntegrationResult, WorldNote } from "@/types/world-building"

type Refetch = () => Promise<unknown>

interface UseWorldbuildingNoteActionsArgs {
  bookId: string
  chapterFilter: string
  refetchNotes: Refetch
  setChapterFilter: (value: string) => void
  setChapterNotes: (value: WorldNote[] | null) => void
  setLoadingChapterNotes: (value: boolean) => void
  setNoteSavingId: (value: string | null) => void
  setNoteStatusId: (value: string | null) => void
}

export function useWorldbuildingNoteActions({
  bookId,
  chapterFilter,
  refetchNotes,
  setChapterFilter,
  setChapterNotes,
  setLoadingChapterNotes,
  setNoteSavingId,
  setNoteStatusId,
}: UseWorldbuildingNoteActionsArgs) {
  async function handleFetchNotesByChapter() {
    const chapter = Number(chapterFilter)
    if (!Number.isFinite(chapter) || chapter < 1) return
    setLoadingChapterNotes(true)
    try {
      const result = await worldBuildingApi.getNotesByChapter(bookId, chapter)
      setChapterNotes(result)
    } catch {
      setChapterNotes([])
    } finally {
      setLoadingChapterNotes(false)
    }
  }

  function handleClearChapterFilter() {
    setChapterFilter("")
    setChapterNotes(null)
  }

  const saveGapAsNote = async (item: WorldGapItem) => {
    setNoteSavingId(item.id)
    try {
      await worldBuildingApi.createNote(bookId, {
        world_document_id: item.world_document_id,
        note_type: "world_gap",
        chapter_number: item.story_chapter_number ?? null,
        title: item.title,
        body: item.description,
        priority: item.priority >= 8 ? "critical" : item.priority >= 6 ? "high" : "medium",
        status: "open",
        linked_gap_id: item.id,
        context_label: item.world_document_title ?? item.character_name ?? null,
        suggested_fix: item.suggested_fix,
      })
      await refetchNotes()
    } finally {
      setNoteSavingId(null)
    }
  }

  const setNoteStatus = async (noteId: string, status: string) => {
    setNoteStatusId(noteId)
    try {
      await worldBuildingApi.updateNoteStatus(bookId, noteId, status)
      await refetchNotes()
    } finally {
      setNoteStatusId(null)
    }
  }

  const saveIntegrationAsNote = async (item: WorldIntegrationResult["integration_opportunities"][number]) => {
    setNoteSavingId(item.id)
    try {
      await worldBuildingApi.createNote(bookId, {
        world_document_id: item.world_document_id,
        note_type: "world_integration",
        chapter_number: item.target_chapter ?? null,
        title: item.element_name,
        body: item.description,
        priority: item.priority >= 8 ? "critical" : item.priority >= 6 ? "high" : "medium",
        status: "open",
        linked_integration_id: item.id,
        context_label: item.world_document_title ?? item.element_type,
        suggested_fix: item.suggestions.join(" "),
      })
      await refetchNotes()
    } finally {
      setNoteSavingId(null)
    }
  }

  const deleteNote = async (noteId: string) => {
    setNoteStatusId(noteId)
    try {
      await worldBuildingApi.deleteNote(bookId, noteId)
      await refetchNotes()
    } finally {
      setNoteStatusId(null)
    }
  }

  return {
    deleteNote,
    handleClearChapterFilter,
    handleFetchNotesByChapter,
    saveGapAsNote,
    saveIntegrationAsNote,
    setNoteStatus,
  }
}
