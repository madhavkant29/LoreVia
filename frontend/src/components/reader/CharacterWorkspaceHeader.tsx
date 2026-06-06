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
    <>
      <button
        type="button"
        onClick={onBack}
        className={`inline-flex items-center gap-2 text-sm font-medium transition ${isDark ? "text-slate-300 hover:text-white" : "text-stone-600 hover:text-stone-950"}`}
      >
        <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fillRule="evenodd" d="M11.78 4.22a.75.75 0 0 1 0 1.06L8.06 9h8.19a.75.75 0 0 1 0 1.5H8.06l3.72 3.72a.75.75 0 1 1-1.06 1.06l-5-5a.75.75 0 0 1 0-1.06l5-5a.75.75 0 0 1 1.06 0Z" clipRule="evenodd" />
        </svg>
        Back
      </button>

      <div className="mt-4 flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0 xl:max-w-[32rem]">
          <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-teal-300" : "text-teal-700"}`}>Story Bible</p>
          <h1 className={`mt-2 text-[2.55rem] font-semibold tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>{title}</h1>
          <p className={`mt-1.5 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
            {description}
          </p>
        </div>

        <div className="flex flex-col gap-3 xl:min-w-[820px] xl:max-w-[940px] xl:flex-1">
          {stats}
          {actions}
        </div>
      </div>
    </>
  )
}
