"use client"

import React, { Suspense, useDeferredValue, useState } from "react"

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
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [coverUrlOverride, setCoverUrlOverride] = useState<string | null>(null)
  const deferedBookCoverUrl = coverUrlOverride !== null ? coverUrlOverride : book.cover_url
  const deferredStoryHealth = useDeferredValue(storyHealth)
  const deferredPreWritingCheck = useDeferredValue(preWritingCheck)
  const deferredRevisionIntelligence = useDeferredValue(revisionIntelligence)
  const deferredWriterWorkspace = useDeferredValue(writerWorkspace)
  const manuscriptRecap = buildManuscriptRecap(summaryCollection)
  return (
    <div className="space-y-4">
      <OverviewHeader
        isDark={isDark}
        activeBookMode={activeBookMode}
        canUseAuthorMode={canUseAuthorMode}
        modeSaving={modeSaving}
        onModeChange={onModeChange}
        onToggleTheme={onToggleTheme}
      />

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
        onToggle={(event) => setDetailsOpen(event.currentTarget.open)}
      >
        <summary className={`flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-4 sm:px-5 ${isDark ? "hover:bg-white/[0.03]" : "hover:bg-stone-50"}`}>
          <span>
            <span className={`block text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Project details</span>
            <span className={`mt-1 block text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>Goals, story structure, and writing statistics</span>
          </span>
          <span aria-hidden="true" className={`text-lg ${isDark ? "text-slate-400" : "text-stone-500"}`}>{detailsOpen ? "−" : "+"}</span>
        </summary>

        {detailsOpen ? (
          <div className={`border-t px-4 pb-5 pt-4 sm:px-5 ${isDark ? "border-white/[0.07]" : "border-stone-200"}`}>
          <div role="tablist" aria-label="Project details" className={`flex gap-5 overflow-x-auto border-b ${isDark ? "border-white/[0.08]" : "border-stone-200"}`}>
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
          <div id="overview-details-panel" role="tabpanel" aria-labelledby={`overview-tab-${activeTab}`} tabIndex={0} className="mt-5">
          {activeTab === "planning" ? (
            <PlanningTab
              isDark={isDark}
              writerWorkspace={deferredWriterWorkspace}
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
              onOpenRelationships={onOpenRelationships}
              onNavigate={onNavigate}
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
