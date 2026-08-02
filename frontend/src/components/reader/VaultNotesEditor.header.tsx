import type { VaultNote } from "@/types/book"

import { Tooltip } from "@/components/ui/Tooltip"
import { formatRelativeTime, noteTitle } from "./VaultNotesEditor.helpers"
import { IconCheck, IconCopy, IconDocument, IconExpand, IconStar } from "./VaultNotesEditor.icons"

type EditorMode = "edit" | "preview" | "split"

export function VaultNoteEditorHeader({
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
    <div className={`flex flex-col gap-5 border-b px-5 py-4 ${isDark ? "border-white/[0.08]" : "border-stone-200"} lg:flex-row lg:items-start lg:justify-between`}>
      <div className="min-w-0">
        <div className={`flex flex-wrap items-center gap-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
          {selectedNote.path.split("/").slice(0, -1).map((segment, index, array) => (
            <div key={`${segment}-${index}`} className="flex items-center gap-2">
              <span className={index === 0 ? "inline-flex items-center gap-2" : ""}>
                {index === 0 ? <IconDocument small /> : null}
                {segment}
              </span>
              {index < array.length - 1 ? <span>&gt;</span> : null}
            </div>
          ))}
          {selectedNote.path.includes("/") ? <span>&gt;</span> : <IconDocument small />}
          <span className={`font-medium ${isDark ? "text-slate-200" : "text-stone-800"}`}>{noteTitle(selectedNote.path)}</span>
        </div>

        <div className="mt-5 flex items-start gap-3">
          <div className="min-w-0">
            <h3 className={`truncate font-serif text-5xl tracking-[-0.05em] ${isDark ? "text-white" : "text-stone-950"}`}>{noteTitle(selectedNote.path)}</h3>
          </div>
          <Tooltip content={isFavorite ? "Remove from favorites" : "Add to favorites"}>
            <button
              type="button"
              aria-label={isFavorite ? "Remove from favorites" : "Add to favorites"}
              onClick={onFavoriteToggle}
              className={`mt-1 rounded-full p-2 transition ${isFavorite ? "text-amber-300" : isDark ? "text-slate-500 hover:bg-white/[0.05] hover:text-white" : "text-stone-400 hover:bg-stone-100 hover:text-stone-900"}`}
            >
              <IconStar filled={isFavorite} />
            </button>
          </Tooltip>
        </div>

        <div className="mt-4 flex flex-wrap gap-2" role="tablist" aria-label="Note editor mode">
          {(["edit", "preview", "split"] as EditorMode[]).map((value) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={mode === value}
              onClick={() => onModeChange(value)}
              className={`rounded-md px-4 py-2 text-sm font-medium capitalize transition ${
                mode === value
                  ? "bg-emerald-500/16 text-emerald-200"
                  : isDark
                    ? "bg-white/[0.03] text-slate-300 hover:bg-white/[0.07]"
                    : "bg-stone-100 text-stone-700 hover:bg-stone-200"
              }`}
            >
              {value}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 lg:justify-end">
        <span className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{status || `Saved ${formatRelativeTime(selectedNote.updated_at)}`}</span>
        <button type="button" onClick={onSaveNow} className={`rounded-md border px-3 py-2 text-sm font-medium ${isDark ? "border-white/[0.08] bg-white/[0.03] text-slate-200 hover:bg-white/[0.07]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}>
          <span className="inline-flex items-center gap-2"><IconCheck />Save now</span>
        </button>
        <Tooltip content="Copy note reference">
          <button type="button" aria-label="Copy note reference" onClick={onCopyReference} className={`rounded-md border p-2.5 ${isDark ? "border-white/[0.08] bg-white/[0.03] text-slate-300 hover:bg-white/[0.07]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}>
            <IconCopy />
          </button>
        </Tooltip>
        <Tooltip content="Open full graph">
          <button type="button" aria-label="Open full graph" onClick={onOpenGraph} className={`rounded-md border p-2.5 ${isDark ? "border-white/[0.08] bg-white/[0.03] text-slate-300 hover:bg-white/[0.07]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}>
            <IconExpand />
          </button>
        </Tooltip>
      </div>
    </div>
  )
}
