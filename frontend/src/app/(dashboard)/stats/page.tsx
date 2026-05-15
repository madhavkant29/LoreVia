"use client"

import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"

import {
  WorkspaceEmptyState,
  WorkspaceHeader,
  WorkspaceMetric,
  WorkspacePage,
  WorkspacePanel,
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
        <WorkspacePanel tone="strong" className="p-6 sm:p-8">
          <WorkspaceHeader
            eyebrow="Dashboard"
            title="Writing momentum, not just account totals."
            description="This dashboard now tracks live writing output across the windows authors usually care about most: today, this week, longer rolling streaks, and the recent heatmap of saved work."
            meta={
              <div className="app-chip">
                {stats ? `${formatWordCount(stats.writing.today.words)} today` : "Syncing writing stats"}
              </div>
            }
          />
        </WorkspacePanel>

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
            <section className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
              <WorkspacePanel className="overflow-hidden p-0">
                <div className="rounded-[1.9rem] border border-[#3e352d] bg-[#1f1a16] p-5 text-[#f3eadc] shadow-[0_32px_90px_-55px_rgba(0,0,0,0.78)] sm:p-6">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.26em] text-[#b7a995]">Writing dashboard</p>
                      <h2 className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-[#fff6ea] sm:text-[2rem]">
                        See the pace of the work, not only the scale of the library.
                      </h2>
                    </div>
                    <p className="max-w-sm text-sm leading-7 text-[#c8bba9]">
                      Each save now feeds a history view with calendar windows, rolling totals, a contribution heatmap, and today&apos;s chapter-by-chapter gains.
                    </p>
                  </div>

                  <div className="mt-6 grid gap-4 sm:grid-cols-2">
                    {writingCards.map((card) => (
                      <WritingStatCard
                        key={card.key}
                        label={card.label}
                        stat={card.stat}
                        showProgress={card.showProgress}
                      />
                    ))}
                  </div>

                  <div className="mt-6 rounded-[1.55rem] border border-[#3a3129] bg-[#25201b] p-4 sm:p-5">
                    <WritingHeatmapPanel
                      heatmap={heatmap}
                      entriesTodayCount={stats.writing.entries_today.length}
                    />
                  </div>
                </div>
              </WorkspacePanel>

              <div className="space-y-6">
                <WorkspacePanel className="overflow-hidden p-0">
                  <div className="rounded-[1.9rem] border border-[#3e352d] bg-[#1f1a16] p-5 text-[#f3eadc] shadow-[0_32px_90px_-55px_rgba(0,0,0,0.78)] sm:p-6">
                    <EntriesTodayPanel entries={stats.writing.entries_today} />
                  </div>
                </WorkspacePanel>

                <WorkspacePanel className="p-6">
                  <p className="app-eyebrow">Targets</p>
                  <h2 className="mt-3 text-2xl font-semibold text-[rgb(var(--foreground))]">
                    The progress bars stay anchored to your daily goal.
                  </h2>
                  <p className="mt-2 text-sm leading-7 text-[rgb(var(--muted-foreground))]">
                    Today tracks against one daily target. This week tracks against seven daily targets, so the dashboard still reads clearly even when you write in bursts.
                  </p>

                  <div className="mt-5 grid gap-4">
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
                </WorkspacePanel>
              </div>
            </section>

            <WorkspacePanel className="p-6">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className="app-eyebrow">Workspace totals</p>
                  <h2 className="mt-3 text-2xl font-semibold text-[rgb(var(--foreground))]">
                    The broader account picture is still here.
                  </h2>
                </div>
                <p className="max-w-2xl text-sm leading-7 text-[rgb(var(--muted-foreground))]">
                  Writing momentum now leads the page, but public reading milestones and private workspace load remain useful context for everything LoreVia is carrying for you.
                </p>
              </div>

              <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {secondaryStats.map((item) => (
                  <WorkspaceMetric
                    key={item.label}
                    label={item.label}
                    value={item.value}
                    note={item.note}
                    accent={item.label === "Words read" ? "accent" : item.label === "Uploads tracked" ? "success" : "default"}
                  />
                ))}
              </div>
            </WorkspacePanel>
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

  return (
    <article className="rounded-[1.45rem] border border-[#3a3129] bg-[#28221d] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <p className="text-[0.95rem] font-medium text-[#b8ac9a]">{label}</p>
      <p className="mt-2 text-[1.95rem] font-semibold tracking-[-0.04em] text-[#fff6ea]">
        {stat.words.toLocaleString()}
        <span className="ml-2 text-base font-medium text-[#d6c8b7]">words</span>
      </p>

      {showProgress && stat.target_words ? (
        <div className="mt-4">
          <div className="flex items-center justify-between gap-3 text-xs text-[#b6a896]">
            <span>{stat.words.toLocaleString()} / {stat.target_words.toLocaleString()} words</span>
            <span>{progressWidth}%</span>
          </div>
          <div className="mt-2 h-2 rounded-full bg-[#4a4036]">
            <div
              className="h-full rounded-full bg-[#49d75f] shadow-[0_0_12px_rgba(73,215,95,0.45)]"
              style={{ width: `${progressWidth}%` }}
            />
          </div>
        </div>
      ) : (
        <p className="mt-4 text-xs text-[#9d907f]">
          {label.startsWith("Last") ? "Rolling time window" : "Calendar time window"}
        </p>
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
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#b8aa99]">Recent cadence</p>
          <h3 className="mt-2 text-lg font-semibold text-[#fff6ea]">Heatmap of saved writing</h3>
        </div>
        <p className="text-xs text-[#a99c8b]">
          {entriesTodayCount} {entriesTodayCount === 1 ? "entry" : "entries"} logged today
        </p>
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
                className="text-[10px] font-medium text-[#978b7c]"
                style={{ gridColumnStart: month.column + 1 }}
              >
                {month.label}
              </div>
            ))}
          </div>

          <div className="mt-2 flex gap-2">
            <div className="grid gap-1">
              {HEATMAP_WEEKDAY_LABELS.map((label) => (
                <div key={label} className="flex h-[0.9rem] items-center text-[10px] text-[#978b7c]">
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
    </div>
  )
}

function HeatmapCell({ day }: { day: WritingHeatmapCell }) {
  return (
    <div
      className={cn(
        "h-[0.9rem] w-[0.9rem] rounded-full border border-[#3b322a]",
        day.level === 0 && "bg-[#332b24]",
        day.level === 1 && "bg-[#44692f]",
        day.level === 2 && "bg-[#4e9135]",
        day.level === 3 && "bg-[#58c944]",
        day.level === 4 && "bg-[#76f05d]"
      )}
      title={`${day.date}: ${formatWordCount(day.words)}`}
    />
  )
}

function EntriesTodayPanel({ entries }: { entries: WritingEntry[] }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#b8aa99]">Entries today</p>
      <h2 className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-[#fff6ea]">
        The chapters and sections that moved today.
      </h2>
      <p className="mt-2 text-sm leading-7 text-[#c8bba9]">
        Every positive save is grouped here so the dashboard feels like a real daily ledger, not a single number with no story behind it.
      </p>

      <div className="mt-5 space-y-3">
        {entries.length === 0 ? (
          <div className="rounded-[1.35rem] border border-dashed border-[#4a4036] bg-[#28221d] p-4 text-sm text-[#b8ac9a]">
            No entries yet today. The next saved chapter will appear here automatically.
          </div>
        ) : (
          entries.map((entry) => (
            <div
              key={`${entry.book_id ?? "book"}-${entry.chapter_number ?? "chapter"}-${entry.title}`}
              className="flex items-center justify-between gap-4 rounded-[1.35rem] border border-[#3a3129] bg-[#28221d] px-4 py-3"
            >
              <div className="min-w-0">
                <p className="truncate text-lg font-medium text-[#fff6ea]">{entry.title}</p>
                <p className="mt-1 text-xs text-[#9d907f]">
                  {entry.chapter_number ? `Chapter ${entry.chapter_number}` : "Section save"}
                </p>
              </div>
              <p className="shrink-0 text-lg font-semibold text-[#d7c8b8]">+{entry.words.toLocaleString()} words</p>
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
    <div className="rounded-[1.35rem] border border-[rgba(var(--border),0.72)] bg-[rgba(255,255,255,0.44)] p-4 dark:bg-[rgba(255,255,255,0.03)]">
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
