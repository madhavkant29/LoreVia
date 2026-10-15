import type { RefObject } from "react"

import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { IconPlus, IconUpload } from "./VaultNotesEditor.icons"

export function VaultNotesTopbar({
  busy,
  importInputRef,
  isDark,
  inspectorOpen,
  selectedNoteAvailable,
  onCreateNote,
  onDuplicateCurrent,
  onExportNotes,
  onImportNotes,
  onToggleInspector,
  onOpenLibrary,
}: {
  busy: boolean
  importInputRef: RefObject<HTMLInputElement | null>
  isDark: boolean
  inspectorOpen: boolean
  selectedNoteAvailable: boolean
  onCreateNote: () => void
  onDuplicateCurrent: () => void
  onExportNotes: () => void
  onImportNotes: (file: File) => void
  onToggleInspector: () => void
  onOpenLibrary: () => void
}) {
  return (
    <div className={`flex flex-col gap-4 border-b pb-4 lg:flex-row lg:items-end lg:justify-between ${isDark ? "border-white/[0.08]" : "border-stone-200"}`}>
      <div>
        <h1 className={`text-xl font-semibold tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>Notes</h1>
        <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-600"}`}>Organize references and edit one note at a time.</p>
      </div>

      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={onOpenLibrary} className={`rounded-sm border px-3 py-2 text-sm xl:hidden ${isDark ? "border-white/10 text-slate-300" : "border-stone-200 text-stone-700"}`}>Browse notes</button>
        <button type="button" onClick={onCreateNote} disabled={busy} className="inline-flex items-center gap-2 rounded-sm bg-teal-800 px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:opacity-60">
          <IconPlus />
          New note
        </button>
        <button type="button" onClick={() => importInputRef.current?.click()} disabled={busy} className={`inline-flex items-center gap-2 rounded-sm border px-3 py-2 text-sm font-medium ${isDark ? "border-white/10 text-slate-300 hover:bg-white/[0.04]" : "border-stone-200 text-stone-600 hover:bg-stone-50"}`}>
          <IconUpload />
          Import ZIP
        </button>
        <button type="button" onClick={onExportNotes} disabled={busy} className={`inline-flex items-center gap-2 rounded-sm border px-3 py-2 text-sm font-medium ${isDark ? "border-white/10 text-slate-300 hover:bg-white/[0.04]" : "border-stone-200 text-stone-600 hover:bg-stone-50"}`}>
          <IconUpload className="rotate-180" />
          Export ZIP
        </button>
        <button
          type="button"
          aria-pressed={inspectorOpen}
          onClick={onToggleInspector}
          disabled={!selectedNoteAvailable}
          className={`rounded-sm border px-3 py-2 text-sm font-medium transition-colors disabled:opacity-50 ${inspectorOpen ? isDark ? "border-teal-300 text-teal-200" : "border-teal-700 text-teal-700" : isDark ? "border-white/10 text-slate-300 hover:bg-white/[0.04]" : "border-stone-200 text-stone-600 hover:bg-stone-50"}`}
        >
          Details
        </button>

          <button type="button" aria-label="Duplicate selected note" onClick={onDuplicateCurrent} disabled={!selectedNoteAvailable || busy} className={`inline-flex items-center justify-center px-3 py-2 text-sm rounded-sm border ${isDark ? "border-white/10 text-slate-300" : "border-stone-200 text-stone-600"}`}>
            Duplicate
          </button>
        <button type="button" onClick={() => window.dispatchEvent(new Event(SUPPORT_HELP_EVENT))} className={`rounded-sm border px-3 py-2 text-sm ${isDark ? "border-white/10 text-slate-300" : "border-stone-200 text-stone-700"}`}>Help</button>
        <input
          ref={importInputRef}
          type="file"
          accept=".zip,application/zip"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) onImportNotes(file)
            event.currentTarget.value = ""
          }}
        />
      </div>
    </div>
  )
}
