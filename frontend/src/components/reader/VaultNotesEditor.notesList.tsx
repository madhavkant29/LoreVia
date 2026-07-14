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
      <p className={`text-3xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Notes</p>
      <div className="mt-3 flex gap-2" role="tablist" aria-label="Notes view">
        <button type="button" role="tab" aria-selected={notesView === "recent"} onClick={() => onViewChange("recent")} className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${notesView === "recent" ? "bg-emerald-500/16 text-emerald-200" : isDark ? "text-slate-400 hover:bg-white/[0.05] hover:text-white" : "text-stone-500 hover:bg-stone-100 hover:text-stone-900"}`}>
          Recent
        </button>
        <button type="button" role="tab" aria-selected={notesView === "favorites"} onClick={() => onViewChange("favorites")} className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${notesView === "favorites" ? "bg-emerald-500/16 text-emerald-200" : isDark ? "text-slate-400 hover:bg-white/[0.05] hover:text-white" : "text-stone-500 hover:bg-stone-100 hover:text-stone-900"}`}>
          Favorites
        </button>
      </div>

      <div className="mt-3 max-h-[18rem] space-y-1 overflow-auto pr-1">
        {displayedNotes.length === 0 ? (
          <div className={`rounded-md border border-dashed px-4 py-8 text-center text-sm ${isDark ? "border-white/[0.08] text-slate-500" : "border-stone-300 text-stone-500"}`}>
            {notesView === "favorites" ? "Star a note to keep it here." : "No notes match that search."}
          </div>
        ) : (
          displayedNotes.map((note) => {
            const active = note.path === selectedPath
            return (
              <button
                key={note.path}
                type="button"
                onClick={() => onSelectNote(note.path)}
                draggable
                onDragStart={(event) => {
                  const payload: NotesDragItem = { kind: "note", path: note.path }
                  event.dataTransfer.effectAllowed = "move"
                  event.dataTransfer.setData("application/lorevia-note-item", JSON.stringify(payload))
                }}
                className={`flex w-full items-center justify-between gap-3 rounded-md px-3 py-3 text-left transition ${
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
                    <span className="truncate text-sm font-medium">{noteTitle(note.path)}</span>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <span className={`text-xs ${active ? (isDark ? "text-slate-300" : "text-stone-600") : isDark ? "text-slate-500" : "text-stone-400"}`}>{formatRelativeTime(note.updated_at)}</span>
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
