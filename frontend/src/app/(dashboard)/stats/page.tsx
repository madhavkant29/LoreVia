"use client"

import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"

import {
  WorkspaceEmptyState,
  WorkspacePage,
} from "@/components/ui/Workspace"
import { booksApi } from "@/lib/api/books"
import { asQueryKey, booksStatsCacheKey } from "@/lib/query/cacheKeys"
import {
  HEATMAP_WEEKDAY_LABELS,
  buildSecondaryStats,
  buildWritingCards,
  buildWritingHeatmap,
  formatWordCount,
  type WritingHeatmapCell,
} from "@/lib/utils/writingStats"
import { cn } from "@/lib/utils/text"
import type { UserStats, WritingEntry, WritingPeriodStat } from "@/types/book"

export default function StatsPage() {
  const { data: stats = null, isLoading: loading } = useQuery<UserStats | null>({
    queryKey: asQueryKey(booksStatsCacheKey()),
    queryFn: () => booksApi.getStats(),
  })

  const writingCards = useMemo(() => (stats ? buildWritingCards(stats.writing) : []), [stats])
  const heatmap = useMemo(() => (stats ? buildWritingHeatmap(stats.writing.heatmap) : null), [stats])
  const secondaryStats = useMemo(() => (stats ? buildSecondaryStats(stats) : []), [stats])

  return (
    <WorkspacePage className="min-h-0 bg-transparent">
      <div className="space-y-8 pb-12">
        <section className="overflow-hidden rounded-lg border-2 border-slate-200 bg-white p-6 dark:border-slate-700/70 dark:bg-[#10171d] sm:p-8 lg:p-10">
          <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_240px] lg:items-center">
            <div className="min-w-0">
              <p className="text-3xs font-semibold uppercase tracking-[0.28em] text-[#1f615d] dark:text-[#69c6b1]">Stats dashboard</p>
              <h1 className="mt-4 max-w-[700px] font-display text-[3rem] leading-[0.94] tracking-[-0.06em] text-stone-950 dark:text-[#f3ede4] sm:text-[4rem]">
                Writing momentum,
                <br className="hidden sm:block" />
                not just account totals.
              </h1>
              <p className="mt-5 max-w-[620px] text-[1.02rem] leading-8 text-stone-600 dark:text-slate-300">
                Track your writing output across time, see how your habits compound, and stay aligned with your goals.
              </p>
            </div>

            <div className="flex justify-start lg:justify-end">
              <div className="min-w-0 rounded-lg border-2 border-slate-200 bg-[#fcfcfb] px-5 py-5 dark:border-slate-700/70 dark:bg-[#131c23]">
                <div className="flex items-center gap-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border-2 border-slate-200 bg-emerald-50 text-[#1f615d] dark:border-slate-700/70 dark:bg-[#18242a] dark:text-[#69c6b1]">
                    <LeafIcon />
                  </div>
                  <div className="min-w-0">
                    <p className="text-[2.2rem] font-semibold tracking-[-0.05em] text-[#1f615d] dark:text-[#f3ede4]">
                      {stats ? stats.writing.today.words.toLocaleString() : "0"}
                    </p>
                    <p className="text-base text-stone-600 dark:text-slate-300">words today</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

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
            <section className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.55fr)_320px]">
              <div className="min-w-0 space-y-6">
                <section className="overflow-hidden rounded-lg border-2 border-slate-200 bg-white p-5 dark:border-slate-700/70 dark:bg-[#10171d] sm:p-6">
                  <div className="flex items-start gap-3">
                    <span className="mt-1 text-stone-500 dark:text-slate-400">
                      <TrendIcon />
                    </span>
                    <div className="min-w-0">
                      <h2 className="text-[1.9rem] font-semibold tracking-[-0.035em] text-stone-950 dark:text-[#f3ede4]">Writing momentum overview</h2>
                      <p className="mt-2 text-sm leading-7 text-stone-600 dark:text-slate-300">
                        Your writing output across key time windows.
                      </p>
                    </div>
                  </div>

                  <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    {writingCards.map((card) => (
                      <WritingStatCard
                        key={card.key}
                        label={card.label}
                        stat={card.stat}
                        showProgress={card.showProgress}
                      />
                    ))}
                  </div>
                </section>

                <section className="overflow-hidden rounded-lg border-2 border-slate-200 bg-white p-5 dark:border-slate-700/70 dark:bg-[#10171d] sm:p-6">
                  <WritingHeatmapPanel
                    heatmap={heatmap}
                    entriesTodayCount={stats.writing.entries_today.length}
                  />
                </section>
              </div>

              <div className="min-w-0 space-y-6">
                <section className="overflow-hidden rounded-lg border-2 border-slate-200 bg-white p-5 dark:border-slate-700/70 dark:bg-[#10171d] sm:p-6">
                  <EntriesTodayPanel entries={stats.writing.entries_today} />
                </section>

                <section className="overflow-hidden rounded-lg border-2 border-slate-200 bg-white p-5 dark:border-slate-700/70 dark:bg-[#10171d] sm:p-6">
                  <div className="flex items-start gap-3">
                    <span className="mt-1 text-stone-500 dark:text-slate-400">
                      <TargetIcon />
                    </span>
                    <div className="min-w-0">
                      <h2 className="text-[1.9rem] font-semibold tracking-[-0.035em] text-stone-950 dark:text-[#f3ede4]">Targets</h2>
                      <p className="mt-2 text-sm leading-7 text-stone-600 dark:text-slate-300">
                        Stay on track with your daily goal.
                      </p>
                    </div>
                  </div>

                  <div className="mt-5 min-w-0 overflow-hidden rounded-lg border-2 border-slate-200 bg-[#fcfcfb] p-4 dark:border-slate-700/70 dark:bg-[#121920]">
                    <div className="grid gap-4">
                      <ProgressSummary
                        label="Today"
                        current={stats.writing.today.words}
                        target={stats.writing.today.target_words ?? 0}
                      />
                      <ProgressSummary
                        label="This Week"
                        current={stats.writing.this_week.words}
                        target={stats.writing.this_week.target_words ?? 0}
                      />
                    </div>
                  </div>
                </section>
              </div>
            </section>

            <section className="overflow-hidden rounded-lg border-2 border-slate-200 bg-white p-5 dark:border-slate-700/70 dark:bg-[#10171d] sm:p-6">
              <div className="flex items-start gap-3">
                <span className="mt-1 text-stone-500 dark:text-slate-400">
                  <StackIcon />
                </span>
                <div className="min-w-0">
                  <h2 className="text-[1.9rem] font-semibold tracking-[-0.035em] text-stone-950 dark:text-[#f3ede4]">Workspace totals</h2>
                  <p className="mt-2 break-words text-sm leading-7 text-stone-600 dark:text-slate-300">
                    Key totals and usage across your LoreVia workspace.
                  </p>
                </div>
              </div>

              <div className="mt-6 grid grid-cols-[repeat(auto-fit,minmax(min(100%,220px),1fr))] gap-4">
                {secondaryStats.map((item) => (
                  <WorkspaceTotalsCard
                    key={item.label}
                    label={item.label}
                    value={item.value}
                    note={item.note}
                  />
                ))}
              </div>
            </section>
          </>
        )}
      </div>
    </WorkspacePage>
  )
}

function WritingStatCard({
  label,
  stat,
  showProgress,
}: {
  label: string
  stat: WritingPeriodStat
  showProgress: boolean
}) {
  const progressWidth = Math.max(0, Math.min(100, stat.progress_pct ?? 0))
  const description = showProgress
    ? `${stat.words.toLocaleString()} / ${stat.target_words?.toLocaleString() ?? "0"} words`
    : label.startsWith("Last")
      ? "Rolling window"
      : "Calendar window"

  return (
    <article className="min-w-0 overflow-hidden rounded-lg border-2 border-slate-200 bg-[#fcfcfb] p-4 dark:border-slate-700/70 dark:bg-[#121920]">
      <div className="flex items-center gap-2 text-stone-600 dark:text-slate-400">
        <CalendarIcon />
        <p className="text-[0.95rem] font-medium">{label}</p>
      </div>
      <p className="mt-3 break-words text-[1.95rem] font-semibold tracking-[-0.04em] text-stone-950 dark:text-[#fff6ea]">
        {stat.words.toLocaleString()}{" "}
        <span className="text-base font-medium text-stone-500 dark:text-slate-400">words</span>
      </p>

      {showProgress && stat.target_words ? (
        <div className="mt-4">
          <div className="flex items-center justify-between gap-3 text-xs text-stone-500 dark:text-slate-400">
            <span>{description}</span>
            <span>{progressWidth}%</span>
          </div>
          <div className="mt-3 h-2 rounded-full bg-stone-200 dark:bg-[#2a343d]">
            <div
              className="h-full rounded-full bg-emerald-500"
              style={{ width: `${progressWidth}%` }}
            />
          </div>
        </div>
      ) : (
        <div className="mt-5">
          <p className="text-xs text-stone-500 dark:text-slate-400">{description}</p>
          <div className="mt-3 h-2 rounded-full bg-stone-200 dark:bg-[#2a343d]" />
        </div>
      )}
    </article>
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
          {entriesTodayCount} {entriesTodayCount === 1 ? "active day" : "active days"}
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

function EntriesTodayPanel({ entries }: { entries: WritingEntry[] }) {
  return (
    <div>
      <div className="flex items-start gap-3">
        <span className="mt-1 text-stone-500 dark:text-slate-400">
          <DocumentIcon />
        </span>
        <div className="min-w-0">
          <h2 className="text-[1.9rem] font-semibold tracking-[-0.035em] text-stone-950 dark:text-[#f3ede4]">Entries today</h2>
          <p className="mt-2 break-words text-sm leading-7 text-stone-600 dark:text-slate-300">
            The chapters and sections that moved today.
          </p>
        </div>
      </div>

      <div className="mt-5 space-y-3">
        {entries.length === 0 ? (
          <div className="flex min-h-[320px] flex-col items-center justify-center rounded-lg border-2 border-slate-200 bg-[#fcfcfb] px-6 py-8 text-center dark:border-slate-700/70 dark:bg-[#121920]">
            <div className="flex h-24 w-24 items-center justify-center rounded-full border-2 border-slate-200 bg-[#f4f7f6] text-stone-700 dark:border-slate-700/70 dark:bg-[#182028] dark:text-slate-300">
              <DocumentIcon large />
            </div>
            <p className="mt-6 text-[1.9rem] font-semibold tracking-[-0.035em] text-stone-950 dark:text-[#f3ede4]">No entries saved today</p>
            <p className="mt-3 max-w-[280px] text-sm leading-7 text-stone-600 dark:text-slate-300">
              Your saved chapters and sections will appear here.
            </p>
          </div>
        ) : (
          entries.map((entry) => (
            <div
              key={`${entry.book_id ?? "book"}-${entry.chapter_number ?? "chapter"}-${entry.title}`}
              className="flex min-w-0 items-center justify-between gap-4 overflow-hidden rounded-lg border-2 border-slate-200 bg-[#fcfcfb] px-4 py-3 dark:border-slate-700/70 dark:bg-[#121920]"
            >
              <div className="min-w-0">
                <p className="truncate text-lg font-medium text-stone-950 dark:text-[#fff6ea]">{entry.title}</p>
                <p className="mt-1 text-xs text-stone-500 dark:text-[#9d907f]">
                  {entry.chapter_number ? `Chapter ${entry.chapter_number}` : "Section save"}
                </p>
              </div>
              <p className="shrink-0 text-lg font-semibold text-stone-700 dark:text-[#d7c8b8]">+{entry.words.toLocaleString()} words</p>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function ProgressSummary({
  label,
  current,
  target,
}: {
  label: string
  current: number
  target: number
}) {
  const progressPct = target > 0 ? Math.max(0, Math.min(100, Math.round((current / target) * 100))) : 0

  return (
    <div className="min-w-0 overflow-hidden rounded-lg border-2 border-slate-200 bg-[rgba(255,255,255,0.44)] p-4 dark:border-slate-700/70 dark:bg-[rgba(255,255,255,0.03)]">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-[rgb(var(--foreground))]">{label}</p>
        <p className="text-xs text-[rgb(var(--muted-foreground))]">{progressPct}%</p>
      </div>
      <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">
        {current.toLocaleString()} / {target.toLocaleString()} words
      </p>
      <div className="mt-3 h-2 rounded-full bg-[rgba(var(--foreground),0.08)]">
        <div
          className="h-full rounded-full bg-emerald-500"
          style={{ width: `${progressPct}%` }}
        />
      </div>
    </div>
  )
}

function WorkspaceTotalsCard({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <article className="min-w-0 rounded-md border-2 border-slate-200 bg-[#fcfcfb] p-5 dark:border-slate-700/70 dark:bg-[#121920]">
      <div className="flex flex-col gap-4">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border-2 border-slate-200 bg-[#f4f7f6] text-[#1f615d] dark:border-slate-700/70 dark:bg-[#182028] dark:text-[#69c6b1]">
          <TotalsIcon />
        </div>
        <div className="min-w-0 space-y-2">
          <p className="break-words text-[clamp(1.8rem,4vw,2.4rem)] font-semibold leading-none tracking-[-0.05em] text-stone-950 dark:text-[#f3ede4]">
            {value}
          </p>
          <p className="text-sm font-semibold text-stone-950 dark:text-[#f3ede4]">{label}</p>
          <p className="mt-2 break-words text-sm leading-6 text-stone-600 dark:text-slate-300">{note}</p>
        </div>
      </div>
    </article>
  )
}

function LeafIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18c5-1 9-5 10-10-4 1-8 5-10 10z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 16c2-4 5-7 9-9" />
    </svg>
  )
}

function TrendIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l5-5 4 4 7-8" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M14 7h6v6" />
    </svg>
  )
}

function CalendarIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <rect x="4.5" y="6" width="15" height="13.5" rx="2.2" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 4.5v3M16 4.5v3M4.5 10h15" />
    </svg>
  )
}

function DropletIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3.5c3 4 5.5 7 5.5 10A5.5 5.5 0 016.5 13.5c0-3 2.5-6 5.5-10z" />
    </svg>
  )
}

function TargetIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <circle cx="12" cy="12" r="7.5" />
      <circle cx="12" cy="12" r="3" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 12l6-6" />
    </svg>
  )
}

function StackIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4l8 4-8 4-8-4 8-4zM4 12l8 4 8-4M4 16l8 4 8-4" />
    </svg>
  )
}

function DocumentIcon({ large = false }: { large?: boolean }) {
  return (
    <svg className={large ? "h-10 w-10" : "h-5 w-5"} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 3.5h7l5 5V19a1.5 1.5 0 01-1.5 1.5h-10A1.5 1.5 0 016 19V5A1.5 1.5 0 017.5 3.5z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M14 3.5V9h5M9 13h6M9 17h6" />
    </svg>
  )
}

function TotalsIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 18V10M12 18V6M19 18v-8" />
    </svg>
  )
}
