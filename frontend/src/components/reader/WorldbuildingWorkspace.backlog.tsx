import type { WorldNote } from "@/types/world-building"

import { LoadingState } from "./WorldbuildingWorkspace.components"
import { bodyTextClass, mutedTextClass, secondaryButtonClass, titleTextClass } from "./WorldbuildingWorkspace.helpers"

export function SavedCleanupBacklogCard({
  isDark,
  notesLoading,
  chapterFilter,
  loadingChapterNotes,
  isChapterFiltered,
  openNotes,
  addressedNotes,
  noteStatusId,
  appliedChapter,
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
  appliedChapter?: number | null
  onChapterFilterChange: (value: string) => void
  onFetchNotesByChapter: () => void
  onClearChapterFilter: () => void
  onRefreshNotes: () => void
  onResolveNote: (noteId: string) => void
  onReopenNote: (noteId: string) => void
  onDeleteNote: (noteId: string) => void
}) {
  const renderNote = (note: WorldNote, addressed: boolean) => (
    <article key={note.id} className={`py-4 ${addressed ? "opacity-80" : ""}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h4 className={`text-sm font-semibold ${titleTextClass(isDark)}`}>{note.title || "Untitled note"}</h4>
          <p className={`mt-1 text-xs ${mutedTextClass(isDark)}`}>
            {addressed
              ? `Resolved ${note.addressed_at ? new Date(note.addressed_at).toLocaleDateString() : "recently"}`
              : `${note.context_label || "General world gap"}${note.chapter_number ? ` · Chapter ${note.chapter_number}` : ""}`}
          </p>
          <p className={`mt-2 text-sm leading-6 ${bodyTextClass(isDark)}`}>{note.body}</p>
          {note.suggested_fix ? <p className={`mt-2 text-sm leading-6 ${isDark ? "text-amber-100" : "text-amber-900"}`}><span className={mutedTextClass(isDark)}>Next step: </span>{note.suggested_fix}</p> : null}
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <button type="button" aria-label={`${addressed ? "Reopen" : "Resolve"}: ${note.title || "Untitled note"}`} onClick={() => addressed ? onReopenNote(note.id) : onResolveNote(note.id)} disabled={!!noteStatusId || loadingChapterNotes} className={`text-sm font-medium underline decoration-transparent underline-offset-4 hover:decoration-current disabled:opacity-50 ${isDark ? "text-slate-200" : "text-stone-700"}`}>
            {noteStatusId === note.id ? "Updating…" : addressed ? "Reopen" : "Resolve"}
          </button>
          <button type="button" aria-label={`Delete: ${note.title || "Untitled note"}`} onClick={() => onDeleteNote(note.id)} disabled={!!noteStatusId || loadingChapterNotes} className={`text-sm underline decoration-transparent underline-offset-4 hover:decoration-current disabled:opacity-50 ${isDark ? "text-rose-300" : "text-rose-700"}`}>Delete</button>
        </div>
      </div>
    </article>
  )

  return (
    <section aria-label="Saved cleanup backlog">
      <div className={`flex flex-col gap-4 border-b pb-4 lg:flex-row lg:items-end lg:justify-between ${isDark ? "border-white/10" : "border-stone-200"}`}>
        <div>
          <h2 className={`text-lg font-semibold ${titleTextClass(isDark)}`}>Saved cleanup backlog</h2>
          <p className={`mt-1 text-sm ${mutedTextClass(isDark)}`}>Keep confirmed world gaps separate from raw analysis.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="number"
            aria-label="Chapter number filter"
            className={`w-20 rounded-md border px-2 py-1.5 text-xs ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`}
            placeholder="Ch."
            value={chapterFilter}
            onChange={(event) => onChapterFilterChange(event.target.value)}
            min={1}
          />
          <button type="button" disabled={loadingChapterNotes || !!noteStatusId} onClick={onFetchNotesByChapter} className={secondaryButtonClass(isDark)}>
            {loadingChapterNotes ? "Loading..." : "Filter by chapter"}
          </button>
          {isChapterFiltered ? (
            <button type="button" onClick={onClearChapterFilter} className={secondaryButtonClass(isDark)}>
              Show all
            </button>
          ) : null}
          <button type="button" disabled={loadingChapterNotes || !!noteStatusId} onClick={onRefreshNotes} className={secondaryButtonClass(isDark)}>
            Refresh notes
          </button>
        </div>
      </div>
      <p className="mt-3 text-sm">{appliedChapter ? `Showing chapter ${appliedChapter} cleanup notes.` : "Showing all cleanup notes."} {chapterFilter && Number(chapterFilter) !== appliedChapter ? "Apply the filter to change these results." : ""}</p>
      {notesLoading ? (
        <div className="mt-4"><LoadingState label="Loading saved world-gap notes..." isDark={isDark} /></div>
      ) : (
        <div>
          <div className="flex items-baseline justify-between pt-4">
            <h3 className={`text-sm font-semibold ${titleTextClass(isDark)}`}>Open Notes</h3>
            <span className={`text-xs ${mutedTextClass(isDark)}`}>{openNotes.length}</span>
          </div>
          {openNotes.length ? (
            <div className={`divide-y ${isDark ? "divide-white/10" : "divide-stone-200"}`}>{openNotes.map((note) => renderNote(note, false))}</div>
          ) : <p className={`py-5 text-sm ${mutedTextClass(isDark)}`}>No open world gap notes right now.</p>}

          <details className={`border-t pt-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
            <summary className={`cursor-pointer text-sm font-semibold ${titleTextClass(isDark)}`}>Addressed Notes <span className={`ml-1 font-normal ${mutedTextClass(isDark)}`}>{addressedNotes.length}</span></summary>
            {addressedNotes.length ? (
              <div className={`mt-2 divide-y ${isDark ? "divide-white/10" : "divide-stone-200"}`}>{addressedNotes.map((note) => renderNote(note, true))}</div>
            ) : <p className={`py-5 text-sm ${mutedTextClass(isDark)}`}>No resolved notes yet.</p>}
          </details>
        </div>
      )}
    </section>
  )
}
