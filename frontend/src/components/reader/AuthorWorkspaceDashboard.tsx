"use client"

import React, { Suspense, useDeferredValue, useEffect, useState } from "react"

import { panelClass } from "@/components/overview/utils"
import { RevisionIntelligencePanel } from "@/components/revision/RevisionIntelligencePanel"
import { ErrorCard } from "@/components/ui/ErrorCard"
import { Skeleton } from "@/components/ui/Skeleton"
import {
  ActiveIssuesCard,
  CurrentProjectCard,
  OverviewHeader,
  RecentChaptersCard,
  RevisionPreviewPlaceholder,
  StoryPulseCard,
} from "./AuthorDashboardPrimaryPanels"
import {
  AuthorOverviewTab,
  PlanningTab,
  StoryMapTab,
  WorkspaceStatsTab,
} from "./AuthorDashboardTabs"
import type { Book, GoalCalendarItem, PreWritingCheck, RevisionIntelligence, StoryHealth, UserStats, WriterWorkspace } from "@/types/book"
import { buildManuscriptRecap } from "@/lib/utils/summaries"
import type { ChapterListResponse, SummaryCollectionResponse } from "@/types/reader"

type WorkspaceSaveState = "idle" | "saving" | "saved" | "error"
const DETAIL_TABS = [["planning", "Planning"], ["story-map", "Story Map"], ["stats", "Statistics"]] as const
type AuthorDashboardTab = typeof DETAIL_TABS[number][0]
type Props = {
  bookId: string
  book: Book
  isDark: boolean
  activeBookMode: "reader" | "author"
  canUseAuthorMode: boolean
  modeSaving: boolean
  greetingName: string
  canOpenManuscript: boolean
  currentWords: number | null
  targetWords: number | null
  percentComplete: number
  chapters: ChapterListResponse["chapters"]
  summaryCollection?: SummaryCollectionResponse | null
  unitTitle: string
  unitPrefix: string
  storyHealth: StoryHealth | null
  preWritingCheck: PreWritingCheck | null
  revisionIntelligence: RevisionIntelligence | null
  writerWorkspace: WriterWorkspace | null
  continuityIssueCount: number | null
  worldGapCount: number | null
  timelineIssueCount: number | null
  processingSummary: string | null
  chapterCount: number | null
  characterCount: number
  worldArticleCount: number
  loginStreakDays: number
  weeklyLoginActivity: boolean[]
  dailyWords: number
  dailyTarget: number
  userStats: UserStats | null
  saveState: WorkspaceSaveState
  saveMessage: string | null
  storyHealthError?: boolean
  onRetryStoryHealth?: () => void
  preWritingCheckError?: boolean
  onRetryPreWritingCheck?: () => void
  revisionIntelligenceError?: boolean
  onRetryRevisionIntelligence?: () => void
  writerWorkspaceError?: boolean
  onRetryWriterWorkspace?: () => void
  onModeChange: (nextMode: "reader" | "author") => void
  onToggleTheme: () => void
  onNavigate: (href: string) => void
  onOpenManuscript: () => void
  onOpenRelationships: () => void
  onSaveGoalCalendar: (goalCalendar: GoalCalendarItem[]) => Promise<boolean>
  onRevisionChange: (revision: RevisionIntelligence) => void
  onWriterWorkspaceChange: (workspace: WriterWorkspace) => void
}

export function AuthorWorkspaceDashboard({
  bookId,
  book,
  isDark,
  activeBookMode,
  canUseAuthorMode,
  modeSaving,
  canOpenManuscript,
  currentWords,
  targetWords,
  percentComplete,
  chapters,
  summaryCollection = null,
  unitTitle,
  unitPrefix,
  storyHealth,
  preWritingCheck,
  revisionIntelligence,
  writerWorkspace,
  continuityIssueCount,
  worldGapCount,
  timelineIssueCount,
  processingSummary,
  chapterCount,
  characterCount,
  worldArticleCount,
  loginStreakDays,
  weeklyLoginActivity,
  dailyWords,
  dailyTarget,
  userStats,
  saveState,
  saveMessage,
  storyHealthError,
  onRetryStoryHealth,
  preWritingCheckError,
  onRetryPreWritingCheck,
  revisionIntelligenceError,
  onRetryRevisionIntelligence,
  writerWorkspaceError,
  onRetryWriterWorkspace,
  onModeChange,
  onToggleTheme,
  onNavigate,
  onOpenManuscript,
  onOpenRelationships,
  onSaveGoalCalendar,
  onRevisionChange,
  onWriterWorkspaceChange,
}: Props) {
  const [activeTab, setActiveTab] = useState<AuthorDashboardTab>("planning")
  const [detailsOpen, setDetailsOpen] = useState(true)
  const [taskNotice, setTaskNotice] = useState<number | null>(null)
  const [coverUrlOverride, setCoverUrlOverride] = useState<string | null>(null)
  const deferedBookCoverUrl = coverUrlOverride !== null ? coverUrlOverride : book.cover_url
  const deferredStoryHealth = useDeferredValue(storyHealth)
  const deferredPreWritingCheck = useDeferredValue(preWritingCheck)
  const deferredRevisionIntelligence = useDeferredValue(revisionIntelligence)
  const deferredWriterWorkspace = useDeferredValue(writerWorkspace)
  const manuscriptRecap = buildManuscriptRecap(summaryCollection)
  const measuredChapters = chapters.filter((chapter) => typeof chapter.word_count === "number" && chapter.word_count > 0)
  const averageChapterWords = measuredChapters.length
    ? Math.round(measuredChapters.reduce((total, chapter) => total + (chapter.word_count ?? 0), 0) / measuredChapters.length)
    : null
  const calendarItems = deferredWriterWorkspace?.goal_calendar ?? []
  const activeCharacters = deferredPreWritingCheck?.active_characters ?? []

  useEffect(() => {
    if (taskNotice === null) return
    const timeoutId = window.setTimeout(() => setTaskNotice(null), 7000)
    return () => window.clearTimeout(timeoutId)
  }, [taskNotice])

  useEffect(() => {
    if (window.location.hash !== "#author-project-tasks") return
    setDetailsOpen(true)
    setActiveTab("planning")
    window.requestAnimationFrame(() => document.getElementById("author-project-tasks")?.scrollIntoView?.({ block: "start" }))
  }, [])

  const openTasks = () => {
    setDetailsOpen(true)
    setActiveTab("planning")
    setTaskNotice(null)
    window.requestAnimationFrame(() => document.getElementById("author-project-tasks")?.scrollIntoView?.({ block: "start", behavior: "smooth" }))
  }

  const openStats = () => {
    setDetailsOpen(true)
    setActiveTab("stats")
    window.requestAnimationFrame(() => document.getElementById("overview-tab-stats")?.scrollIntoView?.({ block: "start", behavior: "smooth" }))
  }

  return (
    <div className="space-y-5" data-author-overview>
      <OverviewHeader
        isDark={isDark}
        activeBookMode={activeBookMode}
        canUseAuthorMode={canUseAuthorMode}
        modeSaving={modeSaving}
        onModeChange={onModeChange}
        onToggleTheme={onToggleTheme}
      />

      {taskNotice !== null ? (
        <div
          role="status"
          className={`fixed bottom-4 left-4 right-4 z-50 flex max-w-sm flex-wrap items-center justify-between gap-4 rounded-lg border px-4 py-3 shadow-xl sm:bottom-6 sm:left-auto sm:right-6 ${isDark ? "border-teal-400/30 bg-[#10231f] text-slate-100" : "border-teal-200 bg-teal-50 text-stone-900"}`}
        >
          <div className="min-w-0">
            <p className="text-sm font-semibold">{taskNotice} task{taskNotice === 1 ? "" : "s"} added to Planning.</p>
            <p className={`mt-1 text-xs ${isDark ? "text-slate-300" : "text-stone-600"}`}>Find it under Revision tasks in Planning.</p>
          </div>
          <div className="flex items-center gap-3">
            <button type="button" onClick={openTasks} className={`text-sm font-semibold underline underline-offset-4 ${isDark ? "text-teal-200" : "text-teal-800"}`}>
              View tasks
            </button>
            <button
              type="button"
              aria-label="Dismiss task created notification"
              onClick={() => setTaskNotice(null)}
              className={`flex h-8 w-8 items-center justify-center rounded-full text-lg leading-none ${isDark ? "text-slate-300 hover:bg-white/10 hover:text-white" : "text-stone-500 hover:bg-black/5 hover:text-stone-900"}`}
            >
              ×
            </button>
          </div>
        </div>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(19rem,0.75fr)]">
        <CurrentProjectCard
          book={book}
          isDark={isDark}
          canOpenManuscript={canOpenManuscript}
          currentWords={currentWords}
          targetWords={targetWords}
          percentComplete={percentComplete}
          dailyWords={dailyWords}
          dailyTarget={dailyTarget}
          loginStreakDays={loginStreakDays}
          onOpenManuscript={onOpenManuscript}
          bookId={bookId}
          resolvedCoverUrl={deferedBookCoverUrl}
          onCoverUpdated={(updated) => setCoverUrlOverride(updated.cover_url ?? null)}
          manuscriptRecap={manuscriptRecap?.content ?? null}
          recapChapterCount={manuscriptRecap?.chapterCount ?? 0}
        />
        <RecentChaptersCard
          book={book}
          isDark={isDark}
          chapters={chapters}
          unitTitle={unitTitle}
          unitPrefix={unitPrefix}
          onNavigate={onNavigate}
          bookId={bookId}
        />
      </section>

      <AuthorOverviewTab
        isDark={isDark}
        currentWords={currentWords}
        targetWords={targetWords}
        chapterCount={chapterCount}
        characterCount={characterCount}
        worldArticleCount={worldArticleCount}
        percentComplete={percentComplete}
        dailyWords={dailyWords}
        dailyTarget={dailyTarget}
        loginStreakDays={loginStreakDays}
        weeklyLoginActivity={weeklyLoginActivity}
        totalRevisionItems={deferredRevisionIntelligence?.summary.active_item_count ?? null}
        highSeverityItems={deferredRevisionIntelligence?.summary.high_severity_count ?? null}
        chapters={chapters}
        unitTitle={unitTitle}
        onNavigate={onNavigate}
        onOpenManuscript={onOpenManuscript}
        canOpenManuscript={canOpenManuscript}
        onOpenStats={openStats}
        bookId={bookId}
      />

      <Suspense fallback={<Skeleton variant="card" className="min-h-72" />}>
        <section className="grid gap-4 xl:grid-cols-[minmax(19rem,0.72fr)_minmax(0,1.25fr)_minmax(18rem,0.72fr)]">
          <ActiveIssuesCard
            isDark={isDark}
            continuityIssueCount={continuityIssueCount}
            worldGapCount={worldGapCount}
            timelineIssueCount={timelineIssueCount}
            onNavigate={onNavigate}
            bookId={bookId}
            processingSummary={processingSummary}
          />
          {deferredRevisionIntelligence ? (
            <RevisionIntelligencePanel
              bookId={bookId}
              revision={deferredRevisionIntelligence}
              writerWorkspace={deferredWriterWorkspace}
              isDark={isDark}
              onRevisionChange={onRevisionChange}
              onWriterWorkspaceChange={onWriterWorkspaceChange}
              variant="preview"
            />
          ) : revisionIntelligenceError && onRetryRevisionIntelligence ? (
            <ErrorCard variant="compact" isDark={isDark} message="Revision intelligence could not be loaded." onRetry={onRetryRevisionIntelligence} />
          ) : (
            <RevisionPreviewPlaceholder isDark={isDark} />
          )}
          <StoryPulseCard
            bookId={bookId}
            isDark={isDark}
            storyHealth={deferredStoryHealth}
            storyHealthError={storyHealthError}
            onRetryStoryHealth={onRetryStoryHealth}
          />
        </section>
      </Suspense>

      <details
        className={panelClass(isDark, "overflow-hidden")}
        data-testid="author-workspace-details"
        open={detailsOpen}
        onToggle={(event) => setDetailsOpen(event.currentTarget.open)}
      >
        <summary className={`flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-4 sm:px-5 ${isDark ? "hover:bg-white/[0.03]" : "hover:bg-stone-50"}`}>
          <span>
            <span className={`block text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Author command center</span>
            <span className={`mt-1 block text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>Planning, story structure, and writing statistics</span>
          </span>
          <span aria-hidden="true" className={`text-lg ${isDark ? "text-slate-400" : "text-stone-500"}`}>{detailsOpen ? "−" : "+"}</span>
        </summary>

        {detailsOpen ? (
          <div className={`border-t px-4 pb-5 pt-4 sm:px-5 ${isDark ? "border-white/[0.07]" : "border-stone-200"}`}>
          <div role="tablist" aria-label="Author command center" className={`flex gap-5 overflow-x-auto border-b ${isDark ? "border-white/[0.08]" : "border-stone-200"}`}>
            {DETAIL_TABS.map(([tab, label]) => (
              <button
                key={tab}
                type="button"
                role="tab"
                id={`overview-tab-${tab}`}
                aria-controls="overview-details-panel"
                tabIndex={activeTab === tab ? 0 : -1}
                aria-selected={activeTab === tab}
                onKeyDown={(event) => {
                  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return
                  event.preventDefault()
                  const index = DETAIL_TABS.findIndex(([value]) => value === tab)
                  const next = event.key === "Home" ? 0 : event.key === "End" ? DETAIL_TABS.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + DETAIL_TABS.length) % DETAIL_TABS.length
                  setActiveTab(DETAIL_TABS[next][0])
                  document.getElementById(`overview-tab-${DETAIL_TABS[next][0]}`)?.focus()
                }}
                onClick={() => setActiveTab(tab)}
                className={`border-b-2 px-1 pb-3 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-teal-500/60 ${
                  activeTab === tab
                    ? isDark ? "border-teal-300 text-white" : "border-teal-800 text-stone-950"
                    : isDark ? "border-transparent text-slate-400 hover:text-white" : "border-transparent text-stone-500 hover:text-stone-950"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {activeTab === "planning" ? (
            <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Workspace snapshot">
              <section className={`rounded-md border p-4 ${isDark ? "border-white/10 bg-white/[0.02]" : "border-stone-200 bg-stone-50"}`}>
                <h3 className="font-serif text-base font-semibold">Goal Calendar</h3>
                <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{deferredWriterWorkspace ? `${calendarItems.length} planning item${calendarItems.length === 1 ? "" : "s"} · ${calendarItems.filter((item) => !item.completed).length} open` : "Planning data is unavailable"}</p>
                <button type="button" onClick={() => document.getElementById("author-goal-calendar")?.scrollIntoView?.({ block: "start", behavior: "smooth" })} className={`mt-4 text-sm font-semibold ${isDark ? "text-teal-300" : "text-teal-800"}`}>View calendar →</button>
              </section>
              <section className={`rounded-md border p-4 ${isDark ? "border-white/10 bg-white/[0.02]" : "border-stone-200 bg-stone-50"}`}>
                <h3 className="font-serif text-base font-semibold">Active story cast</h3>
                <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{deferredPreWritingCheck ? activeCharacters.length ? activeCharacters.slice(0, 3).map((character) => character.name).join(", ") : "No active characters identified" : "Story cast is unavailable"}</p>
                <button type="button" onClick={() => setActiveTab("story-map")} className={`mt-4 text-sm font-semibold ${isDark ? "text-teal-300" : "text-teal-800"}`}>Open story map →</button>
              </section>
              <section className={`rounded-md border p-4 ${isDark ? "border-white/10 bg-white/[0.02]" : "border-stone-200 bg-stone-50"}`}>
                <h3 className="font-serif text-base font-semibold">Chapter length</h3>
                <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{averageChapterWords === null ? "No measured chapters yet" : `${averageChapterWords.toLocaleString()} words on average across ${measuredChapters.length} measured ${measuredChapters.length === 1 ? "chapter" : "chapters"}`}</p>
                <button type="button" onClick={openStats} className={`mt-4 text-sm font-semibold ${isDark ? "text-teal-300" : "text-teal-800"}`}>View chapter breakdown →</button>
              </section>
              <section className={`rounded-md border p-4 ${isDark ? "border-white/10 bg-white/[0.02]" : "border-stone-200 bg-stone-50"}`}>
                <h3 className="font-serif text-base font-semibold">Writing activity</h3>
                <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{userStats ? `${userStats.writing.last_7_days.words.toLocaleString()} words in the last 7 days across your workspace` : "Writing activity is unavailable"}</p>
                <button type="button" onClick={openStats} className={`mt-4 text-sm font-semibold ${isDark ? "text-teal-300" : "text-teal-800"}`}>View statistics →</button>
              </section>
            </div>
          ) : null}
          <div id="overview-details-panel" role="tabpanel" aria-labelledby={`overview-tab-${activeTab}`} tabIndex={0} className="mt-5">
          {activeTab === "planning" ? (
            <PlanningTab
              isDark={isDark}
              writerWorkspace={deferredWriterWorkspace}
              revisionIntelligence={deferredRevisionIntelligence}
              currentWords={currentWords}
              targetWords={targetWords}
              chapterCount={chapterCount}
              dailyWords={dailyWords}
              dailyTarget={dailyTarget}
              loginStreakDays={loginStreakDays}
              saveState={saveState}
              saveMessage={saveMessage}
              onSaveGoalCalendar={onSaveGoalCalendar}
              onOpenManuscript={onOpenManuscript}
              writerWorkspaceError={writerWorkspaceError}
              onRetryWriterWorkspace={onRetryWriterWorkspace}
            />
          ) : null}

          {activeTab === "story-map" ? (
            <StoryMapTab
              isDark={isDark}
              bookId={bookId}
              preWritingCheck={deferredPreWritingCheck}
              revisionIntelligence={deferredRevisionIntelligence}
              writerWorkspace={deferredWriterWorkspace}
              onOpenRelationships={onOpenRelationships}
              onNavigate={onNavigate}
              onRevisionChange={onRevisionChange}
              onWriterWorkspaceChange={onWriterWorkspaceChange}
              onTaskCreated={(count) => setTaskNotice(count)}
              preWritingCheckError={preWritingCheckError}
              onRetryPreWritingCheck={onRetryPreWritingCheck}
              revisionIntelligenceError={revisionIntelligenceError}
              onRetryRevisionIntelligence={onRetryRevisionIntelligence}
            />
          ) : null}

          {activeTab === "stats" ? (
            <WorkspaceStatsTab
              isDark={isDark}
              currentWords={currentWords}
              targetWords={targetWords}
              chapterCount={chapterCount}
              characterCount={characterCount}
              worldArticleCount={worldArticleCount}
              percentComplete={percentComplete}
              chapters={chapters}
              dailyWords={dailyWords}
              dailyTarget={dailyTarget}
              userStats={userStats}
              loginStreakDays={loginStreakDays}
              weeklyLoginActivity={weeklyLoginActivity}
              onOpenManuscript={onOpenManuscript}
            />
          ) : null}
          </div>
        </div>
        ) : null}
      </details>
    </div>
  )
}
