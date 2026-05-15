import type { UserStats, WritingDashboardStats, WritingHeatmapDay, WritingPeriodStat } from "@/types/book"

export const HEATMAP_WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const

export type WritingCardKey =
  | "today"
  | "this_week"
  | "this_month"
  | "this_year"
  | "last_24_hours"
  | "last_7_days"
  | "last_30_days"
  | "last_year"

export type WritingCard = {
  key: WritingCardKey
  label: string
  stat: WritingPeriodStat
  showProgress: boolean
}

export type WritingHeatmapCell = WritingHeatmapDay & {
  level: 0 | 1 | 2 | 3 | 4
}

export type WritingHeatmapColumn = {
  id: string
  days: WritingHeatmapCell[]
}

export type WritingHeatmapMonth = {
  label: string
  column: number
}

const MONTH_FORMATTER = new Intl.DateTimeFormat("en-US", {
  month: "short",
  timeZone: "UTC",
})

export function buildWritingCards(writing: WritingDashboardStats): WritingCard[] {
  return [
    { key: "today", label: "Today", stat: writing.today, showProgress: true },
    { key: "this_week", label: "This Week", stat: writing.this_week, showProgress: true },
    { key: "this_month", label: "This Month", stat: writing.this_month, showProgress: false },
    { key: "this_year", label: "This Year", stat: writing.this_year, showProgress: false },
    { key: "last_24_hours", label: "Last 24 Hours", stat: writing.last_24_hours, showProgress: false },
    { key: "last_7_days", label: "Last 7 Days", stat: writing.last_7_days, showProgress: false },
    { key: "last_30_days", label: "Last 30 Days", stat: writing.last_30_days, showProgress: false },
    { key: "last_year", label: "Last Year", stat: writing.last_year, showProgress: false },
  ]
}

export function buildWritingHeatmap(heatmapDays: WritingHeatmapDay[]) {
  const sortedDays = [...heatmapDays].sort((left, right) => left.date.localeCompare(right.date))
  const maxWords = sortedDays.reduce((currentMax, day) => Math.max(currentMax, day.words), 0)
  const columns: WritingHeatmapColumn[] = []

  for (let index = 0; index < sortedDays.length; index += 7) {
    const slice = sortedDays.slice(index, index + 7)
    if (slice.length === 0) continue
    columns.push({
      id: slice[0].date,
      days: slice.map((day) => ({
        ...day,
        level: getHeatmapLevel(day.words, maxWords),
      })),
    })
  }

  const months: WritingHeatmapMonth[] = []
  let previousMonthLabel = ""
  columns.forEach((column, index) => {
    const monthLabel = MONTH_FORMATTER.format(new Date(`${column.days[0].date}T00:00:00Z`))
    if (monthLabel !== previousMonthLabel) {
      months.push({ label: monthLabel, column: index })
      previousMonthLabel = monthLabel
    }
  })

  return {
    columns,
    months,
    maxWords,
  }
}

export function getHeatmapLevel(words: number, maxWords: number): 0 | 1 | 2 | 3 | 4 {
  if (words <= 0 || maxWords <= 0) return 0

  const ratio = words / maxWords
  if (ratio < 0.25) return 1
  if (ratio < 0.5) return 2
  if (ratio < 0.75) return 3
  return 4
}

export function formatWordCount(words: number) {
  return `${words.toLocaleString()} words`
}

export function buildSecondaryStats(stats: UserStats) {
  return [
    {
      label: "Books finished",
      value: stats.public.total_books_read.toLocaleString(),
      note: "Completed or fully consumed titles",
    },
    {
      label: "Words read",
      value: stats.public.total_words_read.toLocaleString(),
      note: "Finished plus in-progress reading",
    },
    {
      label: "Upload units used",
      value: stats.private.total_uploads.toLocaleString(),
      note: "Books plus active worldbuilding corpus",
    },
    {
      label: "LLM requests",
      value: (stats.private.llm_request_count ?? 0).toLocaleString(),
      note: "Tracked AI calls tied to your account",
    },
    {
      label: "LLM tokens",
      value: (stats.private.llm_total_tokens ?? 0).toLocaleString(),
      note: "Prompt plus completion tokens recorded so far",
    },
    {
      label: "Saved quotes",
      value: stats.private.saved_quotes.toLocaleString(),
      note: "Private evidence and notes",
    },
  ]
}
