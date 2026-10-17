import type { ReactNode } from "react"

export function VaultNotesSidebarShell({
  bookTitle,
  children,
  isDark,
}: {
  bookTitle: string
  busy: boolean
  children: ReactNode
  isDark: boolean
  onCreateNote: () => void
}) {
  return (
    <aside className={`overflow-hidden rounded-sm border ${isDark ? "border-white/[0.08]" : "border-stone-200"}`}>
      <div className={`border-b px-4 py-3 ${isDark ? "border-white/[0.08]" : "border-stone-200"}`}>
        <h3 className={`break-words text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{bookTitle}</h3>
        <p className={`mt-0.5 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>Note library</p>
      </div>

      <div className="p-4">{children}</div>
    </aside>
  )
}
