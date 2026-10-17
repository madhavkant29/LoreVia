import type { ReactNode } from "react"

export function CharacterWorkspaceHeader({
  title,
  description,
  stats,
  actions,
  isDark,
}: {
  title: string
  description: string
  stats: ReactNode
  actions: ReactNode
  isDark: boolean
}) {
  return (
    <header className={`border-b pb-5 ${isDark ? "border-[#202a38]" : "border-stone-200"}`}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <h1 className={`text-2xl font-semibold tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>{title}</h1>
          <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-600"}`}>{description}</p>
        </div>
        {actions}
      </div>
      <div className="mt-4">
        {stats}
      </div>
    </header>
  )
}
