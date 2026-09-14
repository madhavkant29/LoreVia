"use client"

import { useEffect, useMemo, useState } from "react"
import type { Route } from "next"
import Link from "next/link"

import { DailyGoalCard } from "@/components/overview/DailyGoalCard"
import { GoalCalendarCard } from "@/components/overview/GoalCalendarCard"
import { Icon } from "@/components/overview/Icon"
import { ProjectOverviewCard } from "@/components/overview/ProjectOverviewCard"
import type { IconName, WorkspaceSaveState } from "@/components/overview/types"
import { formatPlannerDate } from "@/components/overview/utils"
import { WritingStreakCard } from "@/components/overview/WritingStreakCard"
import { RevisionIntelligencePanel } from "@/components/revision/RevisionIntelligencePanel"
import { ErrorCard } from "@/components/ui/ErrorCard"
import type {
  GoalCalendarItem,
  PreWritingCheck,
  RevisionActionItem,
  RevisionIntelligence,
  StoryHealth,
  UserStats,
  WriterWorkspace,
} from "@/types/book"
import type { ChapterListResponse } from "@/types/reader"

type RevisionInsightSelection = { key: string; title: string; subtitle: string; items: RevisionActionItem[] }
type RevisionSeverityFilter = "all" | "high" | "medium" | "low"

export function AuthorOverviewTab({
  isDark,
  currentWords,
  targetWords,
  chapterCount,
  characterCount,
  worldArticleCount,
  percentComplete,
  dailyWords,
  dailyTarget,
  loginStreakDays,
  weeklyLoginActivity,
  totalRevisionItems,
  highSeverityItems,
  chapters,
  unitTitle,
  onNavigate,
  onOpenManuscript,
  bookId,
}: {
  isDark: boolean
  currentWords: number | null
  targetWords: number | null
  chapterCount: number | null
  characterCount: number
  worldArticleCount: number
  percentComplete: number
  dailyWords: number
  dailyTarget: number
  loginStreakDays: number
  weeklyLoginActivity: boolean[]
  totalRevisionItems: number
  highSeverityItems: number
  chapters: ChapterListResponse["chapters"]
  unitTitle: string
  onNavigate: (href: string) => void
  onOpenManuscript: () => void
  bookId: string
}) {
  const manuscriptProgress = clamp(
    targetWords && currentWords !== null ? (currentWords / targetWords) * 100 : percentComplete,
    0,
    100,
  )
  const latestChapter = chapters[chapters.length - 1]

  return (
    <div className="grid gap-5 xl:auto-rows-fr xl:grid-cols-[minmax(0,0.86fr)_minmax(0,0.92fr)_minmax(0,1fr)]">
      <ProjectOverviewCard
        isDark={isDark}
        currentWords={currentWords}
        chapterCount={chapterCount}
        characterCount={characterCount}
        worldArticleCount={worldArticleCount}
      />
      <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
        <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>At a glance</p>
        <div className="mt-5 space-y-3">
          <CompactProgressRow isDark={isDark} label="Draft progress" value={`${Math.round(manuscriptProgress)}%`} percent={manuscriptProgress} />
          <CompactProgressRow isDark={isDark} label="Daily quota" value={`${dailyWords.toLocaleString()} / ${dailyTarget.toLocaleString()}`} percent={(dailyWords / dailyTarget) * 100} />
          <InfoLine isDark={isDark} label="Active revision items" value={String(totalRevisionItems)} />
          <InfoLine isDark={isDark} label="Last written" value={latestChapter ? `${unitTitle} ${latestChapter.number}` : "No chapter activity"} />
          <button type="button" onClick={() => onNavigate(`/${bookId}/reports`)} className={footerLinkClass(isDark)}>
            View workspace stats <Icon name="chevron" />
          </button>
        </div>
      </section>
      <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
        <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Up next</p>
        <div className="mt-5 space-y-3">
          <ActionRow isDark={isDark} icon="pen" title="Continue writing" body={latestChapter ? `${unitTitle} ${latestChapter.number}` : "Open manuscript"} onClick={onOpenManuscript} />
          <ActionRow isDark={isDark} icon="timeline" title="Review high severity risks" body={`${highSeverityItems} item${highSeverityItems === 1 ? "" : "s"} need attention`} onClick={() => onNavigate(`/${bookId}/analysis`)} tone="amber" />
          <ActionRow isDark={isDark} icon="analysis" title="Run story health scan" body="Open the current report" onClick={() => onNavigate(`/${bookId}/analysis`)} tone="teal" />
          <div className="pt-2">
            <WritingStreakCard isDark={isDark} streakDays={loginStreakDays} weekActivity={weeklyLoginActivity} compact />
          </div>
        </div>
      </section>
    </div>
  )
}

export function RevisionHubTab({
  bookId,
  isDark,
  revisionIntelligence,
  writerWorkspace,
  chapters,
  storyHealth,
  onRevisionChange,
  onWriterWorkspaceChange,
  revisionIntelligenceError,
  onRetryRevisionIntelligence,
  writerWorkspaceError,
  onRetryWriterWorkspace,
  storyHealthError,
  onRetryStoryHealth,
}: {
  bookId: string
  isDark: boolean
  revisionIntelligence: RevisionIntelligence | null
  writerWorkspace: WriterWorkspace | null
  chapters: ChapterListResponse["chapters"]
  storyHealth: StoryHealth | null
  onRevisionChange: (revision: RevisionIntelligence) => void
  onWriterWorkspaceChange: (workspace: WriterWorkspace) => void
  revisionIntelligenceError?: boolean
  onRetryRevisionIntelligence?: () => void
  writerWorkspaceError?: boolean
  onRetryWriterWorkspace?: () => void
  storyHealthError?: boolean
  onRetryStoryHealth?: () => void
}) {
  const [selectedInsight, setSelectedInsight] = useState<RevisionInsightSelection | null>(null)
  const [chapterSeverityFilter, setChapterSeverityFilter] = useState<RevisionSeverityFilter>("all")
  const [selectedChapterKey, setSelectedChapterKey] = useState<string | null>(null)
  const [selectedRevisionItemId, setSelectedRevisionItemId] = useState<string | null>(null)
  const [chapterFindingsHighlighted, setChapterFindingsHighlighted] = useState(false)

  // Compute derived data before early returns to ensure hooks can be used consistently
  const allItems = useMemo(() => (
    revisionIntelligence
      ? [
          ...revisionIntelligence.change_impacts,
          ...revisionIntelligence.scene_advice,
          ...revisionIntelligence.confusion_map,
          ...revisionIntelligence.voice_alerts,
        ]
      : []
  ), [revisionIntelligence])

  const timelineItems = useMemo(() => allItems.filter((item) =>
    [item.title, item.description, item.recommendation, item.source_label]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .match(/\btimeline\b|\border\b|\bsequence\b|\btransition\b|\bearlier\b|\blater\b|\bbefore\b|\bafter\b/)
  ), [allItems])

  const focusCards = useMemo<RevisionInsightSelection[]>(() => (
    revisionIntelligence
      ? [
          {
            key: "continuity",
            title: "Continuity & logic",
            subtitle: "Downstream logic, contradictions, and dependency breaks LoreVia surfaced.",
            items: revisionIntelligence.change_impacts,
          },
          {
            key: "character",
            title: "Character consistency",
            subtitle: "Voice, behavior, and point-of-view consistency checks LoreVia flagged.",
            items: revisionIntelligence.voice_alerts,
          },
          {
            key: "world",
            title: "Worldbuilding gaps",
            subtitle: "Lore and anchoring issues that may leave the reader under-oriented.",
            items: revisionIntelligence.confusion_map,
          },
          {
            key: "timeline",
            title: "Timeline / order",
            subtitle: "Ordering, transition, and chronology issues surfaced across the current revision set.",
            items: timelineItems,
          },
        ]
      : []
  ), [revisionIntelligence, timelineItems])

  const filteredChapterItems = allItems.filter((item) =>
    chapterSeverityFilter === "all" ? true : item.severity === chapterSeverityFilter
  )

  const chaptersByNumber = new Map(chapters.map((chapter) => [chapter.number, chapter]))
  const visibleChapterNumbers = chapters.slice(-5).map((chapter) => chapter.number)
  const referencedChapterNumbers = filteredChapterItems
    .map((item) => item.chapter_ref)
    .filter((chapterNumber): chapterNumber is number => typeof chapterNumber === "number")
  const chapterNumbers = [...new Set([...visibleChapterNumbers, ...referencedChapterNumbers])].sort((left, right) => right - left)
  const chapterFindings: Array<{
    key: string
    chapterNumber: number | null
    title: string
    subtitle: string
    items: RevisionActionItem[]
  }> = chapterNumbers.map((chapterNumber) => {
    const chapter = chaptersByNumber.get(chapterNumber)
    return {
      key: `chapter-${chapterNumber}`,
      chapterNumber,
      title: `Chapter ${chapterNumber}`,
      subtitle: chapter?.title || "Referenced by revision intelligence",
      items: filteredChapterItems.filter((item) => item.chapter_ref === chapterNumber),
    }
  })

  const unassignedChapterItems = filteredChapterItems.filter((item) => typeof item.chapter_ref !== "number")
  if (unassignedChapterItems.length > 0) {
    chapterFindings.push({
      key: "book-wide",
      chapterNumber: null,
      title: "Book-wide findings",
      subtitle: "Not tied to a specific chapter yet",
      items: unassignedChapterItems,
    })
  }

  const selectedChapterFinding = chapterFindings.find((row) => row.key === selectedChapterKey) ?? null

  // All hooks must be called before any conditional returns
  useEffect(() => {
    if (!selectedInsight || !revisionIntelligence) return
    const nextSelection = [...focusCards].find((card) => card.key === selectedInsight.key) ?? null
    setSelectedInsight((current) => current === nextSelection ? current : nextSelection)
  }, [focusCards, revisionIntelligence, selectedInsight])

  useEffect(() => {
    if (selectedChapterKey === null || !revisionIntelligence) return
    const hasSelectedChapter = chapterFindings.some(({ key, items }) => key === selectedChapterKey && items.length > 0)
    if (!hasSelectedChapter) {
      setSelectedChapterKey(null)
    }
  }, [chapterFindings, selectedChapterKey, chapterSeverityFilter, revisionIntelligence])

  useEffect(() => {
    if (selectedRevisionItemId === null || !revisionIntelligence) return
    const hasSelectedItem = allItems.some((item) => item.id === selectedRevisionItemId)
    if (!hasSelectedItem) {
      setSelectedRevisionItemId(null)
    }
  }, [allItems, selectedRevisionItemId, revisionIntelligence])

  useEffect(() => {
    if (!chapterFindingsHighlighted) return
    const timeoutId = window.setTimeout(() => setChapterFindingsHighlighted(false), 1800)
    return () => window.clearTimeout(timeoutId)
  }, [chapterFindingsHighlighted])

  if (revisionIntelligenceError && !revisionIntelligence && onRetryRevisionIntelligence) {
    return (
      <ErrorCard
        message="Failed to load revision intelligence"
        onRetry={onRetryRevisionIntelligence}
        variant="compact"
        isDark={isDark}
      />
    )
  }

  if (!revisionIntelligence) {
    return (
      <EmptyTabState
        isDark={isDark}
        title="Revision intelligence is still syncing."
        body="LoreVia will populate the full revision hub here once the latest manuscript intelligence finishes processing."
      />
    )
  }

  const highCount = allItems.filter((item) => item.severity === "high").length || revisionIntelligence.summary.high_severity_count
  const mediumCount = allItems.filter((item) => item.severity === "medium").length
  const lowCount = allItems.filter((item) => item.severity === "low").length
  const readyScore = storyHealth && storyHealth.available !== false ? storyHealth.score : null

  const selectReadinessSeverity = (severity: RevisionSeverityFilter) => {
    setChapterSeverityFilter(severity)
    setSelectedChapterKey(null)
    setSelectedRevisionItemId(null)
    setChapterFindingsHighlighted(true)
  }

  const renderClickableFinding = (item: RevisionActionItem) => {
    const isActive = selectedRevisionItemId === item.id
    return (
      <button
        type="button"
        key={item.id}
        onClick={() => setSelectedRevisionItemId((current) => current === item.id ? null : item.id)}
        className={`w-full rounded-md border px-3 py-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-white hover:bg-slate-50"} ${isActive ? (isDark ? "ring-1 ring-sky-400/60" : "ring-1 ring-sky-500/50") : ""}`}
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full px-2 py-1 text-3xs font-semibold uppercase tracking-[0.18em] ${severityClass(item.severity, isDark)}`}>{item.severity}</span>
          {item.chapter_ref ? <span className={isDark ? "text-xs text-slate-300" : "text-xs text-slate-600"}>{`Chapter ${item.chapter_ref}`}</span> : null}
          <span className={isDark ? "text-xs text-slate-300" : "text-xs text-slate-600"}>{item.source_label || "Revision intelligence"}</span>
        </div>
        <p className={`mt-2 text-sm font-semibold leading-6 ${isDark ? "text-slate-100" : "text-slate-800"}`}>{item.title}</p>
        <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{item.recommendation || item.description}</p>
        {isActive ? (
          <div className={`mt-3 rounded-md border px-3 py-3 ${isDark ? "border-sky-400/25 bg-sky-500/10" : "border-sky-200 bg-sky-50"}`}>
            <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-sky-200" : "text-sky-800"}`}>What LoreVia found</p>
            <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-200" : "text-slate-700"}`}>{item.description}</p>
            {item.recommendation ? (
              <>
                <p className={`mt-3 text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-sky-200" : "text-sky-800"}`}>Suggested next step</p>
                <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-200" : "text-slate-700"}`}>{item.recommendation}</p>
              </>
            ) : null}
            <div className={`mt-3 flex flex-wrap gap-2 text-3xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>
              <span>Status: {item.status.replace("_", " ")}</span>
              <span>Category: {item.category}</span>
            </div>
          </div>
        ) : null}
      </button>
    )
  }

  return (
    <div className="space-y-5">
      {writerWorkspaceError && !writerWorkspace && onRetryWriterWorkspace ? (
        <ErrorCard
          message="Failed to load writing goals and workspace settings"
          onRetry={onRetryWriterWorkspace}
          variant="compact"
          isDark={isDark}
        />
      ) : null}
      {storyHealthError && !storyHealth && onRetryStoryHealth ? (
        <ErrorCard
          message="Failed to load the story health score"
          onRetry={onRetryStoryHealth}
          variant="compact"
          isDark={isDark}
        />
      ) : null}
      <div className="grid gap-5 xl:auto-rows-fr xl:grid-cols-[minmax(13rem,0.75fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(13rem,0.7fr)]">
        <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Revision focus</p>
          <div className="mt-4 space-y-3">
            {focusCards.map((card, index) => {
              const severity = index === 0 ? "high" : index < 3 ? "medium" : "low"
              const isActive = selectedInsight?.key === card.key
              const count = card.items.length
              return (
              <button
                type="button"
                key={card.key}
                onClick={() => setSelectedInsight(isActive ? null : card)}
                className={`w-full rounded-md border px-3 py-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-white hover:bg-slate-50"} ${isActive ? (isDark ? "ring-1 ring-sky-400/60" : "ring-1 ring-sky-500/50") : ""}`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className={`text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-800"}`}>{card.title}</span>
                  <span className={`rounded-full px-2 py-1 text-3xs font-semibold ${severityClass(String(severity)[0].toUpperCase() + String(severity).slice(1), isDark)}`}>{count}</span>
                </div>
              </button>
            )})}
          </div>
        </section>
        <section className={`${panelClass(isDark, "h-full p-4 sm:p-5 transition-shadow duration-300")} ${chapterFindingsHighlighted ? (isDark ? "shadow-[0_0_0_2px_rgba(56,189,248,0.5),0_0_30px_rgba(20,184,166,0.22)]" : "shadow-[0_0_0_2px_rgba(14,116,144,0.3),0_0_26px_rgba(14,165,233,0.2)]") : ""}`}>
          <div className="flex items-center justify-between gap-3">
            <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Chapter-specific findings</p>
            <div className="flex gap-1">
              {(["all", "high", "medium", "low"] as const).map((label) => {
                const isActive = chapterSeverityFilter === label
                return (
                  <button
                    type="button"
                    key={label}
                    onClick={() => {
                      setChapterSeverityFilter(label)
                      setSelectedChapterKey(null)
                    }}
                    className={`rounded-full px-2 py-1 text-3xs font-semibold transition ${isActive ? (isDark ? "bg-sky-500/15 text-sky-200" : "bg-sky-50 text-sky-700") : (isDark ? "bg-white/[0.05] text-slate-300 hover:bg-white/[0.08]" : "bg-slate-100 text-slate-600 hover:bg-slate-200")}`}
                  >
                    {label[0].toUpperCase() + label.slice(1)}
                  </button>
                )
              })}
            </div>
          </div>
          <div className="mt-4 space-y-2">
            {chapterFindings.map(({ key, title, subtitle, items }) => {
              const isActive = selectedChapterKey === key
              return (
                <button
                  type="button"
                  key={key}
                  onClick={() => {
                    setSelectedChapterKey(isActive ? null : key)
                    setSelectedRevisionItemId(null)
                  }}
                  className={`flex w-full items-center justify-between gap-3 rounded-md border px-3 py-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-white hover:bg-slate-50"} ${isActive ? (isDark ? "ring-1 ring-sky-400/60" : "ring-1 ring-sky-500/50") : ""}`}
                >
                  <div className="min-w-0">
                    <p className={`text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-800"}`}>{title}</p>
                    <p className={`mt-1 break-words text-xs leading-5 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{subtitle}</p>
                  </div>
                  <span className={`text-sm font-semibold ${isDark ? "text-teal-300" : "text-teal-700"}`}>{items.length} issue{items.length === 1 ? "" : "s"}</span>
                </button>
            )})}
          </div>
        </section>
        <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Recommended fixes</p>
          <div className="mt-4 space-y-3">
            {allItems.slice(0, 3).map((item) => (
              <div key={item.id} className={`rounded-md border px-3 py-3 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white"}`}>
                <p className={`break-words text-sm font-semibold leading-6 ${isDark ? "text-slate-100" : "text-slate-800"}`}>{item.title}</p>
                <p className={`mt-1 break-words text-xs leading-5 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{item.recommendation || item.description}</p>
              </div>
            ))}
            {allItems.length === 0 ? <p className={isDark ? "text-sm text-slate-300" : "text-sm text-slate-600"}>No high-impact fixes are currently surfaced.</p> : null}
          </div>
        </section>
        <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Readiness summary</p>
          <div className="mt-5 flex justify-center">
            {readyScore !== null ? (
              <ScoreRing isDark={isDark} score={readyScore} label="ready" />
            ) : (
              <p className={isDark ? "text-sm text-slate-300" : "text-sm text-slate-600"}>Story-health analysis is not available yet.</p>
            )}
          </div>
          <div className="mt-4 space-y-2">
            <InfoLine
              isDark={isDark}
              label="High severity"
              value={String(highCount)}
              active={chapterSeverityFilter === "high"}
              onClick={() => selectReadinessSeverity("high")}
            />
            <InfoLine
              isDark={isDark}
              label="Medium severity"
              value={String(mediumCount)}
              active={chapterSeverityFilter === "medium"}
              onClick={() => selectReadinessSeverity("medium")}
            />
            <InfoLine
              isDark={isDark}
              label="Low severity"
              value={String(lowCount)}
              active={chapterSeverityFilter === "low"}
              onClick={() => selectReadinessSeverity("low")}
            />
          </div>
          <Link href={`/${bookId}/analysis` as Route} className={footerLinkClass(isDark)}>View readiness report <Icon name="chevron" /></Link>
        </section>
      </div>
      {selectedInsight ? (
        <section className={panelClass(isDark, "p-4 sm:p-5")}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Selected findings</p>
              <h3 className={`mt-2 text-lg font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{selectedInsight.title}</h3>
              <p className={`mt-1 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{selectedInsight.subtitle}</p>
            </div>
            <button
              type="button"
              onClick={() => setSelectedInsight(null)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${isDark ? "bg-white/10 text-slate-200 hover:bg-white/15" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}
            >
              Clear
            </button>
          </div>
          <div className="mt-4 space-y-3">
            {selectedInsight.items.length > 0 ? selectedInsight.items.map((item) => renderClickableFinding(item)) : (
              <p className={isDark ? "text-sm text-slate-300" : "text-sm text-slate-600"}>No findings are currently surfaced for this bucket.</p>
            )}
          </div>
        </section>
      ) : null}
      {selectedChapterFinding ? (
        <section className={panelClass(isDark, "p-4 sm:p-5")}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Chapter findings</p>
              <h3 className={`mt-2 text-lg font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{selectedChapterFinding.title}</h3>
              <p className={`mt-1 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                {chapterSeverityFilter === "all"
                  ? "All surfaced revision findings for this row."
                  : `${chapterSeverityFilter[0].toUpperCase() + chapterSeverityFilter.slice(1)} severity findings for this row.`}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setSelectedChapterKey(null)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${isDark ? "bg-white/10 text-slate-200 hover:bg-white/15" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}
            >
              Clear
            </button>
          </div>
          <div className="mt-4 space-y-3">
            {selectedChapterFinding.items.length > 0 ? selectedChapterFinding.items.map((item) => renderClickableFinding(item)) : (
              <p className={isDark ? "text-sm text-slate-300" : "text-sm text-slate-600"}>No findings are currently surfaced for this chapter.</p>
            )}
          </div>
        </section>
      ) : null}
      <RevisionIntelligencePanel
        bookId={bookId}
        revision={revisionIntelligence}
        writerWorkspace={writerWorkspace}
        isDark={isDark}
        onRevisionChange={onRevisionChange}
        onWriterWorkspaceChange={onWriterWorkspaceChange}
      />
    </div>
  )
}

export function PlanningTab({
  isDark,
  writerWorkspace,
  currentWords,
  targetWords,
  chapterCount,
  dailyWords,
  dailyTarget,
  loginStreakDays,
  saveState,
  saveMessage,
  onSaveGoalCalendar,
  onOpenManuscript,
  writerWorkspaceError,
  onRetryWriterWorkspace,
}: {
  isDark: boolean
  writerWorkspace: WriterWorkspace | null
  currentWords: number | null
  targetWords: number | null
  chapterCount: number | null
  dailyWords: number
  dailyTarget: number
  loginStreakDays: number
  saveState: WorkspaceSaveState
  saveMessage: string | null
  onSaveGoalCalendar: (goalCalendar: GoalCalendarItem[]) => Promise<boolean>
  onOpenManuscript: () => void
  writerWorkspaceError?: boolean
  onRetryWriterWorkspace?: () => void
}) {
  if (writerWorkspaceError && !writerWorkspace && onRetryWriterWorkspace) {
    return (
      <ErrorCard
        message="Failed to load workspace data"
        onRetry={onRetryWriterWorkspace}
        variant="compact"
        isDark={isDark}
      />
    )
  }

  const chapterTarget = writerWorkspace?.word_count_goals.chapter_target ?? 0
  const etaDays = targetWords && currentWords !== null && dailyTarget > 0
    ? Math.max(0, Math.ceil(Math.max(0, targetWords - currentWords) / dailyTarget))
    : null
  const incompleteItems = (writerWorkspace?.goal_calendar ?? []).filter((item) => !item.completed)

  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <PlanningMetric isDark={isDark} label="Book goal" value={targetWords ? `${targetWords.toLocaleString()} words` : "Not set"} />
        <PlanningMetric isDark={isDark} label="Chapter goal" value={chapterTarget > 0 ? `${chapterTarget.toLocaleString()} avg. words` : `${formatNumber(chapterCount)} chapters`} />
        <PlanningMetric isDark={isDark} label="Daily quota" value={`${dailyTarget.toLocaleString()} words`} />
        <PlanningMetric isDark={isDark} label="Writing streak" value={`${loginStreakDays} day${loginStreakDays === 1 ? "" : "s"}`} />
        <PlanningMetric isDark={isDark} label="Target completion" value={etaDays !== null ? (etaDays === 0 ? "Target reached" : `In ${etaDays} days`) : "Not available"} />
      </div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(18rem,0.45fr)] xl:auto-rows-fr">
        <GoalCalendarCard
          isDark={isDark}
          writerWorkspace={writerWorkspace}
          saveState={saveState}
          saveMessage={saveMessage}
          onSaveGoalCalendar={onSaveGoalCalendar}
          onOpenManuscript={onOpenManuscript}
        />
        <div className="space-y-5">
          <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
            <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Session goals</p>
            <div className="mt-4 space-y-3">
              {incompleteItems.slice(0, 3).map((item) => (
                <div key={item.id} className={`rounded-md border px-3 py-3 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white"}`}>
                  <p className={`break-words text-sm font-semibold leading-6 ${isDark ? "text-slate-100" : "text-slate-800"}`}>{item.title}</p>
                  <p className={`mt-1 text-xs ${isDark ? "text-slate-300" : "text-slate-600"}`}>Due {formatPlannerDate(item.due_date)}</p>
                </div>
              ))}
              {incompleteItems.length === 0 ? <p className={isDark ? "text-sm text-slate-300" : "text-sm text-slate-600"}>Add a planning item to define the next session.</p> : null}
            </div>
          </section>
          <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
            <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Quotas</p>
            <div className="mt-4 space-y-3">
              <CompactProgressRow isDark={isDark} label="Daily quota" value={`${dailyWords} / ${dailyTarget}`} percent={(dailyWords / dailyTarget) * 100} />
              {targetWords ? <CompactProgressRow isDark={isDark} label="Book target" value={`${formatNumber(currentWords)} / ${targetWords.toLocaleString()}`} percent={currentWords !== null ? (currentWords / targetWords) * 100 : 0} /> : null}
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

export function WorkspaceStatsTab({
  isDark,
  currentWords,
  targetWords,
  chapterCount,
  characterCount,
  worldArticleCount,
  percentComplete,
  chapters,
  dailyWords,
  dailyTarget,
  userStats,
  loginStreakDays,
  weeklyLoginActivity,
  onOpenManuscript,
}: {
  isDark: boolean
  currentWords: number | null
  targetWords: number | null
  chapterCount: number | null
  characterCount: number
  worldArticleCount: number
  percentComplete: number
  chapters: ChapterListResponse["chapters"]
  dailyWords: number
  dailyTarget: number
  userStats: UserStats | null
  loginStreakDays: number
  weeklyLoginActivity: boolean[]
  onOpenManuscript: () => void
}) {
  const averageWords = chapterCount && currentWords ? Math.round(currentWords / chapterCount) : 0
  const progress = clamp(
    targetWords && currentWords !== null ? (currentWords / targetWords) * 100 : percentComplete,
    0,
    100,
  )
  const chapterWordStats = chapters
    .filter((chapter) => typeof chapter.word_count === "number" && chapter.word_count > 0)
    .map((chapter) => ({ label: `Ch. ${chapter.number}`, value: chapter.word_count ?? 0 }))
  const measuredChapterAverage = chapterWordStats.length > 0
    ? Math.round(chapterWordStats.reduce((sum, chapter) => sum + chapter.value, 0) / chapterWordStats.length)
    : averageWords
  const recentWritingDays = getRecentWritingDays(userStats, 7)
  const recentWritingTotal = userStats?.writing.last_7_days.words ?? recentWritingDays.reduce((sum, day) => sum + day.value, 0)
  const recentWritingAverage = recentWritingDays.length > 0 ? Math.round(recentWritingTotal / recentWritingDays.length) : null

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,0.92fr)_minmax(0,1fr)_minmax(0,1fr)]">
      <h3 className="sr-only">Workspace stats</h3>
      <div className="xl:col-span-3">
        <ProjectOverviewCard isDark={isDark} currentWords={currentWords} chapterCount={chapterCount} characterCount={characterCount} worldArticleCount={worldArticleCount} />
      </div>
      <div className="space-y-5">
        <DailyGoalCard isDark={isDark} dailyWords={dailyWords} dailyTarget={dailyTarget} onUpdateGoal={onOpenManuscript} />
        <WritingStreakCard isDark={isDark} streakDays={loginStreakDays} weekActivity={weeklyLoginActivity} />
        <ProgressBreakdownCard
          isDark={isDark}
          progress={progress}
          currentWords={currentWords}
          targetWords={targetWords}
          chapters={chapters}
          dailyWords={dailyWords}
          dailyTarget={dailyTarget}
          userStats={userStats}
        />
      </div>
      <div className="space-y-5">
        <BarChartCard
          isDark={isDark}
          title="Chapter cadence"
          eyebrow="Average words per measured chapter"
          value={measuredChapterAverage ? measuredChapterAverage.toLocaleString() : "No data"}
          data={chapterWordStats.slice(-5)}
          emptyLabel="No chapter word counts have been recorded yet."
        />
        <BarChartCard
          isDark={isDark}
          title="Writing velocity"
          eyebrow="Average words per day, last 7 days"
          value={recentWritingAverage !== null ? recentWritingAverage.toLocaleString() : "No data"}
          data={recentWritingDays}
          emptyLabel="No daily writing entries have been recorded this week."
        />
      </div>
      <div className="space-y-5">
        <TrendCard isDark={isDark} userStats={userStats} currentWords={currentWords} />
        <InsightsCard
          isDark={isDark}
          worldArticleCount={worldArticleCount}
          currentWords={currentWords}
          targetWords={targetWords}
          chapters={chapters}
          userStats={userStats}
        />
      </div>
    </div>
  )
}

export function StoryMapTab({
  isDark,
  bookId,
  preWritingCheck,
  revisionIntelligence,
  onOpenRelationships,
  onNavigate,
  preWritingCheckError,
  onRetryPreWritingCheck,
  revisionIntelligenceError,
  onRetryRevisionIntelligence,
}: {
  isDark: boolean
  bookId: string
  preWritingCheck: PreWritingCheck | null
  revisionIntelligence: RevisionIntelligence | null
  onOpenRelationships: () => void
  onNavigate: (href: string) => void
  preWritingCheckError?: boolean
  onRetryPreWritingCheck?: () => void
  revisionIntelligenceError?: boolean
  onRetryRevisionIntelligence?: () => void
}) {
  if (preWritingCheckError && !preWritingCheck && onRetryPreWritingCheck) {
    return (
      <ErrorCard
        message="Failed to load story map data"
        onRetry={onRetryPreWritingCheck}
        variant="compact"
        isDark={isDark}
      />
    )
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-[minmax(0,0.98fr)_minmax(0,1.02fr)]">
        <section className={panelClass(isDark, "p-4 sm:p-5")}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Memory map</p>
              <h3 className={`mt-2 text-xl font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Who is in play and what still needs closure.</h3>
            </div>
            <button type="button" onClick={onOpenRelationships} className="text-sm font-semibold text-teal-700">
              Open graph
            </button>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <div className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Active characters</p>
              <div className="mt-3 space-y-3">
                {(preWritingCheck?.active_characters ?? []).slice(0, 4).map((character) => (
                  <div key={character.id}>
                    <p className={`text-sm font-medium ${isDark ? "text-slate-100" : "text-slate-800"}`}>{character.name}</p>
                    <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                      {character.role || "Character"}{character.last_seen_chapter ? ` / last seen in Chapter ${character.last_seen_chapter}` : ""}
                    </p>
                  </div>
                ))}
                {(preWritingCheck?.active_characters.length ?? 0) === 0 ? <p className={isDark ? "text-sm text-slate-300" : "text-sm text-slate-600"}>Character memory is still syncing.</p> : null}
              </div>
            </div>

            <div className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Unresolved threads</p>
              <div className="mt-3 space-y-3">
                {(preWritingCheck?.unresolved_threads ?? []).slice(0, 4).map((thread) => (
                  <div key={thread.id}>
                    <p className={`text-sm font-medium ${isDark ? "text-slate-100" : "text-slate-800"}`}>{thread.title}</p>
                    <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                      {thread.status}{thread.introduced_at ? ` / introduced in Chapter ${thread.introduced_at}` : ""}
                    </p>
                  </div>
                ))}
                {(preWritingCheck?.unresolved_threads.length ?? 0) === 0 ? <p className={isDark ? "text-sm text-slate-300" : "text-sm text-slate-600"}>No open threads are surfaced yet.</p> : null}
              </div>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <button type="button" onClick={() => onNavigate(`/${bookId}/timeline`)} className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-teal-800/10 text-teal-100 hover:bg-teal-800/20" : "bg-teal-50 text-teal-800 hover:bg-teal-100"}`}>
              Open timeline
            </button>
            <button type="button" onClick={() => onNavigate(`/${bookId}/characters`)} className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white/[0.06] text-slate-200 hover:bg-white/[0.1]" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}>
              Open character bible
            </button>
          </div>
        </section>

        <section className={panelClass(isDark, "p-4 sm:p-5")}>
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Continuity findings</p>
          <div className="mt-4 space-y-3">
            {(preWritingCheck?.alerts ?? []).slice(0, 5).map((alert) => (
              <div key={`${alert.title}-${alert.chapter_ref ?? "na"}`} className={`rounded-md border px-4 py-3 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white"}`}>
                <div className="flex items-center justify-between gap-3">
                  <p className={`text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-800"}`}>{alert.title}</p>
                  {alert.chapter_ref ? <span className={`text-xs ${isDark ? "text-slate-300" : "text-slate-600"}`}>Ch {alert.chapter_ref}</span> : null}
                </div>
                <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{alert.body}</p>
              </div>
            ))}
            {(preWritingCheck?.alerts.length ?? 0) === 0 ? <p className={isDark ? "text-sm text-slate-300" : "text-sm text-slate-600"}>Continuity findings will appear here after the next intelligence pass.</p> : null}
          </div>
        </section>
      </div>

      {revisionIntelligence ? (
        <RevisionIntelligencePanel
          bookId={bookId}
          revision={revisionIntelligence}
          writerWorkspace={null}
          isDark={isDark}
          onRevisionChange={() => {}}
          onWriterWorkspaceChange={() => {}}
          variant="story-map"
        />
      ) : revisionIntelligenceError && onRetryRevisionIntelligence ? (
        <ErrorCard
          message="Failed to load revision intelligence"
          onRetry={onRetryRevisionIntelligence}
          variant="compact"
          isDark={isDark}
        />
      ) : null}
    </div>
  )
}


function CompactProgressRow({ isDark, label, value, percent, tone = "teal" }: { isDark: boolean; label: string; value: string; percent: number; tone?: "teal" | "amber" | "rose" }) {
  const color = tone === "amber" ? "bg-amber-400" : tone === "rose" ? "bg-rose-400" : "bg-teal-500"
  return (
    <div className={`rounded-md border px-4 py-3 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white"}`}>
      <div className="flex items-center justify-between gap-3">
        <span className={`min-w-0 text-sm ${isDark ? "text-slate-300" : "text-slate-600"}`}>{label}</span>
        <span className={`max-w-[58%] break-words text-right text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-800"}`}>{value}</span>
      </div>
      <div className={`mt-3 h-1.5 overflow-hidden rounded-full ${isDark ? "bg-white/[0.08]" : "bg-slate-100"}`}>
        <div className={`h-full rounded-full ${color}`} style={{ width: `${clamp(percent, 0, 100)}%` }} />
      </div>
    </div>
  )
}

function InfoLine({ isDark, label, value, onClick, active = false }: { isDark: boolean; label: string; value: string; onClick?: () => void; active?: boolean }) {
  const baseClass = `flex w-full items-center justify-between gap-3 rounded-md border px-4 py-3 text-sm ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white"}`

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={`${baseClass} transition ${isDark ? "hover:bg-white/[0.06]" : "hover:bg-slate-50"} ${active ? (isDark ? "ring-1 ring-sky-400/60" : "ring-1 ring-sky-500/50") : ""}`}
      >
        <span className={isDark ? "min-w-0 text-left text-slate-300" : "min-w-0 text-left text-slate-600"}>{label}</span>
        <span className={`max-w-[56%] break-words text-right font-semibold ${isDark ? "text-slate-100" : "text-slate-800"}`}>{value}</span>
      </button>
    )
  }

  return (
    <div className={baseClass}>
      <span className={isDark ? "min-w-0 text-slate-300" : "min-w-0 text-slate-600"}>{label}</span>
      <span className={`max-w-[56%] break-words text-right font-semibold ${isDark ? "text-slate-100" : "text-slate-800"}`}>{value}</span>
    </div>
  )
}

function ActionRow({ isDark, icon, title, body, onClick, tone = "default" }: { isDark: boolean; icon: IconName; title: string; body: string; onClick: () => void; tone?: "default" | "amber" | "teal" }) {
  const iconClass = tone === "amber"
    ? isDark ? "text-amber-300" : "text-amber-700"
    : tone === "teal"
      ? isDark ? "text-teal-300" : "text-teal-700"
      : isDark ? "text-slate-300" : "text-slate-600"
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center gap-3 rounded-md border px-4 py-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06]" : "border-slate-200 bg-white hover:bg-slate-50"}`}
    >
      <Icon name={icon} className={`h-5 w-5 ${iconClass}`} />
      <div className="min-w-0 flex-1">
        <p className={`break-words text-sm font-semibold leading-6 ${isDark ? "text-slate-100" : "text-slate-800"}`}>{title}</p>
        <p className={`mt-1 break-words text-xs leading-5 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{body}</p>
      </div>
      <Icon name="chevron" className={`h-4 w-4 ${isDark ? "text-teal-300" : "text-teal-700"}`} />
    </button>
  )
}

function ScoreRing({ isDark, score, label }: { isDark: boolean; score: number; label: string }) {
  const safeScore = clamp(Math.round(score), 0, 100)
  return (
    <div
      className="relative flex h-28 w-28 items-center justify-center rounded-full"
      style={{ background: `conic-gradient(#8b5cf6 0 ${safeScore}%, ${isDark ? "#1b2430" : "#edf0f5"} ${safeScore}% 100%)` }}
    >
      <div className={`flex h-20 w-20 flex-col items-center justify-center rounded-full ${isDark ? "bg-[#0d141c]" : "bg-white"}`}>
        <span className={`text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{safeScore}</span>
        <span className={`text-3xs ${isDark ? "text-slate-300" : "text-slate-600"}`}>{label}</span>
      </div>
    </div>
  )
}

function PlanningMetric({ isDark, label, value }: { isDark: boolean; label: string; value: string }) {
  return (
    <div className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-white"}`}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>{label}</p>
      <p className={`mt-2 break-words text-lg font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{value}</p>
    </div>
  )
}

function ProgressBreakdownCard({
  isDark,
  progress,
  currentWords,
  targetWords,
  chapters,
  dailyWords,
  dailyTarget,
  userStats,
}: {
  isDark: boolean
  progress: number
  currentWords: number | null
  targetWords: number | null
  chapters: ChapterListResponse["chapters"]
  dailyWords: number
  dailyTarget: number
  userStats: UserStats | null
}) {
  const processedChapters = chapters.filter((chapter) => chapter.processed).length
  const intelligenceReadyChapters = chapters.filter((chapter) => chapter.intelligence_available !== false).length
  const chapterTotal = chapters.length
  const weeklyWords = userStats?.writing.this_week.words ?? 0
  const weeklyTarget = userStats?.writing.this_week.target_words ?? null
  const rows: Array<{ label: string; value: string; percent: number; tone: "teal" | "amber" | "rose" }> = [
    {
      label: "Processed chapters",
      value: `${processedChapters} / ${chapterTotal}`,
      percent: chapterTotal > 0 ? (processedChapters / chapterTotal) * 100 : 0,
      tone: processedChapters === chapterTotal ? "teal" : "amber",
    },
    {
      label: "Intelligence coverage",
      value: `${intelligenceReadyChapters} / ${chapterTotal}`,
      percent: chapterTotal > 0 ? (intelligenceReadyChapters / chapterTotal) * 100 : 0,
      tone: intelligenceReadyChapters === chapterTotal ? "teal" : "amber",
    },
    {
      label: "Daily goal",
      value: `${dailyWords.toLocaleString()} / ${dailyTarget.toLocaleString()}`,
      percent: (dailyWords / dailyTarget) * 100,
      tone: dailyWords >= dailyTarget ? "teal" : "amber",
    },
  ]

  if (targetWords) {
    rows.unshift({
      label: "Book target",
      value: `${formatNumber(currentWords)} / ${targetWords.toLocaleString()}`,
      percent: progress,
      tone: "teal",
    })
  }

  if (weeklyTarget && weeklyTarget > 0) {
    rows.push({
      label: "Weekly goal",
      value: `${weeklyWords.toLocaleString()} / ${weeklyTarget.toLocaleString()}`,
      percent: (weeklyWords / weeklyTarget) * 100,
      tone: weeklyWords >= weeklyTarget ? "teal" : "amber",
    })
  }

  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Progress breakdown</p>
      <div className="mt-4 space-y-3">
        {rows.map(({ label, value, percent, tone }) => (
          <CompactProgressRow key={label} isDark={isDark} label={label} value={value} percent={percent} tone={tone} />
        ))}
      </div>
    </section>
  )
}

function BarChartCard({
  isDark,
  title,
  eyebrow,
  value,
  data,
  emptyLabel,
}: {
  isDark: boolean
  title: string
  eyebrow: string
  value: string
  data: Array<{ label: string; value: number }>
  emptyLabel: string
}) {
  const maxValue = data.reduce((max, item) => Math.max(max, item.value), 0)
  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>{title}</p>
      <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-slate-600"}`}>{eyebrow}</p>
      <p className={`mt-1 text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{value}</p>
      {data.length > 0 ? (
        <div className="mt-5 flex h-32 items-end gap-3 border-b border-white/10 px-2">
          {data.map((item) => (
            <div key={item.label} className="flex flex-1 flex-col items-center justify-end gap-2" title={`${item.label}: ${item.value.toLocaleString()} words`}>
              <div className="w-full rounded-t-lg bg-teal-500/80" style={{ height: `${clamp((item.value / Math.max(1, maxValue)) * 100, 8, 100)}%` }} />
              <span className={`text-3xs ${isDark ? "text-slate-300" : "text-slate-600"}`}>{item.label}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className={`mt-5 rounded-md border px-4 py-6 text-sm leading-6 ${isDark ? "border-white/[0.06] bg-white/[0.03] text-slate-300" : "border-slate-200 bg-slate-50 text-slate-600"}`}>{emptyLabel}</p>
      )}
    </section>
  )
}

function TrendCard({ isDark, userStats, currentWords }: { isDark: boolean; userStats: UserStats | null; currentWords: number | null }) {
  const recentDays = getRecentWritingDays(userStats, 14)
  const maxValue = recentDays.reduce((max, day) => Math.max(max, day.value), 0)
  const last30Words = userStats?.writing.last_30_days.words ?? null
  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Trend overview</p>
      <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-slate-600"}`}>Words written in the last 30 days</p>
      <p className="mt-2 text-2xl font-semibold text-teal-500">{last30Words !== null ? last30Words.toLocaleString() : "No data"}</p>
      {recentDays.length > 0 ? (
        <div className="mt-5 grid h-28 items-end gap-1.5" style={{ gridTemplateColumns: `repeat(${recentDays.length}, minmax(0, 1fr))` }}>
          {recentDays.map((day) => (
            <div key={day.key} className="rounded-t-lg bg-teal-500/70" title={`${day.label}: ${day.value.toLocaleString()} words`} style={{ height: `${day.value > 0 ? clamp((day.value / Math.max(1, maxValue)) * 100, 8, 100) : 0}%` }} />
          ))}
        </div>
      ) : (
        <p className={`mt-5 rounded-md border px-4 py-6 text-sm leading-6 ${isDark ? "border-white/[0.06] bg-white/[0.03] text-slate-300" : "border-slate-200 bg-slate-50 text-slate-600"}`}>No recent writing entries have been recorded.</p>
      )}
      <p className={`mt-4 text-xs ${isDark ? "text-slate-300" : "text-slate-600"}`}>Current manuscript words: {formatNumber(currentWords)}</p>
    </section>
  )
}

function InsightsCard({
  isDark,
  worldArticleCount,
  currentWords,
  targetWords,
  chapters,
  userStats,
}: {
  isDark: boolean
  worldArticleCount: number
  currentWords: number | null
  targetWords: number | null
  chapters: ChapterListResponse["chapters"]
  userStats: UserStats | null
}) {
  const measuredChapters = chapters.filter((chapter) => typeof chapter.word_count === "number" && chapter.word_count > 0).length
  const processedChapters = chapters.filter((chapter) => chapter.processed).length
  const last7Words = userStats?.writing.last_7_days.words ?? null
  const insights = [
    `${measuredChapters} of ${chapters.length} chapters have measured word counts.`,
    `${processedChapters} of ${chapters.length} chapters are processed for workspace intelligence.`,
    currentWords !== null
      ? targetWords
        ? `${formatNumber(currentWords)} of ${targetWords.toLocaleString()} target words are drafted.`
        : `${formatNumber(currentWords)} manuscript words are drafted; no book target is set.`
      : "Manuscript word total is not available yet.",
    last7Words !== null ? `${last7Words.toLocaleString()} words were recorded in the last 7 days.` : "Recent writing totals will appear after the stats feed syncs.",
    `${worldArticleCount.toLocaleString()} world item${worldArticleCount === 1 ? "" : "s"} are attached to this workspace.`,
  ]
  return (
    <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Insights</p>
      <div className="mt-4 space-y-3">
        {insights.map((insight, index) => (
          <div key={insight} className={`rounded-md border px-4 py-3 text-sm leading-6 ${isDark ? "border-white/[0.06] bg-white/[0.03] text-slate-300" : "border-slate-200 bg-white text-slate-600"}`}>
            <span className={`mr-2 font-semibold ${isDark ? "text-teal-300" : "text-teal-700"}`}>{index + 1}.</span>{insight}
          </div>
        ))}
      </div>
      <button type="button" className={footerLinkClass(isDark)}>View all insights <Icon name="chevron" /></button>
    </section>
  )
}


function EmptyTabState({ isDark, title, body }: { isDark: boolean; title: string; body: string }) {
  return (
    <div className={`rounded-md border border-dashed px-5 py-10 text-center ${isDark ? "border-white/[0.08] text-slate-300" : "border-slate-200 text-slate-600"}`}>
      <p className={`text-lg font-semibold ${isDark ? "text-slate-200" : "text-slate-800"}`}>{title}</p>
      <p className="mt-2 text-sm leading-6">{body}</p>
    </div>
  )
}

function panelClass(isDark: boolean, extra = "") {
  return `min-w-0 rounded-lg border ${
    isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"
  } ${extra}`
}

function footerLinkClass(isDark: boolean) {
  return `mt-5 inline-flex w-full items-center justify-center gap-2 rounded-md border px-4 py-3 text-sm font-semibold transition ${
    isDark ? "border-white/10 bg-white/[0.04] text-teal-200 hover:bg-white/[0.08]" : "border-slate-200 bg-white text-teal-800 hover:bg-slate-50"
  }`
}

function severityClass(severity: string, isDark: boolean) {
  if (severity === "High") return isDark ? "bg-rose-500/10 text-rose-300" : "bg-rose-50 text-rose-800"
  if (severity === "Medium") return isDark ? "bg-amber-500/10 text-amber-300" : "bg-amber-50 text-amber-800"
  return isDark ? "bg-emerald-500/10 text-emerald-300" : "bg-emerald-50 text-emerald-800"
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

function formatNumber(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "Unavailable"
  return value.toLocaleString()
}

function getRecentWritingDays(userStats: UserStats | null, count: number) {
  if (!userStats?.writing.heatmap.length) return []

  return [...userStats.writing.heatmap]
    .sort((left, right) => left.date.localeCompare(right.date))
    .slice(-count)
    .map((day) => {
      const date = new Date(`${day.date}T00:00:00Z`)
      return {
        key: day.date,
        label: date.toLocaleDateString(undefined, { weekday: "short", timeZone: "UTC" }),
        value: day.words,
      }
    })
}
