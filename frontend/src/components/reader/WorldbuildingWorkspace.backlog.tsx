import type { WorldNote } from "@/types/world-building"

import { BacklogColumn, LoadingState, NoteCard, WorkspaceCard } from "./WorldbuildingWorkspace.components"
import { secondaryButtonClass } from "./WorldbuildingWorkspace.helpers"

export function SavedCleanupBacklogCard({
  isDark,
  notesLoading,
  chapterFilter,
  loadingChapterNotes,
  isChapterFiltered,
  openNotes,
  addressedNotes,
  noteStatusId,
  onChapterFilterChange,
  onFetchNotesByChapter,
  onClearChapterFilter,
  onRefreshNotes,
  onResolveNote,
  onReopenNote,
  onDeleteNote,
}: {
  isDark: boolean
  notesLoading: boolean
  chapterFilter: string
  loadingChapterNotes: boolean
  isChapterFiltered: boolean
  openNotes: WorldNote[]
  addressedNotes: WorldNote[]
  noteStatusId: string | null
  onChapterFilterChange: (value: string) => void
  onFetchNotesByChapter: () => void
  onClearChapterFilter: () => void
  onRefreshNotes: () => void
  onResolveNote: (noteId: string) => void
  onReopenNote: (noteId: string) => void
  onDeleteNote: (noteId: string) => void
}) {
  return (
    <WorkspaceCard
      number="9"
      sectionLabel="Saved Cleanup Backlog"
      title="Saved cleanup backlog"
      description="Track open cleanup notes and addressed items."
      isDark={isDark}
      action={(
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="number"
            className={`w-20 rounded-md border px-2 py-1.5 text-xs ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`}
            placeholder="Ch."
            value={chapterFilter}
            onChange={(event) => onChapterFilterChange(event.target.value)}
            min={1}
          />
          <button type="button" disabled={loadingChapterNotes} onClick={onFetchNotesByChapter} className={secondaryButtonClass(isDark)}>
            {loadingChapterNotes ? "Loading..." : "Filter by chapter"}
          </button>
          {isChapterFiltered ? (
            <button type="button" onClick={onClearChapterFilter} className={secondaryButtonClass(isDark)}>
              Show all
            </button>
          ) : null}
          <button type="button" onClick={onRefreshNotes} className={secondaryButtonClass(isDark)}>
            Refresh notes
          </button>
        </div>
      )}
    >
      {notesLoading ? (
        <LoadingState label="Loading saved world-gap notes..." isDark={isDark} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <BacklogColumn
            label="Open Notes"
            count={openNotes.length}
            isDark={isDark}
            emptyTitle="No open world gap notes right now."
            items={openNotes.map((note) => (
              <NoteCard
                key={note.id}
                note={note}
                isDark={isDark}
                noteStatusId={noteStatusId}
                onPrimaryAction={() => onResolveNote(note.id)}
                onDelete={() => onDeleteNote(note.id)}
                primaryLabel={noteStatusId === note.id ? "Updating..." : "Resolve"}
              />
            ))}
          />
          <BacklogColumn
            label="Addressed Notes"
            count={addressedNotes.length}
            isDark={isDark}
            emptyTitle="No resolved notes yet."
            items={addressedNotes.map((note) => (
              <NoteCard
                key={note.id}
                note={note}
                isDark={isDark}
                noteStatusId={noteStatusId}
                onPrimaryAction={() => onReopenNote(note.id)}
                onDelete={() => onDeleteNote(note.id)}
                primaryLabel={noteStatusId === note.id ? "Updating..." : "Reopen"}
                addressed
              />
            ))}
          />
        </div>
      )}
    </WorkspaceCard>
  )
}
