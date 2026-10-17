import type { VaultNote } from "@/types/book"

import { Tooltip } from "@/components/ui/Tooltip"
import { formatRelativeTime, noteTitle } from "./VaultNotesEditor.helpers"
import { IconCheck, IconCopy, IconDocument, IconExpand, IconStar } from "./VaultNotesEditor.icons"

type EditorMode = "edit" | "preview" | "split"

export function VaultNoteEditorHeader({
  busy = false,
  isDark,
  isFavorite,
  mode,
  selectedNote,
  status,
  onCopyReference,
  onFavoriteToggle,
  onModeChange,
  onOpenGraph,
  onSaveNow,
}: {
  busy?: boolean
  isDark: boolean
  isFavorite: boolean
  mode: EditorMode
  selectedNote: VaultNote
  status: string | null
  onCopyReference: () => void
  onFavoriteToggle: () => void
  onModeChange: (value: EditorMode) => void
  onOpenGraph: () => void
  onSaveNow: () => void
}) {
  return (
    <div className={`flex flex-col gap-4 border-b px-4 py-4 ${isDark ? "border-white/[0.08]" : "border-stone-200"} lg:flex-row lg:items-start lg:justify-between`}>
      <div className="min-w-0">
        <div className={`flex flex-wrap items-center gap-2 text-sm ${isDark ? "text-slate-400" : "text-stone-600"}`}>
          {selectedNote.path.split("/").slice(0, -1).map((segment, index, array) => (
            <div key={`${segment}-${index}`} className="flex min-w-0 items-center gap-2 break-words">
              <span className={index === 0 ? "inline-flex items-center gap-2" : ""}>
                {index === 0 ? <IconDocument small /> : null}
                {segment}
              </span>
              {index < array.length - 1 ? <span>&gt;</span> : null}
            </div>
          ))}
          {!selectedNote.path.includes("/") ? <span className="inline-flex items-center gap-2"><IconDocument small />Notes</span> : null}
        </div>

        <div className="mt-3 flex items-start gap-2">
          <div className="min-w-0">
            <h3 className={`break-words text-2xl font-semibold tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>{noteTitle(selectedNote.path)}</h3>
          </div>
          <Tooltip content={isFavorite ? "Remove from favorites" : "Add to favorites"}>
            <button
              type="button"
              aria-label={isFavorite ? "Remove from favorites" : "Add to favorites"}
              onClick={onFavoriteToggle}
              className={`rounded-sm p-1.5 transition-colors ${isFavorite ? "text-amber-300" : isDark ? "text-slate-400 hover:bg-white/[0.05] hover:text-white" : "text-stone-600 hover:bg-stone-100 hover:text-stone-900"}`}
            >
              <IconStar filled={isFavorite} />
            </button>
          </Tooltip>
        </div>

        <div className={`mt-3 flex gap-4 border-b ${isDark ? "border-white/[0.08]" : "border-stone-200"}`} role="tablist" aria-label="Note editor mode">
          {(["edit", "preview", "split"] as EditorMode[]).map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={mode === value}
              id={`note-mode-${value}`}
              aria-controls="note-editor-panel"
              tabIndex={mode === value ? 0 : -1}
              onKeyDown={(event) => {
                const modes: EditorMode[] = ["edit", "preview", "split"]
                const index = modes.indexOf(value)
                const next = event.key === "Home" ? 0 : event.key === "End" ? 2 : event.key === "ArrowRight" ? (index + 1) % 3 : event.key === "ArrowLeft" ? (index + 2) % 3 : -1
                if (next < 0) return
                event.preventDefault(); onModeChange(modes[next]); document.getElementById(`note-mode-${modes[next]}`)?.focus()
              }}
              onClick={() => onModeChange(value)}
              className={`border-b-2 px-0 py-2 text-sm font-medium capitalize transition-colors ${
                mode === value
                  ? isDark ? "border-emerald-300 text-emerald-200" : "border-teal-700 text-teal-800"
                  : isDark
                    ? "border-transparent text-slate-400 hover:text-slate-200"
                    : "border-transparent text-stone-600 hover:text-stone-800"
              }`}
            >
              {value}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 lg:justify-end">
        <span role="status" className={`text-sm ${isDark ? "text-slate-400" : "text-stone-600"}`}>{status || `Saved ${formatRelativeTime(selectedNote.updated_at)}`}</span>
        <button type="button" disabled={busy} onClick={onSaveNow} className={`rounded-sm border px-3 py-2 text-sm font-medium ${isDark ? "border-white/[0.08] bg-white/[0.03] text-slate-200 hover:bg-white/[0.07]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}>
          <span className="inline-flex items-center gap-2"><IconCheck />Save now</span>
        </button>
        <Tooltip content="Copy note reference">
          <button type="button" aria-label="Copy note reference" onClick={onCopyReference} className={`rounded-sm border p-2.5 ${isDark ? "border-white/[0.08] bg-white/[0.03] text-slate-300 hover:bg-white/[0.07]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}>
            <IconCopy />
          </button>
        </Tooltip>
        <Tooltip content="Open full graph">
          <button type="button" disabled={busy} aria-label="Open full graph" onClick={onOpenGraph} className={`rounded-sm border p-2.5 ${isDark ? "border-white/[0.08] bg-white/[0.03] text-slate-300 hover:bg-white/[0.07]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}>
            <IconExpand />
          </button>
        </Tooltip>
      </div>
    </div>
  )
}
