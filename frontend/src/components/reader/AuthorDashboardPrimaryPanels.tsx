"use client"

import { useMemo, useState } from "react"
import type { Route } from "next"
import Link from "next/link"

import { Icon } from "@/components/overview/Icon"
import type { IconName } from "@/components/overview/types"
import { clamp, formatNumber, panelClass, severityClass } from "@/components/overview/utils"
import { CoverEditOverlay } from "@/components/ui/CoverEditOverlay"
import { ErrorCard } from "@/components/ui/ErrorCard"
import { SmartBookCover } from "@/components/ui/SmartBookCover"
import { WorkspaceModeSwitcher } from "@/components/reader/WorkspaceModeSwitcher"
import { buildIssueDisplay } from "@/lib/utils/storyFeedback"
import type { Book, PreWritingCheck, StoryHealth } from "@/types/book"
import type { ChapterListResponse } from "@/types/reader"

export function OverviewHeader({
  isDark,
  activeBookMode,
  canUseAuthorMode,
  modeSaving,
  greetingName,
  onModeChange,
  onToggleTheme,
}: {
  isDark: boolean
  activeBookMode: "reader" | "author"
  canUseAuthorMode: boolean
  modeSaving: boolean
  greetingName: string
  onModeChange: (nextMode: "reader" | "author") => void
  onToggleTheme: () => void
}) {
  return (
    <section className={panelClass(isDark, "overflow-hidden p-4 sm:p-5")}>
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="min-w-0">
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-teal-200/80" : "text-teal-800"}`}>Author workspace</p>
          <h1 className={`mt-2 font-serif text-3xl leading-none sm:text-4xl ${isDark ? "text-white" : "text-slate-900"}`}>
            Welcome back, {greetingName}.
          </h1>
          <p className={`mt-3 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
            Drafting, revision pressure, and story memory now live in one calmer workspace.
          </p>
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
            className={`flex h-11 w-11 items-center justify-center rounded-full border transition ${isDark ? "border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/[0.08]" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"}`}
            aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
          >
            <Icon name={isDark ? "sun" : "moon"} />
          </button>
        </div>
      </div>
    </section>
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
  onOpenRelationships,
  onNavigate,
  bookId,
  resolvedCoverUrl,
  onCoverUpdated,
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
  onOpenRelationships: () => void
  onNavigate: (href: string) => void
  bookId: string
  resolvedCoverUrl: string | null | undefined
  onCoverUpdated: (book: Book) => void
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
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Current project</p>
      <div className="mt-4 grid gap-5 md:grid-cols-[9rem_minmax(0,1fr)] xl:grid-cols-[10rem_minmax(0,1fr)]">
        <SmartBookCover
          src={resolvedCoverUrl}
          title={book.title}
          isDark={isDark}
          className="aspect-[0.72] min-h-48 overflow-hidden rounded-lg"
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
          <div className="flex flex-wrap items-center gap-3">
            <h2 className={`break-words text-2xl font-semibold tracking-tight sm:text-3xl ${isDark ? "text-white" : "text-slate-950"}`}>{book.title}</h2>
            <span className={`text-xs font-semibold ${isDark ? "text-teal-300" : "text-teal-700"}`}>{book.work_type === "screenplay" ? "Screenplay" : "Manuscript"}</span>
          </div>
          <p className={`mt-3 max-w-xl break-words text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
            {book.public_description?.trim() || (
              currentWords !== null
                ? `${currentWords.toLocaleString()} manuscript words saved${hasBookTarget ? ` toward a ${targetWords.toLocaleString()}-word target` : ""}.`
                : "No project description has been added."
            )}
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            {canOpenManuscript ? (
              <button
                type="button"
                onClick={onOpenManuscript}
                className={`inline-flex min-h-11 items-center gap-2 rounded-md px-5 py-2.5 text-sm font-semibold transition ${isDark ? "bg-teal-800 text-white hover:bg-teal-700" : "bg-teal-800 text-white hover:bg-teal-700"}`}
              >
                <Icon name="book" />
                Open Manuscript Editor
                <Icon name="chevron" />
              </button>
            ) : null}
            <button type="button" onClick={onOpenRelationships} className={secondaryButtonClass(isDark)}>
              <Icon name="users" />
              Open relationship map
            </button>
            <button type="button" onClick={() => onNavigate(`/${bookId}/summaries`)} className={secondaryButtonClass(isDark)}>
              <Icon name="search" />
              Open summaries
            </button>
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <HeroMetric isDark={isDark} label="Draft progress" value={hasBookTarget ? `${formatNumber(currentWords)} / ${targetWords.toLocaleString()}` : `${formatNumber(currentWords)} words`} note={hasBookTarget ? `${Math.round(manuscriptProgress)}% of target` : "No book target set"} progress={hasBookTarget ? manuscriptProgress : undefined} />
        <HeroMetric isDark={isDark} label="Daily target" value={`${dailyWords.toLocaleString()} / ${dailyTarget.toLocaleString()}`} note="Today's quota" progress={goalProgress} />
        <HeroMetric isDark={isDark} label="Writing rhythm" value={`${loginStreakDays} day${loginStreakDays === 1 ? "" : "s"}`} note="Current streak" />
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
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Latest chapters</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <StatusPill isDark={isDark} label={book.status === "ready" ? "Drafting" : book.status.replace(/_/g, " ")} tone="violet" />
            <StatusPill isDark={isDark} label={`${chapters.length} indexed ${unitTitle.toLowerCase()}${chapters.length === 1 ? "" : "s"}`} tone="slate" />
          </div>
        </div>
        <button type="button" onClick={() => onNavigate(`/${bookId}/manuscript`)} className={`text-xs font-semibold ${isDark ? "text-teal-300" : "text-teal-700"}`}>
          Open draft
        </button>
      </div>
      <div className="mt-5 space-y-3">
        {recentChapters.length > 0 ? recentChapters.map((chapter) => (
          <button
            key={chapter.number}
            type="button"
            onClick={() => onNavigate(`/${bookId}/chapter/${chapter.number}`)}
            className={`flex w-full items-start justify-between gap-3 rounded-md border px-4 py-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-white hover:bg-slate-50"}`}
          >
            <div className="min-w-0">
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>{unitPrefix} {chapter.number}</p>
              <p className={`mt-1 break-words text-sm font-medium leading-6 ${isDark ? "text-slate-100" : "text-slate-800"}`}>{chapter.title || `${unitTitle} ${chapter.number}`}</p>
              <p className={`mt-1 text-xs ${isDark ? "text-slate-300" : "text-slate-600"}`}>{chapter.read ? "Opened" : "Not opened"}</p>
            </div>
            <span className={`text-xs font-semibold ${isDark ? "text-teal-300" : "text-teal-700"}`}>{chapter.read ? "Read" : "Open"}</span>
          </button>
        )) : (
          <p className={`rounded-md border border-dashed px-4 py-6 text-sm ${isDark ? "border-white/[0.08] text-slate-300" : "border-slate-200 text-slate-600"}`}>
            No {unitTitle.toLowerCase()}s are available yet.
          </p>
        )}
      </div>
      <button type="button" onClick={() => onNavigate(`/${bookId}/chapters`)} className={footerLinkClass(isDark)}>
        View all chapters <Icon name="chevron" />
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
        <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Story pulse</p>
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
  const healthColor = score >= 85 ? "#45d483" : score >= 70 ? "#8b5cf6" : score >= 55 ? "#f5bf3d" : "#fb7185"
  const topMetrics = (storyHealth?.metrics ?? []).filter((metric) => metric.available !== false).slice(0, 3)
  const selectedMetric = topMetrics.find((metric) => metric.label === selectedMetricLabel) ?? null

  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Story pulse</p>
          <h2 className={`mt-2 text-lg font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Key metrics only.</h2>
        </div>
        <span className={`rounded-full px-3 py-1 text-3xs font-semibold ${isDark ? "bg-white/[0.05] text-slate-300" : "bg-slate-100 text-slate-600"}`}>{status}</span>
      </div>

      <div className="mt-5 flex items-center gap-4">
        {healthAvailable ? (
          <div
            className="relative flex h-24 w-24 items-center justify-center rounded-full"
            style={{ background: `conic-gradient(${healthColor} 0 ${score}%, ${isDark ? "#1b2430" : "#edf0f5"} ${score}% 100%)` }}
          >
            <div className={`flex h-[4.6rem] w-[4.6rem] flex-col items-center justify-center rounded-full ${isDark ? "bg-[#0d141c]" : "bg-white"}`}>
              <span className={`text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{score}</span>
              <span className={`text-3xs ${isDark ? "text-slate-300" : "text-slate-600"}`}>health</span>
            </div>
          </div>
        ) : null}
        <p className={`min-w-0 break-words text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{summary}</p>
      </div>

      <div className="mt-5 space-y-3">
        {topMetrics.map((metric) => (
          <button
            key={metric.label}
            type="button"
            onClick={() => setSelectedMetricLabel((current) => current === metric.label ? null : metric.label)}
            className={`w-full rounded-md border px-4 py-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-white hover:bg-slate-50"} ${selectedMetricLabel === metric.label ? (isDark ? "ring-1 ring-sky-400/60" : "ring-1 ring-sky-500/50") : ""}`}
          >
            <div className="flex items-center justify-between gap-3">
              <span className={isDark ? "min-w-0 break-words text-sm text-slate-200" : "min-w-0 break-words text-sm text-slate-700"}>{metric.label}</span>
              <span className="text-sm font-semibold text-teal-700">{metric.score}%</span>
            </div>
          </button>
        ))}
      </div>

      {selectedMetric ? (
        <div className={`mt-4 rounded-md border px-4 py-3 ${isDark ? "border-sky-400/30 bg-sky-500/10" : "border-sky-200 bg-sky-50"}`}>
          <p className={`text-sm font-semibold ${isDark ? "text-sky-100" : "text-sky-800"}`}>{selectedMetric.label}: {selectedMetric.score}%</p>
          <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{selectedMetric.detail}</p>
        </div>
      ) : null}

      <Link
        href={`/${bookId}/analysis` as Route}
        className={`mt-5 inline-flex w-full items-center justify-center rounded-md border px-4 py-3 text-sm font-semibold transition ${
          isDark ? "border-white/10 bg-white/[0.04] text-teal-200 hover:bg-white/[0.08]" : "border-slate-200 bg-white text-teal-800 hover:bg-slate-50"
        }`}
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
  continuityIssueCount: number
  worldGapCount: number
  timelineIssueCount: number
  onNavigate: (href: string) => void
  bookId: string
  processingSummary: string | null
}) {
  const issues = [
    { title: "Continuity Flags", rawCount: continuityIssueCount, severity: "High", icon: "users" as IconName, href: `/${bookId}/reports` },
    { title: "World Gaps", rawCount: worldGapCount, severity: "Medium", icon: "gap" as IconName, href: `/${bookId}/world-gap` },
    { title: "Timeline Conflicts", rawCount: timelineIssueCount, severity: "Low", icon: "timeline" as IconName, href: `/${bookId}/timeline` },
  ].map((issue) => ({
    ...issue,
    ...buildIssueDisplay(issue.rawCount),
  }))

  return (
      <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Next actions</p>
            <h2 className={`mt-2 text-xl font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Keep the risky parts visible.</h2>
          </div>
          <Icon name="spark" className="h-5 w-5 text-teal-700" />
        </div>

        <p className={`mt-4 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
          Keep revision fallout visible before it reaches readers.
        </p>

        {processingSummary ? (
          <p className={`mt-4 rounded-md border px-4 py-3 text-sm leading-6 ${isDark ? "border-white/[0.06] bg-white/[0.03] text-slate-300" : "border-slate-200 bg-slate-50 text-slate-600"}`}>
            {processingSummary}
          </p>
        ) : null}

        <button
          type="button"
          onClick={() => onNavigate(`/${bookId}/reports`)}
          className={`mt-4 inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold transition ${isDark ? "bg-teal-800 text-white hover:bg-teal-700" : "bg-teal-800 text-white hover:bg-teal-700"}`}
        >
          Create revision checklist
        </button>

        <div className="mt-4 space-y-3">
        {issues.map((issue) => (
          <button
            key={issue.title}
            type="button"
            onClick={() => onNavigate(issue.href)}
            className={`flex w-full items-center gap-3 rounded-md border px-4 py-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-white hover:bg-slate-50"}`}
          >
            <Icon name={issue.icon} className="h-5 w-5 text-teal-700" />
            <div className="min-w-0 flex-1">
              <p className={`break-words text-sm font-semibold leading-6 ${isDark ? "text-slate-100" : "text-slate-800"}`}>{issue.title}</p>
              <p className={`mt-1 break-words text-xs leading-5 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{issue.label}</p>
            </div>
            <span className={`rounded-full px-2 py-1 text-3xs font-semibold ${severityClass(issue.severity, isDark)}`}>{issue.severity}</span>
          </button>
        ))}
      </div>
    </section>
  )
}

export function CompactQuickLinksCard({
  isDark,
  links,
  onNavigate,
}: {
  isDark: boolean
  links: Array<{ title: string; body: string; href: string; icon: IconName }>
  onNavigate: (href: string) => void
}) {
  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Workspace links</p>
      <div className="mt-4 space-y-3">
        {links.map((link) => (
          <button
            key={link.title}
            type="button"
            onClick={() => onNavigate(link.href)}
            className={`flex w-full items-start gap-3 rounded-md border px-4 py-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-white hover:bg-slate-50"}`}
          >
            <Icon name={link.icon} className="mt-0.5 h-5 w-5 text-teal-700" />
            <div className="min-w-0">
              <p className={`break-words text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-800"}`}>{link.title}</p>
              <p className={`mt-1 break-words text-xs leading-5 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{link.body}</p>
            </div>
          </button>
        ))}
      </div>
    </section>
  )
}

export function RecentSignalsCard({
  isDark,
  unitTitle,
  recentAlerts,
  chapters,
  onNavigate,
  bookId,
  preWritingCheckError,
  onRetryPreWritingCheck,
}: {
  isDark: boolean
  unitTitle: string
  recentAlerts: PreWritingCheck["alerts"]
  chapters: ChapterListResponse["chapters"]
  onNavigate: (href: string) => void
  bookId: string
  preWritingCheckError?: boolean
  onRetryPreWritingCheck?: () => void
}) {
  const recentEntries = useMemo(() => {
    const chapterSignals = chapters.slice(-2).reverse().map((chapter) => ({
      title: `${unitTitle} ${chapter.number}: ${chapter.title || `${unitTitle} ${chapter.number}`}`,
      note: chapter.read ? "Recently opened" : "Ready to review",
      href: `/${bookId}/chapter/${chapter.number}`,
    }))

    return [
      ...recentAlerts.slice(0, 2).map((alert) => ({
        title: alert.title,
        note: alert.chapter_ref ? `Chapter ${alert.chapter_ref}` : "Author alert",
        href: `/${bookId}/analysis`,
      })),
      ...chapterSignals,
    ].slice(0, 4)
  }, [bookId, chapters, recentAlerts, unitTitle])

  if (preWritingCheckError && recentAlerts.length === 0 && chapters.length === 0 && onRetryPreWritingCheck) {
    return (
      <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
        <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Recent signals</p>
        <div className="mt-4">
          <ErrorCard
            message="Failed to load recent signals"
            onRetry={onRetryPreWritingCheck}
            variant="compact"
            isDark={isDark}
          />
        </div>
      </section>
    )
  }

  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Recent signals</p>
      <div className="mt-4 space-y-3">
        {recentEntries.length > 0 ? recentEntries.map((entry) => (
          <button
            key={`${entry.title}-${entry.note}`}
            type="button"
            onClick={() => onNavigate(entry.href)}
            className={`w-full rounded-md border px-4 py-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-white hover:bg-slate-50"}`}
          >
              <p className={`break-words text-sm font-medium leading-6 ${isDark ? "text-slate-100" : "text-slate-800"}`}>{entry.title}</p>
              <p className={`mt-1 break-words text-xs leading-5 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{entry.note}</p>
            </button>
        )) : (
          <p className={isDark ? "text-sm text-slate-300" : "text-sm text-slate-600"}>Signals will appear here as the workspace syncs.</p>
        )}
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
    <div className={`rounded-md border p-3 ${isDark ? "border-white/[0.06] bg-white/[0.025]" : "border-slate-200 bg-slate-50"}`}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>{label}</p>
      <p className={`mt-2 break-words text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-800"}`}>{value}</p>
      {typeof progress === "number" ? (
        <div className={`mt-3 h-1.5 overflow-hidden rounded-full ${isDark ? "bg-white/[0.08]" : "bg-slate-200"}`}>
          <div className="h-full rounded-full bg-teal-700" style={{ width: `${clamp(progress, 0, 100)}%` }} />
        </div>
      ) : null}
      <p className={`mt-2 text-3xs ${isDark ? "text-slate-300" : "text-slate-600"}`}>{note}</p>
    </div>
  )
}

function StatusPill({
  isDark,
  label,
  tone,
}: {
  isDark: boolean
  label: string
  tone: "violet" | "slate"
}) {
  const toneClass = tone === "violet"
    ? isDark ? "bg-violet-500/10 text-violet-200" : "bg-violet-50 text-violet-700"
    : isDark ? "bg-white/[0.06] text-slate-300" : "bg-slate-100 text-slate-600"
  return <span className={`rounded-full px-2.5 py-1 text-3xs font-semibold capitalize ${toneClass}`}>{label}</span>
}

export function RevisionPreviewPlaceholder({ isDark }: { isDark: boolean }) {
  return (
    <section className={panelClass(isDark, "flex min-h-64 items-center justify-center p-5")}>
      <p className={`text-sm ${isDark ? "text-slate-300" : "text-slate-600"}`}>Revision intelligence is still syncing.</p>
    </section>
  )
}

function secondaryButtonClass(isDark: boolean) {
  return `inline-flex min-h-11 items-center gap-2 rounded-md border px-4 py-2.5 text-sm font-semibold transition ${
    isDark ? "border-white/10 bg-white/[0.04] text-slate-100 hover:bg-white/[0.08]" : "border-slate-200 bg-white text-slate-800 hover:bg-slate-50"
  }`
}

function footerLinkClass(isDark: boolean) {
  return `mt-5 inline-flex items-center gap-2 text-xs font-semibold ${isDark ? "text-teal-200" : "text-teal-800"}`
}
