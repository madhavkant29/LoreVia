import type { ReactNode } from "react"

export function CharacterWorkspaceHeader({
  title,
  description,
  stats,
  actions,
  onBack,
  isDark,
}: {
  title: string
  description: string
  stats: ReactNode
  actions: ReactNode
  onBack: () => void
  isDark: boolean
}) {
  return (
    <header className={`rounded-md border ${isDark ? "border-[#202a38] bg-[#080d13]" : "border-stone-200 bg-white"}`}>
      <div className={`flex flex-col gap-3 border-b px-4 py-3 lg:flex-row lg:items-center lg:justify-between ${isDark ? "border-[#17202c]" : "border-stone-200"}`}>
        <div className="flex min-w-0 items-center gap-4">
          <img src="/logoandtextlight.png" alt="LoreVia" className="h-10 w-auto shrink-0 object-contain dark:hidden" />
          <img src="/logoandtext.png" alt="LoreVia" className="hidden h-10 w-auto shrink-0 object-contain dark:block" />
          <button
            type="button"
            onClick={onBack}
            className={`inline-flex items-center gap-1 text-sm font-medium transition ${isDark ? "text-slate-300 hover:text-white" : "text-stone-500 hover:text-stone-950"}`}
          >
            Projects
            <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path fillRule="evenodd" d="M7.22 4.22a.75.75 0 0 1 1.06 0l5 5a.75.75 0 0 1 0 1.06l-5 5a.75.75 0 1 1-1.06-1.06L11.69 10 7.22 5.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
            </svg>
          </button>
          <div className="min-w-0">
            <h1 className={`truncate text-sm font-semibold ${isDark ? "text-slate-100" : "text-stone-800"}`}>{title}</h1>
            <p className={`truncate text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{description}</p>
          </div>
        </div>

        <div className="flex flex-1 flex-col gap-3 lg:flex-row lg:items-center lg:justify-end">
          <label className={`flex h-10 w-full min-w-[220px] items-center gap-2 rounded-md border px-3 lg:w-[280px] xl:w-[320px] ${isDark ? "border-[#202a38] bg-[#0d121a]" : "border-stone-200 bg-stone-50"}`}>
            <svg className={`h-4 w-4 ${isDark ? "text-slate-500" : "text-stone-400"}`} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path fillRule="evenodd" d="M8.5 3a5.5 5.5 0 1 0 3.473 9.765l3.63 3.631a.75.75 0 1 0 1.06-1.06l-3.63-3.63A5.5 5.5 0 0 0 8.5 3ZM4.5 8.5a4 4 0 1 1 8 0 4 4 0 0 1-8 0Z" clipRule="evenodd" />
            </svg>
            <span className={`min-w-0 flex-1 text-sm ${isDark ? "text-slate-500" : "text-stone-400"}`}>Search (Ctrl K)</span>
          </label>
          {actions}
        </div>
      </div>

      <div className="px-4 py-3">
        {stats}
      </div>
    </header>
  )
}
