"use client"

import { useEffect, useMemo, useRef, useState } from "react"
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
import { Dialog } from "@/components/ui/Dialog"
import { ErrorCard } from "@/components/ui/ErrorCard"
import { findRevisionTaskSource } from "@/lib/utils/revisionIntelligence"
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
  canOpenManuscript,
  onOpenStats,
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
  totalRevisionItems: number | null
  highSeverityItems: number | null
  canOpenManuscript: boolean
  onOpenStats: () => void
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
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)_minmax(0,0.9fr)]">
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
          <InfoLine isDark={isDark} label="Active revision items" value={totalRevisionItems === null ? "Not available" : String(totalRevisionItems)} />
          <InfoLine isDark={isDark} label="Last written" value={latestChapter ? `${unitTitle} ${latestChapter.number}` : "No chapter activity"} />
          <button type="button" onClick={onOpenStats} className={footerLinkClass(isDark)}>
            View workspace stats <Icon name="chevron" />
          </button>
        </div>
      </section>
      <section className={panelClass(isDark, "h-full p-4 sm:p-5")}>
        <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Up next</p>
        <div className="mt-5 space-y-3">
          {canOpenManuscript ? <ActionRow isDark={isDark} icon="pen" title="Continue writing" body={latestChapter ? `${unitTitle} ${latestChapter.number}` : "Open manuscript"} onClick={onOpenManuscript} /> : null}
          <ActionRow isDark={isDark} icon="timeline" title="Review high severity risks" body={highSeverityItems === null ? "Open the revision report" : `${highSeverityItems} item${highSeverityItems === 1 ? "" : "s"} need attention`} onClick={() => onNavigate(`/${bookId}/analysis`)} tone="amber" />
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
  revisionIntelligence,
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
  revisionIntelligence: RevisionIntelligence | null
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
  const [selectedTaskSnapshot, setSelectedTaskSnapshot] = useState<GoalCalendarItem | null>(null)
  const [confirmTaskDelete, setConfirmTaskDelete] = useState(false)
  const [deletingTask, setDeletingTask] = useState(false)
  const [taskDeleteError, setTaskDeleteError] = useState(false)
  const taskListRef = useRef<HTMLElement>(null)
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
  const taskItems = (writerWorkspace?.goal_calendar ?? []).filter((item) => item.quota_unit === "tasks")
  const selectedTask = taskItems.find((item) => item.id === selectedTaskSnapshot?.id) ?? selectedTaskSnapshot
  const sourceFinding = selectedTask ? findRevisionTaskSource(revisionIntelligence, selectedTask.id) : null
  const closeTaskDetails = () => {
    if (deletingTask) return
    setSelectedTaskSnapshot(null)
    setConfirmTaskDelete(false)
    setTaskDeleteError(false)
  }
  const deleteSelectedTask = async () => {
    if (!selectedTask || deletingTask || !writerWorkspace) return
    setDeletingTask(true)
    setTaskDeleteError(false)
    try {
      const saved = await onSaveGoalCalendar(writerWorkspace.goal_calendar.filter((item) => item.id !== selectedTask.id))
      if (saved) {
        setSelectedTaskSnapshot(null)
        setConfirmTaskDelete(false)
        window.setTimeout(() => taskListRef.current?.focus(), 0)
      } else {
        setTaskDeleteError(true)
      }
    } catch {
      setTaskDeleteError(true)
    } finally {
      setDeletingTask(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <PlanningMetric isDark={isDark} label="Book goal" value={targetWords ? `${targetWords.toLocaleString()} words` : "Not set"} />
        <PlanningMetric isDark={isDark} label="Chapter goal" value={chapterTarget > 0 ? `${chapterTarget.toLocaleString()} avg. words` : `${formatNumber(chapterCount)} chapters`} />
        <PlanningMetric isDark={isDark} label="Daily quota" value={`${dailyTarget.toLocaleString()} words`} />
        <PlanningMetric isDark={isDark} label="Sign-in streak" value={`${loginStreakDays} day${loginStreakDays === 1 ? "" : "s"}`} />
        <PlanningMetric isDark={isDark} label="Target completion" value={etaDays !== null ? (etaDays === 0 ? "Target reached" : `In ${etaDays} days`) : "Not available"} />
      </div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(18rem,0.45fr)] xl:auto-rows-fr">
        <div id="author-goal-calendar" className="min-w-0 scroll-mt-6">
          <GoalCalendarCard
            isDark={isDark}
            writerWorkspace={writerWorkspace}
            saveState={saveState}
            saveMessage={saveMessage}
            onSaveGoalCalendar={onSaveGoalCalendar}
            onOpenManuscript={onOpenManuscript}
          />
        </div>
        <div className="space-y-5">
          <section id="author-project-tasks" ref={taskListRef} tabIndex={-1} className={panelClass(isDark, "scroll-mt-6 p-4 sm:p-5")}>
            <h3 className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Revision tasks</h3>
            <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-200" : "text-slate-700"}`}>
              Tasks from Story Map and the revision workflow are saved in this project’s Goal Calendar. Select a task for details; its source finding remains on the revision board.
            </p>
            <p className={`mt-3 text-xs ${isDark ? "text-teal-200" : "text-teal-800"}`}>
              {taskItems.length} task{taskItems.length === 1 ? "" : "s"} in this project
            </p>
            {taskItems.length > 0 ? (
              <ul className={`mt-3 divide-y ${isDark ? "divide-white/10" : "divide-stone-200"}`}>
                {taskItems.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedTaskSnapshot(item)
                        setConfirmTaskDelete(false)
                        setTaskDeleteError(false)
                      }}
                      className={`flex w-full items-start justify-between gap-3 rounded-sm px-2 py-3 text-left text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-400 ${isDark ? "hover:bg-white/[0.06]" : "hover:bg-stone-100"}`}
                      aria-label={`View task details: ${item.title}`}
                    >
                      <span className={item.completed ? "line-through opacity-60" : "font-medium"}>{item.title}</span>
                      <span className={`shrink-0 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{formatPlannerDate(item.due_date)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </section>
          <Dialog
            open={selectedTask !== null}
            onClose={closeTaskDetails}
            title={selectedTask?.title ?? "Task details"}
            eyebrow="Revision task"
            size="sm"
            className="rounded-xl"
            contentClassName="relative p-5 sm:p-6"
            titleClassName="pr-8 text-xl"
          >
            <button
              type="button"
              onClick={closeTaskDetails}
              disabled={deletingTask}
              aria-label="Close task details"
              className="absolute right-4 top-4 rounded-md px-2 py-1 text-xl leading-none text-[rgb(var(--muted-foreground))] hover:bg-[rgba(var(--foreground),0.08)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal-400"
            >
              ×
            </button>
            {selectedTask ? (
              <div className="mt-5 space-y-5 text-sm">
                <dl className="grid grid-cols-2 gap-4 border-y border-[rgba(var(--border),0.5)] py-4">
                  <div>
                    <dt className="text-[rgb(var(--muted-foreground))]">Status</dt>
                    <dd className="mt-1 font-medium">{selectedTask.completed ? "Completed" : "Open"}</dd>
                  </div>
                  <div>
                    <dt className="text-[rgb(var(--muted-foreground))]">Due</dt>
                    <dd className="mt-1 font-medium">{formatPlannerDate(selectedTask.due_date)}</dd>
                  </div>
                </dl>
                {sourceFinding ? (
                  <div className="space-y-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[rgb(var(--muted-foreground))]">Source finding</p>
                    <p className="leading-6">{sourceFinding.description}</p>
                    <dl className="grid grid-cols-2 gap-3 text-xs">
                      <div><dt className="text-[rgb(var(--muted-foreground))]">Category</dt><dd className="mt-1 capitalize">{sourceFinding.category}</dd></div>
                      <div><dt className="text-[rgb(var(--muted-foreground))]">Severity</dt><dd className="mt-1 capitalize">{sourceFinding.severity}</dd></div>
                      {sourceFinding.chapter_ref != null ? <div><dt className="text-[rgb(var(--muted-foreground))]">Chapter</dt><dd className="mt-1">{sourceFinding.chapter_ref}</dd></div> : null}
                    </dl>
                    {sourceFinding.recommendation ? <p className="border-l-2 border-teal-500 pl-3 leading-6">{sourceFinding.recommendation}</p> : null}
                  </div>
                ) : null}
                <p className="text-xs text-[rgb(var(--muted-foreground))]">Manage this task in Goal Calendar.</p>
                {taskDeleteError ? <p role="alert" className="text-xs text-red-400">Could not delete this task. Please try again.</p> : null}
                {confirmTaskDelete ? (
                  <div className="rounded-md border border-red-500/30 p-3">
                    <p className="leading-6">Delete this task from Goal Calendar? The source finding will stay on the revision board.</p>
                    <div className="mt-3 flex flex-wrap justify-end gap-2">
                      <button type="button" disabled={deletingTask} onClick={() => setConfirmTaskDelete(false)} className="rounded-md border border-[rgba(var(--border),0.7)] px-3 py-2 font-medium disabled:opacity-50">Cancel</button>
                      <button type="button" disabled={deletingTask} onClick={deleteSelectedTask} className="rounded-md bg-red-700 px-3 py-2 font-semibold text-white hover:bg-red-600 disabled:opacity-50">{deletingTask ? "Deleting…" : "Confirm delete"}</button>
                    </div>
                  </div>
                ) : (
                  <button type="button" onClick={() => setConfirmTaskDelete(true)} className="rounded-md border border-red-500/30 px-3 py-2 font-medium text-red-400 hover:bg-red-500/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-red-400">Delete task</button>
                )}
              </div>
            ) : null}
          </Dialog>
          <section className={panelClass(isDark, "p-4 sm:p-5")}>
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
          <section className={panelClass(isDark, "p-4 sm:p-5")}>
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
  const recentWritingTrend = getRecentWritingDays(userStats, 14)
  const completedChapterCount = chapters.filter((chapter) => chapter.processed).length

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,0.82fr)_minmax(0,1.18fr)]">
      <h3 className="sr-only">Workspace stats</h3>
      <div className="xl:col-span-2">
        <ProjectOverviewCard isDark={isDark} currentWords={currentWords} chapterCount={chapterCount} characterCount={characterCount} worldArticleCount={worldArticleCount} />
      </div>
      <div className="space-y-5">
        <DailyGoalCard isDark={isDark} dailyWords={dailyWords} dailyTarget={dailyTarget} onUpdateGoal={onOpenManuscript} />
        <WritingStreakCard isDark={isDark} streakDays={loginStreakDays} weekActivity={weeklyLoginActivity} />
        <GoalRingCard isDark={isDark} progress={progress} currentWords={currentWords} targetWords={targetWords} />
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
      <div className="grid gap-5 md:grid-cols-2">
        <ChapterLengthChart isDark={isDark} data={chapterWordStats} average={measuredChapterAverage} />
        <WritingLineChart isDark={isDark} data={recentWritingTrend} average={recentWritingAverage} />
        <ChapterProcessingChart isDark={isDark} processed={completedChapterCount} total={chapters.length} />
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
  writerWorkspace,
  onOpenRelationships,
  onNavigate,
  onRevisionChange,
  onWriterWorkspaceChange,
  onTaskCreated,
  preWritingCheckError,
  onRetryPreWritingCheck,
  revisionIntelligenceError,
  onRetryRevisionIntelligence,
}: {
  isDark: boolean
  bookId: string
  preWritingCheck: PreWritingCheck | null
  revisionIntelligence: RevisionIntelligence | null
  writerWorkspace: WriterWorkspace | null
  onOpenRelationships: () => void
  onNavigate: (href: string) => void
  onRevisionChange: (revision: RevisionIntelligence) => void
  onWriterWorkspaceChange: (workspace: WriterWorkspace) => void
  onTaskCreated: (count: number) => void
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
              <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Story cast</p>
              <h3 className={`mt-2 text-xl font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Characters, threads, and the next pressure point.</h3>
            </div>
            <button type="button" onClick={onOpenRelationships} className="text-sm font-semibold text-teal-700 dark:text-teal-300">
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
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Continuity notes</p>
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

      <StoryMapSignalCharts isDark={isDark} preWritingCheck={preWritingCheck} />

      {revisionIntelligence ? (
        <RevisionIntelligencePanel
          bookId={bookId}
          revision={revisionIntelligence}
          writerWorkspace={writerWorkspace}
          isDark={isDark}
          onRevisionChange={onRevisionChange}
          onWriterWorkspaceChange={onWriterWorkspaceChange}
          onTaskCreated={onTaskCreated}
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

function StoryMapSignalCharts({ isDark, preWritingCheck }: { isDark: boolean; preWritingCheck: PreWritingCheck | null }) {
  const recentEvents = preWritingCheck?.recent_events ?? []
  const activeCharacters = preWritingCheck?.active_characters ?? []
  const maxChapter = Math.max(
    preWritingCheck?.upcoming_chapter ? preWritingCheck.upcoming_chapter - 1 : 0,
    ...recentEvents.map((event) => event.chapter_number),
    ...activeCharacters.map((character) => character.last_seen_chapter ?? 0),
    1,
  )

  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Story shape</p>
          <h3 className={`mt-2 text-xl font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>A visual read on movement through the draft.</h3>
        </div>
        <p className={`text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>Based on the chapters and entities already in this project</p>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(18rem,0.85fr)]">
        <div className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-white/[0.025]" : "border-slate-200/70 bg-slate-50/60"}`}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className={`text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-800"}`}>Recent story beats</p>
              <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>Where the latest extracted events land by chapter.</p>
            </div>
            <span className={`text-xs font-semibold ${isDark ? "text-teal-200" : "text-teal-800"}`}>{recentEvents.length} beats</span>
          </div>
          {recentEvents.length > 0 ? (
            <div className="mt-6 space-y-4">
              {recentEvents.slice(-6).map((event) => (
                <div key={`${event.chapter_number}-${event.detail}`} className="grid grid-cols-[3.5rem_minmax(0,1fr)] items-start gap-3">
                  <div className={`pt-1 text-xs font-semibold ${isDark ? "text-teal-200" : "text-teal-800"}`}>Ch {event.chapter_number}</div>
                  <div className="relative border-l pl-4 before:absolute before:-left-[0.34rem] before:top-1.5 before:h-2.5 before:w-2.5 before:rounded-full before:bg-teal-500">
                    <p className={`text-sm leading-6 ${isDark ? "text-slate-200" : "text-slate-700"}`}>{event.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className={`mt-5 rounded-md border border-dashed px-4 py-6 text-sm ${isDark ? "border-white/[0.08] text-slate-300" : "border-slate-200 text-slate-600"}`}>No extracted story beats are available yet.</p>
          )}
        </div>

        <div className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-white/[0.025]" : "border-slate-200/70 bg-slate-50/60"}`}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className={`text-sm font-semibold ${isDark ? "text-slate-100" : "text-slate-800"}`}>Last-seen spread</p>
              <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>The latest chapter where each active character appears.</p>
            </div>
            <span className={`text-xs font-semibold ${isDark ? "text-teal-200" : "text-teal-800"}`}>Ch {maxChapter}</span>
          </div>
          {activeCharacters.length > 0 ? (
            <div className="mt-6 space-y-4">
              {activeCharacters.slice(0, 6).map((character) => {
                const lastSeen = character.last_seen_chapter ?? 0
                const width = lastSeen > 0 ? Math.max(8, (lastSeen / maxChapter) * 100) : 0
                return (
                  <div key={character.id}>
                    <div className="flex items-center justify-between gap-3">
                      <p className={`min-w-0 truncate text-sm font-medium ${isDark ? "text-slate-200" : "text-slate-700"}`}>{character.name}</p>
                      <span className={`shrink-0 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>{lastSeen > 0 ? `Ch ${lastSeen}` : "Not placed"}</span>
                    </div>
                    <div className={`mt-2 h-2 overflow-hidden rounded-full ${isDark ? "bg-white/[0.08]" : "bg-slate-200"}`}>
                      <div className="h-full rounded-full bg-gradient-to-r from-teal-600 to-sky-400" style={{ width: `${width}%` }} />
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <p className={`mt-5 rounded-md border border-dashed px-4 py-6 text-sm ${isDark ? "border-white/[0.08] text-slate-300" : "border-slate-200 text-slate-600"}`}>No active character positions are available yet.</p>
          )}
        </div>
      </div>
    </section>
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

function GoalRingCard({ isDark, progress, currentWords, targetWords }: { isDark: boolean; progress: number; currentWords: number | null; targetWords: number | null }) {
  const safeProgress = clamp(Math.round(progress), 0, 100)
  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <div className="flex items-center gap-4">
        <div
          className="relative flex h-24 w-24 shrink-0 items-center justify-center rounded-full"
          style={{ background: `conic-gradient(#14b8a6 0 ${safeProgress}%, ${isDark ? "#26313a" : "#e5e7eb"} ${safeProgress}% 100%)` }}
          aria-label={`${safeProgress}% of the book target`}
          role="img"
        >
          <div className={`flex h-[4.25rem] w-[4.25rem] items-center justify-center rounded-full text-lg font-semibold ${isDark ? "bg-[#0d141c] text-white" : "bg-white text-stone-950"}`}>{safeProgress}%</div>
        </div>
        <div className="min-w-0">
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Book progress</p>
          <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-200" : "text-slate-700"}`}>
            {currentWords !== null && targetWords ? `${currentWords.toLocaleString()} of ${targetWords.toLocaleString()} words` : "No book target is set yet."}
          </p>
        </div>
      </div>
    </section>
  )
}

function ChapterLengthChart({ isDark, data, average }: { isDark: boolean; data: Array<{ label: string; value: number }>; average: number }) {
  const maxValue = data.reduce((max, item) => Math.max(max, item.value), 0)
  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Chapter length</p>
          <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-slate-600"}`}>Word count by measured chapter</p>
        </div>
        <p className={`text-lg font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{average ? average.toLocaleString() : "—"}<span className={`ml-1 text-xs font-normal ${isDark ? "text-slate-400" : "text-stone-500"}`}>avg</span></p>
      </div>
      {data.length > 0 ? (
        <div className="mt-5 space-y-3">
          {data.map((item) => (
            <div key={item.label} className="grid grid-cols-[3rem_minmax(0,1fr)_4.5rem] items-center gap-3" title={`${item.label}: ${item.value.toLocaleString()} words`}>
              <span className={`text-xs font-medium ${isDark ? "text-slate-300" : "text-slate-600"}`}>{item.label}</span>
              <div className={`h-2.5 overflow-hidden rounded-full ${isDark ? "bg-white/[0.08]" : "bg-slate-100"}`}>
                <div className="h-full rounded-full bg-gradient-to-r from-teal-600 to-sky-400" style={{ width: `${Math.max(5, (item.value / Math.max(1, maxValue)) * 100)}%` }} />
              </div>
              <span className={`text-right text-xs font-semibold ${isDark ? "text-slate-200" : "text-slate-700"}`}>{item.value.toLocaleString()}</span>
            </div>
          ))}
        </div>
      ) : <EmptyChartMessage isDark={isDark}>No chapter word counts have been recorded yet.</EmptyChartMessage>}
    </section>
  )
}

function WritingLineChart({ isDark, data, average }: { isDark: boolean; data: Array<{ key: string; label: string; value: number }>; average: number | null }) {
  const width = 520
  const height = 180
  const padding = { top: 18, right: 14, bottom: 30, left: 14 }
  const maxValue = data.reduce((max, item) => Math.max(max, item.value), 0)
  const points = data.map((item, index) => {
    const x = data.length === 1 ? width / 2 : padding.left + (index / (data.length - 1)) * (width - padding.left - padding.right)
    const y = maxValue > 0 ? height - padding.bottom - (item.value / maxValue) * (height - padding.top - padding.bottom) : height - padding.bottom
    return { ...item, x, y }
  })
  const path = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" ")

  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Writing rhythm</p>
          <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-slate-600"}`}>Saved words over the last 14 recorded days</p>
        </div>
        <p className={`text-lg font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{average !== null ? average.toLocaleString() : "—"}<span className={`ml-1 text-xs font-normal ${isDark ? "text-slate-400" : "text-stone-500"}`}>daily avg</span></p>
      </div>
      {data.length > 0 ? (
        <div className="mt-4">
          <svg viewBox={`0 0 ${width} ${height}`} className="h-44 w-full" role="img" aria-label="Writing rhythm line chart">
            {[0.25, 0.5, 0.75].map((ratio) => <line key={ratio} x1={padding.left} x2={width - padding.right} y1={height - padding.bottom - ratio * (height - padding.top - padding.bottom)} y2={height - padding.bottom - ratio * (height - padding.top - padding.bottom)} stroke={isDark ? "#26313a" : "#e5e7eb"} strokeDasharray="4 6" />)}
            <path d={path} fill="none" stroke={isDark ? "#5eead4" : "#0f766e"} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
            {points.map((point) => <circle key={point.key} cx={point.x} cy={point.y} r="4" fill={isDark ? "#0d141c" : "white"} stroke={isDark ? "#5eead4" : "#0f766e"} strokeWidth="2" />)}
            <text x={padding.left} y={height - 7} fill={isDark ? "#94a3b8" : "#64748b"} fontSize="11">{data[0].label}</text>
            <text x={width - padding.right} y={height - 7} textAnchor="end" fill={isDark ? "#94a3b8" : "#64748b"} fontSize="11">{data[data.length - 1].label}</text>
          </svg>
        </div>
      ) : <EmptyChartMessage isDark={isDark}>No recent writing entries have been recorded.</EmptyChartMessage>}
    </section>
  )
}

function ChapterProcessingChart({ isDark, processed, total }: { isDark: boolean; processed: number; total: number }) {
  const remaining = Math.max(0, total - processed)
  const processedPercent = total > 0 ? (processed / total) * 100 : 0
  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>Draft coverage</p>
          <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-slate-600"}`}>Chapters available to the workspace</p>
        </div>
        <p className={`text-lg font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{processed}/{total}</p>
      </div>
      <div className={`mt-6 h-4 overflow-hidden rounded-full ${isDark ? "bg-white/[0.08]" : "bg-slate-100"}`}>
        <div className="h-full rounded-full bg-gradient-to-r from-teal-600 to-emerald-400" style={{ width: `${processedPercent}%` }} />
      </div>
      <div className={`mt-4 flex justify-between text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
        <span>{processed} processed</span>
        <span>{remaining} remaining</span>
      </div>
    </section>
  )
}

function EmptyChartMessage({ isDark, children }: { isDark: boolean; children: string }) {
  return <p className={`mt-5 rounded-md border border-dashed px-4 py-6 text-sm leading-6 ${isDark ? "border-white/[0.08] text-slate-300" : "border-slate-200 bg-slate-50 text-slate-600"}`}>{children}</p>
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
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-300" : "text-slate-600"}`}>At a glance</p>
      <div className="mt-4 space-y-3">
        {insights.map((insight, index) => (
          <div key={insight} className={`rounded-md border px-4 py-3 text-sm leading-6 ${isDark ? "border-white/[0.06] bg-white/[0.03] text-slate-300" : "border-slate-200 bg-white text-slate-600"}`}>
            <span className={`mr-2 inline-block h-2 w-2 rounded-full ${index === 0 ? "bg-teal-500" : index === 1 ? "bg-sky-400" : "bg-slate-400"}`} />{insight}
          </div>
        ))}
      </div>
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
