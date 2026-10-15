"use client"

import { useState } from "react"
import type { Route } from "next"
import Link from "next/link"

import { Icon } from "@/components/overview/Icon"
import type { IconName } from "@/components/overview/types"
import { clamp, formatNumber, panelClass } from "@/components/overview/utils"
import { CoverEditOverlay } from "@/components/ui/CoverEditOverlay"
import { ErrorCard } from "@/components/ui/ErrorCard"
import { SmartBookCover } from "@/components/ui/SmartBookCover"
import { WorkspaceModeSwitcher } from "@/components/reader/WorkspaceModeSwitcher"
import type { Book, StoryHealth } from "@/types/book"
import type { ChapterListResponse } from "@/types/reader"

export function OverviewHeader({
  isDark,
  activeBookMode,
  canUseAuthorMode,
  modeSaving,
  onModeChange,
  onToggleTheme,
}: {
  isDark: boolean
  activeBookMode: "reader" | "author"
  canUseAuthorMode: boolean
  modeSaving: boolean
  onModeChange: (nextMode: "reader" | "author") => void
  onToggleTheme: () => void
}) {
  return (
    <header className={`flex flex-col gap-4 border-b pb-4 sm:flex-row sm:items-end sm:justify-between ${isDark ? "border-white/[0.08]" : "border-stone-200"}`}>
        <div className="min-w-0">
          <h1 className={`text-2xl font-semibold tracking-tight sm:text-3xl ${isDark ? "text-white" : "text-stone-950"}`}>Book overview</h1>
          <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-600"}`}>Draft progress, recent chapters, and the issues that need attention.</p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <WorkspaceModeSwitcher
            isDark={isDark}
            activeMode={activeBookMode}
            modeSaving={modeSaving}
            writingAvailable={canUseAuthorMode}
            onModeChange={onModeChange}
          />

          <button
            type="button"
            onClick={onToggleTheme}
            className={`flex h-10 w-10 items-center justify-center rounded-sm border transition-colors ${isDark ? "border-white/10 text-slate-300 hover:bg-white/[0.06]" : "border-stone-200 text-stone-600 hover:bg-stone-50"}`}
            aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
          >
            <Icon name={isDark ? "sun" : "moon"} />
          </button>
        </div>
    </header>
  )
}

export function CurrentProjectCard({
  book,
  isDark,
  canOpenManuscript,
  currentWords,
  targetWords,
  percentComplete,
  dailyWords,
  dailyTarget,
  loginStreakDays,
  onOpenManuscript,
  bookId,
  resolvedCoverUrl,
  onCoverUpdated,
  manuscriptRecap = null,
  recapChapterCount = 0,
}: {
  book: Book
  isDark: boolean
  canOpenManuscript: boolean
  currentWords: number | null
  targetWords: number | null
  percentComplete: number
  dailyWords: number
  dailyTarget: number
  loginStreakDays: number
  onOpenManuscript: () => void
  bookId: string
  resolvedCoverUrl: string | null | undefined
  onCoverUpdated: (book: Book) => void
  manuscriptRecap?: string | null
  recapChapterCount?: number
}) {
  const goalProgress = clamp((dailyWords / Math.max(1, dailyTarget)) * 100, 0, 100)
  const hasBookTarget = typeof targetWords === "number" && targetWords > 0
  const manuscriptProgress = clamp(
    hasBookTarget && currentWords !== null ? (currentWords / targetWords) * 100 : percentComplete,
    0,
    100,
  )
  const etaDays = hasBookTarget && currentWords !== null && dailyTarget > 0
    ? Math.max(0, Math.ceil(Math.max(0, targetWords - currentWords) / dailyTarget))
    : null
  const etaDate = etaDays !== null
    ? new Date(Date.now() + etaDays * 24 * 60 * 60 * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
    : "No target set"

  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <p className={`text-xs font-medium ${isDark ? "text-slate-400" : "text-stone-500"}`}>Current project</p>
      <div className="mt-3 grid grid-cols-[4rem_minmax(0,1fr)] items-start gap-4 sm:grid-cols-[7rem_minmax(0,1fr)] sm:gap-5">
        <SmartBookCover
          src={resolvedCoverUrl}
          title={book.title}
          isDark={isDark}
          className="aspect-[0.72] w-full overflow-hidden rounded-sm"
          overlay={
            <CoverEditOverlay
              bookId={bookId}
              isDark={isDark}
              hasCover={Boolean(resolvedCoverUrl)}
              onCoverUpdated={onCoverUpdated}
            />
          }
        />
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h2 className={`break-words text-2xl font-semibold tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>{book.title}</h2>
            <span className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{book.work_type === "screenplay" ? "Screenplay" : "Manuscript"}</span>
          </div>
          <p className={`mt-3 max-w-xl break-words text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
            {book.public_description?.trim() || (
              currentWords !== null
                ? `${currentWords.toLocaleString()} manuscript words saved${hasBookTarget ? ` toward a ${targetWords.toLocaleString()}-word target` : ""}.`
                : "No project description has been added."
            )}
          </p>
          {manuscriptRecap ? (
            <details className={`mt-4 border-t pt-4 ${isDark ? "border-white/[0.08]" : "border-stone-200"}`}>
              <summary className={`cursor-pointer text-sm font-semibold ${isDark ? "text-slate-200" : "text-stone-800"}`}>Manuscript recap</summary>
              <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{manuscriptRecap}</p>
              <p className={`mt-2 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>Compiled from {recapChapterCount} available chapter recap{recapChapterCount === 1 ? "" : "s"}.</p>
            </details>
          ) : null}
          <div className="mt-5 flex flex-wrap gap-2">
            {canOpenManuscript ? (
              <button
                type="button"
                onClick={onOpenManuscript}
                className="inline-flex min-h-10 items-center gap-2 rounded-sm bg-teal-800 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-teal-700"
              >
                <Icon name="book" />
                Open Manuscript Editor
                <Icon name="chevron" />
              </button>
            ) : null}
            <Link
              href={`/${bookId}/author-loop` as Route}
              className={`inline-flex min-h-10 items-center rounded-sm border px-4 py-2 text-sm font-semibold transition-colors ${isDark ? "border-white/10 text-slate-200 hover:bg-white/[0.06]" : "border-stone-300 text-stone-700 hover:bg-stone-50"}`}
            >
              Resume revision workflow
            </Link>
          </div>
        </div>
      </div>

      <div className={`mt-5 grid grid-cols-2 gap-y-4 border-t pt-4 xl:grid-cols-4 ${isDark ? "border-white/[0.08]" : "border-stone-200"}`}>
        <HeroMetric isDark={isDark} label="Draft progress" value={hasBookTarget ? `${formatNumber(currentWords)} / ${targetWords.toLocaleString()}` : `${formatNumber(currentWords)} words`} note={hasBookTarget ? `${Math.round(manuscriptProgress)}% of target` : "No book target set"} progress={hasBookTarget ? manuscriptProgress : undefined} />
        <HeroMetric isDark={isDark} label="Daily target" value={`${dailyWords.toLocaleString()} / ${dailyTarget.toLocaleString()}`} note="Today's quota" progress={goalProgress} />
        <HeroMetric isDark={isDark} label="Sign-in streak" value={`${loginStreakDays} day${loginStreakDays === 1 ? "" : "s"}`} note="Consecutive login days" />
        <HeroMetric isDark={isDark} label="Est. completion" value={etaDate} note={etaDays !== null ? (etaDays === 0 ? "Target reached" : `In ${etaDays} day${etaDays === 1 ? "" : "s"}`) : "Set a book target to calculate"} />
      </div>
    </section>
  )
}

export function RecentChaptersCard({
  book,
  isDark,
  chapters,
  unitTitle,
  unitPrefix,
  onNavigate,
  bookId,
}: {
  book: Book
  isDark: boolean
  chapters: ChapterListResponse["chapters"]
  unitTitle: string
  unitPrefix: string
  onNavigate: (href: string) => void
  bookId: string
}) {
  const recentChapters = chapters.slice(-3).reverse()

  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Latest {unitTitle.toLowerCase()}s</h2>
          <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{chapters.length} indexed · {book.status === "ready" ? "Draft ready" : book.status.replace(/_/g, " ")}</p>
        </div>
        <button type="button" onClick={() => onNavigate(`/${bookId}/manuscript`)} className={`text-xs font-semibold ${isDark ? "text-teal-300" : "text-teal-700"}`}>
          Open draft
        </button>
      </div>
      <div className={`mt-4 divide-y border-y ${isDark ? "divide-white/[0.07] border-white/[0.07]" : "divide-stone-200 border-stone-200"}`}>
        {recentChapters.length > 0 ? recentChapters.map((chapter) => (
          <button
            key={chapter.number}
            type="button"
            onClick={() => onNavigate(`/${bookId}/chapter/${chapter.number}`)}
            className={`flex w-full items-start justify-between gap-3 px-1 py-3 text-left transition-colors ${isDark ? "hover:bg-white/[0.03]" : "hover:bg-stone-50"}`}
          >
            <div className="min-w-0">
              <p className={`text-xs font-medium ${isDark ? "text-slate-400" : "text-stone-500"}`}>{unitPrefix} {chapter.number}</p>
              <p className={`mt-1 break-words text-sm font-medium leading-6 ${isDark ? "text-slate-100" : "text-slate-800"}`}>{chapter.title || `${unitTitle} ${chapter.number}`}</p>
              <p className={`mt-1 text-xs ${isDark ? "text-slate-300" : "text-slate-600"}`}>{chapter.read ? "Opened" : "Not opened"}</p>
            </div>
            <span className={`text-xs font-semibold ${isDark ? "text-teal-300" : "text-teal-700"}`}>{chapter.read ? "Read" : "Open"}</span>
          </button>
        )) : (
          <p className={`px-1 py-5 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
            No {unitTitle.toLowerCase()}s are available yet.
          </p>
        )}
      </div>
      <button type="button" onClick={() => onNavigate(`/${bookId}/chapters`)} className={footerLinkClass(isDark)}>
        View all {unitTitle.toLowerCase()}s <Icon name="chevron" />
      </button>
    </section>
  )
}

export function StoryPulseCard({
  bookId,
  isDark,
  storyHealth,
  storyHealthError,
  onRetryStoryHealth,
}: {
  bookId: string
  isDark: boolean
  storyHealth: StoryHealth | null
  storyHealthError?: boolean
  onRetryStoryHealth?: () => void
}) {
  const [selectedMetricLabel, setSelectedMetricLabel] = useState<string | null>(null)
  if (storyHealthError && !storyHealth && onRetryStoryHealth) {
    return (
      <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
        <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Story health</p>
        <div className="mt-4">
          <ErrorCard
            message="Failed to load story health"
            onRetry={onRetryStoryHealth}
            variant="compact"
            isDark={isDark}
          />
        </div>
      </section>
    )
  }

  const healthAvailable = Boolean(storyHealth && storyHealth.available !== false)
  const score = healthAvailable ? storyHealth!.score : 0
  const status = storyHealth?.status ?? "Not available"
  const summary = storyHealth?.summary ?? "Story health needs analyzed manuscript evidence before a score can be calculated."
  const topMetrics = (storyHealth?.metrics ?? []).filter((metric) => metric.available !== false).slice(0, 3)
  const selectedMetric = topMetrics.find((metric) => metric.label === selectedMetricLabel) ?? null

  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Story health</p>
          <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{status}</p>
        </div>
        {healthAvailable ? <span className={`text-3xl font-semibold tabular-nums ${isDark ? "text-white" : "text-stone-950"}`}>{score}<span className={`ml-1 text-sm font-normal ${isDark ? "text-slate-400" : "text-stone-600"}`}>/100</span></span> : null}
      </div>

      <p className={`mt-4 min-w-0 break-words text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{summary}</p>

      <div className={`mt-4 divide-y border-y ${isDark ? "divide-white/[0.07] border-white/[0.07]" : "divide-stone-200 border-stone-200"}`}>
        {topMetrics.map((metric) => (
          <button
            key={metric.label}
            type="button"
            aria-label={`${metric.label}: ${metric.score}%`}
            aria-expanded={selectedMetricLabel === metric.label}
            onClick={() => setSelectedMetricLabel((current) => current === metric.label ? null : metric.label)}
            className={`w-full px-1 py-3 text-left transition-colors ${isDark ? "hover:bg-white/[0.03]" : "hover:bg-stone-50"}`}
          >
            <div className="flex items-center justify-between gap-3">
              <span className={isDark ? "min-w-0 break-words text-sm text-slate-200" : "min-w-0 break-words text-sm text-slate-700"}>{metric.label}</span>
              <span className="text-sm font-semibold text-teal-700 dark:text-teal-300">{metric.score}%</span>
            </div>
          </button>
        ))}
      </div>

      {selectedMetric ? (
        <div className={`mt-4 border-l-2 pl-3 ${isDark ? "border-teal-400" : "border-teal-700"}`}>
          <p className={`text-sm font-semibold ${isDark ? "text-sky-100" : "text-sky-800"}`}>{selectedMetric.label}: {selectedMetric.score}%</p>
          <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{selectedMetric.detail}</p>
        </div>
      ) : null}

      <Link
        href={`/${bookId}/analysis` as Route}
        className={`mt-4 inline-flex text-sm font-semibold ${isDark ? "text-teal-300 hover:text-teal-200" : "text-teal-800 hover:text-teal-700"}`}
      >
        View full report
      </Link>
    </section>
  )
}

export function ActiveIssuesCard({
  isDark,
  continuityIssueCount,
  worldGapCount,
  timelineIssueCount,
  onNavigate,
  bookId,
  processingSummary,
}: {
  isDark: boolean
  continuityIssueCount: number | null
  worldGapCount: number | null
  timelineIssueCount: number | null
  onNavigate: (href: string) => void
  bookId: string
  processingSummary: string | null
}) {
  const issues = [
    { title: "Continuity Flags", rawCount: continuityIssueCount, icon: "users" as IconName, href: `/${bookId}/reports` },
    { title: "World Gaps", rawCount: worldGapCount, icon: "gap" as IconName, href: `/${bookId}/world-gap` },
    { title: "Timeline Conflicts", rawCount: timelineIssueCount, icon: "timeline" as IconName, href: `/${bookId}/timeline` },
  ].map((issue) => ({
    ...issue,
    label: issue.rawCount === null ? "Open to check findings" : issue.rawCount === 0 ? "No findings reported" : `${issue.rawCount} issue${issue.rawCount === 1 ? "" : "s"} detected`,
  }))

  return (
      <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Revision priorities</h2>
            <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>Open findings by category</p>
          </div>
        </div>

        {processingSummary ? (
          <p className={`mt-4 border-l-2 pl-3 text-xs leading-5 ${isDark ? "border-slate-600 text-slate-400" : "border-stone-300 text-stone-500"}`}>
            {processingSummary}
          </p>
        ) : null}

        <button
          type="button"
          onClick={() => onNavigate(`/${bookId}/reports`)}
          className={`mt-4 text-sm font-semibold ${isDark ? "text-teal-300 hover:text-teal-200" : "text-teal-800 hover:text-teal-700"}`}
        >
          Review all findings
        </button>

        <div className={`mt-4 divide-y border-y ${isDark ? "divide-white/[0.07] border-white/[0.07]" : "divide-stone-200 border-stone-200"}`}>
        {issues.map((issue) => (
          <button
            key={issue.title}
            type="button"
            onClick={() => onNavigate(issue.href)}
            className={`flex w-full items-center gap-3 px-1 py-3 text-left transition-colors ${isDark ? "hover:bg-white/[0.03]" : "hover:bg-stone-50"}`}
          >
            <Icon name={issue.icon} className="h-5 w-5 text-teal-700" />
            <div className="min-w-0 flex-1">
              <p className={`break-words text-sm font-semibold leading-6 ${isDark ? "text-slate-100" : "text-slate-800"}`}>{issue.title}</p>
              <p className={`mt-1 break-words text-xs leading-5 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{issue.label}</p>
            </div>
          </button>
        ))}
      </div>
    </section>
  )
}

function HeroMetric({
  isDark,
  label,
  value,
  note,
  progress,
}: {
  isDark: boolean
  label: string
  value: string
  note: string
  progress?: number
}) {
  return (
    <div className={`px-1 sm:border-l sm:px-4 first:sm:border-l-0 first:sm:pl-0 ${isDark ? "border-white/[0.08]" : "border-stone-200"}`}>
      <p className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{label}</p>
      <p className={`mt-2 break-words text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-800"}`}>{value}</p>
      {typeof progress === "number" ? (
        <div className={`mt-3 h-1 overflow-hidden ${isDark ? "bg-white/[0.08]" : "bg-stone-200"}`}>
          <div className="h-full bg-teal-700" style={{ width: `${clamp(progress, 0, 100)}%` }} />
        </div>
      ) : null}
      <p className={`mt-2 text-xs ${isDark ? "text-slate-300" : "text-slate-600"}`}>{note}</p>
    </div>
  )
}

export function RevisionPreviewPlaceholder({ isDark }: { isDark: boolean }) {
  return (
    <section className={panelClass(isDark, "flex min-h-64 items-center justify-center p-5")}>
      <p className={`text-sm ${isDark ? "text-slate-300" : "text-slate-600"}`}>Revision intelligence is still syncing.</p>
    </section>
  )
}

function footerLinkClass(isDark: boolean) {
  return `mt-5 inline-flex items-center gap-2 text-xs font-semibold ${isDark ? "text-teal-200" : "text-teal-800"}`
}
