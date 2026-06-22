"use client"

import React, { Suspense, useDeferredValue, useState } from "react"

import { panelClass } from "@/components/overview/utils"
import { RevisionIntelligencePanel } from "@/components/revision/RevisionIntelligencePanel"
import { Skeleton } from "@/components/ui/Skeleton"
import {
  ActiveIssuesCard,
  CompactQuickLinksCard,
  CurrentProjectCard,
  OverviewHeader,
  RecentChaptersCard,
  RecentSignalsCard,
  RevisionPreviewPlaceholder,
  StoryPulseCard,
} from "./AuthorDashboardPrimaryPanels"
import {
  AuthorOverviewTab,
  PlanningTab,
  RevisionHubTab,
  StoryMapTab,
  WorkspaceStatsTab,
} from "./AuthorDashboardTabs"
import type { Book, GoalCalendarItem, PreWritingCheck, RevisionActionItem, RevisionIntelligence, StoryHealth, UserStats, WriterWorkspace } from "@/types/book"
import type { ChapterListResponse } from "@/types/reader"

type IconName =
  | "analysis"
  | "book"
  | "calendar"
  | "chat"
  | "chevron"
  | "edit"
  | "file"
  | "flame"
  | "gap"
  | "graph"
  | "moon"
  | "pen"
  | "search"
  | "spark"
  | "sun"
  | "timeline"
  | "users"
  | "voice"

type WorkspaceSaveState = "idle" | "saving" | "saved" | "error"
type AuthorDashboardTab = "overview" | "revision" | "planning" | "story-map" | "stats"
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
  targetWords: number
  percentComplete: number
  chapters: ChapterListResponse["chapters"]
  unitTitle: string
  unitPrefix: string
  storyHealth: StoryHealth | null
  preWritingCheck: PreWritingCheck | null
  revisionIntelligence: RevisionIntelligence | null
  writerWorkspace: WriterWorkspace | null
  continuityIssueCount: number
  worldGapCount: number
  timelineIssueCount: number
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
  greetingName,
  canOpenManuscript,
  currentWords,
  targetWords,
  percentComplete,
  chapters,
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
  const [activeTab, setActiveTab] = useState<AuthorDashboardTab>("overview")
  const [coverUrlOverride, setCoverUrlOverride] = useState<string | null>(null)
  const deferedBookCoverUrl = coverUrlOverride !== null ? coverUrlOverride : book.cover_url
  const deferredStoryHealth = useDeferredValue(storyHealth)
  const deferredPreWritingCheck = useDeferredValue(preWritingCheck)
  const deferredRevisionIntelligence = useDeferredValue(revisionIntelligence)
  const deferredWriterWorkspace = useDeferredValue(writerWorkspace)
  const recentAlerts = preWritingCheck?.alerts ?? []
  const quickLinks = [
    { title: "Story Advisor", body: "Ask for revision guidance and continuity checks.", href: `/${bookId}/advisor`, icon: "graph" as IconName },
    { title: "Ask LoreVia", body: "Search the manuscript memory without leaving the workspace.", href: `/${bookId}/ask`, icon: "chat" as IconName },
    { title: "Character Graph", body: "Open the relationship map for cast-level context.", href: `/${bookId}/graph`, icon: "users" as IconName },
    { title: "Timeline", body: "Review event order and pressure points.", href: `/${bookId}/timeline`, icon: "timeline" as IconName },
  ]
  const totalRevisionItems = deferredRevisionIntelligence?.summary.active_item_count ?? continuityIssueCount + worldGapCount + timelineIssueCount
  const highSeverityItems = deferredRevisionIntelligence?.summary.high_severity_count ?? continuityIssueCount

  return (
    <div className="space-y-4">
      <OverviewHeader
        isDark={isDark}
        activeBookMode={activeBookMode}
        canUseAuthorMode={canUseAuthorMode}
        modeSaving={modeSaving}
        greetingName={greetingName}
        onModeChange={onModeChange}
        onToggleTheme={onToggleTheme}
      />

      <section className="grid gap-5 xl:auto-rows-fr xl:grid-cols-[minmax(0,1.32fr)_minmax(18rem,0.86fr)_minmax(17.5rem,0.82fr)]">
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
          onOpenRelationships={onOpenRelationships}
          onNavigate={onNavigate}
          bookId={bookId}
          resolvedCoverUrl={deferedBookCoverUrl}
          onCoverUpdated={(updated) => setCoverUrlOverride(updated.cover_url ?? null)}
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
        <StoryPulseCard
          bookId={bookId}
          isDark={isDark}
          storyHealth={deferredStoryHealth}
          storyHealthError={storyHealthError}
          onRetryStoryHealth={onRetryStoryHealth}
        />
      </section>

      <Suspense fallback={<Skeleton variant="card" className="min-h-72" />}>
        <section className="grid gap-5 xl:auto-rows-fr xl:grid-cols-[minmax(18rem,0.92fr)_minmax(0,1.12fr)_minmax(17rem,0.8fr)]">
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
        ) : (
          <RevisionPreviewPlaceholder isDark={isDark} />
        )}
        <div className="grid auto-rows-fr gap-5">
          <CompactQuickLinksCard isDark={isDark} links={quickLinks} onNavigate={onNavigate} />
          <RecentSignalsCard
            isDark={isDark}
            unitTitle={unitTitle}
            recentAlerts={recentAlerts}
            chapters={chapters}
            onNavigate={onNavigate}
            bookId={bookId}
            preWritingCheckError={preWritingCheckError}
            onRetryPreWritingCheck={onRetryPreWritingCheck}
          />
        </div>
      </section>
      </Suspense>

      <section className={panelClass(isDark, "overflow-hidden p-4 sm:p-5")} data-testid="author-workspace-tabs">
        <div className="grid gap-4 border-b border-white/[0.06] pb-4 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1fr)] lg:items-end">
          <div>
            <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Secondary workspace</p>
            <h2 className={`mt-2 font-serif text-3xl leading-none ${isDark ? "text-white" : "text-slate-900"}`}>
              {activeTab === "planning" ? "Plan with intent. Write with momentum." : "Your author command center."}
            </h2>
            <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-500"}`}>
              {activeTab === "planning"
                ? "Align goals, schedule sessions, and protect the manuscript from drift."
                : "Deep tools for planning, structure, and story intelligence."}
            </p>
          </div>
          <div role="tablist" aria-label="Author workspace tabs" className={`grid gap-1 rounded-md border p-1 sm:grid-cols-3 xl:grid-cols-5 ${isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-slate-200 bg-slate-50"}`}>
            {([
              ["overview", "Overview"],
              ["revision", "Revision Hub"],
              ["planning", "Planning"],
              ["story-map", "Story Map"],
              ["stats", "Workspace Stats"],
            ] as const).map(([tab, label]) => (
              <button
                key={tab}
                type="button"
                role="tab"
                aria-selected={activeTab === tab}
                onClick={() => setActiveTab(tab)}
                className={`rounded-xl px-3 py-2.5 text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-teal-500/60 ${
                  activeTab === tab
                    ? "bg-teal-800 text-white"
                    : isDark ? "text-slate-300 hover:bg-white/[0.06]" : "text-slate-600 hover:bg-white"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-5">
          {activeTab === "overview" ? (
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
              totalRevisionItems={totalRevisionItems}
              highSeverityItems={highSeverityItems}
              chapters={chapters}
              unitTitle={unitTitle}
              onNavigate={onNavigate}
              onOpenManuscript={onOpenManuscript}
              bookId={bookId}
            />
          ) : null}

          {activeTab === "revision" ? (
            <RevisionHubTab
              bookId={bookId}
              isDark={isDark}
              revisionIntelligence={deferredRevisionIntelligence}
              writerWorkspace={deferredWriterWorkspace}
              chapters={chapters}
              storyHealth={deferredStoryHealth}
              onRevisionChange={onRevisionChange}
              onWriterWorkspaceChange={onWriterWorkspaceChange}
              revisionIntelligenceError={revisionIntelligenceError}
              onRetryRevisionIntelligence={onRetryRevisionIntelligence}
              writerWorkspaceError={writerWorkspaceError}
              onRetryWriterWorkspace={onRetryWriterWorkspace}
              storyHealthError={storyHealthError}
              onRetryStoryHealth={onRetryStoryHealth}
            />
          ) : null}

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
      </section>
    </div>
  )
}
