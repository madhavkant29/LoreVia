import type { VaultNote } from "@/types/book"

import { formatRelativeTime, noteTitle, type NotesDragItem } from "./VaultNotesEditor.helpers"
import { IconDocument } from "./VaultNotesEditor.icons"

type NotesView = "recent" | "favorites"

export function VaultNotesList({
  displayedNotes,
  isDark,
  notesView,
  selectedPath,
  onSelectNote,
  onViewChange,
}: {
  displayedNotes: VaultNote[]
  isDark: boolean
  notesView: NotesView
  selectedPath: string | null
  onSelectNote: (path: string) => void
  onViewChange: (view: NotesView) => void
}) {
  return (
    <div className="mt-6">
      <p className={`text-xs font-medium ${isDark ? "text-slate-400" : "text-stone-600"}`}>Notes</p>
      <div className={`mt-2 flex gap-4 border-b ${isDark ? "border-white/[0.08]" : "border-stone-200"}`} role="group" aria-label="Notes view">
        <button type="button" aria-pressed={notesView === "recent"} onClick={() => onViewChange("recent")} className={`border-b-2 px-1 pb-2 text-sm font-medium transition-colors ${notesView === "recent" ? isDark ? "border-teal-300 text-white" : "border-teal-800 text-stone-950" : isDark ? "border-transparent text-slate-400 hover:text-white" : "border-transparent text-stone-600 hover:text-stone-900"}`}>
          Recent
        </button>
        <button type="button" aria-pressed={notesView === "favorites"} onClick={() => onViewChange("favorites")} className={`border-b-2 px-1 pb-2 text-sm font-medium transition-colors ${notesView === "favorites" ? isDark ? "border-teal-300 text-white" : "border-teal-800 text-stone-950" : isDark ? "border-transparent text-slate-400 hover:text-white" : "border-transparent text-stone-600 hover:text-stone-900"}`}>
          Favorites
        </button>
      </div>

      <div className="mt-3 max-h-[18rem] space-y-1 overflow-auto pr-1">
        {displayedNotes.length === 0 ? (
          <div className={`border-t px-1 py-5 text-sm ${isDark ? "border-white/[0.08] text-slate-400" : "border-stone-200 text-stone-600"}`}>
            {notesView === "favorites" ? "Star a note to keep it here." : "No notes here. Clear filters or create a new note."}
          </div>
        ) : (
          displayedNotes.map((note) => {
            const active = note.path === selectedPath
            return (
              <button
                key={note.path}
                type="button"
                onClick={() => onSelectNote(note.path)}
                aria-current={active ? "true" : undefined}
                draggable
                onDragStart={(event) => {
                  const payload: NotesDragItem = { kind: "note", path: note.path }
                  event.dataTransfer.effectAllowed = "move"
                  event.dataTransfer.setData("application/lorevia-note-item", JSON.stringify(payload))
                }}
                className={`flex w-full items-center justify-between gap-3 rounded-sm px-3 py-3 text-left transition ${
                  active
                    ? isDark
                      ? "bg-white/[0.06] text-white"
                      : "bg-stone-100 text-stone-950"
                    : isDark
                      ? "text-slate-300 hover:bg-white/[0.04]"
                      : "text-stone-700 hover:bg-stone-100"
                }`}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <IconDocument small />
                    <span className="break-words text-sm font-medium">{noteTitle(note.path)}</span>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <span className={`text-xs ${active ? (isDark ? "text-slate-300" : "text-stone-600") : isDark ? "text-slate-400" : "text-stone-600"}`}>{formatRelativeTime(note.updated_at)}</span>
                  {active ? <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" /> : null}
                </div>
              </button>
            )
          })
        )}
      </div>
    </div>
  )
}
