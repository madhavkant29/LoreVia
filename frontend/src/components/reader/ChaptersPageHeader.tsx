"use client"

import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"

type ChaptersPageHeaderProps = {
  title: string
  subtitle: string
  processedCount: number | null
  totalCount: number | null
  isDark: boolean
  backLabel: string
  homeHref?: string
  primaryActionLabel: string
  primaryActionBusyLabel: string
  primaryActionBusy: boolean
  primaryActionDisabled?: boolean
  onBack: () => void
  onPrimaryAction: () => void
}

export function ChaptersPageHeader({
  title,
  subtitle,
  processedCount,
  totalCount,
  isDark,
  backLabel,
  homeHref,
  primaryActionLabel,
  primaryActionBusyLabel,
  primaryActionBusy,
  primaryActionDisabled = false,
  onBack,
  onPrimaryAction,
}: ChaptersPageHeaderProps) {
  const countReady = typeof processedCount === "number" && typeof totalCount === "number"

  return (
    <section className={`flex flex-col gap-4 border-b pb-5 lg:flex-row lg:items-end lg:justify-between ${isDark ? "border-white/[0.08]" : "border-stone-200"}`}>
      <div className="min-w-0 max-w-3xl">
        {!homeHref ? (
          <button type="button" onClick={onBack} className={`mb-3 text-sm font-medium ${isDark ? "text-slate-400 hover:text-white" : "text-stone-500 hover:text-stone-900"}`}>
            ← {backLabel}
          </button>
        ) : null}
        <h1 className={`text-2xl font-semibold tracking-tight sm:text-3xl ${isDark ? "text-white" : "text-stone-950"}`}>{title}</h1>
        <p className={`mt-1 break-words text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{subtitle}</p>
      </div>

      <div className="flex shrink-0 flex-wrap items-center gap-4">
        <div className="text-right">
          {countReady ? (
            <p className={`text-sm font-semibold tabular-nums ${isDark ? "text-white" : "text-stone-950"}`}>{processedCount} / {totalCount}</p>
          ) : (
            <span aria-label="Chapter counts unavailable">—</span>
          )}
          <p className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>processed</p>
        </div>
        <button
          type="button"
          onClick={onPrimaryAction}
          disabled={primaryActionBusy || primaryActionDisabled}
          className={`rounded-sm border px-4 py-2.5 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500/60 disabled:cursor-not-allowed disabled:opacity-50 ${isDark ? "border-white/15 text-slate-200 hover:bg-white/5" : "border-stone-300 text-stone-700 hover:bg-stone-100"}`}
        >
          {primaryActionBusy ? primaryActionBusyLabel : primaryActionLabel}
        </button>
        <button type="button" onClick={() => window.dispatchEvent(new Event(SUPPORT_HELP_EVENT))} className="min-h-11 px-2 text-sm underline underline-offset-4">Help</button>
      </div>
    </section>
  )
}
