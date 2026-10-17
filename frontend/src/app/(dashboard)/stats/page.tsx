"use client"

import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"

import {
  WorkspaceEmptyState,
  WorkspaceHeader,
  WorkspacePage,
  WorkspacePanel,
} from "@/components/ui/Workspace"
import { booksApi } from "@/lib/api/books"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { asQueryKey, booksStatsCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"
import {
  HEATMAP_WEEKDAY_LABELS,
  buildSecondaryStats,
  buildWritingCards,
  buildWritingHeatmap,
  formatWordCount,
  type WritingHeatmapCell,
} from "@/lib/utils/writingStats"
import { cn } from "@/lib/utils/text"
import type { UserStats } from "@/types/book"

export default function StatsPage() {
  const userTier = useAuthStore((state) => state.user?.tier)
  const authHydrated = useAuthStore((state) => state.hydrated)
  const canUseAuthorTools = canUseAuthorFeatures(userTier)
  const { data: stats = null, isLoading: loading } = useQuery<UserStats | null>({
    queryKey: asQueryKey(booksStatsCacheKey()),
    queryFn: () => booksApi.getStats(),
    enabled: authHydrated && canUseAuthorTools,
  })

  const writingCards = useMemo(() => (stats ? buildWritingCards(stats.writing) : []), [stats])
  const heatmap = useMemo(() => (stats ? buildWritingHeatmap(stats.writing.heatmap) : null), [stats])
  const secondaryStats = useMemo(() => (stats ? buildSecondaryStats(stats) : []), [stats])

  if (!authHydrated) {
    return <WorkspacePage className="min-h-0 bg-transparent"><WorkspaceEmptyState title="Loading stats" body="Preparing your writing dashboard." /></WorkspacePage>
  }

  return (
    <WorkspacePage className="min-h-0 bg-transparent">
      <div className="space-y-8 pb-12">
        {!canUseAuthorTools ? (
          <WorkspacePanel tone="strong" className="p-6 sm:p-8">
            <WorkspaceHeader
              eyebrow="Author feature"
              title="Stats require an active trial or paid plan."
              description="Free accounts can read and export owned projects, plus use one Story Advisor turn each week."
            />
          </WorkspacePanel>
        ) : null}

        {canUseAuthorTools ? (
          <>
        <header className="border-b border-[rgba(var(--border),0.8)] pb-6">
          <p className="app-eyebrow">Writing stats</p>
          <h1 className="mt-3 text-4xl font-semibold tracking-[-0.04em] text-stone-950 dark:text-[#f3ede4]">Writing progress</h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-stone-600 dark:text-slate-300">Review your writing rhythm, current targets, and workspace totals without losing the trend in dashboard noise.</p>
        </header>

        {loading ? (
          <WorkspaceEmptyState
            title="Loading dashboard"
            body="LoreVia is gathering your writing momentum and workspace totals."
          />
        ) : !stats || !heatmap ? (
          <WorkspaceEmptyState
            title="Stats unavailable"
            body="We could not load your dashboard metrics right now."
          />
        ) : (
          <>
            <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
              <section className="min-w-0 border border-[rgba(var(--border),0.8)] bg-white p-5 dark:bg-[#10171d] sm:p-6">
                <WritingHeatmapPanel heatmap={heatmap} entriesTodayCount={stats.writing.entries_today.length} />
              </section>
              <section className="border border-[rgba(var(--border),0.8)] bg-white p-5 dark:bg-[#10171d] sm:p-6">
                <h2 className="text-xl font-semibold text-stone-950 dark:text-[#f3ede4]">Progress summary</h2>
                <p className="mt-2 text-sm text-stone-600 dark:text-slate-300">Words saved against your current targets.</p>
                <div className="mt-5 grid gap-5">
                  <ProgressSummary label="Today" current={stats.writing.today.words} target={stats.writing.today.target_words} />
                  <ProgressSummary label="This week" current={stats.writing.this_week.words} target={stats.writing.this_week.target_words} />
                </div>
              </section>
            </section>

            <section className="border-y border-[rgba(var(--border),0.8)] py-5">
              <h2 className="text-xl font-semibold text-stone-950 dark:text-[#f3ede4]">Breakdown</h2>
              <div className="mt-4 grid grid-cols-2 gap-x-5 xl:grid-cols-4">
                {writingCards.map((card) => (
                  <div key={card.key} className="border-t border-[rgba(var(--border),0.7)] py-3">
                    <p className="text-xs text-stone-500 dark:text-slate-400">{card.label}</p>
                    <p className="mt-1 text-lg font-semibold text-stone-950 dark:text-[#f3ede4]">{formatWordCount(card.stat.words)}</p>
                  </div>
                ))}
                {secondaryStats.map((item) => (
                  <div key={item.label} className="border-t border-[rgba(var(--border),0.7)] py-3">
                    <p className="text-xs text-stone-500 dark:text-slate-400">{item.label}</p>
                    <p className="mt-1 text-lg font-semibold text-stone-950 dark:text-[#f3ede4]">{item.value}</p>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
          </>
        ) : null}
      </div>
    </WorkspacePage>
  )
}

function WritingHeatmapPanel({
  heatmap,
  entriesTodayCount,
}: {
  heatmap: ReturnType<typeof buildWritingHeatmap>
  entriesTodayCount: number
}) {
  return (
    <div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-stone-500 dark:text-slate-400">
            <DropletIcon />
            <h3 className="text-[1.9rem] font-semibold tracking-[-0.035em] text-stone-950 dark:text-[#f3ede4]">Heatmap of saved writing</h3>
          </div>
          <p className="mt-2 text-sm leading-7 text-stone-600 dark:text-slate-300">
            Daily writing activity over the past year.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-stone-500 dark:text-slate-400">
          <span>Less</span>
          <div className="flex items-center gap-1">
            {[0, 1, 2, 3, 4, 5].map((index) => (
              <span
                key={index}
                className={cn(
                  "h-3 w-3 rounded-[4px] border border-slate-200 dark:border-slate-700/70",
                  index === 0 && "bg-stone-100 dark:bg-[#232a31]",
                  index === 1 && "bg-emerald-100 dark:bg-[#24483f]",
                  index === 2 && "bg-emerald-200 dark:bg-[#2c6a5a]",
                  index === 3 && "bg-emerald-300 dark:bg-[#3b8e78]",
                  index === 4 && "bg-emerald-400 dark:bg-[#59c3ad]",
                  index === 5 && "bg-emerald-500 dark:bg-[#76d4c0]"
                )}
              />
            ))}
          </div>
          <span>More</span>
        </div>
      </div>

      <div className="mt-4 overflow-x-auto">
        <div className="min-w-max">
          <div
            className="grid gap-1 pl-12"
            style={{ gridTemplateColumns: `repeat(${heatmap.columns.length}, minmax(0, 0.9rem))` }}
          >
            {heatmap.months.map((month) => (
              <div
                key={`${month.label}-${month.column}`}
                className="text-3xs font-medium text-stone-500 dark:text-slate-400"
                style={{ gridColumnStart: month.column + 1 }}
              >
                {month.label}
              </div>
            ))}
          </div>

          <div className="mt-2 flex gap-2">
            <div className="grid gap-1">
              {HEATMAP_WEEKDAY_LABELS.map((label) => (
                <div key={label} className="flex h-[0.9rem] items-center text-3xs text-stone-500 dark:text-slate-400">
                  {label}
                </div>
              ))}
            </div>

            <div
              className="grid gap-1"
              style={{ gridTemplateColumns: `repeat(${heatmap.columns.length}, minmax(0, 0.9rem))` }}
            >
              {heatmap.columns.map((column) => (
                <div key={column.id} className="grid gap-1">
                  {column.days.map((day) => (
                    <HeatmapCell key={day.date} day={day} />
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-5 flex items-center justify-between gap-4 text-sm text-stone-500 dark:text-slate-400">
        <p className="break-words">Each square represents one day. Darker shades indicate more words written.</p>
        <p className="shrink-0 text-[#1f615d] dark:text-[#69c6b1]">
          {entriesTodayCount} {entriesTodayCount === 1 ? "entry today" : "entries today"}
        </p>
      </div>
    </div>
  )
}

function HeatmapCell({ day }: { day: WritingHeatmapCell }) {
  return (
    <div
      className={cn(
        "h-[0.9rem] w-[0.9rem] rounded-[4px] border border-slate-200 dark:border-slate-700/70",
        day.level === 0 && "bg-stone-100 dark:bg-[#232a31]",
        day.level === 1 && "bg-emerald-100 dark:bg-[#24483f]",
        day.level === 2 && "bg-emerald-200 dark:bg-[#2c6a5a]",
        day.level === 3 && "bg-emerald-300 dark:bg-[#3b8e78]",
        day.level === 4 && "bg-emerald-400 dark:bg-[#59c3ad]"
      )}
      title={`${day.date}: ${formatWordCount(day.words)}`}
    />
  )
}

function ProgressSummary({
  label,
  current,
  target,
}: {
  label: string
  current: number
  target: number | null | undefined
}) {
  const progressPct = target && target > 0 ? Math.max(0, Math.min(100, Math.round((current / target) * 100))) : null

  return (
    <div className="min-w-0 overflow-hidden rounded-lg border-2 border-slate-200 bg-[rgba(255,255,255,0.44)] p-4 dark:border-slate-700/70 dark:bg-[rgba(255,255,255,0.03)]">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-[rgb(var(--foreground))]">{label}</p>
        <p className="text-xs text-[rgb(var(--muted-foreground))]">{progressPct === null ? "No target" : `${progressPct}%`}</p>
      </div>
      <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">
        {target == null ? `${current.toLocaleString()} words` : `${current.toLocaleString()} / ${target.toLocaleString()} words`}
      </p>
      {progressPct !== null ? <div className="mt-3 h-2 rounded-full bg-[rgba(var(--foreground),0.08)]">
        <div
          className="h-full rounded-full bg-emerald-500"
          style={{ width: `${progressPct}%` }}
        />
      </div> : null}
    </div>
  )
}

function DropletIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3.5c3 4 5.5 7 5.5 10A5.5 5.5 0 016.5 13.5c0-3 2.5-6 5.5-10z" />
    </svg>
  )
}
