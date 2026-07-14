import type { RefObject } from "react"

import { Tooltip } from "@/components/ui/Tooltip"
import { IconMore, IconPlus, IconUpload } from "./VaultNotesEditor.icons"

export function VaultNotesTopbar({
  busy,
  importInputRef,
  isDark,
  selectedNoteAvailable,
  onCreateNote,
  onDuplicateCurrent,
  onExportNotes,
  onImportNotes,
}: {
  busy: boolean
  importInputRef: RefObject<HTMLInputElement | null>
  isDark: boolean
  selectedNoteAvailable: boolean
  onCreateNote: () => void
  onDuplicateCurrent: () => void
  onExportNotes: () => void
  onImportNotes: (file: File) => void
}) {
  return (
    <div className="flex flex-col gap-4 border-b border-white/[0.08] pb-4 lg:flex-row lg:items-center lg:justify-between">
      <div>
        <h2 className={`font-serif text-[2rem] tracking-[-0.04em] ${isDark ? "text-white" : "text-stone-950"}`}>Vault notes workspace</h2>
        <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>A book-native vault for character notes, links, themes, and evolving story context.</p>
      </div>

      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={onCreateNote} disabled={busy} className="inline-flex items-center gap-2 rounded-md bg-[#1f615d] px-4 py-3 text-sm font-semibold text-white disabled:opacity-60">
          <IconPlus />
          New note
        </button>
        <button type="button" onClick={() => importInputRef.current?.click()} disabled={busy} className={`inline-flex items-center gap-2 rounded-md border px-4 py-3 text-sm font-medium ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
          <IconUpload />
          Import ZIP
        </button>
        <button type="button" onClick={onExportNotes} disabled={busy} className="inline-flex items-center gap-2 rounded-md bg-[#1f615d] px-4 py-3 text-sm font-semibold text-white">
          <IconUpload className="rotate-180" />
          Export ZIP
        </button>
        <Tooltip content="Duplicate selected note">
          <button type="button" aria-label="Duplicate selected note" onClick={onDuplicateCurrent} disabled={!selectedNoteAvailable || busy} className={`inline-flex h-[3rem] w-[3rem] items-center justify-center rounded-md border ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
            <IconMore />
          </button>
        </Tooltip>
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
