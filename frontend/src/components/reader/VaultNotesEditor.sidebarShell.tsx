import type { ReactNode } from "react"

import { IconDocument, IconPlus } from "./VaultNotesEditor.icons"

export function VaultNotesSidebarShell({
  bookTitle,
  busy,
  children,
  isDark,
  onCreateNote,
}: {
  bookTitle: string
  busy: boolean
  children: ReactNode
  isDark: boolean
  onCreateNote: () => void
}) {
  return (
    <aside className={`overflow-hidden rounded-lg border ${isDark ? "border-white/[0.08] bg-[#07101d]/90" : "border-stone-200 bg-white/90"}`}>
      <div className={`border-b px-5 py-5 ${isDark ? "border-white/[0.08]" : "border-stone-200"}`}>
        <div className="flex items-center gap-3">
          <div className={`flex h-12 w-12 items-center justify-center rounded-md ${isDark ? "bg-emerald-500/12 text-emerald-200" : "bg-emerald-50 text-emerald-700"}`}>
            <IconDocument />
          </div>
          <div className="min-w-0">
            <h3 className={`truncate text-xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{bookTitle}</h3>
            <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Vault notes workspace</p>
          </div>
        </div>
      </div>

      <div className="p-4">{children}</div>

      <div className={`border-t px-4 py-4 ${isDark ? "border-white/[0.08]" : "border-stone-200"}`}>
        <button type="button" onClick={onCreateNote} disabled={busy} className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium ${isDark ? "text-sky-200 hover:bg-white/[0.04]" : "text-sky-700 hover:bg-stone-100"}`}>
          <IconPlus />
          New note
        </button>
      </div>
    </aside>
  )
}
