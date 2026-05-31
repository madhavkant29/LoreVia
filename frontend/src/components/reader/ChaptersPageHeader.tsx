"use client"

type ChaptersPageHeaderProps = {
  title: string
  subtitle: string
  processedCount: number | null
  totalCount: number | null
  isDark: boolean
  backLabel: string
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
  primaryActionLabel,
  primaryActionBusyLabel,
  primaryActionBusy,
  primaryActionDisabled = false,
  onBack,
  onPrimaryAction,
}: ChaptersPageHeaderProps) {
  const countReady = typeof processedCount === "number" && typeof totalCount === "number"

  return (
    <section className="relative">
      <button
        type="button"
        onClick={onBack}
        className={`inline-flex items-center gap-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-300/60 ${
          isDark ? "text-slate-400 hover:text-white" : "text-stone-500 hover:text-stone-900"
        }`}
      >
        <span
          aria-hidden="true"
          className={`flex h-7 w-7 items-center justify-center rounded-full border ${
            isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white"
          }`}
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 18l-6-6 6-6" />
          </svg>
        </span>
        <span>{backLabel}</span>
      </button>

      <div className="mt-8 flex flex-col gap-8 xl:flex-row xl:items-start xl:justify-between">
        <div className="max-w-[46rem]">
          <p className={`text-3xs font-semibold uppercase tracking-[0.3em] ${isDark ? "text-teal-300" : "text-teal-700"}`}>Manuscript</p>
          <h1 className={`mt-3 font-serif text-[2.9rem] leading-none tracking-[-0.04em] sm:text-[4.4rem] ${isDark ? "text-white" : "text-stone-950"}`}>{title}</h1>
          <p className={`mt-4 max-w-2xl text-base leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{subtitle}</p>

          <div className="mt-7">
            <button
              type="button"
              onClick={onPrimaryAction}
              disabled={primaryActionBusy || primaryActionDisabled}
              className={`inline-flex items-center justify-center rounded-md border px-5 py-3 text-sm font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-300/60 disabled:cursor-not-allowed disabled:opacity-50 ${
                isDark
                  ? "border-emerald-400/20 bg-emerald-400/14 text-emerald-50 hover:bg-emerald-400/20"
                  : "border-teal-200 bg-teal-600 text-white hover:bg-teal-700"
              }`}
            >
              <span
                aria-hidden="true"
                className={`mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full ${
                  isDark ? "bg-emerald-300/18 text-emerald-100" : "bg-white/20 text-white"
                }`}
              >
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </span>
              {primaryActionBusy ? primaryActionBusyLabel : primaryActionLabel}
            </button>
          </div>
        </div>

        <div className={`min-w-[13rem] self-start rounded-lg border px-5 py-4 ${isDark ? "border-white/10 bg-[#0c1219]/90 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"}`}>
          <div className="flex items-center gap-3">
            <span className={`inline-flex h-8 w-8 items-center justify-center rounded-full border ${isDark ? "border-teal-400/20 bg-teal-400/10 text-teal-200" : "border-teal-200 bg-teal-50 text-teal-700"}`}>
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75l2.25 2.25L15 9.75" />
                <circle cx="12" cy="12" r="9" />
              </svg>
            </span>
            <div className="min-w-0">
              {countReady ? (
                <p className={`text-[1.85rem] font-semibold tracking-[-0.03em] ${isDark ? "text-white" : "text-stone-950"}`}>
                  {processedCount} / {totalCount}
                </p>
              ) : (
                <div className={`h-8 w-24 animate-pulse rounded-full ${isDark ? "bg-white/[0.08]" : "bg-stone-200"}`} />
              )}
              <p className={`mt-0.5 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>processed</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
